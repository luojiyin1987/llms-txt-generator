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

本项目依赖 [Dokobot](https://dokobot.ai) 进行真实浏览器页面读取，支持登录墙、JS 渲染和机器人检测等复杂场景。

Dokobot 提供两种安装方式，**至少选择一种**：

#### 方式一：Chrome 扩展（推荐，一键安装）

支持 Chrome、Edge、Brave 和 Arc 浏览器。

1. 打开 [Chrome Web Store](https://chromewebstore.google.com/detail/dokobot/dlbiigchkpmpijahmlofleeemiomaneo) 安装 Dokobot 扩展。
2. 安装完成后，点击扩展图标启动本地服务。
3. 之后运行本项目的 `--dokobot-local` 模式即可调用。

#### 方式二：Dokobot CLI（命令行 / 脚本化）

适合在服务器或 CI 环境中使用。

```bash
# 全局安装 CLI
npm i -g @dokobot/cli@latest

# 中国大陆网络受限地区可使用镜像
npm i -g @dokobot/cli@latest --registry=https://registry.npmmirror.com
```

安装完成后，确保 `dokobot` 命令在 `PATH` 中可用：

```bash
dokobot --version
```

更多 Dokobot 使用文档见 [官方指南](https://dokobot.ai/zh-CN/guide)。

---

## Quick start

```bash
python3 scripts/smoke_test.py
```

### 从实时文档站点生成

使用 Dokobot 读取并生成（需先安装 Chrome 扩展或 CLI）：

```bash
python3 scripts/generate_llms_txt.py \
  --site-url https://example.com/docs \
  --dokobot-local \
  --with-full \
  --with-sitemap-summary \
  --with-ai-suggestions
```

### 从本地文档目录生成

无需 Dokobot，直接读取本地 Markdown：

```bash
python3 scripts/generate_llms_txt.py \
  --docs-dir ./docs \
  --base-url https://docs.example.com \
  --with-full
```

### 从 GitHub README 生成

```bash
python3 scripts/generate_llms_txt.py \
  --readme https://github.com/example/project \
  --with-full
```

---

See [REFERENCE.md](REFERENCE.md) for end-to-end examples and advanced options.

The live URL flow requires a working `dokobot` CLI and browser setup. By default it stops if `robots.txt` cannot be read; use `--ignore-robots` only when you intentionally want to override that check.
