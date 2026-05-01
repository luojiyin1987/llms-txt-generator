# llms-txt-generator

Skill scaffold and helper scripts for generating curated `llms.txt` outputs from websites, docs sites, API projects, sitemaps, READMEs, and local docs directories.

## Files

- `SKILL.md`: skill entrypoint
- `REFERENCE.md`: workflow details
- `scripts/crawl_site.py`: source discovery, filtering, classification
- `scripts/clean_markdown.py`: markdown cleanup and link extraction
- `scripts/build_llms_txt.py`: final artifact renderer
- `scripts/smoke_test.py`: offline smoke test

## Quick start

```bash
python3 scripts/smoke_test.py
```

See [REFERENCE.md](REFERENCE.md) for end-to-end examples, including the required `dokobot` step for live site crawling.
