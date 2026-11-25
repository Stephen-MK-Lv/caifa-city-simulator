@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  call "%~dp0安装依赖.cmd"
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" run.py
if errorlevel 1 (
  echo 启动未完成。若提示端口占用，请打开已有服务，或按使用说明更换端口。
  pause
)
endlocal
