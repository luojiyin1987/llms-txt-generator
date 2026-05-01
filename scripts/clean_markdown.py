#!/usr/bin/env python3
"""Clean markdown-like page text and extract links."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from llms_site_lib import (
    clean_markdown_text,
    extract_markdown_links,
    extract_title_and_summary,
    write_json,
    write_text,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", help="Input file. Omit to read from stdin.")
    parser.add_argument("--source-url", help="Source URL used to resolve relative links.")
    parser.add_argument("--json-out", help="Write structured JSON output to this path.")
    parser.add_argument("--md-out", help="Write cleaned markdown output to this path.")
    parser.add_argument("--stdout-markdown", action="store_true", help="Print cleaned markdown to stdout.")
    parser.add_argument("--stdout-json", action="store_true", help="Print structured JSON to stdout.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.input:
        raw_text = Path(args.input).read_text(encoding="utf-8")
        source = args.input
    else:
        raw_text = sys.stdin.read()
        source = "stdin"

    cleaned = clean_markdown_text(raw_text)
    title, summary = extract_title_and_summary(cleaned)
    links = extract_markdown_links(cleaned, base_url=args.source_url)

    payload = {
        "source": source,
        "source_url": args.source_url or "",
        "title": title,
        "summary": summary,
        "content": cleaned,
        "links": links,
        "stats": {
            "char_count": len(cleaned),
            "link_count": len(links),
        },
    }

    if args.json_out:
        write_json(args.json_out, payload)
    if args.md_out:
        write_text(args.md_out, cleaned)
    if args.stdout_json:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    if args.stdout_markdown:
        sys.stdout.write(cleaned)
    if not any([args.json_out, args.md_out, args.stdout_json, args.stdout_markdown]):
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
