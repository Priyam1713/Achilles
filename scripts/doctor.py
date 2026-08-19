from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
STATE_ROOT = Path(os.getenv("SOAI_STATE_DIR", ROOT / "state")).expanduser()
MODEL_ROOT = Path(os.getenv("SOAI_MODEL_DIR", ROOT / "models")).expanduser()
RUNTIME_ROOT = Path(os.getenv("SOAI_RUNTIME_DIR", ROOT / "runtimes")).expanduser()


def tcp(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except OSError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    issues: list[str] = []
    info: dict[str, object] = {
        "paths": {
            "state": str(STATE_ROOT),
            "models": str(MODEL_ROOT),
            "runtimes": str(RUNTIME_ROOT),
        }
    }
    models = yaml.safe_load((ROOT / "configs/models.yaml").read_text())["models"]
    final = [model for model in models if model["status"] == "final"]
    info["final_models"] = len(final)
    info["manifest_models"] = len(models)

    locks = {}
    for name in ("runtime-lock.json", "model-lock.json", "worker-lock.json"):
        exists = (STATE_ROOT / name).exists()
        locks[name] = exists
        if not exists:
            issues.append(f"missing {STATE_ROOT / name}")
    info["locks"] = locks

    ggufs = {
        "qwen35-9b-Q6_K": MODEL_ROOT / "qwen35-9b/gguf/qwen35-9b-Q6_K.gguf",
        "qwen38-27b-UD-Q4_K_M": (
            MODEL_ROOT / "qwen38-27b/gguf/Qwen3.8-27B-UD-Q4_K_M.gguf"
        ),
        "qwen38-27b-MTP-Q4_0": (
            MODEL_ROOT / "qwen38-27b/gguf/MTP/mtp-Qwen3.8-27B-Q4_0.gguf"
        ),
        "qwen38-27b-mmproj-F16": MODEL_ROOT / "qwen38-27b/gguf/mmproj-F16.gguf",
    }
    info["ggufs"] = {key: path.exists() for key, path in ggufs.items()}
    for key, exists in info["ggufs"].items():
        if not exists:
            issues.append(f"missing quantized brain {key}")

    info["services"] = {
        "llama_router": tcp("127.0.0.1", 8080),
        "kernel": tcp("127.0.0.1", 7788),
        "search": tcp("127.0.0.1", 8888),
        "media": tcp("127.0.0.1", 7867),
    }
    info["hf_token"] = bool(os.getenv("HF_TOKEN"))
    info["nvidia_smi"] = bool(shutil.which("nvidia-smi"))
    if shutil.which("nvidia-smi"):
        try:
            info["gpu"] = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,driver_version",
                    "--format=csv,noheader",
                ],
                text=True,
                timeout=4,
            ).strip()
        except (OSError, subprocess.SubprocessError) as exc:
            info["gpu_error"] = str(exc)

    print(json.dumps({"ok": not issues, "info": info, "issues": issues}, indent=2))
    return 1 if args.strict and issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
