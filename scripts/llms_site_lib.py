#!/usr/bin/env python3
"""Shared helpers for llms.txt generation scripts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


NOISE_LINE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"^\s*skip to content\s*$",
        r"^\s*search\s*$",
        r"^\s*menu\s*$",
        r"^\s*(sign in|log in|login|sign up|signup)\s*$",
        r"^\s*cookie (settings|preferences)\s*$",
        r"^\s*(previous|next)\s*$",
        r"^\s*table of contents\s*$",
        r"^\s*on this page\s*$",
        r"^\s*edit this page\s*$",
        r"^\s*was this page helpful\??\s*$",
        r"^\s*back to top\s*$",
        r"^\s*copy page\s*$",
    ]
]

EXCLUDE_TOKEN_PATTERNS = [
    "login",
    "log-in",
    "signin",
    "sign-in",
    "signup",
    "sign-up",
    "register",
    "auth",
    "oauth",
    "sso",
    "privacy",
    "cookie",
    "consent",
    "checkout",
    "cart",
    "billing",
    "pricing",
    "contact-sales",
    "book-demo",
    "webinar",
    "campaign",
    "utm_",
]

OPTIONAL_TOKEN_PATTERNS = [
    "blog",
    "news",
    "release",
    "changelog",
    "announcement",
    "migration",
    "faq",
]

INCLUDE_SECTION_MAP = [
    ("API", ["api", "reference", "openapi", "swagger", "schema"]),
    ("Guides", ["guide", "tutorial", "how-to", "howto", "concept", "learn"]),
    ("Getting Started", ["getting-started", "quickstart", "quick-start", "install", "introduction", "intro"]),
    ("Examples", ["example", "sample", "cookbook", "recipe"]),
]

URL_RE = re.compile(r"https?://[^\s)>]+")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


@dataclass
class PageRecord:
    target: str
    title: str
    description: str
    section: str
    decision: str
    reason: str
    source: str

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "title": self.title,
            "description": self.description,
            "section": self.section,
            "decision": self.decision,
            "reason": self.reason,
            "source": self.source,
        }


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def read_text_source(source: str) -> str:
    if is_url(source):
        request = Request(
            source,
            headers={
                "User-Agent": "llms-txt-generator/0.1 (+https://llmstxt.org)",
                "Accept": "text/plain,text/markdown,text/xml,application/xml,text/html;q=0.8,*/*;q=0.1",
            },
        )
        with urlopen(request, timeout=20) as response:  # noqa: S310
            data = response.read()
        return data.decode("utf-8", errors="replace")
    return Path(source).read_text(encoding="utf-8")


def resolve_readme_source(source: str) -> str:
    if not is_url(source):
        return source

    parsed = urlparse(source)
    host = (parsed.hostname or "").lower()
    parts = [part for part in parsed.path.split("/") if part]
    if host == "raw.githubusercontent.com":
        return source
    if host != "github.com" or len(parts) < 2:
        return source

    owner, repo = parts[0], parts[1]
    if len(parts) == 2:
        return f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/README.md"
    if len(parts) >= 5 and parts[2] == "blob":
        branch = parts[3]
        path = "/".join(parts[4:])
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    return source


def write_text(path: str | Path, content: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: str | Path, payload: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_filename(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip())
    value = value.strip("-._")
    return value or "page"


def normalize_url(url: str, base_url: str | None = None) -> str:
    url = url.strip()
    if not url:
        return url
    if base_url and not is_url(url):
        url = urljoin(base_url, url)
    if not is_url(url):
        return url

    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    filtered_query: list[tuple[str, str]] = []
    for key, values in query.items():
        if key.lower().startswith("utm_"):
            continue
        if key.lower() in {"ref", "source"}:
            continue
        for value in values:
            filtered_query.append((key, value))

    clean = parsed._replace(
        fragment="",
        query=urlencode(filtered_query, doseq=True),
    )
    rebuilt = urlunparse(clean)
    if rebuilt.endswith("/") and parsed.path not in {"", "/"}:
        rebuilt = rebuilt[:-1]
    return rebuilt


def maybe_drop_noise_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if len(stripped) > 120:
        return False
    return any(pattern.match(stripped) for pattern in NOISE_LINE_PATTERNS)


def clean_markdown_text(raw_text: str) -> str:
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    cleaned: list[str] = []
    previous_blank = False
    for line in lines:
        if maybe_drop_noise_line(line):
            continue
        line = re.sub(r"[ \t]+$", "", line)
        if re.fullmatch(r"[-=]{3,}", line.strip()):
            if cleaned and cleaned[-1].startswith("#"):
                continue
        blank = not line.strip()
        if blank and previous_blank:
            continue
        cleaned.append(line)
        previous_blank = blank
    return "\n".join(cleaned).strip() + "\n"


def extract_markdown_links(text: str, base_url: str | None = None) -> list[dict]:
    seen: set[str] = set()
    links: list[dict] = []
    for label, href in MD_LINK_RE.findall(text):
        target = normalize_url(href, base_url=base_url)
        if not target or target.startswith("mailto:") or target.startswith("#"):
            continue
        if target in seen:
            continue
        seen.add(target)
        links.append({"title": collapse_ws(label), "target": target, "kind": "markdown"})
    for match in URL_RE.findall(text):
        target = normalize_url(match, base_url=base_url)
        if not target or target in seen:
            continue
        seen.add(target)
        links.append({"title": "", "target": target, "kind": "bare"})
    return links


def extract_title_and_summary(text: str) -> tuple[str, str]:
    title = ""
    summary = ""
    paragraphs: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        heading = HEADING_RE.match(line)
        if heading and heading.group(1) == "#":
            title = heading.group(2).strip()
            continue
        if not title and len(line) <= 90 and not line.startswith(("-", "*", ">")):
            title = line
            continue
        if line.startswith(">"):
            line = line[1:].strip()
        if len(line) > 20:
            paragraphs.append(line)
        if len(paragraphs) >= 2:
            break
    if paragraphs:
        summary = collapse_ws(paragraphs[0])[:280]
    return title or "Untitled", summary


def collapse_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def summarize_content(text: str, limit: int = 220) -> str:
    _, summary = extract_title_and_summary(text)
    if not summary:
        lines = [collapse_ws(line) for line in text.splitlines() if collapse_ws(line)]
        summary = lines[0] if lines else ""
    if len(summary) <= limit:
        return summary
    return summary[: limit - 1].rstrip() + "..."


def normalized_terms(*values: str) -> set[str]:
    terms: set[str] = set()
    for value in values:
        for part in re.split(r"[^a-z0-9]+", value.lower()):
            if part:
                terms.add(part)
    return terms


def keyword_matches_terms(keyword: str, terms: set[str]) -> bool:
    parts = [part for part in re.split(r"[^a-z0-9]+", keyword.lower()) if part]
    return bool(parts) and all(part in terms for part in parts)


def classification_text(target: str, title: str) -> str:
    if is_url(target):
        parsed = urlparse(target)
        return f"{parsed.path} {parsed.query} {title}".strip()
    return f"{target} {title}".strip()


def should_exclude_target(target: str, title: str = "") -> tuple[bool, str]:
    parsed = urlparse(target) if is_url(target) else None

    # Check hostname segments separately to avoid false positives on subdomains.
    # e.g. auth.example.com should NOT match the "auth" exclude token.
    if parsed and parsed.hostname:
        hostname_segments = set(parsed.hostname.lower().split("."))
        for token in EXCLUDE_TOKEN_PATTERNS:
            if token in hostname_segments:
                return True, "matched excluded token in hostname"

    haystack = f"{parsed.path if parsed else target} {parsed.query if parsed else ''} {title}".lower()
    if any(token in haystack for token in EXCLUDE_TOKEN_PATTERNS):
        return True, "matched excluded token"

    if parsed:
        query = parse_qs(parsed.query)
        if any(key.lower() in {"page", "offset", "cursor", "before", "after"} for key in query):
            return True, "pagination-like query"
        if re.search(r"/page/\d+/?$", parsed.path):
            return True, "pagination path"
        if "/tag/" in parsed.path or "/category/" in parsed.path or "/archive/" in parsed.path:
            return True, "listing/archive path"
    return False, ""


def classify_target(target: str, title: str = "") -> tuple[str, str, str]:
    excluded, reason = should_exclude_target(target, title=title)
    if excluded:
        return "Excluded", "exclude", reason

    haystack = classification_text(target, title).lower()
    terms = normalized_terms(classification_text(target, title))
    if any(token in haystack for token in OPTIONAL_TOKEN_PATTERNS):
        return "Optional", "optional", "secondary content"

    for section, tokens in INCLUDE_SECTION_MAP:
        if any(keyword_matches_terms(token, terms) for token in tokens):
            return section, "include", "matched core section token"

    if any(keyword_matches_terms(token, terms) for token in {"readme", "docs", "documentation"}):
        return "Docs", "include", "generic docs signal"

    return "Docs", "include", "default include"


def unique_records(records: Iterable[PageRecord]) -> list[PageRecord]:
    merged: dict[str, PageRecord] = {}
    for record in records:
        key = normalize_url(record.target)
        if key not in merged:
            merged[key] = record
            continue
        merged[key] = merge_records(merged[key], record)
    return list(merged.values())


def group_records(records: Iterable[PageRecord]) -> dict[str, list[PageRecord]]:
    grouped: dict[str, list[PageRecord]] = {}
    for record in records:
        grouped.setdefault(record.section, []).append(record)
    for section_records in grouped.values():
        section_records.sort(key=lambda item: (item.decision != "include", item.title.lower(), item.target.lower()))
    return grouped


def parse_sitemap_xml(text: str) -> list[str]:
    root = ET.fromstring(text)
    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag.split("}", 1)[0] + "}"
    urls = [loc.text.strip() for loc in root.findall(f".//{namespace}loc") if loc.text and loc.text.strip()]
    return urls


def load_page_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def infer_target_from_markdown_path(path: Path, base_url: str | None = None, repo_url: str | None = None) -> str:
    rel = path.as_posix()
    if base_url:
        clean_rel = rel
        if clean_rel.endswith("README.md"):
            clean_rel = clean_rel[: -len("README.md")]
        elif clean_rel.endswith(".md"):
            clean_rel = clean_rel[: -len(".md")]
        return normalize_url(clean_rel, base_url=base_url)
    if repo_url:
        return normalize_url(rel, base_url=repo_url.rstrip("/") + "/blob/main/")
    return rel


def build_clean_page_payload(raw_text: str, source_url: str, source: str = "crawl") -> dict:
    cleaned = clean_markdown_text(raw_text)
    title, summary = extract_title_and_summary(cleaned)
    links = extract_markdown_links(cleaned, base_url=source_url)
    return {
        "source": source,
        "source_url": source_url,
        "title": title,
        "summary": summary,
        "content": cleaned,
        "links": links,
        "stats": {
            "char_count": len(cleaned),
            "link_count": len(links),
        },
    }


def build_robots_parser(site_url: str) -> RobotFileParser:
    parsed = urlparse(site_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
    except Exception:
        parser.allow_all = True
    return parser


def can_fetch_with_robots(parser: RobotFileParser | None, url: str, user_agent: str = "llms-txt-generator") -> bool:
    if parser is None:
        return True
    try:
        return parser.can_fetch(user_agent, url)
    except Exception:
        return True


def hostname_of(value: str) -> str:
    if not is_url(value):
        return ""
    return (urlparse(value).hostname or "").lower().rstrip(".")


def derive_allowed_hosts(*values: str | None, allow_domains: Iterable[str] | None = None) -> set[str]:
    hosts = {hostname_of(value) for value in values if value}
    hosts.discard("")
    if allow_domains:
        for domain in allow_domains:
            clean = domain.strip().lower().rstrip(".")
            if clean:
                hosts.add(clean)
    return hosts


def target_is_allowed(target: str, allowed_hosts: set[str]) -> bool:
    if not is_url(target):
        return True
    if not allowed_hosts:
        return False
    hostname = hostname_of(target)
    return any(hostname == allowed or hostname.endswith(f".{allowed}") for allowed in allowed_hosts)


def filter_records_by_hosts(records: Iterable[PageRecord], allowed_hosts: set[str]) -> tuple[list[PageRecord], list[PageRecord]]:
    kept: list[PageRecord] = []
    dropped: list[PageRecord] = []
    for record in records:
        if target_is_allowed(record.target, allowed_hosts):
            kept.append(record)
        else:
            dropped.append(record)
    return kept, dropped


DECISION_PRIORITY = {"exclude": 3, "include": 2, "optional": 1}
SOURCE_PRIORITY = {
    "seed-page": 6,
    "docs-dir": 6,
    "readme": 6,
    "site-url": 5,
    "seed-link": 4,
    "docs-link": 4,
    "readme-link": 4,
    "sitemap": 1,
}
SECTION_PRIORITY = {
    "Excluded": 5,
    "API": 4,
    "Guides": 4,
    "Getting Started": 4,
    "Examples": 3,
    "Docs": 2,
    "Optional": 1,
}


def title_quality(title: str, target: str) -> int:
    clean = collapse_ws(title)
    if not clean or clean in {"Home", "Untitled"}:
        return 0
    slug = Path(urlparse(target).path if is_url(target) else target).name.replace("-", " ").replace("_", " ").strip().lower()
    score = 1
    if clean.lower() != slug:
        score += 2
    if " " in clean:
        score += 1
    return score


def description_quality(description: str) -> int:
    clean = collapse_ws(description)
    if not clean:
        return 0
    return min(len(clean), 240)


def record_priority(record: PageRecord) -> tuple[int, int, int, int, int]:
    src_prio = max(SOURCE_PRIORITY.get(s, 0) for s in record.source.split(","))
    return (
        src_prio,
        description_quality(record.description),
        title_quality(record.title, record.target),
        DECISION_PRIORITY.get(record.decision, 0),
        SECTION_PRIORITY.get(record.section, 0),
    )


def better_title(left: PageRecord, right: PageRecord) -> str:
    left_score = title_quality(left.title, left.target)
    right_score = title_quality(right.title, right.target)
    if right_score > left_score:
        return right.title
    if left_score > right_score:
        return left.title
    return right.title if len(collapse_ws(right.title)) > len(collapse_ws(left.title)) else left.title


def better_description(left: PageRecord, right: PageRecord) -> str:
    left_score = description_quality(left.description)
    right_score = description_quality(right.description)
    if right_score > left_score:
        return right.description
    return left.description


def merge_records(left: PageRecord, right: PageRecord) -> PageRecord:
    primary = left if record_priority(left) >= record_priority(right) else right
    return PageRecord(
        target=normalize_url(primary.target),
        title=better_title(left, right),
        description=better_description(left, right),
        section=primary.section,
        decision=primary.decision,
        reason=primary.reason,
        source=",".join(sorted(set(filter(None, [left.source, right.source])))),
    )
