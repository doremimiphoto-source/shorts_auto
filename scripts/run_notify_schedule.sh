#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_EXE="$PROJECT_DIR/.venv/bin/python"
LOG_FILE="$PROJECT_DIR/logs/batch_stderr.log"

export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1
export HF_HOME="$HOME/.cache/huggingface"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

mkdir -p "$PROJECT_DIR/logs"
cd "$PROJECT_DIR"

"$PYTHON_EXE" -m scripts.notify_schedule 2>>"$LOG_FILE"
