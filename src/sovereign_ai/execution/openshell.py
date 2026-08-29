from __future__ import annotations

import asyncio
import os
import secrets
import shlex
import shutil
import subprocess
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path

from .base import ExecutionBackend, ExecutionResult
from .staging import reconcile_workspace, snapshot_tree, validate_tree


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
        self._availability_cache: tuple[float, bool] | None = None

    def _wsl_path(self, path: str) -> str:
        # `wsl <command> <windows-path>` applies legacy command-line translation that
        # strips backslashes before wslpath sees them (`D:\repo` becomes `D:repo`).
        # --exec passes argv without that shell-style rewrite.
        return subprocess.check_output(
            ["wsl", "--exec", "wslpath", "-a", path], text=True, timeout=5
        ).strip()

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
            output = subprocess.check_output(
                [*prefix, "openshell", "status"],
                text=True,
                stderr=subprocess.STDOUT,
                timeout=15,
            )
            # The CLI currently exits zero even when its own status text says the
            # credential is missing. Require affirmative connection *and*
            # authentication signals so the broker can fall back to Docker instead of
            # selecting a sandbox that will reject every command (F-075).
            folded = output.casefold()
            connected = "connected" in folded and "disconnected" not in folded
            authenticated = "authenticated" in folded and "unauthenticated" not in folded
            return connected and authenticated
        except Exception:
            return False

    def available(self) -> bool:
        now = time.monotonic()
        if self._availability_cache is not None and now - self._availability_cache[0] < 10:
            return self._availability_cache[1]
        if self._windows_wsl:
            try:
                subprocess.check_call(
                    ["wsl", "sh", "-lc", "command -v openshell >/dev/null 2>&1"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15,
                )
                available = self._sync_status_ok()
            except Exception:
                available = False
        elif shutil.which("openshell") is not None:
            available = self._sync_status_ok()
        else:
            available = False
        self._availability_cache = (now, available) if available else None
        return available

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
        validate_tree(workspace)

        before = snapshot_tree(workspace) if sync_back else None
        sandbox = f"soai-{secrets.token_hex(5)}"  # short names avoid driver/name edge cases.
        policy = self._host_path_for_cli(self.policy_path)
        source = self._host_path_for_cli(workspace)
        # The current base image runs as an unprivileged user and does not permit creating
        # /workspace.  /tmp is explicitly writable in our policy and is already isolated
        # per sandbox, so it is the correct copy-in root.
        sandbox_workspace = "/tmp/project"
        command = f"cd {sandbox_workspace} && exec {shlex.join(list(argv))}"
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
            f"{source}:{sandbox_workspace}",
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
