"""추천 폰트 다운로드 스크립트.

assets/fonts/ 에 FFmpeg 직접 참조용으로 저장.
- Pretendard (GitHub, OFL-1.1)
- Gowun Dodum (Google Fonts, OFL-1.1)
- Noto Sans KR (Google Fonts, OFL-1.1)
- Noto Serif KR (Google Fonts, OFL-1.1)
- Nanum Gothic (Google Fonts, OFL-1.1)
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import requests

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FONT_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT = 60


def download(url: str, dest: Path, label: str) -> bool:
    if dest.exists():
        print(f"  [SKIP] {label} - 이미 존재: {dest.name}")
        return True
    print(f"  [DOWN] {label} ...", end="", flush=True)
    try:
        r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        dest.write_bytes(r.content)
        print(f" {len(r.content)//1024}KB OK")
        return True
    except Exception as e:
        print(f" FAIL: {e}")
        return False


def download_zip_extract(url: str, label: str, members: dict[str, str]) -> bool:
    """zip을 다운로드해 특정 파일만 추출. members = {zip_내부경로: 저장파일명}"""
    missing = {src: dst for src, dst in members.items() if not (FONT_DIR / dst).exists()}
    if not missing:
        print(f"  [SKIP] {label} - 모두 존재")
        return True
    print(f"  [DOWN] {label} zip...", end="", flush=True)
    try:
        r = requests.get(url, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        print(f" {len(r.content)//1024}KB", end="", flush=True)
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            names = zf.namelist()
            for src, dst in missing.items():
                # 대소문자 무시 partial match
                matched = next((n for n in names if src.lower() in n.lower()), None)
                if matched:
                    data = zf.read(matched)
                    (FONT_DIR / dst).write_bytes(data)
                    print(f"\n    extracted → {dst}")
                else:
                    print(f"\n    NOT FOUND in zip: {src}")
        return True
    except Exception as e:
        print(f" FAIL: {e}")
        return False


# ── Google Fonts 직접 다운로드 URL ──────────────────────────────────────
# Google Fonts CSS2 API → 정적 woff2/ttf URL 사용

# google/fonts GitHub raw 직접 다운로드 (TTF/OTF, FFmpeg 호환)
_GH_RAW = "https://raw.githubusercontent.com/google/fonts/main/ofl"

GOOGLE_FONT_FILES: list[tuple[str, str]] = [
    # (GitHub raw URL, 저장 파일명)
    (f"{_GH_RAW}/gowundodum/GowunDodum-Regular.ttf",               "GowunDodum-Regular.ttf"),
    (f"{_GH_RAW}/notosanskr/NotoSansKR-Bold.ttf",                  "NotoSansKR-Bold.ttf"),
    (f"{_GH_RAW}/notosanskr/NotoSansKR-Black.ttf",                 "NotoSansKR-Black.ttf"),
    (f"{_GH_RAW}/notosanskr/NotoSansKR-Medium.ttf",                "NotoSansKR-Medium.ttf"),
    (f"{_GH_RAW}/notosanskr/NotoSansKR-Regular.ttf",               "NotoSansKR-Regular.ttf"),
    (f"{_GH_RAW}/notoserifkr/NotoSerifKR-SemiBold.otf",            "NotoSerifKR-SemiBold.otf"),
    (f"{_GH_RAW}/notoserifkr/NotoSerifKR-Regular.otf",             "NotoSerifKR-Regular.otf"),
    (f"{_GH_RAW}/nanumgothic/NanumGothic-Regular.ttf",             "NanumGothic-Regular.ttf"),
    (f"{_GH_RAW}/nanumgothic/NanumGothic-Bold.ttf",                "NanumGothic-Bold.ttf"),
]

# ── Pretendard (GitHub Release) ─────────────────────────────────────────
PRETENDARD_ZIP_URL = (
    "https://github.com/orioncactus/pretendard/releases/download/"
    "v1.3.9/Pretendard-1.3.9.zip"
)
PRETENDARD_MEMBERS = {
    "Pretendard-ExtraBold.otf": "Pretendard-ExtraBold.otf",
    "Pretendard-Bold.otf":      "Pretendard-Bold.otf",
    "Pretendard-Black.otf":     "Pretendard-Black.otf",
    "Pretendard-Regular.otf":   "Pretendard-Regular.otf",
    "Pretendard-Medium.otf":    "Pretendard-Medium.otf",
}




def main() -> None:
    print(f"\n[폰트 다운로드] 저장 위치: {FONT_DIR}\n")
    ok = 0
    fail = 0

    print("── Pretendard ──")
    if download_zip_extract(PRETENDARD_ZIP_URL, "Pretendard v1.3.9", PRETENDARD_MEMBERS):
        ok += len(PRETENDARD_MEMBERS)
    else:
        fail += len(PRETENDARD_MEMBERS)

    print("\n── Google Fonts (GitHub raw TTF) ──")
    for url, filename in GOOGLE_FONT_FILES:
        dest = FONT_DIR / filename
        if download(url, dest, filename):
            ok += 1
        else:
            fail += 1

    print(f"\n완료: 성공 {ok}개 / 실패 {fail}개")
    print("\n설치된 폰트 목록:")
    for f in sorted(FONT_DIR.glob("*.*")):
        print(f"  {f.name}  ({f.stat().st_size // 1024}KB)")


if __name__ == "__main__":
    main()
