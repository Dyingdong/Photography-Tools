#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
macOS 双击运行版：筛选无对应JPG的CR3/DNG文件工具
"""

import os
import shutil
import sys
import readline
import glob

def complete_path(text, state):
    """实现路径Tab补全"""
    text = os.path.expanduser(text)
    matches = glob.glob(text + '*') + [None]
    return matches[state]

readline.set_completer_delims('\t')
readline.parse_and_bind("tab: complete")
readline.set_completer(complete_path)

def get_folder_path():
    """通过终端输入获取文件夹路径"""
    print("\n请输入要处理的文件夹完整路径（可直接拖拽文件夹到终端）：")
    print("示例：/Users/你的用户名/Desktop/照片文件夹")
    print("(输入完成后按回车键，输入q退出)")
    
    while True:
        folder_path = input("> ").strip()
        if folder_path.lower() == 'q':
            return None
        
        folder_path = folder_path.replace('\\', '')
        
        if os.path.isdir(folder_path):
            return folder_path
        else:
            print(f"错误：路径 '{folder_path}' 不存在或不是文件夹，请重新输入！")

def is_folder_empty(folder_path):
    """判断文件夹是否为空"""
    with os.scandir(folder_path) as entries:
        for entry in entries:
            if not entry.name.startswith('.'):
                return False
    return True

def move_unmatched_raw_files(target_folder):
    if is_folder_empty(target_folder):
        print(f"ℹ️  文件夹为空，跳过处理: {target_folder}")
        return 0

    raw_extensions = ('.cr3', '.dng')
    dest_folder = os.path.join(target_folder, "unused_raw_files")
    
    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)
        print(f"\n✅ 已创建文件夹: {dest_folder}")
    else:
        print(f"\nℹ️  文件夹已存在: {dest_folder}")
        
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
        if os.path.basename(dirpath).startswith('.'):
            continue
        
        print(f"\n📁 当前处理文件夹：{dirpath}")
        moved = move_unmatched_raw_files(dirpath)
        total_moved += moved
    
    print(f"\n🎉 所有文件夹处理完成！")
    print(f"📊 总计移动无匹配JPG的RAW文件：{total_moved} 个")

if __name__ == "__main__":
    # 解决macOS双击运行编码问题
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
    sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1)
    
    print("=== 筛选无对应JPG的CR3/DNG文件工具 (递归子文件夹+拖拽修复+空文件夹跳过) ===")
    
    target_folder = get_folder_path()
    
    if not target_folder:
        print("\n🚪 未选择文件夹，程序退出")
    else:
        print(f"\n📂 已选择根文件夹: {target_folder}")
        process_all_subfolders(target_folder)
        
    input("\n\n按回车键退出...")