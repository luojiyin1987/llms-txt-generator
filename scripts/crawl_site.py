#!/usr/bin/env python3
"""Build a curated page plan from a site, sitemap, README, or docs directory."""

from __future__ import annotations

import argparse
from pathlib import Path

from llms_site_lib import (
    PageRecord,
    classify_target,
    derive_allowed_hosts,
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
    summarize_content,
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
    parser.add_argument("--seed-file", action="append", default=[], help="Cleaned page JSON file(s) from clean_markdown.py.")
    parser.add_argument("--allow-domain", action="append", default=[], help="Additional allowed domain. Can be passed more than once.")
    parser.add_argument("--base-url", help="Base URL used to resolve relative links.")
    parser.add_argument("--repo-url", help="Repo URL used to map local docs paths to blob URLs.")
    parser.add_argument("--output", help="Write plan JSON to this path.")
    return parser.parse_args()


def records_from_sitemap(source: str) -> list[PageRecord]:
    text = read_text_source(source)
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
    for seed_file in seed_files:
        payload = load_page_json(seed_file)
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


def records_from_readme(source: str, base_url: str | None = None) -> list[PageRecord]:
    text = read_text_source(source)
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


def build_payload(args: argparse.Namespace) -> dict:
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
        records = records_from_seed_files(args.seed_file, site_url=args.site_url)

    if args.seed_file and source_kind != "site-url":
        records.extend(records_from_seed_files(args.seed_file))
    if args.seed_file:
        records = enrich_descriptions(records, args.seed_file)

    allowed_hosts = derive_allowed_hosts(
        args.site_url,
        args.base_url,
        args.readme if is_url(args.readme or "") else None,
        args.repo_url,
        allow_domains=args.allow_domain,
    )
    if source_kind == "sitemap" and not allowed_hosts:
        allowed_hosts = {
            hostname_of(record.target)
            for record in records
            if is_url(record.target)
        }
    records, dropped_records = filter_records_by_hosts(records, allowed_hosts)
    records = unique_records(records)
    grouped = group_records(records)

    included = [record for record in records if record.decision == "include"]
    optional = [record for record in records if record.decision == "optional"]
    excluded = [record for record in records if record.decision == "exclude"]

    title = "Generated llms.txt"
    summary = "Curated documentation map for LLM consumption."
    for record in records:
        if record.decision == "include" and record.description:
            summary = record.description
            break
    for record in records:
        if record.title and record.title not in {"Home", "Untitled"}:
            title = record.title
            break

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
