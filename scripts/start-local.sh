#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
PYTHON_BIN="${PYTHON_BIN:-}"

if [ -z "$PYTHON_BIN" ]; then
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="python3.11"
  else
    PYTHON_BIN="python3"
  fi
fi

if [ ! -f "$ROOT_DIR/.env" ]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
fi

echo "Starting backend and frontend..."

(
  cd "$BACKEND_DIR"
  if [ ! -d ".venv" ]; then
    "$PYTHON_BIN" -m venv .venv
  fi
  source .venv/bin/activate
  pip install -r requirements.txt
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
) &

(
  cd "$FRONTEND_DIR"
  npm install
  npm run dev
) &

wait
