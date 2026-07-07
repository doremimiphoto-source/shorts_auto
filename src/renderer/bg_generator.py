"""콘텐츠 매칭 AI 배경 생성 (Pollinations AI — 무료, API 키 불필요).

스크립트 hook/body/twist 내용 → 영문 이미지 프롬프트 → 1080×1920 배경 이미지 생성.
생성 이미지 → 3초 루프 MP4 변환 → 렌더 파이프라인에 전달 (-stream_loop -1 로 루프).
생성 실패(타임아웃·네트워크 오류) 시 None 반환 → 기존 풀 폴백.
"""

from __future__ import annotations

import hashlib
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path




# ── 한국 학생 맥락 프롬프트 (한국풍·내용매칭·seed 변형 다양성) ───────────────────
# 사용자 요구: 외국/추상 이미지 대신 한국 학생 실사 장면, 내용과 매칭, 반복 없이.
_KR_STYLE = (
    "photorealistic candid editorial photography, realistic Korean student, "
    "cinematic warm amber and soft teal color grade, shallow depth of field bokeh, "
    "natural lighting, no text no watermark, no logo, vertical portrait 9:16"
)

# 다양성용 세팅/앵글 변형 (seed로 선택 → 같은 주제라도 다른 장면)
_KR_SETTINGS = [
    "at a tidy wooden desk at night under a warm amber desk lamp",
    "by a large window with soft morning daylight streaming in",
    "in a cozy study room with bookshelves softly blurred behind",
    "at a clean minimal desk with neat stationery and colorful sticky notes",
    "in a quiet apartment room with city night lights bokeh through the window",
    "at a library-style desk with stacked textbooks and a small plant",
]

# 주제(키워드) → 한국 학생 장면 (내용 매칭). 모두 한국 맥락.
_KR_TOPICS: list[tuple[list[str], str]] = [
    (["부적", "행운", "합격", "기원", "lucky"],
     "a Korean middle school student in navy school uniform holding a good-luck exam charm with a hopeful smile"),
    (["멀리던지기", "멀리차기", "에어로빅", "줄넘기", "체육", "달리기"],
     "a Korean middle school student in PE uniform mid-motion in a school gymnasium, energetic"),
    (["도덕", "인성", "배려", "봉사"],
     "a thoughtful Korean middle school student writing reflections in a notebook in a calm classroom"),
    (["역사", "독후감", "한국사", "조선", "고려", "삼국", "임진왜란"],
     "a Korean middle school student studying history, a Korean palace (Gyeongbokgung) poster softly visible on the wall"),
    (["수학", "일차부등식", "방정식", "함수", "그래프", "도형", "확률"],
     "a Korean middle school student solving math problems in a workbook, pencil in hand, concentrating"),
    (["과학", "영양소", "광물", "실험", "세포", "화학", "물리"],
     "a Korean middle school student in a school science lab with beakers, curious and focused"),
    (["국어", "문학", "반어", "역설", "풍자", "서술형", "소설", "수필", "고전"],
     "a Korean middle school student absorbed in reading a Korean literature book at a desk"),
    (["음악", "칼림바", "리코더", "가창", "음악신문"],
     "a Korean middle school student practicing a musical instrument in a bright music room"),
    (["영어", "영단어", "영어 듣기", "영어 쓰기", "english"],
     "a Korean middle school student studying English with vocabulary flashcards at a desk"),
    (["한문", "한자", "성어", "중국어", "한어병음"],
     "a Korean middle school student practicing Chinese characters with a brush pen, focused"),
    (["암기", "기억", "망각", "두문자", "연상", "외우", "플래시"],
     "a Korean middle school student memorizing with colorful flashcards and sticky notes on the wall"),
    (["포모도로", "시간표", "플래너", "시간 관리", "계획", "루틴"],
     "a Korean middle school student with a study planner and a small timer on a tidy desk"),
    (["수면", "밤새", "잠", "숙면", "해마", "졸음"],
     "a Korean middle school student sleeping peacefully at a desk, gentle bedside lamp, textbooks beside them"),
    (["슬럼프", "동기", "멘탈", "포기", "의지", "집중", "스트레스"],
     "a determined Korean middle school student at a desk facing a sunrise window, motivational mood"),
    (["스마트폰", "sns", "유튜브", "인스타", "디지털", "게임"],
     "a Korean middle school student setting down a smartphone to open a textbook, refocusing"),
    (["기출", "기말", "중간고사", "모의고사", "시험 대비", "수행평가", "내신", "벼락치기"],
     "a Korean middle school student studying intensely for exams at a desk piled with textbooks, determined focus"),
]

_KR_DEFAULT = ("a Korean middle school student in navy school uniform studying diligently, "
               "focused and calm")


def _build_prompt(script: dict, seed: int | None = None) -> str:
    """스크립트 내용 → 한국 학생 장면 프롬프트 (내용 매칭 + seed 변형)."""
    full = " ".join([
        str(script.get("hook", "")), str(script.get("body", "")),
        str(script.get("twist", "")), str(script.get("title", "")),
        str(script.get("hook_pattern", "")),
    ]).lower()
    scene = _KR_DEFAULT
    for keywords, s in _KR_TOPICS:
        if any(kw.lower() in full for kw in keywords):
            scene = s
            break
    setting = _KR_SETTINGS[(seed or 0) % len(_KR_SETTINGS)]
    return f"{scene}, {setting}, {_KR_STYLE}"


def generate_bg_video(
    script: dict,
    cache_dir: Path,
    *,
    timeout_sec: int = 45,
    duration: int = 35,
    ffmpeg_bin: str = "ffmpeg",
    seed: int | None = None,
) -> Path | None:
    """AI 이미지 생성 → 풀 길이 Ken Burns 판/줌 영상. 실패 시 None 반환.

    - Pollinations AI(FLUX)로 1080×1920 이미지 생성
    - scale 1.30× → crop 이동으로 35초 무루프 판 애니메이션
    - 해시 마지막 자리로 이동 방향 다양화 (4방향)
    - cache_dir에 프롬프트 해시 기반 캐시 → 동일 콘텐츠 재생성 방지
    - seed: 영상별 고유 시드 → 같은 콘텐츠라도 매번 다른 이미지 (반복 제거)
    """
    # seed를 해시·URL·프롬프트에 반영 → 동일 콘텐츠라도 영상마다 다른 한국 장면
    seed_val = int(seed) % 1_000_000 if seed is not None else None
    prompt = _build_prompt(script, seed_val)
    hash_src = f"{prompt}|seed={seed_val}" if seed_val is not None else prompt
    content_hash = hashlib.sha256(hash_src.encode()).hexdigest()[:14]
    img_path = cache_dir / f"aibg_{content_hash}.jpg"
    vid_path = cache_dir / f"aibg_{content_hash}_full.mp4"

    # ── 캐시 히트 (풀 비디오 ≥ 200 KB)
    if vid_path.exists() and vid_path.stat().st_size > 200_000:
        return vid_path

    cache_dir.mkdir(parents=True, exist_ok=True)

    # ── Pollinations AI 이미지 생성
    if not (img_path.exists() and img_path.stat().st_size > 10_000):
        encoded = urllib.parse.quote(prompt)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width=1080&height=1920&nologo=true&enhance=true&model=flux-realism"
        )
        if seed_val is not None:
            url += f"&seed={seed_val}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ShortsAuto/1.0"})
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                data = resp.read()
            if len(data) < 10_000:
                return None
            img_path.write_bytes(data)
        except Exception:
            return None

    if not img_path.exists() or img_path.stat().st_size < 10_000:
        return None

    # ── Ken Burns: scale 1.40× → crop 이동 (pan 애니메이션)
    # 1.40× 스케일로 1080×1920 주변에 더 넓은 pan 여유 확보 (더 역동적인 움직임)
    sw = 1512   # 1080 * 1.40 (짝수)
    sh = 2688   # 1920 * 1.40 (짝수)
    xp = sw - 1080   # 432px pan 폭
    yp = sh - 1920   # 768px pan 높이
    d  = duration

    # 해시 마지막 16진수로 4방향 중 선택 → 콘텐츠마다 다른 이동 패턴
    pan_dir = int(content_hash[-1], 16) % 4
    if pan_dir == 0:
        xe = f"min({xp}*t/{d},{xp})"        # 좌→우
        ye = f"min({yp}*t/{d},{yp})"        # 상→하 (대각)
    elif pan_dir == 1:
        xe = f"max({xp}-{xp}*t/{d},0)"      # 우→좌
        ye = f"max({yp}-{yp}*t/{d},0)"      # 하→상 (역대각)
    elif pan_dir == 2:
        xe = f"min({xp}*t/{d},{xp})"        # 좌→우
        ye = f"{yp // 2}"                   # 수평 이동 (중앙 Y 고정)
    else:
        xe = f"{xp // 2}"                   # 중앙 X 고정
        ye = f"min({yp}*t/{d},{yp})"        # 수직 이동 (상→하)

    vf = (
        f"scale={sw}:{sh}:flags=lanczos,"
        f"crop=1080:1920:x='{xe}':y='{ye}',"
        f"setsar=1"
    )

    cmd = [
        ffmpeg_bin, "-hide_banner", "-y",
        "-loop", "1", "-i", str(img_path),
        "-vf", vf,
        "-t", str(d),
        "-r", "30",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-pix_fmt", "yuv420p",
        str(vid_path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=180, check=False)
    if result.returncode != 0 or not vid_path.exists() or vid_path.stat().st_size < 100_000:
        return None

    return vid_path
