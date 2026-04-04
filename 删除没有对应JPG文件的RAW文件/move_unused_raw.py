import os
import shutil
import sys
import readline
import glob

def complete_path(text, state):
    """实现路径Tab补全"""
    # 处理用户输入的波浪号（~）替换为用户目录
    text = os.path.expanduser(text)
    # 查找匹配的路径
    matches = glob.glob(text + '*') + [None]
    return matches[state]

# 启用Tab补全
readline.set_completer_delims('\t')
readline.parse_and_bind("tab: complete")
readline.set_completer(complete_path)

def get_folder_path():
    """通过终端输入获取文件夹路径，兼容所有系统，修复拖拽反斜杠问题"""
    print("\n请输入要处理的文件夹完整路径（可直接拖拽文件夹到终端）：")
    print("示例：/Users/你的用户名/Desktop/照片文件夹")
    print("(输入完成后按回车键，输入q退出)")
    
    while True:
        folder_path = input("> ").strip()
        # 退出逻辑
        if folder_path.lower() == 'q':
            return None
        
        # ============== 核心修复：移除拖拽带来的反斜杠转义字符 ==============
        folder_path = folder_path.replace('\\', '')
        
        # 验证路径是否存在且是文件夹
        if os.path.isdir(folder_path):
            return folder_path
        else:
            print(f"错误：路径 '{folder_path}' 不存在或不是文件夹，请重新输入！")

def move_unmatched_raw_files(target_folder):
    """
    移动没有对应JPG文件的CR3/DNG文件到新建文件夹
    :param target_folder: 目标文件夹路径
    """
    # 定义要处理的RAW文件格式
    raw_extensions = ('.cr3', '.dng')
    # 新建文件夹名称
    dest_folder = os.path.join(target_folder, "unused_raw_files")
    
    # 1. 自动创建目标文件夹（如果不存在）
    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)
        print(f"\n✅ 已创建文件夹: {dest_folder}")
    else:
        print(f"\nℹ️  文件夹已存在: {dest_folder}")
        
    # 2. 收集所有JPG文件的名称（去除后缀，不区分大小写）
    jpg_filenames = set()
    for filename in os.listdir(target_folder):
        # 过滤隐藏文件（以.开头的文件）
        if filename.startswith('.'):
            continue
        # 过滤出JPG/JPEG文件（不区分大小写）
        if filename.lower().endswith(('.jpg', '.jpeg')):
            # 提取文件名（不含后缀）
            name_without_ext = os.path.splitext(filename)[0]
            jpg_filenames.add(name_without_ext.lower())  # 统一小写，避免大小写问题
            
    print(f"🔍 找到 {len(jpg_filenames)} 个JPG/JPEG文件")
    
    # 3. 筛选并移动无对应JPG的CR3/DNG文件
    moved_count = 0
    failed_files = []
    for filename in os.listdir(target_folder):
        # 过滤隐藏文件（以.开头的文件）
        if filename.startswith('.'):
            continue
        # 只处理CR3/DNG文件（不区分大小写）
        if filename.lower().endswith(raw_extensions):
            # 提取文件名（不含后缀）
            name_without_ext = os.path.splitext(filename)[0]
            # 检查是否有对应JPG文件
            if name_without_ext.lower() not in jpg_filenames:
                # 构造源文件和目标文件路径
                src_path = os.path.join(target_folder, filename)
                dest_path = os.path.join(dest_folder, filename)
                
                # 移动文件（避免覆盖同名文件）
                try:
                    # 先检查目标文件是否已存在，避免覆盖
                    if os.path.exists(dest_path):
                        # 重命名目标文件（加后缀）
                        name, ext = os.path.splitext(filename)
                        dest_path = os.path.join(dest_folder, f"{name}_copy{ext}")
                        
                    shutil.move(src_path, dest_path)
                    print(f"✅ 已移动: {filename}")
                    moved_count += 1
                except Exception as e:
                    failed_files.append((filename, str(e)))
                    print(f"❌ 移动失败 {filename}: {e}")
                    
    # 输出最终结果
    print(f"\n==================== 当前文件夹操作完成 ====================")
    print(f"✅ 成功移动 {moved_count} 个文件到 {dest_folder}")
    if failed_files:
        print(f"❌ 移动失败 {len(failed_files)} 个文件：")
        for fn, err in failed_files:
            print(f"   - {fn}: {err}")
    else:
        print(f"ℹ️  无文件移动失败")
    print("=" * 60)
    
    return moved_count

def process_all_subfolders(root_folder):
    """
    递归遍历根目录 + 所有子文件夹，批量执行文件筛选移动操作
    :param root_folder: 根文件夹路径
    """
    total_moved = 0
    print(f"\n🚀 开始递归处理所有子文件夹，根目录：{root_folder}")
    print("=" * 80)
    
    # os.walk 递归遍历所有子文件夹
    for dirpath, dirnames, filenames in os.walk(root_folder):
        # 跳过隐藏文件夹（macOS/Windows 系统隐藏目录）
        if os.path.basename(dirpath).startswith('.'):
            continue
        
        print(f"\n📁 当前处理文件夹：{dirpath}")
        # 对当前文件夹执行核心处理逻辑
        moved = move_unmatched_raw_files(dirpath)
        total_moved += moved
    
    # 最终汇总统计
    print(f"\n🎉 所有文件夹处理完成！")
    print(f"📊 总计移动无匹配JPG的RAW文件：{total_moved} 个")

if __name__ == "__main__":
    print("=== 筛选无对应JPG的CR3/DNG文件工具 (递归子文件夹+拖拽修复版) ===")
    
    # 获取文件夹路径（兼容旧版macOS，修复拖拽反斜杠）
    target_folder = get_folder_path()
    
    if not target_folder:
        print("\n🚪 未选择文件夹，程序退出")
    else:
        print(f"\n📂 已选择根文件夹: {target_folder}")
        # 执行递归处理所有子文件夹
        process_all_subfolders(target_folder)
        
    # 暂停查看结果
    input("\n\n按回车键退出...")