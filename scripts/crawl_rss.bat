@echo off
setlocal

set "USERPROFILE_DIR=C:\Users\DKSYSTEMS"
set "FFMPEG_WINGET=%USERPROFILE_DIR%\AppData\Local\Microsoft\WinGet\Links"
set "FFMPEG_PROG=C:\Program Files\ffmpeg\bin"

if exist "%FFMPEG_WINGET%\ffmpeg.exe" (
    set "PATH=%FFMPEG_WINGET%;%PATH%"
) else if exist "%FFMPEG_PROG%\ffmpeg.exe" (
    set "PATH=%FFMPEG_PROG%;%PATH%"
)

set "PYTHON_EXE=D:\Application\Claude\shorts_auto\.venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "TRANSFORMERS_CACHE=%USERPROFILE_DIR%\.cache\huggingface\hub"
set "HF_HOME=%USERPROFILE_DIR%\.cache\huggingface"
set "SENTENCE_TRANSFORMERS_HOME=%USERPROFILE_DIR%\.cache\torch\sentence_transformers"

cd /d "D:\Application\Claude\shorts_auto"

set "BAT_LOG=D:\Application\Claude\shorts_auto\logs\batch_stderr.log"
"%PYTHON_EXE%" -m scripts.crawl_rss --limit 10 2>>"%BAT_LOG%"

endlocal
