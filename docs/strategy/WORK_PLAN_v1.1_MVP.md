# 작업계획서 v1.1 — MVP 수직 슬라이스
**문서 유형**: 작업계획서 (개정)
**버전**: v1.1 (IMPL_AUDIT_v2.0 결정 반영)
**작성일**: 2026-06-29
**상태**: 🔵 구현 중
**채널**: @HiddenFindsDaily

---

## 변경 이력

| 버전 | 날짜 | 내용 |
|------|------|------|
| v1.0 | 2026-06-29 | 최초 작업계획 (Phase 0~6, 수평 레이어) |
| v1.1 | 2026-06-29 | Opus 감사 반영 — 과설계 4건 제외, 슬라이드 4종, 수직 슬라이스 전환 |

---

## 사용자 확정 결정 (2026-06-29)

| # | 결정 | 반영 |
|---|------|------|
| 1 | 과설계 4건 전부 제외 | similarity 삭제 / meta_token / temu_db / revenue_report 연기 |
| 2 | 슬라이드 4종 단순화 | HOOK / REVEAL / COMPARE / CTA (CONTEXT 제거) |
| 3 | 수직 슬라이스 | V2(여행) → Pinterest 끝까지 먼저 |

---

## MVP 정의 — "첫 매출 검증 수직선"

```
목표: 여행 콘텐츠 1세트 자동 생성 → Pinterest 업로드 → 어필리에이트 클릭까지
      전 과정을 1개 수직선으로 완성·검증

V2(여행) ──▶ 카드 생성 ──▶ Pinterest 핀 ──▶ 어필리에이트 직링크 ──▶ 클릭/전환
```

**MVP에 필요한 모듈 (6개만)**

| 순서 | 모듈 | 역할 | API 키 |
|------|------|------|--------|
| 1 | `cards/db.py` | cards.db 전용 opener (B-01 해결) | 불필요 |
| 2 | `src/renderer/carousel_renderer.py` | 4종 슬라이드 × 3비율 렌더러 | 불필요 |
| 3 | `src/crawler/travel_generator.py` | LLM 여행지 정보 생성 | Groq(기존) |
| 4 | `src/affiliate/link_manager.py` | UTM 어필리에이트 링크 | 불필요 |
| 5 | `src/uploader/pinterest.py` | Pinterest 핀 업로드 | Pinterest(심사 1~3일) |
| 6 | `cards/main.py` | V2→Pinterest 파이프라인 | - |

> Pinterest API 키는 마지막 업로드 단계에서만 필요. 1~5는 키 없이 완성·테스트 가능.

---

## MVP 제외 항목 (검증 후 추가)

| 항목 | 상태 | 추가 시점 |
|------|------|----------|
| similarity 임베딩 dedup | ❌ 삭제 | DB 유니크로 대체 (영구) |
| meta_token_manager | ⏸ 연기 | Instagram 단계에서 |
| temu_db CLI | ⏸ 연기 | V1 매출 검증 후 |
| revenue_log 리포트 | ⏸ 연기 | 운영 2주 후 |
| V1 (AliExpress) | ⏸ 2차 | MVP 검증 후 |
| V3 (K-뷰티) | ⏸ 2차 | MVP 검증 후 |
| Instagram | ⏸ 3차 | Pinterest 안정화 후 |
| TikTok | ⏸ 3차 | API 심사 후 |

---

## 슬라이드 4종 정의 (확정)

| 유형 | 용도 | 배경 | 레이아웃 |
|------|------|------|---------|
| **HOOK** | 첫 슬라이드, 시선 강탈 | AI 이미지 (Pollinations) | 대형 훅 타이틀 + 그라디언트 오버레이 |
| **REVEAL** | 정보 1개씩 공개 (반복) | 여행: Unsplash 실사 / 제품: 실제 상품 이미지 | 이미지 + 정보 카드 (이름·위치·가격·팁) |
| **COMPARE** | 좌/우 2컬럼 비교 (V1 전용) | 단색 그라디언트 | 2분할 레이아웃 |
| **CTA** | 마지막, 저장·공유·링크 | 단색 그라디언트 | 채널 브랜딩 + Linktree |

---

## 구현 진행 상태

### Phase 0 — 사전 준비 ✅ 완료
- [x] 디렉토리 구조 (cards/, src/affiliate/, output/cards/)
- [x] cards.db 초기화 (테이블 5개)
- [x] Poppins + Inter 폰트 다운로드
- [x] config.py Secrets 필드 추가
- [x] cards/config.py + cards_schema.sql

### Phase 1 — 렌더링 기반 (진행 중)
- [x] bg_generator.py — generate_bg_image() + 영어 프롬프트 3종
- [ ] cards/db.py — cards.db opener (B-01)
- [ ] carousel_renderer.py — 4종 슬라이드 × 3비율

### Phase 2 — V2 Pinterest 수직선
- [ ] travel_generator.py — LLM 여행지 생성
- [ ] link_manager.py — UTM 링크
- [ ] pinterest.py — 핀 업로드
- [ ] cards/main.py — 파이프라인 통합
- [ ] V2 → Pinterest 실업로드 검증

### Phase 3+ — 검증 후 확장
- [ ] V1 / V3 데이터 수집기
- [ ] Instagram / TikTok 업로더

---

## 완료 기준 (MVP)

```bash
# 1. 키 없이 카드 생성 검증
python -m cards.main --vertical v2 --platform pinterest --dry-run
→ output/cards/v2_travel/ 에 8장 카드 생성 확인

# 2. Pinterest 키 발급 후 실업로드
python -m cards.main --vertical v2 --platform pinterest
→ Pinterest에 핀 게시 + cards.db card_uploads에 success 기록
→ 핀 클릭 시 어필리에이트 링크로 이동 확인
```

---

*관련: IMPL_AUDIT_v2.0.md | DEV_SPEC_v1.0.md (B-01·O-01~04 반영분은 본 문서 우선)*
