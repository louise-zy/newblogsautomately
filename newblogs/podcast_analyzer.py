import json
import os
import time
import requests
from dashscope.audio.asr import Transcription
from dashscope import Generation
import dashscope

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "sk-e28a0c76241a48f4b30458ad598e1ae1")
dashscope.api_key = DASHSCOPE_API_KEY

def transcribe_audio(audio_url):
    print(f"[*] 提交音频转写任务: {audio_url}")
    try:
        task_response = Transcription.async_call(
            model='paraformer-v1',
            file_urls=[audio_url]
        )
        
        if task_response.status_code != 200:
            print(f"[-] 转写提交失败: {task_response.message}")
            return None
            
        task_id = task_response.output.task_id
        print(f"[*] 转写任务ID: {task_id}，等待完成...")
        
        # 轮询等待
        status = 'PENDING'
        while status in ['PENDING', 'RUNNING']:
            time.sleep(10) # 每10秒检查一次
            response = Transcription.fetch(task=task_id)
            if response.status_code != 200:
                print(f"[-] 获取转写状态失败: {response.message}")
                return None
            
            status = response.output.task_status
            if status == 'SUCCEEDED':
                # 获取结果
                results = response.output.results
                if results and len(results) > 0:
                    transcription_url = results[0].get('transcription_url')
                    if transcription_url:
                        print(f"[*] 获取到转写结果URL，正在下载...")
                        r = requests.get(transcription_url)
                        r.encoding = 'utf-8'
                        trans_data = r.json()
                        
                        full_text = ""
                        # paraformer-v1 JSON structure usually has 'transcripts' list
                        if 'transcripts' in trans_data:
                            for t in trans_data['transcripts']:
                                full_text += t.get('text', '') + "\n"
                        return full_text
                    else:
                         print(f"[-] 未找到转写结果URL: {results}")
                         return None
            elif status == 'FAILED':
                print(f"[-] 转写失败: {response.output}")
                return None
                
    except Exception as e:
        print(f"[-] 转写异常: {e}")
        return None

def analyze_podcast_audio(audio_url):
    # 1. Transcribe
    text = transcribe_audio(audio_url)
    if not text:
        return None
        
    print(f"[*] 音频转写完成，字数: {len(text)}，开始生成摘要...")
    
    # 2. Summarize using Qwen-Turbo (Text)
    prompt = """
    你是一位专业的播客内容分析师。请阅读以下播客的全文逐字稿，并生成一份详细的摘要分析。
    
    请输出 JSON 格式，包含以下字段：
    {
        "title_translated": "推测的中文标题",
        "one_sentence_summary": "一句话核心总结",
        "summary": "详细摘要(300-500字)，包含核心观点、论据和重要事实",
        "key_takeaways": ["关键洞察1", "关键洞察2", "关键洞察3"],
        "domain": "所属领域",
        "score": 85,
        "reason": "评分理由"
    }
    
    注意：请确保输出合法的 JSON 格式。
    """
    
    try:
        # 截断过长的文本，保留前 30000 字符 (Qwen-Turbo 支持长上下文，但为了稳妥)
        if len(text) > 30000:
            text = text[:30000] + "...(truncated)"
            
        messages = [
            {'role': 'system', 'content': 'You are a helpful assistant.'},
            {'role': 'user', 'content': f"{prompt}\n\n播客内容:\n{text}"}
        ]
        
        response = Generation.call(
            model='qwen-turbo',
            messages=messages,
            result_format='message'
        )
        
        if response.status_code == 200:
            content = response.output.choices[0].message.content
            # 清理 Markdown
            content = content.replace('```json', '').replace('```', '').strip()
            # 尝试找到 JSON 的起止
            if '{' in content and '}' in content:
                start = content.find('{')
                end = content.rfind('}') + 1
                content = content[start:end]
            
            return json.loads(content)
        else:
            print(f"[-] Qwen 摘要生成失败: {response.message}")
            return None
            
    except Exception as e:
        print(f"[-] 摘要生成异常: {e}")
        return None
