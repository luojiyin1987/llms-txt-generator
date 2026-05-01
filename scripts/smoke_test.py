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


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def main() -> int:
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
""",
            encoding="utf-8",
        )

        cleaned_json = tmp / "home.json"
        run(str(SCRIPTS / "clean_markdown.py"), str(raw_page), "--source-url", "https://example.com/docs", "--json-out", str(cleaned_json))
        cleaned = json.loads(cleaned_json.read_text(encoding="utf-8"))
        assert cleaned["title"] == "Example Docs"
        assert cleaned["stats"]["link_count"] == 4

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
        run(str(SCRIPTS / "crawl_site.py"), "--sitemap", str(sitemap), "--output", str(sitemap_plan_json))
        sitemap_plan = json.loads(sitemap_plan_json.read_text(encoding="utf-8"))
        assert sitemap_plan["stats"]["excluded"] == 1

    print("smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
