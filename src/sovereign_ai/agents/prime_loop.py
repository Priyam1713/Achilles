from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .base import AgentLoop, AgentStep
from .pi_loop import PI_EXTENSION


def resolve_prime_agent_binary() -> str | None:
    """Resolve a real Prime Agent executable, including NVM global installs."""
    override = os.environ.get("SOAI_PRIME_AGENT_BINARY")
    if override and os.access(override, os.X_OK):
        return override
    found = shutil.which("prime-agent")
    if found and Path(found).exists() and os.access(found, os.X_OK):
        return found
    candidates = sorted(
        (Path.home() / ".nvm" / "versions" / "node").glob("*/bin/prime-agent"),
        reverse=True,
    )
    return str(candidates[0]) if candidates and os.access(candidates[0], os.X_OK) else None


class PrimeAgentLoop(AgentLoop):
    """Governed bridge to Prime Agent's persistent-RLM coding harness.

    Prime remains responsible for planning, context management and its IPython/RLM
    orchestration.  Filesystem and command authority do not cross with it: all built-in
    tools and discovered resources are disabled, and the same Achilles extension used by
    the Pi arm is its sole tool plane.
    """

    def __init__(
        self,
        binary: str,
        base_url: str,
        model: str,
        kernel_url: str = "http://127.0.0.1:7788",
        session_token: str = "",
        timeout_s: float = 180.0,
        provider_id: str = "sovereign",
    ):
        self.binary = binary
        self.base_url = base_url
        self.model = model
        self.kernel_url = kernel_url
        self.session_token = session_token
        self.timeout_s = timeout_s
        self.provider_id = provider_id
        self.enable_tools = True

    def _models_json(self) -> dict[str, Any]:
        return {
            "providers": {
                self.provider_id: {
                    "baseUrl": self.base_url,
                    "api": "openai-completions",
                    "apiKey": "local-backend-no-key-required",
                    "compat": {
                        "supportsDeveloperRole": False,
                        "supportsReasoningEffort": False,
                        "supportsUsageInStreaming": True,
                        "maxTokensField": "max_tokens",
                        "thinkingFormat": "qwen-chat-template",
                    },
                    "models": [
                        {
                            "id": self.model,
                            "contextWindow": 32768,
                            "maxTokens": 4096,
                            "reasoning": False,
                        }
                    ],
                }
            }
        }

    def _environment(self, state: dict[str, Any], agent_dir: Path) -> dict[str, str]:
        env = dict(os.environ)
        env.update(
            {
                "PRIME_AGENT_CODING_AGENT_DIR": str(agent_dir),
                "PI_OFFLINE": "1",
                "PRIME_AGENT_TELEMETRY": "0",
                "DO_NOT_TRACK": "1",
                "SOAI_KERNEL_URL": self.kernel_url,
                "SOAI_SESSION_TOKEN": self.session_token,
                "SOAI_AGENT_PROFILE_ID": str(state.get("agent_profile_id") or ""),
                "SOAI_WORKSPACE": str(state.get("workspace") or ""),
                "SOAI_RUN_ID": str(state.get("run_id") or ""),
            }
        )
        return env

    async def next_step(self, state: dict[str, Any]) -> AgentStep:
        if state.get("history"):
            return AgentStep(kind="done", payload={"summary": state["history"][-1]}, done=True)
        if not PI_EXTENSION.is_file():
            return AgentStep(
                kind="harness_error",
                payload={"error": f"Achilles extension missing: {PI_EXTENSION}"},
                done=True,
            )

        agent_dir = Path(tempfile.mkdtemp(prefix="prime-agent-adapter-"))
        (agent_dir / "models.json").write_text(
            json.dumps(self._models_json(), indent=2), encoding="utf-8"
        )
        argv = [
            self.binary,
            "--print",
            "--mode",
            "text",
            "--no-session",
            "--offline",
            "--provider",
            self.provider_id,
            "--model",
            self.model,
            "--thinking",
            "off",
            "--no-builtin-tools",
            "--no-extensions",
            "--no-skills",
            "--no-prompt-templates",
            "--no-context-files",
            "--extension",
            str(PI_EXTENSION),
            "--",
            str(state.get("task", "")),
        ]
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=state.get("workspace"),
                env=self._environment(state, agent_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout_s)
        except TimeoutError:
            if proc is not None and proc.returncode is None:
                proc.kill()
                await proc.wait()
            return AgentStep(
                kind="harness_timeout",
                payload={"error": f"prime-agent exceeded {self.timeout_s:g}s"},
                done=True,
            )
        except FileNotFoundError:
            return AgentStep(
                kind="harness_error",
                payload={"error": f"prime-agent binary not found: {self.binary}"},
                done=True,
            )

        summary = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            return AgentStep(
                kind="harness_error",
                payload={
                    "error": f"prime-agent exited {proc.returncode}",
                    "stderr": stderr_text[-4000:],
                    "stdout": summary[-2000:],
                },
                done=True,
            )
        state.setdefault("history", []).append(summary)
        return AgentStep(kind="done", payload={"summary": summary[-4000:]}, done=True)
