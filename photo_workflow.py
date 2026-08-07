# -*- coding: utf-8 -*-
"""
照片 CR3 / JPG 整理工具

功能：
1. CR3整理
2. JPG整理
3. 操作日志
4. 支持撤销最近一次操作

所有文件移动操作均记录日志。
"""

import json
import os
import shlex
import shutil
import sys
import uuid


# ====================== 文件类型 ======================

# 只处理 Canon CR3
CR3_SUFFIX = (
    ".cr3",
)

# JPG
JPG_SUFFIX = (
    ".jpg",
    ".jpeg",
)


# ====================== 自动创建目录 ======================

# CR3目录
NO_MATCH_CR3_DIR = "无匹配JPG的CR3文件"
ALL_CR3_DIR = "全部CR3文件"
MATCHED_CURRENT_CR3_DIR = "有匹配JPG的CR3文件"
MATCHED_ALL_CR3_DIR = "所有匹配JPG的CR3文件"


# JPG目录
CURRENT_JPG_DIR = "当前文件夹JPG照片"
ALL_JPG_DIR = "所有文件夹JPG照片"


# 程序自动生成目录
GENERATED_DIRS = {
    NO_MATCH_CR3_DIR,
    ALL_CR3_DIR,
    MATCHED_CURRENT_CR3_DIR,
    MATCHED_ALL_CR3_DIR,
    CURRENT_JPG_DIR,
    ALL_JPG_DIR,
}


LOG_FILE_NAME = "操作日志.jsonl"


# ====================== 全局状态 ======================

ROOT_DIR = None
CURRENT_TX = None


# ====================== 日志 ======================

def get_log_file():
    if ROOT_DIR:
        return os.path.join(ROOT_DIR, LOG_FILE_NAME)

    return LOG_FILE_NAME



def begin_tx():
    global CURRENT_TX

    CURRENT_TX = {
        "id": str(uuid.uuid4())
    }



def log_action(action_type, src="", dst=""):

    if CURRENT_TX is None:
        raise RuntimeError("尚未开始事务")


    record = {
        "tx": CURRENT_TX["id"],
        "type": action_type,
        "src": src,
        "dst": dst,
    }


    with open(
        get_log_file(),
        "a",
        encoding="utf-8"
    ) as file:

        file.write(
            json.dumps(
                record,
                ensure_ascii=False
            )
            + "\n"
        )



def load_logs():

    log_file = get_log_file()

    if not os.path.exists(log_file):
        return []


    logs = []

    with open(
        log_file,
        "r",
        encoding="utf-8"
    ) as file:

        for line in file:

            try:
                logs.append(
                    json.loads(
                        line.strip()
                    )
                )

            except:
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



    with open(
        log_file,
        "w",
        encoding="utf-8"
    ) as file:

        for record in logs:

            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False
                )
                + "\n"
            )
			
# ====================== 文件操作 ======================


def unique_path(path):
    """
    目标存在同名文件时自动编号
    """

    if not os.path.exists(path):
        return path


    base, ext = os.path.splitext(path)

    index = 1

    while os.path.exists(
        f"{base}_{index}{ext}"
    ):
        index += 1


    return f"{base}_{index}{ext}"



def safe_mkdir(path):
    """
    创建目录并记录
    """

    if os.path.isdir(path):
        return False


    os.makedirs(
        path,
        exist_ok=True
    )

    log_action(
        "mkdir",
        dst=path
    )

    return True



def safe_move(src, dst):

    final_dst = unique_path(dst)

    shutil.move(
        src,
        final_dst
    )

    log_action(
        "move",
        src=src,
        dst=final_dst
    )

    return final_dst



def safe_copy(src, dst):

    final_dst = unique_path(dst)

    shutil.copy2(
        src,
        final_dst
    )

    log_action(
        "copy",
        src=src,
        dst=final_dst
    )

    return final_dst



def restore_move(src, dst):

    """
    撤销移动
    """

    final_dst = unique_path(dst)


    os.makedirs(
        os.path.dirname(final_dst),
        exist_ok=True
    )


    shutil.move(
        src,
        final_dst
    )


    return final_dst



def undo_last():

    global CURRENT_TX


    logs = load_logs()


    if not logs:

        print(
            "⚠️ 没有可撤销内容"
        )

        return



    last_tx = logs[-1].get("tx")


    group = [
        item
        for item in logs
        if item.get("tx") == last_tx
    ]


    print(
        f"\n🔄 正在撤销操作: {last_tx}"
    )


    rename_count = 0



    # 逆序恢复
    for item in reversed(group):

        action_type = item.get("type")

        src = item.get("src", "")

        dst = item.get("dst", "")



        try:


            if (
                action_type == "move"
                and os.path.exists(dst)
            ):

                restored = restore_move(
                    dst,
                    src
                )


                if restored != src:
                    rename_count += 1



            elif (
                action_type == "copy"
                and os.path.isfile(dst)
            ):

                os.remove(dst)



            elif (
                action_type == "mkdir"
                and os.path.isdir(dst)
            ):

                if not os.listdir(dst):

                    os.rmdir(dst)



        except OSError as error:

            print(
                f"⚠️ 撤销失败: {dst or src}"
            )

            print(error)



    save_logs(
        [
            item
            for item in logs
            if item.get("tx") != last_tx
        ]
    )


    CURRENT_TX = None


    print(
        "✅ 已撤销最近一次操作"
    )


    if rename_count:

        print(
            f"⚠️ {rename_count}个文件恢复时自动改名"
        )

# ====================== 文件判断与匹配 ======================


def stem_key(filename):
    """
    获取不带扩展名的文件名
    用于 JPG 与 CR3 匹配
    """

    return os.path.splitext(
        filename
    )[0].strip().casefold()



def is_jpg(filename):

    return filename.lower().endswith(
        JPG_SUFFIX
    )



def is_cr3(filename):

    """
    只识别 Canon CR3
    """

    return filename.lower().endswith(
        CR3_SUFFIX
    )



def matched_cr3_names(filenames):
    """
    返回与 JPG 同名的 CR3 文件
    """

    jpg_stems = {
        stem_key(name)
        for name in filenames
        if is_jpg(name)
    }


    return [
        name
        for name in filenames
        if is_cr3(name)
        and stem_key(name) in jpg_stems
    ]



# ====================== 目录遍历 ======================


def iter_dirs(root):

    """
    递归遍历目录

    自动跳过：
    - 隐藏目录
    - 程序生成目录
    """

    for dirpath, dirnames, filenames in os.walk(root):


        dirnames[:] = [
            dirname
            for dirname in dirnames
            if (
                dirname not in GENERATED_DIRS
                and not dirname.startswith(".")
            )
        ]


        if os.path.basename(dirpath).startswith("."):

            continue


        yield dirpath, filenames



def move_files_to_flat_target(files, target):

    """
    将文件移动到同一个目标目录
    """

    safe_mkdir(target)


    total = 0


    for src in files:


        if not os.path.isfile(src):

            continue


        safe_move(
            src,
            os.path.join(
                target,
                os.path.basename(src)
            )
        )


        total += 1



    return total
	
# ====================== CR3功能 ======================


# 功能1：
# 移动没有同名 JPG 的 CR3
# 每个目录单独整理

def move_unmatched_cr3():

    begin_tx()


    print(
        "\n🚀 移动没有同名 JPG 的 CR3"
    )


    total = 0


    for dirpath, filenames in iter_dirs(ROOT_DIR):


        jpg_stems = {
            stem_key(name)
            for name in filenames
            if is_jpg(name)
        }



        unmatched = [
            name
            for name in filenames
            if (
                is_cr3(name)
                and stem_key(name)
                not in jpg_stems
            )
        ]



        if not unmatched:

            continue



        target = os.path.join(
            dirpath,
            NO_MATCH_CR3_DIR
        )


        safe_mkdir(target)



        for name in unmatched:


            safe_move(
                os.path.join(
                    dirpath,
                    name
                ),

                os.path.join(
                    target,
                    name
                )
            )


            total += 1



    print(
        f"✅ 完成，共移动 {total} 个 CR3 文件"
    )

    print(
        "🔁 可输入 u 撤销"
    )





# 功能2：
# 移动所有目录 CR3 到根目录

def move_all_cr3():


    begin_tx()


    print(
        "\n🚀 移动所有目录中的 CR3"
    )


    sources = []


    for dirpath, filenames in iter_dirs(ROOT_DIR):


        sources.extend(
            os.path.join(
                dirpath,
                name
            )

            for name in filenames

            if is_cr3(name)
        )



    target = os.path.join(
        ROOT_DIR,
        ALL_CR3_DIR
    )


    total = move_files_to_flat_target(
        sources,
        target
    )



    print(
        f"✅ 完成，共移动 {total} 个 CR3 文件"
    )

    print(
        "🔁 可输入 u 撤销"
    )





# 功能3：
# 移动当前目录中有同名 JPG 的 CR3

def move_matched_cr3_current():


    begin_tx()


    print(
        "\n🚀 移动当前目录同名 JPG 的 CR3"
    )



    filenames = [

        name

        for name in os.listdir(ROOT_DIR)

        if os.path.isfile(
            os.path.join(
                ROOT_DIR,
                name
            )
        )

    ]



    sources = [

        os.path.join(
            ROOT_DIR,
            name
        )

        for name in matched_cr3_names(
            filenames
        )

    ]



    total = move_files_to_flat_target(

        sources,

        os.path.join(
            ROOT_DIR,
            MATCHED_CURRENT_CR3_DIR
        )

    )



    print(
        f"✅ 完成，共移动 {total} 个匹配 CR3"
    )

    print(
        "🔁 可输入 u 撤销"
    )





# 功能4：
# 移动所有目录中有同名 JPG 的 CR3

def move_matched_cr3_recursive():


    begin_tx()


    print(
        "\n🚀 移动所有目录同名 JPG 的 CR3"
    )



    sources = []



    for dirpath, filenames in iter_dirs(ROOT_DIR):


        sources.extend(

            os.path.join(
                dirpath,
                name
            )

            for name in matched_cr3_names(
                filenames
            )

        )



    total = move_files_to_flat_target(

        sources,

        os.path.join(
            ROOT_DIR,
            MATCHED_ALL_CR3_DIR
        )

    )



    print(
        f"✅ 完成，共移动 {total} 个匹配 CR3"
    )

    print(
        "🔁 可输入 u 撤销"
    )
	
# ====================== JPG功能 ======================


# 功能5：
# 移动当前目录 JPG

def move_jpg_current():


    begin_tx()


    print(
        "\n🚀 移动当前目录 JPG"
    )



    sources = [

        os.path.join(
            ROOT_DIR,
            name
        )

        for name in os.listdir(ROOT_DIR)

        if (
            os.path.isfile(
                os.path.join(
                    ROOT_DIR,
                    name
                )
            )

            and is_jpg(name)
        )

    ]



    total = move_files_to_flat_target(

        sources,

        os.path.join(
            ROOT_DIR,
            CURRENT_JPG_DIR
        )

    )



    print(
        f"✅ 完成，共移动 {total} 个 JPG 文件"
    )

    print(
        "🔁 可输入 u 撤销"
    )





# 功能6：
# 移动所有目录 JPG

def move_jpg_recursive():


    begin_tx()


    print(
        "\n🚀 移动所有目录 JPG"
    )



    sources = []



    for dirpath, filenames in iter_dirs(ROOT_DIR):


        sources.extend(

            os.path.join(
                dirpath,
                name
            )

            for name in filenames

            if is_jpg(name)

        )



    total = move_files_to_flat_target(

        sources,

        os.path.join(
            ROOT_DIR,
            ALL_JPG_DIR
        )

    )



    print(
        f"✅ 完成，共移动 {total} 个 JPG 文件"
    )

    print(
        "🔁 可输入 u 撤销"
    )





# ====================== 初始化目录 ======================


def clean_input_path(value):

    """
    处理拖拽路径
    """

    value = os.path.expanduser(
        value.strip()
        .strip('"')
        .strip("'")
    )


    if os.path.isdir(value):

        return os.path.abspath(value)



    if os.name != "nt":

        try:

            parts = shlex.split(value)

            if (
                len(parts) == 1
                and os.path.isdir(parts[0])
            ):

                return os.path.abspath(parts[0])


        except ValueError:

            pass



    return value





def set_root():

    global ROOT_DIR


    print(
        "\n📁 输入照片目录"
    )

    print(
        "输入路径后回车，直接回车退出"
    )


    while True:

        path = input("> ").strip()


        # 空输入退出终端
        if path == "":
            return False


        path = clean_input_path(path)


        if os.path.isdir(path):

            ROOT_DIR = path

            print(
                f"✅ 当前目录: {ROOT_DIR}"
            )

            return True


        print(
            "❌ 路径无效，请重新输入"
        )




# ====================== 颜色显示函数 ======================

def format_text(
    text,
    bold=False,
    color=None
):
    """
    终端特殊显示格式

    参数:
        text: 要显示的内容
        bold: 是否加粗
        color: 颜色名称
               可选:
               black
               red
               green
               yellow
               blue
               magenta
               cyan
               white

    返回:
        添加终端控制字符后的字符串
    """

    styles = []


    # 加粗
    if bold:
        styles.append("1")


    # 颜色
    colors = {
        "black": "30",
        "red": "31",
        "green": "32",
        "yellow": "33",
        "blue": "34",
        "magenta": "35",
        "cyan": "36",
        "white": "37",
    }


    if color in colors:
        styles.append(colors[color])


    # 没有特殊效果
    if not styles:
        return text


    return (
        "\033["
        + ";".join(styles)
        + "m"
        + text
        + "\033[0m"
    )
	
	
def blodAndGreenText(text):
    return format_text(text, bold=True, color="green")
	
# ====================== 菜单 ======================

	
def menu():


    print(
        "\n================ CR3 / JPG整理工具 ================"
    )


    print(
        f"📁 当前目录: {ROOT_DIR}"
    )


    print(
        "---------------------------------------------------"
    )


    print(
        "【CR3处理】"
    )


    print(
        "1 → 移动" + blodAndGreenText(" 当前文件夹和所有子文件夹 ") + "中" + blodAndGreenText(" 没有匹配JPG ") + "的CR3文件"
    )


    print(
        "2 → 移动" + blodAndGreenText(" 当前文件夹和所有子文件夹 ") + "中" + blodAndGreenText(" 全部        ") + "的CR3文件"
    )


    print(
        "3 → 移动" + blodAndGreenText(" 当前文件夹               ") + "中" + blodAndGreenText(" 有匹配JPG   ") + "的CR3文件"
    )


    print(
		"4 → 移动" + blodAndGreenText(" 当前文件夹和所有子文件夹 ") + "中" + blodAndGreenText(" 有匹配JPG   ") + "的CR3文件"
    )



    print(
        ""
    )


    print(
        "【JPG处理】"
    )


    print(
        "5 → 移动" + blodAndGreenText(" 当前文件夹               ") + "中 的JPG照片"
    )


    print(
        "6 → 移动" + blodAndGreenText(" 当前文件夹和所有子文件夹 ") + "中 的JPG照片"
    )



    print(
        ""
    )


    print(
        "u → 撤销最近一次操作"
    )


    print(
        "0 → 退出"
    )



    return input("> ").strip().lower()





# ====================== 主程序 ======================


def main():


    if hasattr(
        sys.stdout,
        "reconfigure"
    ):

        sys.stdout.reconfigure(
            encoding="utf-8"
        )



    if not set_root():

        return



    actions = {


        "1": move_unmatched_cr3,

        "2": move_all_cr3,

        "3": move_matched_cr3_current,

        "4": move_matched_cr3_recursive,


        "5": move_jpg_current,

        "6": move_jpg_recursive,


        "u": undo_last,

    }



    while True:


        option = menu()



        if option == "0":

            print(
                "\n📁 返回路径选择"
            )


        if not set_root():

            break


        continue



        action = actions.get(option)



        if action is None:

            print(
                "❌ 输入错误"
            )

            continue



        try:

            action()



        except (
            OSError,
            shutil.Error
        ) as error:


            print(
                f"❌ 操作失败: {error}"
            )



    input(
        "\n回车退出..."
    )





if __name__ == "__main__":

    main()