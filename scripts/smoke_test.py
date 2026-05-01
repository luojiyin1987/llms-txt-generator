#!/usr/bin/env python3
"""Offline smoke test for the llms.txt generator scripts."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from unittest import mock  # noqa: E402

from llms_site_lib import (  # noqa: E402
    PageRecord,
    build_robots_parser,
    classify_target,
    normalize_url,
    resolve_readme_source,
    unique_records,
)


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def main() -> int:
    help_result = run(str(SCRIPTS / "generate_llms_txt.py"), "-h")
    assert "--ignore-robots" in help_result.stdout
    assert "--with-full" in help_result.stdout

    normalized = normalize_url("https://example.com/docs?q=hello world&x=a%26b&utm_source=newsletter")
    assert normalized == "https://example.com/docs?q=hello+world&x=a%26b"

    merged = unique_records(
        [
            PageRecord(
                target="https://example.com/api",
                title="Api",
                description="",
                section="API",
                decision="include",
                reason="sitemap",
                source="sitemap",
            ),
            PageRecord(
                target="https://example.com/api",
                title="API Reference",
                description="REST API overview",
                section="API",
                decision="include",
                reason="seed",
                source="seed-page",
            ),
        ]
    )
    assert len(merged) == 1
    assert merged[0].title == "API Reference"
    assert merged[0].description == "REST API overview"

    docsify_classification = classify_target("https://example.com/docsify-demo", title="Docsify Demo")
    assert docsify_classification[0] != "Docs" or docsify_classification[2] != "generic docs signal"

    apidoc_classification = classify_target("https://example.com/apidoc", title="Apidoc")
    assert apidoc_classification[0] != "API" or apidoc_classification[2] != "matched core section token"

    assert resolve_readme_source("https://github.com/example/project") == "https://raw.githubusercontent.com/example/project/HEAD/README.md"
    assert resolve_readme_source("https://github.com/example/project/blob/main/README.md") == "https://raw.githubusercontent.com/example/project/main/README.md"

    with mock.patch("urllib.robotparser.RobotFileParser.read", side_effect=OSError("network down")):
        parser = build_robots_parser("https://example.com/docs")
        assert parser.allow_all, "expected fallback to allow_all when robots.txt is unreadable"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        raw_page = tmp / "home.md"
        raw_page.write_text(
            """# Example Docs

Skip to content

Example Docs is the home for the SDK and API guides.

- [Quickstart](https://example.com/docs/quickstart)
- [API Reference](https://example.com/docs/api)
- [Release Notes](https://example.com/docs/changelog)
- [Login](https://example.com/login)
- [GitHub Issues](https://github.com/example/project/issues)
""",
            encoding="utf-8",
        )

        readme = tmp / "README.md"
        readme.write_text(
            """# SDK

See the docs:

- [Docs Home](https://docs.example.com/docs)
- [API Reference](https://docs.example.com/api/reference)
- [Issues](https://github.com/example/project/issues)
""",
            encoding="utf-8",
        )

        cleaned_json = tmp / "home.json"
        run(str(SCRIPTS / "clean_markdown.py"), str(raw_page), "--source-url", "https://example.com/docs", "--json-out", str(cleaned_json))
        cleaned = json.loads(cleaned_json.read_text(encoding="utf-8"))
        assert cleaned["title"] == "Example Docs"
        assert cleaned["stats"]["link_count"] == 5

        readme_plan_json = tmp / "readme-plan.json"
        run(str(SCRIPTS / "crawl_site.py"), "--readme", str(readme), "--output", str(readme_plan_json))
        readme_plan = json.loads(readme_plan_json.read_text(encoding="utf-8"))
        assert any(page["target"] == "https://docs.example.com/docs" for page in readme_plan["pages"])
        assert all("github.com/example/project/issues" not in page["target"] for page in readme_plan["pages"])

        sitemap = tmp / "sitemap.xml"
        sitemap.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/docs/quickstart</loc></url>
  <url><loc>https://example.com/docs/api</loc></url>
  <url><loc>https://example.com/privacy</loc></url>
</urlset>
""",
            encoding="utf-8",
        )

        plan_json = tmp / "plan.json"
        run(
            str(SCRIPTS / "crawl_site.py"),
            "--site-url",
            "https://example.com/docs",
            "--seed-file",
            str(cleaned_json),
            "--output",
            str(plan_json),
        )
        plan = json.loads(plan_json.read_text(encoding="utf-8"))
        assert plan["stats"]["included"] >= 2
        assert any(page["decision"] == "exclude" for page in plan["pages"])
        assert plan["stats"]["dropped_external"] == 1
        assert all("github.com" not in page["target"] for page in plan["pages"])
        api_page = next(page for page in plan["pages"] if page["target"] == "https://example.com/docs/api")
        assert api_page["title"] == "API Reference"
        assert plan["project"]["title"] == "Example Docs"

        out_dir = tmp / "out"
        run(
            str(SCRIPTS / "build_llms_txt.py"),
            "--plan",
            str(plan_json),
            "--page-json-dir",
            str(tmp),
            "--output-dir",
            str(out_dir),
            "--with-sitemap-summary",
            "--with-ai-suggestions",
        )
        llms_txt = (out_dir / "llms.txt").read_text(encoding="utf-8")
        assert "# Example Docs" in llms_txt
        assert "## API" in llms_txt or "## Docs" in llms_txt
        assert (out_dir / "sitemap-summary.md").exists()
        assert (out_dir / "ai-content-suggestions.md").exists()

        docs_dir = tmp / "docs"
        docs_dir.mkdir()
        (docs_dir / "index.md").write_text(
            """# Local Docs

Start here.

- [Guide](guide.md)
""",
            encoding="utf-8",
        )
        (docs_dir / "guide.md").write_text(
            """# Guide

This is the full guide body.
""",
            encoding="utf-8",
        )
        generated_out = tmp / "generated-out"
        artifacts = tmp / "generated-artifacts"
        run(
            str(SCRIPTS / "generate_llms_txt.py"),
            "--docs-dir",
            str(docs_dir),
            "--output-dir",
            str(generated_out),
            "--artifacts-dir",
            str(artifacts),
            "--with-full",
        )
        llms_full = (generated_out / "llms-full.txt").read_text(encoding="utf-8")
        assert "This is the full guide body." in llms_full

        sitemap_plan_json = tmp / "sitemap-plan.json"
        run(
            str(SCRIPTS / "crawl_site.py"),
            "--sitemap",
            str(sitemap),
            "--project-title",
            "Example Platform",
            "--project-summary",
            "Canonical docs for the Example Platform.",
            "--output",
            str(sitemap_plan_json),
        )
        sitemap_plan = json.loads(sitemap_plan_json.read_text(encoding="utf-8"))
        assert sitemap_plan["stats"]["excluded"] == 1
        assert sitemap_plan["project"]["title"] == "Example Platform"
        assert sitemap_plan["project"]["summary"] == "Canonical docs for the Example Platform."

    print("smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
