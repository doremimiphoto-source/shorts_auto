# 키 발급 가이드 (지금 필요한 것만)
**버전**: v1.0
**작성일**: 2026-06-29
**대상**: V2(여행)·V3(K-뷰티) → Pinterest 실운영

> 코드는 전부 완성됨. 아래 키만 발급해 `.env`에 넣으면 즉시 실업로드된다.
> `.env` 위치: `/Users/doremi/Developer/shorts_auto/.env`

---

## ① Pinterest API (필수 — V2·V3 실업로드)

### 발급 단계
1. https://developers.pinterest.com 접속 → Pinterest 계정(@HiddenFindsDaily)으로 로그인
2. 상단 **"My apps"** → **"Connect app"** (또는 "Create app")
3. 앱 정보 입력:
   - App name: `HiddenFindsDaily`
   - Description: `Automated pin publishing for travel & beauty affiliate content`
   - Website: `https://linktr.ee/HiddenFindsDaily`
4. 생성 후 앱 대시보드에서 확인:
   - **App ID** / **App secret** 복사
5. **OAuth 설정** → Redirect URI 추가: `https://localhost/callback`
6. **"Generate access token"** 클릭 → 권한(scope) 체크:
   - `boards:read`, `boards:write`, `pins:read`, `pins:write`
   - 생성된 **Access Token** 복사
7. **보드 ID 확인** (터미널):
   ```bash
   curl -H "Authorization: Bearer <ACCESS_TOKEN>" \
        "https://api.pinterest.com/v5/boards"
   ```
   → 응답 JSON에서 각 보드의 `"id"` 복사
   (보드가 없으면 Pinterest 앱에서 "Hidden Travel Gems", "K-Beauty Picks" 보드 먼저 생성)

### .env 에 입력
```
PINTEREST_ACCESS_TOKEN=<6번 토큰>
PINTEREST_BOARD_V2=<여행 보드 id>
PINTEREST_BOARD_V3=<K-뷰티 보드 id>
```

> ⚠️ 신규 앱은 "Trial access"로 시작 — 본인 계정 게시는 즉시 가능.
> 대규모/타계정 게시는 "Standard access" 심사 필요(우리는 본인 계정이라 불필요).

### 발급 후 실행
```bash
# 먼저 dry-run 으로 확인
python -m cards.main --vertical v2 --platform pinterest --dry-run
# 실업로드
python -m cards.main --vertical v2 --platform pinterest
```

---

## ② Naver Shopping API (필수 — V3 K-뷰티 제품 데이터)

> 무료·즉시 발급 (일 25,000 호출). 한국 제품 실데이터 소스.

### 발급 단계
1. https://developers.naver.com/apps/#/register 접속 → 네이버 로그인
2. **애플리케이션 이름**: `HiddenFindsDaily`
3. **사용 API**: "검색" 선택 → 하위 **"쇼핑"** 체크
4. **비로그인 오픈 API 서비스 환경**: "WEB 설정" → URL `http://localhost`
5. **"등록하기"** → 즉시 발급
6. 발급된 **Client ID** / **Client Secret** 복사

### .env 에 입력
```
NAVER_CLIENT_ID=<Client ID>
NAVER_CLIENT_SECRET=<Client Secret>
```

### 발급 후 실행
```bash
python -m cards.main --vertical v3 --platform pinterest --category serum --dry-run
# 카테고리: serum / sunscreen / toner / cleanser / "sheet mask" / cushion / "lip tint" / essence
```

---

## ③ 어필리에이트 ID (선택 — 수익 추적용, 나중에 가능)

링크는 ID 없이도 생성됨(aid=PENDING). 수익 발생하려면 발급 후 입력:

| 파트너 | 발급 | .env 키 | 용도 |
|--------|------|---------|------|
| Booking.com | https://join.booking.com | `BOOKING_AFFILIATE_ID` | V2 여행 |
| YesStyle | https://www.yesstyle.com/en/affiliate-program.html | `YESSTYLE_AFFILIATE_ID` | V3 뷰티 |

> 코드가 자동으로 `aid=PENDING`을 발급 ID로 교체하므로, ID만 넣으면 됨.

---

## ④ 자동화 (launchd) — 키 입력 후 설정

### 설치 (매일 14:00 자동 게시)
```bash
cp /Users/doremi/Developer/shorts_auto/cards/launchd/com.hiddenfindsdaily.v2travel.plist \
   ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.hiddenfindsdaily.v2travel.plist
```

### 확인 / 해제
```bash
launchctl list | grep hiddenfindsdaily          # 등록 확인
launchctl unload ~/Library/LaunchAgents/com.hiddenfindsdaily.v2travel.plist   # 해제
```
로그: `logs/cards_YYYYMMDD.log`

> 쇼츠 launchd와 라벨·시각이 겹치지 않음 (격리 유지).

---

## 발급 우선순위

```
지금 (V2 여행 운영):        ① Pinterest         ← 이것만 있으면 V2 실운영
V3 K-뷰티 추가 시:          ② Naver Shopping     ← 무료·즉시
수익화 단계:                ③ Booking/YesStyle   ← 나중에
운영 자동화:                ④ launchd            ← 키 입력 후
```

---

*상세 셋업(전체 플랫폼): SETUP_GUIDE_DETAILED_v1.0.md*
