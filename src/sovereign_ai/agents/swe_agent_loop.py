from __future__ import annotations

import asyncio
import os
import shutil
import signal
import tempfile
from pathlib import Path
from typing import Any

from .base import AgentLoop, AgentStep

_REPO_ROOT = Path(__file__).resolve().parents[3]
SWE_AGENT_RUNNER = _REPO_ROOT / "integrations" / "swe_agent" / "runner.py"
_DEFAULT_RUNTIME = Path.home() / ".local" / "share" / "sovereign-ai" / "runtimes" / "swe-agent"


def resolve_swe_agent_runtime() -> tuple[Path, Path] | None:
    root = Path(os.environ.get("SOAI_SWE_AGENT_RUNTIME", _DEFAULT_RUNTIME)).expanduser()
    python = root / ".venv" / "bin" / "python"
    config = root / "config" / "bash_only.yaml"
    if not python.is_file() or not os.access(python, os.X_OK):
        return None
    if not config.is_file() or not SWE_AGENT_RUNNER.is_file():
        return None
    return python, config


class SWEAgentLoop(AgentLoop):
    """Official SWE-agent control loop with execution delegated to Achilles."""

    def __init__(
        self,
        python_binary: Path,
        config_path: Path,
        base_url: str,
        model: str,
        kernel_url: str = "http://127.0.0.1:7788",
        session_token: str = "",
        timeout_s: float = 180.0,
    ) -> None:
        self.python_binary = Path(python_binary)
        self.config_path = Path(config_path)
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
        if not self.python_binary.is_file() or not SWE_AGENT_RUNNER.is_file():
            return AgentStep(
                kind="harness_error",
                payload={"error": f"SWE-agent runtime not found: {self.python_binary}"},
                done=True,
            )

        run_root = Path(tempfile.mkdtemp(prefix="swe-agent-adapter-"))
        home = run_root / "home"
        home.mkdir()
        env = dict(os.environ)
        env.update(
            {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(home / ".config"),
                "XDG_CACHE_HOME": str(home / ".cache"),
                "LITELLM_TELEMETRY": "False",
                "DO_NOT_TRACK": "1",
            }
        )
        argv = [
            str(self.python_binary),
            str(SWE_AGENT_RUNNER),
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
            "--config",
            str(self.config_path),
            "--output-dir",
            str(run_root / "trajectory"),
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
            shutil.rmtree(run_root, ignore_errors=True)
            return AgentStep(
                kind="harness_timeout",
                payload={"error": f"SWE-agent exceeded {self.timeout_s:g}s"},
                done=True,
            )
        except FileNotFoundError:
            shutil.rmtree(run_root, ignore_errors=True)
            return AgentStep(
                kind="harness_error",
                payload={"error": f"SWE-agent Python not found: {self.python_binary}"},
                done=True,
            )

        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")
        marker = next(
            (
                line
                for line in reversed(stdout_text.splitlines())
                if line.startswith("SOAI_SWE_AGENT_RESULT=")
            ),
            None,
        )
        shutil.rmtree(run_root, ignore_errors=True)
        if proc.returncode != 0 or marker is None:
            return AgentStep(
                kind="harness_error",
                payload={
                    "error": f"SWE-agent exited {proc.returncode}",
                    "stderr": stderr_text[-6000:],
                    "stdout": stdout_text[-6000:],
                },
                done=True,
            )
        summary = marker.removeprefix("SOAI_SWE_AGENT_RESULT=")
        state.setdefault("history", []).append(summary)
        return AgentStep(kind="done", payload={"summary": summary[-4000:]}, done=True)
