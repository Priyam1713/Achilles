from __future__ import annotations

import sqlite3
from pathlib import Path


class MemoryGraph:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS edges (src TEXT, rel TEXT, dst TEXT, weight REAL DEFAULT 1, provenance TEXT, PRIMARY KEY(src,rel,dst))"
            )
            c.execute("CREATE INDEX IF NOT EXISTS edge_src ON edges(src)")
            c.execute("CREATE INDEX IF NOT EXISTS edge_dst ON edges(dst)")

    def link(
        self, src: str, rel: str, dst: str, weight: float = 1.0, provenance: str | None = None
    ):
        with sqlite3.connect(self.path) as c:
            c.execute(
                "INSERT OR REPLACE INTO edges VALUES(?,?,?,?,?)",
                (src, rel, dst, weight, provenance),
            )

    def neighbors(self, node: str, limit: int = 50):
        with sqlite3.connect(self.path) as c:
            c.row_factory = sqlite3.Row
            rows = c.execute(
                "SELECT * FROM edges WHERE src=? OR dst=? ORDER BY weight DESC LIMIT ?",
                (node, node, limit),
            ).fetchall()
        return [dict(r) for r in rows]
