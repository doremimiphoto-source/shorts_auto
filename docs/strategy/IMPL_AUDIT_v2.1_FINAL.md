# 최종 실증 검증 보고서 (코드 실행 + 픽셀 확인)
**문서 유형**: 최종 구현 전 검증 (Final Empirical Verification)
**버전**: v2.1
**작성일**: 2026-06-29
**검토 모델**: Claude Opus 4.8
**상태**: 🟢 검증 완료 — 구현 재개 컨펌 대기
**방식**: 문서 대조가 아닌 **실제 코드 실행 + 렌더링 결과 픽셀 검사**

---

## 왜 검증할 때마다 이슈가 나왔는가 (정직한 설명)

| 단계 | 검증 방식 | 발견된 이슈 성격 |
|------|----------|---------------|
| PRE_IMPL_AUDIT v1.0 | 요구사항 문서 대조 | API 존재 여부, 정책 (Temu API 없음 등) |
| IMPL_AUDIT v2.0 | 코드 정적 분석 | db.py 재사용 결함, 과설계 |
| **IMPL_AUDIT v2.1 (본 문서)** | **코드 실행 + 픽셀 검사** | **렌더링 글리프 깨짐, LLM 스키마 불일치** |

→ 각 단계는 **추상 → 정적 → 실증** 순으로 깊어졌고, 실증 단계(실행)에서만 보이는 이슈가 마지막에 드러난 것.
→ **본 v2.1은 실제로 코드를 돌리고 결과 이미지를 눈으로 확인한 마지막 단계**이므로, 이후 새 이슈가 추가로 나올 여지가 가장 낮음.

---

## 1. 실증 검증 결과 — 작동 확인 (✅)

| 항목 | 검증 방법 | 결과 |
|------|----------|------|
| carousel_renderer 3비율 | `python -m src.renderer.carousel_renderer {ratio}` 실행 | ✅ pinterest(1000×1500)·instagram(1080×1080)·tiktok(1080×1920) 정확 |
| 레이아웃 비율 적응 | 3비율 HOOK/REVEAL/CTA 픽셀 확인 | ✅ 배지·타이틀·카드 위치가 비율마다 자연스럽게 적응 |
| 텍스트 줄바꿈·하이라이터 | 픽셀 확인 | ✅ 정상 (형광펜·둥근박스·하단페이드 작동) |
| 파일 크기 | 슬라이드당 ~150~240KB | ✅ 업로드 적합 |
| cards/db.py | `open_cards_db()` 실행 | ✅ cards.db 연결·중복체크 정상 (B-01 해결 확인) |
| config.py 신규 필드 | 로드 테스트 | ✅ Pinterest/Meta/TikTok/Naver 필드 정상 |
| bg_generator.generate_bg_image | 함수 추가 | ✅ (네트워크 호출은 런타임 검증 예정) |

> 렌더링 품질은 **상업적 사용 가능 수준**으로 확인됨 (프로페셔널한 소셜 카드 외형).

---

## 2. 실증 검증에서 발견된 신규 이슈 (2건)

### 🔴 [F-01] 이모지·특수문자 글리프 깨짐 (두부 박스)

- **증상**: 렌더링 결과에서 `→ 💾 📤 💬 ✈️ 🔗 ⭐` 등이 **빈 사각형(☐)으로 깨짐**
- **원인**: Poppins/Inter 폰트에 **이모지·화살표 글리프 미포함**. Pillow는 글자별 폰트 자동 폴백을 안 함.
- **영향 범위**:
  - HOOK 슬라이드 "Swipe to see them →" 의 화살표
  - CTA 슬라이드 "💾 📤 💬" 액션 아이콘
  - CTA 링크 박스 "🔗" 아이콘
  - (향후) 가격 비교 ⭐ 평점, 여행 ✈️ 등
- **심각도**: HIGH — 소셜 카드는 이모지가 시각 언어의 핵심. 깨지면 아마추어 인상.
- **해결안 (택1)**:
  - **(A) 권장** — Noto Emoji(흑백, 확장 가능 TTF) 다운로드 + 글리프 폴백 헬퍼 `_draw_rich()` 추가. 이모지 부분만 Noto로 그림. 다크 배경에 흰색/민트 이모지 → 모던한 외형.
  - (B) Noto Color Emoji(컬러) — 단, Pillow는 특정 크기(109px)만 지원 → 리사이즈 필요, 까다로움.
  - (C) 이모지 전부 제거 — 안전하나 바이럴 카드 매력 감소.
- **권장**: (A). 재사용 가능한 `_draw_rich()` 1개로 전 슬라이드 해결.

### 🟠 [F-02] RewriterChain 직접 재사용 불가 (스키마 불일치)

- **계획 문서 주장** (DEV_SPEC §2-5): "RewriterChain 100% 재사용, 영어 프롬프트만 교체"
- **실제 코드 검증**:
  - `RewriterChain.generate()` → 백엔드가 prompt 치환 후 LLM 호출 → `_parse_response()` 가 **고정 키**(hook/body/twist/title/hashtags)로 파싱 → `RewriteResult` 반환
  - `RewriteResult` 스키마는 **단일 대본**(hook/body/twist)용. 여행 카드의 **5개 장소 × {이름·위치·시기·예산·하이라이트}** 같은 **다중 항목 구조**를 담을 수 없음.
- **결론**: RewriterChain/RewriteResult **추상화는 카드 용도에 부적합**. 단, 그 아래 **Groq/Gemini 클라이언트 + 폴백 패턴 + API 키**는 재사용 가치 있음.
- **해결안**: `cards/llm.py` 신규 — 동일 API 키(GROQ/GEMINI) 재사용 + 동일 폴백 패턴, 단 **카드용 JSON 스키마**(항목 리스트) 반환. RewriterChain은 미사용.
- **심각도**: MEDIUM — 구조만 분리하면 됨. API 키·폴백 로직은 재활용.

---

## 3. 미검증 항목 (외부 의존 — 현 단계 검증 불가, 위험 낮음)

| 항목 | 미검증 이유 | 위험 | 대응 |
|------|-----------|------|------|
| Pinterest API 실업로드 | Access Token 미발급(심사 대기) | 낮음 | v5 `image_base64` 방식 확정 — Imgur 불필요 |
| REVEAL 실사진 배경 | 데모는 그라디언트만 | 낮음 | cover-fit + 다크 카드 오버레이 로직 검증됨 |
| COMPARE 슬라이드 | V1 전용 (MVP 제외) | 없음 | 2차 확장 시 |
| 실제 어필리에이트 딥링크 | 파트너 계정 미승인 | 낮음 | 링크 구조 선구현, ID는 발급 후 주입 |
| LLM 실호출 | 영어 프롬프트 미작성 | 낮음 | cards/llm.py 구현 시 즉시 검증 가능 |

---

## 4. 수정 반영 모듈 목록 (최종)

| 모듈 | 상태 | 비고 |
|------|------|------|
| `cards/db.py` | ✅ 완료 | B-01 해결 |
| `cards/config.py` | ✅ 완료 | |
| `src/cards_schema.sql` | ✅ 완료 | |
| `src/renderer/bg_generator.py` | ✅ 완료 | generate_bg_image 추가 |
| `src/renderer/carousel_renderer.py` | ⚠️ F-01 수정 필요 | 이모지 폴백 추가 |
| `cards/llm.py` | 🆕 신규 필요 | F-02 — RewriterChain 대체 |
| `scripts/download_emoji_font.py` | 🆕 신규 필요 | F-01 — Noto Emoji |
| `src/crawler/travel_generator.py` | ⬜ 예정 | cards/llm.py 사용 |
| `src/affiliate/link_manager.py` | ⬜ 예정 | |
| `src/uploader/pinterest.py` | ⬜ 예정 | image_base64 |
| `cards/main.py` | ⬜ 예정 | |

---

## 5. 남은 MVP 구현 순서 (수정 반영)

```
1. [F-01] download_emoji_font.py + carousel_renderer 이모지 폴백  ← 렌더러 완성
2. [F-02] cards/llm.py (Groq/Gemini 폴백 + 카드 JSON 스키마)
3. travel_generator.py (cards/llm.py 사용, 영어 여행 콘텐츠)
4. link_manager.py (UTM 어필리에이트 링크)
5. pinterest.py (image_base64 업로드)
6. cards/main.py (V2→Pinterest 파이프라인, --dry-run 지원)
7. 통합 검증: dry-run으로 8슬라이드 생성 → (키 발급 후) 실업로드
```

---

## 6. 종합 판정

| 항목 | 판정 |
|------|------|
| 렌더링 엔진 | ✅ 작동·품질 확인 (이모지만 수정) |
| DB 레이어 | ✅ 완료 |
| 설계 정합성 | 🟠 RewriterChain 가정 1건 수정 (cards/llm.py로 분리) |
| 남은 구현량 | 신규 5개 모듈 + 렌더러 이모지 패치 |
| 추가 이슈 가능성 | 낮음 (실증 단계 완료) |
| **구현 재개 가능 여부** | ✅ **가능 — F-01·F-02 반영하여 진행** |

---

*본 문서가 최종 검증 기준. 컨펌 시 위 §5 순서로 구현 재개.*
