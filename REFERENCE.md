# Reference

## Source modes

### Website URL

Use the one-shot orchestrator for a stable end-to-end flow. It uses `dokobot` for rendered page reads, respects `robots.txt` by default, cleans markdown, discovers same-site links, and builds final artifacts. If `robots.txt` cannot be read, the run now fails unless you explicitly pass `--ignore-robots`.

Example:

```bash
python3 scripts/generate_llms_txt.py \
  --site-url https://example.com/docs \
  --dokobot-local \
  --with-full \
  --with-sitemap-summary \
  --with-ai-suggestions
```

If you need just the crawl/plan phase:

```bash
python3 scripts/crawl_site.py \
  --site-url https://example.com/docs \
  --dokobot-local \
  --page-json-dir artifacts/clean \
  --output artifacts/plan.json
```

### Sitemap

Point `crawl_site.py` to a sitemap URL or a local XML file:

```bash
python3 scripts/crawl_site.py \
  --sitemap https://example.com/sitemap.xml \
  --output artifacts/plan.json
```

### README

For a GitHub README URL or local markdown file, the script reads markdown directly. GitHub repo URLs and `blob/.../README.md` URLs are resolved to raw markdown automatically. When no explicit allowed domains are provided, README mode keeps only high-confidence docs links instead of blindly restricting everything to `github.com`.

### docs directory

Point `crawl_site.py` at a local directory of markdown files. If you know the deployed base URL or repo URL, pass it so links are emitted as URLs instead of local paths.

```bash
python3 scripts/crawl_site.py \
  --docs-dir ./docs \
  --base-url https://docs.example.com \
  --output artifacts/plan.json
```

## Output policy

### `llms.txt`

Use:

- one H1 title
- one blockquote summary
- optional high-signal notes before any H2 sections
- H2 sections containing markdown link lists with short descriptions
- `## Optional` only for secondary material

### `llms-full.txt`

Expanded companion file containing:

- the top-level `llms.txt` overview
- per-page cleaned content for included and optional pages
- source URLs for every expanded section

## Filtering heuristics

Exclude by default when URL path or title suggests:

- `login`, `signin`, `signup`, `register`, `auth`, `oauth`, `sso`
- `privacy`, `cookies`, `consent`
- `cart`, `checkout`, `billing`, `pricing`, `demo`, `contact-sales`
- `search`, `tag`, `category`, `archive`, `page/2`, `?page=2`, `?offset=`

Downgrade to `Optional` when the page is useful but non-core:

- changelog or release notes
- migration guides
- examples gallery
- blog posts explaining the product

Keep in main sections when the page is core product understanding:

- getting started
- installation
- tutorials
- concepts
- API reference
- CLI reference
- SDK docs
- architecture or integration docs

## Validation

Run:

```bash
python3 scripts/smoke_test.py
```

This checks:

- markdown cleaning
- link extraction
- sitemap parsing
- include/optional/exclude heuristics
- live site orchestration CLI shape
- final `llms.txt` rendering
