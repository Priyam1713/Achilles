from __future__ import annotations

import csv
import shutil
import subprocess
import time
from pathlib import Path

import psutil

from sovereign_ai.kernel.types import ResourceSnapshot


def _nvidia_snapshot() -> tuple[str | None, int, int, int]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None, 0, 0, 0
    cmd = [
        exe,
        "--query-gpu=name,memory.total,memory.used,memory.free",
        "--format=csv,noheader,nounits",
    ]
    try:
        output = subprocess.check_output(cmd, text=True, timeout=5).strip().splitlines()[0]
        row = next(csv.reader([output]))
        name = row[0].strip()
        total, used, free = (int(float(v.strip())) for v in row[1:4])
        return name, total, used, free
    except Exception:
        return None, 0, 0, 0


def snapshot(path: str | Path = ".") -> ResourceSnapshot:
    gpu_name, vtotal, vused, vfree = _nvidia_snapshot()
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage(str(Path(path).resolve().anchor or "/"))
    mb = 1024 * 1024
    gb = 1024 * 1024 * 1024
    return ResourceSnapshot(
        timestamp=time.time(),
        gpu_name=gpu_name,
        vram_total_mb=vtotal,
        vram_used_mb=vused,
        vram_free_mb=vfree,
        ram_total_mb=int(vm.total / mb),
        ram_used_mb=int(vm.used / mb),
        ram_free_mb=int(vm.available / mb),
        disk_total_gb=round(disk.total / gb, 2),
        disk_free_gb=round(disk.free / gb, 2),
    )
