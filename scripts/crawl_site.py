#!/usr/bin/env python3
"""Build a curated page plan from a site, sitemap, README, or docs directory."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import deque
from pathlib import Path
from urllib.parse import urlparse

from llms_site_lib import (
    PageRecord,
    build_clean_page_payload,
    build_robots_parser,
    can_fetch_with_robots,
    classify_target,
    derive_allowed_hosts,
    description_quality,
    extract_markdown_links,
    extract_title_and_summary,
    filter_records_by_hosts,
    group_records,
    hostname_of,
    infer_target_from_markdown_path,
    is_url,
    load_page_json,
    normalize_url,
    parse_sitemap_xml,
    read_text_source,
    record_priority,
    resolve_readme_source,
    safe_filename,
    summarize_content,
    title_quality,
    unique_records,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--site-url", help="Seed website or docs URL.")
    group.add_argument("--sitemap", help="Sitemap URL or local XML file.")
    group.add_argument("--readme", help="README markdown file or URL.")
    group.add_argument("--docs-dir", help="Local docs directory containing markdown files.")
    parser.add_argument(
        "--seed-file", action="append", default=[], help="Cleaned page JSON file(s) from clean_markdown.py."
    )
    parser.add_argument(
        "--allow-domain", action="append", default=[], help="Additional allowed domain. Can be passed more than once."
    )
    parser.add_argument("--base-url", help="Base URL used to resolve relative links.")
    parser.add_argument("--repo-url", help="Repo URL used to map local docs paths to blob URLs.")
    parser.add_argument("--project-title", help="Explicit project title used as the llms.txt H1.")
    parser.add_argument("--project-summary", help="Explicit project summary used as the llms.txt blockquote.")
    parser.add_argument("--page-json-dir", help="Directory for cleaned crawled page JSON files.")
    parser.add_argument("--max-pages", type=int, default=20, help="Maximum live pages to fetch for site-url discovery.")
    parser.add_argument("--dokobot-command", default="dokobot", help="Dokobot executable name or path.")
    parser.add_argument("--dokobot-local", action="store_true", help="Use dokobot local mode.")
    parser.add_argument("--dokobot-timeout", type=int, default=120, help="Dokobot timeout in seconds.")
    parser.add_argument("--dokobot-screens", type=int, default=2, help="Dokobot screens to capture per page.")
    parser.add_argument("--ignore-robots", action="store_true", help="Ignore robots.txt during live site discovery.")
    parser.add_argument("--output", help="Write plan JSON to this path.")
    return parser.parse_args()


def records_from_sitemap(source: str) -> list[PageRecord]:
    try:
        text = read_text_source(source)
    except Exception as exc:
        print(f"Warning: unable to fetch sitemap {source}: {exc}", file=sys.stderr)
        return []
    urls = parse_sitemap_xml(text)
    records: list[PageRecord] = []
    for url in urls:
        normalized = normalize_url(url)
        title = Path(normalized).name.replace("-", " ").replace("_", " ").strip() or normalized
        section, decision, reason = classify_target(normalized, title=title)
        records.append(
            PageRecord(
                target=normalized,
                title=title.title(),
                description="",
                section=section,
                decision=decision,
                reason=reason,
                source="sitemap",
            )
        )
    return records


def records_from_seed_files(seed_files: list[str], site_url: str | None = None) -> list[PageRecord]:
    payloads: list[dict] = []
    for seed_file in seed_files:
        try:
            payloads.append(load_page_json(seed_file))
        except Exception as exc:
            print(f"Warning: unable to load seed file {seed_file}: {exc}", file=sys.stderr)
    return records_from_seed_payloads(payloads, site_url=site_url)


def records_from_seed_payloads(seed_payloads: list[dict], site_url: str | None = None) -> list[PageRecord]:
    records: list[PageRecord] = []
    if site_url:
        section, decision, reason = classify_target(site_url, title="")
        records.append(
            PageRecord(
                target=normalize_url(site_url),
                title="Home",
                description="Primary docs entry point.",
                section=section,
                decision=decision,
                reason=reason,
                source="site-url",
            )
        )
    for payload in seed_payloads:
        source_url = payload.get("source_url") or site_url or ""
        title = payload.get("title") or "Untitled"
        summary = payload.get("summary") or summarize_content(payload.get("content", ""))
        if source_url:
            section, decision, reason = classify_target(source_url, title=title)
            records.append(
                PageRecord(
                    target=normalize_url(source_url),
                    title=title,
                    description=summary,
                    section=section,
                    decision=decision,
                    reason=reason,
                    source="seed-page",
                )
            )
        for link in payload.get("links", []):
            target = normalize_url(link.get("target", ""), base_url=source_url or site_url)
            if not target:
                continue
            label = link.get("title") or Path(target).name or target
            section, decision, reason = classify_target(target, title=label)
            records.append(
                PageRecord(
                    target=target,
                    title=label,
                    description="",
                    section=section,
                    decision=decision,
                    reason=reason,
                    source="seed-link",
                )
            )
    return records


def read_with_dokobot(url: str, args: argparse.Namespace) -> str:
    command = [
        args.dokobot_command,
        "doko",
        "read",
        url,
        "--timeout",
        str(args.dokobot_timeout),
        "--screens",
        str(args.dokobot_screens),
    ]
    if args.dokobot_local:
        command.append("--local")
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    text = result.stdout.strip()
    if not text:
        return ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(payload, dict) and isinstance(payload.get("text"), str):
        return payload["text"]
    return text


def crawl_live_site(args: argparse.Namespace, allowed_hosts: set[str]) -> tuple[list[dict], dict[str, int]]:
    page_json_dir = Path(args.page_json_dir) if args.page_json_dir else None
    if page_json_dir:
        page_json_dir.mkdir(parents=True, exist_ok=True)

    robots_parser = None if args.ignore_robots else build_robots_parser(args.site_url)
    queue: deque[str] = deque([normalize_url(args.site_url)])
    seen: set[str] = set()
    payloads: list[dict] = []
    stats = {"robots_blocked": 0, "fetch_errors": 0, "crawled_pages": 0}

    while queue and len(payloads) < args.max_pages:
        url = normalize_url(queue.popleft())
        if not url or url in seen:
            continue
        seen.add(url)
        if not can_fetch_with_robots(robots_parser, url):
            stats["robots_blocked"] += 1
            continue

        try:
            raw_text = read_with_dokobot(url, args)
        except subprocess.CalledProcessError:
            stats["fetch_errors"] += 1
            continue
        if not raw_text.strip():
            continue

        payload = build_clean_page_payload(raw_text, url, source="dokobot")
        payloads.append(payload)
        stats["crawled_pages"] += 1

        if page_json_dir:
            filename = safe_filename(payload["title"] or url.rsplit("/", 1)[-1])
            write_json(page_json_dir / f"{len(payloads):03d}-{filename}.json", payload)

        for link in payload.get("links", []):
            target = normalize_url(link.get("target", ""), base_url=url)
            if not target or target in seen or target in queue:
                continue
            if not filter_records_by_hosts(
                [
                    PageRecord(
                        target=target,
                        title="",
                        description="",
                        section="",
                        decision="include",
                        reason="",
                        source="crawl-link",
                    )
                ],
                allowed_hosts,
            )[0]:
                continue
            section, decision, _ = classify_target(target, title=link.get("title", ""))
            if decision == "exclude":
                continue
            queue.append(target)

    return payloads, stats


def records_from_readme(source: str, base_url: str | None = None) -> list[PageRecord]:
    try:
        text = read_text_source(resolve_readme_source(source))
    except Exception as exc:
        print(f"Warning: unable to fetch README {source}: {exc}", file=sys.stderr)
        return []
    title, summary = extract_title_and_summary(text)
    records: list[PageRecord] = [
        PageRecord(
            target=normalize_url(source, base_url=base_url),
            title=title,
            description=summary,
            section="Docs",
            decision="include",
            reason="primary README",
            source="readme",
        )
    ]
    for link in extract_markdown_links(text, base_url=(base_url or source) if is_url(source) else None):
        section, decision, reason = classify_target(link["target"], title=link["title"])
        records.append(
            PageRecord(
                target=link["target"],
                title=link["title"] or Path(link["target"]).name,
                description="",
                section=section,
                decision=decision,
                reason=reason,
                source="readme-link",
            )
        )
    return records


def keep_readme_link_record(record: PageRecord) -> bool:
    if record.source != "readme-link":
        return True
    if record.decision == "exclude":
        return False
    if is_url(record.target):
        parsed = urlparse(record.target)
        host = (parsed.hostname or "").lower()
        path_parts = [part.lower() for part in parsed.path.split("/") if part]
        if host in {"github.com", "gitlab.com"} and any(
            part in {"issues", "pull", "pulls", "discussions", "actions", "compare"} for part in path_parts
        ):
            return False
    return True


def records_from_docs_dir(directory: str, base_url: str | None = None, repo_url: str | None = None) -> list[PageRecord]:
    docs_path = Path(directory)
    records: list[PageRecord] = []
    for path in sorted(docs_path.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        title, summary = extract_title_and_summary(text)
        target = infer_target_from_markdown_path(path.relative_to(docs_path), base_url=base_url, repo_url=repo_url)
        section, decision, reason = classify_target(target, title=title)
        records.append(
            PageRecord(
                target=target,
                title=title,
                description=summary,
                section=section,
                decision=decision,
                reason=reason,
                source="docs-dir",
            )
        )
        for link in extract_markdown_links(text, base_url=base_url):
            link_section, link_decision, link_reason = classify_target(link["target"], title=link["title"])
            records.append(
                PageRecord(
                    target=link["target"],
                    title=link["title"] or Path(link["target"]).name,
                    description="",
                    section=link_section,
                    decision=link_decision,
                    reason=link_reason,
                    source="docs-link",
                )
            )
    return records


def enrich_descriptions(records: list[PageRecord], seed_files: list[str]) -> list[PageRecord]:
    description_map: dict[str, str] = {}
    title_map: dict[str, str] = {}
    for seed_file in seed_files:
        payload = load_page_json(seed_file)
        source_url = normalize_url(payload.get("source_url", ""))
        if not source_url:
            continue
        if payload.get("summary"):
            description_map[source_url] = payload["summary"]
        if payload.get("title"):
            title_map[source_url] = payload["title"]

    enriched: list[PageRecord] = []
    for record in records:
        target = normalize_url(record.target)
        description = record.description or description_map.get(target, "")
        title = record.title
        if title in {"Home", "Untitled"} and target in title_map:
            title = title_map[target]
        enriched.append(
            PageRecord(
                target=target,
                title=title,
                description=description,
                section=record.section,
                decision=record.decision,
                reason=record.reason,
                source=record.source,
            )
        )
    return enriched


def infer_project_metadata(records: list[PageRecord]) -> tuple[str, str]:
    include_records = [record for record in records if record.decision == "include"]
    candidates = include_records or records

    title = "Generated llms.txt"
    title_candidates = [record for record in candidates if title_quality(record.title, record.target) > 0]
    if title_candidates:
        best_title_record = max(
            title_candidates,
            key=lambda record: (
                record_priority(record)[0],
                title_quality(record.title, record.target),
                description_quality(record.description),
            ),
        )
        title = best_title_record.title

    summary = "Curated documentation map for LLM consumption."
    summary_candidates = [record for record in candidates if description_quality(record.description) > 0]
    if summary_candidates:
        best_summary_record = max(
            summary_candidates,
            key=lambda record: (
                record_priority(record)[0],
                description_quality(record.description),
                title_quality(record.title, record.target),
            ),
        )
        summary = best_summary_record.description

    return title, summary


def build_payload(args: argparse.Namespace) -> dict:
    live_crawl_stats = {"robots_blocked": 0, "fetch_errors": 0, "crawled_pages": 0}
    allowed_hosts = derive_allowed_hosts(
        args.site_url,
        args.base_url,
        args.readme if is_url(args.readme or "") else None,
        args.repo_url,
        allow_domains=args.allow_domain,
    )

    if args.sitemap:
        source_kind = "sitemap"
        records = records_from_sitemap(args.sitemap)
    elif args.readme:
        source_kind = "readme"
        records = records_from_readme(args.readme, base_url=args.base_url)
    elif args.docs_dir:
        source_kind = "docs-dir"
        records = records_from_docs_dir(args.docs_dir, base_url=args.base_url, repo_url=args.repo_url)
    else:
        source_kind = "site-url"
        if args.seed_file:
            records = records_from_seed_files(args.seed_file, site_url=args.site_url)
        else:
            seed_payloads, live_crawl_stats = crawl_live_site(args, allowed_hosts)
            records = records_from_seed_payloads(seed_payloads, site_url=args.site_url)

    if args.seed_file and source_kind != "site-url":
        records.extend(records_from_seed_files(args.seed_file))
    if args.seed_file:
        records = enrich_descriptions(records, args.seed_file)
    if source_kind == "readme" and not allowed_hosts:
        records = [record for record in records if keep_readme_link_record(record)]
        allowed_hosts = {hostname_of(record.target) for record in records if is_url(record.target)}
    if source_kind == "sitemap" and not allowed_hosts:
        allowed_hosts = {hostname_of(record.target) for record in records if is_url(record.target)}
    records, dropped_records = filter_records_by_hosts(records, allowed_hosts)
    records = unique_records(records)
    grouped = group_records(records)

    included = [record for record in records if record.decision == "include"]
    optional = [record for record in records if record.decision == "optional"]
    excluded = [record for record in records if record.decision == "exclude"]

    inferred_title, inferred_summary = infer_project_metadata(records)
    title = args.project_title or inferred_title
    summary = args.project_summary or inferred_summary

    payload = {
        "source": {
            "kind": source_kind,
            "value": args.sitemap or args.readme or args.docs_dir or args.site_url,
        },
        "project": {
            "title": title,
            "summary": summary,
        },
        "stats": {
            "total": len(records),
            "included": len(included),
            "optional": len(optional),
            "excluded": len(excluded),
            "dropped_external": len(dropped_records),
            "crawled_pages": live_crawl_stats["crawled_pages"],
            "robots_blocked": live_crawl_stats["robots_blocked"],
            "fetch_errors": live_crawl_stats["fetch_errors"],
        },
        "allowed_hosts": sorted(allowed_hosts),
        "pages": [record.to_dict() for record in records],
        "sections": {section: [record.to_dict() for record in items] for section, items in grouped.items()},
    }
    return payload


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    if args.output:
        write_json(args.output, payload)
    else:
        import json
        import sys

        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
