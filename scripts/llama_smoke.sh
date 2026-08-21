#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(pwd)}"; cd "$ROOT"
source "$ROOT/scripts/runtime_env.sh"
SERVER="$SOAI_RUNTIME_DIR/llama.cpp/build/bin/llama-server"
PRESET="$SOAI_STATE_DIR/llama-models.ini"
LOG="$SOAI_STATE_DIR/llama-router-smoke.log"
"$SERVER" --models-preset "$PRESET" --models-max 1 --host 127.0.0.1 --port 18080 --no-models-autoload >"$LOG" 2>&1 &
pid=$!
trap 'kill $pid 2>/dev/null || true' EXIT
for _ in $(seq 1 60); do curl -fsS http://127.0.0.1:18080/health >/dev/null 2>&1 && break; sleep 1; done
curl -fsS http://127.0.0.1:18080/models?reload=1 > "$SOAI_STATE_DIR/llama-models-smoke.json"

model_status() {
  curl -fsS "http://127.0.0.1:18080/models" | python3 -c "import json,sys; d=json.load(sys.stdin); x=[m for m in d.get('data',[]) if m.get('id')=='$1']; print(x[0].get('status',{}).get('value','') if x else '')"
}

for m in qwen35-9b qwen38-27b; do
  # FIXES.md F-024: a preset with load-on-startup=true (currently qwen35-9b) is already
  # loading -- or finished loading -- by the time this loop reaches it, because the
  # router started it automatically the moment the process came up, before this script's
  # health-check even returned. Issuing POST /models/load again on top of that raced load
  # gets rejected with 400 by the router, which under -fsS + set -euo pipefail killed this
  # whole script (and, via the EXIT trap, the router it had just started). Check status
  # first and only issue the explicit load when the model genuinely hasn't started yet.
  echo "Loading $m..."
  state="$(model_status "$m")"
  if [[ "$state" != loading && "$state" != loaded ]]; then
    curl -fsS -X POST http://127.0.0.1:18080/models/load -H 'content-type: application/json' -d "{\"model\":\"$m\"}" >/dev/null
  fi
  ok=0
  for _ in $(seq 1 240); do
    state="$(model_status "$m")"
    [[ "$state" == loaded ]] && { ok=1; break; }
    sleep 1
  done
  [[ $ok == 1 ]] || { echo "$m failed to load; see $LOG" >&2; exit 1; }
  curl -fsS -X POST http://127.0.0.1:18080/v1/chat/completions -H 'content-type: application/json' -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly READY\"}],\"max_tokens\":8,\"temperature\":0}" > "$SOAI_STATE_DIR/llama-smoke-$m.json"
  curl -fsS -X POST http://127.0.0.1:18080/models/unload -H 'content-type: application/json' -d "{\"model\":\"$m\"}" >/dev/null
  echo "$m OK"
done
