@echo off
setlocal

set "USERPROFILE_DIR=C:\Users\DKSYSTEMS"
set "PYTHON_EXE=D:\Application\Claude\shorts_auto\.venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "HF_HOME=%USERPROFILE_DIR%\.cache\huggingface"

cd /d "D:\Application\Claude\shorts_auto"
"%PYTHON_EXE%" -m scripts.notify_schedule 2>>"D:\Application\Claude\shorts_auto\logs\batch_stderr.log"

endlocal
