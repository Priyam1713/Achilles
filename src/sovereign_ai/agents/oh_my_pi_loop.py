from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import socket
import tempfile
from pathlib import Path
from typing import Any

from .base import AgentLoop, AgentStep

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_RUNTIME = Path.home() / ".local" / "share" / "sovereign-ai" / "runtimes" / "oh-my-pi"
_DEFAULT_MCP_RUNTIME = (
    Path.home() / ".local" / "share" / "sovereign-ai" / "runtimes" / "achilles-mcp-venv"
)
_HTTP_MCP_RUNNER = _REPO_ROOT / "integrations" / "oh_my_pi" / "http_mcp_runner.py"


def resolve_oh_my_pi_runtime() -> tuple[Path, Path, Path] | None:
    """Resolve the isolated official OMP CLI, Bun, and the shared Achilles MCP Python."""
    root = Path(os.environ.get("SOAI_OH_MY_PI_RUNTIME", _DEFAULT_RUNTIME)).expanduser()
    mcp_root = Path(os.environ.get("SOAI_MCP_RUNTIME", _DEFAULT_MCP_RUNTIME)).expanduser()
    omp = root / "node_modules" / ".bin" / "omp"
    bun = root / "node_modules" / ".bin" / "bun"
    mcp_python = mcp_root / "bin" / "python"
    paths = (omp, bun, mcp_python)
    if not all(path.is_file() and os.access(path, os.X_OK) for path in paths):
        return None
    if not _HTTP_MCP_RUNNER.is_file():
        return None
    return paths


class OhMyPiAgentLoop(AgentLoop):
    """Official Oh My Pi CLI with Achilles MCP as its sole authority-bearing tool plane."""

    def __init__(
        self,
        binary: Path,
        bun_binary: Path,
        mcp_python: Path,
        base_url: str,
        model: str,
        timeout_s: float = 180.0,
        provider_id: str = "sovereign",
    ):
        self.binary = Path(binary)
        self.bun_binary = Path(bun_binary)
        self.mcp_python = Path(mcp_python)
        self.base_url = base_url
        self.model = model
        self.timeout_s = timeout_s
        self.provider_id = provider_id
        self.enable_tools = True

    def _models_config(self) -> dict[str, Any]:
        return {
            "providers": {
                self.provider_id: {
                    "baseUrl": self.base_url,
                    "api": "openai-completions",
                    "auth": "none",
                    "compat": {
                        "supportsDeveloperRole": False,
                        "supportsReasoningEffort": False,
                        "supportsUsageInStreaming": True,
                        "maxTokensField": "max_tokens",
                        "thinkingFormat": "qwen-chat-template",
                        "qwenTemplateReasoningEffort": False,
                    },
                    "models": [
                        {
                            "id": self.model,
                            "name": self.model,
                            "contextWindow": 32768,
                            "maxTokens": 4096,
                            "reasoning": False,
                            "supportsTools": True,
                        }
                    ],
                }
            }
        }

    def _bridge_environment(self, state: dict[str, Any]) -> dict[str, str]:
        env = dict(os.environ)
        env.update(
            {
            "PYTHONPATH": str(_REPO_ROOT / "src"),
            "SOAI_MCP_AGENT_PROFILE_ID": str(state.get("agent_profile_id") or ""),
            "SOAI_MCP_WORKSPACE": str(state.get("workspace") or ""),
            "SOAI_MCP_RUN_ID": str(state.get("run_id") or ""),
            }
        )
        for key in ("SOVEREIGN_CONFIG_ROOT", "SOVEREIGN_STATE_DIR", "SOVEREIGN_RUNTIME_DIR"):
            if value := os.environ.get(key):
                env[key] = value
        return env

    def _mcp_config(self, mcp_url: str) -> dict[str, Any]:
        return {
            "mcpServers": {
                "achilles": {
                    "type": "http",
                    "url": mcp_url,
                    "timeout": 30000,
                }
            }
        }

    @staticmethod
    def _free_loopback_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            return int(listener.getsockname()[1])

    async def _wait_for_server(
        self, proc: asyncio.subprocess.Process, port: int, timeout_s: float = 15.0
    ) -> bool:
        deadline = asyncio.get_running_loop().time() + timeout_s
        while asyncio.get_running_loop().time() < deadline:
            if proc.returncode is not None:
                return False
            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", port)
                writer.close()
                await writer.wait_closed()
                del reader
                return True
            except OSError:
                await asyncio.sleep(0.05)
        return False

    def _environment(self, run_root: Path, agent_dir: Path) -> dict[str, str]:
        env = dict(os.environ)
        runtime_bin = str(self.binary.parent)
        env.update(
            {
                # A disposable home prevents OMP's compatibility importers from seeing
                # operator Claude/Codex/Cursor/OpenCode configuration.
                "HOME": str(run_root / "home"),
                "XDG_CONFIG_HOME": str(run_root / "xdg-config"),
                "XDG_DATA_HOME": str(run_root / "xdg-data"),
                "XDG_STATE_HOME": str(run_root / "xdg-state"),
                "XDG_CACHE_HOME": str(run_root / "xdg-cache"),
                "PI_CODING_AGENT_DIR": str(agent_dir),
                "PATH": runtime_bin + os.pathsep + os.environ.get("PATH", ""),
                "DO_NOT_TRACK": "1",
                "OMP_TELEMETRY": "0",
            }
        )
        return env

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
        required = (self.binary, self.bun_binary, self.mcp_python)
        if not all(path.is_file() for path in required):
            return AgentStep(
                kind="harness_error",
                payload={"error": f"Oh My Pi runtime not found: {self.binary}"},
                done=True,
            )

        run_root = Path(tempfile.mkdtemp(prefix="oh-my-pi-adapter-"))
        agent_dir = run_root / "agent"
        for directory in (
            agent_dir,
            run_root / "home",
            run_root / "xdg-config",
            run_root / "xdg-data",
            run_root / "xdg-state",
            run_root / "xdg-cache",
        ):
            directory.mkdir(parents=True, exist_ok=True)
        # JSON is valid YAML. Keeping these machine-authored configs as JSON avoids
        # adding a YAML runtime dependency to the trusted adapter.
        (agent_dir / "models.yml").write_text(
            json.dumps(self._models_config(), indent=2), encoding="utf-8"
        )
        (agent_dir / "config.yml").write_text(
            json.dumps(
                {
                    "mcp": {"enableProjectConfig": False},
                    # With built-in `read` disabled, xd:// would hide MCP schemas behind
                    # a device the model cannot inspect. Expose the governed MCP tools
                    # directly instead; this changes presentation, never authority.
                    "tools": {"xdev": False},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        workspace = str(state.get("workspace") or "")
        task = str(state.get("task") or "").replace(workspace, ".")
        task += (
            "\n\nThe repository is the current workspace. Use only the Achilles MCP tools "
            "for repository inspection, command execution, and edits. Use relative paths. "
            "Do not merely describe a patch: inspect the repository and implement the requested change."
        )
        argv = [
            str(self.binary),
            "--print",
            "--mode",
            "text",
            "--no-session",
            "--model",
            f"{self.provider_id}/{self.model}",
            "--thinking",
            "off",
            "--no-tools",
            "--no-lsp",
            "--no-pty",
            "--no-extensions",
            "--no-skills",
            "--no-rules",
            "--no-title",
            "--no-prewalk",
            "--approval-mode",
            "yolo",
            "--max-time",
            str(max(5, int(self.timeout_s - 3))),
            "--cwd",
            workspace,
            task,
        ]
        proc = None
        mcp_proc = None
        try:
            mcp_port = self._free_loopback_port()
            mcp_proc = await asyncio.create_subprocess_exec(
                str(self.mcp_python),
                str(_HTTP_MCP_RUNNER),
                "--port",
                str(mcp_port),
                cwd=str(_REPO_ROOT),
                env=self._bridge_environment(state),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                start_new_session=os.name != "nt",
            )
            if not await self._wait_for_server(mcp_proc, mcp_port):
                return AgentStep(
                    kind="harness_error",
                    payload={"error": "Achilles HTTP MCP bridge did not become ready"},
                    done=True,
                )
            (agent_dir / "mcp.json").write_text(
                json.dumps(self._mcp_config(f"http://127.0.0.1:{mcp_port}/mcp"), indent=2),
                encoding="utf-8",
            )
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=workspace,
                env=self._environment(run_root, agent_dir),
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
                payload={"error": f"Oh My Pi exceeded {self.timeout_s:g}s"},
                done=True,
            )
        except FileNotFoundError:
            return AgentStep(
                kind="harness_error",
                payload={"error": f"Oh My Pi binary not found: {self.binary}"},
                done=True,
            )
        finally:
            if mcp_proc is not None:
                await self._stop(mcp_proc)
            shutil.rmtree(run_root, ignore_errors=True)

        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            return AgentStep(
                kind="harness_error",
                payload={
                    "error": f"Oh My Pi exited {proc.returncode}",
                    "stderr": stderr_text[-6000:],
                    "stdout": stdout_text[-6000:],
                },
                done=True,
            )
        state.setdefault("history", []).append(stdout_text)
        return AgentStep(kind="done", payload={"summary": stdout_text[-4000:]}, done=True)
