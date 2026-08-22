from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from .base import AgentLoop, AgentStep

_REPO_SRC = str(Path(__file__).resolve().parents[2])


class GooseAgentLoop(AgentLoop):
    """Subprocess bridge to the compiled `goose` CLI (`knowledge/research.md` D-015).

    `D-015`'s safety boundary requires every external harness to stay subordinate: "the
    kernel issues the run_id, grants, leases and final state transition. Anything Goose
    reports is untrusted evidence until a verifier says otherwise." By default every
    invocation passes `--no-profile` and no `--with-extension`/`--with-builtin` flag, so
    Goose is launched with **zero** filesystem or shell tool access. It cannot bypass
    `ExecutionBroker`/`PolicyEngine` because it has no path to touch anything outside the
    one text completion it returns -- not because a policy layer stopped it, but because
    it was never given the means. This is a smaller contract than `NativeAgentLoop`'s real
    per-step tool loop: `next_step()` here runs Goose's own CLI to completion in one
    subprocess call and returns a single `done` step, since the CLI does not hand control
    back to a caller between its own internal turns.

    Setting `enable_tools=True` bridges Goose's own MCP stdio extension mechanism
    (`--with-extension`) to `agents/mcp_bridge.py`, which exposes the *same*
    `read_file`/`list_directory`/`run_command` tools `NativeAgentLoop` already uses,
    calling the identical `WorkspaceRegistry`/`ExecutionBroker` primitives -- so a
    tool-enabled Goose run is held to the same policy gate as the reference loop, not a
    weaker one. Off by default: most callers (including the harness tournament's default
    construction in `kernel/app.py`) get the zero-tool comparison this loop shipped with
    first, so nothing about existing behavior or tests changes silently.
    """

    def __init__(
        self,
        goose_binary: str,
        base_url: str,
        model: str,
        timeout_s: float = 120.0,
        enable_tools: bool = False,
    ):
        self.goose_binary = goose_binary
        self.base_url = base_url
        self.model = model
        self.timeout_s = timeout_s
        self.enable_tools = enable_tools

    async def next_step(self, state: dict[str, Any]) -> AgentStep:
        # One `goose run` invocation already runs Goose's own loop to completion --
        # nothing left for a second `next_step()` call to do for the same run.
        if state.get("history"):
            return AgentStep(kind="done", payload={"summary": state["history"][-1]}, done=True)

        task = str(state.get("task", ""))
        env = dict(os.environ)
        env.update(
            {
                "GOOSE_PROVIDER": "openai",
                "OPENAI_BASE_URL": self.base_url,
                # llama.cpp's OpenAI-compatible server does not check this value, but the
                # openai provider's own config validation requires the key to be present.
                "OPENAI_API_KEY": "local-backend-no-key-required",
                "GOOSE_MODEL": self.model,
            }
        )
        argv = [self.goose_binary, "run", "--no-profile", "--no-session", "-q"]
        if self.enable_tools:
            argv += ["--with-extension", self._extension_command(state)]
        argv += ["--text", task]
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            return AgentStep(
                kind="harness_error", payload={"error": f"goose binary not found: {exc}"}, done=True
            )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout_s)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return AgentStep(
                kind="harness_error",
                payload={"error": f"goose run exceeded {self.timeout_s}s timeout"},
                done=True,
            )

        summary = stdout.decode("utf-8", errors="replace").strip()
        state.setdefault("history", []).append(summary)

        if proc.returncode != 0:
            return AgentStep(
                kind="harness_error",
                payload={
                    "error": f"goose exited {proc.returncode}: {stderr.decode('utf-8', errors='replace')[:2000]}"
                },
                done=True,
            )
        return AgentStep(kind="done", payload={"summary": summary}, done=True)

    @staticmethod
    def _extension_command(state: dict[str, Any]) -> str:
        """Builds the `--with-extension` value per Goose's own documented format:
        `'[name:]ENV1=val1 ENV2=val2 command args...'`. `agent_profile_id` and
        `workspace` come from this run's own `state` (the same values `NativeAgentLoop`
        reads from it), never a default, so a tool-enabled run without an explicit
        identity fails the same fail-closed `CapabilityGrant` check any other unnamed
        caller would.
        """
        env_pairs = []
        agent_profile_id = state.get("agent_profile_id")
        if agent_profile_id:
            env_pairs.append(f"SOAI_MCP_AGENT_PROFILE_ID={agent_profile_id}")
        workspace = state.get("workspace")
        if workspace:
            env_pairs.append(f"SOAI_MCP_WORKSPACE={workspace}")
        config_root = os.environ.get("SOVEREIGN_CONFIG_ROOT")
        if config_root:
            env_pairs.append(f"SOVEREIGN_CONFIG_ROOT={config_root}")
        state_dir = os.environ.get("SOVEREIGN_STATE_DIR")
        if state_dir:
            env_pairs.append(f"SOVEREIGN_STATE_DIR={state_dir}")
        env_pairs.append(f"PYTHONPATH={_REPO_SRC}")
        return (
            f"kernel_tools:{' '.join(env_pairs)} "
            f"{sys.executable} -m sovereign_ai.agents.mcp_bridge"
        )
