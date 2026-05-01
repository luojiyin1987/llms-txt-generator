#!/usr/bin/env python3
"""One-shot orchestration for llms.txt generation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from crawl_site import read_with_dokobot
from llms_site_lib import (
    build_clean_page_payload,
    build_robots_parser,
    can_fetch_with_robots,
    infer_target_from_markdown_path,
    is_url,
    load_page_json,
    normalize_url,
    read_text_source,
    resolve_readme_source,
    safe_filename,
    write_json,
)

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--site-url", help="Seed website or docs URL.")
    group.add_argument("--sitemap", help="Sitemap URL or local XML file.")
    group.add_argument("--readme", help="README markdown file or URL.")
    group.add_argument("--docs-dir", help="Local docs directory containing markdown files.")
    parser.add_argument("--output-dir", default="out", help="Final output directory.")
    parser.add_argument("--artifacts-dir", default="artifacts", help="Intermediate artifact directory.")
    parser.add_argument(
        "--allow-domain", action="append", default=[], help="Additional allowed domain. Can be passed more than once."
    )
    parser.add_argument("--base-url", help="Base URL used to resolve relative links.")
    parser.add_argument("--repo-url", help="Repo URL used to map local docs paths to blob URLs.")
    parser.add_argument("--project-title", help="Explicit project title used as the llms.txt H1.")
    parser.add_argument("--project-summary", help="Explicit project summary used as the llms.txt blockquote.")
    parser.add_argument("--with-full", action="store_true", help="Emit llms-full.txt.")
    parser.add_argument("--with-sitemap-summary", action="store_true", help="Emit sitemap-summary.md.")
    parser.add_argument("--with-ai-suggestions", action="store_true", help="Emit ai-content-suggestions.md.")
    parser.add_argument("--page-json-dir", help="Override cleaned page JSON directory.")
    parser.add_argument("--max-pages", type=int, default=20, help="Maximum pages to fetch for live site discovery.")
    parser.add_argument("--dokobot-command", default="dokobot", help="Dokobot executable name or path.")
    parser.add_argument("--dokobot-local", action="store_true", help="Use dokobot local mode.")
    parser.add_argument("--dokobot-timeout", type=int, default=120, help="Dokobot timeout in seconds.")
    parser.add_argument("--dokobot-screens", type=int, default=2, help="Dokobot screens to capture per page.")
    parser.add_argument("--ignore-robots", action="store_true", help="Ignore robots.txt during live site discovery.")
    return parser.parse_args()


def run_command(args: list[str]) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def load_existing_payloads(page_json_dir: Path) -> dict[str, dict]:
    page_map: dict[str, dict] = {}
    for path in sorted(page_json_dir.glob("*.json")):
        payload = load_page_json(path)
        source_url = normalize_url(payload.get("source_url", ""))
        if source_url:
            page_map[source_url] = payload
    return page_map


def write_payload(page_json_dir: Path, payload: dict, index: int) -> None:
    filename = safe_filename(payload.get("title") or payload.get("source_url", "page"))
    write_json(page_json_dir / f"{index:03d}-{filename}.json", payload)


def seed_docs_dir_payloads(args: argparse.Namespace, page_json_dir: Path, existing: dict[str, dict]) -> None:
    if not args.docs_dir:
        return
    docs_path = Path(args.docs_dir)
    next_index = len(existing) + 1
    for path in sorted(docs_path.rglob("*.md")):
        target = infer_target_from_markdown_path(
            path.relative_to(docs_path), base_url=args.base_url, repo_url=args.repo_url
        )
        normalized_target = normalize_url(target)
        if normalized_target in existing:
            continue
        text = path.read_text(encoding="utf-8")
        payload = build_clean_page_payload(text, normalized_target or path.as_posix(), source="docs-dir")
        existing[normalized_target] = payload
        write_payload(page_json_dir, payload, next_index)
        next_index += 1


def seed_readme_payload(args: argparse.Namespace, page_json_dir: Path, existing: dict[str, dict]) -> None:
    if not args.readme:
        return
    target = normalize_url(args.readme, base_url=args.base_url)
    if target in existing:
        return
    text = read_text_source(resolve_readme_source(args.readme))
    payload = build_clean_page_payload(text, target or args.readme, source="readme")
    existing[target] = payload
    write_payload(page_json_dir, payload, len(existing))


def ensure_full_payloads(plan: dict, args: argparse.Namespace, page_json_dir: Path) -> None:
    existing = load_existing_payloads(page_json_dir)
    seed_docs_dir_payloads(args, page_json_dir, existing)
    seed_readme_payload(args, page_json_dir, existing)

    robots_cache: dict[str, object] = {}
    missing: list[str] = []
    next_index = len(existing) + 1

    for page in plan["pages"]:
        if page["decision"] not in {"include", "optional"}:
            continue
        target = normalize_url(page["target"])
        if target in existing:
            continue
        if not is_url(target):
            missing.append(target)
            continue

        if not args.ignore_robots:
            host_key = "/".join(target.split("/", 3)[:3])
            if host_key not in robots_cache:
                robots_cache[host_key] = build_robots_parser(target)
            if not can_fetch_with_robots(robots_cache[host_key], target):
                missing.append(target)
                continue

        try:
            raw_text = read_with_dokobot(target, args)
        except subprocess.CalledProcessError as exc:
            print(f"Warning: dokobot failed for {target}: {exc}", file=sys.stderr)
            missing.append(target)
            continue
        if not raw_text.strip():
            missing.append(target)
            continue

        payload = build_clean_page_payload(raw_text, target, source="full-fetch")
        existing[target] = payload
        write_payload(page_json_dir, payload, next_index)
        next_index += 1

    if missing:
        print("Warning: unable to prepare llms-full.txt content for: " + ", ".join(missing), file=sys.stderr)


def main() -> int:
    args = parse_args()
    artifacts_dir = Path(args.artifacts_dir)
    page_json_dir = Path(args.page_json_dir) if args.page_json_dir else artifacts_dir / "clean"
    page_json_dir.mkdir(parents=True, exist_ok=True)
    plan_path = artifacts_dir / "plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)

    crawl_cmd = [sys.executable, str(SCRIPTS / "crawl_site.py")]
    for name in (
        "site_url",
        "sitemap",
        "readme",
        "docs_dir",
        "base_url",
        "repo_url",
        "project_title",
        "project_summary",
    ):
        value = getattr(args, name)
        if value:
            crawl_cmd.extend([f"--{name.replace('_', '-')}", value])
    for domain in args.allow_domain:
        crawl_cmd.extend(["--allow-domain", domain])
    crawl_cmd.extend(
        [
            "--page-json-dir",
            str(page_json_dir),
            "--max-pages",
            str(args.max_pages),
            "--dokobot-command",
            args.dokobot_command,
            "--dokobot-timeout",
            str(args.dokobot_timeout),
            "--dokobot-screens",
            str(args.dokobot_screens),
            "--output",
            str(plan_path),
        ]
    )
    if args.dokobot_local:
        crawl_cmd.append("--dokobot-local")
    if args.ignore_robots:
        crawl_cmd.append("--ignore-robots")
    run_command(crawl_cmd)

    if args.with_full:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        ensure_full_payloads(plan, args, page_json_dir)

    build_cmd = [
        sys.executable,
        str(SCRIPTS / "build_llms_txt.py"),
        "--plan",
        str(plan_path),
        "--page-json-dir",
        str(page_json_dir),
        "--output-dir",
        args.output_dir,
    ]
    if args.with_full:
        build_cmd.append("--with-full")
    if args.with_sitemap_summary:
        build_cmd.append("--with-sitemap-summary")
    if args.with_ai_suggestions:
        build_cmd.append("--with-ai-suggestions")
    run_command(build_cmd)

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    sys.stdout.write(
        json.dumps(
            {"plan": str(plan_path), "output_dir": args.output_dir, "stats": plan.get("stats", {})},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
