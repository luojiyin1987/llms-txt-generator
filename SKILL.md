---
name: llms-txt-generator
description: Analyze a website, documentation site, API project, sitemap, GitHub README, or local docs directory and generate curated llms.txt plus optional llms-full.txt. Use when the user wants LLM-friendly docs output, page inclusion guidance, sitemap summaries, or content curation for AI consumption.
---

# llms.txt Generator

Generate stable `llms.txt` and optional companion outputs from a docs site, API site, README, or docs directory.

## Use this skill for

- Website or docs-site analysis for `llms.txt`
- API project curation from docs pages, README, or local markdown
- Optional `llms-full.txt`, sitemap summary, and AI-allow/deny recommendations

## Required crawl rule

If the input includes a live website, use the `dokobot` skill for page reads. Do not use ad-hoc HTML scraping for rendered pages.

## Inputs

- `URL`
- `sitemap.xml` URL or file
- GitHub `README` URL or local markdown file
- Local `docs/` directory

## Outputs

- `llms.txt`
- Optional `llms-full.txt`
- Optional `sitemap-summary.md`
- Optional `ai-content-suggestions.md`

## Workflow

1. Detect the source mode: site, sitemap, README, or docs directory.
2. For live sites, use `dokobot` to read the homepage, docs landing page, nav pages, and key API/reference pages.
3. Run `scripts/clean_markdown.py` on each fetched page to normalize content and extract links.
4. Prefer `scripts/generate_llms_txt.py` for end-to-end runs. It drives `dokobot`, respects `robots.txt` by default, cleans pages, discovers same-site links, and emits final artifacts.
5. Use `scripts/crawl_site.py` directly when you only need the crawl/plan phase.
6. If `llms-full.txt` is requested, the orchestration flow reuses the cleaned crawled pages when available.

## Hard filters

Always exclude:

- Login, signup, auth, account, checkout, cart pages
- Privacy, cookie, consent, security-report pages unless the user explicitly asks for policy coverage
- Infinite pagination, search results, faceted listing pages, tag pages, and obvious archives
- Obvious marketing noise such as campaign landing pages, webinar promos, and announcement funnels

## Quick commands

```bash
python3 scripts/generate_llms_txt.py -h
python3 scripts/crawl_site.py -h
python3 scripts/clean_markdown.py -h
python3 scripts/build_llms_txt.py -h
python3 scripts/smoke_test.py
```

## Notes

- `llms.txt` follows the structure described on `llmstxt.org`.
- `llms-full.txt` here is a practical companion file containing expanded cleaned content for the selected pages; it is not the same name used by every toolchain.
- The end-to-end generator requires a working `dokobot` CLI plus its browser-side setup for live URL fetching.
- Detailed heuristics and examples live in [REFERENCE.md](REFERENCE.md).
