import os
import re
import datetime
import sys

# ================= 配置区域 (Configuration) =================
CONFIG = {
    # 路径配置 (默认为当前目录)
    "LOG_DIR": ".",  
    "OUTPUT_DIR": ".",
    
    # 逻辑参数
    "MERGE_THRESHOLD": 5.0,   # (秒) 两个片段间隔超过此值视为新的一句话
}
# ===========================================================

class LogMerger:
    def __init__(self, target_date=None):
        # 如果未指定日期，默认处理今天
        self.target_date = target_date or datetime.datetime.now().strftime("%Y-%m-%d")
        
        # 构造文件路径
        self.log_path = os.path.join(CONFIG["LOG_DIR"], f"{self.target_date}.txt")
        # 输出合并后的句子文件
        self.output_path = os.path.join(CONFIG["OUTPUT_DIR"], f"merged_{self.target_date}.txt")

    def parse_timestamp(self, time_str):
        """解析时间戳字符串 HH:MM:SS 为 datetime 对象"""
        try:
            return datetime.datetime.strptime(f"{self.target_date} {time_str}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    def merge_logs(self):
        """
        读取并缝合日志：
        1. 过滤无效字符
        2. 根据时间间隔合并断句
        3. 返回格式化的字符串列表: ["[HH:MM:SS] 内容...", ...]
        """
        if not os.path.exists(self.log_path):
            print(f"❌ 文件不存在: {self.log_path}")
            return []

        print(f"📂 读取日志: {self.log_path}")
        try:
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                raw_lines = f.readlines()
        except Exception as e:
            print(f"❌ 读取文件失败: {e}")
            return []

        stitched_logs = []
        buffer_text = []
        buffer_start_time = None
        last_dt = None
        
        # 匹配标准 [HH:MM:SS] 格式
        pattern = re.compile(r'\[(\d{2}:\d{2}:\d{2})\]\s*(.*)')
        
        # 过滤词列表 (严格过滤完全匹配的行，或仅包含这些字符的行)
        IGNORE_CHARS = {"/", ",", "，", "。", ".", "、", "[", "]", "【", "】", "sil", "VOICE", ":", "：", "(", ")", "（", "）", "#", "sil"}

        for line in raw_lines:
            match = pattern.match(line.strip())
            if not match:
                continue

            time_str, content = match.groups()
            content = content.strip()

            # 预处理内容：移除 [VOICE] 标记
            content = content.replace("[VOICE]", "").strip()
            
            # 基础清洗：跳过空行和纯符号行
            # 如果 content 仅包含 IGNORE_CHARS 中的字符，也视为无效
            if not content or content in IGNORE_CHARS:
                continue
            
            # 尝试解析时间
            current_dt = self.parse_timestamp(time_str)
            if not current_dt:
                continue

            # 合并逻辑：
            # 1. 如果有上一条记录
            # 2. 且 (当前时间 - 上一条时间) > 阈值
            # -> 视为新的一句话，保存缓冲区中的旧话，开始新话
            if last_dt and (current_dt - last_dt).total_seconds() > CONFIG["MERGE_THRESHOLD"]:
                if buffer_text:
                    # 将缓冲区内容合并
                    full_sentence = "".join(buffer_text).replace("  ", " ")
                    stitched_logs.append(f"[{buffer_start_time}] {full_sentence}")
                
                # 重置缓冲区，开始新的一句
                buffer_text = [content]
                buffer_start_time = time_str
            else:
                # 间隔很短，合并到当前句
                if not buffer_text:
                    buffer_start_time = time_str
                buffer_text.append(content)
            
            last_dt = current_dt

        # 循环结束后，保存缓冲区中最后一条
        if buffer_text:
            full_sentence = "".join(buffer_text).replace("  ", " ")
            stitched_logs.append(f"[{buffer_start_time}] {full_sentence}")

        print(f"✅ 预处理完成: {len(raw_lines)} 行 -> {len(stitched_logs)} 条合并记录")
        return stitched_logs

    def save_merged_logs(self, merged_logs):
        """保存合并后的日志到文件"""
        if not merged_logs:
            print("⚠️ 无数据可保存")
            return
        
        try:
            os.makedirs(os.path.dirname(self.output_path) if os.path.dirname(self.output_path) else ".", exist_ok=True)
            with open(self.output_path, 'w', encoding='utf-8') as f:
                for log in merged_logs:
                    f.write(log + "\n")
            print(f"💾 合并后的日志已保存到: {self.output_path}")
            print(f"📝 共保存 {len(merged_logs)} 条句子")
            print(f"\n💡 提示: 你现在可以手动编辑 {self.output_path} 进行脱敏处理")
            print(f"   完成后，运行 topic_router.py 进行话题嗅探")
        except Exception as e:
            print(f"❌ 保存文件失败: {e}")

    def run(self):
        print(f"=== 开始合并 {self.target_date} 的日志 ===")
        merged_logs = self.merge_logs()
        if merged_logs:
            self.save_merged_logs(merged_logs)
        else:
            print("⚠️ 无数据可处理")

if __name__ == "__main__":
    # 处理命令行参数或用户输入
    target_date = None
    
    # 1. 尝试从命令行参数获取
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
    
    # 2. 如果没有参数且在交互式终端，询问用户
    if not target_date and sys.stdin.isatty():
        print("💡 提示: 你可以直接运行 `python merge_logs.py 2026-02-11` 来指定日期")
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
        merger = LogMerger(target_date)
        merger.run()
    except KeyboardInterrupt:
        print("\n🛑 用户手动停止程序")
    except Exception as e:
        print(f"\n❌ 程序发生未捕获异常: {e}")
        import traceback
        traceback.print_exc()
