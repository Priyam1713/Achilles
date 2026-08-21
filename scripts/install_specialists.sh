#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(pwd)}"
shift || true
PROFILE="core"
while (($#)); do
  case "$1" in
    --profile) PROFILE="${2:?--profile requires a value}"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
case "$PROFILE" in core|workstation|full) ;; *) echo "Unknown profile: $PROFILE" >&2; exit 2 ;; esac
cd "$ROOT"
source "$ROOT/scripts/runtime_env.sh"

# NVIDIA's wheel CDN can be slow for multi-hundred-megabyte CUDA artifacts.
# Keep resumable one-shot installs from failing on uv's short default timeout.
export UV_HTTP_TIMEOUT="${UV_HTTP_TIMEOUT:-600}"
export UV_HTTP_RETRIES="${UV_HTTP_RETRIES:-10}"
source "$ROOT/configs/runtime-sources.env"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
STATE="$SOAI_STATE_DIR"
ENVROOT="$SOAI_ENV_DIR"
SRCROOT="$SOAI_DATA_HOME/sources"
mkdir -p "$ENVROOT" "$SRCROOT" "$STATE"

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
uv python install 3.12
uv python install 3.11.14
TORCH_INDEX="${SOAI_TORCH_INDEX:-https://download.pytorch.org/whl/cu128}"

checkout_pinned() {
  local url="$1" name="$2" commit="$3" dir="$SRCROOT/$2"
  if [[ ! -d "$dir/.git" ]]; then git clone --filter=blob:none --no-checkout "$url" "$dir" >&2; fi
  if git -C "$dir" rev-parse --verify HEAD >/dev/null 2>&1; then
    git -C "$dir" diff --quiet && git -C "$dir" diff --cached --quiet || {
      echo "Refusing dirty specialist checkout: $dir" >&2; return 2;
    }
  fi
  for attempt in 1 2 3 4 5; do
    git -C "$dir" fetch --depth 1 origin "$commit" >&2 && break
    [[ "$attempt" == 5 ]] && return 1
    sleep "$((attempt * 2))"
  done
  git -C "$dir" checkout --detach --force "$commit" >&2
  [[ "$(git -C "$dir" rev-parse HEAD)" == "$commit" ]] || return 2
  printf '%s' "$dir"
}
make_env() { local name="$1" py="${2:-3.12}" env="$ENVROOT/$name"; [[ -x "$env/bin/python" ]] || uv venv --python "$py" "$env"; printf '%s' "$env"; }
install_torch() { uv pip install --python "$1/bin/python" --index-url "$TORCH_INDEX" torch torchvision torchaudio; }

failures=()
run_env() {
  local name="$1" fn="$2" env
  echo "==> specialist dependency island: $name"
  local py="3.12"; [[ "$name" == "vision" ]] && py="3.11.14"
  env="$(make_env "$name" "$py")"
  if [[ "$name" != "paddleocr" ]] && ! install_torch "$env"; then failures+=("$name:torch"); return 0; fi
  if ! "$fn" "$env"; then failures+=("$name:install"); return 0; fi
  if ! uv pip install --python "$env/bin/python" fastapi uvicorn httpx pydantic; then failures+=("$name:worker-api"); return 0; fi
  if ! uv pip check --python "$env/bin/python"; then failures+=("$name:dependency-check"); return 0; fi
  if [[ "$name" == "paddleocr" ]]; then
    if ! "$env/bin/python" - <<'PY'
import paddle
assert paddle.device.is_compiled_with_cuda(), 'Paddle CUDA unavailable'
print('paddleocr', paddle.__version__, paddle.device.get_device())
PY
    then failures+=("$name:cuda-smoke"); fi
  elif ! "$env/bin/python" - <<PY
import torch
assert torch.cuda.is_available(), 'CUDA unavailable'
print('$name', torch.__version__, torch.cuda.get_device_name(0))
PY
  then failures+=("$name:cuda-smoke"); fi
}

pip_retrieval(){ local e="$1"; uv pip install --python "$e/bin/python" 'sentence-transformers>=5,<6' 'transformers>=4.57' 'accelerate>=1.10' einops pillow qwen-vl-utils 'gliner2[local]' bitsandbytes fastapi uvicorn soundfile; }
pip_asr(){ local e="$1"; uv pip install --python "$e/bin/python" qwen-asr accelerate soundfile librosa openai-whisper; }
pip_voxcpm(){ local e="$1" s; s="$(checkout_pinned "$VOXCPM_URL" VoxCPM "$VOXCPM_COMMIT")"; uv pip install --python "$e/bin/python" -e "$s"; }
pip_moss(){ local e="$1" a d; a="$(checkout_pinned "$MOSS_AUDIO_URL" MOSS-Audio "$MOSS_AUDIO_COMMIT")"; d="$(checkout_pinned "$MOSS_TRANSCRIBE_URL" MOSS-Transcribe-Diarize "$MOSS_TRANSCRIBE_COMMIT")"; uv pip install --python "$e/bin/python" -e "$a"; uv pip install --python "$e/bin/python" -e "$d"; }
pip_paddle(){ local e="$1"; uv pip install --python "$e/bin/python" --index-url https://www.paddlepaddle.org.cn/packages/stable/cu126/ paddlepaddle-gpu==3.2.1; uv pip install --python "$e/bin/python" 'paddleocr[doc-parser]'; uv pip install --python "$e/bin/python" https://paddle-whl.bj.bcebos.com/nightly/cu126/safetensors/safetensors-0.6.2.dev0-cp38-abi3-linux_x86_64.whl; }
pip_vision(){ local e="$1" d; d="$(checkout_pinned "$DEPTH_ANYTHING_3_URL" Depth-Anything-3 "$DEPTH_ANYTHING_3_COMMIT")"; uv pip install --python "$e/bin/python" rfdetr; uv pip install --python "$e/bin/python" -e "$d"; }
pip_sam(){ local e="$1" s; s="$(checkout_pinned "$SAM3_URL" sam3 "$SAM3_COMMIT")"; uv pip install --python "$e/bin/python" -e "$s"; }
pip_uitars(){ local e="$1"; uv pip install --python "$e/bin/python" 'transformers>=4.57' accelerate pillow qwen-vl-utils bitsandbytes; }
pip_science(){ local e="$1"; uv pip install --python "$e/bin/python" chronos-forecasting esm scikit-learn xgboost catboost pandas polars duckdb; }
pip_tabpfn(){ local e="$1"; uv pip install --python "$e/bin/python" tabpfn; }
pip_fairchem(){ local e="$1"; uv pip install --python "$e/bin/python" fairchem-core; }
pip_med(){ local e="$1"; uv pip install --python "$e/bin/python" 'transformers>=4.57' accelerate pillow; }
pip_ace(){ local e="$1" s; s="$(checkout_pinned "$ACE_STEP_URL" ACE-Step-1.5 "$ACE_STEP_COMMIT")"; [[ -f "$s/pyproject.toml" ]] && uv pip install --python "$e/bin/python" -e "$s" || true; }

install_wangp() {
  local name="wangp"
  local env="$ENVROOT/$name"
  local src="$SOAI_RUNTIME_DIR/Wan2GP"
  echo "==> specialist dependency island: $name (upstream RTX20xx-50xx profile)"
  if [[ ! -f "$src/requirements.txt" ]]; then
    failures+=("wangp:runtime-source-missing")
    return 0
  fi
  uv python install 3.11.14
  [[ -x "$env/bin/python" ]] || uv venv --python 3.11.14 "$env"
  if ! uv pip install --python "$env/bin/python" --index-url https://download.pytorch.org/whl/cu130 \
      torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0; then
    failures+=("wangp:torch")
    return 0
  fi
  if ! uv pip install --python "$env/bin/python" -r "$src/requirements.txt"; then
    failures+=("wangp:upstream-requirements")
    return 0
  fi
  if ! uv pip install --python "$env/bin/python" fastapi uvicorn; then
    failures+=("wangp:worker-api")
    return 0
  fi
  if ! uv pip check --python "$env/bin/python"; then failures+=("wangp:dependency-check"); fi
  if ! "$env/bin/python" - <<'PYSMOKE'
import torch
assert torch.cuda.is_available(), 'CUDA unavailable'
print('wangp', torch.__version__, torch.cuda.get_device_name(0))
PYSMOKE
  then failures+=("wangp:cuda-smoke"); fi
}

run_env retrieval pip_retrieval
run_env qwen_asr pip_asr
run_env voxcpm pip_voxcpm
run_env paddleocr pip_paddle
run_env vision pip_vision
run_env ui_tars pip_uitars
run_env science_general pip_science
if [[ "$PROFILE" != core ]]; then
  run_env moss_audio pip_moss
  run_env sam pip_sam
  run_env tabpfn pip_tabpfn
  run_env medgemma pip_med
  run_env ace_step pip_ace
  install_wangp
fi
if [[ "$PROFILE" == full ]]; then
  run_env fairchem pip_fairchem
fi

FAIL_FILE="$STATE/worker-install-failures.txt"
: > "$FAIL_FILE"
for x in "${failures[@]:-}"; do [[ -n "$x" ]] && echo "$x" >> "$FAIL_FILE"; done
python3 - "$STATE" "$ENVROOT" "$SRCROOT" "$FAIL_FILE" <<'PY'
import json, sys, time
from pathlib import Path
state_dir, envroot, srcroot, fail_file = map(Path, sys.argv[1:])
failures=[x for x in fail_file.read_text().splitlines() if x.strip()]
state={"generated_at":time.time(),"env_root":str(envroot),"source_root":str(srcroot),"workers":{},"failures":failures}
if envroot.exists():
    for p in sorted(envroot.iterdir()):
        if (p/'bin/python').exists(): state['workers'][p.name]={"env":str(p)}
(state_dir/'worker-lock.json').write_text(json.dumps(state,indent=2))
PY

if ((${#failures[@]})); then
  printf 'Specialist install completed with %d issue(s):\n' "${#failures[@]}" >&2
  printf ' - %s\n' "${failures[@]}" >&2
  exit 2
fi
echo "Specialist dependency islands installed: $ENVROOT"
