from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
from pathlib import Path

import psutil


def cmd(args):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT, timeout=8).strip()
    except Exception as e:
        return f"ERROR: {e}"


def gpu_info() -> dict:
    if not shutil.which("nvidia-smi"):
        return {"available": False}
    raw = cmd(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader,nounits",
        ]
    )
    if raw.startswith("ERROR:"):
        return {"available": False, "error": raw}
    first = raw.splitlines()[0]
    parts = [x.strip() for x in first.split(",")]
    try:
        mem = int(float(parts[1]))
    except Exception:
        mem = 0
    return {
        "available": True,
        "name": parts[0] if parts else None,
        "memory_total_mb": mem,
        "driver_version": parts[2] if len(parts) > 2 else None,
        "raw": raw,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict-target", action="store_true")
    ap.add_argument("--min-ram-gb", type=float, default=28.0)
    ap.add_argument("--min-vram-gb", type=float, default=11.0)
    ap.add_argument("--min-free-disk-gb", type=float, default=50.0)
    args = ap.parse_args()

    disk = psutil.disk_usage(Path.cwd().anchor or "/")
    ram_gb = psutil.virtual_memory().total / 2**30
    free_gb = disk.free / 2**30
    gpu = gpu_info()
    report = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "ram_gb": round(ram_gb, 2),
        "disk_free_gb": round(free_gb, 2),
        "gpu": gpu,
        "tools": {},
    }
    for tool in ["git", "docker", "wsl", "nvidia-smi", "cmake", "uv", "openshell"]:
        report["tools"][tool] = shutil.which(tool)
    if platform.system() == "Windows":
        report["wsl_status"] = cmd(["wsl", "--status"])

    issues: list[str] = []
    if args.strict_target:
        if platform.system() != "Windows":
            issues.append("target bootstrap expects Windows host")
        if not shutil.which("wsl"):
            issues.append("WSL2 command not found")
        if ram_gb < args.min_ram_gb:
            issues.append(f"RAM {ram_gb:.1f}GB < required {args.min_ram_gb:.1f}GB")
        if free_gb < args.min_free_disk_gb:
            issues.append(f"free disk {free_gb:.1f}GB < required {args.min_free_disk_gb:.1f}GB")
        if not gpu.get("available"):
            issues.append("NVIDIA GPU/nvidia-smi unavailable")
        elif gpu.get("memory_total_mb", 0) < int(args.min_vram_gb * 1024):
            issues.append(
                f"VRAM {gpu.get('memory_total_mb', 0) / 1024:.1f}GB < required {args.min_vram_gb:.1f}GB"
            )
    report["issues"] = issues
    report["ok"] = not issues
    print(json.dumps(report, indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
