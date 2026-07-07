"""카드 콘텐츠 시스템용 영어 폰트 다운로드 (Poppins + Inter).

Google Fonts — OFL 라이선스, 상업적 사용 가능.
실행: python scripts/download_cards_fonts.py
"""

import sys
import urllib.request
from pathlib import Path

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

FONTS = [
    (
        "Poppins-Black.ttf",
        "https://fonts.gstatic.com/s/poppins/v21/pxiByp8kv8JHgFVrLBT5V1tvFP-KUEg.woff2",
    ),
    (
        "Poppins-Bold.ttf",
        "https://fonts.gstatic.com/s/poppins/v21/pxiByp8kv8JHgFVrLDD4V1tvFP-KUEg.woff2",
    ),
    (
        "Poppins-SemiBold.ttf",
        "https://fonts.gstatic.com/s/poppins/v21/pxiByp8kv8JHgFVrLEj6V1tvFP-KUEg.woff2",
    ),
    (
        "Poppins-Medium.ttf",
        "https://fonts.gstatic.com/s/poppins/v21/pxiByp8kv8JHgFVrLGT7V1tvFP-KUEg.woff2",
    ),
    (
        "Poppins-Regular.ttf",
        "https://fonts.gstatic.com/s/poppins/v21/pxiEyp8kv8JHgFVrJJfecnFHGPc.woff2",
    ),
]

# Inter는 bunny.net CDN (woff2 → TTF 변환 불필요, Pillow가 woff2 지원 안 함)
# TTF 직접 링크 사용
FONTS_TTF = [
    (
        "Poppins-Black.ttf",
        "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Black.ttf",
    ),
    (
        "Poppins-Bold.ttf",
        "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Bold.ttf",
    ),
    (
        "Poppins-SemiBold.ttf",
        "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-SemiBold.ttf",
    ),
    (
        "Poppins-Medium.ttf",
        "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Medium.ttf",
    ),
    (
        "Poppins-Regular.ttf",
        "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Regular.ttf",
    ),
    (
        "Inter-Bold.ttf",
        "https://github.com/google/fonts/raw/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf",
    ),
]


def download(name: str, url: str) -> bool:
    dst = FONTS_DIR / name
    if dst.exists() and dst.stat().st_size > 10_000:
        print(f"  ✓ {name} (이미 존재)")
        return True
    print(f"  ↓ {name} 다운로드 중...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        if len(data) < 10_000:
            print(f"  ✗ {name} — 파일 크기 이상 ({len(data)} bytes)")
            return False
        dst.write_bytes(data)
        print(f"  ✓ {name} ({len(data) // 1024} KB)")
        return True
    except Exception as e:
        print(f"  ✗ {name} — {e}")
        return False


def main() -> None:
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"폰트 디렉토리: {FONTS_DIR}\n")

    ok = 0
    fail = 0
    for name, url in FONTS_TTF:
        if download(name, url):
            ok += 1
        else:
            fail += 1

    print(f"\n완료: {ok}개 성공, {fail}개 실패")
    if fail > 0:
        print("실패한 폰트는 https://fonts.google.com/specimen/Poppins 에서 수동 다운로드 후")
        print(f"  {FONTS_DIR}/ 에 복사하세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
