from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any


class EventStore:
    """Append-only event log. State is derived from events/checkpoints; events are never updated."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        return con

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE NOT NULL,
                    stream_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    ts REAL NOT NULL,
                    payload_json TEXT NOT NULL,
                    trust TEXT NOT NULL,
                    parent_event_id TEXT
                )
                """
            )
            con.execute("CREATE INDEX IF NOT EXISTS idx_events_stream ON events(stream_id, seq)")

    def append(
        self,
        stream_id: str,
        event_type: str,
        payload: dict[str, Any],
        trust: str = "trusted_local",
        parent_event_id: str | None = None,
    ) -> str:
        event_id = str(uuid.uuid4())
        with self._lock, self._connect() as con:
            con.execute(
                "INSERT INTO events(event_id, stream_id, event_type, ts, payload_json, trust, parent_event_id) VALUES(?,?,?,?,?,?,?)",
                (
                    event_id,
                    stream_id,
                    event_type,
                    time.time(),
                    json.dumps(payload),
                    trust,
                    parent_event_id,
                ),
            )
        return event_id

    def read_stream(self, stream_id: str, after_seq: int = 0) -> Iterable[dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM events WHERE stream_id=? AND seq>? ORDER BY seq",
                (stream_id, after_seq),
            ).fetchall()
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            yield item
