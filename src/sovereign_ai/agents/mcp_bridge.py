"""A policy-gated MCP stdio server exposing the kernel's own read_file/list_directory/
run_command tools -- the tool bridge `FIXES.md` F-043 named as real follow-on work rather
than build under time pressure. Any MCP client that launches this as a stdio extension
(Goose's own `--with-extension`, per its `--help`: "Add stdio extensions from full
commands") gets exactly the same three tools `NativeAgentLoop` (`agents/native_loop.py`)
already exposes to the kernel's own reference loop, calling the identical underlying
primitives -- `WorkspaceRegistry.require()` and `ExecutionBroker.run_approved()` -- so an
external harness reached through this bridge is held to the same policy gate as the
in-process reference loop, not a weaker one built in a hurry.

Usage (matches Goose's `--with-extension` format, `'[name:]ENV1=val1 ENV2=val2 command
args...'`):

    goose run --no-profile --no-session -q --text "..." \
      --with-extension "kernel_tools:SOAI_MCP_AGENT_PROFILE_ID=<id> \
        SOAI_MCP_WORKSPACE=<workspace_path> SOVEREIGN_CONFIG_ROOT=<path> \
        SOVEREIGN_STATE_DIR=<path> python3 -m sovereign_ai.agents.mcp_bridge"

`SOAI_MCP_AGENT_PROFILE_ID` is required: it is the `subject_id` every `run_command` call
checks a `CapabilityGrant` against (kernel/capability_grants.py), exactly as
`AgentPayload.agent_profile_id` already does for the in-process reference loop
(`kernel/job_executor.py`). A bridge invocation with no grantable identity can still
attempt a call -- and, correctly, still be denied by the same fail-closed
`PolicyEngine`/`CapabilityGrant` check every other execute path in this kernel goes
through (FIXES.md F-036/F-037). Nothing about running through MCP instead of the native
loop's own protocol changes what is or is not authorized.
"""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from sovereign_ai.kernel.app import SovereignKernel
from sovereign_ai.kernel.types import TrustLabel

mcp = FastMCP("sovereign-ai-kernel-tools")

_kernel: SovereignKernel | None = None


def _get_kernel() -> SovereignKernel:
    global _kernel
    if _kernel is None:
        _kernel = SovereignKernel.build(os.environ.get("SOVEREIGN_CONFIG_ROOT"))
    return _kernel


def _agent_profile_id() -> str | None:
    return os.environ.get("SOAI_MCP_AGENT_PROFILE_ID")


def _workspace() -> str | None:
    return os.environ.get("SOAI_MCP_WORKSPACE")


@mcp.tool()
def read_file(path: str) -> str:
    """Read a text file. `path` must be inside a workspace this operator registered --
    merely knowing a path never grants authority to read it."""
    kernel = _get_kernel()
    kernel.workspaces.require(path, require_write=False)
    target = Path(path)
    if not target.is_file():
        return f"error: not a file: {path}"
    text = target.read_text(encoding="utf-8", errors="replace")
    truncated = len(text) > 20000
    return text[:20000] + ("\n...[truncated]" if truncated else "")


@mcp.tool()
def list_directory(path: str) -> str:
    """List a directory's immediate entries. Same workspace-registration requirement as
    `read_file`."""
    kernel = _get_kernel()
    kernel.workspaces.require(path, require_write=False)
    target = Path(path)
    if not target.is_dir():
        return f"error: not a directory: {path}"
    entries = sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())
    return "\n".join(entries[:200])


@mcp.tool()
async def run_command(argv: list[str], mutates_state: bool = True) -> str:
    """Run a command inside a registered workspace. Every call is evaluated by the same
    fail-closed `PolicyEngine`/`CapabilityGrant` check every other execute path in this
    kernel goes through (FIXES.md F-036/F-037): with no active grant for the identity in
    `SOAI_MCP_AGENT_PROFILE_ID`, a mutating command is denied, not merely logged as risky.
    `trust=UNTRUSTED_MODEL_OUTPUT` is not settable by the caller, matching
    `NativeAgentLoop._run_command` -- an external harness's output is exactly as trusted
    as the reference loop's own, never more.

    Declared `async` and awaited directly rather than wrapped in `asyncio.run()` --
    FastMCP's stdio transport already runs inside its own event loop, and nesting
    `asyncio.run()` inside a running loop raises `RuntimeError` at call time. Caught live
    the first time this ran through a real `goose` invocation, not in a unit test: the
    tool crashed with exactly that error on every attempt, so the file it was trying to
    (not) delete stayed untouched for the wrong reason -- a crash, not a policy denial.
    """
    if not argv:
        return "error: run_command requires a non-empty argv list"
    kernel = _get_kernel()
    result = await kernel.execution.run_approved(
        [str(item) for item in argv],
        _workspace(),
        trust=TrustLabel.UNTRUSTED_MODEL_OUTPUT,
        approved=False,
        mutates_state=mutates_state,
        subject_id=_agent_profile_id(),
    )
    return (
        f"returncode: {result.returncode}\n"
        f"stdout: {result.stdout[-4000:]}\n"
        f"stderr: {result.stderr[-2000:]}"
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
