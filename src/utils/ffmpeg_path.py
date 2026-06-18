"""ffmpeg 실행 파일 경로 해석 유틸.

PATH에 없는 환경(Task Scheduler SYSTEM 계정, launchd 등)에서
shutil.which 실패 시 알려진 절대 경로를 순서대로 탐색한다.
"""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path

# macOS (Homebrew) 알려진 경로
_KNOWN_PATHS_MAC = [
    Path("/opt/homebrew/bin/ffmpeg"),     # Apple Silicon
    Path("/usr/local/bin/ffmpeg"),         # Intel Mac
    Path("/usr/bin/ffmpeg"),
]

# Windows 알려진 경로
_KNOWN_PATHS_WIN = [
    *(
        Path(f"C:/Users/{u}/AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe")
        for u in ["DKSYSTEMS", "Administrator", "User"]
    ),
    Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
    Path("C:/Program Files (x86)/ffmpeg/bin/ffmpeg.exe"),
    Path("C:/ffmpeg/bin/ffmpeg.exe"),
    Path("C:/ProgramData/chocolatey/bin/ffmpeg.exe"),
]


def resolve_ffmpeg() -> str:
    """ffmpeg 실행 파일 절대 경로 반환. 못 찾으면 'ffmpeg' 그대로 반환."""
    # 1. PATH 우선 탐색
    found = shutil.which("ffmpeg")
    if found:
        return found
    # 2. 환경 변수 FFMPEG_BIN 명시 시 사용
    env_bin = os.environ.get("FFMPEG_BIN", "")
    if env_bin and Path(env_bin).exists():
        return env_bin
    # 3. 플랫폼별 알려진 경로 탐색
    known = _KNOWN_PATHS_MAC if platform.system() == "Darwin" else _KNOWN_PATHS_WIN
    for p in known:
        if p.exists():
            return str(p)
    return "ffmpeg"
