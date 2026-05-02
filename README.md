# llms-txt-generator

Skill scaffold and helper scripts for generating curated `llms.txt` outputs from websites, docs sites, API projects, sitemaps, READMEs, and local docs directories.

## Files

- `SKILL.md`: skill entrypoint
- `REFERENCE.md`: workflow details
- `scripts/crawl_site.py`: source discovery, live-site crawling, filtering, classification
- `scripts/clean_markdown.py`: markdown cleanup and link extraction
- `scripts/build_llms_txt.py`: final artifact renderer
- `scripts/generate_llms_txt.py`: one-shot orchestration from input to outputs
- `scripts/smoke_test.py`: offline smoke test

## Prerequisites

### Install Dokobot

This project uses [Dokobot](https://dokobot.ai) for real-browser page reading, supporting complex scenarios such as login walls, JavaScript rendering, and bot detection.

Dokobot offers two installation options; choose at least one:

#### Option 1: Chrome Extension (Recommended)

Supports Chrome, Edge, Brave, and Arc.

1. Install the Dokobot extension from the [Chrome Web Store](https://chromewebstore.google.com/detail/dokobot/dlbiigchkpmpijahmlofleeemiomaneo).
2. Click the extension icon to start the local service.
3. Use the `--dokobot-local` flag when running this project.

#### Option 2: Dokobot CLI

Ideal for servers or CI environments.

```bash
# Install CLI globally
npm i -g @dokobot/cli@latest

# For mainland China users with network restrictions
npm i -g @dokobot/cli@latest --registry=https://registry.npmmirror.com
```

After installation, make sure the `dokobot` command is available in your `PATH`:

```bash
dokobot --version
```

For more Dokobot documentation, see the [official guide](https://dokobot.ai/guide).

---

## Quick start

```bash
python3 scripts/smoke_test.py
```

### Generate from a live docs site

Requires a working Dokobot setup (Chrome extension or CLI):

```bash
python3 scripts/generate_llms_txt.py \
  --site-url https://example.com/docs \
  --dokobot-local \
  --with-full \
  --with-sitemap-summary \
  --with-ai-suggestions
```

### Generate from a local docs directory

No Dokobot required; reads local Markdown directly:

```bash
python3 scripts/generate_llms_txt.py \
  --docs-dir ./docs \
  --base-url https://docs.example.com \
  --with-full
```

### Generate from a GitHub README

```bash
python3 scripts/generate_llms_txt.py \
  --readme https://github.com/example/project \
  --with-full
```

---

See [REFERENCE.md](REFERENCE.md) for end-to-end examples and advanced options.

The live URL flow requires a working `dokobot` CLI and browser setup. By default it stops if `robots.txt` cannot be read; use `--ignore-robots` only when you intentionally want to override that check.
