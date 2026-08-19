from __future__ import annotations

import json
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DoFn = Callable[[], Awaitable[Any]]
UndoFn = Callable[[], Awaitable[Any]]
VerifyFn = Callable[[Any], Awaitable[bool]]


@dataclass
class TransactionStep:
    name: str
    do: DoFn
    undo: UndoFn | None = None
    verify: VerifyFn | None = None


@dataclass
class TransactionResult:
    id: str
    committed: bool
    completed: list[str] = field(default_factory=list)
    rolled_back: list[str] = field(default_factory=list)
    error: str | None = None


class TransactionManager:
    """Best-effort saga transactions for filesystem/tool/OS workflows.

    Database-native transactions should still use the database's own ACID transaction mechanism.
    """

    def __init__(self, journal_dir: str | Path):
        self.journal_dir = Path(journal_dir)
        self.journal_dir.mkdir(parents=True, exist_ok=True)

    async def run(self, steps: list[TransactionStep]) -> TransactionResult:
        txid = str(uuid.uuid4())
        result = TransactionResult(id=txid, committed=False)
        completed: list[tuple[TransactionStep, Any]] = []
        try:
            for step in steps:
                output = await step.do()
                if step.verify and not await step.verify(output):
                    raise RuntimeError(f"Post-condition failed: {step.name}")
                completed.append((step, output))
                result.completed.append(step.name)
                self._journal(txid, result)
            result.committed = True
            self._journal(txid, result)
            return result
        except Exception as exc:
            result.error = str(exc)
            for step, _ in reversed(completed):
                if step.undo:
                    try:
                        await step.undo()
                        result.rolled_back.append(step.name)
                    except Exception as rollback_exc:
                        result.error += f" | rollback {step.name} failed: {rollback_exc}"
            self._journal(txid, result)
            return result

    def _journal(self, txid: str, result: TransactionResult) -> None:
        path = self.journal_dir / f"{txid}.json"
        payload = {
            "id": result.id,
            "committed": result.committed,
            "completed": result.completed,
            "rolled_back": result.rolled_back,
            "error": result.error,
            "updated_at": time.time(),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
