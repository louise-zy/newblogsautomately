# AI Daily Digest (BestBlogs)

这是一个基于 AI 的全自动 RSS 阅读与摘要工具。它能够自动抓取指定的博客和播客源，筛选出过去 24 小时内的更新内容，并利用大语言模型（DeepSeek & Qwen）生成深度摘要日报。

## 核心功能

*   **多模态支持**：同时支持 **文本博客** 和 **音频播客**。
*   **智能摘要**：
    *   **文章**：使用 `DeepSeek-V3` 生成包含观点、数据和事实的深度摘要。
    *   **播客**：使用 `DashScope (通义听悟)` 进行 ASR 转写，再用 `Qwen-Turbo` 生成结构化的深度解析报告（背景、论点、洞察）。
*   **增量更新**：自动过滤掉旧内容，只处理过去 24 小时内发布的新闻。
*   **自动日报**：生成 Markdown 格式的日报文件，排版精美。
*   **钉钉推送**：支持将生成的日报自动推送到钉钉群机器人。

## 项目结构

```text
newblogs/
├── daily_digest.py          # [核心入口] 主程序。负责调度、RSS抓取、流程控制和日报生成。
├── podcast_analyzer.py      # [播客模块] 负责音频转写(ASR)和播客内容深度分析。
├── rss_finder.py            # [辅助工具] 用于批量检测给定网址的 RSS 订阅源。
├── known_rss_map.json       # [配置文件] 存储已知的 RSS URL 映射表。
├── channels_from_excel.json # [数据源] 博客/网站列表源文件。
├── daily_reports/           # [输出目录] 存放生成的每日 Markdown 报告。
└── PRD.md                   # 项目需求文档。
```

## 依赖配置

项目使用 `newblogs/config.json` 进行配置管理。请在运行前确保该文件存在并包含正确的 API Key。

**config.json 示例**:

```json
{
    "deepseek_api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxx",
    "deepseek_base_url": "https://api.deepseek.com",
    "deepseek_model": "deepseek-chat",
    "dashscope_api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxx",
    "dingtalk": {
        "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=xxxxxx",
        "secret": "SECxxxxxxxx"
    },
    "time_window_hours": 24,
    "limit_testing": false,
    "files": {
        "rss_map_file": "known_rss_map.json",
        "source_file": "channels_from_excel.json",
        "podcast_opml_file": "../BestBlogs_RSS_Podcasts.opml",
        "output_dir": "daily_reports"
    }
}
```

1.  **deepseek_api_key**: 用于 DeepSeek LLM (文章分析)。
2.  **dashscope_api_key**: 用于阿里云 DashScope (播客转写与分析)。
3.53.  **time_window_hours**: 抓取的时间窗口（小时），默认 24。
54.  **dingtalk**: 钉钉机器人配置（可选）。
    *   `webhook_url`: 机器人的 Webhook 地址。
    *   `secret`: 加签密钥（如果开启了加签）。
55.  **files**: 配置文件路径（相对于程序运行目录）。
    *   `rss_map_file`: 已知 RSS 映射表。
    *   `source_file`: 博客源 JSON。
    *   `podcast_opml_file`: 播客 OPML 文件。
    *   `output_dir`: 日报输出目录。

*注：也可以通过环境变量 `OPENAI_API_KEY` 和 `DASHSCOPE_API_KEY` 覆盖配置文件中的设置。*

## GitHub Actions 自动部署

本项目已配置 GitHub Actions Workflow，支持每天北京时间早上 8:00 自动运行并推送钉钉通知。

### 配置步骤

1.  将代码推送到 GitHub 仓库。
2.  在仓库 Settings -> Secrets and variables -> Actions 中添加以下 Repository secrets：
    *   `DEEPSEEK_API_KEY`: DeepSeek API Key
    *   `DASHSCOPE_API_KEY`: DashScope API Key
    *   `DINGTALK_WEBHOOK`: 钉钉机器人 Webhook 地址
    *   `DINGTALK_SECRET`: (可选) 钉钉机器人加签密钥
3.  Workflow 将自动在每天 8:00 运行。

## 如何运行

### 1. 环境准备

确保已安装 Python 3.8+ 及以下依赖库：

```bash
pip install requests feedparser html2text schedule dashscope
```

### 2. 启动程序

直接运行主脚本：

```bash
python daily_digest.py
```

程序启动后会：
1.  加载 `channels_from_excel.json` 和 `known_rss_map.json` 中的博客源。
2.  加载 `../BestBlogs_RSS_Podcasts.opml` 中的播客源。
3.  扫描所有源，寻找过去 24 小时内的更新。
4.  对发现的新文章/播客进行 AI 分析。
5.  在 `daily_reports/` 目录下生成 `Daily_Digest_YYYY-MM-DD.md`。

## 工作原理

1.  **加载源**：脚本启动时读取 JSON 和 OPML 文件，构建订阅列表。
2.  **过滤**：遍历每个 Feed 的 `entries`，比较发布时间。
    *   如果 `(当前时间 - 发布时间) < 24小时`，则标记为新内容。
3.  **分流处理**：
    *   **文本文章**：提取 HTML -> 转 Markdown -> 调用 DeepSeek 生成摘要。
    *   **播客音频**：提取 `enclosure` 音频链接 -> 调用 DashScope 进行语音转写 (ASR) -> 调用 Qwen-Turbo 基于逐字稿生成深度报告。
4.  **生成报告**：将所有分析结果汇总，写入 Markdown 文件。

## 常见问题

*   **为什么只看到很少的内容？**
    *   程序严格限制只处理**过去 24 小时**发布的内容。如果订阅源最近没有更新，或者更新时间超过了 24 小时，都会被跳过。
*   **播客分析失败？**
    *   请检查 `DASHSCOPE_API_KEY` 是否有效。
    *   部分音频格式或超长音频（超过几小时）可能偶尔导致 API 超时。

---
*Created for BestBlogs Project.*
