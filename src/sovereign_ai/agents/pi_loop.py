from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .base import AgentLoop, AgentStep

_REPO_ROOT = Path(__file__).resolve().parents[3]

#: The Pi extension that exposes the kernel's tool plane. Shipped in this repository
#: rather than installed, because it is part of *our* authority model, not Pi's.
PI_EXTENSION = _REPO_ROOT / "integrations" / "pi" / "kernel-tools.ts"


def resolve_pi_binary() -> str | None:
    """Find a working `pi` executable, or return None.

    Same verification `resolve_opencode_binary()` does, for the same reason: an npm-managed
    binary is frequently reached through a symlink that a previous install left dangling,
    and `shutil.which()` will hand it back regardless.
    """
    override = os.environ.get("SOAI_PI_BINARY")
    if override and os.access(override, os.X_OK):
        return override
    found = shutil.which("pi")
    if found:
        resolved = Path(found)
        if resolved.exists() and os.access(resolved, os.X_OK):
            return str(resolved)
    node = shutil.which("node")
    if node:
        candidate = Path(node).resolve().parent / "pi"
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


class PiAgentLoop(AgentLoop):
    """Subprocess bridge to the `pi` CLI, held to the kernel's own policy gate.

    Pi is the harness `knowledge/harness-research.md` ranked first, on a single measured
    property: it reportedly sends roughly 3x less context per turn than its competitors,
    which is the exact quantity this project's hardware punishes. F-055 then measured the
    opposite end of that axis — OpenCode, bridged, scored 1 genuine pass in 5 with four
    300-second timeouts purely on context weight — so measuring Pi is the other half of
    that experiment, not a nice-to-have.

    **Bridging it required a different mechanism from every other adapter.** Pi has no MCP
    client by design, so `agents/mcp_bridge.py` cannot reach it. It does have in-process
    extensions, so `integrations/pi/kernel-tools.ts` registers the kernel's tools and calls
    `POST /tools/{name}` on the local API. That is a better fit than MCP anyway: no second
    process, no stdio handshake, one HTTP call per tool.

    Containment, matching `D-015` exactly:

    * `--no-builtin-tools` removes Pi's own read/bash/edit/write, so the run has no
      ungoverned path to the filesystem, the shell or the network;
    * every tool it does have is a call into the kernel, under the same `PolicyEngine` and
      `CapabilityGrant` checks the native loop passes through, with a 403 surfaced to the
      model as a refusal;
    * `PI_CODING_AGENT_DIR` points at a temporary directory, so a run neither reads nor
      writes the operator's own Pi configuration, sessions or credentials;
    * `--no-session` keeps the run ephemeral and `--offline` blocks Pi's startup network
      calls, which matters on a machine whose whole premise is working without a network.

    Like the Goose and OpenCode adapters, one `pi -p` invocation runs Pi's own loop to
    completion, so `next_step()` returns a single `done` step and step counts are not
    comparable with the native loop's. Wall time and post-condition success are.
    """

    def __init__(
        self,
        pi_binary: str,
        base_url: str,
        model: str,
        kernel_url: str = "http://127.0.0.1:7788",
        session_token: str = "",
        timeout_s: float = 300.0,
        enable_tools: bool = True,
        provider_id: str = "sovereign",
    ):
        self.pi_binary = pi_binary
        self.base_url = base_url
        self.model = model
        self.kernel_url = kernel_url
        self.session_token = session_token
        self.timeout_s = timeout_s
        self.enable_tools = enable_tools
        self.provider_id = provider_id

    def _models_json(self) -> dict[str, Any]:
        """Pi's own provider declaration for our local router.

        Deliberately **not** Pi's built-in `llama.cpp` provider, even though our router is
        one: that integration drives the router's management API to load and list models,
        and against this build it answered 404 for a valid alias and 503 for another
        (diagnosed live, F-056). The generic `openai-completions` path is the same one
        Goose and OpenCode already use successfully here, so it removes a variable rather
        than adding one.
        """
        return {
            "providers": {
                self.provider_id: {
                    "baseUrl": self.base_url,
                    "api": "openai-completions",
                    # Pi hides models it believes are unauthenticated; llama.cpp ignores
                    # the value entirely.
                    "apiKey": "local-backend-no-key-required",
                    "compat": {
                        # llama.cpp's OpenAI-compatible server does not implement the
                        # `developer` role or `reasoning_effort`; Pi's docs name exactly
                        # this case for local servers.
                        "supportsDeveloperRole": False,
                        "supportsReasoningEffort": False,
                    },
                    "models": [
                        {"id": self.model, "contextWindow": 32768, "maxTokens": 4096}
                    ],
                }
            }
        }

    def _environment(self, state: dict[str, Any], agent_dir: Path) -> dict[str, str]:
        env = dict(os.environ)
        env.update(
            {
                "PI_CODING_AGENT_DIR": str(agent_dir),
                "PI_OFFLINE": "1",
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

        agent_dir = Path(tempfile.mkdtemp(prefix="pi-adapter-"))
        (agent_dir / "models.json").write_text(
            json.dumps(self._models_json(), indent=2), encoding="utf-8"
        )

        argv = [
            self.pi_binary,
            "-p",
            "--no-session",
            "--offline",
            "--provider",
            self.provider_id,
            "--model",
            f"{self.provider_id}/{self.model}",
        ]
        if self.enable_tools:
            if not PI_EXTENSION.is_file():
                return AgentStep(
                    kind="harness_error",
                    payload={"error": f"pi extension missing: {PI_EXTENSION}"},
                    done=True,
                )
            # Built-ins off, extension tools on: the kernel's plane is the only tool source.
            argv += ["--no-builtin-tools", "-e", str(PI_EXTENSION)]
        else:
            argv += ["--no-tools"]
        argv.append(str(state.get("task", "")))

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
                payload={"error": f"pi exceeded {self.timeout_s}s"},
                done=True,
            )
        except FileNotFoundError:
            return AgentStep(
                kind="harness_error",
                payload={"error": f"pi binary not found: {self.pi_binary}"},
                done=True,
            )

        summary = stdout.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0:
            return AgentStep(
                kind="harness_error",
                payload={
                    "error": f"pi exited {proc.returncode}",
                    "stderr": stderr.decode("utf-8", errors="replace")[-2000:],
                    "stdout": summary[-2000:],
                },
                done=True,
            )
        state.setdefault("history", []).append(summary)
        return AgentStep(kind="done", payload={"summary": summary[-4000:]}, done=True)
