#!/bin/bash
# macOS용 배치 실행 스크립트 (run_batch.bat 대체)
# launchd 또는 cron에서 호출된다.

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_EXE="$PROJECT_DIR/.venv/bin/python"
LOG_FILE="$PROJECT_DIR/logs/batch_stderr.log"

export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1
export HF_HOME="$HOME/.cache/huggingface"
export TRANSFORMERS_CACHE="$HOME/.cache/huggingface/hub"
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1

# Homebrew PATH 보장 (launchd는 사용자 PATH를 상속하지 않음)
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/bin:$PATH"

# macOS Homebrew Python은 시스템 keychain 미사용 → certifi CA 번들 명시
export SSL_CERT_FILE="$("$PYTHON_EXE" -c "import certifi; print(certifi.where())")"
export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"

mkdir -p "$PROJECT_DIR/logs"

cd "$PROJECT_DIR"

# 절전 해제/로그인 직후 시스템 안정화 대기
sleep 30

"$PYTHON_EXE" -m scripts.run_batch --count 1 2>>"$LOG_FILE"
