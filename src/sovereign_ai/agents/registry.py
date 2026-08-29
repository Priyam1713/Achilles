from __future__ import annotations

from .base import AgentLoop


class AgentLoopRegistry:
    """External harnesses are plugins above the kernel, never trusted kernel dependencies."""

    def __init__(self, default_name: str = "native"):
        self._loops: dict[str, AgentLoop] = {}
        self.default_name = default_name

    def register(self, name: str, loop: AgentLoop) -> None:
        self._loops[name] = loop

    def get(self, name: str | None = None) -> AgentLoop:
        name = name or self.default_name
        if name not in self._loops:
            raise KeyError(f"Agent loop not registered: {name}")
        return self._loops[name]

    def names(self) -> list[str]:
        return sorted(self._loops)
