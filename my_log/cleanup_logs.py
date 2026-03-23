import os
import datetime

def get_target_date():
    """获取目标日期，默认今天，可手动输入"""
    today = datetime.date.today().strftime('%Y-%m-%d')
    user_input = input(f"请输入日期 (YYYY-MM-DD) [回车默认今天 ({today})]: ")
    
    if not user_input:
        return today
    
    # 验证日期格式
    try:
        # 尝试解析输入的日期
        datetime.datetime.strptime(user_input, '%Y-%m-%d')
        return user_input
    except ValueError:
        print("日期格式错误，请使用 YYYY-MM-DD 格式")
        return get_target_date()

def cleanup_files(target_date):
    """删除指定日期的处理后文件"""
    files_to_delete = [
        f"{target_date}.txt",
        f"merged_{target_date}.txt",
        f"topics_{target_date}.json",
        f"summary_{target_date}.txt"
    ]
    
    # 构建完整的文件路径
    file_paths = [os.path.join("d:\\my_log", file) for file in files_to_delete]
    
    # 显示要删除的文件
    print(f"\n准备删除以下文件 ({target_date}):")
    for file_path in file_paths:
        print(f"- {file_path}")
    
    # 确认删除
    confirm = input("\n确认删除？ (y/N): ")
    if confirm.lower() != 'y':
        print("删除操作已取消")
        return
    
    # 执行删除
    deleted_count = 0
    for file_path in file_paths:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"已删除: {file_path}")
                deleted_count += 1
            except Exception as e:
                print(f"删除失败 {file_path}: {e}")
        else:
            print(f"文件不存在: {file_path}")
    
    print(f"\n删除完成，共删除 {deleted_count} 个文件")

def main():
    """主函数"""
    print("💡 提示: 你可以直接运行 `python cleanup_processed_logs.py 2026-02-11` 来指定日期")
    target_date = get_target_date()
    cleanup_files(target_date)

if __name__ == "__main__":
    main()
