#!/bin/zsh
# 쇼츠 조회수 재점검 (7/17 예약) — 분석 실행 + Telegram 알림
# launchd: com.shortsauto.recheck (7/17 10:00 KST). 1회성이므로 실행 후 unload 권장.
set -e
PROJECT="/Users/doremi/Developer/shorts_auto"
cd "$PROJECT"
mkdir -p "$PROJECT/logs"
STAMP=$(date +%Y%m%d)
LOG="$PROJECT/logs/recheck_${STAMP}.log"

{
  echo "===== 쇼츠 조회수 재점검 $(date) ====="
  echo ""
  echo "########## ① 완주율·트래픽·댓글 (최근 30일) ##########"
  "$PROJECT/.venv/bin/python" -m scripts.fetch_analytics --days 30 || echo "(analytics 실패 — 토큰/네트워크 확인)"
  echo ""
  echo "########## ② 리텐션 곡선 상위 5편 (3~9초 이탈) ##########"
  "$PROJECT/.venv/bin/python" -m scripts.fetch_analytics --days 30 --retention 5 || echo "(retention 실패)"
  echo ""
  echo "########## ③ 조회수 + 업로드 시간대 성과 ##########"
  "$PROJECT/.venv/bin/python" -m scripts.fetch_video_stats || echo "(video_stats 실패)"
} > "$LOG" 2>&1

# ── Telegram 알림 ──
TOKEN=$(grep '^TELEGRAM_BOT_TOKEN=' .env | head -1 | cut -d= -f2- | tr -d ' \r')
CHAT=$(grep '^TELEGRAM_ALLOWED_USERS=' .env | head -1 | cut -d= -f2- | cut -d, -f1 | tr -d ' \r')
if [ -n "$TOKEN" ] && [ -n "$CHAT" ]; then
  curl -s "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${CHAT}" \
    --data-urlencode "text=📊 쇼츠 조회수 재점검일(7/17)입니다.
분석 완료 → logs/recheck_${STAMP}.log
세션에서 '쇼츠 재점검' 이라고 하면 baseline 대비 해석 + 다음 레버(훅→본론 3~9초)를 이어갑니다." > /dev/null || true
fi
echo "recheck done → $LOG"
