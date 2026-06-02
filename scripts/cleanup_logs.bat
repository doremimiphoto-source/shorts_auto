@echo off
setlocal
set "PYTHON_EXE=D:\Application\Claude\shorts_auto\.venv\Scripts\python.exe"
set "PYTHONUTF8=1"
cd /d "D:\Application\Claude\shorts_auto"
"%PYTHON_EXE%" -m scripts.cleanup_logs --days 30
endlocal
