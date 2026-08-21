"""Report real install state, derived from lock files, the filesystem and live probes.

FIXES.md F-020: docs/IMPLEMENTATION_STATUS.md used to hand-describe install state in
prose, which drifted from the actual machine within days -- it still listed model
download, the CUDA build and specialist environments as "still to be performed" work
after all three were long since done. This script never guesses: every line it prints
comes from a lock file this project already writes (model-lock.json, runtime-lock.json,
worker-lock.json), from `git rev-parse HEAD` in a runtime checkout, from a real
`Path.exists()`/directory listing against SOAI_MODEL_DIR, or from an actual TCP probe of
a declared port. If a claim isn't backed by one of those, it isn't printed.

Usage (inside WSL, where the install lives):

    source scripts/runtime_env.sh
    python3 scripts/doctor.py            # human-readable
    python3 scripts/doctor.py --json     # machine-readable
    python3 scripts/doctor.py --strict   # exit 1 if any issue was found (used by bootstrap.ps1)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from verify_host import declared_ports  # noqa: E402
from verify_sources import profile_ids  # noqa: E402


def _env_dir(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else default


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def git_head(path: Path) -> str | None:
    if not (path / ".git").exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else None


def tcp_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except OSError:
        return False


def check_runtimes(state_dir: Path) -> dict[str, Any]:
    lock = _load_json(state_dir / "runtime-lock.json")
    if lock is None:
        return {"status": "no runtime-lock.json -- runtimes not installed via this script"}
    report = {}
    for name, entry in lock.get("runtimes", {}).items():
        path = Path(entry["path"])
        actual = git_head(path)
        locked = entry.get("commit")
        report[name] = {
            "path": str(path),
            "present": path.exists(),
            "locked_commit": locked,
            "actual_commit": actual,
            "drifted": bool(actual and locked and actual != locked),
        }
    return report


def check_workers(state_dir: Path) -> dict[str, Any]:
    lock = _load_json(state_dir / "worker-lock.json")
    if lock is None:
        return {"status": "no worker-lock.json -- specialist workers not installed via this script"}
    report = {}
    for name, entry in lock.get("workers", {}).items():
        env = Path(entry["env"])
        report[name] = {"env": str(env), "present": env.exists()}
    failures = lock.get("failures") or []
    failures_file = state_dir / "worker-install-failures.txt"
    if failures_file.exists() and failures_file.stat().st_size > 0:
        failures = [*failures, failures_file.read_text(encoding="utf-8").strip()]
    return {"workers": report, "failures": failures}


def check_models(model_dir: Path, state_dir: Path, manifest_models: list[dict[str, Any]]) -> dict[str, Any]:
    lock = _load_json(state_dir / "model-lock.json")
    synced = (lock or {}).get("models", {})
    report = {}
    for model in manifest_models:
        if model.get("status") != "final" or model.get("source_type") == "none":
            continue
        model_id = model["id"]
        model_root = model_dir / model_id
        lock_entry = synced.get(model_id)
        needs_gguf = "llama_cpp" in (model.get("preferred_engines") or [])
        gguf_files = list((model_root / "gguf").glob("*.gguf")) if model_root.exists() else []
        report[model_id] = {
            "locked": lock_entry is not None,
            "on_disk": model_root.exists() and any(model_root.iterdir()) if model_root.exists() else False,
            "locked_revision": (lock_entry or {}).get("revision"),
            "needs_local_gguf": needs_gguf,
            "gguf_ready": bool(gguf_files) if needs_gguf else None,
        }
    return report


def check_openshell(state_dir: Path) -> str | None:
    health_file = state_dir / "openshell-health.txt"
    return health_file.read_text(encoding="utf-8").strip() if health_file.exists() else None


def check_services() -> dict[str, Any]:
    """Live TCP reachability of every port this install declares, not a hard-coded list.

    A hand-typed port/service list is exactly how this project once shipped a stale
    "search: 8888" entry that no config file had declared in months -- the same class of
    drift F-020 exists to close. `verify_host.declared_ports()` was already built for
    F-001/F-018/F-019 to read ports from configs/system.yaml, engines.yaml and
    workers.yaml instead of hard-coding them; reuse it here rather than re-deriving a
    second, divergent list.
    """
    report = {}
    for port, purpose in sorted(declared_ports().items()):
        report[str(port)] = {"purpose": purpose, "open": tcp_open("127.0.0.1", port)}
    return report


def check_environment() -> dict[str, Any]:
    info: dict[str, Any] = {
        "hf_token_set": bool(os.getenv("HF_TOKEN")),
        "nvidia_smi": bool(shutil.which("nvidia-smi")),
    }
    if info["nvidia_smi"]:
        try:
            info["gpu"] = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                text=True,
                timeout=4,
            ).strip()
        except (OSError, subprocess.SubprocessError) as exc:
            info["gpu_error"] = str(exc)
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", default=None)
    parser.add_argument("--state-dir", default=None)
    parser.add_argument(
        "--profile",
        choices=("core", "workstation", "full"),
        default="core",
        help="only models in this install profile count toward --strict issues; "
        "out-of-profile models are still listed, just not treated as missing",
    )
    parser.add_argument("--json", action="store_true", help="print the full report as JSON only")
    parser.add_argument(
        "--strict", action="store_true", help="exit 1 if any issue was found (used by bootstrap.ps1)"
    )
    args = parser.parse_args()

    home = Path.home()
    data_home = _env_dir("SOAI_DATA_HOME", home / ".local/share/sovereign-ai")
    model_dir = Path(args.model_dir) if args.model_dir else _env_dir("SOAI_MODEL_DIR", data_home / "models")
    state_dir = Path(args.state_dir) if args.state_dir else _env_dir("SOAI_STATE_DIR", data_home / "state")

    manifest = yaml.safe_load((REPO / "configs/models.yaml").read_text(encoding="utf-8"))["models"]
    local_manifest_path = REPO / "configs/models.local.yaml"
    if local_manifest_path.exists():
        local = yaml.safe_load(local_manifest_path.read_text(encoding="utf-8")) or {}
        by_id = {m["id"]: m for m in manifest}
        for m in local.get("models") or []:
            by_id[m["id"]] = m
        manifest = list(by_id.values())

    profiles = yaml.safe_load((REPO / "configs/install-profiles.yaml").read_text(encoding="utf-8"))["profiles"]
    # None means "every final model belongs to this profile" (e.g. `full`).
    in_profile = profile_ids(args.profile, profiles)

    def wanted(model_id: str) -> bool:
        return in_profile is None or model_id in in_profile

    report: dict[str, Any] = {
        "model_dir": str(model_dir),
        "state_dir": str(state_dir),
        "runtimes": check_runtimes(state_dir),
        "workers": check_workers(state_dir),
        "models": check_models(model_dir, state_dir, manifest),
        "openshell_health": check_openshell(state_dir),
        "services": check_services(),
        "environment": check_environment(),
    }

    issues: list[str] = []
    runtimes = report["runtimes"]
    if "status" in runtimes:
        issues.append(runtimes["status"])
    else:
        issues += [
            f"runtime {name} missing" for name, info in runtimes.items() if not info["present"]
        ]
        issues += [
            f"runtime {name} drifted from its lock" for name, info in runtimes.items() if info["drifted"]
        ]
    workers = report["workers"]
    if "status" in workers:
        issues.append(workers["status"])
    else:
        issues += [f"worker {name} missing" for name, info in workers["workers"].items() if not info["present"]]
        issues += [f"worker install failure: {f}" for f in workers["failures"]]
    issues += [
        f"model {model_id} not on disk (profile: {args.profile})"
        for model_id, info in report["models"].items()
        if not info["on_disk"] and wanted(model_id)
    ]
    issues += [
        f"model {model_id} missing gguf conversion"
        for model_id, info in report["models"].items()
        if info["needs_local_gguf"] and not info["gguf_ready"] and wanted(model_id)
    ]
    if report["openshell_health"] and report["openshell_health"] != "healthy":
        issues.append(f"openshell health: {report['openshell_health']}")
    report["issues"] = issues
    report["ok"] = not issues

    if args.json:
        print(json.dumps(report, indent=2))
        return 1 if args.strict and issues else 0

    print(f"model dir : {model_dir}")
    print(f"state dir : {state_dir}")
    print()

    print("-- runtimes --")
    if "status" in runtimes:
        print(f"  {runtimes['status']}")
    else:
        for name, info in runtimes.items():
            flag = "MISSING" if not info["present"] else ("DRIFTED" if info["drifted"] else "ok")
            print(f"  {name:20} {flag:8} locked={info['locked_commit']!r:44} actual={info['actual_commit']!r}")
    print()

    print("-- specialist workers --")
    if "status" in workers:
        print(f"  {workers['status']}")
    else:
        for name, info in workers["workers"].items():
            print(f"  {name:20} {'ok' if info['present'] else 'MISSING venv'}")
        if workers["failures"]:
            print(f"  failures recorded: {workers['failures']}")
    print()

    print(f"-- models (manifest status=final, profile={args.profile}) --")
    for model_id, info in report["models"].items():
        flags = []
        if not info["locked"]:
            flags.append("not locked")
        if not info["on_disk"]:
            flags.append("NOT ON DISK" if wanted(model_id) else "not on disk (out of profile)")
        if info["needs_local_gguf"] and not info["gguf_ready"] and wanted(model_id):
            flags.append("gguf conversion pending")
        print(f"  {model_id:34} {', '.join(flags) if flags else 'ready'}")
    print()

    print("-- declared services (live TCP probe) --")
    for port, info in report["services"].items():
        print(f"  {port:>6} {info['purpose']:28} {'open' if info['open'] else 'closed'}")
    print()

    env = report["environment"]
    print(f"HF_TOKEN set : {env['hf_token_set']}")
    print(f"nvidia-smi   : {env.get('gpu') or ('available' if env['nvidia_smi'] else 'not found')}")
    print(f"OpenShell    : {report['openshell_health'] or 'no openshell-health.txt found'}")

    if issues:
        print(f"\n{len(issues)} issue(s):")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\nNo issues found.")

    return 1 if args.strict and issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
