"""콘텐츠 매칭 AI 배경 생성 (Pollinations AI — 무료, API 키 불필요).

스크립트 hook/body/twist 내용 → **얼굴 없는** 공부 장면(책상·책·문구·손글씨) 프롬프트
→ 여러 장 생성 → 크로스페이드로 이어 붙인 다중장면 배경 영상(1080×1920).
단일 장면 실패/불가 시 None 반환 → render_stage에서 스톡 폴백.

개선 이력(2026-07):
  - 실사 느낌: "candid amateur photo / documentary / not cgi" + enhance=false
  - 다중장면: 영상당 여러 장면 크로스페이드 → 60초 단조로움·3~9초 이탈 완화
  - **얼굴 제거**: AI 얼굴/손 왜곡이 잦아 사람 얼굴을 빼고 책상·물건 위주로.
    사람은 손글씨(손만, 얼굴 없음)로 약간만 → 왜곡 리스크 제거 + 콘텐츠 매칭 유지
  - 반환 인터페이스(단일 Path)는 그대로 → composer 무변경
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)


# ── 생성 크기 = 영상 창(1080×1160, 거의 정사각) 비율 (강제 크롭·왜곡 방지) ──────
# composer의 영상 윈도우는 1080×1160. 9:16으로 뽑으면 세로가 심하게 잘려 구도가 틀어짐.
# → 창 비율(0.931)로 생성하고, composer가 Ken Burns만 얹도록.
_GEN_W, _GEN_H = 1296, 1392   # 창 비율 유지 + 해상도 여유 (÷8, Pollinations 안전)
_OUT_W, _OUT_H = 1080, 1160   # composer 영상 윈도우 크기

# ── 실사 스냅 스타일 (사람이 직접 찍은 사진 느낌, 얼굴 없음) ──────────────────────
# 프롬프트를 과하게 길게 하면 Pollinations 실패율↑ → 핵심 큐만 간결하게.
_STYLE = (
    "candid amateur photo, natural window light, true-to-life colors, subtle film grain, "
    "cozy korean study aesthetic, not cgi, no text, no watermark"
)
# 물건/책상 장면 — 사람 없음
_NO_PERSON = "no people, no person, no face, still life"

# 물건 중심 프레이밍 변형 (seed로 선택 → 같은 주제라도 다른 컷)
_KR_SETTINGS = [
    "top-down flat lay on a tidy wooden desk, soft daylight",
    "close-up on the desk by a window with soft daylight",
    "on a cozy desk with a small plant and warm afternoon light",
    "45-degree angle on a neat desk, sticky notes around, morning light",
    "on a light wooden desk with a bookshelf softly blurred behind",
    "minimal tidy desk, soft shadows, gentle daylight",
]

# 주제(키, 키워드, 얼굴없는 장면). 키 = 풀 폴더명 (assets/bg_ai_pool/<키>/).
_KR_TOPICS: list[tuple[str, list[str], str]] = [
    ("charm", ["부적", "행운", "합격", "기원", "lucky"],
     "a Korean good-luck exam charm (bujeok) placed on an open notebook on a desk"),
    ("pe", ["멀리던지기", "멀리차기", "에어로빅", "줄넘기", "체육", "달리기"],
     "a jump rope, clean sneakers and a water bottle on a school gym floor"),
    ("ethics", ["도덕", "인성", "배려", "봉사"],
     "an open notebook with neat handwritten reflections and a pen on a calm desk"),
    ("history", ["역사", "독후감", "한국사", "조선", "고려", "삼국", "임진왜란"],
     "an open Korean history textbook with sticky notes, a pen and a highlighter on a desk"),
    ("math", ["수학", "일차부등식", "방정식", "함수", "그래프", "도형", "확률"],
     "an open math workbook full of handwritten equations with a pencil and eraser on a desk"),
    ("science", ["과학", "영양소", "광물", "실험", "세포", "화학", "물리"],
     "science lab beakers, a small microscope and an open science notebook on a desk"),
    ("korean", ["국어", "문학", "반어", "역설", "풍자", "서술형", "소설", "수필", "고전"],
     "an open Korean literature book with reading glasses and a bookmark on a wooden desk"),
    ("music", ["음악", "칼림바", "리코더", "가창", "음악신문"],
     "sheet music, a wooden recorder and a kalimba on a bright desk"),
    ("english", ["영어", "영단어", "영어 듣기", "영어 쓰기", "english"],
     "English vocabulary flashcards and an open workbook with a pen on a desk"),
    ("hanja", ["한문", "한자", "성어", "중국어", "한어병음"],
     "a brush pen, black ink and Chinese character practice sheets on a desk"),
    ("memorize", ["암기", "기억", "망각", "두문자", "연상", "외우", "플래시"],
     "colorful flashcards and sticky notes spread across a desk and wall"),
    ("planner", ["포모도로", "시간표", "플래너", "시간 관리", "계획", "루틴"],
     "an open study planner with a pen and a small round timer on a tidy desk"),
    ("sleep", ["수면", "밤새", "잠", "숙면", "해마", "졸음"],
     "an open book and a dimmed warm desk lamp at night on a cozy desk"),
    ("motivation", ["슬럼프", "동기", "멘탈", "포기", "의지", "집중", "스트레스"],
     "an open notebook with a short motivational note by a bright window at sunrise"),
    ("phone", ["스마트폰", "sns", "유튜브", "인스타", "디지털", "게임"],
     "a smartphone set face-down next to an open textbook and a pen on a desk"),
    ("exam", ["기출", "기말", "중간고사", "모의고사", "시험 대비", "수행평가", "내신", "벼락치기"],
     "a desk piled with textbooks, highlighters and exam prep papers"),
]

_KR_DEFAULT_KEY = "default"
_KR_DEFAULT = "a tidy study desk with an open notebook, a pen and warm daylight"

# 얼굴없는 배경 이미지 사전생성 풀 (렌더타임 Pollinations 의존 제거)
_POOL_DIR = Path(__file__).resolve().parents[2] / "assets" / "bg_ai_pool"
_PERSON_KEY = "_person"

# 사람 장면 — 얼굴 절대 없음 (손글씨·뒷모습·오버숄더). 사람 존재감 '약간'용.
_PERSON_SCENES = [
    ("a hand writing korean study notes in an open notebook on a wooden desk by a window, "
     "close-up, only a hand visible, no face, no head"),
    ("over-the-shoulder view from behind of a student writing in a notebook at a desk, "
     "back of the head only, no face visible"),
    ("back view of a student sitting at a tidy desk studying by a window, seen from behind, "
     "no face, only the back and shoulders"),
]


def _match_topic(script: dict) -> tuple[str, str]:
    """스크립트 내용 → (주제 키, 얼굴없는 장면). 미매칭 시 default."""
    full = " ".join([
        str(script.get("hook", "")), str(script.get("body", "")),
        str(script.get("twist", "")), str(script.get("title", "")),
        str(script.get("hook_pattern", "")),
    ]).lower()
    for key, keywords, scene in _KR_TOPICS:
        if any(kw.lower() in full for kw in keywords):
            return key, scene
    return _KR_DEFAULT_KEY, _KR_DEFAULT


def _match_scene(script: dict) -> str:
    """[호환용] 장면만 반환."""
    return _match_topic(script)[1]


def _pool_list(key: str) -> list[Path]:
    d = _POOL_DIR / key
    if not d.exists():
        return []
    return sorted(p for p in d.glob("*.jpg") if p.stat().st_size > 8_000)


def _pick_from_pool(key: str, seed: int, n: int) -> list[Path]:
    """사전생성 풀에서 N장 선택 (물건 위주 + 사람 1). 풀 부족 시 []."""
    objs = _pool_list(key) or _pool_list(_KR_DEFAULT_KEY)
    if not objs:
        return []
    persons = _pool_list(_PERSON_KEY)
    want_person = n >= 3 and bool(persons)
    n_obj = n - 1 if want_person else n
    # seed로 서로 다른 조합 선택 (중복 없이 회전)
    chosen: list[Path] = []
    for i in range(min(n_obj, len(objs))):
        chosen.append(objs[(seed + i * 7) % len(objs)])
    # 중복 제거 (풀이 작을 때)
    seen = set(); uniq = []
    for p in chosen:
        if p not in seen:
            seen.add(p); uniq.append(p)
    chosen = uniq
    if want_person:
        chosen.insert(min(1, len(chosen)), persons[seed % len(persons)])
    return chosen[:n]


def _object_prompt(scene: str, setting: str) -> str:
    return f"{scene}, {setting}, {_NO_PERSON}, {_STYLE}"


def _person_prompt(idx: int) -> str:
    """얼굴 없는 사람 장면(손글씨/뒷모습/오버숄더) — seed로 회전."""
    scene = _PERSON_SCENES[idx % len(_PERSON_SCENES)]
    return f"{scene}, {_STYLE}"


def _build_prompt(script: dict, seed: int | None = None) -> str:
    """[호환용] 단일 장면(물건) 프롬프트 — 기존 호출부/테스트 유지."""
    scene = _match_scene(script)
    setting = _KR_SETTINGS[(seed or 0) % len(_KR_SETTINGS)]
    return _object_prompt(scene, setting)


def _fetch_image(prompt: str, out_path: Path, *, seed: int, timeout_sec: int,
                 retries: int = 3) -> Path | None:
    """Pollinations 실사 이미지 1장 다운로드 (재시도+백오프). 실패 시 None.

    다중장면 생성 시 연속 요청 일부가 실패/타임아웃하므로 재시도로 성공률을 높인다.
    enhance=false = 프롬프트에 충실한 원본(실사 톤).
    """
    if out_path.exists() and out_path.stat().st_size > 10_000:
        return out_path
    url = (
        f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
        f"?width={_GEN_W}&height={_GEN_H}&nologo=true&enhance=false&model=flux-realism&seed={seed}"
    )
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ShortsAuto/1.0"})
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                data = resp.read()
            if len(data) >= 10_000:
                out_path.write_bytes(data)
                return out_path
        except Exception:
            pass
        if attempt < retries:
            time.sleep(3.0 * (attempt + 1))   # 점증 백오프 (3·6·9s) — 부하/레이트리밋 완화
    return None


def _build_multiscene(imgs: list[Path], duration: int, out_path: Path,
                      ffmpeg_bin: str) -> Path | None:
    """N장 이미지(창 비율) → 크로스페이드 연결 → 1080×1160 영상.

    생성 크기(1296×1392)와 출력(1080×1160)이 같은 비율이라 **왜곡 없이 축소만** 한다.
    영상 모션(Ken Burns)은 composer가 얹으므로 여기선 장면 전환(크로스페이드)만 담당.
    """
    n = len(imgs)
    if n == 0:
        return None
    xf = 0.8 if n > 1 else 0.0                       # 크로스페이드 길이(초)
    seg = (duration + (n - 1) * xf) / n              # 장면당 길이 (겹침 보정)

    cmd = [ffmpeg_bin, "-hide_banner", "-y"]
    for img in imgs:
        cmd += ["-loop", "1", "-t", f"{seg:.2f}", "-i", str(img)]

    filters = []
    for i in range(n):
        # 창 비율 그대로 축소 (crop 없음 → 구도 보존, 강제 왜곡 제거)
        filters.append(
            f"[{i}:v]scale={_OUT_W}:{_OUT_H}:flags=lanczos,setsar=1,fps=30,"
            f"format=yuv420p,setpts=PTS-STARTPTS[v{i}]"
        )
    if n == 1:
        last = "v0"
    else:
        prev = "v0"
        for i in range(1, n):
            off = i * (seg - xf)
            out = f"x{i}" if i < n - 1 else "vout"
            filters.append(
                f"[{prev}][v{i}]xfade=transition=fade:duration={xf}:offset={off:.2f}[{out}]"
            )
            prev = out
        last = "vout"

    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", f"[{last}]",
        "-t", str(duration), "-r", "30",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-pix_fmt", "yuv420p",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=180, check=False)
    if result.returncode != 0 or not out_path.exists() or out_path.stat().st_size < 100_000:
        return None
    return out_path


def generate_bg_video(
    script: dict,
    cache_dir: Path,
    *,
    timeout_sec: int = 45,
    duration: int = 60,
    ffmpeg_bin: str = "ffmpeg",
    seed: int | None = None,
    scenes: int = 3,
) -> Path | None:
    """콘텐츠 매칭 실사 다중장면 배경(얼굴 없음) 생성. 실패 시 None.

    소스 우선순위 (렌더타임 API 의존 최소화):
      1) 사전생성 풀(assets/bg_ai_pool/<주제>/) — Pollinations 무호출 (안정)
      2) 풀 부족 시 Pollinations 라이브 생성 (기존)
    - **얼굴 없이** 책상·물건 위주 + 한 장면은 얼굴없는 사람(손글씨/뒷모습/오버숄더)
    - 크로스페이드 다중장면 → 60초 단조로움·3~9초 이탈 완화
    - seed: 영상별 고유 → 반복 제거 / 캐시로 재생성 방지
    """
    seed_val = int(seed) % 1_000_000 if seed is not None else 0
    topic_key, scene_prompt = _match_topic(script)
    n = max(1, min(int(scenes), 4))

    key = hashlib.sha256(
        f"{topic_key}|seed={seed_val}|n={n}|pool_v6".encode()).hexdigest()[:14]
    vid_path = cache_dir / f"aibg_{key}_multi.mp4"
    if vid_path.exists() and vid_path.stat().st_size > 200_000:
        return vid_path

    cache_dir.mkdir(parents=True, exist_ok=True)

    # 1) 사전생성 풀 우선 (Pollinations 무호출 → 렌더 안정)
    imgs = _pick_from_pool(topic_key, seed_val, n)
    if imgs:
        log.info("bg 풀 사용: topic=%s, %d장", topic_key, len(imgs))
        return _build_multiscene(imgs, duration, vid_path, ffmpeg_bin)

    # 2) 풀 부족 → Pollinations 라이브 생성 (기존 폴백)
    log.info("bg 풀 없음(topic=%s) → 라이브 생성 시도", topic_key)
    person_slot = 1 if n >= 3 else -1
    imgs = []
    for i in range(n):
        s = (seed_val * 10 + i) % 1_000_000
        if i == person_slot:
            prompt = _person_prompt(seed_val + i)
        else:
            setting = _KR_SETTINGS[s % len(_KR_SETTINGS)]
            prompt = _object_prompt(scene_prompt, setting)
        if i > 0:
            time.sleep(1.5)      # 요청 간 간격 — 연속 요청 실패율 완화
        img = _fetch_image(prompt, cache_dir / f"aibg_{key}_{i}.jpg",
                           seed=s, timeout_sec=timeout_sec)
        if img:
            imgs.append(img)
    if not imgs:
        return None
    if len(imgs) < n:
        log.warning("일부 장면 생성 실패: %d/%d (나머지는 성공분으로 구성)", len(imgs), n)

    return _build_multiscene(imgs, duration, vid_path, ffmpeg_bin)
