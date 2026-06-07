# -*- coding: utf-8 -*-
import os
import shutil
import sys
import readline
import glob

# 全局常量
RAW_SUFFIX = ('.cr3', '.dng')
EXCLUDE_DIR = "unused_raw_files"
TARGET_FOLDER_ALL = "all_raw_files"
TARGET_FOLDER_MATCHED = "matched_raw_files"

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

# ====================== 功能1：移动无对应JPG的RAW ======================
def move_unmatched_raw_files(target_folder):
    jpg_filenames = set()
    for filename in os.listdir(target_folder):
        if filename.startswith('.'): continue
        if filename.lower().endswith(('.jpg', '.jpeg')):
            name_without_ext = os.path.splitext(filename)[0]
            jpg_filenames.add(name_without_ext.lower())

    dest_folder = os.path.join(target_folder, "unused_raw_files")
    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)

    moved_count = 0
    for filename in os.listdir(target_folder):
        if filename.startswith('.'): continue
        if filename.lower().endswith(RAW_SUFFIX):
            name_without_ext = os.path.splitext(filename)[0]
            if name_without_ext.lower() not in jpg_filenames:
                src = os.path.join(target_folder, filename)
                dst = os.path.join(dest_folder, filename)
                if os.path.exists(dst):
                    name, ext = os.path.splitext(filename)
                    dst = os.path.join(dest_folder, f"{name}_copy{ext}")
                shutil.move(src, dst)
                moved_count += 1
    return moved_count

def process_all_subfolders(root_folder):
    total_moved = 0
    print(f"\n🚀 开始移动无匹配JPG的RAW文件")
    for dirpath, dirnames, filenames in os.walk(root_folder):
        dirnames[:] = [d for d in dirnames if d != EXCLUDE_DIR and not d.startswith('.')]
        if os.path.basename(dirpath).startswith('.'): continue
        print(f"📁 处理: {dirpath}")
        total_moved += move_unmatched_raw_files(dirpath)
    print(f"\n🎉 移动完成，总计：{total_moved} 个")

# ====================== 功能2：复制全部RAW到根目录 ======================
def copy_all_raw_to_root_folder(root_dir):
    target_dir = os.path.join(root_dir, TARGET_FOLDER_ALL)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    copied = set()
    total = 0
    print("\n🚀 开始复制全部RAW文件...")

    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in [EXCLUDE_DIR, TARGET_FOLDER_ALL, TARGET_FOLDER_MATCHED] and not d.startswith('.')]
        current = os.path.basename(dirpath)
        if current in [EXCLUDE_DIR, TARGET_FOLDER_ALL, TARGET_FOLDER_MATCHED]: continue

        print(f"🔍 扫描: {dirpath}")
        for f in filenames:
            if f.lower().endswith(RAW_SUFFIX):
                if f in copied: continue
                copied.add(f)
                src = os.path.join(dirpath, f)
                dst = os.path.join(target_dir, f)
                shutil.copy2(src, dst)
                total += 1
                print(f"   ✅ 复制: {f}")

    print(f"\n🎉 全部复制完成：{total} 个")
    print(f"📂 位置：{target_dir}")

# ====================== 🔥 功能3：你要的新功能 ======================
# 复制【有对应JPG的RAW】到根目录下新建文件夹
def copy_matched_raw_to_root_folder(root_dir):
    target_dir = os.path.join(root_dir, TARGET_FOLDER_MATCHED)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    copied_files = set()
    total = 0

    print("\n🚀 开始复制【有对应JPG的RAW文件】...")

    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in [EXCLUDE_DIR, TARGET_FOLDER_ALL, TARGET_FOLDER_MATCHED] and not d.startswith('.')]
        current = os.path.basename(dirpath)
        if current in [EXCLUDE_DIR, TARGET_FOLDER_ALL, TARGET_FOLDER_MATCHED]: continue

        print(f"🔍 扫描: {dirpath}")

        # 先收集当前目录所有 JPG
        jpg_names = set()
        for f in filenames:
            if f.lower().endswith(('.jpg', '.jpeg')):
                name_no_ext = os.path.splitext(f)[0].lower()
                jpg_names.add(name_no_ext)

        # 复制有对应JPG的RAW
        for f in filenames:
            if f.lower().endswith(RAW_SUFFIX):
                name_no_ext = os.path.splitext(f)[0].lower()
                if name_no_ext in jpg_names:
                    if f in copied_files: continue
                    copied_files.add(f)

                    src = os.path.join(dirpath, f)
                    dst = os.path.join(target_dir, f)
                    shutil.copy2(src, dst)
                    total += 1
                    print(f"   ✅ 复制: {f}")

    print("\n" + "="*60)
    print(f"🎉 【有对应JPG的RAW】复制完成！")
    print(f"📊 总数：{total} 个")
    print(f"📂 保存到：{target_dir}")
    print("="*60)

# ====================== 菜单 ======================
def show_menu():
    print("\n========== RAW 整理工具 ==========")
    print("1 → 移动【无JPG匹配】的RAW到子目录")
    print("2 → 复制【全部RAW】到根目录统一文件夹")
    print("3 → 复制【有JPG匹配】的RAW到根目录统一文件夹")
    print("0 → 退出")
    return input("> ").strip()

def check_exit():
    while True:
        a = input("\n执行完毕，是否退出？(y/n)：").lower()
        return a == 'y'

# ====================== 主程序 ======================
if __name__ == "__main__":
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
    while True:
        opt = show_menu()
        if opt == "0":
            print("👋 退出程序")
            break

        elif opt == "1":
            p = get_folder_path("请输入要处理的根目录")
            if p:
                process_all_subfolders(p)
                if check_exit(): break

        elif opt == "2":
            p = get_folder_path("请输入要扫描的根目录")
            if p:
                copy_all_raw_to_root_folder(p)
                if check_exit(): break

        elif opt == "3":
            p = get_folder_path("请输入要扫描的根目录")
            if p:
                copy_matched_raw_to_root_folder(p)
                if check_exit(): break

        else:
            print("❌ 输入无效")
    input("\n按回车键关闭...")