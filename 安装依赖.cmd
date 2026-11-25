@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo 首次安装需要 Python 3.12 或更新版本，以及可访问 PyPI 的网络。
if exist ".venv\Scripts\python.exe" goto install
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -m venv .venv
  if not errorlevel 1 goto install
)
where python >nul 2>nul
if not errorlevel 1 (
  python -m venv .venv
  if not errorlevel 1 goto install
)
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
  "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m venv .venv
  if not errorlevel 1 goto install
)
echo 未找到可用 Python。请安装 Python 3.12 后再次打开本文件。
pause
exit /b 1
:install
".venv\Scripts\python.exe" -m pip install -r requirements-lock.txt
if errorlevel 1 (
  echo 依赖安装失败。请检查网络或 Python 版本，保留现有数据后重试。
  pause
  exit /b 1
)
echo 安装完成。请打开“启动Web仿真.cmd”。
exit /b 0
