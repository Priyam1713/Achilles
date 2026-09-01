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
_DEFAULT_RUNTIME = (
    Path.home() / ".local" / "share" / "sovereign-ai" / "runtimes" / "qwen-code-runtime"
)
_DEFAULT_MCP_RUNTIME = (
    Path.home() / ".local" / "share" / "sovereign-ai" / "runtimes" / "achilles-mcp-venv"
)

# Complete built-in registry for official Qwen Code 0.22.3.  Whole-tool CLI deny
# rules remove these declarations while leaving the explicitly supplied, namespaced
# `mcp__achilles__*` tools available.  Safe mode separately removes every ambient
# extension, skill, hook, project MCP server, context file, and discovery command.
QWEN_CODE_BUILTIN_TOOLS = (
    "edit",
    "write_file",
    "read_file",
    "zoom_image",
    "grep_search",
    "glob",
    "run_shell_command",
    "todo_write",
    "save_memory",
    "agent",
    "skill",
    "exit_plan_mode",
    "enter_plan_mode",
    "web_fetch",
    "web_search",
    "image_gen",
    "list_directory",
    "lsp",
    "ask_user_question",
    "cron_create",
    "cron_list",
    "cron_delete",
    "loop_wakeup",
    "create_sub_session",
    "list_agents",
    "task_stop",
    "task_create",
    "task_update",
    "task_list",
    "team_create",
    "team_delete",
    "team_plan_approval",
    "request_shutdown",
    "send_message",
    "structured_output",
    "monitor",
    "notebook_edit",
    "tool_search",
    "read_mcp_resource",
    "enter_worktree",
    "exit_worktree",
    "workflow",
    "artifact",
    "record_artifact",
    "report_findings",
    "get_goal",
    "update_goal",
    "display_image",
)


def resolve_qwen_code_runtime() -> tuple[Path, Path] | None:
    root = Path(os.environ.get("SOAI_QWEN_CODE_RUNTIME", _DEFAULT_RUNTIME)).expanduser()
    mcp_root = Path(os.environ.get("SOAI_MCP_RUNTIME", _DEFAULT_MCP_RUNTIME)).expanduser()
    qwen = root / "node_modules" / ".bin" / "qwen"
    mcp_python = mcp_root / "bin" / "python"
    if not all(path.is_file() and os.access(path, os.X_OK) for path in (qwen, mcp_python)):
        return None
    return qwen, mcp_python


class QwenCodeAgentLoop(AgentLoop):
    """Official Qwen Code CLI with Achilles MCP as its only tool authority."""

    def __init__(
        self,
        binary: Path,
        mcp_python: Path,
        base_url: str,
        model: str,
        timeout_s: float = 180.0,
    ) -> None:
        self.binary = Path(binary)
        self.mcp_python = Path(mcp_python)
        self.base_url = base_url
        self.model = model
        self.timeout_s = timeout_s
        self.enable_tools = True

    def _mcp_config(self, state: dict[str, Any]) -> dict[str, Any]:
        bridge_env = {
            "PYTHONPATH": str(_REPO_ROOT / "src"),
            "SOVEREIGN_CONFIG_ROOT": str(
                Path(os.environ.get("SOVEREIGN_CONFIG_ROOT", _REPO_ROOT / "configs")).expanduser()
            ),
            "SOAI_MCP_AGENT_PROFILE_ID": str(state.get("agent_profile_id") or ""),
            "SOAI_MCP_WORKSPACE": str(state.get("workspace") or ""),
            "SOAI_MCP_RUN_ID": str(state.get("run_id") or ""),
        }
        for key in ("SOVEREIGN_STATE_DIR", "SOVEREIGN_RUNTIME_DIR"):
            if value := os.environ.get(key):
                bridge_env[key] = value
        return {
            "mcpServers": {
                "achilles": {
                    "command": str(self.mcp_python),
                    "args": ["-m", "sovereign_ai.agents.mcp_bridge"],
                    "env": bridge_env,
                    "timeout": 30_000,
                    "trust": True,
                }
            }
        }

    @staticmethod
    def _environment(run_root: Path) -> dict[str, str]:
        env = dict(os.environ)
        home = run_root / "home"
        env.update(
            {
                "HOME": str(home),
                "QWEN_HOME": str(run_root / "qwen-home"),
                "XDG_CONFIG_HOME": str(run_root / "xdg-config"),
                "XDG_DATA_HOME": str(run_root / "xdg-data"),
                "XDG_STATE_HOME": str(run_root / "xdg-state"),
                "XDG_CACHE_HOME": str(run_root / "xdg-cache"),
                "DO_NOT_TRACK": "1",
                "NO_BROWSER": "1",
                "QWEN_CODE_SUPPRESS_YOLO_WARNING": "1",
                # Headless one-shot sessions otherwise race their first model request
                # against progressive MCP discovery and may see no Achilles tools.
                "QWEN_CODE_LEGACY_MCP_BLOCKING": "1",
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
        if not self.binary.is_file() or not self.mcp_python.is_file():
            return AgentStep(
                kind="harness_error",
                payload={"error": f"Qwen Code runtime not found: {self.binary}"},
                done=True,
            )

        run_root = Path(tempfile.mkdtemp(prefix="qwen-code-adapter-"))
        for relative in (
            "home",
            "qwen-home",
            "xdg-config",
            "xdg-data",
            "xdg-state",
            "xdg-cache",
        ):
            (run_root / relative).mkdir(parents=True, exist_ok=True)
        mcp_config = run_root / "mcp.json"
        mcp_config.write_text(json.dumps(self._mcp_config(state), indent=2), encoding="utf-8")

        workspace = str(state.get("workspace") or "")
        task = str(state.get("task") or "").replace(workspace, ".")
        task += (
            "\n\nThe repository is the current workspace. Use only the namespaced Achilles MCP "
            "tools for inspection, commands, and edits. Use relative paths. Implement the change; "
            "do not merely describe a patch."
        )
        argv = [
            str(self.binary),
            "--prompt",
            task,
            "--output-format",
            "json",
            "--safe-mode",
            "--approval-mode",
            "yolo",
            "--auth-type",
            "openai",
            "--openai-api-key",
            "achilles-local",
            "--openai-base-url",
            self.base_url,
            "--model",
            self.model,
            "--mcp-config",
            str(mcp_config),
            "--exclude-tools",
            ",".join(QWEN_CODE_BUILTIN_TOOLS),
            "--max-wall-time",
            str(max(5, int(self.timeout_s - 3))),
            "--max-tool-calls",
            str(max(8, int(state.get("max_steps") or 12) * 4)),
        ]
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=workspace,
                env=self._environment(run_root),
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
                payload={"error": f"Qwen Code exceeded {self.timeout_s:g}s"},
                done=True,
            )
        except FileNotFoundError:
            return AgentStep(
                kind="harness_error",
                payload={"error": f"Qwen Code binary not found: {self.binary}"},
                done=True,
            )
        finally:
            shutil.rmtree(run_root, ignore_errors=True)

        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            return AgentStep(
                kind="harness_error",
                payload={
                    "error": f"Qwen Code exited {proc.returncode}",
                    "stderr": stderr_text[-6000:],
                    "stdout": stdout_text[-6000:],
                },
                done=True,
            )
        summary = stdout_text
        try:
            parsed = json.loads(stdout_text)
            if isinstance(parsed, dict):
                summary = str(parsed.get("response") or parsed.get("result") or stdout_text)
            elif isinstance(parsed, list) and parsed:
                terminal = parsed[-1]
                if isinstance(terminal, dict):
                    summary = str(terminal.get("result") or stdout_text)
        except json.JSONDecodeError:
            pass
        state.setdefault("history", []).append(summary)
        return AgentStep(kind="done", payload={"summary": summary[-4000:]}, done=True)
