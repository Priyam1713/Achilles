from __future__ import annotations

import importlib.util
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: The points a hook can attach to. Small on purpose: Claude Code documents around thirty
#: lifecycle events, and `knowledge/harness-research.md` records that the *shape* is worth
#: stealing rather than the surface area. Four points cover injecting context, refusing an
#: action, annotating a result and observing the end of a run; each additional one is a
#: promise to keep working, so they get added when something needs them.
HOOK_POINTS = ("before_turn", "before_tool", "after_tool", "after_run")


@dataclass
class HookRegistry:
    """Operator-authored Python that runs inside the loop.

    Adapted from Pi's in-process extensions rather than Claude Code's subprocess hooks, and
    the difference is the point: a subprocess per tool call costs a process spawn on a
    machine where the whole budget is already latency, while an in-process call costs a
    function call. Pi's 25+ hooks are the mechanism `harness-research.md` singles out as
    "Claude Code's hook idea without the subprocess cost".

    **A hook can refuse and annotate. It can never authorise.** `before_tool` may return a
    denial and that denial is honoured; nothing it returns can make `PolicyEngine` allow an
    action it would otherwise refuse, and nothing it returns widens a `CapabilityGrant`. The
    same one-directional rule the advisor follows (F-061), for the same reason: adding a
    veto is safe, adding a permission is not.

    Hooks are **operator code, not model output** -- they arrive from a directory the
    operator controls, so they are trusted the way a config file is trusted. That is exactly
    why they must not be loadable from a workspace an agent can write to.
    """

    handlers: dict[str, list[Callable[..., Any]]] = field(
        default_factory=lambda: {point: [] for point in HOOK_POINTS}
    )
    errors: list[str] = field(default_factory=list)

    def on(self, point: str, handler: Callable[..., Any]) -> None:
        if point not in self.handlers:
            raise ValueError(f"unknown hook point: {point!r} (known: {', '.join(HOOK_POINTS)})")
        self.handlers[point].append(handler)

    def count(self) -> int:
        return sum(len(v) for v in self.handlers.values())

    # -- invocation --------------------------------------------------------------------

    def before_turn(self, state: dict[str, Any], messages: list[dict[str, Any]]):
        """Let hooks add to or filter the prompt for one turn.

        A hook returning a list replaces the messages; returning None leaves them. A hook
        that raises is recorded and skipped -- a broken extension must not take the loop
        down with it, and silently swallowing the error would make it undebuggable.
        """
        for handler in self.handlers["before_turn"]:
            try:
                replacement = handler(state, messages)
            except Exception as exc:
                self._record(handler, exc)
                continue
            if isinstance(replacement, list):
                messages = replacement
        return messages

    def before_tool(self, tool: Any, args: dict[str, Any], state: dict[str, Any]) -> str | None:
        """Return a refusal reason to block a tool call, or None to allow it.

        "Allow" here means "this hook has no objection" -- never "this hook authorises it".
        The action still faces every policy and grant check it would have faced.
        """
        for handler in self.handlers["before_tool"]:
            try:
                verdict = handler(tool, args, state)
            except Exception as exc:
                self._record(handler, exc)
                continue
            if isinstance(verdict, str) and verdict.strip():
                return verdict.strip()
            if verdict is False:
                return f"a hook refused {tool}"
        return None

    def after_tool(
        self, tool: Any, args: dict[str, Any], observation: dict[str, Any]
    ) -> dict[str, Any]:
        for handler in self.handlers["after_tool"]:
            try:
                replacement = handler(tool, args, observation)
            except Exception as exc:
                self._record(handler, exc)
                continue
            if isinstance(replacement, dict):
                observation = replacement
        return observation

    def after_run(self, state: dict[str, Any], step: Any) -> None:
        for handler in self.handlers["after_run"]:
            try:
                handler(state, step)
            except Exception as exc:
                self._record(handler, exc)

    def _record(self, handler: Callable[..., Any], exc: Exception) -> None:
        name = getattr(handler, "__name__", repr(handler))
        self.errors.append(f"{name}: {type(exc).__name__}: {exc}")


def load_hooks(directory: str | Path | None) -> HookRegistry:
    """Load every `*.py` in a directory, calling its `register(hooks)`.

    Deliberately explicit and unclever: no entry points, no package discovery, no import
    from anywhere the operator did not name. A hook is code this kernel executes with its
    own privileges, so where it comes from is a decision the operator makes by putting a
    file in a directory they control -- never something inferred from the environment.

    A file that fails to import is recorded and skipped. One bad extension should cost its
    own functionality, not the whole loop.
    """
    registry = HookRegistry()
    if not directory:
        return registry
    root = Path(directory)
    if not root.is_dir():
        return registry

    for path in sorted(root.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"sovereign_hook_{path.stem}", path)
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot load {path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            register = getattr(module, "register", None)
            if register is None:
                raise AttributeError("no register(hooks) function")
            register(registry)
        except Exception as exc:
            registry.errors.append(f"{path.name}: {type(exc).__name__}: {exc}")
    return registry
