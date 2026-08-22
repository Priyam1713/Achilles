from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from .base import Tool, ToolContext, tool_error
from .registry import ToolSpec

StepStatus = Literal["pending", "active", "done", "blocked"]

_STATUS_MARK = {"pending": "[ ]", "active": "[>]", "done": "[x]", "blocked": "[!]"}


@dataclass
class PlanStep:
    step: str
    status: StepStatus = "pending"


@dataclass
class PlanStore:
    """The plans of in-flight runs, keyed by `run_id`.

    Deliberately in-memory and process-local. A plan is working state for one run, not a
    durable record: what actually happened is already in the append-only event journal, and
    persisting a second, model-authored account of it would create a source of truth that
    can disagree with the first.
    """

    plans: dict[str, list[PlanStep]] = field(default_factory=dict)

    def set(self, run_id: str, steps: list[PlanStep]) -> None:
        self.plans[run_id] = steps

    def get(self, run_id: str | None) -> list[PlanStep]:
        return self.plans.get(run_id or "", [])

    def render(self, run_id: str | None) -> str:
        steps = self.get(run_id)
        if not steps:
            return ""
        return "\n".join(f"{_STATUS_MARK[s.status]} {s.step}" for s in steps)


class UpdatePlanTool(Tool):
    """Let the agent keep a checklist, so the loop can put it back in front of it.

    Adapted from Cline's Focus Chain (`knowledge/harness-research.md`), which describes a
    re-injected todo list as "a north star that cuts through accumulating context noise".
    That is precisely the failure this project created for itself in F-049: history is
    elided deterministically to fit a 16K window, and nothing re-states the objective
    afterwards, so a long run can forget what it was doing while still having room to keep
    doing something.

    The plan is **written by the model, not generated for it**. Cline spends a turn
    producing a todo list up front; at 6-52 tok/s that is a whole generation before any work
    happens. Making it a tool means an agent that wants a plan pays for one, an agent that
    does not keeps its turns, and the loop re-injects whatever exists (falling back to the
    original objective, which costs nothing).
    """

    spec = ToolSpec(
        id="update_plan",
        description="Record or update the checklist for this task so it survives compaction",
        capabilities=["planning", "coding"],
        risk_scope="none",
        schema={
            "args": {
                "steps": [
                    "<short step description>",
                ],
                "statuses": ["pending|active|done|blocked"],
            },
            "note": "cheap and non-mutating; call it when the plan changes, not every turn",
        },
    )

    def __init__(self, plans: PlanStore):
        self.plans = plans

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        raw = args.get("steps")
        if not isinstance(raw, list) or not raw:
            return tool_error("update_plan requires a non-empty 'steps' list")
        statuses = args.get("statuses")
        statuses = statuses if isinstance(statuses, list) else []

        steps: list[PlanStep] = []
        for index, entry in enumerate(raw[:20]):
            # Accept both shapes a small model produces: a bare string, or an object with
            # its own status. Rejecting either would spend a turn teaching it the schema.
            if isinstance(entry, dict):
                text = str(entry.get("step") or entry.get("text") or "").strip()
                status = str(entry.get("status") or "pending")
            else:
                text = str(entry).strip()
                status = str(statuses[index]) if index < len(statuses) else "pending"
            if not text:
                continue
            if status not in _STATUS_MARK:
                status = "pending"
            steps.append(PlanStep(step=text[:200], status=status))  # type: ignore[arg-type]

        if not steps:
            return tool_error("update_plan received no usable steps")
        self.plans.set(ctx.run_id or "", steps)
        done = sum(1 for s in steps if s.status == "done")
        return {
            "recorded": len(steps),
            "done": done,
            "plan": self.plans.render(ctx.run_id),
        }
