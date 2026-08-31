from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path
from typing import Any

from .base import AgentLoop, AgentStep

_REPO_ROOT = Path(__file__).resolve().parents[3]
OPENHANDS_RUNNER = _REPO_ROOT / "integrations" / "openhands" / "runner.py"
_DEFAULT_RUNTIME = (
    Path.home() / ".local" / "share" / "sovereign-ai" / "runtimes" / "openhands-sdk-venv"
)
_DEFAULT_MCP_RUNTIME = (
    Path.home() / ".local" / "share" / "sovereign-ai" / "runtimes" / "achilles-mcp-venv"
)


def resolve_openhands_runtime() -> tuple[Path, Path] | None:
    root = Path(os.environ.get("SOAI_OPENHANDS_RUNTIME", _DEFAULT_RUNTIME)).expanduser()
    mcp_root = Path(os.environ.get("SOAI_MCP_RUNTIME", _DEFAULT_MCP_RUNTIME)).expanduser()
    python = root / "bin" / "python"
    mcp_python = mcp_root / "bin" / "python"
    if not all(path.is_file() and os.access(path, os.X_OK) for path in (python, mcp_python)):
        return None
    if not OPENHANDS_RUNNER.is_file():
        return None
    return python, mcp_python


class OpenHandsAgentLoop(AgentLoop):
    """Current OpenHands SDK loop with Achilles MCP as its sole I/O authority."""

    def __init__(
        self,
        python_binary: Path,
        mcp_python: Path,
        base_url: str,
        model: str,
        timeout_s: float = 180.0,
    ):
        self.python_binary = Path(python_binary)
        self.mcp_python = Path(mcp_python)
        self.binary = self.python_binary
        self.base_url = base_url
        self.model = model
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
        if not self.python_binary.is_file() or not OPENHANDS_RUNNER.is_file():
            return AgentStep(
                kind="harness_error",
                payload={"error": f"OpenHands SDK runtime not found: {self.python_binary}"},
                done=True,
            )

        env = dict(os.environ)
        env.update(
            {
                "OPENHANDS_SUPPRESS_BANNER": "1",
                "LITELLM_TELEMETRY": "False",
                "DO_NOT_TRACK": "1",
            }
        )
        argv = [
            str(self.python_binary),
            str(OPENHANDS_RUNNER),
            "--task",
            str(state.get("task", "")),
            "--workspace",
            str(state.get("workspace", "")),
            "--model",
            self.model,
            "--base-url",
            self.base_url,
            "--subject-id",
            str(state.get("agent_profile_id") or ""),
            "--run-id",
            str(state.get("run_id") or ""),
            "--mcp-python",
            str(self.mcp_python),
            "--repo-root",
            str(_REPO_ROOT),
        ]
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=state.get("workspace"),
                env=env,
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
                payload={"error": f"OpenHands exceeded {self.timeout_s:g}s"},
                done=True,
            )
        except FileNotFoundError:
            return AgentStep(
                kind="harness_error",
                payload={"error": f"OpenHands Python not found: {self.python_binary}"},
                done=True,
            )

        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")
        marker = next(
            (
                line
                for line in reversed(stdout_text.splitlines())
                if line.startswith("SOAI_OPENHANDS_RESULT=")
            ),
            None,
        )
        if proc.returncode != 0 or marker is None:
            return AgentStep(
                kind="harness_error",
                payload={
                    "error": f"OpenHands exited {proc.returncode}",
                    "stderr": stderr_text[-6000:],
                    "stdout": stdout_text[-6000:],
                },
                done=True,
            )
        summary = marker.removeprefix("SOAI_OPENHANDS_RESULT=")
        state.setdefault("history", []).append(summary)
        return AgentStep(kind="done", payload={"summary": summary[-4000:]}, done=True)
