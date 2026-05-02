# llms-txt-generator

用于从网站、文档站点、API 项目、站点地图、README 和本地文档目录生成精选 `llms.txt` 的 Skill 脚手架与辅助脚本。

## 文件说明

- `SKILL.md`: Skill 入口文件
- `REFERENCE.md`: 工作流详细说明
- `scripts/crawl_site.py`: 来源发现、实时站点爬取、过滤与分类
- `scripts/clean_markdown.py`: Markdown 清理与链接提取
- `scripts/build_llms_txt.py`: 最终产物渲染
- `scripts/generate_llms_txt.py`: 从输入到输出的一站式编排
- `scripts/smoke_test.py`: 离线冒烟测试

## 前置要求

### 安装 Dokobot

本项目依赖 [Dokobot](https://dokobot.ai) 进行真实浏览器页面读取，支持登录墙、JS 渲染和机器人检测等复杂场景。

Dokobot 提供两种安装方式，**至少选择一种**：

#### 方式一：Chrome 扩展（推荐，一键安装）

支持 Chrome、Edge、Brave 和 Arc 浏览器。

1. 打开 [Chrome Web Store](https://chromewebstore.google.com/detail/dokobot/dlbiigchkpmpijahmlofleeemiomaneo) 安装 Dokobot 扩展。
2. 安装完成后，点击扩展图标启动本地服务。
3. 之后运行本项目时使用 `--dokobot-local` 参数即可调用。

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

## 快速开始

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

更多端到端示例和高级选项请查看 [REFERENCE.md](REFERENCE.md)。

实时 URL 流程需要可用的 `dokobot` CLI 和浏览器环境。默认情况下，如果无法读取 `robots.txt` 会停止运行；仅在您有意覆盖该检查时，才使用 `--ignore-robots`。
