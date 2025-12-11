import os
import json
import requests
import html2text
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

# ==========================================
# 配置区域
# ==========================================
# 请将您的 DeepSeek API Key 填入下方引号中
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "sk-f0da4ec56a0344d299f15d078ea811af") 

# DeepSeek API 配置
OPENAI_BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat" 

# ==========================================
# 核心提示词 (仅保留文章分析)
# ==========================================
ARTICLE_ANALYSIS_PROMPT = """
# 技术文章深度分析与评估专家系统

## Context（上下文）
你是一位专业技术 **文章分析专家**。你的职责是对技术文章进行深度分析和专业评估。

## Objective（目标）
1. 快速准确理解文章核心价值和创新点
2. 对文章进行专业领域分类和结构化标签标注
3. 提取文章核心观点和金句
4. 运用标准化评分体系进行质量评估 (0-100分)
5. 输出结构化 JSON 格式的专业分析报告。

## Response（响应格式）
请直接输出 JSON，不要包含 Markdown 代码块标记：
{
  "oneSentenceSummary": "一句话核心总结 (50字内)",
  "summary": "核心内容概要总结 (300-500字)",
  "domain": "所属领域 (软件编程/人工智能/产品设计/商业科技)",
  "tags": ["标签1", "标签2"],
  "mainPoints": ["核心观点1", "核心观点2"],
  "score": 85,
  "scoreReason": "评分理由"
}
"""

# ==========================================
# 工具函数
# ==========================================

def fetch_url_content(url):
    """
    通用 URL 获取函数
    """
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

def fetch_article_as_markdown(url):
    """
    获取文章并转换为 Markdown
    """
    print(f"[*] 正在抓取文章内容: {url}")
    content = fetch_url_content(url)
    if not content:
        return None
    
    try:
        # 尝试解码
        html_text = content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            html_text = content.decode('gbk')
        except:
            html_text = content.decode('utf-8', errors='ignore')

    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.body_width = 0 # 不自动换行
    markdown_content = h.handle(html_text)
    
    return markdown_content

def call_llm(system_prompt, user_content):
    """
    调用 LLM 进行分析 (无模拟模式)
    """
    print("[*] 正在请求 LLM 进行分析...")
    
    if "sk-your-deepseek-api-key-here" in OPENAI_API_KEY:
        return "Error: 请先在脚本中配置正确的 API Key"

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.5,
            "stream": False
        }
        resp = requests.post(f"{OPENAI_BASE_URL}/chat/completions", json=payload, headers=headers, timeout=60)
        
        if resp.status_code != 200:
            return f"LLM API Error: {resp.status_code} - {resp.text}"
            
        data = resp.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        return f"LLM 调用异常: {e}"

# ==========================================
# OPML 与 RSS 处理
# ==========================================

def parse_opml(opml_path):
    """
    解析 OPML 文件，提取 RSS Feed URL
    """
    print(f"[*] 正在解析 OPML 文件: {opml_path}")
    feeds = []
    try:
        tree = ET.parse(opml_path)
        root = tree.getroot()
        # 查找所有 outline 节点
        for outline in root.findall(".//outline"):
            xml_url = outline.get('xmlUrl')
            title = outline.get('title') or outline.get('text')
            if xml_url:
                feeds.append({'title': title, 'url': xml_url})
    except Exception as e:
        print(f"[-] OPML 解析失败: {e}")
    
    print(f"[+] 找到 {len(feeds)} 个订阅源")
    return feeds

def get_articles_from_rss(feed_url):
    """
    简单的 RSS 解析器，获取最新的文章链接
    """
    print(f"[*] 正在获取 RSS: {feed_url}")
    content = fetch_url_content(feed_url)
    if not content:
        return []

    articles = []
    try:
        root = ET.fromstring(content)
        # RSS 2.0
        for item in root.findall(".//item"):
            link = item.find('link').text
            title = item.find('title').text
            if link:
                articles.append({'title': title, 'link': link})
        
        # Atom (如果 RSS 2.0 没找到，尝试 Atom)
        if not articles:
            # Atom 使用 namespace，这里简化处理，直接找 entry
            # 这是一个简化的 XML 查找，实际 Atom 可能需要处理 xmlns
            for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
                link_node = entry.find("{http://www.w3.org/2005/Atom}link")
                title_node = entry.find("{http://www.w3.org/2005/Atom}title")
                if link_node is not None:
                    href = link_node.get('href')
                    title = title_node.text if title_node is not None else "No Title"
                    if href:
                        articles.append({'title': title, 'link': href})
                        
    except Exception as e:
        print(f"[-] RSS 解析警告 ({feed_url}): {e}")
    
    return articles

# ==========================================
# 主流程
# ==========================================

def run_batch_processing(opml_path, limit=5):
    """
    批量处理流程
    :param opml_path: OPML 文件路径
    :param limit: 最大处理文章数量
    """
    print(f"\n{'='*50}")
    print(f"开始批量处理 (Limit: {limit})")
    print(f"{'='*50}")

    # 1. 获取订阅源
    feeds = parse_opml(opml_path)
    if not feeds:
        print("未找到订阅源，退出。")
        return

    processed_count = 0
    
    # 2. 遍历订阅源
    for feed in feeds:
        if processed_count >= limit:
            break
            
        print(f"\n>> 正在检查订阅源: {feed['title']}")
        articles = get_articles_from_rss(feed['url'])
        
        # 3. 遍历该源下的文章 (只取前 1-2 篇以示演示，避免抓取太多)
        for article in articles[:2]: 
            if processed_count >= limit:
                break
                
            article_url = article['link']
            article_title = article.get('title', 'Unknown Title')
            
            print(f"\n  -- 处理文章 ({processed_count + 1}/{limit}): {article_title}")
            print(f"     链接: {article_url}")
            
            # 4. 获取文章正文
            markdown_content = fetch_article_as_markdown(article_url)
            if not markdown_content or len(markdown_content) < 100:
                print("     [!] 文章内容过短或无法获取，跳过")
                continue
            
            # 5. LLM 分析
            truncated_content = markdown_content[:8000] # 截断防止超长
            result_json = call_llm(ARTICLE_ANALYSIS_PROMPT, truncated_content)
            
            # 6. 打印结果
            print(f"     [LLM 分析结果]:")
            print(f"     {result_json}")
            
            processed_count += 1
            time.sleep(1) # 避免请求过快

    print(f"\n{'='*50}")
    print(f"处理完成，共分析 {processed_count} 篇文章")
    print(f"{'='*50}")

if __name__ == "__main__":
    opml_file = r"d:\ai-related\bestblogs\BestBlogs_RSS_ALL copy.opml"
    
    # 在这里设置要处理的文章总数上限
    ARTICLE_LIMIT = 10
    
    run_batch_processing(opml_file, limit=ARTICLE_LIMIT)
