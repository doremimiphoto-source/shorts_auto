#!/bin/bash
# launchd 에이전트 설치 스크립트
# 맥에서 실행: bash scripts/launchd/install_launchd.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
PLIST_SRC="$PROJECT_DIR/scripts/launchd"

echo "프로젝트 경로: $PROJECT_DIR"
mkdir -p "$LAUNCHD_DIR"

ALL_LABELS=(
    com.shortsauto.batch_0700
    com.shortsauto.batch_1530
    com.shortsauto.batch_1800
    com.shortsauto.batch_2000
    com.shortsauto.crawl_rss
    com.shortsauto.notify_schedule
    com.shortsauto.cleanup_logs
    com.shortsauto.bot
)

# 기존 에이전트 언로드 (오류 무시)
for label in "${ALL_LABELS[@]}"; do
    launchctl unload "$LAUNCHD_DIR/$label.plist" 2>/dev/null || true
done

# plist 복사 + 경로 치환 (PROJECT_DIR + HOME) — ollama.plist는 템플릿 전용, 제외
# 심볼릭 링크가 있으면 먼저 제거 (링크를 통한 write는 소스 파일을 덮어씀)
for plist in "$PLIST_SRC"/com.shortsauto.batch_*.plist \
             "$PLIST_SRC"/com.shortsauto.crawl_rss.plist \
             "$PLIST_SRC"/com.shortsauto.notify_schedule.plist \
             "$PLIST_SRC"/com.shortsauto.cleanup_logs.plist \
             "$PLIST_SRC"/com.shortsauto.bot.plist; do
    [ -f "$plist" ] || continue
    fname="$(basename "$plist")"
    dest="$LAUNCHD_DIR/$fname"
    [ -L "$dest" ] && rm -f "$dest"  # 심볼릭 링크 제거
    sed -e "s|REPLACE_WITH_PROJECT_PATH|$PROJECT_DIR|g" \
        -e "s|REPLACE_WITH_HOME|$HOME|g" \
        "$plist" > "$dest"
    chmod 644 "$dest"
    echo "설치: $dest"
done

# sh 스크립트 실행 권한
chmod +x "$PROJECT_DIR/scripts/run_batch.sh"
chmod +x "$PROJECT_DIR/scripts/run_crawl_rss.sh"
chmod +x "$PROJECT_DIR/scripts/run_notify_schedule.sh"
chmod +x "$PROJECT_DIR/scripts/run_cleanup_logs.sh"

# 배치·부가 에이전트 로드
for label in com.shortsauto.batch_0700 com.shortsauto.batch_1530 com.shortsauto.batch_1800 com.shortsauto.batch_2000 \
             com.shortsauto.crawl_rss com.shortsauto.notify_schedule com.shortsauto.cleanup_logs; do
    launchctl load "$LAUNCHD_DIR/$label.plist"
    echo "로드됨: $label"
done

# Telegram Bot 로드 (TELEGRAM_BOT_TOKEN 설정된 경우만)
if grep -q "^TELEGRAM_BOT_TOKEN=.\+" "$PROJECT_DIR/.env" 2>/dev/null; then
    launchctl load "$LAUNCHD_DIR/com.shortsauto.bot.plist"
    echo "로드됨: com.shortsauto.bot"
else
    echo "건너뜀: com.shortsauto.bot (.env에 TELEGRAM_BOT_TOKEN 미설정)"
fi

echo ""
echo "완료. 등록된 에이전트 확인:"
launchctl list | grep shortsauto
