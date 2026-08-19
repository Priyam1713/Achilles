from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


class MemoryStore:
    """Local provenance-aware memory. FTS is built-in; vector/multimodal indexes attach separately."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT,
                    trust TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL,
                    project TEXT,
                    sensitivity TEXT,
                    supersedes TEXT,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            con.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(id UNINDEXED, content, source, project)"
            )

    def put(
        self,
        kind: str,
        content: str,
        source: str | None = None,
        trust: str = "trusted_local",
        confidence: float = 1.0,
        project: str | None = None,
        sensitivity: str | None = None,
        expires_at: float | None = None,
        supersedes: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        memory_id = str(uuid.uuid4())
        with self._connect() as con:
            con.execute(
                "INSERT INTO memories VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    memory_id,
                    kind,
                    content,
                    source,
                    trust,
                    confidence,
                    time.time(),
                    expires_at,
                    project,
                    sensitivity,
                    supersedes,
                    json.dumps(metadata or {}),
                ),
            )
            con.execute(
                "INSERT INTO memories_fts(id, content, source, project) VALUES(?,?,?,?)",
                (memory_id, content, source or "", project or ""),
            )
        return memory_id

    def search_lexical(self, query: str, limit: int = 12) -> list[dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT m.*, bm25(memories_fts) AS rank
                FROM memories_fts f JOIN memories m ON f.id=m.id
                WHERE memories_fts MATCH ?
                AND (m.expires_at IS NULL OR m.expires_at > ?)
                ORDER BY rank LIMIT ?
                """,
                (query, time.time(), limit),
            ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json"))
            out.append(item)
        return out
