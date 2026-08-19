#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(pwd)}"
source "$ROOT/scripts/runtime_env.sh"
PY="$SOAI_ENV_DIR/wangp/bin/python"
WANGP="$SOAI_RUNTIME_DIR/Wan2GP"
[[ -x "$PY" ]] || { echo "WanGP worker environment missing: run scripts/install_specialists.sh" >&2; exit 2; }
[[ -f "$WANGP/shared/api.py" ]] || { echo "WanGP runtime missing: $WANGP" >&2; exit 2; }
mkdir -p "$SOAI_OUTPUT_DIR" "$SOAI_STATE_DIR/wangp"
exec "$PY" "$ROOT/scripts/wangp_worker.py" \
  --wangp-root "$WANGP" \
  --output-dir "$SOAI_OUTPUT_DIR" \
  --host 127.0.0.1 \
  --port 7867
