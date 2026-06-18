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
)

# 기존 에이전트 언로드 (오류 무시)
for label in "${ALL_LABELS[@]}"; do
    launchctl unload "$LAUNCHD_DIR/$label.plist" 2>/dev/null || true
done

# plist 복사 + 경로 치환 (PROJECT_DIR + HOME)
for plist in "$PLIST_SRC"/*.plist; do
    fname="$(basename "$plist")"
    dest="$LAUNCHD_DIR/$fname"
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

# 에이전트 로드
for label in "${ALL_LABELS[@]}"; do
    launchctl load "$LAUNCHD_DIR/$label.plist"
    echo "로드됨: $label"
done

echo ""
echo "완료. 등록된 에이전트 확인:"
launchctl list | grep shortsauto
