"""MeloTTS 한국어 smoke test.

1) 모델 로드 (첫 호출 시 자동 다운로드)
2) 화자 목록 확인
3) speed 변형 5종으로 짧은 샘플 합성
4) 결과 wav 출력 (output/audio/melo_smoke_*.wav)
"""

from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SAMPLES = [
    ("kr_soft_default", 0.95, "안녕하세요. 오늘 들려드릴 사연은 평범한 어느 직장인의 이야기입니다."),
    ("kr_soft_slow",    0.90, "조용한 새벽, 그녀는 오래된 일기장을 펼쳤습니다."),
    ("kr_soft_normal",  1.00, "그날 이후로 그는 다시는 그곳으로 돌아가지 않았습니다."),
    ("kr_soft_brisk",   1.05, "전화는 끊어졌고 메시지는 읽음 표시만 남아 있었어요."),
    ("kr_soft_calm",    0.92, "마지막 한 줄을 읽고 그는 천천히 눈을 감았습니다."),
]


def main() -> int:
    # eunjeon 빌드 우회 패치 (melo_engine 의 헬퍼 재사용)
    from src.tts.melo_engine import _patch_g2pkk_for_windows
    _patch_g2pkk_for_windows()
    from melo.api import TTS

    out_dir = PROJECT_ROOT / "output" / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(" MeloTTS Korean smoke test")
    print("=" * 60)

    t0 = time.monotonic()
    model = TTS(language="KR", device="cpu")
    print(f"Model loaded in {time.monotonic() - t0:.1f}s")

    spk2id = model.hps.data.spk2id
    # HParams 속성 객체 (dict 아님). vars() 로 키 조회.
    attrs = [k for k in vars(spk2id).keys() if not k.startswith("_")]
    print(f"Speaker keys: {attrs}")
    melo_key = "KR" if "KR" in attrs else (attrs[0] if attrs else "")
    melo_speaker_id = getattr(spk2id, melo_key) if melo_key else 0
    print(f"Selected speaker: {melo_key} -> id={melo_speaker_id}")

    for voice_id, speed, text in SAMPLES:
        out = out_dir / f"melo_smoke_{voice_id}.wav"
        t0 = time.monotonic()
        model.tts_to_file(text=text, speaker_id=melo_speaker_id, output_path=str(out), speed=speed)
        elapsed = time.monotonic() - t0
        size_kb = out.stat().st_size / 1024 if out.exists() else 0
        print(f"  [{voice_id}] speed={speed} elapsed={elapsed:.1f}s size={size_kb:.0f}KB '{text[:30]}...'")

    print()
    print(f"Output dir: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
