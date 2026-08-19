from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from statistics import fmean


class BenchmarkStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS benchmark_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    model_id TEXT NOT NULL,
                    engine_id TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    quality REAL NOT NULL,
                    latency_ms REAL NOT NULL,
                    reliability REAL NOT NULL,
                    vram_peak_mb REAL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_bench_lookup ON benchmark_runs(model_id, engine_id, capability)"
            )

    def record(
        self,
        model_id: str,
        engine_id: str,
        capability: str,
        quality: float,
        latency_ms: float,
        reliability: float,
        vram_peak_mb: float | None = None,
        metadata: dict | None = None,
    ) -> None:
        with sqlite3.connect(self.path) as con:
            con.execute(
                "INSERT INTO benchmark_runs(ts, model_id, engine_id, capability, quality, latency_ms, reliability, vram_peak_mb, metadata_json) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    time.time(),
                    model_id,
                    engine_id,
                    capability,
                    quality,
                    latency_ms,
                    reliability,
                    vram_peak_mb,
                    json.dumps(metadata or {}),
                ),
            )

    def aggregate(
        self, model_id: str, engine_id: str, capability: str, limit: int = 20
    ) -> dict | None:
        with sqlite3.connect(self.path) as con:
            rows = con.execute(
                "SELECT quality, latency_ms, reliability, vram_peak_mb FROM benchmark_runs WHERE model_id=? AND engine_id=? AND capability=? ORDER BY id DESC LIMIT ?",
                (model_id, engine_id, capability, limit),
            ).fetchall()
        if not rows:
            return None
        qualities = [r[0] for r in rows]
        latencies = [r[1] for r in rows]
        reliabilities = [r[2] for r in rows]
        peaks = [r[3] for r in rows if r[3] is not None]
        return {
            "quality": fmean(qualities),
            "latency_ms": fmean(latencies),
            "reliability": fmean(reliabilities),
            "vram_peak_mb": fmean(peaks) if peaks else None,
            "samples": len(rows),
        }
