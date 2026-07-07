# 콘텐츠 제작 원칙 (구속력 있는 규칙)
**문서 유형**: 콘텐츠 원칙 (Binding Content Principles)
**버전**: v1.0
**작성일**: 2026-06-29
**상태**: 🟢 확정 — 모든 카드 생성 모듈이 준수해야 함

---

## 원칙 1: 사실 기반 (Fact-Based) — 환각 금지

> **LLM은 글쓰기(phrasing)만 담당한다. 사실(facts)은 실제 데이터 소스에서만 가져온다.**

| 버티컬 | 사실 소스 (무료) | LLM 역할 |
|--------|----------------|---------|
| V2 여행 | Wikipedia REST API + Wikivoyage + OSM Nominatim | 검증된 장소의 실제 정보를 **재서술만** |
| V1 쇼핑 | AliExpress Portals API (실가격·평점) | 비교 카피 작성 |
| V3 K-뷰티 | Naver Shopping API (실제품·가격) | 영어 제품 설명 |

**검증 정책 (엄격 — 사용자 확정)**:
```
1. LLM이 후보 N+buffer 제안 (장소명·국가만)
2. 각 후보를 무료 API로 실존 검증 (Wikipedia/Nominatim)
3. 검증 통과 장소만 채택, 미검증은 폐기
4. 검증된 장소의 실제 정보(설명·위치·국가)만 사용
5. LLM은 이 검증된 사실로 카피를 작성 (사실 발명 금지)
```

**금지**:
- ❌ LLM이 가격·평점·예산·날짜·통계를 지어내기
- ❌ 실존하지 않는 장소·제품 게시
- ❌ 검증 안 된 수치를 사실인 양 표기
- ✅ 추정이 불가피하면 "roughly", "around" 등으로 명확히 hedge

---

## 원칙 2: 인간이 쓴 느낌 (Human Voice)

> **AI 리스티클 톤 금지. 여행자 1인칭 경험담 보이스 (사용자 확정).**

**채택 보이스**: 실제로 다녀온 여행자의 1인칭 경험담
- "I almost skipped this one, but..."
- "Took me 3 hours by boat and it was worth every minute"
- 개인적 의견·솔직한 코멘트·casual 표현

**AI 특유 패턴 (제거 대상)**:
| AI 티 | 대체 |
|-------|------|
| "Discover...", "Unveil...", "Nestled in..." | 직접적·구체적 표현 |
| 과도한 em-dash(—) 남발 | 자연스러운 문장 |
| 모든 문장이 균형잡힌 대구 | 길이·리듬 변주 |
| 형용사 나열 ("stunning, breathtaking, magical") | 구체적 디테일 1개 |
| 이모지 떡칠 | 절제된 사용 |
| 완벽한 격식체 | 약간의 구어체·생략 |

**프롬프트 강제 사항**:
- 1인칭("I", "my") 사용
- 구체적 디테일 (시간·비용·감각) 1개 이상
- 광고문구 금지, 친구에게 말하듯

---

## 원칙 3: 전부 무료 서비스 (100% Free)

> **유료 API·구독·크레딧 일절 사용 금지.**

| 용도 | 서비스 | 무료 근거 |
|------|--------|----------|
| LLM | Groq (llama-3.3-70b) | 무료 (RPM 제한) |
| LLM 폴백 | Gemini 2.0 Flash | 무료 (RPD 1500) |
| 이미지 생성 | Pollinations AI | 무료, 키 불필요 |
| 사실 검증 | Wikipedia REST API | 무료, 키 불필요 |
| 사실 검증 | Wikivoyage (MediaWiki API) | 무료, 키 불필요 |
| 지리 검증 | OSM Nominatim | 무료 (1 req/sec, UA 필수) |
| 실제 사진 | Unsplash API | 무료 (50 req/h) |
| 제품 데이터 | AliExpress Portals / Naver Shopping | 무료 |
| 카드 렌더 | Pillow | 무료 (로컬) |
| 업로드 | Pinterest/Instagram/TikTok API | 무료 |
| 폰트 | Poppins/Inter/Noto Emoji | 무료 (OFL) |

**검증 규칙**: 새 의존성 추가 시 무료 여부를 먼저 확인하고 본 표에 추가.

---

## 준수 검증 (모듈별 체크)

| 모듈 | 원칙1 (사실) | 원칙2 (보이스) | 원칙3 (무료) |
|------|-----------|--------------|-----------|
| `cards/facts.py` (신규) | ✅ 검증 엔진 | - | ✅ Wiki/OSM 무료 |
| `cards/crawler/travel.py` | ✅ 검증 후 생성 | ✅ 1인칭 프롬프트 | ✅ |
| `cards/llm.py` | (사실 미발명 강제) | (보이스 프롬프트) | ✅ Groq/Gemini |
| `cards/bg.py` | - | - | ✅ Pollinations |

---

*본 원칙은 모든 버티컬(V1/V2/V3)·전 플랫폼에 적용된다.*
