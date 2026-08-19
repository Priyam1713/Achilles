from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VerificationResult:
    passed: bool
    verifier: str
    evidence: dict[str, Any] = field(default_factory=dict)
    message: str = ""


class Verifier(ABC):
    @abstractmethod
    async def verify(
        self, before: Any, after: Any, expectation: dict[str, Any]
    ) -> VerificationResult: ...
