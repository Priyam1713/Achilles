from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import tempfile
from pathlib import Path
from typing import Any

from .base import AgentLoop, AgentStep

_REPO_ROOT = Path(__file__).resolve().parents[3]
MINI_SWE_RUNNER = _REPO_ROOT / "integrations" / "mini_swe" / "runner.py"
_DEFAULT_RUNTIME = (
    Path.home()
    / ".local"
    / "share"
    / "sovereign-ai"
    / "runtimes"
    / "mini-swe-agent-venv"
)


def resolve_mini_swe_runtime() -> tuple[Path, Path] | None:
    override = os.environ.get("SOAI_MINI_SWE_RUNTIME")
    root = Path(override).expanduser() if override else _DEFAULT_RUNTIME
    python = root / "bin" / "python"
    mini = root / "bin" / "mini"
    if not python.is_file() or not mini.is_file() or not MINI_SWE_RUNNER.is_file():
        return None
    if not os.access(python, os.X_OK) or not os.access(mini, os.X_OK):
        return None
    return python, mini


class MiniSWEAgentLoop(AgentLoop):
    """mini-SWE-agent v2 with its bash environment replaced by Achilles authority."""

    def __init__(
        self,
        python_binary: Path,
        mini_binary: Path,
        base_url: str,
        model: str,
        kernel_url: str = "http://127.0.0.1:7788",
        session_token: str = "",
        timeout_s: float = 180.0,
    ):
        self.python_binary = Path(python_binary)
        self.binary = Path(mini_binary)
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
        if not self.python_binary.is_file() or not MINI_SWE_RUNNER.is_file():
            return AgentStep(
                kind="harness_error",
                payload={"error": f"mini-SWE-agent runtime not found: {self.python_binary}"},
                done=True,
            )

        run_dir = Path(tempfile.mkdtemp(prefix="mini-swe-agent-adapter-"))
        trajectory_path = run_dir / "trajectory.json"

        def read_trace() -> str:
            if not trajectory_path.is_file():
                return ""
            raw = trajectory_path.read_text(encoding="utf-8", errors="replace")
            try:
                messages = json.loads(raw).get("messages", [])[-6:]
                compact = [
                    {
                        "role": message.get("role"),
                        "content": str(message.get("content") or "")[-800:],
                        "actions": message.get("extra", {}).get("actions", []),
                        "exit_status": message.get("extra", {}).get("exit_status"),
                    }
                    for message in messages
                ]
                return json.dumps(compact, separators=(",", ":"))
            except (json.JSONDecodeError, AttributeError):
                return raw[-12000:]
        env = dict(os.environ)
        env.update(
            {
                "MSWEA_GLOBAL_CONFIG_DIR": str(run_dir / "config"),
                "MSWEA_CONFIGURED": "true",
                "MSWEA_SILENT_STARTUP": "1",
                "MSWEA_COST_TRACKING": "ignore_errors",
                "LITELLM_TELEMETRY": "False",
                "DO_NOT_TRACK": "1",
            }
        )
        argv = [
            str(self.python_binary),
            str(MINI_SWE_RUNNER),
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
            "--output-path",
            str(trajectory_path),
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
            trace = read_trace()
            shutil.rmtree(run_dir, ignore_errors=True)
            return AgentStep(
                kind="harness_timeout",
                payload={
                    "error": (
                        f"mini-swe-agent exceeded {self.timeout_s:g}s; "
                        f"trajectory tail: {trace[-2000:]}"
                    ),
                    "trajectory": trace,
                },
                done=True,
            )
        except FileNotFoundError:
            shutil.rmtree(run_dir, ignore_errors=True)
            return AgentStep(
                kind="harness_error",
                payload={"error": f"mini-SWE-agent Python not found: {self.python_binary}"},
                done=True,
            )
        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")
        trace = read_trace()
        marker = next(
            (line for line in reversed(stdout_text.splitlines()) if line.startswith("SOAI_MINI_RESULT=")),
            None,
        )
        if proc.returncode != 0 or marker is None:
            shutil.rmtree(run_dir, ignore_errors=True)
            return AgentStep(
                kind="harness_error",
                payload={
                    "error": (
                        f"mini-swe-agent exited {proc.returncode}; "
                        f"trajectory tail: {trace[-2000:]}"
                    ),
                    "stderr": stderr_text[-4000:],
                    "stdout": stdout_text[-4000:],
                    "trajectory": trace,
                },
                done=True,
            )
        summary = marker.removeprefix("SOAI_MINI_RESULT=")
        state.setdefault("history", []).append(summary)
        shutil.rmtree(run_dir, ignore_errors=True)
        return AgentStep(kind="done", payload={"summary": summary[-4000:]}, done=True)
