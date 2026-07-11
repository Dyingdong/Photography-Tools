# -*- coding: utf-8 -*-
"""照片 RAW/JPG 整理工具。

所有移动、复制操作都会写入事务日志，可通过菜单中的 u 撤销最近一次操作。
"""

import json
import os
import shlex
import shutil
import sys
import uuid

# ====================== 文件类型 ======================
JPG_SUFFIX = (".jpg", ".jpeg")
RAW_SUFFIX = (
    ".cr2", ".cr3",             # Canon
    ".nef", ".nrw",             # Nikon
    ".arw", ".srf", ".sr2",     # Sony
    ".raf",                       # Fujifilm
    ".orf",                       # Olympus / OM System
    ".rw2",                       # Panasonic
    ".pef",                       # Pentax
    ".srw",                       # Samsung
    ".dng", ".raw",              # 通用格式
)

# ====================== 自动创建的中文目录 ======================
EXCLUDE_DIR = "无同名JPG的RAW"
TARGET_ALL = "全部RAW"
TARGET_MATCHED_CURRENT = "当前目录同名JPG的RAW"
TARGET_MATCHED_RECURSIVE = "所有目录同名JPG的RAW"
TARGET_JPG_CURRENT = "当前目录JPG"
TARGET_JPG_RECURSIVE = "所有目录JPG"

GENERATED_DIRS = {
    EXCLUDE_DIR,
    TARGET_ALL,
    TARGET_MATCHED_CURRENT,
    TARGET_MATCHED_RECURSIVE,
    TARGET_JPG_CURRENT,
    TARGET_JPG_RECURSIVE,
}

LOG_FILE_NAME = "操作日志.jsonl"

# ====================== 全局状态 ======================
ROOT_DIR = None
CURRENT_TX = None


# ====================== 路径与日志 ======================
def get_log_file():
    """日志保存在当前处理目录中，避免不同目录的操作互相干扰。"""
    if ROOT_DIR:
        return os.path.join(ROOT_DIR, LOG_FILE_NAME)
    return LOG_FILE_NAME


def begin_tx():
    global CURRENT_TX
    CURRENT_TX = {"id": str(uuid.uuid4())}


def log_action(action_type, src="", dst=""):
    if CURRENT_TX is None:
        raise RuntimeError("尚未开始事务")

    record = {
        "tx": CURRENT_TX["id"],
        "type": action_type,
        "src": src,
        "dst": dst,
    }

    with open(get_log_file(), "a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_logs():
    log_file = get_log_file()
    if not os.path.exists(log_file):
        return []

    logs = []
    with open(log_file, "r", encoding="utf-8") as file:
        for line in file:
            try:
                logs.append(json.loads(line.strip()))
            except (json.JSONDecodeError, TypeError):
                # 忽略异常或不完整日志行，避免程序无法启动。
                continue
    return logs


def save_logs(logs):
    log_file = get_log_file()

    if not logs:
        try:
            os.remove(log_file)
        except FileNotFoundError:
            pass
        return

    with open(log_file, "w", encoding="utf-8") as file:
        for record in logs:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


# ====================== 文件操作与撤销 ======================
def unique_path(path):
    """目标重名时自动追加 _1、_2，保证不覆盖已有文件。"""
    if not os.path.exists(path):
        return path

    base, ext = os.path.splitext(path)
    index = 1
    while os.path.exists(f"{base}_{index}{ext}"):
        index += 1
    return f"{base}_{index}{ext}"


def safe_mkdir(path):
    """仅记录本事务真正新建的目录。"""
    if os.path.isdir(path):
        return False

    os.makedirs(path, exist_ok=True)
    log_action("mkdir", dst=path)
    return True


def safe_move(src, dst):
    final_dst = unique_path(dst)
    shutil.move(src, final_dst)
    log_action("move", src=src, dst=final_dst)
    return final_dst


def safe_copy(src, dst):
    final_dst = unique_path(dst)
    shutil.copy2(src, final_dst)
    log_action("copy", src=src, dst=final_dst)
    return final_dst


def restore_move(src, dst):
    """撤销移动；原位置已有同名文件时不覆盖，自动改名恢复。"""
    final_dst = unique_path(dst)
    os.makedirs(os.path.dirname(final_dst), exist_ok=True)
    shutil.move(src, final_dst)
    return final_dst


def undo_last():
    global CURRENT_TX

    logs = load_logs()
    if not logs:
        print("⚠️ 没有可撤销内容")
        return

    last_tx = logs[-1].get("tx")
    group = [record for record in logs if record.get("tx") == last_tx]

    print(f"\n🔄 正在撤销最近一次操作: {last_tx}")
    restored_with_rename = 0

    # 逆序回滚：先还原文件，再删除本事务创建的空目录。
    for item in reversed(group):
        action_type = item.get("type")
        src = item.get("src", "")
        dst = item.get("dst", "")

        try:
            if action_type == "move" and os.path.exists(dst):
                restored = restore_move(dst, src)
                if restored != src:
                    restored_with_rename += 1

            elif action_type == "copy" and os.path.isfile(dst):
                os.remove(dst)

            elif action_type == "mkdir" and os.path.isdir(dst):
                if not os.listdir(dst):
                    os.rmdir(dst)
        except OSError as error:
            print(f"⚠️ 撤销失败: {dst or src}\n   {error}")

    save_logs([record for record in logs if record.get("tx") != last_tx])
    CURRENT_TX = None

    print("✅ 已撤销最近一次操作")
    if restored_with_rename:
        print(f"⚠️ 有 {restored_with_rename} 个原位置存在同名文件，恢复时已自动改名")


# ====================== 匹配与遍历工具 ======================
def stem_key(filename):
    """按不区分大小写的主文件名匹配 JPG 与 RAW。"""
    return os.path.splitext(filename)[0].strip().casefold()


def is_jpg(filename):
    return filename.lower().endswith(JPG_SUFFIX)


def is_raw(filename):
    return filename.lower().endswith(RAW_SUFFIX)


def matched_raw_names(filenames):
    """返回与同一文件列表中 JPG 主文件名一致的 RAW 文件名。"""
    jpg_stems = {stem_key(name) for name in filenames if is_jpg(name)}
    return [name for name in filenames if is_raw(name) and stem_key(name) in jpg_stems]


def iter_dirs(root):
    """递归遍历，同时跳过隐藏目录和本工具生成的目录。"""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in GENERATED_DIRS and not dirname.startswith(".")
        ]

        if os.path.basename(dirpath).startswith("."):
            continue

        yield dirpath, filenames


def move_files_to_flat_target(files, target):
    """把文件移动到同一目标目录，重名时自动编号。"""
    safe_mkdir(target)
    total = 0

    for src in files:
        if not os.path.isfile(src):
            continue
        safe_move(src, os.path.join(target, os.path.basename(src)))
        total += 1

    return total


# ====================== 初始化目录 ======================
def clean_input_path(value):
    """兼容引号路径和 macOS/Linux 终端拖拽产生的反斜杠转义。"""
    value = os.path.expanduser(value.strip().strip('"').strip("'"))
    if os.path.isdir(value):
        return os.path.abspath(value)

    if os.name != "nt":
        try:
            parts = shlex.split(value)
            if len(parts) == 1 and os.path.isdir(parts[0]):
                return os.path.abspath(parts[0])
        except ValueError:
            pass

    return value


def set_root():
    global ROOT_DIR

    print("\n📁 输入目录")
    print("拖拽文件夹或输入路径，q 退出")

    while True:
        path = input("> ").strip()
        if path.lower() == "q":
            return False

        path = clean_input_path(path)
        if os.path.isdir(path):
            ROOT_DIR = path
            print(f"✅ 当前目录: {ROOT_DIR}")
            return True

        print("❌ 路径无效")


# ====================== 功能1：递归移动无匹配 RAW ======================
def move_unmatched_raw():
    begin_tx()
    print("\n🚀 移动没有同名 JPG 的 RAW（逐目录整理）")

    total = 0
    for dirpath, filenames in iter_dirs(ROOT_DIR):
        jpg_stems = {stem_key(name) for name in filenames if is_jpg(name)}
        unmatched = [
            name
            for name in filenames
            if is_raw(name) and stem_key(name) not in jpg_stems
        ]

        if not unmatched:
            continue

        target = os.path.join(dirpath, EXCLUDE_DIR)
        safe_mkdir(target)

        for name in unmatched:
            safe_move(
                os.path.join(dirpath, name),
                os.path.join(target, name),
            )
            total += 1

    print(f"✅ 完成，共移动 {total} 个 RAW 文件")
    print("🔁 可输入 u 撤销最近一次操作")


# ====================== 功能2：复制全部 RAW ======================
def copy_all_raw():
    begin_tx()
    print("\n🚀 复制当前目录及所有子目录中的 RAW")

    sources = []
    for dirpath, filenames in iter_dirs(ROOT_DIR):
        sources.extend(
            os.path.join(dirpath, name)
            for name in filenames
            if is_raw(name)
        )

    target = os.path.join(ROOT_DIR, TARGET_ALL)
    safe_mkdir(target)

    total = 0
    for src in sources:
        safe_copy(src, os.path.join(target, os.path.basename(src)))
        total += 1

    print(f"✅ 完成，共复制 {total} 个 RAW 文件")
    print("🔁 可输入 u 撤销最近一次操作")


# ====================== 功能3：移动当前目录 JPG ======================
def move_jpg_current():
    begin_tx()
    print("\n🚀 移动当前目录中的 JPG")

    sources = [
        os.path.join(ROOT_DIR, name)
        for name in os.listdir(ROOT_DIR)
        if os.path.isfile(os.path.join(ROOT_DIR, name)) and is_jpg(name)
    ]

    total = move_files_to_flat_target(
        sources,
        os.path.join(ROOT_DIR, TARGET_JPG_CURRENT),
    )

    print(f"✅ 完成，共移动 {total} 个 JPG 文件")
    print("🔁 可输入 u 撤销最近一次操作")


# ====================== 功能4：递归移动 JPG ======================
def move_jpg_recursive():
    begin_tx()
    print("\n🚀 移动当前目录及所有子目录中的 JPG")

    sources = []
    for dirpath, filenames in iter_dirs(ROOT_DIR):
        sources.extend(
            os.path.join(dirpath, name)
            for name in filenames
            if is_jpg(name)
        )

    total = move_files_to_flat_target(
        sources,
        os.path.join(ROOT_DIR, TARGET_JPG_RECURSIVE),
    )

    print(f"✅ 完成，共移动 {total} 个 JPG 文件")
    print("🔁 可输入 u 撤销最近一次操作")


# ====================== 功能5：当前目录匹配 RAW ======================
def move_matched_raw_current():
    """仅处理根目录：移动有同名 JPG 的 RAW。"""
    begin_tx()
    print("\n🚀 移动当前目录中有同名 JPG 的 RAW")

    filenames = [
        name
        for name in os.listdir(ROOT_DIR)
        if os.path.isfile(os.path.join(ROOT_DIR, name))
    ]
    sources = [
        os.path.join(ROOT_DIR, name)
        for name in matched_raw_names(filenames)
    ]

    total = move_files_to_flat_target(
        sources,
        os.path.join(ROOT_DIR, TARGET_MATCHED_CURRENT),
    )

    print(f"✅ 完成，共移动 {total} 个匹配的 RAW 文件")
    print("🔁 可输入 u 撤销最近一次操作")


# ====================== 功能6：递归匹配 RAW ======================
def move_matched_raw_recursive():
    """遍历根目录及子目录，移动各目录中有同名 JPG 的 RAW。"""
    begin_tx()
    print("\n🚀 移动当前目录及所有子目录中有同名 JPG 的 RAW")

    sources = []
    for dirpath, filenames in iter_dirs(ROOT_DIR):
        sources.extend(
            os.path.join(dirpath, name)
            for name in matched_raw_names(filenames)
        )

    total = move_files_to_flat_target(
        sources,
        os.path.join(ROOT_DIR, TARGET_MATCHED_RECURSIVE),
    )

    print(f"✅ 完成，共移动 {total} 个匹配的 RAW 文件")
    print("🔁 可输入 u 撤销最近一次操作")


# ====================== 菜单 ======================
def menu():
    print("\n================ RAW / JPG 工具 ================")
    print(f"📁 当前目录: {ROOT_DIR}")
    print("------------------------------------------------")
    print("1 → 递归移动没有同名 JPG 的 RAW（放入各自子目录）")
    print("2 → 递归复制全部 RAW 到根目录的新目录")
    print("3 → 移动当前目录中的 JPG")
    print("4 → 递归移动所有 JPG 到根目录的新目录")
    print("5 → 移动当前目录中有同名 JPG 的 RAW")
    print("6 → 递归移动有同名 JPG 的 RAW 到根目录的新目录")
    print("u → 撤销最近一次操作")
    print("0 → 退出")
    return input("> ").strip().lower()


# ====================== 主程序 ======================
def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if not set_root():
        return

    actions = {
        "1": move_unmatched_raw,
        "2": copy_all_raw,
        "3": move_jpg_current,
        "4": move_jpg_recursive,
        "5": move_matched_raw_current,
        "6": move_matched_raw_recursive,
        "u": undo_last,
    }

    while True:
        option = menu()
        if option == "0":
            break

        action = actions.get(option)
        if action is None:
            print("❌ 输入错误")
            continue

        try:
            action()
        except (OSError, shutil.Error) as error:
            print(f"❌ 操作失败: {error}")

    input("\n回车退出...")


if __name__ == "__main__":
    main()
