#!/bin/zsh
# HiddenFindsDaily 카드 자동 실행 래퍼 (launchd 에서 호출)
# 사용: run_daily.sh --vertical v2 --platform pinterest --region "..." --theme "..."
set -e
PROJECT="/Users/doremi/Developer/shorts_auto"
cd "$PROJECT"
LOGDIR="$PROJECT/logs"
mkdir -p "$LOGDIR"
STAMP=$(date +%Y%m%d)
"$PROJECT/.venv/bin/python" -m cards.main "$@" >> "$LOGDIR/cards_${STAMP}.log" 2>&1
