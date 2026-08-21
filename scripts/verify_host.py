from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

import psutil
import yaml

REPO = Path(__file__).resolve().parent.parent


def declared_ports() -> dict[int, str]:
    """Every TCP port this installation intends to own, read from config, not hard-coded.

    Hard-coding this list is how the 2026-08-19 audit ended up asserting a port collision
    that did not exist (FIXES.md F-001). The check must read the same files the runtime
    reads, so it cannot drift from what actually gets bound.
    """
    ports: dict[int, str] = {}

    def load(rel: str) -> dict:
        path = REPO / rel
        return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}

    system = load("configs/system.yaml").get("system", {})
    if system.get("port"):
        ports[int(system["port"])] = "sovereign kernel API"

    for engine_id, spec in (load("configs/engines.yaml").get("engines") or {}).items():
        for key in ("base_url", "health_url"):
            url = (spec or {}).get(key)
            if not url:
                continue
            try:
                port = int(url.split("://", 1)[1].split("/", 1)[0].rsplit(":", 1)[1])
            except (IndexError, ValueError):
                continue
            ports.setdefault(port, f"engine:{engine_id}")

    for worker, spec in (load("configs/workers.yaml").get("workers") or {}).items():
        if (spec or {}).get("port"):
            ports.setdefault(int(spec["port"]), f"worker:{worker}")

    compose = REPO / "infra/docker-compose.yml"
    if compose.exists():
        for service, spec in (yaml.safe_load(compose.read_text(encoding="utf-8")).get(
            "services"
        ) or {}).items():
            for mapping in (spec or {}).get("ports", []):
                parts = str(mapping).split(":")
                if len(parts) >= 2:
                    try:
                        ports.setdefault(int(parts[-2]), f"container:{service}")
                    except ValueError:
                        pass
    return ports


def _host_listeners() -> tuple[dict[int, list[dict]], str | None]:
    listeners: dict[int, list[dict]] = {}
    try:
        for conn in psutil.net_connections(kind="tcp"):
            if conn.status != psutil.CONN_LISTEN or not conn.laddr:
                continue
            namespace = "windows" if platform.system() == "Windows" else "local"
            entry = {"pid": conn.pid, "address": conn.laddr.ip, "namespace": namespace}
            try:
                entry["process"] = psutil.Process(conn.pid).name() if conn.pid else None
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                entry["process"] = None
            listeners.setdefault(conn.laddr.port, []).append(entry)
    except (psutil.AccessDenied, PermissionError) as exc:
        return {}, f"cannot enumerate host listeners: {exc}"
    return listeners, None


def _wsl_listeners(distro: str = "Ubuntu-24.04") -> tuple[dict[int, list[dict]], str | None]:
    """Enumerate listeners *inside* WSL2.

    This function exists because of a real mistake (FIXES.md F-001). WSL2 runs its own
    network namespace: a process bound to 127.0.0.1 inside the distro is invisible to
    Get-NetTCPConnection / psutil on the Windows host. Checking only the host and
    concluding "the port is free" is not a weaker check, it is the wrong check -- most of
    this project's services run inside WSL, so that is where collisions actually happen.
    """
    if not shutil.which("wsl"):
        return {}, None
    try:
        raw = subprocess.check_output(
            ["wsl", "-d", distro, "--", "ss", "-ltnpH"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    except Exception as exc:
        return {}, f"cannot enumerate WSL listeners: {exc}"

    listeners: dict[int, list[dict]] = {}
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        local = parts[3]
        if ":" not in local:
            continue
        try:
            port = int(local.rsplit(":", 1)[1])
        except ValueError:
            continue
        process = None
        pid = None
        if 'users:(("' in line:
            tail = line.split('users:(("', 1)[1]
            process = tail.split('"', 1)[0]
            if "pid=" in tail:
                try:
                    pid = int(tail.split("pid=", 1)[1].split(",", 1)[0])
                except ValueError:
                    pass
        listeners.setdefault(port, []).append(
            {
                "pid": pid,
                "process": process,
                "address": local.rsplit(":", 1)[0],
                "namespace": f"wsl:{distro}",
            }
        )
    return listeners, None


def port_report(distro: str = "Ubuntu-24.04") -> dict:
    """Report what is actually listening, so ownership is measured rather than assumed.

    Covers BOTH the Windows host and the WSL2 namespace. A foreign listener is not
    automatically a failure -- it is a fact the installer must act on. The rule this
    enforces: never adopt, overwrite or stop a service we do not own.
    """
    host, host_err = _host_listeners()
    wsl, wsl_err = _wsl_listeners(distro)

    merged: dict[int, list[dict]] = {}
    for source in (host, wsl):
        for port, entries in source.items():
            merged.setdefault(port, []).extend(entries)

    declared = declared_ports()
    result: dict[str, Any] = {
        "errors": [e for e in (host_err, wsl_err) if e],
        "declared": {},
        # The neighbourhood matters too: an adjacent service we might collide with after a
        # config change is worth seeing before the install, not after.
        "other_occupied": {
            port: entries
            for port, entries in sorted(merged.items())
            if port not in declared and port < 40000
        },
    }
    for port, purpose in sorted(declared.items()):
        found = merged.get(port, [])
        result["declared"][port] = {
            "purpose": purpose,
            "state": "occupied" if found else "free",
            "listeners": found,
        }
    return result


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
    ap.add_argument(
        "--check-ports",
        action="store_true",
        help="report which declared service ports are already occupied, and by what",
    )
    ap.add_argument(
        "--fail-on-foreign-port",
        action="store_true",
        help="exit non-zero if any declared port is held by a process we did not start",
    )
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
    if args.check_ports or args.fail_on_foreign_port:
        ports = port_report()
        report["ports"] = ports
        occupied = [
            f"port {port} ({info['purpose']}) held by "
            + ", ".join(
                f"{listener.get('process') or 'unknown'}#{listener.get('pid')}"
                f"@{listener.get('namespace')}"
                for listener in info["listeners"]
            )
            for port, info in ports["declared"].items()
            if info.get("state") == "occupied"
        ]
        report["occupied_ports"] = occupied
        issues.extend(ports["errors"])
        if args.fail_on_foreign_port:
            issues.extend(occupied)

    report["issues"] = issues
    report["ok"] = not issues
    print(json.dumps(report, indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
