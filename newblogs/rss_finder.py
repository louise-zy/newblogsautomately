import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import concurrent.futures

# ==========================================
# 配置
# ==========================================
# 常见的 RSS 路径后缀，用于暴力猜测
COMMON_RSS_PATHS = [
    '/feed',
    '/rss',
    '/atom.xml',
    '/feed.xml',
    '/rss.xml',
    '/index.xml'
]

def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

def find_rss_for_url(url):
    """
    探测单个 URL 的 RSS 地址
    """
    print(f"[*] 正在扫描: {url}")
    if not url.startswith('http'):
        url = 'https://' + url
        
    found_feeds = set()
    
    try:
        # 1. 获取首页内容
        resp = requests.get(url, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # 2. 方法一：检查 <head> 中的 <link> 标签 (最标准的方式)
        # 查找 type 为 application/rss+xml 或 application/atom+xml 的 link
        links = soup.find_all('link', type=['application/rss+xml', 'application/atom+xml'])
        for link in links:
            href = link.get('href')
            if href:
                full_url = urljoin(url, href)
                found_feeds.add(full_url)
                print(f"    [+] 发现 (Head Link): {full_url}")

        # 3. 方法二：扫描页面上的 <a> 标签 (通常在页脚)
        a_tags = soup.find_all('a')
        for a in a_tags:
            href = a.get('href')
            text = a.get_text().lower()
            if not href:
                continue
                
            # 检查链接文本或 href 是否包含 rss/feed 关键词
            if 'rss' in text or 'feed' in text or 'atom' in text or \
               'rss' in href.lower() or '/feed' in href.lower():
                
                # 排除一些明显的干扰项
                if 'twitter' in href or 'facebook' in href or 'linkedin' in href:
                    continue
                    
                full_url = urljoin(url, href)
                # 简单验证一下这个链接是不是 xml
                if full_url not in found_feeds:
                     # 这里可以做更深度的验证，但为了速度先通过后缀判断
                    if full_url.endswith('.xml') or full_url.endswith('/feed') or full_url.endswith('/rss'):
                         found_feeds.add(full_url)
                         print(f"    [+] 发现 (A Tag): {full_url}")

        # 4. 方法三：如果都没找到，尝试常见路径猜测 (暴力尝试)
        if not found_feeds:
            print("    [?] 标准方法未找到，尝试常见路径猜测...")
            for path in COMMON_RSS_PATHS:
                guess_url = urljoin(url, path)
                try:
                    head_resp = requests.head(guess_url, headers=get_headers(), timeout=5)
                    if head_resp.status_code == 200:
                        content_type = head_resp.headers.get('Content-Type', '').lower()
                        if 'xml' in content_type:
                            found_feeds.add(guess_url)
                            print(f"    [+] 发现 (Guess): {guess_url}")
                            break # 找到一个就停止
                except:
                    pass

    except Exception as e:
        print(f"    [-] 扫描失败: {e}")
        return None

    return list(found_feeds)

def batch_find_rss(url_list):
    """
    批量探测
    """
    print(f"\n{'='*50}")
    print(f"开始批量 RSS 探测 (共 {len(url_list)} 个网站)")
    print(f"{'='*50}\n")
    
    results = {}
    
    # 使用线程池并发处理，加快速度
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {executor.submit(find_rss_for_url, url): url for url in url_list}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                feeds = future.result()
                if feeds:
                    results[url] = feeds
                else:
                    print(f"    [-] {url} 未找到 RSS")
            except Exception as e:
                print(f"    [-] {url} 处理异常: {e}")
                
    return results

import json
import os

if __name__ == "__main__":
    # ==========================================
    # 从 JSON 文件读取网站列表
    # ==========================================
    
    # 获取当前脚本所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(current_dir, "channels_from_excel.json")
    
    print(f"[*] 正在读取 JSON 文件: {json_path}")
    
    if not os.path.exists(json_path):
        print(f"[-] 错误: 文件不存在 {json_path}")
        exit(1)
        
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # 提取所有 "网址" 字段
        test_sites = []
        for item in data:
            url = item.get("网址")
            # 简单的 URL 验证
            if url and len(url) > 5:
                # 清理 URL (比如 json 中的转义符)
                url = url.replace('\\/', '/')
                test_sites.append(url)
                
        # 去重
        test_sites = list(set(test_sites))
                
        print(f"[+] 成功提取 {len(test_sites)} 个网址")
        
        # 开始批量探测
        found = batch_find_rss(test_sites)
        
        print(f"\n{'='*50}")
        print("最终结果汇总:")
        print(f"{'='*50}")
        
        # 简单的统计
        success_count = len(found)
        print(f"成功找到 RSS: {success_count} / {len(test_sites)}")
        
        for site, feeds in found.items():
            print(f"\n[网站]: {site}")
            for feed in feeds:
                print(f"  - {feed}")
                
    except Exception as e:
        print(f"[-] 发生错误: {e}")
