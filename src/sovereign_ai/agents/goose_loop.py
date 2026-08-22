from __future__ import annotations

import asyncio
import os
from typing import Any

from .base import AgentLoop, AgentStep


class GooseAgentLoop(AgentLoop):
    """Subprocess bridge to the compiled `goose` CLI (`knowledge/research.md` D-015).

    `D-015`'s safety boundary requires every external harness to stay subordinate: "the
    kernel issues the run_id, grants, leases and final state transition. Anything Goose
    reports is untrusted evidence until a verifier says otherwise." This adapter satisfies
    that boundary the simplest way that is still honest about what it does not yet do:
    every invocation passes `--no-profile` and no `--with-extension`/`--with-builtin`
    flag, so Goose is launched with **zero** filesystem or shell tool access. It cannot
    bypass `ExecutionBroker`/`PolicyEngine` because it has no path to touch anything
    outside the one text completion it returns -- not because a policy layer stopped it,
    but because it was never given the means. This is a smaller contract than
    `NativeAgentLoop`'s real per-step tool loop: `next_step()` here runs Goose's own CLI to
    completion in one subprocess call and returns a single `done` step, since the CLI does
    not hand control back to a caller between its own internal turns.

    Real per-step tool use (the same `read_file`/`list_directory`/`run_command` the kernel
    already exposes to `NativeAgentLoop`) would mean bridging Goose's MCP extension
    mechanism (`--with-extension`/`--with-streamable-http-extension`) to those same
    policy-gated calls. That is real, valuable follow-on work, deliberately not built
    here -- see `docs/FIXES.md`'s honest-limits note for this loop. Hand-rolling that
    bridge under time pressure risks either silently not working, or worse, accidentally
    handing Goose real unrestricted execution if the wiring is wrong; a text-only,
    zero-tool comparison today is safer than a rushed, unverified tool bridge.
    """

    def __init__(
        self,
        goose_binary: str,
        base_url: str,
        model: str,
        timeout_s: float = 120.0,
    ):
        self.goose_binary = goose_binary
        self.base_url = base_url
        self.model = model
        self.timeout_s = timeout_s

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
        try:
            proc = await asyncio.create_subprocess_exec(
                self.goose_binary,
                "run",
                "--no-profile",
                "--no-session",
                "-q",
                "--text",
                task,
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
