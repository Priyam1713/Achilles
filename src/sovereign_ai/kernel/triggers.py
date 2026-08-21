from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path

from pydantic import BaseModel

from .migrations import Migration, MigrationRunner

MIGRATIONS = [
    Migration(
        version=1,
        name="create_recurring_triggers_table",
        sql="""
            CREATE TABLE IF NOT EXISTS recurring_triggers (
                id TEXT PRIMARY KEY,
                workflow_definition_id TEXT NOT NULL,
                interval_seconds REAL NOT NULL,
                enabled INTEGER NOT NULL,
                next_run_at REAL NOT NULL,
                last_run_at REAL,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS recurring_triggers_due
                ON recurring_triggers(enabled, next_run_at);
        """,
    ),
]


class RecurringTriggerRecord(BaseModel):
    """A time-bounded schedule that starts a `WorkflowInstance` automatically (FIXES.md
    Tier 5) -- the "recurring triggers" half of `docs/IMPLEMENTATION_STATUS.md`'s pending
    item that F-038 explicitly left open.

    Owns: which `WorkflowDefinition` to start and how often.

    Must not own: workflow execution itself -- `TriggerScheduler` only ever calls the
    existing `WorkflowService.start()`, the same method a human-initiated
    `POST /workflows/definitions/{id}/start` call already uses. A trigger is a second way
    to *initiate* a workflow instance, never a second way to *run* one.
    """

    id: str
    workflow_definition_id: str
    interval_seconds: float
    enabled: bool
    next_run_at: float
    last_run_at: float | None = None
    created_at: float


class RecurringTriggerStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        MigrationRunner(self.path, MIGRATIONS).apply_pending()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @staticmethod
    def _record(row: sqlite3.Row) -> RecurringTriggerRecord:
        return RecurringTriggerRecord(
            id=row["id"],
            workflow_definition_id=row["workflow_definition_id"],
            interval_seconds=row["interval_seconds"],
            enabled=bool(row["enabled"]),
            next_run_at=row["next_run_at"],
            last_run_at=row["last_run_at"],
            created_at=row["created_at"],
        )

    def create(
        self, workflow_definition_id: str, interval_seconds: float, *, enabled: bool = True
    ) -> RecurringTriggerRecord:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        trigger_id = uuid.uuid4().hex
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO recurring_triggers
                   (id,workflow_definition_id,interval_seconds,enabled,next_run_at,created_at)
                   VALUES(?,?,?,?,?,?)""",
                (trigger_id, workflow_definition_id, interval_seconds, int(enabled), now + interval_seconds, now),
            )
        record = self.get(trigger_id)
        assert record is not None
        return record

    def get(self, trigger_id: str) -> RecurringTriggerRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM recurring_triggers WHERE id=?", (trigger_id,)
            ).fetchone()
        return self._record(row) if row else None

    def list(self) -> list[RecurringTriggerRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM recurring_triggers ORDER BY created_at"
            ).fetchall()
        return [self._record(row) for row in rows]

    def due(self, *, now: float | None = None) -> list[RecurringTriggerRecord]:
        now = now if now is not None else time.time()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM recurring_triggers WHERE enabled=1 AND next_run_at<=? ORDER BY next_run_at",
                (now,),
            ).fetchall()
        return [self._record(row) for row in rows]

    def mark_ran(self, trigger_id: str, *, now: float | None = None) -> RecurringTriggerRecord:
        now = now if now is not None else time.time()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT interval_seconds FROM recurring_triggers WHERE id=?", (trigger_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Unknown recurring trigger: {trigger_id}")
            connection.execute(
                "UPDATE recurring_triggers SET last_run_at=?, next_run_at=? WHERE id=?",
                (now, now + row["interval_seconds"], trigger_id),
            )
        record = self.get(trigger_id)
        assert record is not None
        return record

    def set_enabled(self, trigger_id: str, enabled: bool) -> RecurringTriggerRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE recurring_triggers SET enabled=? WHERE id=?", (int(enabled), trigger_id)
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Unknown recurring trigger: {trigger_id}")
        record = self.get(trigger_id)
        assert record is not None
        return record
