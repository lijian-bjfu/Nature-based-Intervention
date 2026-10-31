#!/bin/bash
# 在 Mac 上打包成一个不依赖 Python 的可执行文件（双击就能跑，不用装 Python、不用开终端）。
#
# 用法：
#   cd 流程单系统/packaging
#   ./build_mac.sh
#
# 打包这台 Mac 本身需要装 Python 3（随便哪个版本都行）和 pip，这是打包这一步才需要的，
# 生成出来的那个可执行文件本身不需要。生成结果在 packaging/dist_mac/nbi_flow_system，
# 发给别人的时候把这一个文件拷过去就行，不用带别的。
set -e
cd "$(dirname "$0")/.."   # 回到 流程单系统/ 目录

python3 -m pip install --quiet --upgrade pyinstaller

python3 -m PyInstaller \
  --onefile \
  --name nbi_flow_system \
  --paths app \
  --distpath packaging/dist_mac \
  --workpath packaging/build_mac \
  --specpath packaging \
  --console \
  run.py

echo ""
echo "打包完成：packaging/dist_mac/nbi_flow_system"
echo "双击这个文件（或者在终端里 ./nbi_flow_system）就能跑，会自动打开浏览器。"
echo "数据会存在这个可执行文件旁边的 data/ 文件夹里——发给别人之前，自己先在这台机器"
echo "上双击试跑一次、确认没问题，再把这一个文件拷给对方（对方那边会在自己电脑上"
echo "重新生成一份空的 data/，不会带着你测试时产生的数据过去）。"
