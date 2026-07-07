# cards/ — HiddenFindsDaily 카드 콘텐츠 시스템

> ⚠️ **분리 계약 (SEPARATION CONTRACT) — 반드시 준수**
>
> 본 `cards/` 패키지는 기존 **쇼츠 영상 생성 모듈(`src/`, `bot/`)과 완전히 분리된 별도 서비스**다.
> 어떤 작업도 쇼츠 시스템에 영향을 주어서는 안 된다.

---

## 🚫 절대 금지 (쇼츠 영향 방지)

1. **`src/` · `bot/` 파일을 절대 수정하지 않는다.**
   - 카드 기능이 쇼츠 코드 변경을 요구하면 → `cards/` 안에서 래핑/복제로 해결.
2. **`cards/` 에서 `src/` 를 import 하지 않는다.** (`from src...`, `import src` 금지)
   - 현재 상태: cards→src import **0건**, src→cards import **0건**.
3. **공유 venv 라이브러리의 버전을 변경/다운그레이드하지 않는다.** (install 추가만 허용)
4. **`data/shorts.db` 에 접근하지 않는다.** 카드는 `data/cards.db` 만 사용.
5. **`output/` 쇼츠 영역에 쓰지 않는다.** 카드는 `output/cards/` 만 사용.

---

## ✅ 분리 경계 (자원별)

| 자원 | 쇼츠 (건드리지 말 것) | 카드 (이 패키지) |
|------|---------------------|------------------|
| 코드 | `src/`, `bot/` | `cards/` |
| DB | `data/shorts.db` | `data/cards.db` |
| DB 래퍼 | `src/db.py` `Database` | `cards/db.py` `CardsDB` (자체) |
| 설정/시크릿 | `src/config.py` `Secrets` | `cards/config.py` `CardSecrets` (자체) |
| LLM | `src/rewriter/` | `cards/llm.py` (SDK 직접) |
| 배경 생성 | `src/renderer/bg_generator.py` | `cards/bg.py` (자체) |
| 렌더러 | `src/renderer/card_renderer.py` (한국어, 1080×1920) | `cards/renderer.py` (영어, 3비율) |
| 출력 | `output/` | `output/cards/` |
| 스케줄러 | `task_ShortsAuto_*` | `task_Card_*` |
| 진입점 | `python -m src.main` | `python -m cards.main` |

## 🤝 허용되는 공유 (읽기 전용, 안전)

- `.env` — 쇼츠 `Secrets`·카드 `CardSecrets` 가 **서로 다른 클래스**로 독립 로드 (`extra='ignore'`).
- `assets/fonts/` — 쇼츠는 Pretendard, 카드는 Poppins/Inter. **다른 파일**, 충돌 없음.
- `.venv/` — 라이브러리 읽기 공유. **버전 변경 금지**.

---

## 패키지 구조

```
cards/
├── config.py     CardSecrets + 캔버스/해시태그 상수
├── db.py         CardsDB — cards.db 전용 SQLite 래퍼
├── schema.sql    cards.db 스키마 (card_contents/uploads/affiliate_links/...)
├── bg.py         Pollinations AI 배경 (HOOK 슬라이드용)
├── renderer.py   캐러셀 렌더러 — HOOK/REVEAL/COMPARE/CTA × 3비율
├── llm.py        (예정) Groq/Gemini 직접 호출 + 카드 JSON 스키마
├── main.py       (예정) 파이프라인 오케스트레이터
├── crawler/      (예정) travel / aliexpress / kbeauty
├── uploader/     (예정) pinterest / instagram / tiktok / imgur
└── affiliate/    (예정) UTM 링크 매니저
```

## 실행

```bash
python -m cards.renderer instagram        # 데모 렌더 (3비율: pinterest/instagram/tiktok)
python -m cards.main --vertical v2 --platform pinterest --dry-run   # (예정)
```

---

## 검증 명령 (분리 무결성 자가 점검)

```bash
# cards → src 결합 0 확인
grep -rn "from src\|import src" cards/ --include="*.py" | grep -v __pycache__   # → 출력 없어야 정상

# 쇼츠 파일 무변경 확인
git status --short src/ bot/ | grep -v "^??"                                    # → 출력 없어야 정상
```

---

*상세 설계: `docs/strategy/ISOLATION_DESIGN_v1.0.md`*
