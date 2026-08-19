from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

from .base import ExecutionBackend, ExecutionResult
from .staging import reconcile_workspace, snapshot_tree, validate_tree


class DockerBackend(ExecutionBackend):
    """Transactional restrictive fallback when OpenShell is unhealthy.

    The host workspace is never mounted directly. A verified copy is mounted into a no-network,
    capability-dropped container; successful mutating runs are reconciled back transactionally.
    Failed commands simply discard the staged tree.
    """

    def __init__(self, image: str = "soai-exec:latest"):
        self.image = image
        self._windows_wsl = os.name == "nt" and shutil.which("wsl") is not None

    def _wsl_docker_ok(self) -> bool:
        if not self._windows_wsl:
            return False
        try:
            subprocess.check_call(
                ["wsl", "sh", "-lc", "docker version >/dev/null 2>&1"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=6,
            )
            return True
        except Exception:
            return False

    @staticmethod
    def _native_docker_healthy() -> bool:
        if shutil.which("docker") is None:
            return False
        try:
            subprocess.check_call(
                ["docker", "version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=6,
            )
            return True
        except Exception:
            return False

    def available(self) -> bool:
        return self._native_docker_healthy() or self._wsl_docker_ok()

    def _wsl_path(self, path: Path) -> str:
        return subprocess.check_output(
            ["wsl", "wslpath", "-a", str(path)], text=True, timeout=5
        ).strip()

    async def run(
        self,
        argv: Sequence[str],
        cwd: str | None = None,
        *,
        sync_back: bool = True,
    ) -> ExecutionResult:
        if not self.available():
            raise RuntimeError("Docker CLI/daemon not installed or healthy")
        if cwd is None:
            raise ValueError("Docker execution requires an explicit workspace")

        workspace = Path(cwd).resolve(strict=True)
        validate_tree(workspace)
        before = snapshot_tree(workspace) if sync_back else None

        use_wsl = self._windows_wsl and not self._native_docker_healthy()
        base = ["wsl", "docker"] if use_wsl else ["docker"]
        backend = "docker-wsl2" if use_wsl else "docker"

        with tempfile.TemporaryDirectory(prefix="soai-docker-stage-") as tmp:
            staged = Path(tmp) / "workspace"
            shutil.copytree(workspace, staged, symlinks=True)
            validate_tree(staged)
            mount = self._wsl_path(staged) if use_wsl else str(staged)
            cmd = [
                *base,
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--pids-limit",
                "256",
                "--memory",
                "4g",
                "--cpus",
                "2",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=512m",
                "--tmpfs",
                "/home/sandbox:rw,nosuid,size=512m",
                "-v",
                f"{mount}:/workspace:rw",
                "-w",
                "/workspace",
                self.image,
                *argv,
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            rc = proc.returncode
            if rc == 0 and sync_back:
                stats = reconcile_workspace(workspace, staged, before or {})
                stdout += (
                    f"\n[sovereign-kernel] committed workspace transaction: "
                    f"+{stats['created']} ~{stats['modified']} -{stats['deleted']}\n"
                ).encode()
            return ExecutionResult(
                rc,
                stdout.decode(errors="replace"),
                stderr.decode(errors="replace"),
                backend,
            )
