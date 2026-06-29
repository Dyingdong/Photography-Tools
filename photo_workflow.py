# -*- coding: utf-8 -*-
import os
import shutil
import sys
import glob
import readline
import json
import uuid

# ====================== 常量 ======================
RAW_SUFFIX = ('.cr3', '.dng', '.nef', '.arw')

EXCLUDE_DIR = "unused_raw_files"
TARGET_ALL = "all_raw_files"
TARGET_MATCHED = "matched_raw_files"
TARGET_JPG_FLAT = "jpg_flat_files"
TARGET_JPG_RECURSIVE = "jpg_recursive_files"

LOG_FILE = "action_log.jsonl"


# ====================== 全局状态 ======================
ROOT_DIR = None
CURRENT_TX = None


# ====================== 事务系统 ======================
def begin_tx():
    global CURRENT_TX
    CURRENT_TX = {
        "id": str(uuid.uuid4()),
        "created_dirs": set()
    }


def log_action(t, src, dst):
    record = {
        "tx": CURRENT_TX["id"],
        "type": t,
        "src": src,
        "dst": dst
    }

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_logs():
    if not os.path.exists(LOG_FILE):
        return []

    logs = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                logs.append(json.loads(line.strip()))
            except:
                pass
    return logs


def save_logs(logs):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        for r in logs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ====================== Undo（完整事务回滚） ======================
def safe_move_no_log(src, dst):
    final_dst = dst

    if os.path.exists(dst):
        base, ext = os.path.splitext(dst)
        i = 1
        while os.path.exists(f"{base}_{i}{ext}"):
            i += 1
        final_dst = f"{base}_{i}{ext}"

    shutil.move(src, final_dst)


def undo_last():
    logs = load_logs()

    if not logs:
        print("⚠️ 没有可撤销内容")
        return

    last_tx = logs[-1]["tx"]
    group = [x for x in logs if x["tx"] == last_tx]

    print(f"\n🔄 回滚事务: {last_tx}")

    # 1️⃣ 回滚文件操作
    for item in reversed(group):
        t = item["type"]
        src = item["src"]
        dst = item["dst"]

        if t == "move":
            if os.path.exists(dst):
                safe_move_no_log(dst, src)

        elif t == "copy":
            if os.path.exists(dst):
                os.remove(dst)

    # 2️⃣ 删除本事务日志
    logs = [x for x in logs if x["tx"] != last_tx]
    save_logs(logs)

    # 3️⃣ 删除本次创建的空目录
    if CURRENT_TX and isinstance(CURRENT_TX, dict):
        for d in sorted(CURRENT_TX["created_dirs"], reverse=True):
            try:
                if os.path.exists(d) and len(os.listdir(d)) == 0:
                    os.rmdir(d)
            except:
                pass

    print("✅ 已完全撤销（文件 + 文件夹）")


# ====================== 工具函数 ======================
def norm(name):
    return os.path.splitext(name)[0].lower().replace(" ", "").replace("(", "").replace(")", "")


def safe_mkdir(p):
    os.makedirs(p, exist_ok=True)

    # ⭐ 记录创建目录（关键）
    if CURRENT_TX is not None:
        CURRENT_TX["created_dirs"].add(p)


def safe_move(src, dst):
    final_dst = dst

    if os.path.exists(dst):
        base, ext = os.path.splitext(dst)
        i = 1
        while os.path.exists(f"{base}_{i}{ext}"):
            i += 1
        final_dst = f"{base}_{i}{ext}"

    shutil.move(src, final_dst)
    log_action("move", src, final_dst)
    return final_dst


def safe_copy(src, dst):
    final_dst = dst

    if os.path.exists(dst):
        base, ext = os.path.splitext(dst)
        i = 1
        while os.path.exists(f"{base}_{i}{ext}"):
            i += 1
        final_dst = f"{base}_{i}{ext}"

    shutil.copy2(src, final_dst)
    log_action("copy", src, final_dst)
    return final_dst


def iter_dirs(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in {
                EXCLUDE_DIR,
                TARGET_ALL,
                TARGET_MATCHED,
                TARGET_JPG_FLAT,
                TARGET_JPG_RECURSIVE
            } and not d.startswith('.')
        ]
        if os.path.basename(dirpath).startswith('.'):
            continue
        yield dirpath, filenames


# ====================== 初始化目录 ======================
def set_root():
    global ROOT_DIR

    print("\n📁 输入目录")
    print("拖拽文件夹或输入路径，q退出")

    while True:
        p = input("> ").strip()
        if p.lower() == "q":
            return False

        p = p.replace("\\", "").strip()

        if os.path.isdir(p):
            ROOT_DIR = p
            print(f"✅ 当前目录: {ROOT_DIR}")
            return True

        print("❌ 路径无效")


# ====================== 功能1 ======================
def move_unmatched_raw():
    begin_tx()

    print("\n🚀 移动无JPG RAW")

    total = 0

    for dirpath, filenames in iter_dirs(ROOT_DIR):
        jpg_set = {
            norm(f)
            for f in filenames
            if f.lower().endswith((".jpg", ".jpeg"))
        }

        dest = os.path.join(dirpath, EXCLUDE_DIR)
        safe_mkdir(dest)

        for f in filenames:
            if f.lower().endswith(RAW_SUFFIX):
                if norm(f) not in jpg_set:
                    safe_move(
                        os.path.join(dirpath, f),
                        os.path.join(dest, f)
                    )
                    total += 1

    print(f"✅ 完成: {total}")
    print("🔁 可输入 u 撤销（事务级）")


# ====================== 功能2 ======================
def copy_all_raw():
    begin_tx()

    print("\n🚀 复制全部RAW")

    target = os.path.join(ROOT_DIR, TARGET_ALL)
    safe_mkdir(target)

    seen = set()
    total = 0

    for dirpath, filenames in iter_dirs(ROOT_DIR):
        for f in filenames:
            if f.lower().endswith(RAW_SUFFIX):
                src = os.path.join(dirpath, f)

                if src in seen:
                    continue
                seen.add(src)

                safe_copy(src, os.path.join(target, f))
                total += 1

    print(f"✅ 完成: {total}")


# ====================== 功能3 ======================
def move_jpg_current():
    begin_tx()

    print("\n🚀 移动当前JPG")

    target = os.path.join(ROOT_DIR, TARGET_JPG_FLAT)
    safe_mkdir(target)

    total = 0

    for f in os.listdir(ROOT_DIR):
        src = os.path.join(ROOT_DIR, f)

        if os.path.isfile(src) and f.lower().endswith((".jpg", ".jpeg")):
            safe_move(src, os.path.join(target, f))
            total += 1

    print(f"✅ 完成: {total}")
    print("🔁 可输入 u 撤销（事务级）")


# ====================== 功能4 ======================
def move_jpg_recursive():
    begin_tx()

    print("\n🚀 移动递归JPG")

    target = os.path.join(ROOT_DIR, TARGET_JPG_RECURSIVE)
    safe_mkdir(target)

    seen = set()
    total = 0

    for dirpath, filenames in iter_dirs(ROOT_DIR):
        for f in filenames:
            if f.lower().endswith((".jpg", ".jpeg")):
                src = os.path.join(dirpath, f)

                if src in seen:
                    continue
                seen.add(src)

                safe_move(src, os.path.join(target, f))
                total += 1

    print(f"✅ 完成: {total}")
    print("🔁 可输入 u 撤销（事务级）")


# ====================== 菜单 ======================
def menu():
    print("\n========== RAW工具 ==========")
    print(f"📁 当前: {ROOT_DIR}")
    print("--------------------------------")
    print("1 → 移动无JPG RAW")
    print("2 → 复制全部RAW")
    print("3 → 移动当前JPG")
    print("4 → 移动递归JPG")
    print("u → 撤销（整个事务）")
    print("0 → 退出")
    return input("> ").strip()


# ====================== 主程序 ======================
def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if not set_root():
        return

    while True:
        opt = menu()

        if opt == "0":
            break

        elif opt == "u":
            undo_last()

        elif opt == "1":
            move_unmatched_raw()

        elif opt == "2":
            copy_all_raw()

        elif opt == "3":
            move_jpg_current()

        elif opt == "4":
            move_jpg_recursive()

        else:
            print("❌ 输入错误")

    input("\n回车退出...")


if __name__ == "__main__":
    main()