@echo off
setlocal

set "USERPROFILE_DIR=C:\Users\DKSYSTEMS"
set "FFMPEG_WINGET=%USERPROFILE_DIR%\AppData\Local\Microsoft\WinGet\Links"
set "FFMPEG_PROG=C:\Program Files\ffmpeg\bin"
set "FFMPEG_PROG86=C:\Program Files (x86)\ffmpeg\bin"

if exist "%FFMPEG_WINGET%\ffmpeg.exe" (
    set "PATH=%FFMPEG_WINGET%;%PATH%"
) else if exist "%FFMPEG_PROG%\ffmpeg.exe" (
    set "PATH=%FFMPEG_PROG%;%PATH%"
) else if exist "%FFMPEG_PROG86%\ffmpeg.exe" (
    set "PATH=%FFMPEG_PROG86%;%PATH%"
)

set "PYTHON_EXE=D:\Application\Claude\shorts_auto\.venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "TRANSFORMERS_CACHE=%USERPROFILE_DIR%\.cache\huggingface\hub"
set "HF_HOME=%USERPROFILE_DIR%\.cache\huggingface"
set "SENTENCE_TRANSFORMERS_HOME=%USERPROFILE_DIR%\.cache\torch\sentence_transformers"
set "TRANSFORMERS_OFFLINE=1"
set "HF_DATASETS_OFFLINE=1"

cd /d "D:\Application\Claude\shorts_auto"

set "BAT_LOG=D:\Application\Claude\shorts_auto\logs\batch_stderr.log"
"%PYTHON_EXE%" -m scripts.run_batch --count 1 2>>"%BAT_LOG%"

endlocal
