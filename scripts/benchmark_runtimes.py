"""Compare GGUF inference engines with identical model-placement and benchmark inputs.

This is the engine half of the Local AI Olympics. It measures throughput and resource
pressure only; it never edits routing configuration and cannot promote a runtime. Model
quality is a separate gate because two engines can both load a GGUF while interpreting a
new architecture differently.

Usage inside WSL::

    source scripts/runtime_env.sh
    uv run python scripts/benchmark_runtimes.py --list
    uv run python scripts/benchmark_runtimes.py --only-model qwen38-27b-obliterated-iq4xs
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from statistics import median
from typing import Any

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from benchmark_brains import VramSampler  # noqa: E402


def _env_dir(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else default


def git_head(path: Path) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def build_argv(
    binary: Path,
    dialect: str,
    model: Path,
    gpu_layers: int,
    defaults: dict[str, Any],
) -> list[str]:
    if dialect not in {"upstream", "ik"}:
        raise ValueError(f"Unsupported runtime dialect: {dialect}")
    flash = "on" if dialect == "upstream" else "1"
    if not defaults.get("flash_attention", True):
        flash = "off" if dialect == "upstream" else "0"
    return [
        str(binary),
        "-m",
        str(model),
        "-p",
        str(defaults["n_prompt"]),
        "-n",
        str(defaults["n_gen"]),
        "-r",
        str(defaults["repetitions"]),
        "-b",
        str(defaults["batch_size"]),
        "-ub",
        str(defaults["ubatch_size"]),
        "-t",
        str(defaults["threads"]),
        "-ctk",
        str(defaults["cache_type_k"]),
        "-ctv",
        str(defaults["cache_type_v"]),
        "-ngl",
        str(gpu_layers),
        "-fa",
        flash,
        "-o",
        "json",
    ]


def parse_measurements(rows: list[dict[str, Any]]) -> dict[str, Any]:
    measurements: dict[str, Any] = {}
    identity: dict[str, Any] = {}
    for row in rows:
        n_prompt = int(row.get("n_prompt") or 0)
        n_gen = int(row.get("n_gen") or 0)
        key = f"pp{n_prompt}" if n_prompt else f"tg{n_gen}"
        samples = [float(value) for value in (row.get("samples_ts") or [])]
        measurements[key] = {
            "tokens_per_second": round(float(row.get("avg_ts") or 0.0), 4),
            "stddev_tokens_per_second": round(float(row.get("stddev_ts") or 0.0), 4),
            "median_tokens_per_second": round(median(samples), 4) if samples else 0.0,
            "min_tokens_per_second": round(min(samples), 4) if samples else 0.0,
            "max_tokens_per_second": round(max(samples), 4) if samples else 0.0,
            "samples_tokens_per_second": samples,
        }
        if not identity:
            identity = {
                key: row.get(key)
                for key in (
                    "model_type",
                    "model_size",
                    "model_n_params",
                    "n_gpu_layers",
                    "n_threads",
                    "type_k",
                    "type_v",
                    "flash_attn",
                )
            }
    return {"identity": identity, "measurements": measurements}


def gpu_snapshot() -> dict[str, Any] | None:
    """Capture enough device state to expose order/thermal bias in a long tournament."""
    fields = (
        "temperature.gpu",
        "power.draw",
        "clocks.sm",
        "clocks.mem",
        "memory.used",
        "memory.free",
    )
    proc = subprocess.run(
        [
            "nvidia-smi",
            f"--query-gpu={','.join(fields)}",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    values = [item.strip() for item in proc.stdout.splitlines()[0].split(",")]
    return dict(zip(fields, values, strict=False))


def host_available_memory_mb() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def telemetry_snapshot() -> dict[str, Any]:
    return {
        "gpu": gpu_snapshot(),
        "host_available_memory_mb": host_available_memory_mb(),
    }


def run_one(
    runtime: dict[str, Any],
    model: dict[str, Any],
    binary: Path,
    model_path: Path,
    defaults: dict[str, Any],
    timeout_s: int,
) -> dict[str, Any]:
    argv = build_argv(
        binary, runtime["dialect"], model_path, int(model["gpu_layers"]), defaults
    )
    started = time.time()
    telemetry_start = telemetry_snapshot()
    with VramSampler() as sampler:
        try:
            proc = subprocess.run(
                argv, capture_output=True, text=True, timeout=timeout_s, check=False
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "argv": argv,
                "elapsed_s": round(time.time() - started, 2),
                "vram_peak_mb": sampler.peak_mb,
                "telemetry_start": telemetry_start,
                "telemetry_end": telemetry_snapshot(),
            }
        peak = sampler.peak_mb

    base = {
        "argv": argv,
        "elapsed_s": round(time.time() - started, 2),
        "vram_peak_mb": peak,
        "telemetry_start": telemetry_start,
        "telemetry_end": telemetry_snapshot(),
    }
    if proc.returncode != 0:
        return {
            **base,
            "status": "failed",
            "returncode": proc.returncode,
            "stderr_tail": proc.stderr.splitlines()[-30:],
        }
    try:
        rows = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return {
            **base,
            "status": "unparsable",
            "error": str(exc),
            "stdout_tail": proc.stdout.splitlines()[-30:],
        }
    if not isinstance(rows, list):
        return {**base, "status": "unparsable", "error": "expected a JSON row list"}
    return {**base, "status": "ok", **parse_measurements(rows)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(REPO / "configs/runtime-tournament.yaml"))
    parser.add_argument("--only-runtime", action="append")
    parser.add_argument("--only-model", action="append")
    parser.add_argument("--runtime-dir")
    parser.add_argument("--model-dir")
    parser.add_argument("--state-dir")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--list", action="store_true", help="resolve candidates; run nothing")
    parser.add_argument(
        "--reverse-cells",
        action="store_true",
        help="reverse the model/runtime cell order for a counterbalanced follow-up pass",
    )
    args = parser.parse_args()

    home = Path.home()
    data_home = _env_dir("SOAI_DATA_HOME", home / ".local/share/sovereign-ai")
    runtime_dir = Path(args.runtime_dir) if args.runtime_dir else _env_dir(
        "SOAI_RUNTIME_DIR", data_home / "runtimes"
    )
    model_dir = Path(args.model_dir) if args.model_dir else _env_dir(
        "SOAI_MODEL_DIR", data_home / "models"
    )
    state_dir = Path(args.state_dir) if args.state_dir else _env_dir(
        "SOAI_STATE_DIR", data_home / "state"
    )
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    defaults = config["defaults"]

    runtimes = [
        item
        for item in config["runtimes"]
        if not args.only_runtime or item["id"] in args.only_runtime
    ]
    models = [
        item
        for item in config["models"]
        if not args.only_model or item["id"] in args.only_model
    ]
    resolved_runtimes = {
        item["id"]: runtime_dir / item["binary"] for item in runtimes
    }
    resolved_models = {item["id"]: model_dir / item["path"] for item in models}

    print(f"runtime dir: {runtime_dir}")
    print(f"model dir  : {model_dir}")
    for item in runtimes:
        binary = resolved_runtimes[item["id"]]
        print(f"  runtime {item['id']:20} {'ready' if binary.is_file() else 'MISSING'}  {binary}")
    for item in models:
        path = resolved_models[item["id"]]
        print(f"  model   {item['id']:38} {'ready' if path.is_file() else 'MISSING'}  ngl={item['gpu_layers']}")
    if args.list:
        return 0

    cells = [(model, runtime) for model in models for runtime in runtimes]
    if args.reverse_cells:
        cells.reverse()
    execution_order = [
        {"model_id": model["id"], "runtime_id": runtime["id"]}
        for model, runtime in cells
    ]

    results: list[dict[str, Any]] = []
    for cell_index, (model, runtime) in enumerate(cells):
        model_path = resolved_models[model["id"]]
        binary = resolved_runtimes[runtime["id"]]
        record = {
            "cell_index": cell_index,
            "runtime_id": runtime["id"],
            "runtime_label": runtime["label"],
            "runtime_status": runtime["status"],
            "runtime_commit": git_head(runtime_dir / runtime["checkout"]),
            "model_id": model["id"],
            "model_label": model["label"],
            "model_path": str(model_path),
            "model_bytes": model_path.stat().st_size if model_path.is_file() else None,
        }
        if not binary.is_file() or not model_path.is_file():
            record.update(status="skipped", reason="binary or model missing")
        else:
            print(f"\n==> {runtime['id']} / {model['id']}", flush=True)
            record.update(
                run_one(runtime, model, binary, model_path, defaults, args.timeout)
            )
        results.append(record)

    host_gpu = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version,power.limit",
            "--format=csv,noheader",
        ],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    report = {
        "generated_at": time.time(),
        "host_gpu": host_gpu,
        "defaults": defaults,
        "execution_order": execution_order,
        "reverse_cells": args.reverse_cells,
        "promotion_gates": config.get("promotion_gates", {}),
        "results": results,
        "promotion_performed": False,
    }
    state_dir.mkdir(parents=True, exist_ok=True)
    out = state_dir / "runtime-tournament.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\nRuntime results")
    print(f"{'runtime':20} {'model':38} {'pp tok/s':>10} {'tg tok/s':>10} {'VRAM':>8}")
    print("-" * 94)
    for record in results:
        if record["status"] != "ok":
            print(f"{record['runtime_id']:20} {record['model_id']:38} {record['status']:>10}")
            continue
        pp = record["measurements"].get(f"pp{defaults['n_prompt']}", {}).get(
            "tokens_per_second", 0
        )
        tg = record["measurements"].get(f"tg{defaults['n_gen']}", {}).get(
            "tokens_per_second", 0
        )
        print(
            f"{record['runtime_id']:20} {record['model_id']:38} "
            f"{pp:>10.2f} {tg:>10.2f} {record['vram_peak_mb']!s:>8}"
        )
    print("\nThis is throughput evidence only. Quality/stability remain separate gates.")
    print(f"Report: {out}")
    return 1 if any(item["status"] in {"failed", "timeout", "unparsable"} for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
