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
            if supersedes is not None:
                # Keep the old memory row for provenance/audit, but pull it out of the
                # lexical index so a search never surfaces both the stale and current
                # version (FIXES.md F-008).
                con.execute("DELETE FROM memories_fts WHERE id=?", (supersedes,))
        return memory_id

    def retire(self, memory_id: str) -> None:
        """Remove a memory from the lexical index without deleting its audit row."""
        with self._connect() as con:
            con.execute("DELETE FROM memories_fts WHERE id=?", (memory_id,))

    def search_lexical(
        self, query: str, limit: int = 12, allowed_projects: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """`allowed_projects=None` (the default) applies no scope filter -- every existing
        caller keeps its current, unrestricted behavior. Pass a list (empty or not) to
        enforce `AgentProfile.memory_scopes` (FIXES.md Tier 5): a memory with no `project`
        set is always visible (it was never scoped to begin with), and a memory whose
        `project` is in the list is visible; anything else is filtered out before it ever
        reaches a caller. An empty list therefore means "unscoped memories only" -- the
        fail-closed reading for a profile with zero granted scopes, not "no filter"."""
        sql = """
            SELECT m.*, bm25(memories_fts) AS rank
            FROM memories_fts f JOIN memories m ON f.id=m.id
            WHERE memories_fts MATCH ?
            AND (m.expires_at IS NULL OR m.expires_at > ?)
        """
        params: list[Any] = [query, time.time()]
        if allowed_projects is not None:
            if allowed_projects:
                placeholders = ",".join("?" for _ in allowed_projects)
                sql += f" AND (m.project IS NULL OR m.project IN ({placeholders}))"
                params.extend(allowed_projects)
            else:
                # No scopes granted: only unscoped memories are visible, not everything.
                sql += " AND m.project IS NULL"
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)
        with self._connect() as con:
            rows = con.execute(sql, params).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json"))
            out.append(item)
        return out
