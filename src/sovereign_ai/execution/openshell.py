from __future__ import annotations

import asyncio
import os
import secrets
import shlex
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

from .base import ExecutionBackend, ExecutionResult
from .staging import reconcile_workspace, snapshot_tree


class OpenShellBackend(ExecutionBackend):
    """High-assurance OpenShell adapter.

    OpenShell's current host-workspace contract is copy-in/copy-out rather than a live
    bind mount. Mutating commands therefore execute as an optimistic filesystem
    transaction: snapshot -> upload -> run -> download -> concurrent-edit check -> commit.
    Failed sandbox commands never mutate the host workspace.
    """

    def __init__(self, policy_path: str = "configs/openshell-policy.yaml"):
        self.policy_path = str(Path(policy_path).resolve())
        self._windows_wsl = os.name == "nt" and shutil.which("wsl") is not None

    def _wsl_path(self, path: str) -> str:
        return subprocess.check_output(["wsl", "wslpath", "-a", path], text=True, timeout=5).strip()

    def _prefix(self) -> list[str]:
        # On Windows the supported architecture is the WSL2 Linux plane. Never
        # silently switch to a native Windows CLI just because one happens to be
        # on PATH; that would change path/policy semantics under the kernel.
        if self._windows_wsl:
            return ["wsl"]
        return []

    def _host_path_for_cli(self, path: str | Path) -> str:
        raw = str(Path(path).resolve())
        if self._windows_wsl:
            return self._wsl_path(raw)
        return raw

    def _sync_status_ok(self) -> bool:
        prefix = self._prefix()
        try:
            subprocess.check_call(
                [*prefix, "openshell", "status"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
            )
            return True
        except Exception:
            return False

    def available(self) -> bool:
        if self._windows_wsl:
            try:
                subprocess.check_call(
                    ["wsl", "sh", "-lc", "command -v openshell >/dev/null 2>&1"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                )
                return self._sync_status_ok()
            except Exception:
                return False
        if shutil.which("openshell") is not None:
            return self._sync_status_ok()
        return False

    async def _cli(self, *args: str) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            *self._prefix(),
            "openshell",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode(errors="replace"), stderr.decode(errors="replace")

    async def run(
        self,
        argv: Sequence[str],
        cwd: str | None = None,
        *,
        sync_back: bool = True,
    ) -> ExecutionResult:
        if not self.available():
            raise RuntimeError("OpenShell CLI/gateway is not installed or healthy")
        if cwd is None:
            raise ValueError("OpenShell execution requires an explicit workspace")

        workspace = Path(cwd).resolve(strict=True)
        if not workspace.is_dir():
            raise ValueError(f"Workspace is not a directory: {workspace}")

        before = snapshot_tree(workspace) if sync_back else None
        sandbox = f"soai-{secrets.token_hex(5)}"  # short names avoid driver/name edge cases.
        policy = self._host_path_for_cli(self.policy_path)
        source = self._host_path_for_cli(workspace)
        command = f"cd /workspace/project && exec {shlex.join(list(argv))}"
        backend = "openshell-wsl2" if self._prefix() else "openshell"

        # Keep the sandbox only long enough to retrieve successful mutations.
        create_args = [
            "sandbox",
            "create",
            "--name",
            sandbox,
            "--no-tty",
            "--policy",
            policy,
            "--upload",
            f"{source}:/workspace/project",
            "--no-git-ignore",
            "--",
            "sh",
            "-lc",
            command,
        ]
        if not sync_back:
            create_args.insert(2, "--no-keep")

        rc = -1
        stdout = ""
        stderr = ""
        try:
            rc, stdout, stderr = await self._cli(*create_args)
            if rc != 0 or not sync_back:
                return ExecutionResult(rc, stdout, stderr, backend)

            with tempfile.TemporaryDirectory(prefix="soai-openshell-stage-") as tmp:
                stage_parent = Path(tmp)
                stage_cli = self._host_path_for_cli(stage_parent)
                dl_rc, dl_out, dl_err = await self._cli(
                    "sandbox",
                    "download",
                    sandbox,
                    "project",
                    stage_cli,
                )
                stdout += dl_out
                stderr += dl_err
                if dl_rc != 0:
                    return ExecutionResult(dl_rc, stdout, stderr, backend)

                staged = stage_parent / "project"
                if not staged.exists():
                    # Be strict rather than guessing a destination layout that could commit the wrong tree.
                    return ExecutionResult(
                        70,
                        stdout,
                        stderr
                        + f"\nOpenShell download did not produce expected staged directory: {staged}",
                        backend,
                    )
                stats = reconcile_workspace(workspace, staged, before or {})
                stdout += (
                    f"\n[sovereign-kernel] committed workspace transaction: "
                    f"+{stats['created']} ~{stats['modified']} -{stats['deleted']}\n"
                )
                return ExecutionResult(0, stdout, stderr, backend)
        finally:
            if sync_back:
                # Delete is best-effort cleanup; failure is surfaced in stderr only when possible.
                try:
                    await self._cli("sandbox", "delete", sandbox)
                except Exception:
                    pass
