from __future__ import annotations

import json
import sqlite3
import struct
from collections.abc import Iterable
from pathlib import Path

import numpy as np


class LocalVectorStore:
    """Persistent cosine index: exact search, vectorized with numpy.

    Scores every stored vector against the query with one batched matrix-vector
    product instead of a per-row Python loop, and only builds a result dict (with
    its JSON metadata decode) for the winning `limit` rows rather than all of them.
    Measured, not assumed: at 20k stored 4096-dim vectors (the size Octen-Embedding-8B
    emits) a full search is well under a second end to end, including SQLite I/O --
    see FIXES.md F-008 for the actual numbers, including the honest ceiling on how
    much the numpy rewrite alone buys (roughly 4-5x; most of the remaining cost is
    SQLite blob I/O and Python object construction, not the arithmetic). It is still
    an exact O(n) scan, not a sub-linear ANN index: for the personal/community-scale
    memory stores this project targets (thousands to low hundreds of thousands of
    memories) that is the right tradeoff, and correctness of ranking never degrades
    the way approximate methods can. Swap for FAISS/LanceDB/sqlite-vec behind this
    same interface without changing ContextBuilder if a deployment ever needs
    sub-linear search at millions of vectors.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _con(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def _init(self):
        with self._con() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS vectors (id TEXT PRIMARY KEY, dim INTEGER NOT NULL, vec BLOB NOT NULL, content TEXT, source TEXT, trust TEXT, confidence REAL, metadata_json TEXT)"
            )
            # FIXES.md Tier 5: mirrors memory/store.py's `project` scope tag, so vector
            # search can be filtered by AgentProfile.memory_scopes the same way lexical
            # search already is. `_init()` runs on every construction (this store predates
            # MigrationRunner), so the column add must be idempotent -- check first.
            existing_columns = {row["name"] for row in c.execute("PRAGMA table_info(vectors)").fetchall()}
            if "project" not in existing_columns:
                c.execute("ALTER TABLE vectors ADD COLUMN project TEXT")

    @staticmethod
    def _pack(v: Iterable[float]) -> tuple[int, bytes]:
        vals = [float(x) for x in v]
        return len(vals), struct.pack(f"<{len(vals)}f", *vals)

    def put(
        self,
        id: str,
        vector: Iterable[float],
        content: str = "",
        source: str | None = None,
        trust: str = "trusted_local",
        confidence: float = 1.0,
        metadata: dict | None = None,
        project: str | None = None,
    ):
        dim, blob = self._pack(vector)
        with self._con() as c:
            c.execute(
                """INSERT OR REPLACE INTO vectors
                   (id,dim,vec,content,source,trust,confidence,metadata_json,project)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (id, dim, blob, content, source, trust, confidence, json.dumps(metadata or {}), project),
            )

    def delete(self, id: str) -> None:
        with self._con() as c:
            c.execute("DELETE FROM vectors WHERE id=?", (id,))

    def has_vectors(self, allowed_projects: list[str] | None = None) -> bool:
        """Return whether a scoped search has anything to query.

        This cheap preflight lets callers avoid loading an embedding worker when the local
        index is empty. It deliberately mirrors ``search_vector`` scope semantics so a
        profile cannot infer that vectors exist outside its allowed projects.
        """
        sql = "SELECT 1 FROM vectors"
        params: list[str] = []
        if allowed_projects is not None:
            if allowed_projects:
                placeholders = ",".join("?" for _ in allowed_projects)
                sql += f" WHERE (project IS NULL OR project IN ({placeholders}))"
                params.extend(allowed_projects)
            else:
                sql += " WHERE project IS NULL"
        sql += " LIMIT 1"
        with self._con() as c:
            return c.execute(sql, params).fetchone() is not None

    def search_vector(
        self, query: Iterable[float], limit: int = 20, allowed_projects: list[str] | None = None
    ):
        """`allowed_projects` mirrors `MemoryStore.search_lexical`'s parameter of the same
        name (FIXES.md Tier 5): `None` applies no filter (existing behavior, unchanged);
        an empty list means unscoped vectors only; a non-empty list means unscoped plus
        those specific projects."""
        q = np.asarray([float(x) for x in query], dtype=np.float32)
        sql = "SELECT * FROM vectors WHERE dim=?"
        params = [len(q)]
        if allowed_projects is not None:
            if allowed_projects:
                placeholders = ",".join("?" for _ in allowed_projects)
                sql += f" AND (project IS NULL OR project IN ({placeholders}))"
                params.extend(allowed_projects)
            else:
                sql += " AND project IS NULL"
        with self._con() as c:
            rows = c.execute(sql, params).fetchall()
        if not rows:
            return []

        matrix = np.frombuffer(b"".join(r["vec"] for r in rows), dtype=np.float32).reshape(
            len(rows), len(q)
        )
        q_norm = np.linalg.norm(q) or 1.0
        row_norms = np.linalg.norm(matrix, axis=1)
        row_norms[row_norms == 0] = 1.0
        scores = (matrix @ q) / (row_norms * q_norm)

        # Only the winning `limit` rows need their JSON metadata decoded and a dict
        # built -- doing that for every row (as an earlier version of this method did)
        # wasted most of the work on rows that get thrown away by the final sort.
        k = min(limit, len(rows))
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top])]

        return [
            {
                "id": rows[i]["id"],
                "content": rows[i]["content"],
                "source": rows[i]["source"],
                "trust": rows[i]["trust"],
                "confidence": rows[i]["confidence"],
                "score": float(scores[i]),
                "metadata": json.loads(rows[i]["metadata_json"] or "{}"),
            }
            for i in top
        ]
