from __future__ import annotations

from typing import Any

from .base import Tool, ToolContext, tool_error
from .registry import ToolSpec

#: How deep sub-tasks may nest. One level only: a sub-task that can spawn sub-tasks turns a
#: bounded step budget into an unbounded tree, and the failure mode is a run that looks busy
#: forever. Depth is carried in the child's `run_id`, so it survives across the loop boundary
#: without a second piece of state to keep in sync.
MAX_DEPTH = 1


class SpawnSubtaskTool(Tool):
    """Run a self-contained piece of work in a **fresh context** and return only its result.

    Adapted from Roo/Kilo's Boomerang Tasks (`knowledge/harness-research.md`): the parent
    pauses, the child runs in its own context, and the parent resumes **with only the
    summary**. That last clause is the whole point, and the reason this is worth building on
    a 16 K window -- a search that takes nine turns costs the parent one observation instead
    of nine, so the expensive context is spent on the task rather than on the looking.

    Authority is inherited, never widened: the child runs with the parent's `subject_id`,
    workspace and approval state, so every grant check it faces is the one the parent would
    have faced. A sub-task is a way to spend *context* differently, not a way to spend
    *authority* differently.

    The hand-back is deliberately narrow -- `succeeded`, `summary`, `steps` -- because an
    unstructured one is how a child's prose becomes a parent's confusion. oh-my-pi makes the
    same point about schema-validated subagent results.

    **Executed by the loop, not by this class.** The registered tool carries the schema so
    the roster and constrained decoding know about it, but a sub-task needs a loop of the
    *caller's* shape, and a tool registered in a shared dispatcher only ever holds a
    reference to whoever registered it first. That is not a theoretical problem: it made a
    test loop with scripted inference silently delegate to the kernel's real model.
    `NativeAgentLoop` therefore intercepts the call and builds its own child; reaching this
    class's `run()` means it was invoked outside a loop, and it says so rather than doing
    something surprising.
    """

    spec = ToolSpec(
        id="spawn_subtask",
        description=(
            "Run a self-contained sub-task in its own fresh context and get back just its "
            "result (use for searches or investigations whose intermediate steps you do not "
            "need)"
        ),
        capabilities=["planning", "coding", "delegation"],
        risk_scope="workspace",
        schema={
            "args": {"objective": "<what the sub-task should achieve>", "max_steps": 8},
            "note": "the sub-task inherits your authority exactly; it cannot do more than you can",
        },
    )

    def __init__(self, max_steps_cap: int = 12):
        self.max_steps_cap = max_steps_cap

    @staticmethod
    def _depth(run_id: str | None) -> int:
        return (run_id or "").count(":sub")

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return tool_error(
            "spawn_subtask can only be used from inside an agent loop, which runs the "
            "sub-task itself; calling it through the bare tool plane does nothing"
        )

    def prepare(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        """Validate a request and build the child's starting state, or return an error.

        Kept here rather than in the loop so the rules that make a sub-task safe -- an
        objective is required, depth is capped, the budget is bounded, and authority is
        inherited verbatim -- live next to the tool they belong to.
        """
        objective = str(args.get("objective") or "").strip()
        if not objective:
            return {"error": "spawn_subtask requires an 'objective'"}
        if self._depth(ctx.run_id) >= MAX_DEPTH:
            return {
                "error": "sub-tasks cannot nest further; do this work directly",
                "depth": self._depth(ctx.run_id),
            }

        max_steps = max(1, min(int(args.get("max_steps") or 8), self.max_steps_cap))
        child_run_id = f"{ctx.run_id or 'unscoped'}:sub{self._depth(ctx.run_id) + 1}"
        state: dict[str, Any] = {
            "run_id": child_run_id,
            "task": objective,
            # Fresh history: this is the isolation, and it is the entire value.
            "history": [],
            "workspace": ctx.workspace,
            # Inherited verbatim. A child must not be a way to escape the parent's limits.
            "approved": ctx.approved,
            "agent_profile_id": ctx.subject_id,
            "workspace_lease_id": ctx.workspace_lease_id,
            "max_steps": max_steps,
        }
        return {"state": state, "objective": objective, "max_steps": max_steps}

    @staticmethod
    def result(objective: str, outcome: str, summary: str, steps: int) -> dict[str, Any]:
        """The narrow, structured hand-back."""
        succeeded = outcome == "done" and bool(summary)
        return {
            "objective": objective,
            "succeeded": succeeded,
            "outcome": outcome,
            "steps": steps,
            # The only thing that reaches the parent's context.
            "summary": summary[:2000] if succeeded else "",
            "note": (
                "sub-task completed" if succeeded else f"sub-task did not finish ({outcome})"
            ),
        }
