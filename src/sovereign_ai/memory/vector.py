from __future__ import annotations

import json
import math
import sqlite3
import struct
from collections.abc import Iterable
from pathlib import Path


class LocalVectorStore:
    """Dependency-light persistent cosine index. Swap for FAISS/LanceDB without changing ContextBuilder."""

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

    @staticmethod
    def _unpack(dim: int, b: bytes):
        return struct.unpack(f"<{dim}f", b)

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

    def search_vector(self, query: Iterable[float], limit: int = 20):
        q = [float(x) for x in query]
        qn = math.sqrt(sum(x * x for x in q)) or 1.0
        out = []
        with self._con() as c:
            rows = c.execute("SELECT * FROM vectors").fetchall()
        for r in rows:
            if r["dim"] != len(q):
                continue
            v = self._unpack(r["dim"], r["vec"])
            vn = math.sqrt(sum(x * x for x in v)) or 1.0
            score = sum(a * b for a, b in zip(q, v, strict=True)) / (qn * vn)
            out.append(
                {
                    "id": r["id"],
                    "content": r["content"],
                    "source": r["source"],
                    "trust": r["trust"],
                    "confidence": r["confidence"],
                    "score": score,
                    "metadata": json.loads(r["metadata_json"] or "{}"),
                }
            )
        return sorted(out, key=lambda x: x["score"], reverse=True)[:limit]
