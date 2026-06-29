#!/bin/zsh
cd "$(dirname "$0")"
python3 "photo_workflow.py"
echo -e "\n执行完毕，按回车关闭窗口..."
read