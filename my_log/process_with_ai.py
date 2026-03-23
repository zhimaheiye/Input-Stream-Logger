import os
import re
import datetime
import json
import requests
import sys
import time
from typing import List, Dict
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# ================= 配置区域 (Configuration) =================
CONFIG = {
    # API 配置
    "API_KEY": os.getenv("API_KEY"),
    "BASE_URL": os.getenv("BASE_URL", "https://api.openai.com/v1"),
    "MODEL_NAME": os.getenv("MODEL_NAME", "gpt-3.5-turbo"),
    
    # 路径配置 (默认为当前目录)
    "INPUT_DIR": ".",  
    "OUTPUT_DIR": ".",
    
    # 逻辑参数
    "CHUNK_SIZE": 10,         # (条) 每次发给 AI 处理的句子数量
    "REQUEST_INTERVAL": 1.0,  # (秒) 基础 API 请求间隔
    "RETRY_COUNT": 5,         # 增加重试次数
    "MAX_BACKOFF": 32         # (秒) 最大退避时间
}
# ===========================================================

class AIProcessor:
    def __init__(self, target_date=None):
        # 如果未指定日期，默认处理今天
        self.target_date = target_date or datetime.datetime.now().strftime("%Y-%m-%d")
        
        # 构造文件路径
        self.input_path = os.path.join(CONFIG["INPUT_DIR"], f"merged_{self.target_date}.txt")
        # 输出文件改为 .jsonl 格式，方便后续处理，同时也生成 .md 方便阅读
        self.output_json_path = os.path.join(CONFIG["OUTPUT_DIR"], f"Knowledge_{self.target_date}_cleaned.jsonl")
        self.output_md_path = os.path.join(CONFIG["OUTPUT_DIR"], f"Knowledge_{self.target_date}_cleaned.md")
        
        # 初始化已处理的时间戳集合（用于断点续传）
        self.processed_times = self._load_processed_times()
        
        self.session = self._init_session()

    def _load_processed_times(self):
        """读取已存在的 JSONL 文件，加载已处理的时间点，避免重复处理"""
        processed = set()
        if os.path.exists(self.output_json_path):
            print(f"🔄 检测到已有进度文件，正在加载已处理数据...")
            try:
                with open(self.output_json_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            item = json.loads(line.strip())
                            if "time" in item:
                                processed.add(item["time"])
                        except json.JSONDecodeError:
                            continue
                print(f"✅ 已加载 {len(processed)} 条历史记录，将跳过重复内容")
            except Exception as e:
                print(f"⚠️ 读取历史进度失败: {e}")
        return processed

    def _init_session(self):
        """初始化持久化 HTTP 会话"""
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {CONFIG['API_KEY']}",
            "Content-Type": "application/json"
        })
        return session

    def read_merged_logs(self) -> List[str]:
        """读取合并后的日志文件"""
        if not os.path.exists(self.input_path):
            print(f"❌ 输入文件不存在: {self.input_path}")
            print(f"💡 请先运行 merge_logs.py 生成合并后的日志文件")
            return []

        print(f"📂 读取合并日志: {self.input_path}")
        try:
            with open(self.input_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            print(f"✅ 读取完成: {len(lines)} 条句子")
            return lines
        except Exception as e:
            print(f"❌ 读取文件失败: {e}")
            return []

    def _clean_json_response(self, text):
        """尝试清洗 LLM 返回的 JSON 字符串"""
        # 移除 Markdown 代码块标记 ```json ... ```
        text = re.sub(r'^```json\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
        return text.strip()

    def _call_llm(self, chunk_text) -> List[Dict]:
        """调用 LLM API 进行提取，期望返回 JSON 格式"""
        
        # 优化后的 System Prompt：强调 JSON 输出，简化任务
        system_prompt = """你是一个日志分析助手。你的任务是读取用户的语音转录日志，并提取出**有意义的事实、操作或计划**。

请遵循以下规则：
1. **输入**：一段包含时间戳的日志文本。
2. **任务**：
   - 忽略无意义的语气词、碎片、乱码（如 "sil", "/", "..."）。
   - 提取用户明确提到的**动作**（如"修改代码"、"打开网页"）、**数据**（如"报错500"、"攻击力100"）或**计划**（如"明天开会"）。
   - 如果某句话完全是废话或无法理解，请直接忽略，不要输出。
3. **输出格式**：
   - 必须是标准的 **JSON 数组**。
   - 每个元素包含 `time` (时间字符串), `type` (类型: Action/Data/Plan/Other), `content` (提取的内容, 简练概括)。
   - **不要输出 markdown 标记**（如 ```json），直接输出 JSON 字符串。

**输入示例**:
[10:00:01] 哎，我先把这个窗口关了
[10:00:05] 改成 20 试试
[10:00:10] 报错 Error 404

**输出示例**:
[
  {"time": "10:00:01", "type": "Action", "content": "关闭窗口"},
  {"time": "10:00:05", "type": "Action", "content": "参数修改为 20"},
  {"time": "10:00:10", "type": "Data", "content": "报错 Error 404"}
]
"""
        
        user_content = f"请将以下日志转换为 JSON 数组（若无有效信息则返回空数组 []）：\n\n{chunk_text}"

        payload = {
            "model": CONFIG["MODEL_NAME"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.1,
            "max_tokens": 2048
        }

        # 指数退避策略
        delay = CONFIG["REQUEST_INTERVAL"]
        
        for attempt in range(CONFIG["RETRY_COUNT"]):
            try:
                response = self.session.post(CONFIG["BASE_URL"], json=payload, timeout=60)
                
                # 处理 429 (Too Many Requests) 和 403 (Limit Exceeded)
                if response.status_code in [429, 403]:
                    if attempt < CONFIG["RETRY_COUNT"] - 1:
                        print(f"⏳ 触发限流 ({response.status_code})，等待 {delay:.1f} 秒后重试...")
                        time.sleep(delay)
                        delay = min(delay * 2, CONFIG["MAX_BACKOFF"]) # 指数退避，最大 32s
                        continue
                    else:
                        print(f"❌ 多次重试后仍限流，跳过此批次。")
                        return []
                
                if response.status_code != 200:
                    print(f"❌ API 错误 {response.status_code}: {response.text}")
                    # 某些 400 可能是参数问题，不建议重试，但偶尔网络抖动也可能导致
                    if response.status_code >= 500: # 服务器错误可以重试
                         time.sleep(1)
                         continue
                    return []

                data = response.json()
                if 'choices' in data and len(data['choices']) > 0:
                    content = data['choices'][0]['message']['content']
                    cleaned_content = self._clean_json_response(content)
                    
                    try:
                        # 尝试解析 JSON
                        parsed_data = json.loads(cleaned_content)
                        # 兼容处理
                        if isinstance(parsed_data, dict):
                            for key in parsed_data:
                                if isinstance(parsed_data[key], list):
                                    parsed_data = parsed_data[key]
                                    break
                            else:
                                parsed_data = [parsed_data]
                        
                        if isinstance(parsed_data, list):
                            return parsed_data
                        else:
                            print(f"⚠️ 解析出的 JSON 不是列表: {type(parsed_data)}")
                            return []
                            
                    except json.JSONDecodeError:
                        print(f"⚠️ JSON 解析失败，内容预览: {cleaned_content[:50]}...")
                        return []
                else:
                    return []
            
            except requests.exceptions.RequestException as e:
                print(f"⚠️ 网络请求失败 (尝试 {attempt+1}/{CONFIG['RETRY_COUNT']}): {e}")
                time.sleep(delay)
                delay = min(delay * 2, CONFIG["MAX_BACKOFF"])
            except Exception as e:
                print(f"⚠️ 未知错误: {e}")
                time.sleep(1)
        
        return []

    def _append_results(self, results: List[Dict]):
        """实时追加保存结果"""
        if not results:
            return

        try:
            os.makedirs(os.path.dirname(self.output_json_path) if os.path.dirname(self.output_json_path) else ".", exist_ok=True)
            with open(self.output_json_path, 'a', encoding='utf-8') as f:
                for item in results:
                    # 再次检查是否重复（虽然处理前检查过，但防止 batch 内部重复）
                    if item.get("time") not in self.processed_times:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")
                        self.processed_times.add(item.get("time"))
        except Exception as e:
            print(f"❌ 追加写入 JSONL 失败: {e}")

    def process_chunks(self, logs) -> List[Dict]:
        """分块处理日志"""
        if not logs:
            return []

        all_results = []
        chunk_size = CONFIG["CHUNK_SIZE"]
        total_chunks = (len(logs) + chunk_size - 1) // chunk_size

        print(f"🚀 开始 AI 提取，共 {total_chunks} 个批次 (每批 {chunk_size} 条)...")
        
        for i in range(0, len(logs), chunk_size):
            batch = logs[i:i + chunk_size]
            
            # 断点续传检查：
            # 提取 batch 中第一条日志的时间戳
            first_log_time = None
            try:
                # batch[0] 格式如 "[07:07:43] 内容..."
                match = re.match(r'\[(\d{2}:\d{2}:\d{2})\]', batch[0])
                if match:
                    first_log_time = match.group(1)
            except:
                pass

            # 如果该批次的起始时间已经在已处理列表中，极大概率是已经跑过的批次
            # 为了节省 API 调用和避免重复，直接跳过
            if first_log_time and first_log_time in self.processed_times:
                print(f"   ⏭️ 批次 {i//chunk_size + 1} 已处理 (时间点 {first_log_time} 存在)，跳过。")
                continue

            batch_text = "\n".join(batch)
            
            print(f"   正在处理批次 {i//chunk_size + 1}/{total_chunks} ...", end="\r")
            
            batch_results = self._call_llm(batch_text)
            
            if batch_results:
                # 立即保存这一批次的结果
                self._append_results(batch_results)
                all_results.extend(batch_results)
                print(f"   ✅ 批次 {i//chunk_size + 1} 完成，保存 {len(batch_results)} 条数据。")
            else:
                print(f"   ⚠️ 批次 {i//chunk_size + 1} 未提取到数据或失败。")
            
            time.sleep(CONFIG["REQUEST_INTERVAL"])

        print(f"\n✅ 提取完成，本次共获取 {len(all_results)} 条新数据")
        return all_results

    def generate_final_report(self):
        """最后根据 JSONL 生成一次完整的 Markdown 报告"""
        if not os.path.exists(self.output_json_path):
            return

        print("📊 正在生成最终 Markdown 报告...")
        try:
            # 读取所有 JSONL 数据并按时间排序
            all_data = []
            with open(self.output_json_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        all_data.append(json.loads(line))
                    except:
                        continue
            
            # 按时间排序
            all_data.sort(key=lambda x: x.get("time", ""))
            
            with open(self.output_md_path, 'w', encoding='utf-8') as f:
                f.write(f"# 知识清洗记录 {self.target_date}\n")
                f.write(f"> 最后更新: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("| 时间 | 类型 | 内容 |\n")
                f.write("|---|---|---|\n")
                for item in all_data:
                    time_str = item.get("time", "??:??:??")
                    dtype = item.get("type", "Info")
                    content = item.get("content", "").replace("\n", " ")
                    f.write(f"| {time_str} | {dtype} | {content} |\n")
            
            print(f"💾 Markdown 报告已更新: {self.output_md_path}")
        except Exception as e:
            print(f"❌ 生成 Markdown 报告失败: {e}")

    def run(self):
        print(f"=== 开始 AI 处理 {self.target_date} 的日志 ===")
        # 1. 读取合并后的日志
        merged_logs = self.read_merged_logs()
        
        # 2. 分块提取 (内部包含实时保存)
        if merged_logs:
            self.process_chunks(merged_logs)
            
            # 3. 最后生成可视化报告
            self.generate_final_report()
        else:
            print("⚠️ 无数据可处理。")

if __name__ == "__main__":
    # 处理命令行参数或用户输入
    target_date = None
    
    # 1. 尝试从命令行参数获取
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
    
    # 2. 如果没有参数且在交互式终端，询问用户
    if not target_date and sys.stdin.isatty():
        print("💡 提示: 你可以直接运行 `python process_with_ai.py 2026-02-11` 来指定日期")
        try:
            date_input = input("📅 请输入日期 (YYYY-MM-DD) [回车默认今天]: ").strip()
            if date_input:
                target_date = date_input
        except (EOFError, KeyboardInterrupt):
            print("\n")
            sys.exit(0)

    # 3. 默认使用今天
    if not target_date:
        target_date = datetime.datetime.now().strftime("%Y-%m-%d")
        print(f"ℹ️ 未指定日期，默认处理今天: {target_date}")
    
    try:
        processor = AIProcessor(target_date)
        processor.run()
    except KeyboardInterrupt:
        print("\n🛑 用户手动停止程序")
    except Exception as e:
        print(f"\n❌ 程序发生未捕获异常: {e}")
        import traceback
        traceback.print_exc()
