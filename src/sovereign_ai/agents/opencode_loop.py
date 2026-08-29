from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from .base import AgentLoop, AgentStep

_REPO_SRC = str(Path(__file__).resolve().parents[2])


def resolve_opencode_binary() -> str | None:
    """Find a *working* `opencode` executable, or return None.

    `shutil.which()` alone is not enough, and this is not hypothetical: on the machine this
    adapter was written for, `~/.local/bin/opencode` was a **broken symlink** left by an
    earlier install, which `which` happily returned and which then failed at
    `subprocess.exec` time with an unhelpful `TypeError`. npm also ships this package with a
    platform launcher (`bin/opencode.exe`) plus the real binary inside an optional
    platform dependency (`opencode-linux-x64/bin/opencode`), so the useful executable is
    often not where PATH points.

    Resolution order, most explicit first:

    1. `SOAI_OPENCODE_BINARY`, so an operator can always override.
    2. `shutil.which()`, **verified** to resolve to an existing executable file.
    3. The npm global layout, including the platform-specific optional dependency.
    """
    override = os.environ.get("SOAI_OPENCODE_BINARY")
    if override and os.access(override, os.X_OK):
        return override

    found = shutil.which("opencode")
    if found:
        resolved = Path(found)
        if resolved.exists() and os.access(resolved, os.X_OK):
            return str(resolved)

    for root in _npm_global_roots():
        package = root / "opencode-ai"
        if not package.is_dir():
            continue
        for candidate in sorted(package.glob("node_modules/opencode-*/bin/opencode")):
            if os.access(candidate, os.X_OK):
                return str(candidate)
        direct = package / "bin" / "opencode"
        if os.access(direct, os.X_OK):
            return str(direct)
    return None


def _npm_global_roots() -> list[Path]:
    roots: list[Path] = []
    prefix = os.environ.get("NPM_CONFIG_PREFIX")
    if prefix:
        roots.append(Path(prefix) / "lib" / "node_modules")
    node = shutil.which("node")
    if node:
        # .../<version>/bin/node -> .../<version>/lib/node_modules
        roots.append(Path(node).resolve().parent.parent / "lib" / "node_modules")
    roots.append(Path.home() / ".npm-global" / "lib" / "node_modules")
    roots.append(Path("/usr/local/lib/node_modules"))
    return [root for root in roots if root.is_dir()]

#: OpenCode's own built-in tools, disabled so a bridged run uses the kernel's governed
#: tools instead of its own ungoverned filesystem and shell access. This is the same
#: containment `GooseAgentLoop` gets from `--no-profile` plus a single `--with-extension`,
#: expressed the way OpenCode's config expects it. Leaving any of these enabled would make
#: a tournament result meaningless: the harness would be measured on tools that never pass
#: through `PolicyEngine`, against a native loop whose every action does.
_BUILTIN_TOOLS_TO_DISABLE = (
    "bash",
    "edit",
    "write",
    "read",
    "grep",
    "glob",
    "list",
    "patch",
    "webfetch",
    "websearch",
    "todowrite",
    "todoread",
    "task",
)


class OpenCodeAgentLoop(AgentLoop):
    """Subprocess bridge to the `opencode` CLI, held to the kernel's own policy gate.

    `knowledge/harness-research.md` ranked OpenCode the strongest mature provider-neutral
    open coding harness, and F-054's tournament could not measure it because no adapter
    existed. This is that adapter.

    Containment follows `D-015`'s rule exactly, the same way `GooseAgentLoop` does: the
    kernel issues the `run_id`, the grants and the final state transition, and anything the
    harness reports is untrusted evidence until a verifier says otherwise. Concretely, a
    bridged run gets:

    * **every OpenCode built-in tool disabled** (`_BUILTIN_TOOLS_TO_DISABLE`), so it has no
      ungoverned path to the filesystem, the shell or the network;
    * **our MCP bridge as its only tool source**, which dispatches through the same
      `ToolDispatcher` instances the native loop uses, so identical policy, identical
      grants, identical audit;
    * **a generated config written outside the task workspace** and pointed at with
      `OPENCODE_CONFIG`. This matters more than it looks: the tournament's post-conditions
      inspect the workspace directory, so dropping an `opencode.json` into it would let the
      harness's own configuration file count as task output.

    Like the Goose adapter, `next_step()` runs the CLI to completion in one subprocess call
    and returns a single `done` step, because `opencode run` does not hand control back to
    a caller between its own internal turns. Step counts from this loop are therefore not
    comparable with the native loop's; wall time and post-condition success are.
    """

    def __init__(
        self,
        opencode_binary: str,
        base_url: str,
        model: str,
        # 300s rather than Goose's 120s because OpenCode fetches its provider package
        # from npm on first use for a given provider. Measured here: the first run blocked
        # for minutes on a throttled link, then took ~5s once cached (F-055).
        timeout_s: float = 300.0,
        enable_tools: bool = True,
        provider_id: str = "sovereign",
    ):
        self.opencode_binary = opencode_binary
        self.base_url = base_url
        self.model = model
        self.timeout_s = timeout_s
        # Unlike Goose, tools default **on**: an OpenCode run with no tools at all cannot
        # do anything except answer from the prompt, and the zero-tool comparison Goose
        # shipped with first has already been recorded (F-043). There is no reason to
        # repeat it for a harness added after the bridge existed.
        self.enable_tools = enable_tools
        self.provider_id = provider_id

    def _config(self, state: dict[str, Any]) -> dict[str, Any]:
        """The generated OpenCode configuration for one run."""
        config: dict[str, Any] = {
            "$schema": "https://opencode.ai/config.json",
            "provider": {
                self.provider_id: {
                    "npm": "@ai-sdk/openai-compatible",
                    "name": "Sovereign local router",
                    "options": {
                        "baseURL": self.base_url,
                        # llama.cpp's OpenAI-compatible server ignores this, but the
                        # provider package's own validation requires a value to exist.
                        "apiKey": "local-backend-no-key-required",
                    },
                    "models": {self.model: {"id": self.model}},
                }
            },
        }
        if self.enable_tools:
            config["tools"] = {name: False for name in _BUILTIN_TOOLS_TO_DISABLE}
            config["mcp"] = {
                "kernel": {
                    "type": "local",
                    # `sys.executable`, never a bare "python3": the bridge needs the
                    # interpreter that actually has this project's dependencies installed.
                    # Pointing at the system python instead makes the MCP server fail its
                    # import and die silently, and OpenCode then blocks waiting for a
                    # server that will never speak -- diagnosed the hard way, as a run that
                    # hung to its full timeout with empty output (F-055).
                    "command": [sys.executable, "-m", "sovereign_ai.agents.mcp_bridge"],
                    "enabled": True,
                    # OpenCode's default MCP tool-fetch timeout is 5s. Our bridge builds a
                    # whole SovereignKernel first -- config load, registry validation and
                    # migrations across a dozen SQLite stores -- which is comfortably more
                    # than that on a cold cache, and a timed-out MCP server means the run
                    # silently proceeds with no tools at all rather than failing loudly.
                    "timeout": 60000,
                    "environment": self._bridge_environment(state),
                }
            }
        else:
            # No tools at all: the harness can only answer from its prompt.
            config["tools"] = {name: False for name in _BUILTIN_TOOLS_TO_DISABLE}
        return config

    def _bridge_environment(self, state: dict[str, Any]) -> dict[str, str]:
        env = {
            "PYTHONPATH": _REPO_SRC,
            "SOAI_MCP_AGENT_PROFILE_ID": str(state.get("agent_profile_id") or ""),
            "SOAI_MCP_WORKSPACE": str(state.get("workspace") or ""),
            "SOAI_MCP_RUN_ID": str(state.get("run_id") or ""),
        }
        for name in ("SOVEREIGN_CONFIG_ROOT", "SOVEREIGN_STATE_DIR", "SOVEREIGN_RUNTIME_DIR"):
            value = os.environ.get(name)
            if value:
                env[name] = value
        return env

    async def next_step(self, state: dict[str, Any]) -> AgentStep:
        # One `opencode run` invocation already runs OpenCode's own loop to completion.
        if state.get("history"):
            return AgentStep(kind="done", payload={"summary": state["history"][-1]}, done=True)

        task = str(state.get("task", ""))
        workspace = state.get("workspace")

        config_dir = Path(tempfile.mkdtemp(prefix="opencode-adapter-"))
        config_path = config_dir / "opencode.json"
        config_path.write_text(json.dumps(self._config(state), indent=2), encoding="utf-8")

        env = dict(os.environ)
        env["OPENCODE_CONFIG"] = str(config_path)

        argv = [
            self.opencode_binary,
            "run",
            "--model",
            f"{self.provider_id}/{self.model}",
            # Auto-approve OpenCode's *own* permission prompts. This does not widen what the
            # run may do: every tool it has comes from the MCP bridge, and each of those is
            # still judged by `PolicyEngine` and `CapabilityGrant`. Without it a headless
            # run simply blocks forever on a prompt nobody can answer.
            "--auto",
            task,
        ]
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=workspace,
                env=env,
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
                payload={"error": f"opencode exceeded {self.timeout_s}s"},
                done=True,
            )
        except FileNotFoundError:
            return AgentStep(
                kind="harness_error",
                payload={"error": f"opencode binary not found: {self.opencode_binary}"},
                done=True,
            )

        summary = stdout.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0:
            return AgentStep(
                kind="harness_error",
                payload={
                    "error": f"opencode exited {proc.returncode}",
                    "stderr": stderr.decode("utf-8", errors="replace")[-2000:],
                    "stdout": summary[-2000:],
                },
                done=True,
            )
        state.setdefault("history", []).append(summary)
        return AgentStep(kind="done", payload={"summary": summary[-4000:]}, done=True)
