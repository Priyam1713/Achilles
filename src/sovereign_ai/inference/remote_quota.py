from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path

from sovereign_ai.kernel.migrations import Migration, MigrationRunner

MIGRATIONS = [
    Migration(
        version=1,
        name="create_remote_calls_table",
        sql="""
            CREATE TABLE IF NOT EXISTS remote_calls (
                id TEXT PRIMARY KEY,
                engine_id TEXT NOT NULL,
                model_id TEXT NOT NULL,
                status TEXT NOT NULL,
                route_reason TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                cost_usd REAL NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS remote_calls_engine_time
                ON remote_calls(engine_id, created_at);
        """,
    ),
]


class RemoteQuotaLedger:
    """Provenance and budget accounting for every remote-inference call attempt.

    `knowledge/research.md`'s remote-inference policy requires "request, token, cost,
    quota, timeout, and circuit-breaker limits" and "provenance recording of provider,
    model, endpoint, and route reason" before any remote provider may be enabled. This is
    the one ledger both requirements share: every attempt (successful, failed, or refused
    before it ever left the machine) is one row, so budget checks and the provenance trail
    are the same read instead of two things that can drift apart.

    A row is written for a refusal too (`status="refused"`, zero tokens/cost) so a
    circuit-breaker trip or an exhausted daily budget is itself part of the audit trail,
    not a silent no-op.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        MigrationRunner(self.path, MIGRATIONS).apply_pending()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def record(
        self,
        engine_id: str,
        model_id: str,
        *,
        status: str,
        route_reason: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
        now: float | None = None,
    ) -> None:
        if status not in {"success", "failure", "refused"}:
            raise ValueError(f"unknown remote call status: {status!r}")
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO remote_calls
                   (id,engine_id,model_id,status,route_reason,prompt_tokens,
                    completion_tokens,cost_usd,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    uuid.uuid4().hex,
                    engine_id,
                    model_id,
                    status,
                    route_reason,
                    prompt_tokens,
                    completion_tokens,
                    cost_usd,
                    now if now is not None else time.time(),
                ),
            )

    def usage_today(self, engine_id: str, *, now: float | None = None) -> dict[str, float]:
        """Requests, tokens and cost attributed to `engine_id` in the current UTC day.

        Requests count every attempt regardless of outcome (a refused or failed call still
        consumed a slot against `max_requests_per_day`); tokens and cost count successes
        only, since a failed or refused call moved no tokens and was never billed.
        """
        now = now if now is not None else time.time()
        day_start = now - (now % 86400)
        with self._connect() as connection:
            row = connection.execute(
                """SELECT
                       COUNT(*) AS requests,
                       COALESCE(SUM(CASE WHEN status='success' THEN prompt_tokens + completion_tokens ELSE 0 END), 0) AS tokens,
                       COALESCE(SUM(CASE WHEN status='success' THEN cost_usd ELSE 0 END), 0) AS cost_usd
                   FROM remote_calls
                   WHERE engine_id = ? AND created_at >= ?""",
                (engine_id, day_start),
            ).fetchone()
        return {"requests": row["requests"], "tokens": row["tokens"], "cost_usd": row["cost_usd"]}

    def consecutive_failures(self, engine_id: str) -> int:
        """Failures since the most recent success, for circuit-breaker tripping.

        A `refused` row (budget/breaker already open) does not count as a new failure and
        does not reset the streak -- only a real `success` clears it.
        """
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT status FROM remote_calls
                   WHERE engine_id = ? AND status != 'refused'
                   ORDER BY created_at DESC""",
                (engine_id,),
            ).fetchall()
        streak = 0
        for row in rows:
            if row["status"] == "failure":
                streak += 1
            else:
                break
        return streak

    def last_failure_at(self, engine_id: str) -> float | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT MAX(created_at) AS t FROM remote_calls WHERE engine_id = ? AND status = 'failure'",
                (engine_id,),
            ).fetchone()
        return row["t"]
