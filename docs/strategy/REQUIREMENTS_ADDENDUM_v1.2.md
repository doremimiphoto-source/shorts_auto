# 요구사항 추가 정의서 (V1/V3 정제)
**문서 유형**: 요구사항 추가 (Addendum)
**버전**: v1.2 (REQUIREMENTS_v1.1 보강)
**작성일**: 2026-06-29
**상태**: 🟢 확정
**전제**: 영어 전용, 외국인(글로벌 영어권) 타겟

---

## 변경 이력

| 버전 | 날짜 | 내용 |
|------|------|------|
| v1.1 | 2026-06-29 | 7개 결정 반영 |
| v1.2 | 2026-06-29 | 사용자 V1/V3 정제 — Ali vs Amazon 명시, K-뷰티 한국 메이저사이트 소스 명시 + 법적 재조정 |

---

## V1. 글로벌 쇼핑 비교 — AliExpress vs Amazon (확정)

> 사용자 지시: "제품은 알리와 아마존을 비교"

| 항목 | 확정 내용 |
|------|----------|
| 비교 축 | **AliExpress vs Amazon** (동일/유사 제품의 실제 가격 차이) |
| 콘텐츠 각도 | "같은 제품, 아마존보다 알리가 N배 저렴" (외국인 대상 가성비 폭로) |
| AliExpress 데이터 | AliExpress Portals API — **실가격·평점·이미지** (사실 기반) |
| Amazon 데이터 | 초기 3개월 **수동 실링크 수집** → 실적 후 PA-API (D-04) |
| 사실 원칙 | 가격·평점은 **API/실측만**, LLM 발명 금지 (CONTENT_PRINCIPLES 원칙1) |
| 슬라이드 | COMPARE 레이아웃 (좌 AliExpress / 우 Amazon, VS 중앙) |
| 어필리에이트 | AliExpress Portals + Amazon Associates |

**COMPARE 카드 데이터 구조 (사실 기반)**:
```
left  (AliExpress): {label, price(실API), rating(실API), image(실API)}
right (Amazon):     {label, price(실링크), rating(실링크)}
→ 두 값 모두 실제 소스. 차액 % 는 계산값.
```

---

## V3. K-뷰티 — 한국 제품을 외국인에게 (확정 + 법적 재조정)

> 사용자 지시: "한국제품을 외국사람들에게 노출, 올리브영·지그재그·에이블리·네이버쇼핑 등 메이저 사이트 기준"

### 소스 정책 (법적 재조정 — 중요)

| 메이저 사이트 | 역할 | 데이터 수집 방법 | 비고 |
|-------------|------|----------------|------|
| **네이버 쇼핑** | 제품 데이터 1차 소스 | **Naver Shopping API** (공식·무료) | 합법, 다수 한국 쇼핑몰 집계 |
| 올리브영 | 인기 제품 레퍼런스 | Naver API 경유(올리브영 판매 제품이 네이버에 노출) | 직접 크롤링 금지(ToS) |
| 지그재그 | 패션 트렌드 레퍼런스 | Naver API 경유 / 공개 트렌드 | 직접 크롤링 금지(ToS) |
| 에이블리 | 패션 트렌드 레퍼런스 | Naver API 경유 / 공개 트렌드 | 직접 크롤링 금지(ToS) |

> **재조정 이유 (C-05 / CONTENT_PRINCIPLES 원칙3)**:
> 올리브영·지그재그·에이블리 **직접 자동 크롤링은 각 사 ToS 위반·법적 리스크**.
> → 이들 사이트는 "무엇이 한국에서 인기인가"의 **레퍼런스(주제 풀)**로 삼되,
> 실제 제품 데이터는 **합법적 Naver Shopping API**로 수집한다.
> Naver 쇼핑은 올리브영 등 다수 쇼핑몰 상품을 집계하므로 동일 제품 확보 가능.

### 외국인 구매 라우팅 (글로벌 배송)

국내 전용 사이트(지그재그·에이블리)는 해외배송이 어려우므로, **구매 링크는 글로벌 배송 채널로**:

| 구매 채널 | 글로벌 배송 | 어필리에이트 |
|----------|-----------|------------|
| YesStyle | ✅ 전세계 | 10~15% |
| StyleKorean | ✅ 전세계 | 5~10% |
| Olive Young **Global** | ✅ 전세계 (global.oliveyoung.com) | 제휴 |
| Stylevana | ✅ 전세계 | 8~12% |

```
콘텐츠 흐름:
  네이버 쇼핑 API → 한국 인기 K-뷰티 제품(실제 가격·브랜드) 수집
  → LLM 영어 번역/설명 (제품명 번역은 사실 왜곡 아님)
  → 카드에 영어로 소개 (외국인 대상)
  → 구매 링크는 YesStyle/StyleKorean/올리브영글로벌 (해외배송 가능)
```

### 사실 원칙 적용 (원칙1)
- 제품명·가격·브랜드: **Naver Shopping API 실데이터만**
- 가격은 KRW→USD 환산 시 "approx" 명시
- LLM은 **영어 설명·번역만**, 효능·성분 과장/발명 금지
- 제품 실존: API 응답 = 실존 (별도 검증 불필요)

---

## 공통 (V1·V3 모두)

| 항목 | 확정 |
|------|------|
| 언어 | **영어 전용** (외국인 타겟) |
| 보이스 | 인간이 쓴 느낌 (CONTENT_PRINCIPLES 원칙2) — V1/V3는 "솔직 리뷰어" 톤 검토 |
| 사실 | 가격·평점·제품 전부 실 API (원칙1) |
| 무료 | AliExpress Portals / Naver Shopping API 무료 (원칙3) |

---

## 구현 영향 (MVP 이후 2차)

| 모듈 | v1.1 → v1.2 변경 |
|------|----------------|
| `cards/crawler/shopping.py` (V1) | AliExpress API + Amazon 수동링크 비교 데이터 |
| `cards/crawler/kbeauty.py` (V3) | Naver Shopping API 수집 + 영어 번역 + 글로벌배송 링크 라우팅 |
| `cards/renderer.py` COMPARE | V1 Ali vs Amazon 2컬럼 (이미 구현됨) |
| `cards/affiliate/links.py` | YesStyle/StyleKorean/올리브영글로벌 추가 |

> V1/V3는 MVP(V2 여행→Pinterest) 검증 후 2차 확장. 본 문서는 그때의 구현 기준.

---

*관련: REQUIREMENTS_v1.1.md · CONTENT_PRINCIPLES_v1.0.md (원칙1 사실기반)*
