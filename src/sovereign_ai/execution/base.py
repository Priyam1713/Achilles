from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    returncode: int
    stdout: str
    stderr: str
    backend: str


class ExecutionBackend(ABC):
    @abstractmethod
    async def run(self, argv: Sequence[str], cwd: str | None = None) -> ExecutionResult: ...
