"""ffmpeg 실행 파일 경로 해석 유틸.

Task Scheduler SYSTEM 계정은 사용자 레벨 PATH를 상속받지 않으므로
shutil.which 실패 시 알려진 절대 경로를 순서대로 탐색한다.
"""

from __future__ import annotations

import shutil
from pathlib import Path

_KNOWN_PATHS = [
    # WinGet user-level (기본 설치 위치 — 사용자 이름별 탐색)
    *(
        Path(f"C:/Users/{u}/AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe")
        for u in ["DKSYSTEMS", "Administrator", "User"]
    ),
    # 시스템 레벨 일반 설치 경로
    Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
    Path("C:/Program Files (x86)/ffmpeg/bin/ffmpeg.exe"),
    Path("C:/ffmpeg/bin/ffmpeg.exe"),
    Path("C:/ProgramData/chocolatey/bin/ffmpeg.exe"),
]


def resolve_ffmpeg() -> str:
    """ffmpeg 실행 파일 절대 경로 반환. 못 찾으면 'ffmpeg' 그대로 반환."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    # 환경 변수 FFMPEG_BIN 명시 시 최우선
    import os
    env_bin = os.environ.get("FFMPEG_BIN", "")
    if env_bin and Path(env_bin).exists():
        return env_bin
    # PATH.home() 기반 (현재 실행 계정 기준)
    try:
        winget_home = Path.home() / "AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe"
        if winget_home.exists():
            return str(winget_home)
    except Exception:
        pass
    # 알려진 절대 경로 탐색
    for p in _KNOWN_PATHS:
        if p.exists():
            return str(p)
    return "ffmpeg"
