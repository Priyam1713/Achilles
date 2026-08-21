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
    ):
        dim, blob = self._pack(vector)
        with self._con() as c:
            c.execute(
                "INSERT OR REPLACE INTO vectors VALUES(?,?,?,?,?,?,?,?)",
                (id, dim, blob, content, source, trust, confidence, json.dumps(metadata or {})),
            )

    def delete(self, id: str) -> None:
        with self._con() as c:
            c.execute("DELETE FROM vectors WHERE id=?", (id,))

    def search_vector(self, query: Iterable[float], limit: int = 20):
        q = np.asarray([float(x) for x in query], dtype=np.float32)
        with self._con() as c:
            rows = c.execute("SELECT * FROM vectors WHERE dim=?", (len(q),)).fetchall()
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
