import os
import json
import requests
import datetime
import sys
import re
import time
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

class TopicRouter:
    def __init__(self, target_date=None):
        self.target_date = target_date or datetime.datetime.now().strftime("%Y-%m-%d")
        self.input_path = os.path.join(CONFIG["INPUT_DIR"], f"merged_{self.target_date}.txt")
        self.output_json_path = os.path.join(CONFIG["OUTPUT_DIR"], f"topics_{self.target_date}.json")
        
    def read_logs(self):
        if not os.path.exists(self.input_path):
            print(f"❌ 输入文件不存在: {self.input_path}")
            return None
        with open(self.input_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _clean_json_response(self, text):
        text = re.sub(r'^```json\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
        return text.strip()

    def find_topics(self, text):
        system_prompt = """你是一个话题嗅探器（Topic Router）。你的任务是阅读用户的日志全文（带时间戳）。
不要总结内容！只做“分类”和“划界”。
请像一个图书管理员一样，通读全文，然后告诉我：“从时间戳 A 到时间戳 B，这部分在聊同一个话题。”
可能存在的话题类型有：读书笔记、软件配置、小项目、看论文相关等。
必须输出一个结构化的 JSON 数组。
JSON 示例：
[
  {"start_time": "10:00:00", "end_time": "10:30:00", "topic_type": "读书笔记", "topic_name": "《某本书》"},
  {"start_time": "10:35:00", "end_time": "11:20:00", "topic_type": "软件配置", "topic_name": "配置 LobeChat"}
]
直接返回 JSON 数组，不要输出 markdown 标记。"""

        payload = {
            "model": CONFIG["MODEL_NAME"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请对以下日志文本进行话题划界：\n\n{text}"}
            ],
            "temperature": 0.1
        }
        
        headers = {
            "Authorization": f"Bearer {CONFIG['API_KEY']}",
            "Content-Type": "application/json"
        }

        print("🚀 正在向 AI 发送日志全文以嗅探话题...")
        try:
            # Note: adjust URL if BASE_URL already has /chat/completions or not
            url = CONFIG["BASE_URL"]
            if not url.endswith("/chat/completions"):
                url = f"{url.rstrip('/')}/chat/completions"
                
            response = requests.post(url, json=payload, headers=headers, timeout=120)
            if response.status_code == 200:
                data = response.json()
                content = data['choices'][0]['message']['content']
                cleaned_content = self._clean_json_response(content)
                
                try:
                    topics = json.loads(cleaned_content)
                    return topics
                except json.JSONDecodeError:
                    print(f"⚠️ JSON 解析失败，AI 返回内容:\n{content}")
                    return None
            else:
                print(f"❌ API 请求失败 ({response.status_code}): {response.text}")
                return None
        except Exception as e:
            print(f"❌ 请求出错: {e}")
            return None

    def run(self):
        print(f"=== 开始话题嗅探 {self.target_date} ===")
        text = self.read_logs()
        if not text:
            return

        topics = self.find_topics(text)
        if topics:
            with open(self.output_json_path, 'w', encoding='utf-8') as f:
                json.dump(topics, f, ensure_ascii=False, indent=2)
            print(f"✅ 话题嗅探完成！已生成话题配置文件：{self.output_json_path}")
            print(f"💡 提示：您可以打开该 JSON 文件检查话题划分是否准确，如有需要可手动微调时间戳或话题类型。")
            print(f"👉 下一步：请运行 `conditional_summarizer.py` 进行最终的内容总结。")
        else:
            print("⚠️ 未能提取到话题。")

if __name__ == "__main__":
    target_date = None
    
    # 1. 尝试从命令行参数获取
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
    
    # 2. 如果没有参数且在交互式终端，询问用户
    # 注意：某些 IDE 的“运行”按钮可能也会触发此逻辑
    if not target_date:
        print("💡 提示: 你可以直接运行 `python topic_router.py 2026-02-11` 来指定日期")
        try:
            # 增加 try-except 以防环境不支持 input (虽然极少见)
            if sys.stdin.isatty():
                date_input = input("📅 请输入日期 (YYYY-MM-DD) [回车默认今天]: ").strip()
                if date_input:
                    target_date = date_input
        except (EOFError, KeyboardInterrupt):
            print("\n")
            sys.exit(0)
        except Exception:
            # 如果 input() 失败（非交互式环境），忽略并使用默认
            pass

    # 3. 默认使用今天
    if not target_date:
        target_date = datetime.datetime.now().strftime("%Y-%m-%d")
        print(f"ℹ️ 未指定日期，默认处理今天: {target_date}")
        
    try:
        router = TopicRouter(target_date)
        router.run()
    except KeyboardInterrupt:
        print("\n🛑 用户手动停止程序")
    except Exception as e:
        print(f"\n❌ 程序发生未捕获异常: {e}")
        import traceback
        traceback.print_exc()
