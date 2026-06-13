#!/usr/bin/env bash
# Start FastAPI on :8000 then Vite on :5173 (Ctrl+C stops both).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

UVICORN="$ROOT/.venv/bin/uvicorn"
if [[ ! -x "$UVICORN" ]]; then
  echo "ERROR: $UVICORN not found or not executable."
  echo "  Run:  python3 -m venv .venv"
  echo "        source .venv/bin/activate"
  echo "        pip install -e \".[web]\""
  exit 1
fi

if [[ ! -d "$ROOT/web/node_modules" ]]; then
  echo "ERROR: web/node_modules missing."
  echo "  Run:  npm run install-web"
  exit 1
fi

cleanup() {
  if [[ -n "${UV_PID:-}" ]] && kill -0 "$UV_PID" 2>/dev/null; then
    kill "$UV_PID" 2>/dev/null || true
    wait "$UV_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Starting API http://127.0.0.1:8000 ..."
"$UVICORN" api.main:app --host 127.0.0.1 --port 8000 &
UV_PID=$!

for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -sf "http://127.0.0.1:8000/api/health" >/dev/null 2>&1; then
    echo "API is up."
    break
  fi
  if ! kill -0 "$UV_PID" 2>/dev/null; then
    echo "ERROR: API process exited early. Start it manually to see the error:"
    echo "  $UVICORN api.main:app --host 127.0.0.1 --port 8000"
    exit 1
  fi
  sleep 0.4
done

echo "Starting UI http://127.0.0.1:5173 ..."
npm run dev --prefix web
