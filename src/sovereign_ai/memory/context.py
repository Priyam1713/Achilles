from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .store import MemoryStore


class VectorRetriever(Protocol):
    async def search(self, query: Any, limit: int = 20) -> list[dict[str, Any]]: ...


@dataclass
class ContextItem:
    content: str
    source: str | None
    trust: str
    confidence: float
    score: float


class ContextBuilder:
    def __init__(
        self,
        memory: MemoryStore,
        text_vector: VectorRetriever | None = None,
        multimodal_vector: VectorRetriever | None = None,
    ):
        self.memory = memory
        self.text_vector = text_vector
        self.multimodal_vector = multimodal_vector

    async def retrieve_text(self, query: str, limit: int = 12) -> list[ContextItem]:
        lexical = self.memory.search_lexical(query, limit=limit)
        merged: dict[str, ContextItem] = {}
        for row in lexical:
            merged[row["id"]] = ContextItem(
                content=row["content"],
                source=row["source"],
                trust=row["trust"],
                confidence=row["confidence"],
                score=max(0.01, 1.0 / (1.0 + abs(row["rank"]))),
            )
        if self.text_vector:
            for row in await self.text_vector.search(query, limit=limit * 2):
                key = row.get("id") or row.get("content", "")[:64]
                score = float(row.get("score", 0.0))
                if key in merged:
                    merged[key].score = max(merged[key].score, score)
                else:
                    merged[key] = ContextItem(
                        row.get("content", ""),
                        row.get("source"),
                        row.get("trust", "trusted_local"),
                        float(row.get("confidence", 0.8)),
                        score,
                    )
        return sorted(merged.values(), key=lambda x: x.score * x.confidence, reverse=True)[:limit]
