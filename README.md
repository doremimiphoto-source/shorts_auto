# Shorts Auto Pipeline

한국어 사연·반전 스토리텔링 YouTube Shorts 채널을 위한 **완전 자동화 파이프라인**.

| 항목 | 값 |
|------|---|
| 버전 | 1.0.0 |
| 운영 환경 | Windows 11 Pro / CPU only / 클라우드 무료 API |
| 운영비 | 약 ₩5,000/월 (전기료) |
| 기술 스택 | Python 3.11+ · Gemini Flash · Piper TTS · faster-whisper · FFmpeg · YouTube Data API v3 |

---

## 문서

| 파일 | 내용 |
|------|------|
| [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) | 요구사항 정의서 (v1.0 확정) |
| [docs/SETUP.md](docs/SETUP.md) | 사전 준비 가이드 (설치·API·에셋) |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | 변경 이력 |
| [docs/WORKLOG.md](docs/WORKLOG.md) | 작업 일지 |

## 빠른 시작

> 자세한 절차는 [docs/SETUP.md](docs/SETUP.md) 참조.

```powershell
# 1. 가상환경 생성 + 의존성 설치
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# 2. 환경변수 설정
copy .env.example .env
# .env 파일을 열어 API 키 입력

# 3. 설정 파일
copy config.yaml.example config.yaml

# 4. (구현 진행 후) 첫 dry-run
python -m src.main --dry-run
```

## 디렉토리 구조

```
shorts_auto/
├── docs/             # 문서 (요구정의·변경이력·작업일지·셋업)
├── src/              # 소스 코드 (구현 단계)
│   ├── crawler/      # 소재 수집 (FR-1)
│   ├── rewriter/     # 대본 생성 (FR-2)
│   ├── tts/          # 음성 합성 (FR-3)
│   ├── subtitle/     # 자막 (FR-4)
│   ├── renderer/     # 영상 합성 (FR-5)
│   ├── uploader/     # 업로드 (FR-6)
│   ├── utils/        # 공통 유틸
│   └── notify/       # 알림
├── tests/            # 단위·통합 테스트
├── prompts/          # LLM 프롬프트 템플릿
├── assets/           # 폰트·BGM·배경영상 풀
├── models/           # Piper 음성 모델 등
├── credentials/      # OAuth 클라이언트 시크릿 (gitignore)
├── data/             # SQLite DB, Lock, 백업
├── output/           # 생성물 (gitignore)
├── logs/             # JSONL 로그 (gitignore)
└── scripts/          # 헬퍼 스크립트 (에셋 수집 등)
```

## 라이센스

본 프로젝트는 비공개 운영용이다. 본 저장소의 코드 자체에 대한 외부 라이선스는 부여하지 않는다.
사용된 외부 패키지·모델·에셋의 라이선스는 각 출처를 따른다 (`docs/SETUP.md` §5 참조).
