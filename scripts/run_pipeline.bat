@echo off
cd /d "D:\Application\Claude\shorts_auto"
set LOGFILE=logs\scheduler\run_pipeline_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%.log
set LOGFILE=%LOGFILE: =0%
"D:\Application\Claude\shorts_auto\.venv\Scripts\python.exe" -m src.main >> "%LOGFILE%" 2>&1
