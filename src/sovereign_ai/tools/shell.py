from __future__ import annotations

from typing import Any

from sovereign_ai.execution.broker import ExecutionBroker
from sovereign_ai.kernel.types import TrustLabel

from .base import Tool, ToolContext, tool_error
from .registry import ToolSpec


class RunCommandTool(Tool):
    """The original agent tool, moved into the tool plane unchanged in behaviour.

    Still routed through `ExecutionBroker.run_approved`, so it still runs inside OpenShell
    or the hardened Docker fallback and still cannot mutate without a grant or approval.
    """

    spec = ToolSpec(
        id="run_command",
        description="Run a command in the sandboxed workspace (tests, git, linters, builds)",
        capabilities=["coding", "execution", "shell"],
        risk_scope="workspace",
        schema={
            "args": {"argv": ["<program>", "<arg>"], "mutates_state": False},
            "note": "set mutates_state true for anything that writes; that needs a grant or approval",
        },
    )

    def __init__(self, execution: ExecutionBroker):
        self.execution = execution

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        argv = args.get("argv")
        if not isinstance(argv, list) or not argv:
            return tool_error("run_command requires a non-empty 'argv' list")
        mutates = bool(args.get("mutates_state", True))
        result = await self.execution.run_approved(
            [str(item) for item in argv],
            ctx.workspace,
            trust=TrustLabel.UNTRUSTED_MODEL_OUTPUT,
            approved=ctx.approved,
            mutates_state=mutates,
            subject_id=ctx.subject_id,
            workspace_lease_id=ctx.workspace_lease_id,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-2000:],
        }
