# -*- coding: utf-8 -*-
import os
import shutil
import sys
import readline
import glob

# 全局常量
RAW_SUFFIX = ('.cr3', '.dng')
EXCLUDE_DIR = "unused_raw_files"
TARGET_FOLDER = "all_raw_files"

def complete_path(text, state):
    text = os.path.expanduser(text)
    matches = glob.glob(text + '*') + [None]
    return matches[state]

readline.set_completer_delims('\t')
readline.parse_and_bind("tab: complete")
readline.set_completer(complete_path)

def get_folder_path(tip):
    print(f"\n{tip}")
    print("可直接拖拽文件夹到终端，输入q退出")
    while True:
        folder_path = input("> ").strip()
        if folder_path.lower() == 'q':
            return None
        folder_path = folder_path.replace('\\', '')
        if os.path.isdir(folder_path):
            return folder_path
        print(f"路径无效，请重新输入！")

def is_folder_empty(folder_path):
    with os.scandir(folder_path) as entries:
        for entry in entries:
            if not entry.name.startswith('.'):
                return False
    return True

def move_unmatched_raw_files(target_folder):
    if is_folder_empty(target_folder):
        print(f"ℹ️  文件夹为空，跳过处理: {target_folder}")
        return 0
    raw_extensions = RAW_SUFFIX
    dest_folder = os.path.join(target_folder, "unused_raw_files")
    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)
        print(f"\n✅ 已创建文件夹: {dest_folder}")
    jpg_filenames = set()
    for filename in os.listdir(target_folder):
        if filename.startswith('.'):
            continue
        if filename.lower().endswith(('.jpg', '.jpeg')):
            name_without_ext = os.path.splitext(filename)[0]
            jpg_filenames.add(name_without_ext.lower())
    print(f"🔍 找到 {len(jpg_filenames)} 个JPG/JPEG文件")
    moved_count = 0
    failed_files = []
    for filename in os.listdir(target_folder):
        if filename.startswith('.'):
            continue
        if filename.lower().endswith(raw_extensions):
            name_without_ext = os.path.splitext(filename)[0]
            if name_without_ext.lower() not in jpg_filenames:
                src_path = os.path.join(target_folder, filename)
                dest_path = os.path.join(dest_folder, filename)
                try:
                    if os.path.exists(dest_path):
                        name, ext = os.path.splitext(filename)
                        dest_path = os.path.join(dest_folder, f"{name}_copy{ext}")
                    shutil.move(src_path, dest_path)
                    print(f"✅ 已移动: {filename}")
                    moved_count += 1
                except Exception as e:
                    failed_files.append((filename, str(e)))
                    print(f"❌ 移动失败 {filename}: {e}")
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
    total_moved = 0
    print(f"\n🚀 开始递归处理所有子文件夹，根目录：{root_folder}")
    print("=" * 80)
    for dirpath, dirnames, filenames in os.walk(root_folder):
        dirnames[:] = [d for d in dirnames if d != EXCLUDE_DIR and not d.startswith('.')]
        if os.path.basename(dirpath).startswith('.'):
            continue
        print(f"\n📁 当前处理文件夹：{dirpath}")
        moved = move_unmatched_raw_files(dirpath)
        total_moved += moved
    print(f"\n🎉 所有文件夹处理完成！")
    print(f"📊 总计移动无匹配JPG的RAW文件：{total_moved} 个")
    return total_moved

# ====================== 带扫描日志 + 绝对不重复版本 ======================
def copy_all_raw_to_root_folder(root_dir):
    target_root_dir = os.path.join(root_dir, TARGET_FOLDER)

    if not os.path.exists(target_root_dir):
        os.makedirs(target_root_dir)
        print(f"📂 已创建统一文件夹：{target_root_dir}")

    total_count = 0
    fail_list = []
    copied_files = set()

    print("\n🚀 开始扫描（日志：正在扫描的文件夹）")
    print("=" * 80)

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # ====================== 关键：排除自己 ======================
        dirnames[:] = [
            d for d in dirnames
            if d != EXCLUDE_DIR
            and d != TARGET_FOLDER
            and not d.startswith('.')
        ]

        current_dir_name = os.path.basename(dirpath)
        if current_dir_name == TARGET_FOLDER or current_dir_name == EXCLUDE_DIR or current_dir_name.startswith('.'):
            continue

        # ====================== 打印正在扫描的文件夹 ======================
        print(f"🔍 扫描文件夹: {dirpath}")

        for filename in filenames:
            if filename.lower().endswith(RAW_SUFFIX):
                if filename in copied_files:
                    continue
                copied_files.add(filename)

                src_path = os.path.join(dirpath, filename)
                dst_path = os.path.join(target_root_dir, filename)

                try:
                    shutil.copy2(src_path, dst_path)
                    print(f"   ✅ 已复制: {filename}")
                    total_count += 1
                except Exception as e:
                    fail_list.append((filename, str(e)))

    print("\n" + "="*60)
    print(f"🎉 全部复制完成！")
    print(f"📊 总计复制 RAW 文件：{total_count} 个")
    print(f"📂 存放位置：{target_root_dir}")
    print("="*60)

def show_menu():
    print("\n======== RAW照片整理工具 ========")
    print("1. 分离无对应JPG的RAW文件")
    print("2. 复制所有RAW到根目录（带扫描日志）")
    print("0. 退出程序")
    return input("> ").strip()

def check_exit():
    while True:
        ans = input("\n执行完毕，是否退出？(y/n)：").strip().lower()
        if ans == 'y':
            return True
        if ans == 'n':
            return False
        print("请输入 y / n")

if __name__ == "__main__":
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
    while True:
        opt = show_menu()
        if opt == "0":
            print("👋 退出")
            break
        elif opt == "1":
            path = get_folder_path("请输入处理根目录")
            if path:
                process_all_subfolders(path)
                if check_exit():
                    break
        elif opt == "2":
            path = get_folder_path("请输入扫描根目录")
            if path:
                copy_all_raw_to_root_folder(path)
                if check_exit():
                    break
        else:
            print("❌ 输入无效")
    input("\n按回车键退出")