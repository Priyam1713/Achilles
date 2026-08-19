from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentStep:
    kind: str
    payload: dict[str, Any]
    done: bool = False
    notes: list[str] = field(default_factory=list)


class AgentLoop(ABC):
    @abstractmethod
    async def next_step(self, state: dict[str, Any]) -> AgentStep: ...
