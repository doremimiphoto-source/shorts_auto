@echo off
setlocal EnableDelayedExpansion

:: ── 환경 변수 명시 설정 (Task Scheduler SYSTEM 계정용) ──────────────────────
:: SYSTEM 계정은 사용자 레벨 PATH를 상속받지 않으므로 직접 지정한다.
set "USERPROFILE_DIR=C:\Users\DKSYSTEMS"

:: ffmpeg 경로 우선순위: WinGet 링크 → 직접 설치 경로
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

:: Python 경로 (venv)
set "PYTHON_EXE=D:\Application\Claude\shorts_auto\.venv\Scripts\pythonw.exe"

:: 인코딩
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

:: HuggingFace 캐시 위치 고정 (SYSTEM 계정에서도 동일 경로 사용)
set "TRANSFORMERS_CACHE=%USERPROFILE_DIR%\.cache\huggingface\hub"
set "HF_HOME=%USERPROFILE_DIR%\.cache\huggingface"
set "SENTENCE_TRANSFORMERS_HOME=%USERPROFILE_DIR%\.cache\torch\sentence_transformers"

:: 작업 디렉토리
cd /d "D:\Application\Claude\shorts_auto"

:: 실행
"%PYTHON_EXE%" -m scripts.run_batch --count 1
endlocal
