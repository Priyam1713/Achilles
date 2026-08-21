"""Measure candidate general brains on this exact machine.

Answers F-005 and D-012: dense versus sparse-active hybrid MoE on 12 GB of VRAM.

This script produces *evidence*. It never edits `configs/models.yaml`, never changes a
route, and never promotes anything -- consistent with the project rule that discovery is
separate from promotion. A human reads the report.

Usage (inside WSL, where the runtimes live):

    source scripts/runtime_env.sh
    python3 scripts/benchmark_brains.py --list
    python3 scripts/benchmark_brains.py --only qwen38-27b-q4km
    python3 scripts/benchmark_brains.py            # every resolvable candidate
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parent.parent


def _env_dir(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else default


class VramSampler:
    """Polls nvidia-smi in the background so we capture peak usage, not a final reading.

    A model that fits only because the benchmark ended is not a model that fits.
    """

    def __init__(self, interval: float = 0.4):
        self.interval = interval
        self.samples: list[int] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                out = subprocess.check_output(
                    [
                        "nvidia-smi",
                        "--query-gpu=memory.used",
                        "--format=csv,noheader,nounits",
                    ],
                    text=True,
                    timeout=5,
                )
                self.samples.append(int(out.strip().splitlines()[0]))
            except Exception:
                pass
            self._stop.wait(self.interval)

    def __enter__(self) -> VramSampler:
        if shutil.which("nvidia-smi"):
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    @property
    def peak_mb(self) -> int | None:
        return max(self.samples) if self.samples else None


def reserve_vram_mb() -> int:
    """Single source of truth for VRAM headroom (FIXES.md F-009).

    The scheduler, the llama.cpp preset and this benchmark must not each invent a number.
    """
    system = yaml.safe_load((REPO / "configs/system.yaml").read_text(encoding="utf-8"))
    return int(system.get("resources", {}).get("reserve_vram_mb", 1600))


def _flag(value: Any) -> str:
    """YAML turns bare `on`/`off` into booleans; llama.cpp wants the words back.

    Silently sending `-fa True` is exactly the kind of failure that looks like a model
    problem and is actually a config problem, so normalise it at the boundary.
    """
    if isinstance(value, bool):
        return "on" if value else "off"
    return str(value)


def build_argv(
    binary: Path, model: Path, defaults: dict[str, Any], variant: dict[str, Any]
) -> list[str]:
    fit_target = defaults.get("fit_target_mb") or reserve_vram_mb()
    argv = [
        str(binary),
        "-m",
        str(model),
        "-p",
        str(defaults["n_prompt"]),
        "-n",
        str(defaults["n_gen"]),
        "-r",
        str(defaults["repetitions"]),
        "-fa",
        _flag(defaults["flash_attn"]),
        "-ctk",
        _flag(defaults["cache_type_k"]),
        "-ctv",
        _flag(defaults["cache_type_v"]),
        # Let llama.cpp decide the layer split against a declared memory margin rather than
        # hard-coding -ngl. The margin is the thing we actually have a policy about.
        "-fitt",
        str(fit_target),
        "-fitc",
        str(defaults["n_ctx_fit"]),
        "-o",
        "json",
    ]
    if variant.get("n_cpu_moe") is not None:
        argv += ["-ncmoe", str(variant["n_cpu_moe"])]
    return argv


def run_one(
    binary: Path, model: Path, defaults: dict[str, Any], variant: dict[str, Any], timeout: int
) -> dict[str, Any]:
    # llama-bench cannot drive a draft model: speculative decoding lives in llama-server
    # and llama-speculative. Report that honestly instead of silently measuring the
    # base model and labelling the result as the MTP candidate.
    if variant.get("draft"):
        return {
            "status": "requires-server-mode",
            "reason": (
                "llama-bench has no --model-draft; speculative/MTP variants must be "
                "measured through llama-server. See scripts/benchmark_qwen38_mtp.py."
            ),
            "draft": str(variant["draft"]),
        }
    argv = build_argv(binary, model, defaults, variant)
    started = time.time()
    with VramSampler() as sampler:
        try:
            proc = subprocess.run(
                argv, capture_output=True, text=True, timeout=timeout, check=False
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "argv": argv,
                "elapsed_s": round(time.time() - started, 1),
                "vram_peak_mb": sampler.peak_mb,
            }
        peak = sampler.peak_mb

    elapsed = round(time.time() - started, 1)
    if proc.returncode != 0:
        return {
            "status": "failed",
            "argv": argv,
            "returncode": proc.returncode,
            "elapsed_s": elapsed,
            "vram_peak_mb": peak,
            "stderr_tail": proc.stderr.strip().splitlines()[-15:],
        }

    try:
        rows = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "status": "unparsable",
            "argv": argv,
            "elapsed_s": elapsed,
            "vram_peak_mb": peak,
            "stdout_tail": proc.stdout.strip().splitlines()[-15:],
        }

    measurements: dict[str, dict[str, float]] = {}
    for row in rows:
        n_prompt = int(row.get("n_prompt") or 0)
        n_gen = int(row.get("n_gen") or 0)
        key = f"pp{n_prompt}" if n_prompt else f"tg{n_gen}"
        measurements[key] = {
            "tokens_per_second": round(float(row.get("avg_ts") or 0), 2),
            "stddev_ts": round(float(row.get("stddev_ts") or 0), 2),
            "n_gpu_layers": row.get("n_gpu_layers"),
            "n_cpu_moe": row.get("n_cpu_moe"),
        }
    return {
        "status": "ok",
        "argv": argv,
        "elapsed_s": elapsed,
        "vram_peak_mb": peak,
        "measurements": measurements,
    }


def expand(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    """One candidate may declare a sweep; each sweep point is its own measured variant."""
    sweep = candidate.get("n_cpu_moe")
    if sweep is None:
        return [{"suffix": "", "n_cpu_moe": None, "draft": candidate.get("_draft_path")}]
    if not isinstance(sweep, list):
        sweep = [sweep]
    return [
        {
            "suffix": f"@ncmoe{value}",
            "n_cpu_moe": value,
            "draft": candidate.get("_draft_path"),
        }
        for value in sweep
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(REPO / "configs/brain-candidates.yaml"))
    parser.add_argument("--model-dir", default=None)
    parser.add_argument("--state-dir", default=None)
    parser.add_argument("--llama-bench", default=None)
    parser.add_argument("--only", action="append", help="candidate id (repeatable)")
    parser.add_argument("--timeout", type=int, default=2400, help="per-variant seconds")
    parser.add_argument("--list", action="store_true", help="resolve and report, run nothing")
    args = parser.parse_args()

    home = Path.home()
    data_home = _env_dir("SOAI_DATA_HOME", home / ".local/share/sovereign-ai")
    model_dir = Path(args.model_dir) if args.model_dir else _env_dir(
        "SOAI_MODEL_DIR", data_home / "models"
    )
    state_dir = Path(args.state_dir) if args.state_dir else _env_dir(
        "SOAI_STATE_DIR", data_home / "state"
    )
    runtime_dir = _env_dir("SOAI_RUNTIME_DIR", data_home / "runtimes")
    binary = Path(args.llama_bench) if args.llama_bench else (
        runtime_dir / "llama.cpp/build/bin/llama-bench"
    )

    if not binary.exists():
        print(f"FATAL: llama-bench not found at {binary}", file=sys.stderr)
        print("Build llama.cpp first (scripts/install_wsl_runtimes.sh).", file=sys.stderr)
        return 2

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    defaults = config["defaults"]
    gates = config.get("promotion_gates", {})

    selected = []
    for candidate in config["candidates"]:
        if args.only and candidate["id"] not in args.only:
            continue
        model_path = model_dir / candidate["model"]
        draft_path = model_dir / candidate["draft"] if candidate.get("draft") else None
        missing = []
        if not model_path.exists():
            missing.append(str(model_path))
        if draft_path and not draft_path.exists():
            missing.append(str(draft_path))
        candidate["_model_path"] = model_path
        candidate["_draft_path"] = draft_path
        candidate["_missing"] = missing
        selected.append(candidate)

    print(f"llama-bench : {binary}")
    print(f"model dir   : {model_dir}")
    print(f"fit target  : {defaults.get('fit_target_mb') or reserve_vram_mb()} MiB reserved")
    print()
    for candidate in selected:
        state = "SKIP (files absent)" if candidate["_missing"] else "ready"
        gate = candidate.get("licence_gate")
        gate_note = f"  [licence gate: {gate}]" if gate else ""
        print(f"  {candidate['id']:34} {state}{gate_note}")
    print()

    if args.list:
        return 0

    runnable = [c for c in selected if not c["_missing"]]
    if not runnable:
        print("Nothing resolvable to benchmark.", file=sys.stderr)
        return 1

    results: list[dict[str, Any]] = []
    for candidate in runnable:
        for variant in expand(candidate):
            name = f"{candidate['id']}{variant['suffix']}"
            print(f"==> {name}", flush=True)
            outcome = run_one(
                binary, candidate["_model_path"], defaults, variant, args.timeout
            )
            record = {
                "id": name,
                "candidate_id": candidate["id"],
                "label": candidate["label"],
                "family": candidate.get("family"),
                "licence_gate": candidate.get("licence_gate"),
                "n_cpu_moe": variant["n_cpu_moe"],
                "draft": str(variant["draft"]) if variant["draft"] else None,
                **outcome,
            }
            results.append(record)
            if outcome["status"] == "ok":
                tg = outcome["measurements"].get(f"tg{defaults['n_gen']}", {})
                pp = outcome["measurements"].get(f"pp{defaults['n_prompt']}", {})
                print(
                    f"    tg {tg.get('tokens_per_second')} tok/s | "
                    f"pp {pp.get('tokens_per_second')} tok/s | "
                    f"peak VRAM {outcome['vram_peak_mb']} MiB | "
                    f"ngl {tg.get('n_gpu_layers')}",
                    flush=True,
                )
            else:
                print(f"    {outcome['status']}", flush=True)

    report = {
        "generated_at": time.time(),
        "host": {
            "gpu": subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                 "--format=csv,noheader"],
                capture_output=True, text=True, check=False,
            ).stdout.strip(),
            "llama_bench": str(binary),
        },
        "defaults": defaults,
        "promotion_gates": gates,
        "results": results,
        "skipped": [
            {"id": c["id"], "missing": c["_missing"]} for c in selected if c["_missing"]
        ],
        # Explicitly recorded so no downstream tool can mistake evidence for a decision.
        "promotion_performed": False,
    }
    state_dir.mkdir(parents=True, exist_ok=True)
    out = state_dir / "brain-benchmark.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print(f"{'candidate':40} {'tg tok/s':>10} {'pp tok/s':>10} {'VRAM MiB':>10}  gates")
    print("-" * 88)
    min_tg = float(gates.get("min_tg_tokens_per_second", 0))
    max_vram = float(gates.get("max_vram_peak_mb", 1e9))
    for record in results:
        if record["status"] != "ok":
            print(f"{record['id']:40} {record['status']:>10}")
            continue
        tg = record["measurements"].get(f"tg{defaults['n_gen']}", {}).get("tokens_per_second", 0)
        pp = record["measurements"].get(f"pp{defaults['n_prompt']}", {}).get("tokens_per_second", 0)
        peak = record["vram_peak_mb"] or 0
        flags = []
        if tg < min_tg:
            flags.append(f"tg<{min_tg}")
        if peak > max_vram:
            flags.append("vram")
        if record.get("licence_gate"):
            flags.append("licence")
        verdict = ",".join(flags) if flags else "speed gates pass"
        print(f"{record['id']:40} {tg:>10} {pp:>10} {peak:>10}  {verdict}")
    print()
    print("Throughput is necessary, not sufficient. Quality evaluation and licence review")
    print("are separate gates. Nothing has been promoted.")
    print(f"Report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
