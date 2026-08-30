from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import sys
import tempfile
from pathlib import Path
from typing import Any

from .base import AgentLoop, AgentStep

_DEFAULT_CHECKOUT = (
    Path.home() / ".local" / "share" / "sovereign-ai" / "runtimes" / "deepseek-harness"
)
_UNGOVERNED_TOOL_ROWS = (
    "tool-bash",
    "tool-pwsh",
    "tool-jobs",
    "tool-fs",
    "tool-fs-search",
    "tool-skill",
    "tool-web",
    "tool-str-replace-editor",
)


def resolve_deepseek_harness_checkout() -> Path | None:
    """Return a built DeepSeek Harness checkout suitable for headless execution."""
    override = os.environ.get("SOAI_DEEPSEEK_HARNESS_ROOT")
    checkout = Path(override).expanduser() if override else _DEFAULT_CHECKOUT
    required = (
        checkout / "apps" / "cli" / "lib" / "bin.js",
        checkout / "packages" / "mcp" / "mcp-client" / "lib" / "index.js",
        checkout / "package.json",
    )
    if not (checkout / ".git").is_dir() or not all(path.is_file() for path in required):
        return None
    return checkout


class DeepSeekHarnessAgentLoop(AgentLoop):
    """Governed one-shot bridge to DeepSeek Harness/Cordis.

    The harness retains its orchestration features, while its direct filesystem, shell,
    search, skill, and editor consumers are disabled. Its only workspace-capable tools are
    discovered from Achilles' policy-gated MCP bridge.
    """

    def __init__(
        self,
        checkout: Path,
        base_url: str,
        model: str,
        node_binary: str = "node",
        timeout_s: float = 180.0,
        provider_id: str = "sovereign",
    ):
        self.checkout = Path(checkout)
        self.base_url = base_url
        self.model = model
        self.node_binary = node_binary
        self.timeout_s = timeout_s
        self.provider_id = provider_id
        self.enable_tools = True

    def _bridge_environment(self, state: dict[str, Any]) -> dict[str, str]:
        env = {
            "PYTHONUNBUFFERED": "1",
            "SOAI_MCP_AGENT_PROFILE_ID": str(state.get("agent_profile_id") or ""),
            "SOAI_MCP_WORKSPACE": str(state.get("workspace") or ""),
            "SOAI_MCP_RUN_ID": str(state.get("run_id") or ""),
        }
        for name in ("SOVEREIGN_CONFIG_ROOT", "SOVEREIGN_STATE_DIR", "SOVEREIGN_RUNTIME_DIR"):
            value = os.environ.get(name)
            if value:
                env[name] = value
        return env

    @staticmethod
    def _quoted(value: str) -> str:
        return json.dumps(value)

    def _patch(self, state: dict[str, Any]) -> str:
        """Build the frozen provider and authority overlay for one isolated run."""
        lines = [
            "- id: agent-default-model",
            "  config:",
            f"    provider: {self._quoted(self.provider_id)}",
            f"    model: {self._quoted(self.model)}",
            "- id: llm-pi-ai",
            "  config:",
            "    providers:",
            f"      {self.provider_id}:",
            "        displayName: Achilles local router",
            "        apiKeyEnv: ACHILLES_LOCAL_API_KEY",
            "        api: openai-completions",
            f"        baseURL: {self._quoted(self.base_url)}",
            "        compat:",
            "          supportsDeveloperRole: false",
            "          thinkingFormat: qwen-chat-template",
            "          maxTokensField: max_tokens",
            "        models:",
            f"          - id: {self._quoted(self.model)}",
            "            contextWindow: 32768",
            "            maxTokens: 4096",
            "            reasoningEfforts: false",
        ]
        for tool_id in _UNGOVERNED_TOOL_ROWS:
            lines.extend((f"- id: {tool_id}", "  disabled: true"))
        if self.enable_tools:
            bridge_env = self._bridge_environment(state)
            mcp_plugin = self.checkout / "packages" / "mcp" / "mcp-client" / "lib" / "index.js"
            lines.extend(
                (
                    "- insert:",
                    "    - id: mcp-achilles",
                    f"      name: {self._quoted(str(mcp_plugin))}",
                    "      config:",
                    "        transport: stdio",
                    "        serverName: achilles",
                    f"        command: {self._quoted(sys.executable)}",
                    "        args: ['-m', 'sovereign_ai.agents.mcp_bridge']",
                    f"        cwd: {self._quoted(str(Path(__file__).resolve().parents[3]))}",
                    "        toolCallTimeoutMs: 60000",
                    "        failOnStartupError: true",
                    "        reconnect:",
                    "          enabled: false",
                    "        env:",
                )
            )
            for name, value in sorted(bridge_env.items()):
                lines.append(f"          {name}: {self._quoted(value)}")
        return "\n".join(lines) + "\n"

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

        cli = self.checkout / "apps" / "cli" / "lib" / "bin.js"
        if not cli.is_file() or shutil.which(self.node_binary) is None:
            return AgentStep(
                kind="harness_error",
                payload={"error": f"DeepSeek Harness runtime not found: {self.checkout}"},
                done=True,
            )

        agent_dir = Path(tempfile.mkdtemp(prefix="deepseek-harness-adapter-"))
        patch = agent_dir / "achilles.patch.yml"
        patch.write_text(self._patch(state), encoding="utf-8")
        env = dict(os.environ)
        env.update(
            {
                "DSH_HOME": str(agent_dir / "home"),
                "DSH_PERMISSION_MODE": "danger-full-access",
                "DSH_TELEMETRY_MODE": "DISABLED",
                "DO_NOT_TRACK": "1",
                "ACHILLES_LOCAL_API_KEY": "local-backend-no-key-required",
            }
        )
        argv = [
            self.node_binary,
            str(cli),
            "--profile",
            "headless",
            "--patch",
            str(patch),
            str(state.get("task", "")),
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
                payload={"error": f"deepseek-harness exceeded {self.timeout_s:g}s"},
                done=True,
            )
        except FileNotFoundError:
            return AgentStep(
                kind="harness_error",
                payload={"error": f"node binary not found: {self.node_binary}"},
                done=True,
            )
        finally:
            shutil.rmtree(agent_dir, ignore_errors=True)

        summary = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            return AgentStep(
                kind="harness_error",
                payload={
                    "error": f"deepseek-harness exited {proc.returncode}",
                    "stderr": stderr_text[-4000:],
                    "stdout": summary[-2000:],
                },
                done=True,
            )
        state.setdefault("history", []).append(summary)
        return AgentStep(kind="done", payload={"summary": summary[-4000:]}, done=True)
