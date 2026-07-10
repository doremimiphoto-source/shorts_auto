"""얼굴없는 study 배경 이미지 풀 사전 생성 → assets/bg_ai_pool/<주제>/

렌더타임 Pollinations 의존을 없애기 위해 배경 이미지를 미리 생성해 둔다.
풀이 있으면 render_stage가 API 무호출로 배경을 구성(안정) → 없을 때만 라이브 생성.
assets/ 는 git 추적되므로 Mac에서 한 번 만들면 push→Windows pull로 공유된다.

재실행 가능 (기존 파일 스킵). Pollinations 불안정 대비 재시도·간격 내장.

  python -m scripts.build_bg_pool                       # 전체 주제 6장 + 사람 8장
  python -m scripts.build_bg_pool --per-topic 8 --person 10
  python -m scripts.build_bg_pool --topics planner,exam,math   # 일부 주제만
  python -m scripts.build_bg_pool --delay 2.0           # 요청 간격(초)
"""

from __future__ import annotations

import argparse
import sys
import time

from src.renderer.bg_generator import (
    _KR_TOPICS, _KR_SETTINGS, _KR_DEFAULT, _KR_DEFAULT_KEY, _PERSON_SCENES,
    _POOL_DIR, _PERSON_KEY, _object_prompt, _person_prompt, _fetch_image,
)


def _seed_for(key: str, i: int) -> int:
    """주제·인덱스로 안정적 seed (재실행 시 동일 이미지 재현)."""
    base = sum(ord(c) for c in key) * 1000
    return (base + i * 37) % 1_000_000


def build_topic(key: str, scene: str, per: int, *, delay: float, timeout: int) -> tuple[int, int]:
    d = _POOL_DIR / key
    d.mkdir(parents=True, exist_ok=True)
    made = skipped = 0
    for i in range(per):
        out = d / f"img_{i:02d}.jpg"
        if out.exists() and out.stat().st_size > 8_000:
            skipped += 1
            continue
        setting = _KR_SETTINGS[i % len(_KR_SETTINGS)]
        prompt = _object_prompt(scene, setting)
        img = _fetch_image(prompt, out, seed=_seed_for(key, i), timeout_sec=timeout)
        if img:
            made += 1
            print(f"  [{key}] {i+1}/{per} ✅")
        else:
            print(f"  [{key}] {i+1}/{per} ❌ (실패, 다음 실행에 재시도)")
        time.sleep(delay)
    return made, skipped


def build_person(per: int, *, delay: float, timeout: int) -> tuple[int, int]:
    d = _POOL_DIR / _PERSON_KEY
    d.mkdir(parents=True, exist_ok=True)
    made = skipped = 0
    for i in range(per):
        out = d / f"img_{i:02d}.jpg"
        if out.exists() and out.stat().st_size > 8_000:
            skipped += 1
            continue
        prompt = _person_prompt(i)          # 손글씨/뒷모습/오버숄더 회전
        img = _fetch_image(prompt, out, seed=_seed_for("person", i), timeout_sec=timeout)
        if img:
            made += 1
            print(f"  [_person] {i+1}/{per} ✅")
        else:
            print(f"  [_person] {i+1}/{per} ❌")
        time.sleep(delay)
    return made, skipped


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="얼굴없는 study 배경 이미지 풀 사전 생성")
    ap.add_argument("--per-topic", type=int, default=6, help="주제당 이미지 수")
    ap.add_argument("--person", type=int, default=8, help="얼굴없는 사람 이미지 수")
    ap.add_argument("--topics", default="", help="쉼표구분 주제 키 (미지정=전체)")
    ap.add_argument("--delay", type=float, default=1.5, help="요청 간격(초)")
    ap.add_argument("--timeout", type=int, default=45, help="요청 타임아웃(초)")
    args = ap.parse_args(argv)

    only = {t.strip() for t in args.topics.split(",") if t.strip()}
    topics = [(k, s) for k, _kw, s in _KR_TOPICS] + [(_KR_DEFAULT_KEY, _KR_DEFAULT)]
    if only:
        topics = [(k, s) for k, s in topics if k in only]

    print(f"풀 위치: {_POOL_DIR}")
    total_made = total_skip = 0
    for key, scene in topics:
        print(f"▶ 주제 '{key}' (목표 {args.per_topic}장)")
        m, s = build_topic(key, scene, args.per_topic, delay=args.delay, timeout=args.timeout)
        total_made += m; total_skip += s
    if not only or _PERSON_KEY in only or args.person:
        print(f"▶ 얼굴없는 사람 (_person, 목표 {args.person}장)")
        m, s = build_person(args.person, delay=args.delay, timeout=args.timeout)
        total_made += m; total_skip += s

    print(f"\n완료: 신규 {total_made}장, 스킵(기존) {total_skip}장")
    print("→ git add assets/bg_ai_pool && commit·push 하면 Windows에도 공유됩니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
