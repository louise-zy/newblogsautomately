# AI Daily Digest (BestBlogs)

这是一个基于 AI 的全自动 RSS 阅读与摘要工具。它能够自动抓取指定的博客和播客源，筛选出过去 24 小时内的更新内容，并利用大语言模型（DeepSeek & Qwen）生成深度摘要日报。

## 核心功能

*   **多模态支持**：同时支持 **文本博客** 和 **音频播客**。
*   **智能摘要**：
    *   **文章**：使用 `DeepSeek-V3` 生成包含观点、数据和事实的深度摘要。
    *   **播客**：使用 `DashScope (通义听悟)` 进行 ASR 转写，再用 `Qwen-Turbo` 生成结构化的深度解析报告（背景、论点、洞察）。
*   **增量更新**：自动过滤掉旧内容，只处理过去 24 小时内发布的新闻。
*   **自动日报**：生成 Markdown 格式的日报文件，排版精美。

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

项目运行需要以下环境变量（API Key）：

1.  **OPENAI_API_KEY**: 用于 DeepSeek LLM (文章分析)。
    *   *默认配置在 `daily_digest.py` 中*
2.  **DASHSCOPE_API_KEY**: 用于阿里云 DashScope (播客转写与分析)。
    *   *默认配置在 `podcast_analyzer.py` 中*

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
