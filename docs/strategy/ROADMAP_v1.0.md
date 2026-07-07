# 차후 작업 로드맵 — HiddenFindsDaily
**버전**: v1.0
**작성일**: 2026-07-03
**현재 상태**: Pinterest Trial access 심사 대기 중

---

## 현재 위치

```
✅ 완료: 콘텐츠 3버티컬 + 자동화 + 알림 + 브랜드 + 분리격리
⏳ 대기: Pinterest 승인 (임계경로) ← 지금 여기
```

| 구성요소 | 상태 |
|---------|------|
| V1 쇼핑 / V2 여행 / V3 K-뷰티 콘텐츠 | ✅ 완성·검증 (실데이터·실사진·사실검증) |
| 렌더러 (4슬라이드×3비율, 이모지) | ✅ |
| 자동화 (launchd, 매일 주제 로테이션) | ✅ |
| Telegram 성공/실패 알림 | ✅ |
| Naver API / Unsplash API | ✅ 발급·검증 |
| Linktree / 브랜드 이미지 | ✅ |
| 쇼츠 완전 분리 | ✅ |
| Pinterest API | ⏳ 승인 대기 |

---

## Phase 6 — Pinterest 게시 개시 (승인 직후) ★ 다음 단계

승인 이메일 오면 즉시 진행 (약 30분):

```
1. My apps → App ID / App secret → .env
2. 토큰 발급
   - 빠른 검증: 대시보드 "Generate token" (테스트 토큰 24h)
   - 영구 운영: python -m cards.auth_pinterest (OAuth)
3. 보드 ID 확인: curl .../v5/boards → .env (BOARD_V1/V2/V3)
4. 첫 실게시 검증:
   python -m cards.main --vertical v2 --platform pinterest   (여행)
   python -m cards.main --vertical v3 --platform pinterest --category serum  (뷰티)
   → 핀 이미지·링크·설명 눈으로 확인
5. launchd 등록 → 매일 자동 게시 시작
   cp cards/launchd/*.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.hiddenfindsdaily.*.plist
```

**완료 기준**: V2·V3 핀이 실제 게시되고, Telegram 성공 알림 수신, 매일 자동 운영 확인.

---

## Phase 7 — 검증·안정화 (게시 후 1~2주)

```
- Telegram 알림으로 매일 게시 성공/실패 모니터링
- 핀 렌더링·링크 정상 작동 재확인
- Pinterest 조회수·저장수·클릭 관찰
- 필요 시 콘텐츠 훅/카피 미세 조정
- 목표: 팔로워·트래픽 누적 (Pinterest는 팔로워 없어도 검색 노출)
```

**이 단계 목적**: 첫 채널을 안정적으로 굴리며 반응 데이터 확보. 확장은 그 다음.

---

## Phase 8 — V1 쇼핑 활성화 (선택)

```
옵션 A (지금 가능): 실제 Ali vs Amazon 비교 데이터 수동 입력
  python -c "from cards.db import open_cards_db; from cards.crawler.shopping import add_comparison; ..."
옵션 B (승인 후): AliExpress Portals API 승인 → Ali쪽 데이터 자동 채움
  (cards/crawler/aliexpress_api.py 실응답 검증·완성)
```

> V1은 실가격 데이터가 있어야 게시됨(발명 금지). 데이터 없으면 V2·V3만 운영.

---

## Phase 9 — 멀티플랫폼 확장 (Pinterest 검증 후)

> **원칙: Pinterest에서 콘텐츠가 통하는 걸 확인한 뒤 확장** (검증 전 확장 금지)

| 플랫폼 | 필요 작업 | 선행 조건 |
|--------|----------|----------|
| **Instagram** | Meta 앱 + Imgur 호스팅 + 캐러셀 업로더 | Meta 개발자 승인(즉시), Imgur(즉시) |
| **TikTok** | FFmpeg 영상변환 + Video API 업로더 | TikTok 개발자 심사(1~2주) |

각 플랫폼 업로더는 `cards/uploader/`에 추가 (렌더러·콘텐츠는 재사용, 비율만 전환).

---

## Phase 10 — 수익화 (팔로워 ~500 도달 후)

```
검증된 기준선: 대략 팔로워 500 (프로그램별 상이)
  → YesStyle 인플루언서 재신청 (현재 팔로워 부족으로 거절됨)
  → Amazon Associates (180일 내 판매 3건 조건)
  → Booking.com (신청해두면 리드타임 소화)
→ 승인되면 어필리에이트 ID를 .env에 입력 → 링크 자동 트래킹 전환
```

> 지금은 수익화 아닌 **콘텐츠·팔로워 성장**에 집중 (이미 확정한 방향).

---

## 승인 대기 중 — 선택 작업 (필수 아님)

| 작업 | 가치 | 비고 |
|------|------|------|
| Instagram/TikTok 계정 생성 + 브랜드 이미지 | 중 | 나중에 어차피 필요, rework 0 |
| V1 비교 데이터 입력 | 중 | V1도 게시하려면 |
| 콘텐츠 훅/카피 추가 튜닝 | 하 | 이미 상업 수준 |
| Booking.com 어필리에이트 신청 | 하 | 리드타임 길어 미리 걸어두면 이득 |

> 아무것도 안 해도 됩니다. 승인 시 Phase 6부터 바로 재개.

---

## 전체 흐름 요약

```
[지금] Pinterest 승인 대기
   ↓ (승인 이메일)
Phase 6: 토큰 → 게시 → launchd  (30분)
   ↓
Phase 7: 1~2주 검증·안정화·성장
   ↓
Phase 8: V1 활성화 (선택)
   ↓
Phase 9: Instagram → TikTok 확장
   ↓
Phase 10: 팔로워 500+ → 수익화
```

---

## 핵심 메시지

- **개발은 사실상 완료**. 남은 건 "승인 → 게시 → 성장 → 확장" 운영 사이클.
- **승인만 기다리면 됨.** 이메일 오면 30분 안에 라이브 가능.
- 확장·수익화는 **첫 채널 검증 후** 순차적으로.

---

*관련: WORK_PLAN_v1.1_MVP.md · CREDENTIALS_GUIDE_v1.0.md · CONTENT_PRINCIPLES_v1.0.md*
