from __future__ import annotations

from typing import Any

from .base import VerificationResult, Verifier
from .builtins import ExitCodeVerifier, FileHashVerifier


class VerificationEngine:
    def __init__(self):
        self.verifiers: dict[str, Verifier] = {
            "exit_code": ExitCodeVerifier(),
            "file_hash": FileHashVerifier(),
        }

    def register(self, name: str, verifier: Verifier) -> None:
        self.verifiers[name] = verifier

    async def verify(
        self, name: str, before: Any, after: Any, expectation: dict[str, Any]
    ) -> VerificationResult:
        if name not in self.verifiers:
            return VerificationResult(False, name, message="Verifier not registered")
        return await self.verifiers[name].verify(before, after, expectation)
