from __future__ import annotations

from typing import Any

from sovereign_ai.kernel.types import CapabilityRequest, RoutingMode
from sovereign_ai.specialists.broker import SpecialistBroker

from .vector import LocalVectorStore


class SpecialistVectorRetriever:
    """`VectorRetriever` (memory/context.py) backed by the retrieval specialist worker.

    Closes the gap `docs/IMPLEMENTATION_STATUS.md` named directly: "end-to-end embedding
    -> rerank -> context path using the downloaded retrieval models" was listed as pending
    -- `ContextBuilder` had a `text_vector` slot in its constructor, but nothing was ever
    passed into it (`kernel/app.py` built `ContextBuilder(memory)` with no vector adapter
    at all), so every context assembly was lexical-only regardless of what retrieval
    models were installed.

    Two-stage retrieval, matching `docs/ARCHITECTURE.md`'s "first-stage index, then
    reranked before context assembly": embed the query, take the nearest neighbours from
    the local vector index, then rerank that candidate set with a cross-encoder for
    precision cosine similarity alone does not give. The embedding and reranking calls
    both go through the *existing* `SpecialistBroker` -- GPU leasing, worker launch and
    capability routing are unchanged, not reimplemented for this one path.
    """

    def __init__(
        self,
        specialists: SpecialistBroker,
        vector_store: LocalVectorStore,
        *,
        embed_capability: str = "text_embedding",
        rerank_capability: str = "text_reranking",
        first_stage_multiplier: int = 4,
    ):
        self.specialists = specialists
        self.vector_store = vector_store
        self.embed_capability = embed_capability
        self.rerank_capability = rerank_capability
        self.first_stage_multiplier = first_stage_multiplier

    async def embed(self, texts: list[str]) -> list[list[float]]:
        result = await self.specialists.invoke(
            CapabilityRequest(capability=self.embed_capability, mode=RoutingMode.FAST),
            operation="embed",
            inputs={"texts": texts},
        )
        vectors = result["result"]
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise RuntimeError(
                f"embedding worker returned {len(vectors) if isinstance(vectors, list) else type(vectors)} "
                f"vectors for {len(texts)} inputs"
            )
        return vectors

    async def search(
        self, query: str, limit: int = 20, allowed_projects: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """`allowed_projects` mirrors `MemoryStore.search_lexical`'s parameter of the same
        name (FIXES.md Tier 5) -- applied at the first (vector) stage, before reranking,
        so a scoped-out memory never even reaches the reranker."""
        (query_vector,) = await self.embed([query])
        first_stage = self.vector_store.search_vector(
            query_vector, limit=limit * self.first_stage_multiplier, allowed_projects=allowed_projects
        )
        if not first_stage:
            return []

        rerank_result = await self.specialists.invoke(
            CapabilityRequest(capability=self.rerank_capability, mode=RoutingMode.FAST),
            operation="rerank",
            inputs={"query": query, "candidates": [c["content"] for c in first_stage]},
        )
        ranked = rerank_result["result"]
        output: list[dict[str, Any]] = []
        for entry in ranked[:limit]:
            base = dict(first_stage[entry["index"]])
            base["score"] = float(entry["score"])
            output.append(base)
        return output


class MemoryIndexer:
    """Embeds memory content into the vector store alongside the (synchronous) lexical write.

    Kept separate from `MemoryStore.put()` deliberately: that store has no external
    dependencies and stays synchronous so a memory can always be written even if the
    retrieval worker is not running. Semantic indexing is additive -- call `index()` after
    `memory.put()` for anything worth finding by meaning, not just by keyword.
    """

    def __init__(
        self,
        specialists: SpecialistBroker,
        vector_store: LocalVectorStore,
        *,
        embed_capability: str = "text_embedding",
    ):
        self.specialists = specialists
        self.vector_store = vector_store
        self.embed_capability = embed_capability

    async def index(
        self,
        memory_id: str,
        content: str,
        *,
        source: str | None = None,
        trust: str = "trusted_local",
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
        supersedes: str | None = None,
        project: str | None = None,
    ) -> None:
        result = await self.specialists.invoke(
            CapabilityRequest(capability=self.embed_capability, mode=RoutingMode.FAST),
            operation="embed",
            inputs={"texts": [content]},
        )
        (vector,) = result["result"]
        self.vector_store.put(
            memory_id, vector, content=content, source=source, trust=trust,
            confidence=confidence, metadata=metadata, project=project,
        )
        if supersedes is not None:
            # Mirrors MemoryStore.put()'s FTS cleanup: a superseded memory must stop
            # being retrievable by meaning too, not just by keyword (FIXES.md F-008).
            self.vector_store.delete(supersedes)
