from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .base import VerificationResult, Verifier


class FileHashVerifier(Verifier):
    @staticmethod
    def sha256(path: str | Path) -> str:
        h = hashlib.sha256()
        with Path(path).open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    async def verify(
        self, before: Any, after: Any, expectation: dict[str, Any]
    ) -> VerificationResult:
        path = Path(expectation["path"])
        if not path.exists():
            return VerificationResult(False, "file_hash", message=f"Missing expected file: {path}")
        digest = self.sha256(path)
        expected = expectation.get("sha256")
        passed = expected is None or digest == expected
        return VerificationResult(
            passed, "file_hash", {"sha256": digest}, "ok" if passed else "hash mismatch"
        )


class ExitCodeVerifier(Verifier):
    async def verify(
        self, before: Any, after: Any, expectation: dict[str, Any]
    ) -> VerificationResult:
        code = getattr(
            after, "returncode", after.get("returncode") if isinstance(after, dict) else None
        )
        expected = int(expectation.get("returncode", 0))
        return VerificationResult(
            code == expected, "exit_code", {"actual": code, "expected": expected}
        )
