from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .migrations import Migration, MigrationRunner

RunStatus = Literal["queued", "running", "succeeded", "failed", "cancelled", "interrupted"]

MIGRATIONS = [
    Migration(
        version=1,
        name="create_runs_table",
        sql="""
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                status TEXT NOT NULL,
                request_json TEXT NOT NULL,
                result_json TEXT,
                error TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                started_at REAL,
                finished_at REAL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                UNIQUE(job_id, attempt)
            );
            CREATE INDEX IF NOT EXISTS runs_job_attempt ON runs(job_id, attempt DESC);
            CREATE INDEX IF NOT EXISTS runs_status_updated ON runs(status, updated_at DESC);
        """,
    ),
]


class RunRecord(BaseModel):
    """One execution attempt beneath a `Job` (FIXES.md F-010, design D-008).

    A `Job` records the requested outcome and its current best-known status. A `Run`
    records exactly what was attempted -- retrying a failed job creates a *new* Run rather
    than rewriting history, so `RunStore.list_for_job` is a true attempt log even after
    several retries.
    """

    id: str
    job_id: str
    attempt: int
    status: RunStatus
    request: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float
    updated_at: float
    started_at: float | None = None
    finished_at: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunStore:
    """Durable attempt journal, one row per execution attempt of a job."""

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
    def _record(row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            id=row["id"],
            job_id=row["job_id"],
            attempt=row["attempt"],
            status=row["status"],
            request=json.loads(row["request_json"]),
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            metadata=json.loads(row["metadata_json"]),
        )

    def create(
        self,
        job_id: str,
        attempt: int,
        request: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> RunRecord:
        run_id = uuid.uuid4().hex
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO runs(id,job_id,attempt,status,request_json,created_at,
                   updated_at,metadata_json) VALUES(?,?,?,?,?,?,?,?)""",
                (run_id, job_id, attempt, "queued", json.dumps(request), now, now,
                 json.dumps(metadata or {})),
            )
        record = self.get(run_id)
        assert record is not None
        return record

    def get(self, run_id: str) -> RunRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return self._record(row) if row else None

    def list_for_job(self, job_id: str) -> list[RunRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM runs WHERE job_id=? ORDER BY attempt ASC", (job_id,)
            ).fetchall()
        return [self._record(row) for row in rows]

    def next_attempt(self, job_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT MAX(attempt) AS m FROM runs WHERE job_id=?", (job_id,)
            ).fetchone()
        return (row["m"] or 0) + 1

    def mark_running(self, run_id: str) -> None:
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                "UPDATE runs SET status='running',started_at=?,updated_at=? WHERE id=? AND status='queued'",
                (now, now, run_id),
            )

    def finish(
        self,
        run_id: str,
        status: Literal["succeeded", "failed", "cancelled"],
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                "UPDATE runs SET status=?,result_json=?,error=?,updated_at=?,finished_at=? WHERE id=?",
                (status, json.dumps(result) if result is not None else None, error, now, now, run_id),
            )

    def recover_interrupted(self) -> int:
        """Mark attempts orphaned by a kernel restart. Mirrors JobStore.recover_interrupted;
        called alongside it so a Job's status and its most recent Run's status never
        disagree about whether work is actually still in flight."""
        now = time.time()
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE runs SET status='interrupted',error='kernel restarted before completion',
                   updated_at=?,finished_at=? WHERE status IN ('queued','running')""",
                (now, now),
            )
            return cursor.rowcount
