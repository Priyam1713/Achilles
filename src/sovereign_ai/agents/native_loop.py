from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sovereign_ai.execution.broker import ExecutionBroker
from sovereign_ai.execution.workspaces import WorkspaceRegistry
from sovereign_ai.inference.broker import InferenceBroker
from sovereign_ai.kernel.events import EventStore
from sovereign_ai.kernel.types import CapabilityRequest, RoutingMode, TrustLabel

from .base import AgentLoop, AgentStep

SYSTEM_PROMPT = """You are an agent working inside a sandboxed coding workspace. Every turn,
reply with EXACTLY ONE JSON object describing the next action, and nothing else -- no prose
before or after it.

Available tools:
  {{"tool": "read_file", "args": {{"path": "<absolute path>"}}}}
  {{"tool": "list_directory", "args": {{"path": "<absolute path>"}}}}
  {{"tool": "run_command", "args": {{"argv": ["<program>", "<arg>", ...], "mutates_state": <true|false>}}}}
  {{"tool": "done", "summary": "<what you found or accomplished>"}}

Rules:
- Set "mutates_state": false for read-only commands (tests, git status, git diff, linters).
  Set it true for anything that writes or changes files. A write may require human approval
  and be denied even if you request it -- if so, explain the situation and stop, do not retry
  the same denied action.
- The workspace for this task is: {workspace}
- Call "done" as soon as the task is answered or accomplished. Do not keep exploring after
  you have what you need.
"""


class NativeAgentLoop(AgentLoop):
    """The kernel's own reference agent loop.

    Deterministic JSON tool-call protocol, policy-gated execution (every mutating action
    goes through the same `ExecutionBroker.run_approved` used everywhere else in this
    project, so `docs/SECURITY.md`'s "untrusted model output cannot authorize mutation"
    applies to this loop exactly as it does to a human-triggered API call), and an
    append-only event for every step so a run is auditable after the fact, not just
    trusted because it finished.

    This exists so `D-001` ("no harness is the root of trust") has something concrete to
    mean, and so external harnesses like Goose (`D-015`) have a working reference to be
    compared against in the harness tournament, rather than being the only `AgentLoop`
    this project can actually run. It is deliberately simple: a real tool-calling protocol
    that a small local model can reliably produce, not an attempt to match a frontier
    coding agent's feature set in one pass.
    """

    max_steps_hard_cap = 25

    def __init__(
        self,
        inference: InferenceBroker,
        execution: ExecutionBroker,
        workspaces: WorkspaceRegistry,
        events: EventStore,
    ):
        self.inference = inference
        self.execution = execution
        self.workspaces = workspaces
        self.events = events

    async def next_step(self, state: dict[str, Any]) -> AgentStep:
        state.setdefault("history", [])
        history: list[dict[str, Any]] = state["history"]
        stream_id = f"agent-loop:{state.get('run_id', 'unscoped')}"
        step_count = len(history)
        step_budget = min(int(state.get("max_steps", 10)), self.max_steps_hard_cap)

        if step_count >= step_budget:
            return AgentStep(
                kind="budget_exhausted", payload={"steps_taken": step_count}, done=True
            )

        request = CapabilityRequest(
            capability=state.get("capability", "coding"),
            mode=RoutingMode(state.get("mode", "smart")),
        )
        try:
            result = await self.inference.chat(request, self._build_messages(state))
        except Exception as exc:
            return AgentStep(
                kind="inference_error", payload={"error": f"{type(exc).__name__}: {exc}"}, done=True
            )

        content = self._extract_content(result)
        action = self._parse_action(content)

        if action is None:
            observation = {
                "error": "could not parse a single JSON action from the reply",
                "raw": content[:500],
            }
            history.append({"assistant": content, "observation": observation})
            self.events.append(
                stream_id, "agent.step.unparsable", {"raw": content[:2000]},
                trust="untrusted_model_output",
            )
            return AgentStep(kind="unparsable", payload=observation, done=False)

        tool = action.get("tool")
        if tool == "done":
            summary = action.get("summary", "")
            self.events.append(
                stream_id, "agent.step.done", {"summary": summary},
                trust="untrusted_model_output",
            )
            return AgentStep(kind="done", payload={"summary": summary}, done=True)

        observation = await self._execute_tool(tool, action.get("args") or {}, state)
        history.append({"assistant": content, "action": action, "observation": observation})
        self.events.append(
            stream_id, "agent.step.tool_call",
            {"tool": tool, "args": action.get("args"), "observation": observation},
            trust="untrusted_model_output",
        )
        return AgentStep(kind="observation", payload={"tool": tool, "observation": observation}, done=False)

    def _build_messages(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        system = SYSTEM_PROMPT.format(workspace=state.get("workspace") or "(none registered)")
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        messages.append({"role": "user", "content": str(state.get("task", ""))})
        for turn in state.get("history", []):
            messages.append({"role": "assistant", "content": turn["assistant"]})
            observation = turn.get("observation")
            messages.append(
                {"role": "user", "content": f"Observation: {json.dumps(observation)[:4000]}"}
            )
        return messages

    @staticmethod
    def _extract_content(result: dict[str, Any]) -> str:
        payload = result.get("result") or {}
        choices = payload.get("choices") or []
        if choices:
            content = (choices[0].get("message") or {}).get("content")
            if isinstance(content, str):
                return content
        return ""

    @staticmethod
    def _parse_action(content: str) -> dict[str, Any] | None:
        # A small local model reliably emits one JSON object but not always with nothing
        # else around it (a stray code fence, a leading "Sure, here's my action:"); take
        # the outermost {...} span rather than requiring the whole reply to be pure JSON.
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(content[start : end + 1])
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) and "tool" in parsed else None

    async def _execute_tool(
        self, tool: Any, args: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        workspace = state.get("workspace")
        approved = bool(state.get("approved", False))
        try:
            if tool == "read_file":
                return self._read_file(args.get("path", ""))
            if tool == "list_directory":
                return self._list_directory(args.get("path") or workspace or "")
            if tool == "run_command":
                return await self._run_command(args, workspace, approved)
            return {"error": f"unknown tool: {tool!r}"}
        except PermissionError as exc:
            return {"error": f"denied: {exc}"}
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

    def _read_file(self, path: str) -> dict[str, Any]:
        if not path:
            return {"error": "read_file requires 'path'"}
        # Merely knowing a path never grants authority to read it (execution/workspaces.py):
        # the path must fall under a directory this operator explicitly registered.
        self.workspaces.require(path, require_write=False)
        target = Path(path)
        if not target.is_file():
            return {"error": f"not a file: {path}"}
        text = target.read_text(encoding="utf-8", errors="replace")
        return {"path": str(target), "content": text[:20000], "truncated": len(text) > 20000}

    def _list_directory(self, path: str) -> dict[str, Any]:
        if not path:
            return {"error": "list_directory requires 'path'"}
        self.workspaces.require(path, require_write=False)
        target = Path(path)
        if not target.is_dir():
            return {"error": f"not a directory: {path}"}
        entries = sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())
        return {"path": str(target), "entries": entries[:200]}

    async def _run_command(
        self, args: dict[str, Any], workspace: str | None, approved: bool
    ) -> dict[str, Any]:
        argv = args.get("argv")
        if not isinstance(argv, list) or not argv:
            return {"error": "run_command requires a non-empty 'argv' list"}
        mutates = bool(args.get("mutates_state", True))
        result = await self.execution.run_approved(
            [str(item) for item in argv],
            workspace,
            trust=TrustLabel.UNTRUSTED_MODEL_OUTPUT,
            approved=approved,
            mutates_state=mutates,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-2000:],
        }
