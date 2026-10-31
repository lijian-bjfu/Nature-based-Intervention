@echo off
REM 在 Windows 上打包成一个不依赖 Python 的可执行文件（双击 .exe 就能跑，不用装 Python）。
REM
REM 用法：双击这个文件，或者在命令提示符里：
REM   cd 流程单系统\packaging
REM   build_win.bat
REM
REM 打包这台 Windows 电脑本身需要先装好 Python 3（装的时候勾上 "Add python.exe to PATH"），
REM 这是打包这一步才需要的，生成出来的 .exe 本身不需要。生成结果在
REM packaging\dist_win\nbi_flow_system.exe，发给别人的时候把这一个文件拷过去就行。

cd /d "%~dp0\.."

python -m pip install --quiet --upgrade pyinstaller
if errorlevel 1 (
    echo 找不到 python，先装好 Python 3 并勾选 "Add python.exe to PATH"，再重跑这个脚本。
    pause
    exit /b 1
)

python -m PyInstaller ^
  --onefile ^
  --name nbi_flow_system ^
  --paths app ^
  --distpath packaging\dist_win ^
  --workpath packaging\build_win ^
  --specpath packaging ^
  --console ^
  run.py

echo.
echo 打包完成：packaging\dist_win\nbi_flow_system.exe
echo 双击这个 .exe 就能跑，会自动打开浏览器。数据会存在它旁边的 data\ 文件夹里——
echo 自己先在这台电脑上双击试跑一次、确认没问题，再把这一个 .exe 文件拷给对方
echo （对方那边会在自己电脑上重新生成一份空的 data\，不会带着你测试时产生的数据过去）。
pause
