@echo off
REM === badwordshock EXE 版构建脚本 ===
REM 0. 清理
rmdir /s /q dist\badwordshock 2>nul
rmdir /s /q build 2>nul

REM 1. PyInstaller 打包
pyinstaller badwordshock.spec --noconfirm
if %errorlevel% neq 0 exit /b %errorlevel%

REM 2. 复制 cuBLAS / CUDA runtime DLL 到 EXE 同目录（Windows 保底搜索路径）
copy "C:\Users\Max\AppData\Roaming\Python\Python311\site-packages\torch\lib\cublas64_12.dll" "dist\badwordshock\" >nul
copy "C:\Users\Max\AppData\Roaming\Python\Python311\site-packages\torch\lib\cudart64_12.dll" "dist\badwordshock\" >nul

REM 3. 复制支持文件
copy manifest.json dist\badwordshock\ >nul
xcopy /e /i badwords dist\badwordshock\badwords\ >nul

REM 4. 生成 EXE 版 start.bat
echo @echo off > dist\badwordshock\start.bat
echo "%%~dp0badwordshock.exe" >> dist\badwordshock\start.bat

echo ============================================
echo 构建完成！dist\badwordshock\
echo ============================================
