from __future__ import annotations

import json
from typing import Any

from .base import Tool, ToolContext
from .plan import PlanStore
from .registry import ToolRegistry, ToolSpec


class ToolDispatcher:
    """The tool plane: what an agent can actually do.

    `ToolRegistry` already knew how to *rank* tools contextually and, until wave 8, had
    nothing registered in it -- "contextual tool discovery" was a working algorithm over an
    empty dictionary. The dispatcher is the missing half: it owns the tool instances, keeps
    the registry's specs in sync, renders the prompt-facing description, and routes an
    invocation to exactly one tool.

    It intentionally does *not* enforce policy itself. Each tool authorises through the
    kernel's existing `ExecutionBroker`/`PolicyEngine`/`CapabilityGrant` path, so adding a
    tool can never create a new authority path (`knowledge/research.md` D-034).
    """

    def __init__(self, registry: ToolRegistry | None = None):
        self.registry = registry or ToolRegistry()
        self._tools: dict[str, Tool] = {}
        # Working state for in-flight runs, shared between the `update_plan` tool that
        # writes it and the loop that re-injects it (`knowledge/harness-research.md`,
        # Cline's Focus Chain). It lives here so both halves get the same instance without
        # threading a second object through every constructor.
        self.plans = PlanStore()

    def register(self, tool: Tool) -> None:
        self.registry.register(tool.spec)
        self._tools[tool.spec.id] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def specs(self) -> list[ToolSpec]:
        return [self._tools[name].spec for name in self.names()]

    def discover(self, query: str, capabilities: list[str] | None = None, limit: int = 8):
        return self.registry.discover(query, capabilities, limit)

    def describe(self, specs: list[ToolSpec] | None = None) -> str:
        """Render tools as prompt text.

        One line per tool with an explicit JSON argument shape, because a 9B model copying
        a concrete example is dramatically more reliable than one inferring a schema. The
        risk scope is included so the model can predict a denial instead of retrying into
        one.
        """
        lines = []
        for spec in specs if specs is not None else self.specs():
            args = json.dumps(spec.schema.get("args", {}), sort_keys=True)
            note = spec.schema.get("note")
            line = f'  {{"tool": "{spec.id}", "args": {args}}}  -- {spec.description}'
            if note:
                line += f" ({note})"
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def json_schema_for(spec: ToolSpec) -> dict[str, Any]:
        """A JSON Schema for one tool's arguments, inferred from its example args.

        `ToolSpec.schema["args"]` is written as a *worked example* because that is what a
        small local model copies most reliably in a prompt. A protocol client needs a real
        schema, so this derives one from the same source rather than maintaining a second
        declaration that can drift from the first.

        Types come from the example values; every field is optional because tools already
        validate their own arguments and return a legible error, and an over-strict schema
        turns a fixable mistake into a rejected call the model never sees the reason for.
        """
        args = spec.schema.get("args") or {}
        properties: dict[str, Any] = {}
        for name, example in args.items():
            if isinstance(example, bool):
                properties[name] = {"type": "boolean"}
            elif isinstance(example, int):
                properties[name] = {"type": "integer"}
            elif isinstance(example, float):
                properties[name] = {"type": "number"}
            elif isinstance(example, list):
                properties[name] = {"type": "array", "items": {"type": "string"}}
            elif isinstance(example, dict):
                properties[name] = {"type": "object", "additionalProperties": True}
            else:
                properties[name] = {"type": "string", "description": str(example)}
        return {
            "type": "object",
            "properties": properties,
            "additionalProperties": True,
        }

    def action_schema(self, specs: list[ToolSpec] | None = None) -> dict[str, Any]:
        """A JSON schema for one agent action, derived from the registered tools.

        This is what makes `D-020` enforceable rather than aspirational: constrained
        decoding needs a schema, and a schema written by hand drifts from the tool plane
        the moment a tool is added. Deriving it from the registry means the set of tool
        names a model is *allowed to emit* is, by construction, the set that exists.

        `args` is deliberately loose. The goal of constraining decode is to guarantee a
        parseable action, not to encode every tool's argument rules -- tools validate
        their own arguments and return a legible error, which a model can act on, whereas
        an over-tight grammar produces a truncated or looping generation, which it cannot.
        """
        names = [*(spec.id for spec in (specs if specs is not None else self.specs())), "done"]
        return {
            "type": "object",
            "properties": {
                "tool": {"type": "string", "enum": names},
                "args": {"type": "object"},
                "summary": {"type": "string"},
            },
            "required": ["tool"],
            "additionalProperties": False,
        }

    async def invoke(
        self, name: Any, args: dict[str, Any] | None, ctx: ToolContext
    ) -> dict[str, Any]:
        tool = self._tools.get(name) if isinstance(name, str) else None
        if tool is None:
            return {
                "error": f"unknown tool: {name!r}",
                "available": self.names(),
            }
        try:
            return await tool.run(args or {}, ctx)
        except PermissionError as exc:
            # A denial is an observation, not a crash: the loop should be able to explain
            # it and stop, per NativeAgentLoop's own system prompt.
            return {"error": f"denied: {exc}", "denied": True}
        except Exception as exc:
            # Surfaced to the agent as an observation rather than crashing the run.
            return {"error": f"{type(exc).__name__}: {exc}"}
