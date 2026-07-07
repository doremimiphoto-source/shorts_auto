# 서비스 격리 설계서 — 카드 시스템 ⊥ 쇼츠 시스템
**문서 유형**: 격리 설계서 (Isolation Design)
**버전**: v1.0
**작성일**: 2026-06-29
**상태**: 🟢 검증 완료
**요구사항**: 카드 시스템은 기존 쇼츠 영상 생성 모듈과 **완전 분리**, 쇼츠에 **영향 없이** 별도 서비스로 운영

---

## 변경 이력

| 버전 | 날짜 | 내용 |
|------|------|------|
| v1.0 | 2026-06-29 | 분리 위반 2건 발견 → 공유파일 복원 + cards/ 패키지로 전면 격리 |

---

## 1. 발견된 분리 위반 (수정 전)

| # | 위반 | 영향 | 조치 |
|---|------|------|------|
| V-01 | `src/renderer/bg_generator.py` 수정 (카드 프롬프트 3개 + generate_bg_image) | 쇼츠 `render_stage.py`가 이 파일 import → 배경 선택 오염 위험 | `git checkout` 원본 복원 → `cards/bg.py` 신규 분리 |
| V-02 | `src/config.py` Secrets 에 카드 필드 추가 | 쇼츠 db/main/context가 import | `git checkout` 원본 복원 → `cards/config.py` CardSecrets 분리 |
| V-03 | 카드 모듈을 쇼츠 트리(`src/renderer`, `src/affiliate`)에 배치 | 디렉토리 혼재 | 전부 `cards/` 패키지로 이동 |

---

## 2. 격리 원칙 (확정)

```
원칙 1: cards/ 는 src/ 를 일절 import 하지 않는다.        (zero 코드 결합)
원칙 2: cards/ 는 src/ 파일을 절대 수정하지 않는다.       (쇼츠 무영향)
원칙 3: 런타임 자원을 물리적으로 분리한다.                (DB·출력·스케줄·프로세스)
원칙 4: 공유는 '파일시스템 공존'까지만 허용한다.          (.env·폰트·venv 읽기전용)
```

---

## 3. 검증 결과 (자동 확인됨)

| 검증 | 명령 | 결과 |
|------|------|------|
| cards → src import | `grep "from src" cards/` | ✅ **0건** |
| src → cards import | `grep "from cards" src/ bot/` | ✅ **0건** |
| 쇼츠 모듈 import 정상 | `import src.main` | ✅ 정상 |
| 쇼츠 Secrets 무오염 | `pinterest_*` 필드 부재 | ✅ 확인 (False) |
| 카드 독립 동작 | `import cards.*` | ✅ 정상 |
| 렌더러 이동 후 작동 | `python -m cards.renderer` | ✅ 7슬라이드 생성 |

---

## 4. 자원 분리 매트릭스

| 자원 | 쇼츠 | 카드 | 분리 방식 |
|------|------|------|----------|
| **코드 패키지** | `src/`, `bot/` | `cards/` | 디렉토리 완전 분리, 상호 import 0 |
| **DB** | `data/shorts.db` | `data/cards.db` | 물리적 별도 파일 |
| **DB 래퍼** | `src/db.py` (Database) | `cards/db.py` (CardsDB) | 클래스 자체 분리 (코드 복제 ~40줄) |
| **설정/시크릿** | `src/config.py` (Secrets) | `cards/config.py` (CardSecrets) | BaseSettings 클래스 분리, 동일 .env 읽기 |
| **LLM 호출** | `src/rewriter/` (RewriterChain) | `cards/llm.py` (예정) | 추상화 분리, SDK 직접 호출 |
| **배경 생성** | `src/renderer/bg_generator.py` | `cards/bg.py` | 함수 분리 (Pollinations 독립 구현) |
| **렌더러** | `src/renderer/card_renderer.py` (1080×1920, Pretendard) | `cards/renderer.py` (3비율, Poppins/Inter) | 모듈 분리, 프리미티브 복제 |
| **출력** | `output/` | `output/cards/` | 하위 디렉토리 분리 |
| **스케줄러** | `data/task_ShortsAuto_*.xml` | `data/task_Card_*.xml` (예정) | 별도 launchd job |
| **로그** | `logs/` (쇼츠) | `logs/cards_*` (예정) | 파일 분리 |
| **폰트** | Pretendard (한국어) | Poppins/Inter (영어) | 동일 디렉토리, 다른 파일 (읽기전용) |
| **.env** | 쇼츠 키 | 카드 키 | 동일 파일, 키 네임스페이스 분리, extra='ignore' |
| **Python venv** | `.venv/` 공유 | `.venv/` 공유 | 라이브러리 공유 (읽기전용, 영향 없음) |

---

## 5. 공유 자원의 안전성 분석

### 5-1. .env 파일 공유 — 안전 ✅
- 쇼츠 `Secrets` 와 카드 `CardSecrets` 는 **서로 다른 클래스**, 동일 `.env` 파일을 독립적으로 읽음
- 양쪽 모두 `extra='ignore'` → 상대 키를 무시
- groq/gemini 키는 양쪽이 **읽기만** 공유 → 쇼츠 동작 불변

### 5-2. 폰트 디렉토리 공유 — 안전 ✅
- 쇼츠는 Pretendard만, 카드는 Poppins/Inter만 로드
- 동일 디렉토리의 **다른 파일** → 충돌 없음

### 5-3. Python venv 공유 — 안전 ✅
- Pillow/numpy/pydantic 등 라이브러리 읽기 공유
- 카드가 새 패키지 추가 시(예: google-genai는 이미 설치됨) 쇼츠에 영향 없음 (추가만, 버전 변경 금지)

> ⚠️ **유일한 주의**: venv에 라이브러리 **버전을 변경/다운그레이드하지 말 것**. 추가(install)만 허용. 쇼츠가 쓰는 패키지 버전을 바꾸면 영향 발생.

---

## 6. 프로세스 격리 (런타임)

```
쇼츠 서비스:
  launchd: task_ShortsAuto_0700/1530/1800/2200
  진입점:  python -m src.main
  락:      data/pipeline.lock
  킬스위치: data/killswitch.flag

카드 서비스 (독립):
  launchd: task_Card_Pinterest_* / task_Card_Instagram_* (예정)
  진입점:  python -m cards.main (예정)
  락:      data/cards.lock (예정, 별도)
  킬스위치: data/cards_killswitch.flag (예정, 별도)
```

→ 두 서비스는 **다른 시각, 다른 프로세스**로 실행. 동시 실행돼도 자원 충돌 없음.

---

## 7. 최종 패키지 구조

```
shorts_auto/
├── src/              ← 쇼츠 서비스 (불변, 카드가 건드리지 않음)
│   ├── main.py
│   ├── config.py     (Secrets — 카드 필드 없음, 원본)
│   ├── db.py         (Database)
│   ├── renderer/
│   │   ├── card_renderer.py    (쇼츠 전용, 1080×1920)
│   │   └── bg_generator.py     (원본 복원됨)
│   ├── rewriter/ crawler/ uploader/ ...
│   └── ...
│
├── cards/            ← 카드 서비스 (별도, src 무의존)
│   ├── __init__.py
│   ├── config.py     (CardSecrets + 상수)
│   ├── db.py         (CardsDB — 자체 SQLite 래퍼)
│   ├── schema.sql    (cards.db 스키마)
│   ├── bg.py         (Pollinations 독립)
│   ├── renderer.py   (3비율 캐러셀, Poppins/Inter)
│   ├── llm.py        (예정 — Groq/Gemini SDK 직접)
│   ├── main.py       (예정 — 파이프라인)
│   ├── crawler/      (예정 — travel/aliexpress/kbeauty)
│   ├── uploader/     (예정 — pinterest/instagram/tiktok/imgur)
│   └── affiliate/    (예정 — links)
│
├── data/
│   ├── shorts.db     (쇼츠)
│   └── cards.db      (카드)
│
└── output/
    ├── (쇼츠 영상)
    └── cards/        (카드 이미지)
```

---

## 8. 종합 판정

| 항목 | 판정 |
|------|------|
| 쇼츠 공유 파일 오염 | ✅ 전부 원본 복원 (git checkout) |
| cards → src 코드 결합 | ✅ 0건 (완전 독립) |
| 쇼츠 영향 가능성 | ✅ 없음 (검증 완료) |
| 별도 서비스 운영 | ✅ 가능 (DB·설정·프로세스·스케줄 분리) |
| 유일 제약 | venv 라이브러리 버전 변경 금지 (추가만 허용) |

---

*카드 시스템은 쇼츠와 코드/데이터/프로세스가 완전 분리된 별도 서비스로 확정.*
