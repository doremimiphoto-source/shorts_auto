# Changelog

본 문서는 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) 형식을 따르며,
프로젝트는 [Semantic Versioning](https://semver.org/spec/v2.0.0.html)을 준수한다.

> 요구정의서(`REQUIREMENTS.md`) 자체의 버전 변경은 본 문서에 기록하고,
> 일자별 작업 진행 상세는 `WORKLOG.md`에서 관리한다.

---

## [Unreleased]

### Added
- **시스템 도구 설치**: FFmpeg 8.1, Microsoft VC++ 2022 Redist 14.50, Ollama 0.21.2 (winget user scope)
- **프로젝트 스켈레톤 루트 파일**: `.gitignore`, `.env.example`, `config.yaml.example`, `requirements.txt`, `pyproject.toml`, `README.md`
- **디렉토리 구조**: `src/{crawler,rewriter,tts,subtitle,renderer,uploader,utils,notify}/`, `assets/`, `output/`, `logs/`, `data/`, `models/`, `credentials/`, `prompts/`, `tests/`, `scripts/`
- **DB 스키마** (`src/db_schema.sql`): sources, scripts, videos, uploads, job_logs, asset_usage, api_usage, compliance_checks, daily_kpi (총 9개 테이블)
- **핵심 모듈**:
  - `src/config.py`: pydantic-settings 기반 통합 설정 로더 (`.env` + `config.yaml`)
  - `src/db.py`: SQLite WAL 래퍼 (트랜잭션, 백업)
  - `src/utils/logging.py`: structlog JSON Lines + PII 마스킹 (Bearer/refresh_token/이메일/AIza/gsk 패턴)
  - `src/utils/lock.py`: 파일 락 + stale 회수 (Windows PID 검사 포함)
  - `src/utils/similarity.py`: SHA-256 + ko-sroberta 임베딩 + 코사인 유사도
- **파이프라인 모듈 스켈레톤**:
  - `src/crawler/`: SourceCrawler 인터페이스 + LLMCreatorCrawler(구현) + RedditCrawler(스켈레톤)
  - `src/rewriter/`: Rewriter 인터페이스 + Gemini/Groq/Ollama 클라이언트 + RewriterChain (폴백 체인)
  - `src/tts/`: TTSEngine 인터페이스 + PiperEngine(구현) + EdgeEngine(스켈레톤) + SpeakerSelector(결정론적 선택)
  - `src/subtitle/`: WhisperSubtitleEngine (CPU int8, 한국어 줄바꿈)
  - `src/renderer/`: AssetSelector + VideoComposer (FFmpeg `-filter_complex`)
  - `src/uploader/`: YouTubeUploader (OAuth2 + Resumable Upload), StudioUIAutomation(스켈레톤)
  - `src/notify/`: DiscordNotifier
- **오케스트레이터** (`src/main.py`): argparse, Kill-Switch 검사, Lock 획득, DB 초기화, `--dry-run` 의존성 점검 모드
- **프롬프트 템플릿**: `prompts/story_rewrite.txt`, `prompts/block_keywords.txt`, `prompts/upload_description.txt`
- **에셋 메타데이터**: `assets/bg_video/_metadata.json`, `assets/bgm/_metadata.json`
- **Python 가상환경 + 의존성**: `.venv/` (Python 3.12.4) — pip 26.1, 56개 직간접 의존성 설치 완료
- **Playwright Chromium**: 1208 + headless shell + ffmpeg + winldd
- **단위 테스트** (`tests/`): 45개 테스트 (config, db, lock, logging, similarity, speaker_selector) — **전체 통과**

### Verified
- `python -m src.main --dry-run` 정상 동작 — DB 자동 생성, 9개 테이블, JSON Lines 로그 UTF-8
- 모든 모듈 임포트 가능 (config, db, main, utils, crawler, rewriter, tts, subtitle, renderer, uploader, notify)
- 단위 테스트 **73/73 통과**

### Added (Day 3)
- **Repository 계층** (`src/repository.py`): Source/Script/Video/Upload/JobLog/AssetUsage/ApiUsage Repository — SQL 캡슐화
- **유틸 보강**:
  - `src/utils/content_filter.py`: drop/mask 모드 콘텐츠 필터 (FR-2.5)
  - `src/utils/hook_pattern.py`: 직전 N개 차단 + 결정론적 hook 선택 (FR-2.7)
  - `src/utils/retry.py`: tenacity 기반 지수 백오프 헬퍼
- **파이프라인 단계 함수** (`src/pipeline/`):
  - `context.py`: PipelineContext + stage_timer (job_logs 자동 기록)
  - `crawl_stage`, `rewrite_stage`, `tts_stage`, `subtitle_stage`, `render_stage`, `upload_stage`
  - StageSkipped / StageError 예외 분리
- **main.py 채우기**: 단계 체인 + 예외별 처리 + Discord 알림 + `--skip-upload` 옵션
- **에셋 자동 수집기** (`scripts/fetch_assets.py`): Pexels Videos + Pixabay Music API
- **추가 테스트**: content_filter, hook_pattern, repository, pipeline_context (총 28개 추가)

### Fixed (Day 3)
- `stage_timer`의 성공 경로에서 status가 "running"으로 잘못 기록되던 버그

### Added (Day 4 — BGM 수집 전략 재설계)
- **MusicGen 엔진** (`src/audio/musicgen_engine.py`): Apache 2.0 모델 기반 오프라인 BGM 풀 생성기. 무드별 프롬프트 풀(tension/sad/calm/twist) 내장.
- **Internet Archive Audio API 통합** (`scripts/fetch_assets.py` 의 `fetch_bgm_internet_archive`): Public Domain 필터 자동 다운로드.
- **`scripts/verify_keys.py`**: Gemini/Groq/Pexels/Pixabay/Discord/YouTube OAuth 라이브 호출 검증 도구.
- **테스트**: `test_fetch_assets.py`(IA fetcher mock), `test_musicgen_engine.py`(model mock) — 누적 **83/83 통과**.

### Changed (Day 4)
- **FR-5.5 재정의**: BGM 수집을 3-Tier Hybrid로 — ① MusicGen (Apache 2.0, AI 생성), ② Internet Archive (PD), ③ YouTube 오디오 라이브러리 (수동 백업).
- **`config.yaml.example`** `renderer.bgm.pool_strategy` 섹션 신설.
- **`scripts/fetch_assets.py`** CLI 변경: `bg | bgm | all` → `bg | bgm-musicgen | bgm-ia | all`.

### Removed (Day 4)
- **Pixabay Music API 의존 제거**: Pixabay 공식 API는 Photos/Videos만 지원 — Music 엔드포인트는 404. 라이브 호출 검증 후 확인됨.

### Verified (Day 4)
- 6종 API 키 라이브 호출 검증 통과 (Gemini, Groq, Pexels, Pixabay-Images, Discord Webhook 메시지 송출, YouTube OAuth client_secret.json 발견).

### Added (Day 5 — MeloTTS 한국어 전환 + 의존성 해소)
- **MeloTTS-Korean 설치** (MIT 라이센스): GitHub 클론 + fugashi 버전 핀 완화(`>=1.3.0`) + editable install. 누적 의존성: torch 2.11, torchaudio, mecab-python3, fugashi, g2pkk, pykakasi, soxr.
- **eunjeon no-op 스텁 고도화** (`src/tts/melo_engine.py`): `importlib.machinery.ModuleSpec` 을 `__spec__`에 주입 → `importlib.util.find_spec("eunjeon")` ValueError 해소.
- **unidic v3.1.0 사전** (~526MB): `python -m unidic download` 완료. MeCab 일본어 분석기 필수 데이터.
- **soxr 1.0.0**: transformers 5.x 오디오 처리 의존성.

### Fixed (Day 5)
- `melo_engine.py` 구조 버그: `synthesize()` 메서드가 `_patch_g2pkk_for_windows()` 함수 내부에 중첩돼 `MeloEngine`에서 호출 불가했던 문제 수정 (메서드 들여쓰기 재배치).
- `eunjeon` 스텁에 `__spec__ = None`이어서 `g2pkk.check_mecab()` → `importlib.util.find_spec()` 에서 `ValueError` 발생하던 버그 수정.

### Verified (Day 5)
- **MeloTTS 한국어 스모크 테스트 5종 통과**: kr_soft_default(140s/초회·BERT 다운로드 포함), kr_soft_slow(2.7s), kr_soft_normal(2.6s), kr_soft_brisk(2.6s), kr_soft_calm(2.8s). 평균 각 ~2~3s/문장.
- **`python -m src.main --dry-run` → ok=true, issue_count=0** (MeloTTS import 포함 전 의존성 통과).
- **단위 테스트 95/95 통과** (pytest 9.0.3).

---

## [1.0.0] - 2026-04-29

요구정의서 최종 승인 + 운영 환경(GPU 미보유) 반영 확정.

### Changed
- **LLM 주력 전환**: Ollama 로컬 LLM(Gemma 9B/Qwen 7B) → Gemini 2.5 Flash 무료 API로 변경
  - 사유: GPU 미보유 환경에서 로컬 LLM은 CPU 추론 시 8B 이상 모델 실용성 낮음
  - 폴백 체인 재배치: ① Gemini Flash → ② Groq Llama 3.1 8B → ③ Ollama Gemma 2 2B (CPU 비상용)
- **STT 모델 다운그레이드**: faster-whisper large-v3 → small (CPU int8)
  - 사유: GPU 없이 large-v3는 60초 오디오에 수 분 소요로 비실용적
- **성능 목표 조정** (§3.1): 1영상 end-to-end 5분 → 8~10분
- **기술 스택 표 재배치** (§4.2): GPU 미보유 기준으로 우선순위 재정의
- **하드웨어 요구사항** (§8.1): GPU "선택" → "불필요"
- **운영비 재산정** (§13.1): 전기료 ₩15,000/월 → ₩5,000/월 (CPU only 60W 기준)
- **컴포넌트 다이어그램** (§4.1): LLM/TTS/STT 노드 라벨 갱신

### Fixed
- 디렉토리 경로 표기 오류 (§7): `d:\Application\Codex\shorts_auto\` → `d:\Application\Claude\shorts_auto\`

### Added
- `docs/CHANGELOG.md` 신규 생성 (본 문서)
- `docs/WORKLOG.md` 신규 생성 (작업 일지)
- `docs/SETUP.md` 신규 생성 (사전 준비 가이드)
- §3.1 성능 표에 "인터넷 의존도" 행 추가
- §8.1 하드웨어 표에 "인터넷" 행 추가
- §8.2 사전 설치에 Visual C++ Redistributable 추가 (Whisper 의존성)

---

## [0.2.0-review] - 2026-04-28

정책 리스크 외부 검토 반영.

### Changed
- FR-1 소재 수집: 라이선스 클린 소스 우선순위 도입 (LLM 창작 → Reddit CC-BY → 공공도메인 → 모티프 추출)
- FR-2 LLM: 14B → 9B/7B 다운그레이드 + 유사도 3중 검증 신설
- FR-3 TTS: edge-tts 주력 → Piper TTS 주력으로 변경
- FR-5 영상 합성: MoviePy 주력 → FFmpeg `filter_complex` 직접 호출
- FR-6.8 AI 공시: 설명/태그/Studio UI 3중 적용으로 강화

### Added
- §3.5 법적·정책 준수 체크리스트
- §10.2 운영·인프라 리스크 A1~A12
- §12 운영 Kill-Switch
- §13 운영비 재산정

---

## [0.1.0-draft] - 2026-04-21

요구정의서 초안 작성.

### Added
- 프로젝트 개요, KPI, 범위 정의
- FR-1 ~ FR-8 기능 요구사항
- §3 비기능 요구사항
- §4 시스템 아키텍처
- §5 데이터 모델 (SQLite 스키마)
- §6 절차 Flow (Mermaid 다이어그램)
- §7 디렉토리 구조
- §8 환경 구성
- §9 4주 마일스톤
- §10 리스크 R1~R9

---

## 작성 규칙

- **Added**: 신규 추가된 기능/문서/항목
- **Changed**: 기존 항목의 변경
- **Deprecated**: 곧 제거될 항목
- **Removed**: 제거된 항목
- **Fixed**: 버그/오류 수정
- **Security**: 보안 관련 변경
- 각 변경은 가능하면 **사유(Why)**를 함께 기록한다.
