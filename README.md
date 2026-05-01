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

## Quick start

```bash
python3 scripts/smoke_test.py
```

For a live docs site with Dokobot:

```bash
python3 scripts/generate_llms_txt.py \
  --site-url https://example.com/docs \
  --dokobot-local \
  --with-full \
  --with-sitemap-summary \
  --with-ai-suggestions
```

See [REFERENCE.md](REFERENCE.md) for end-to-end examples, including the required `dokobot` step for live site crawling.
