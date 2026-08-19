from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class CheckpointStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    job_id TEXT PRIMARY KEY,
                    ts REAL NOT NULL,
                    state_json TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )

    def save(self, job_id: str, state: dict[str, Any], status: str = "running") -> None:
        with sqlite3.connect(self.path) as con:
            con.execute(
                "INSERT OR REPLACE INTO checkpoints(job_id, ts, state_json, status) VALUES(?,?,?,?)",
                (job_id, time.time(), json.dumps(state), status),
            )

    def load(self, job_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.path) as con:
            row = con.execute(
                "SELECT state_json, status, ts FROM checkpoints WHERE job_id=?", (job_id,)
            ).fetchone()
        if not row:
            return None
        return {"state": json.loads(row[0]), "status": row[1], "ts": row[2]}
