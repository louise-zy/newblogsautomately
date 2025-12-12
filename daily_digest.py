import os
import json
import time
import datetime
import requests
import feedparser
import html2text
import schedule
import xml.etree.ElementTree as ET
import hmac
import hashlib
import base64
import urllib.parse
from urllib.parse import urlparse
from podcast_analyzer import analyze_podcast_audio

# ==========================================
# 配置
# ==========================================
# 加载配置文件
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(CURRENT_DIR, "config.json")

try:
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
except Exception as e:
    print(f"[-] 配置文件加载失败: {e}")
    config = {}

# API Key 配置
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", config.get("deepseek_api_key", ""))
OPENAI_BASE_URL = config.get("deepseek_base_url", "https://api.deepseek.com")
MODEL_NAME = config.get("deepseek_model", "deepseek-chat")
TIME_WINDOW_HOURS = config.get("time_window_hours", 24)
LIMIT_TESTING = config.get("limit_testing", False)

# 文件路径配置
files_config = config.get("files", {})
RSS_MAP_FILE = os.path.join(CURRENT_DIR, files_config.get("rss_map_file", "known_rss_map.json"))
SOURCE_FILE = os.path.join(CURRENT_DIR, files_config.get("source_file", "channels_from_excel.json"))
PODCAST_OPML_FILE = os.path.join(CURRENT_DIR, files_config.get("podcast_opml_file", "../BestBlogs_RSS_Podcasts.opml"))
OUTPUT_DIR = os.path.join(CURRENT_DIR, files_config.get("output_dir", "daily_reports"))

# 确保输出目录存在
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# DingTalk 配置
DINGTALK_CONFIG = config.get("dingtalk", {})
DINGTALK_WEBHOOK = os.environ.get("DINGTALK_WEBHOOK", DINGTALK_CONFIG.get("webhook_url", ""))
DINGTALK_SECRET = os.environ.get("DINGTALK_SECRET", DINGTALK_CONFIG.get("secret", ""))


# 核心 Prompt
ARTICLE_ANALYSIS_PROMPT = """
# 深度文章分析专家

## 角色
你是一位资深的行业分析师，擅长从长文中提炼高价值信息。

## 目标
深度阅读文章内容，生成一份包含关键细节的详细摘要。**拒绝空洞的套话，必须保留具体的论据、数据和事实。**

## 分析要求
1. **详细摘要 (summary)**:
   - 字数要求: 300-600字。
   - 内容要求: 必须涵盖文章的核心论点、支持这些论点的关键论据、引用的具体数据或案例、以及重要的事实陈述。
   - 风格要求: 逻辑清晰，信息密度高，让读者不看原文也能获取 90% 的关键信息。
2. **一句话总结 (one_sentence_summary)**: 50字以内，高度概括。
3. **关键洞察 (key_takeaways)**: 3-5 个具体的深度洞察。

## 输出格式 (JSON)
请直接输出 JSON，不要包含 Markdown 代码块标记，确保 JSON 格式合法：
{
  "title_translated": "中文标题",
  "one_sentence_summary": "一句话核心总结",
  "summary": "详细摘要(包含观点、论据、数据、事实)",
  "key_takeaways": ["关键洞察1", "关键洞察2", "关键洞察3"],
  "domain": "所属领域",
  "score": 85,
  "reason": "评分理由"
}
"""

# ==========================================
# 工具函数
# ==========================================

def load_rss_feeds():
    """
    加载 RSS 源列表。
    优先使用 known_rss_map.json 中的映射。
    """
    feeds = []
    
    # 1. 加载映射表
    rss_map = {}
    if os.path.exists(RSS_MAP_FILE):
        with open(RSS_MAP_FILE, 'r', encoding='utf-8') as f:
            rss_map = json.load(f)
            
    # 2. 加载源文件 (为了获取网站名称等元数据)
    if os.path.exists(SOURCE_FILE):
        with open(SOURCE_FILE, 'r', encoding='utf-8') as f:
            sources = json.load(f)
            
        for item in sources:
            url = item.get("网址")
            name = item.get("姓名")
            
            # 如果该网址有已知的 RSS
            if url in rss_map:
                feeds.append({
                    "name": name,
                    "homepage": url,
                    "rss_url": rss_map[url]
                })
            # 如果 URL 本身看起来像 RSS (虽然源文件里大部分是主页)
            elif url.endswith('.xml') or url.endswith('/feed'):
                 feeds.append({
                    "name": name,
                    "homepage": url,
                    "rss_url": url
                })
    
    print(f"[*] 已加载 {len(feeds)} 个有效的 RSS 订阅源")
    return feeds

def load_opml_feeds(file_path, limit=None):
    """
    从 OPML 文件加载播客源
    """
    feeds = []
    if not os.path.exists(file_path):
        print(f"[-] OPML 文件不存在: {file_path}")
        return feeds
        
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # 查找所有 type="rss" 的 outline
        for outline in root.findall(".//outline[@type='rss']"):
            title = outline.get("text") or outline.get("title")
            xml_url = outline.get("xmlUrl")
            
            if title and xml_url:
                feeds.append({
                    "name": title,
                    "homepage": xml_url, # 播客通常没有单独的主页 URL 字段，暂时用 rss url 代替或留空
                    "rss_url": xml_url,
                    "is_podcast": True
                })
                
    except Exception as e:
        print(f"[-] 解析 OPML 失败: {e}")
        
    print(f"[*] 已加载 {len(feeds)} 个播客源")
    
    if limit:
        print(f"[*] 限制测试: 仅保留前 {limit} 个播客源")
        feeds = feeds[:limit]
        
    return feeds

def fetch_url_content(url):
    """获取 URL 内容"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        print(f"[-] 请求失败 {url}: {e}")
        return None

def html_to_markdown(html_content):
    """HTML 转 Markdown"""
    if not html_content:
        return ""
    
    try:
        html_text = html_content.decode('utf-8')
    except:
        try:
            html_text = html_content.decode('gbk')
        except:
            html_text = html_content.decode('utf-8', errors='ignore')

    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.body_width = 0
    return h.handle(html_text)

def call_deepseek_analyze(content):
    """调用 DeepSeek 进行分析"""
    if len(content) > 10000:
        content = content[:10000] + "...(truncated)"
        
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": ARTICLE_ANALYSIS_PROMPT},
                {"role": "user", "content": content}
            ],
            "temperature": 0.5,
            "stream": False
        }
        resp = requests.post(f"{OPENAI_BASE_URL}/chat/completions", json=payload, headers=headers, timeout=60)
        
        if resp.status_code != 200:
            print(f"[-] LLM API Error: {resp.text}")
            return None
            
        result = resp.json()['choices'][0]['message']['content']
        # 清理可能的 markdown 标记
        result = result.replace('```json', '').replace('```', '').strip()
        return json.loads(result)
    except Exception as e:
        print(f"[-] LLM 分析失败: {e}")
        return None

def send_dingtalk_notification(title, text):
    """发送钉钉机器人通知 (支持长文本分段)"""
    if not DINGTALK_WEBHOOK:
        print("[-] 未配置钉钉 Webhook，跳过发送。")
        return

    webhook_url = DINGTALK_WEBHOOK
    
    # 如果配置了加签 (Secret)
    if DINGTALK_SECRET:
        timestamp = str(round(time.time() * 1000))
        secret_enc = DINGTALK_SECRET.encode('utf-8')
        string_to_sign = '{}\n{}'.format(timestamp, DINGTALK_SECRET)
        string_to_sign_enc = string_to_sign.encode('utf-8')
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        webhook_url = f"{DINGTALK_WEBHOOK}&timestamp={timestamp}&sign={sign}"

    # 分段发送逻辑
    # 钉钉限制每个消息大概 20000 字节，为了安全起见，限制在 4000 字符左右分段
    MAX_LENGTH = 4000
    
    # 简单的按长度切分可能会切断 Markdown 格式，尝试按行切分
    lines = text.split('\n')
    chunks = []
    current_chunk = ""
    
    for line in lines:
        if len(current_chunk) + len(line) + 1 > MAX_LENGTH:
            chunks.append(current_chunk)
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"
            
    if current_chunk:
        chunks.append(current_chunk)
        
    print(f"[*] 消息过长，已切分为 {len(chunks)} 条发送")

    for i, chunk in enumerate(chunks):
        # 构造消息
        # 钉钉 Markdown 消息
        chunk_title = title if i == 0 else f"{title} (Part {i+1})"
        data = {
            "msgtype": "markdown",
            "markdown": {
                "title": chunk_title,
                "text": chunk
            }
        }

        try:
            resp = requests.post(webhook_url, json=data)
            if resp.json().get("errcode") == 0:
                print(f"[+] 钉钉通知 (Part {i+1}) 发送成功")
            else:
                print(f"[-] 钉钉通知 (Part {i+1}) 发送失败: {resp.text}")
            
            # 稍微延时避免触发频率限制
            time.sleep(1)
            
        except Exception as e:
            print(f"[-] 发送钉钉请求异常: {e}")

def process_feed(feed):
    """处理单个 RSS Feed"""
    print(f"[*] 正在检查: {feed['name']} ({feed['rss_url']})")
    
    try:
        # 解析 RSS
        d = feedparser.parse(feed['rss_url'])
        
        today_articles = []
        # 定义 "今天" 的范围 (过去 24 小时)
        now = datetime.datetime.now()
        
        for entry in d.entries:
            # 获取发布时间
            published_time = None
            if hasattr(entry, 'published_parsed'):
                published_time = datetime.datetime.fromtimestamp(time.mktime(entry.published_parsed))
            elif hasattr(entry, 'updated_parsed'):
                published_time = datetime.datetime.fromtimestamp(time.mktime(entry.updated_parsed))
            
            # 如果没有时间，或者时间在 24 小时内
            is_new = False
            if published_time:
                # 简单判断：过去 TIME_WINDOW_HOURS 小时
                if (now - published_time).total_seconds() < TIME_WINDOW_HOURS * 3600:
                    is_new = True
            else:
                pass 
            
            if is_new:
                print(f"  [+] 发现新内容: {entry.title}")
                link = entry.link
                analysis = None
                is_podcast_entry = False

                # 检查是否为播客 (Audio Enclosure)
                audio_url = None
                if hasattr(entry, 'enclosures'):
                    for enclosure in entry.enclosures:
                        if enclosure.type and enclosure.type.startswith('audio/'):
                            audio_url = enclosure.href
                            break
                
                # 如果是播客源或者是音频内容
                if audio_url:
                    is_podcast_entry = True
                    print(f"   [🎙️] 识别为播客音频: {audio_url}")
                    analysis = analyze_podcast_audio(audio_url)
                else:
                    # 普通文章
                    content_html = fetch_url_content(link)
                    content_md = html_to_markdown(content_html)
                    if content_md:
                         analysis = call_deepseek_analyze(content_md)

                if analysis:
                    today_articles.append({
                        "original_title": entry.title,
                        "link": link,
                        "author": feed['name'],
                        "published": published_time.strftime("%Y-%m-%d %H:%M") if published_time else "Unknown",
                        "analysis": analysis,
                        "is_podcast": is_podcast_entry
                    })
            else:
                if published_time:
                    print(f"  [-] 跳过旧内容: {entry.title} ({published_time})")
                else:
                    print(f"  [-] 跳过无时间戳内容: {entry.title}")
                        
        return today_articles
        
    except Exception as e:
        print(f"[-] 处理 Feed 失败 {feed['rss_url']}: {e}")
        return []

def generate_daily_report(articles):
    """生成日报 Markdown"""
    if not articles:
        print("[!] 今天没有新文章，不生成报告。")
        return
    
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    filename = f"Daily_Digest_{date_str}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# 📅 Daily RSS Digest - {date_str}\n\n")
        f.write(f"> 今日共更新 {len(articles)} 篇文章\n\n")
        f.write("---\n\n")
        
        for i, article in enumerate(articles, 1):
            analysis = article['analysis']
            title_prefix = "[🎙️ 播客] " if article.get('is_podcast') else ""
            f.write(f"## {i}. {title_prefix}{analysis.get('title_translated', article['original_title'])}\n\n")
            f.write(f"- **来源**: {article['author']}\n")
            f.write(f"- **发布时间**: {article['published']}\n")
            f.write(f"- **原文链接**: [点击阅读]({article['link']})\n")
            f.write(f"- **领域**: `{analysis.get('domain', '未知')}`\n")
            f.write(f"- **评分**: {analysis.get('score', 0)} / 100\n\n")
            
            f.write(f"### 📝 核心摘要\n")
            f.write(f"> **{analysis.get('one_sentence_summary', '')}**\n\n")
            f.write(f"{analysis.get('summary', '')}\n\n")
            
            f.write(f"### 💡 关键洞察\n")
            for point in analysis.get('key_takeaways', []):
                f.write(f"- {point}\n")
            
            f.write(f"\n> *评分理由: {analysis.get('reason', '')}*\n\n")
            f.write("---\n\n")
            
    print(f"\n[√] 日报已生成: {filepath}")
    
    # 读取生成的文件内容用于发送
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 发送钉钉通知
    # 钉钉有消息长度限制，这里做个简单截断保护，或者仅发送摘要链接（如果有在线版）
    # 目前我们发送全量，如果过长可能需要切割
    if content:
        send_dingtalk_notification(f"RSS Daily Digest {date_str}", content)
        
    return filepath

def job():
    print(f"\n[{datetime.datetime.now()}] 开始执行每日任务...")
    
    # 确定限制数量
    limit_count = None
    if LIMIT_TESTING:
        # 如果是 True，默认限制为 1；如果是数字，则使用该数字
        limit_count = 1 if isinstance(LIMIT_TESTING, bool) else int(LIMIT_TESTING)
        print(f"[*] 测试模式开启: 仅处理前 {limit_count} 个源")

    # 1. 加载文章 RSS
    feeds = load_rss_feeds()
    if limit_count:
        feeds = feeds[:limit_count]
    
    # 2. 加载播客 RSS
    podcast_feeds = load_opml_feeds(PODCAST_OPML_FILE, limit=limit_count)
    feeds.extend(podcast_feeds)
    
    all_articles = []
    
    for feed in feeds:
        articles = process_feed(feed)
        all_articles.extend(articles)
        
    generate_daily_report(all_articles)
    print(f"[{datetime.datetime.now()}] 任务完成。\n")

if __name__ == "__main__":
    print("Daily Digest Service Started...")
    
    # 立即运行一次测试
    job()
    
    # 设置定时任务 (例如每天早上 08:00)
    # schedule.every().day.at("08:00").do(job)
    
    # while True:
    #     schedule.run_pending()
    #     time.sleep(60)
