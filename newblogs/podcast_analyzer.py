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
    你是一位专业的播客内容分析师，擅长从冗长的音频转录稿中提炼深度价值。
    请仔细阅读以下播客的全文逐字稿，生成一份**深度解析报告**。
    
    ## 分析目标
    不要仅仅停留在表面内容的复述，你需要：
    1. **重构逻辑**：将碎片化的对话整理成结构清晰的逻辑流。
    2. **提炼观点**：明确区分事实（Facts）、观点（Opinions）和猜测（Speculations）。
    3. **捕捉细节**：保留关键的数据、案例、人名和引用，拒绝空洞的概括。
    
    ## 输出结构 (JSON)
    请严格按照以下 JSON 格式输出：
    {
        "title_translated": "推测的中文标题 (如果原标题晦涩，请重新拟定一个吸引人的标题)",
        "one_sentence_summary": "一句话核心总结 (50字以内，击中要害)",
        "summary": "详细深度摘要 (600-1000字)。请按以下结构组织：\n1. **背景与冲突**：讨论的话题背景是什么？核心要解决的问题或冲突是什么？\n2. **核心论点展开**：嘉宾的主要观点是什么？他们是如何论证的？(请保留具体案例和数据)\n3. **关键转折/亮点**：对话中有哪些让人眼前一亮或反直觉的时刻？\n4. **结论与展望**：最终达成了什么共识？对未来有什么预测？",
        "key_takeaways": [
            "关键洞察1 (请包含具体上下文)", 
            "关键洞察2", 
            "关键洞察3", 
            "关键洞察4", 
            "关键洞察5"
        ],
        "domain": "所属领域 (如：AI、商业、SaaS、心理学)",
        "score": 85,
        "reason": "评分理由 (基于内容的深度、新颖度和实用性打分)"
    }
    
    ## 注意事项
    - 保持客观中立的分析口吻。
    - 如果转录稿中有明显的语音识别错误，请根据上下文进行修正。
    - JSON 必须合法，不要包含 Markdown 代码块标记。
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
