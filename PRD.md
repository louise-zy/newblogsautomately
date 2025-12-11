# 项目需求文档 (PRD): Daily RSS Digest with DeepSeek

## 1. 项目概述
本项目旨在构建一个自动化工具，每日定时抓取指定网站的 RSS 订阅源，筛选当天更新的文章，利用 DeepSeek LLM 进行深度摘要分析，并将分析结果汇总推送给用户。

## 2. 核心功能

### 2.1 订阅源管理
- **输入**: 支持读取 `channels_from_excel.json` 或自定义的 RSS 列表文件。
- **动态探测**: (可选) 对于未直接提供 RSS 的 URL，复用之前的 RSS 探测逻辑进行动态获取。

### 2.2 内容抓取与过滤
- **定时任务**: 每天固定时间（如早上 8:00）运行。
- **增量更新**: 仅抓取 **过去 24 小时内** 更新的文章。
- **内容提取**: 
  - 解析 RSS Feed 获取文章标题、链接、发布时间。
  - 访问原文链接，将 HTML 转换为 Markdown 格式，以便 LLM 处理。

### 2.3 智能分析 (DeepSeek LLM)
- **核心能力**: 使用 DeepSeek V3 (或类似模型) 对长文章进行分析。
- **分析维度**:
  - 一句话核心总结
  - 3-5 个关键点 (Key Takeaways)
  - 领域分类与标签
  - 评分 (0-100)
- **Prompt 优化**: 复用现有的 `ARTICLE_ANALYSIS_PROMPT` 并进行微调。

### 2.4 汇总与推送 (Push)
- **报告生成**: 将所有当天的分析结果汇总为一个日报 (Markdown/HTML)。
- **推送渠道 (待确认)**:
  - 选项 A: 生成本地 Markdown/HTML 文件。
  - 选项 B: 发送邮件 (SMTP)。
  - 选项 C: 飞书/钉钉/企业微信 Webhook 机器人。
  - 选项 D: Telegram Bot。

## 3. 技术方案

### 3.1 技术栈
- **语言**: Python 3.8+
- **依赖库**:
  - `feedparser`: 健壮的 RSS/Atom 解析库 (优于手动 XML 解析)。
  - `requests`: 网络请求。
  - `html2text`: HTML 转 Markdown。
  - `schedule`: 轻量级定时任务调度 (或使用 GitHub Actions / 系统 Cron)。
  - `openai` (官方 SDK) 或 `requests`: 调用 DeepSeek API。

### 3.2 数据流
1. **Load Config**: 读取 RSS URL 列表。
2. **Fetch Feeds**: 遍历 URL，使用 `feedparser` 获取条目。
3. **Filter**: `entry.published_parsed` > `24h_ago`。
4. **Scrape Content**: 获取原文 -> 清洗 -> Markdown。
5. **Analyze**: 调用 DeepSeek API -> JSON 结果。
6. **Report**: 模板渲染 -> 生成日报。
7. **Notify**: 发送通知。

### 3.3 目录结构建议
```
d:\ai-related\bestblogs\newblogs\
├── daily_digest.py        # 主程序
├── config.json            # 配置文件 (RSS 列表, API Key)
├── templates/             # 报告模板
│   └── report_template.md
├── output/                # 存放生成的日报
└── utils/                 # 工具函数
    ├── rss_fetcher.py
    ├── llm_client.py
    └── notifier.py
```

## 4. 待确认事项
1. **推送方式**: 您希望通过什么方式接收日报？(邮件、本地文件、即时通讯软件?)
2. **运行环境**: 是在您的本地电脑长期运行，还是部署在服务器/GitHub Actions 上？
3. **DeepSeek API**: 确认您已拥有有效的 API Key。
