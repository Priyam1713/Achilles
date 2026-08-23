from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any

from .registry import ToolSpec


@dataclass
class ToolContext:
    """Everything a tool needs to know about *who* is calling and under what authority.

    Deliberately small and explicit. A tool never reaches back into the kernel for the
    caller's identity, because that is exactly how an agent ends up borrowing authority it
    was not granted: the caller states its subject, its workspace and whether a human has
    approved this step, and the tool is judged against that statement by the same
    `PolicyEngine`/`CapabilityGrant` path every other mutation in this project passes
    through (`knowledge/research.md` D-034).
    """

    workspace: str | None = None
    approved: bool = False
    subject_id: str | None = None
    workspace_lease_id: str | None = None
    run_id: str | None = None
    #: When set, file mutations accumulate here instead of touching the workspace, and are
    #: applied atomically after a human reads the diff (`kernel/sandbox.py`). Writing into a
    #: sandbox needs no grant because it changes nothing real; applying does.
    sandbox: Any | None = None


class Tool(abc.ABC):
    """One capability an agent can actually invoke.

    Wave 8 found `ToolRegistry` holding zero tools while 35 models sat installed and
    unreachable. This class is the seam that closes that: a capability is not delivered
    until it is a `Tool`, registered, discoverable and policy-gated (D-034).
    """

    #: Populated by subclasses; also what gets registered for contextual discovery.
    spec: ToolSpec

    @abc.abstractmethod
    async def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        """Execute the tool. Return a JSON-serialisable dict.

        Raise `PermissionError` when policy or a missing grant denies the action -- the
        dispatcher turns that into a structured `{"error": ..., "denied": true}`
        observation rather than an exception, because a denial is information the agent
        should reason about, not a crash.
        """
        raise NotImplementedError


def tool_error(message: str, **extra: Any) -> dict[str, Any]:
    return {"error": message, **extra}
