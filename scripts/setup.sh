#!/bin/bash
# 프로젝트 초기 설정 스크립트
# 실행: bash scripts/setup.sh
#
# 수행 내역:
#   1. .venv 생성 및 의존성 설치
#   2. launchd 서비스 등록 (선택)

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3.11}"
VENV="$PROJECT_DIR/.venv"

echo "=== shorts_auto 환경 설정 ==="
echo "프로젝트: $PROJECT_DIR"
echo "Python:   $PYTHON"
echo ""

# ── 1. venv 생성 ──────────────────────────────────────────────────
if [ ! -f "$VENV/bin/python" ]; then
    echo "[1/2] venv 생성..."
    "$PYTHON" -m venv "$VENV"
else
    echo "[1/2] venv 이미 존재, 건너뜀"
fi

echo "[1/2] 의존성 설치..."
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r "$PROJECT_DIR/requirements.txt"
echo "      완료"

# ── 2. launchd 등록 여부 확인 ─────────────────────────────────────
echo ""
echo "[2/2] launchd 서비스 등록..."
if [ -f "$PROJECT_DIR/.env" ]; then
    bash "$PROJECT_DIR/scripts/launchd/install_launchd.sh"
else
    echo "      .env 파일 없음 — 먼저 .env를 설정하고 install_launchd.sh를 실행하세요."
fi

# ── 완료 ──────────────────────────────────────────────────────────
echo ""
echo "=== 설정 완료 ==="
