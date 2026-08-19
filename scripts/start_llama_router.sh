#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"
source "$ROOT/scripts/runtime_env.sh"
SERVER="${LLAMA_SERVER:-$SOAI_RUNTIME_DIR/llama.cpp/build/bin/llama-server}"
PRESET="${LLAMA_PRESET:-$SOAI_STATE_DIR/llama-models.ini}"
PORT="${SOAI_LLAMA_PORT:-18080}"
[[ -x "$SERVER" ]] || { echo "Missing llama-server: $SERVER" >&2; exit 1; }
[[ -f "$PRESET" ]] || { echo "Missing $PRESET. Run prepare_llama_models.sh after model sync." >&2; exit 1; }
printf '%s\n' "$$" > "$SOAI_STATE_DIR/llama-router.pid"
exec "$SERVER" \
  --models-preset "$PRESET" \
  --models-max "${LLAMA_MODELS_MAX:-1}" \
  --sleep-idle-seconds "${LLAMA_SLEEP_IDLE_SECONDS:-300}" \
  --host 127.0.0.1 --port "$PORT" \
  --metrics --slots
