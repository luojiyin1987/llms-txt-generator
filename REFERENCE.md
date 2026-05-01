# Reference

## Source modes

### Website URL

Use `dokobot` to read:

- the homepage or docs landing page
- the primary navigation page
- one or two representative API/reference pages if the nav exposes them

Then clean each page and let `crawl_site.py` merge the discovered links.

Example:

```bash
dokobot doko read 'https://example.com/docs' --local > artifacts/raw/home.txt
python3 scripts/clean_markdown.py artifacts/raw/home.txt \
  --source-url https://example.com/docs \
  --json-out artifacts/clean/home.json
python3 scripts/crawl_site.py \
  --site-url https://example.com/docs \
  --seed-file artifacts/clean/home.json \
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

For a GitHub README URL, read it with `dokobot` first or provide a local markdown file. The script treats markdown links as candidate resources.

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
- final `llms.txt` rendering
