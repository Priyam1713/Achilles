from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path
from typing import Any

from .base import AgentLoop, AgentStep

_REPO_ROOT = Path(__file__).resolve().parents[3]
AIDER_RUNNER = _REPO_ROOT / "integrations" / "aider" / "runner.py"
_DEFAULT_RUNTIME = Path.home() / ".local" / "share" / "sovereign-ai" / "runtimes" / "aider-venv"


def resolve_aider_runtime() -> tuple[Path, Path] | None:
    root = Path(os.environ.get("SOAI_AIDER_RUNTIME", _DEFAULT_RUNTIME)).expanduser()
    python = root / "bin" / "python"
    aider = root / "bin" / "aider"
    if not all(path.is_file() and os.access(path, os.X_OK) for path in (python, aider)):
        return None
    if not AIDER_RUNNER.is_file():
        return None
    return python, aider


class AiderAgentLoop(AgentLoop):
    """Official headless Aider on a shadow repo, committing changes through Achilles."""

    def __init__(
        self,
        python_binary: Path,
        aider_binary: Path,
        base_url: str,
        model: str,
        kernel_url: str = "http://127.0.0.1:7788",
        session_token: str = "",
        timeout_s: float = 180.0,
    ):
        self.python_binary = Path(python_binary)
        self.binary = Path(aider_binary)
        self.base_url = base_url
        self.model = model
        self.kernel_url = kernel_url
        self.session_token = session_token
        self.timeout_s = timeout_s
        self.enable_tools = True

    async def _stop(self, proc: asyncio.subprocess.Process) -> None:
        if proc.returncode is not None:
            return
        if os.name != "nt":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
        await proc.wait()

    async def next_step(self, state: dict[str, Any]) -> AgentStep:
        if state.get("history"):
            return AgentStep(kind="done", payload={"summary": state["history"][-1]}, done=True)
        if not self.python_binary.is_file() or not AIDER_RUNNER.is_file():
            return AgentStep(
                kind="harness_error",
                payload={"error": f"Aider runtime not found: {self.python_binary}"},
                done=True,
            )
        argv = [
            str(self.python_binary),
            str(AIDER_RUNNER),
            "--task",
            str(state.get("task", "")),
            "--workspace",
            str(state.get("workspace", "")),
            "--model",
            self.model,
            "--base-url",
            self.base_url,
            "--kernel-url",
            self.kernel_url,
            "--session-token",
            self.session_token,
            "--subject-id",
            str(state.get("agent_profile_id") or ""),
            "--run-id",
            str(state.get("run_id") or ""),
            "--aider",
            str(self.binary),
        ]
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=state.get("workspace"),
                env=dict(os.environ),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=os.name != "nt",
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout_s)
        except TimeoutError:
            if proc is not None:
                await self._stop(proc)
            return AgentStep(
                kind="harness_timeout",
                payload={"error": f"Aider exceeded {self.timeout_s:g}s"},
                done=True,
            )
        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")
        marker = next(
            (line for line in reversed(stdout_text.splitlines()) if line.startswith("SOAI_AIDER_RESULT=")),
            None,
        )
        if proc.returncode != 0 or marker is None:
            return AgentStep(
                kind="harness_error",
                payload={
                    "error": f"Aider exited {proc.returncode}",
                    "stderr": stderr_text[-6000:],
                    "stdout": stdout_text[-6000:],
                },
                done=True,
            )
        summary = marker.removeprefix("SOAI_AIDER_RESULT=")
        state.setdefault("history", []).append(summary)
        return AgentStep(kind="done", payload={"summary": summary[-4000:]}, done=True)
