import os
import json
import requests
import datetime
import sys
import re
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# ================= 配置区域 (Configuration) =================
CONFIG = {
    "API_KEY": os.getenv("API_KEY"),
    "BASE_URL": os.getenv("BASE_URL", "https://api.openai.com/v1/chat/completions"),
    "MODEL_NAME": os.getenv("MODEL_NAME", "gpt-3.5-turbo"),
    "INPUT_DIR": ".",  
    "OUTPUT_DIR": "."
}
# ===========================================================

class ConditionalSummarizer:
    def __init__(self, target_date=None):
        self.target_date = target_date or datetime.datetime.now().strftime("%Y-%m-%d")
        self.log_path = os.path.join(CONFIG["INPUT_DIR"], f"merged_{self.target_date}.txt")
        self.topics_json_path = os.path.join(CONFIG["OUTPUT_DIR"], f"topics_{self.target_date}.json")
        self.output_path = os.path.join(CONFIG["OUTPUT_DIR"], f"summary_{self.target_date}.txt")
        
    def read_files(self):
        if not os.path.exists(self.log_path):
            print(f"❌ 日志文件不存在: {self.log_path}")
            return None, None
        if not os.path.exists(self.topics_json_path):
            print(f"❌ 话题文件不存在: {self.topics_json_path}")
            return None, None
            
        with open(self.log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        with open(self.topics_json_path, 'r', encoding='utf-8') as f:
            topics = json.load(f)
            
        return lines, topics

    def extract_text_block(self, lines, start_time, end_time):
        block = []
        in_block = False
        
        # 将HH:MM:SS或HH:MM转换为HH:MM格式进行粗略比较
        start_time_short = start_time[:5] if len(start_time) >= 5 else start_time
        end_time_short = end_time[:5] if len(end_time) >= 5 else end_time
        
        # 简单提取逻辑：根据时间戳字符串匹配
        # 这里假设日志时间是有序的
        started = False
        for line in lines:
            match = re.search(r'\[(\d{2}:\d{2}:\d{2})\]', line)
            if match:
                current_time = match.group(1)
                if current_time >= start_time:
                    started = True
                if current_time > end_time:
                    if started:
                        break # 超出结束时间
            if started:
                block.append(line)
                
        return "".join(block)

    def process_topic(self, topic, text_block):
        topic_type = topic.get("topic_type", "")
        topic_name = topic.get("topic_name", "")
        
        print(f"\n🔄 正在处理话题: [{topic_type}] {topic_name}")
        
        # 策略 A：极简保留法（读书笔记/论文等）
        if any(keyword in topic_type for keyword in ["读书", "论文", "笔记"]):
            system_prompt = """你是一个内容提炼助手。
当前处理的是外部知识库内容（如读书笔记、看论文）。
【极简保留法】：因为用户有专门的文档存这些，所以你只需要保留“时间 + 书名/论文名”，把长篇大论的细节全部删掉，以节省空间。
直接输出精简后的结果即可。"""
            
        # 策略 B：深度榨取法（软件配置/小项目等）
        else:
            system_prompt = """你是一个实践经验总结助手。
当前处理的是实践经验库内容（如软件配置、小项目、折腾环境等）。
【深度榨取法】：请按照以下结构化模板进行总结提取，去除无意义的语气词和废话：
【需求/目的】：
【尝试的方法/踩的坑】：
【最终结论/成功步骤】：

直接输出上述结构的总结。"""

        payload = {
            "model": CONFIG["MODEL_NAME"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"话题：{topic_name}\n\n请处理以下内容：\n{text_block}"}
            ],
            "temperature": 0.3
        }
        
        headers = {
            "Authorization": f"Bearer {CONFIG['API_KEY']}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(CONFIG["BASE_URL"], json=payload, headers=headers, timeout=120)
            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content'].strip()
            else:
                print(f"❌ API 请求失败 ({response.status_code}): {response.text}")
                return f"处理失败: {topic_name}"
        except Exception as e:
            print(f"❌ 请求出错: {e}")
            return f"处理出错: {topic_name}"

    def run(self):
        print(f"=== 开始话题分类处理 {self.target_date} ===")
        lines, topics = self.read_files()
        if not lines or not topics:
            return

        results = []
        for idx, topic in enumerate(topics):
            start_time = topic.get("start_time", "00:00:00")
            end_time = topic.get("end_time", "23:59:59")
            
            # 补齐秒数
            if len(start_time.split(":")) == 2: start_time += ":00"
            if len(end_time.split(":")) == 2: end_time += ":59"
            
            text_block = self.extract_text_block(lines, start_time, end_time)
            
            if not text_block.strip():
                print(f"⚠️ 话题 '{topic.get('topic_name')}' 未能提取到文本内容")
                continue
                
            summary = self.process_topic(topic, text_block)
            
            results.append(f"### 话题 {idx+1}: [{topic.get('topic_type')}] {topic.get('topic_name')}\n")
            results.append(f"**时间跨度**: {start_time} - {end_time}\n")
            results.append(f"{summary}\n")
            results.append("-" * 40 + "\n")
            
        with open(self.output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(results))
            
        print(f"✅ 所有话题处理完毕！最终总结文件已保存至：{self.output_path}")
        print(f"🎉 流程结束。您可以打开该文件查看 AI 生成的分类总结。")

if __name__ == "__main__":
    target_date = None
    
    # 1. 尝试从命令行参数获取
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
    
    # 2. 如果没有参数且在交互式终端，询问用户
    if not target_date:
        print("💡 提示: 你可以直接运行 `python conditional_summarizer.py 2026-02-11` 来指定日期")
        try:
            if sys.stdin.isatty():
                date_input = input("📅 请输入日期 (YYYY-MM-DD) [回车默认今天]: ").strip()
                if date_input:
                    target_date = date_input
        except (EOFError, KeyboardInterrupt):
            print("\n")
            sys.exit(0)
        except Exception:
            pass

    # 3. 默认使用今天
    if not target_date:
        target_date = datetime.datetime.now().strftime("%Y-%m-%d")
        print(f"ℹ️ 未指定日期，默认处理今天: {target_date}")
        
    try:
        summarizer = ConditionalSummarizer(target_date)
        summarizer.run()
    except KeyboardInterrupt:
        print("\n🛑 用户手动停止程序")
    except Exception as e:
        print(f"\n❌ 程序发生未捕获异常: {e}")
        import traceback
        traceback.print_exc()
