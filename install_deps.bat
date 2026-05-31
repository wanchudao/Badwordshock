@echo off
chcp 65001 >nul
echo ============================================
echo   badwordshock 依赖安装脚本
echo ============================================
echo.
echo 正在安装必需依赖（websockets, numpy, sounddevice, faster-whisper）...
echo.
pip install -r "%~dp0requirements.txt"
echo.
echo ============================================
echo 安装完成！
echo.
echo 如果上述有报错，请检查：
echo 1. Python 是否已安装并加入 PATH（命令行输入 python --version 验证）
echo 2. 是否在使用 DGHub 自带的 Python 环境（如 venv 需先激活）
echo 3. 网络是否能访问 PyPI（国内用户可加 -i https://pypi.tuna.tsinghua.edu.cn/simple）
echo ============================================
echo.
pause
