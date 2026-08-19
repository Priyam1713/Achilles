from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolSpec:
    id: str
    description: str
    capabilities: list[str]
    risk_scope: str = "workspace"
    schema: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


class ToolRegistry:
    """Contextual tool discovery: agents see a small relevant roster, never the entire tool universe."""

    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec):
        self._tools[spec.id] = spec

    def discover(
        self, query: str, capabilities: list[str] | None = None, limit: int = 8
    ) -> list[ToolSpec]:
        q = set(re.findall(r"[a-z0-9_]+", query.lower()))
        caps = set(capabilities or [])
        scored = []
        for t in self._tools.values():
            if not t.enabled:
                continue
            text = set(re.findall(r"[a-z0-9_]+", (t.id + " " + t.description).lower()))
            score = len(q & text) * 2 + len(caps & set(t.capabilities)) * 4
            if score:
                scored.append((score, t))
        scored.sort(key=lambda x: (x[0], x[1].id), reverse=True)
        return [t for _, t in scored[:limit]]
