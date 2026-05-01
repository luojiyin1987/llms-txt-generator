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

from llms_site_lib import PageRecord, classify_target, normalize_url, unique_records


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def main() -> int:
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

        cleaned_json = tmp / "home.json"
        run(str(SCRIPTS / "clean_markdown.py"), str(raw_page), "--source-url", "https://example.com/docs", "--json-out", str(cleaned_json))
        cleaned = json.loads(cleaned_json.read_text(encoding="utf-8"))
        assert cleaned["title"] == "Example Docs"
        assert cleaned["stats"]["link_count"] == 5

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
            "--with-full",
            "--with-sitemap-summary",
            "--with-ai-suggestions",
        )
        llms_txt = (out_dir / "llms.txt").read_text(encoding="utf-8")
        assert "# Example Docs" in llms_txt
        assert "## API" in llms_txt or "## Docs" in llms_txt
        assert (out_dir / "llms-full.txt").exists()
        assert (out_dir / "sitemap-summary.md").exists()
        assert (out_dir / "ai-content-suggestions.md").exists()

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
