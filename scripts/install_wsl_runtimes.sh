#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(pwd)}"
cd "$ROOT"
source "$ROOT/scripts/runtime_env.sh"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing $1" >&2; exit 1; }; }
need git; need python3; need curl; need node; need pnpm

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
uv python install 3.12

# OpenShell is a replaceable execution backend. The installer verifies the gateway AND an actual
# sandbox; a broken experimental WSL path is recorded but does not weaken kernel policy.
if ! command -v openshell >/dev/null 2>&1; then
  curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh
fi

# Build the deterministic Docker fallback image before testing OpenShell.
docker build -t soai-exec:latest -f infra/execution/Dockerfile infra/execution

OPENSHELL_HEALTH=unhealthy
if openshell status >/dev/null 2>&1; then
  if openshell sandbox create --no-keep --no-tty --policy "$ROOT/configs/openshell-policy.yaml" -- sh -lc 'printf soai-openshell-ok' >/tmp/soai-openshell-smoke.log 2>&1; then
    OPENSHELL_HEALTH=healthy
  else
    echo "WARNING: OpenShell CLI/gateway exists but sandbox smoke failed; Docker remains the hardened fallback." >&2
    cat /tmp/soai-openshell-smoke.log >&2 || true
  fi
else
  echo "WARNING: OpenShell gateway is not healthy on this WSL2 host; Docker remains the hardened fallback." >&2
fi
printf '%s\n' "$OPENSHELL_HEALTH" > "$SOAI_STATE_DIR/openshell-health.txt"

clone_or_update() {
  local url="$1" dir="$2"
  if [[ -d "$dir/.git" ]]; then git -C "$dir" pull --ff-only || true; else git clone --depth 1 "$url" "$dir"; fi
}

clone_or_update https://github.com/ggml-org/llama.cpp.git "$SOAI_RUNTIME_DIR/llama.cpp"
clone_or_update https://github.com/giannisanni/pulsar.git "$SOAI_RUNTIME_DIR/pulsar"
clone_or_update https://github.com/deepbeepmeep/Wan2GP.git "$SOAI_RUNTIME_DIR/Wan2GP"
clone_or_update https://github.com/deepseek-ai/deepseek-harness.git "$SOAI_RUNTIME_DIR/deepseek-harness"

# Harness is a developer preview, so build the exact checked-out commit and record it below.
# No plugin is granted kernel authority merely because it is discoverable by the harness.
(
  cd "$SOAI_RUNTIME_DIR/deepseek-harness"
  pnpm install --frozen-lockfile
  pnpm run build
)

# Build llama.cpp for Blackwell/CUDA. Exact generated kernels are tested later by llama_smoke.sh.
cmake -S "$SOAI_RUNTIME_DIR/llama.cpp" -B "$SOAI_RUNTIME_DIR/llama.cpp/build" -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release
cmake --build "$SOAI_RUNTIME_DIR/llama.cpp/build" --config Release -j "$(nproc)"

# Dedicated conversion environment: no dependency leakage into system Python.
CONV="$SOAI_ENV_DIR/llama-convert"
[[ -x "$CONV/bin/python" ]] || uv venv --python 3.12 "$CONV"
uv pip install --python "$CONV/bin/python" -U huggingface-hub transformers sentencepiece protobuf numpy safetensors
printf '%s\n' "$CONV/bin/python" > "$SOAI_STATE_DIR/llama-convert-python.txt"

SOAI_RUNTIME_DIR="$SOAI_RUNTIME_DIR" SOAI_STATE_DIR="$SOAI_STATE_DIR" python3 - <<'PY'
import json, os, subprocess, time
from pathlib import Path
runtime_dir = Path(os.environ['SOAI_RUNTIME_DIR'])
roots={name: runtime_dir / name for name in ('llama.cpp','pulsar','Wan2GP','deepseek-harness')}
lock={"generated_at":time.time(),"runtimes":{}}
for name,path in roots.items():
    try: rev=subprocess.check_output(['git','-C',path,'rev-parse','HEAD'],text=True).strip()
    except Exception: rev=None
    lock['runtimes'][name]={"path":str(Path(path).resolve()),"commit":rev}
Path(os.environ['SOAI_STATE_DIR'], 'runtime-lock.json').write_text(json.dumps(lock,indent=2))
PY

echo "WSL runtime layer installed. Lock: $SOAI_STATE_DIR/runtime-lock.json"
