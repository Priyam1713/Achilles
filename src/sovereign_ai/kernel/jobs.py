from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

JobKind = Literal["chat", "specialist", "media", "agent"]
JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled", "interrupted"]


class JobRecord(BaseModel):
    id: str
    kind: JobKind
    status: JobStatus
    request: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    cancellation_requested: bool = False
    created_at: float
    updated_at: float
    started_at: float | None = None
    finished_at: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobStore:
    """Durable local job journal for work that outlives an HTTP connection."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    cancellation_requested INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    started_at REAL,
                    finished_at REAL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS jobs_status_updated ON jobs(status, updated_at DESC)"
            )

    @staticmethod
    def _record(row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            id=row["id"],
            kind=row["kind"],
            status=row["status"],
            request=json.loads(row["request_json"]),
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            error=row["error"],
            cancellation_requested=bool(row["cancellation_requested"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            metadata=json.loads(row["metadata_json"]),
        )

    def create(
        self, kind: JobKind, request: dict[str, Any], metadata: dict[str, Any] | None = None
    ) -> JobRecord:
        job_id = uuid.uuid4().hex
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO jobs(id,kind,status,request_json,created_at,updated_at,metadata_json) VALUES(?,?,?,?,?,?,?)",
                (job_id, kind, "queued", json.dumps(request), now, now, json.dumps(metadata or {})),
            )
        record = self.get(job_id)
        assert record is not None
        return record

    def get(self, job_id: str) -> JobRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._record(row) if row else None

    def list(self, status: JobStatus | None = None, limit: int = 50) -> list[JobRecord]:
        limit = max(1, min(limit, 500))
        with self._connect() as connection:
            if status:
                rows = connection.execute(
                    "SELECT * FROM jobs WHERE status=? ORDER BY updated_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM jobs ORDER BY updated_at DESC LIMIT ?", (limit,)
                ).fetchall()
        return [self._record(row) for row in rows]

    def mark_running(self, job_id: str) -> None:
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                "UPDATE jobs SET status='running',started_at=?,updated_at=? WHERE id=? AND status='queued'",
                (now, now, job_id),
            )

    def finish(
        self,
        job_id: str,
        status: Literal["succeeded", "failed", "cancelled"],
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                "UPDATE jobs SET status=?,result_json=?,error=?,updated_at=?,finished_at=? WHERE id=?",
                (
                    status,
                    json.dumps(result) if result is not None else None,
                    error,
                    now,
                    now,
                    job_id,
                ),
            )

    def request_cancel(self, job_id: str) -> JobRecord | None:
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                "UPDATE jobs SET cancellation_requested=1,updated_at=? WHERE id=? AND status IN ('queued','running')",
                (now, job_id),
            )
        return self.get(job_id)

    def recover_interrupted(self) -> int:
        now = time.time()
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE jobs SET status='interrupted',error='kernel restarted before completion',
                   updated_at=?,finished_at=? WHERE status IN ('queued','running')""",
                (now, now),
            )
            return cursor.rowcount
