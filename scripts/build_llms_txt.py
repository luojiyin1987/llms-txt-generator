#!/usr/bin/env python3
"""Render llms.txt and optional companion artifacts from a page plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from llms_site_lib import load_page_json, normalize_url, write_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, help="Plan JSON created by crawl_site.py.")
    parser.add_argument("--page-json-dir", help="Directory of cleaned page JSON files.")
    parser.add_argument("--output-dir", default="out", help="Output directory for generated files.")
    parser.add_argument("--with-full", action="store_true", help="Emit llms-full.txt.")
    parser.add_argument("--with-sitemap-summary", action="store_true", help="Emit sitemap-summary.md.")
    parser.add_argument("--with-ai-suggestions", action="store_true", help="Emit ai-content-suggestions.md.")
    return parser.parse_args()


def load_page_map(directory: str | None) -> dict[str, dict]:
    if not directory:
        return {}
    page_map: dict[str, dict] = {}
    for path in sorted(Path(directory).glob("*.json")):
        payload = load_page_json(path)
        source_url = normalize_url(payload.get("source_url", ""))
        if source_url:
            page_map[source_url] = payload
    return page_map


def render_llms_txt(plan: dict) -> str:
    project = plan["project"]
    sections = plan["sections"]
    lines: list[str] = [
        f"# {project['title']}",
        "",
        f"> {project['summary']}",
        "",
        "Important notes:",
        "- Curated for AI consumption from high-signal documentation and reference pages.",
        "- Login, privacy, pagination, and obvious marketing noise pages are excluded by default.",
    ]

    ordered_sections = [
        section
        for section in ["Getting Started", "Guides", "API", "Examples", "Docs"]
        if section in sections and any(page["decision"] == "include" for page in sections[section])
    ]
    remaining = sorted(
        [
            section
            for section, items in sections.items()
            if section not in ordered_sections and section != "Optional" and any(page["decision"] == "include" for page in items)
        ]
    )
    ordered_sections.extend(remaining)

    for section in ordered_sections:
        lines.extend(["", f"## {section}", ""])
        for page in sections[section]:
            if page["decision"] != "include":
                continue
            desc = f": {page['description']}" if page["description"] else ""
            lines.append(f"- [{page['title']}]({page['target']}){desc}")

    optional_pages = [page for page in plan["pages"] if page["decision"] == "optional"]
    if optional_pages:
        lines.extend(["", "## Optional", ""])
        for page in sorted(optional_pages, key=lambda item: (item["section"], item["title"].lower(), item["target"].lower())):
            desc = f": {page['description']}" if page["description"] else ""
            lines.append(f"- [{page['title']}]({page['target']}){desc}")

    return "\n".join(lines).rstrip() + "\n"


def render_llms_full(plan: dict, page_map: dict[str, dict], llms_txt: str) -> str:
    lines = [llms_txt.rstrip(), "", "## Expanded Content", ""]
    for page in plan["pages"]:
        if page["decision"] not in {"include", "optional"}:
            continue
        payload = page_map.get(normalize_url(page["target"]))
        if not payload:
            continue
        lines.extend(
            [
                f"## {page['title']}",
                "",
                f"Source: {page['target']}",
                "",
                payload.get("content", "").rstrip(),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_sitemap_summary(plan: dict) -> str:
    lines = [
        "# Sitemap Summary",
        "",
        f"- Total pages considered: {plan['stats']['total']}",
        f"- Included: {plan['stats']['included']}",
        f"- Optional: {plan['stats']['optional']}",
        f"- Excluded: {plan['stats']['excluded']}",
    ]
    for section, pages in sorted(plan["sections"].items()):
        lines.extend(["", f"## {section}", ""])
        for page in pages:
            lines.append(f"- `{page['decision']}` [{page['title']}]({page['target']}): {page['reason']}")
    return "\n".join(lines).rstrip() + "\n"


def render_ai_suggestions(plan: dict) -> str:
    include_pages = [page for page in plan["pages"] if page["decision"] == "include"]
    excluded_pages = [page for page in plan["pages"] if page["decision"] == "exclude"]
    optional_pages = [page for page in plan["pages"] if page["decision"] == "optional"]

    lines = [
        "# AI Content Suggestions",
        "",
        "## Give To AI",
        "",
    ]
    for page in include_pages:
        lines.append(f"- [{page['title']}]({page['target']}): {page['reason']}")

    lines.extend(["", "## Maybe Give To AI", ""])
    for page in optional_pages:
        lines.append(f"- [{page['title']}]({page['target']}): {page['reason']}")

    lines.extend(["", "## Do Not Give To AI By Default", ""])
    for page in excluded_pages:
        lines.append(f"- [{page['title']}]({page['target']}): {page['reason']}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    page_map = load_page_map(args.page_json_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    llms_txt = render_llms_txt(plan)
    write_text(out_dir / "llms.txt", llms_txt)

    if args.with_full:
        llms_full = render_llms_full(plan, page_map, llms_txt)
        write_text(out_dir / "llms-full.txt", llms_full)
    if args.with_sitemap_summary:
        write_text(out_dir / "sitemap-summary.md", render_sitemap_summary(plan))
    if args.with_ai_suggestions:
        write_text(out_dir / "ai-content-suggestions.md", render_ai_suggestions(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
