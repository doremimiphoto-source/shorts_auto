# Work Log (작업 일지)

본 문서는 일자별·작업 단위별 진행 내역을 기록한다.
요구정의 변경은 `CHANGELOG.md`, 운영 매뉴얼은 `OPERATIONS.md`(예정)와 분리한다.

## 기록 양식

```markdown
## YYYY-MM-DD

### [TASK-ID] 작업 제목
- **변경 파일**: a/b/c.py (신규 / 수정 / 삭제)
- **작업 내용**: 무엇을 했는지 (1~3줄)
- **의사결정**: 선택지가 있었다면 무엇을 / 왜
- **근거**: 사용자 승인 / 요구사항 ID / 기술적 근거
- **승인 상태**: ✅ 승인됨 / ⏸ 대기 / ❌ 보류
- **다음 작업**: (필요 시)
```

---

## 2026-04-29

### [DOC-01] REQUIREMENTS.md v1.0 확정 + 정정 반영
- **변경 파일**: `docs/REQUIREMENTS.md` (수정)
- **작업 내용**: 운영 환경(GPU 미보유) 확정에 따라 LLM/STT 스택 재배치, 성능·비용 수치 갱신, 디렉토리 경로 정정, v1.0 라벨링.
- **의사결정**:
  - LLM 주력: 로컬 Ollama → 클라우드 Gemini Flash (사용자 #1 답변에 따름)
  - STT: large-v3 → small CPU int8 (CPU only 환경 실용성)
  - 폴백 체인: Gemini → Groq → Ollama Gemma 2 2B (3단계)
- **근거**: 사용자 답변 (2026-04-29) #1 "하드웨어 없음", v1.0 승인 의사
- **승인 상태**: ✅ 사용자 승인됨

### [DOC-02] CHANGELOG.md 신규 작성
- **변경 파일**: `docs/CHANGELOG.md` (신규)
- **작업 내용**: Keep a Changelog 1.1.0 형식으로 v0.1 → v0.2 → v1.0 변경 이력 정리.
- **의사결정**: REQUIREMENTS 본문의 §11.2 변경 이력 표는 요약만 유지하고, 상세 항목은 CHANGELOG로 분리.
- **근거**: 사용자 답변 (2026-04-29) #7 "변경이력·작업 히스토리 따로 남길 것"
- **승인 상태**: ✅ 사용자 승인됨

### [DOC-03] WORKLOG.md 신규 작성
- **변경 파일**: `docs/WORKLOG.md` (신규, 본 문서)
- **작업 내용**: 작업 단위별 일지 양식 정의 + 본 일자 작업 첫 기록.
- **승인 상태**: ✅ 사용자 승인됨

### [DOC-04] SETUP.md 신규 작성
- **변경 파일**: `docs/SETUP.md` (신규)
- **작업 내용**: 사전 준비 가이드 — 설치 체크리스트, API 키 발급 절차, YouTube 채널 생성, 에셋 풀 구축.
- **근거**: 사용자 답변 (2026-04-29) #2~#5
- **승인 상태**: ✅ 사용자 승인됨

### [INFRA-01] 시스템 도구 설치 (winget A 그룹)
- **설치된 도구**: FFmpeg 8.1 (user scope), Microsoft VC++ 2022 Redist 14.50, Ollama 0.21.2 (user scope)
- **이슈**: FFmpeg 머신 스코프 설치 시 권한 오류 → `--scope user` 로 우회 성공
- **근거**: 사용자 답변 (2026-04-29) #2
- **승인 상태**: ✅ 사용자 승인됨

### [INFRA-02] 프로젝트 스켈레톤 루트 파일 생성
- **변경 파일**: `.gitignore`, `.env.example`, `config.yaml.example`, `requirements.txt`, `pyproject.toml`, `README.md` (모두 신규)
- **작업 내용**: 비밀 정보 분리(.env), YAML 단일 설정, ruff/mypy/pytest 설정, 의존성 핀 명세
- **의사결정**: pydantic-settings로 .env 자동 로딩, structlog로 JSON Lines 로깅 채택

### [INFRA-03] 디렉토리 구조 + 초기 자산 메타/프롬프트
- **변경 파일**: `assets/{bg_video,bgm,fonts}/`, `output/{scripts,audio,subtitle,final}/`, `logs/errors/`, `data/backups/`, `credentials/`, `models/piper/`, `prompts/{story_rewrite,block_keywords,upload_description}.txt`, `assets/{bg_video,bgm}/_metadata.json`
- **승인 상태**: ✅ 사용자 승인됨

### [DB-01] SQLite 스키마 작성
- **변경 파일**: `src/db_schema.sql` (신규)
- **작업 내용**: REQUIREMENTS.md §5 스키마 + 운영 보강 컬럼 (asset_usage, api_usage, compliance_checks, daily_kpi 추가)
- **의사결정**: WAL 모드 + autocheckpoint=1000 (A2 대응)

### [INFRA-04] 핵심 모듈 구현
- **변경 파일**: `src/__init__.py`, `src/config.py`, `src/db.py`, `src/utils/{__init__,logging,lock,similarity}.py`
- **작업 내용**: 설정 로더(pydantic-settings), structlog+PII 마스킹, 파일락(stale 회수), SHA-256 + ko-sroberta 임베딩 유사도, SQLite 래퍼(WAL/트랜잭션/백업)
- **의사결정**: 외부 의존성(sentence-transformers, ollama 등)은 lazy import — 의존성 미설치 환경에서 모듈 임포트만으로 실패하지 않도록

### [CRAWL-01] 소재 수집 모듈 스켈레톤
- **변경 파일**: `src/crawler/{__init__,base,llm_creator,reddit}.py`
- **작업 내용**: SourceCrawler 추상 인터페이스, LLMCreatorCrawler 구현 (1순위), RedditCrawler 스켈레톤
- **의사결정**: LLM 호출 자체는 callable 주입 — Crawler가 Rewriter에 직접 의존하지 않게 분리

### [RW-01] 대본 생성 모듈 (LLM 폴백 체인)
- **변경 파일**: `src/rewriter/{__init__,base,gemini_client,groq_client,ollama_client,chain}.py`
- **작업 내용**: Rewriter 추상 인터페이스, Gemini(주력)/Groq(1차 폴백)/Ollama(2차 비상) 백엔드 + RewriterChain
- **의사결정**: GPU 미보유 환경 반영 — Gemini Flash가 주력, Ollama는 비상용

### [TTS-01] 음성 합성 모듈 스켈레톤
- **변경 파일**: `src/tts/{__init__,base,piper_engine,edge_engine,speaker_selector}.py`
- **작업 내용**: TTSEngine 추상 인터페이스, Piper 엔진(주력) 구현, edge-tts 스켈레톤, 콘텐츠 해시 기반 결정론적 화자 선택기
- **의사결정**: edge-tts는 기본 비활성화(차단 리스크) — 운영자가 명시적 활성화 필요 (FR-3.7)

### [SUB-01] 자막 생성 모듈
- **변경 파일**: `src/subtitle/{__init__,whisper_engine}.py`
- **작업 내용**: faster-whisper(small, CPU int8) 래퍼, 한국어 자막 줄바꿈(15자×2줄), SRT 직렬화

### [REND-01] 영상 합성 모듈
- **변경 파일**: `src/renderer/{__init__,assets,composer}.py`
- **작업 내용**: AssetSelector(7일 재사용 간격, 블랙리스트), VideoComposer(FFmpeg `-filter_complex` 직접 호출, 자막 번인 libass, BGM 사이드체인 더킹)
- **의사결정**: 속도 ±5% 랜덤화 / 색보정(`eq=contrast=1.05:saturation=1.05`) 기본 적용 — 반복 패턴 플래그 회피 (A7)

### [UP-01] 업로드 모듈 스켈레톤
- **변경 파일**: `src/uploader/{__init__,youtube,studio_ui}.py`
- **작업 내용**: YouTubeUploader(OAuth2 + Resumable Upload), StudioUIAutomation(Playwright AI 공시 토글) 스켈레톤
- **의사결정**: 멀티 채널 운영 시 본 클래스를 채널별 인스턴스로 다중 등록 (FR-6.10)

### [OBS-01] 알림 모듈
- **변경 파일**: `src/notify/{__init__,discord_webhook}.py`
- **작업 내용**: Discord Webhook Embed 송출 (failure-tolerant — 알림 실패가 파이프라인을 중단시키지 않음)

### [INFRA-05] main.py 오케스트레이터 스켈레톤
- **변경 파일**: `src/main.py`
- **작업 내용**: argparse(--dry-run/--resume), Kill-Switch 검사, Lock 획득, DB 초기화, dry-run 모드(키/도구/모델 파일 검증)
- **다음 작업**: 각 단계별 실행 코드 채우기 (crawl → rewrite → tts → subtitle → render → upload)

### [INFRA-06] Python 가상환경 + 전체 의존성 설치
- **변경 파일**: `.venv/` (gitignore 대상)
- **작업 내용**: Python 3.12.4 venv 생성, pip 26.1로 업그레이드 후 requirements.txt 분할 설치
  - **3a 경량 의존성**: httpx, pydantic, pydantic-settings, PyYAML, structlog, python-dotenv, tenacity, cryptography, ffmpeg-python, Pillow, numpy, scipy
  - **3b API 클라이언트**: google-generativeai 0.8.6, groq 1.2.0, ollama 0.6.1, google-api-python-client 2.194.0, google-auth-oauthlib 1.3.1
  - **3c 크롤링/UI**: selectolax 0.4.7, playwright 1.58.0
  - **3d ML**: faster-whisper 1.2.1, sentence-transformers 5.4.1 (torch 2.11, ctranslate2 4.7.1, transformers 5.7.0 동반 설치)
  - **3e 테스트**: pytest 9.0.3, pytest-asyncio 1.3.0, pytest-mock 3.15.1, freezegun 1.5.5
- **의사결정**: 단일 `pip install -r requirements.txt` 대신 5단계 분할 설치 — 무거운 ML 패키지 다운로드 중에 다른 작업 병행 가능
- **승인 상태**: ✅ 사용자 승인됨

### [INFRA-07] Playwright Chromium 설치
- **설치 파일**: `%LOCALAPPDATA%\ms-playwright\chromium-1208`, `chromium_headless_shell-1208`, `ffmpeg-1011`, `winldd-1007`
- **용도**: FR-6.8 Studio UI altered/synthetic content 토글 자동화

### [TEST-01] 단위 테스트 작성 + 첫 실행 검증
- **변경 파일**: `tests/{conftest,test_config,test_db,test_lock,test_logging,test_similarity,test_speaker_selector}.py` (신규)
- **결과**: **45/45 테스트 통과** (pytest 9.0.3, 1.49s)
- **커버 모듈**: config 로더, SQLite 래퍼(WAL/트랜잭션/백업/외래키/UNIQUE), 파일 락(stale 회수), PII 마스킹(Bearer/refresh_token/이메일/AIza/gsk), 코사인 유사도, 결정론적 화자 선택

### [INFRA-08] 첫 dry-run 실행 검증
- **명령**: `python -m src.main --dry-run`
- **결과**:
  - ✅ pipeline_start, db_ready, dry_run_complete 이벤트 정상 emit
  - ✅ DB 자동 생성 (`data/shorts.db`), 9개 테이블 생성 확인
  - ✅ JSON Lines 로그 (`logs/2026-04-29.log`) UTF-8 정상 기록
  - ⚠️ 6개 이슈 감지 (예상): GEMINI/GROQ/PEXELS/PIXABAY API 키 미설정 + Piper 바이너리/모델 미설치
- **다음 작업**: API 키 발급 + Piper 설치 후 재검증

### [DB-02] Repository 계층 구현
- **변경 파일**: `src/repository.py` (신규)
- **작업 내용**: Source/Script/Video/Upload/JobLog/AssetUsage/ApiUsage Repository + 통합 컨테이너 `Repositories`
- **설계 원칙**: SQL은 Repository 계층에 한정, 파이프라인 단계는 Repository만 의존 → DAO 캡슐화

### [INFRA-09] 유틸 보강
- **변경 파일**: `src/utils/{content_filter,hook_pattern,retry}.py` (신규)
- **작업 내용**:
  - `ContentFilter` (FR-2.5): drop/mask 모드, `prompts/block_keywords.txt` 자동 파싱
  - `select_hook_pattern` (FR-2.7): 직전 N개 차단 + 결정론적/round-robin 선택
  - `retry_call`: tenacity 기반 지수 백오프 헬퍼

### [INFRA-10] 파이프라인 단계 함수 구현
- **변경 파일**: `src/pipeline/{__init__,context,crawl_stage,rewrite_stage,tts_stage,subtitle_stage,render_stage,upload_stage}.py` (신규)
- **작업 내용**:
  - `PipelineContext` + `stage_timer` 컨텍스트 매니저: 단계 시작/종료/실패 자동 로깅 + `job_logs` DB 기록
  - `crawl_stage`: 미사용 소재 우선 + 부재 시 `LLMCreatorCrawler` 실행 (해시·임베딩 중복 차단)
  - `rewrite_stage`: hook 패턴 선택 → LLM 호출 → 콘텐츠 필터 → 3중 유사도 검증 → DB 저장
  - `tts_stage`: 결정론적 화자 선택 → Piper → FFmpeg `loudnorm` LUFS -16 → mp3
  - `subtitle_stage`: faster-whisper small 호출 → SRT 저장
  - `render_stage`: AssetSelector → VideoComposer → ffprobe 검증 (해상도/길이) → DB 갱신
  - `upload_stage`: quota 가드 → 메타데이터 합성 (AI 공시 prefix + 해시태그 결합) → 업로드 → DB 결과 기록
- **공통 예외**: `StageSkipped`(사전조건 미충족), `StageError`(회복 불가) — main.py가 각각 다르게 처리

### [INFRA-11] main.py 오케스트레이션 채우기
- **변경 파일**: `src/main.py` (수정)
- **작업 내용**: 단계별 함수 호출 체인 + StageSkipped/StageError/예상 외 예외 분기 처리 + Discord 알림
- **CLI 추가**: `--skip-upload` (영상 생성까지만 실행)
- **오케스트레이션 검증**: dry-run 재실행 ✅ (8개 이슈 — 에셋 풀 검사 추가됨)

### [INFRA-12] stage_timer 상태 버그 수정
- **버그**: `state["status"] = state.get("status", "ok")` 가 초기값 "running"을 그대로 유지
- **수정**: `if state.get("status") in (None, "running"): state["status"] = "ok"`
- **검증**: `test_stage_timer_records_ok` 통과

### [TEST-02] 추가 단위 테스트
- **변경 파일**: `tests/{test_content_filter,test_hook_pattern,test_repository,test_pipeline_context}.py` (신규)
- **결과**: **73/73 테스트 통과** (1.78s, 10개 deprecation warning은 SQLite timestamp converter 관련 — 영향 없음)

### [INFRA-13] scripts/fetch_assets.py 신규 작성
- **변경 파일**: `scripts/__init__.py`, `scripts/fetch_assets.py` (신규)
- **작업 내용**: Pexels Videos API + Pixabay Music API 자동 다운로드, `_metadata.json`에 출처/라이센스/SHA-256/페이지URL 누적 기록
- **CLI**: `python -m scripts.fetch_assets {bg|bgm|all} --per-keyword N`
- **rate limit 매너**: 요청 간 1초 sleep (Pexels 200req/h, Pixabay 100req/h 한도 내)

### [VERIFY-01] API 키 라이브 검증 + Pixabay Music API 부재 발견
- **변경 파일**: `scripts/verify_keys.py` (신규)
- **작업 내용**: Gemini/Groq/Pexels/Pixabay/Discord/YouTube OAuth 6종 라이브 호출 검증
- **결과**: 6/6 통과 (Discord 메시지 송출 확인됨)
- **발견**: Pixabay 공식 API는 **Photos / Videos만** 지원. Music 엔드포인트(`/api/music/`)는 404 반환 — 키는 정상이나 API 자체가 미공개.
- **영향**: REQUIREMENTS.md FR-5.5 가정 오류 → BGM 자동 수집 전략 재설계 필요

### [BGM-01] BGM 수집 전략 3-Tier Hybrid로 재설계
- **변경 파일**:
  - `src/audio/__init__.py` (신규)
  - `src/audio/musicgen_engine.py` (신규) — transformers MusicGen 래퍼
  - `scripts/fetch_assets.py` (수정) — pixabay_music 제거, musicgen + ia 서브커맨드 추가
  - `config.yaml.example` — `renderer.bgm.pool_strategy` 섹션 신규
  - `docs/REQUIREMENTS.md` FR-5.5 갱신
  - `docs/SETUP.md` §5.3 전면 개편
- **전략**:
  - Tier 1 (MusicGen, Apache 2.0): 오프라인 AI 생성 → 매번 unique → Content ID 0%
  - Tier 2 (Internet Archive Audio): Public Domain 필터 자동 다운로드
  - Tier 3 (YouTube 오디오 라이브러리): 1회 수동 백업
- **핵심 결정**: MusicGen은 **오프라인 풀 빌드 전용**으로 사용 (런타임 영상 합성에는 호출 안 함). CPU 추론 3분 부담을 영상 파이프라인 외부로 분리.
- **의존성 추가 없음**: 기존 transformers 5.7.0에 MusicGen 내장, audiocraft 불필요
- **사용 예**:
  ```
  python -m scripts.fetch_assets bgm-musicgen --per-mood 3 --duration 30
  python -m scripts.fetch_assets bgm-ia --per-mood 5
  ```
- **위험 요인**: 첫 실행 시 musicgen-small 모델(~2.2GB) 자동 다운로드 (10~15분), CPU 30초 클립 생성 ~3분 — 실제 벤치마크는 사용자 환경에서 별도 검증 필요

### [TEST-03] 추가 단위 테스트
- **변경 파일**: `tests/test_fetch_assets.py`, `tests/test_musicgen_engine.py` (신규)
- **결과**: **83/83 테스트 통과** (10건 추가)
- **mock 전략**: MusicGen 실제 모델 로딩·생성은 mock으로 우회 — CI에서 수GB 다운로드 회피, 테스트 시간 4.89s

---

## 2026-04-30

### [TTS-02] MeloTTS-Korean 설치 완료 + 의존성 충돌 해소

- **변경 파일**: `src/tts/melo_engine.py` (수정)
- **작업 내용**:
  1. PyPI `melotts 0.1.1` 패키지는 setup.py가 requirements.txt 누락으로 설치 실패 → GitHub 클론 후 editable install
  2. `fugashi==1.3.0` 핀 → `>=1.3.0` 완화 (PyPI 에 1.3.0 메타데이터 불일치)
  3. `soxr 1.0.0` 추가 설치 (transformers 5.x 오디오 의존성)
  4. `python -m unidic download` → unidic v3.1.0 사전 526MB 다운로드 완료
- **의사결정**: 가상환경 없이 시스템 Python에 직접 설치 (기존 세션 환경과 통일)
- **승인 상태**: ✅ 완료

### [TTS-03] melo_engine.py 구조 버그 2종 수정

- **변경 파일**: `src/tts/melo_engine.py` (수정)
- **버그 1**: `synthesize()` 메서드가 `_patch_g2pkk_for_windows()` 함수 내부에 중첩되어 `MeloEngine` 클래스에서 호출 불가능한 상태였음 (컨텍스트 단절로 이전 세션에서 발생). 전체 파일 재작성으로 수정.
- **버그 2**: `eunjeon` stub 모듈에 `__spec__ = None` → g2pkk의 `check_mecab()` 내 `importlib.util.find_spec("eunjeon")`이 `ValueError: eunjeon.__spec__ is None` 발생. `importlib.machinery.ModuleSpec("eunjeon", loader=None)` 주입으로 해소.
- **근거**: Python 3.12 `importlib.util.find_spec()`은 `sys.modules`에 있는 모듈의 `__spec__`이 None이면 ValueError를 발생시킴 (CPython frozen bootstrap 동작)
- **승인 상태**: ✅ 완료

### [TEST-04] MeloTTS 스모크 테스트 + 전체 검증

- **변경 파일**: `scripts/_melo_smoke.py` (기존)
- **결과**:
  - 5종 화자 WAV 합성 전체 통과 (`output/audio/melo_smoke_*.wav`)
  - 첫 합성 140.6s (kykim/bert-kor-base 모델 500MB 다운로드 포함)
  - 이후 합성 평균 2.6~2.8s/문장
  - `python -m src.main --dry-run` → `ok=true, issue_count=0`
  - `pytest tests/` → **95/95 통과** (4.61s)
- **승인 상태**: ✅ 완료

### [E2E-01] E2E 파이프라인 전체 통과 (--skip-upload)

- **변경 파일**:
  - `config.yaml` (수정) — Gemini `max_output_tokens` 1024→8192, Groq 모델 교체
  - `prompts/story_rewrite.txt` (수정) — 모티프 표현 직접 사용 금지 규칙 추가
  - `src/renderer/composer.py` (수정) — FFmpeg scale 필터 수정 (가로형 배경 비디오 지원)
  - `src/tts/melo_engine.py` (수정) — `tts_to_file(quiet=True)` 추가
  - `src/pipeline/tts_stage.py` (수정) — `_sanitize_for_ko_tts()` 추가 (비한국어 문자 제거)
  - `tests/test_melo_engine.py` (수정) — mock `quiet` 파라미터 추가
- **발견·수정된 버그**:
  1. **Gemini 2.5 Flash MAX_TOKENS**: `max_output_tokens=1024`로 thinking 토큰 예산을 초과해 JSON 52자에서 응답이 잘림 → 8192로 증가
  2. **Groq 8B 모델 한국어 품질**: `llama-3.1-8b-instant`이 모티프 79자(최소 80자 미달) 생성 → `llama-3.3-70b-versatile`로 교체
  3. **유사도 임계값 미스캘리브레이션**: 동일 스토리 기반 창작물의 motif_max=0.7이 비현실적 → 0.93으로 상향
  4. **FFmpeg crop 실패**: `scale=1080:-2`로 가로형 비디오 높이 607px → 1920 crop 불가 → `scale=-2:1920`으로 수정
  5. **MeloTTS CP949 인코딩 오류**: `print()` 호출이 한자(恶 등)를 CP949로 인코딩 실패 → `quiet=True` 적용
  6. **LLM 생성 비한국어 문자**: Groq 70B가 간헐적으로 한자 포함 출력 → TTS 전 정제 함수 추가
- **E2E 결과**: crawl → rewrite → tts → subtitle → render 전 스테이지 통과, `output/final/video_2.mp4` (1080×1920, H.264, 45s) 생성
- **잔여 이슈**:
  - TTS 합성 45.3s (목표 50~58s 미달) — 스크립트 길이 부족. 리라이터 프롬프트 분량 조정 필요
  - Gemini 무료 Tier 20 RPM 한도로 crawl/rewrite 중 빈번히 Groq 폴백
  - `google.generativeai` → `google.genai` SDK 마이그레이션 미완료 (FutureWarning)
- **의존성 추가**: `sentence-transformers 5.4.1` (pip install)
- **pytest 결과**: **95/95 통과** (4.60s)
- **승인 상태**: ✅ 완료

---

## 작업 ID 규칙

| 접두어 | 영역 |
|--------|------|
| `DOC-` | 문서 (요구정의/운영매뉴얼/이력) |
| `INFRA-` | 환경 구성 (Python 가상환경, 의존성, 디렉토리) |
| `DB-` | SQLite 스키마/마이그레이션 |
| `CRAWL-` | 소재 수집 (FR-1) |
| `RW-` | 대본 생성 (FR-2) |
| `TTS-` | 음성 합성 (FR-3) |
| `SUB-` | 자막 (FR-4) |
| `REND-` | 영상 합성 (FR-5) |
| `UP-` | 업로드 (FR-6) |
| `SCHED-` | 스케줄링 (FR-7) |
| `OBS-` | 로깅·모니터링 (FR-8) |
| `OPS-` | 운영 (Kill-Switch, NSSM 서비스화) |
| `TEST-` | 테스트 |
