from __future__ import annotations

import re
from typing import Any, ClassVar

import httpx

from sovereign_ai.kernel.registry import CapabilityRegistry
from sovereign_ai.kernel.types import CapabilityRequest, RouteCandidate
from sovereign_ai.resources.arbiter import GPUArbiter
from sovereign_ai.resources.residency import ResidencyCoordinator
from sovereign_ai.resources.scheduler import ResourceScheduler


class WanGPBackend:
    def __init__(self, base_url: str, health_url: str | None = None, timeout: float = 7200.0):
        self.base_url = base_url.rstrip("/")
        self.health_url = health_url or f"{self.base_url}/health"
        self.timeout = timeout

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(self.health_url)
                return r.status_code < 500
        except Exception:
            return False

    async def models(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.get(f"{self.base_url}/models", params={"include_availability": "true"})
            r.raise_for_status()
            return r.json().get("models", [])

    async def generate(
        self, settings: dict[str, Any], timeout_s: float | None = None
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}/generate", json={"settings": settings, "timeout_s": timeout_s}
            )
            r.raise_for_status()
            return r.json()


class MediaBroker:
    """Kernel-owned media routing above WanGP.

    WanGP owns model-specific generation mechanics. The kernel owns capability selection,
    model identity, licensing context, GPU exclusivity and fallback behavior.
    """

    STOP: ClassVar[set[str]] = {
        "model",
        "generation",
        "via",
        "official",
        "distilled",
        "nvfp4",
        "fp8",
        "xl",
        "sft",
        "large",
        "small",
        "the",
        "and",
        "image",
        "video",
        "audio",
    }

    def __init__(
        self,
        registry: CapabilityRegistry,
        scheduler: ResourceScheduler,
        gpu: GPUArbiter,
        residency: ResidencyCoordinator,
    ):
        self.registry = registry
        self.scheduler = scheduler
        self.gpu = gpu
        self.residency = residency
        self.backends: dict[str, WanGPBackend] = {}
        for engine_id, spec in registry.engines.items():
            if spec.kind == "media_worker" and spec.base_url:
                self.backends[engine_id] = WanGPBackend(spec.base_url, spec.health_url)

    @classmethod
    def _tokens(cls, text: str) -> set[str]:
        toks = {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1}
        return toks - cls.STOP

    async def _resolve_model_type(
        self, candidate: RouteCandidate, explicit: str | None = None
    ) -> tuple[str, list[str]]:
        if explicit:
            return explicit, ["caller supplied WanGP model_type"]
        engine = self.registry.engines[candidate.engine_id]
        alias = engine.model_aliases.get(candidate.model_id)
        if isinstance(alias, str):
            return alias, ["pinned engine alias"]
        backend = self.backends[candidate.engine_id]
        model = self.registry.models[candidate.model_id]
        target = self._tokens(" ".join([candidate.model_id, model.name, model.source or ""]))
        choices = await backend.models()
        ranked: list[tuple[float, str, str]] = []
        for item in choices:
            model_type = str(item.get("model_type") or "")
            name = str(item.get("name") or item.get("family_label") or "")
            meta = item.get("metadata") or {}
            hay = self._tokens(
                " ".join(
                    [
                        model_type,
                        name,
                        str(meta.get("family") or ""),
                        str(meta.get("family_label") or ""),
                    ]
                )
            )
            if not target or not hay:
                continue
            overlap = len(target & hay)
            union = len(target | hay)
            score = overlap / max(1, union)
            if overlap:
                ranked.append((score, model_type, name))
        ranked.sort(reverse=True)
        if not ranked:
            raise RuntimeError(
                f"WanGP cannot resolve model_type for {candidate.model_id}; no matching discovered model"
            )
        best = ranked[0]
        if best[0] < 0.15:
            raise RuntimeError(f"WanGP model match too weak for {candidate.model_id}: {best}")
        if len(ranked) > 1 and abs(best[0] - ranked[1][0]) < 0.02 and best[1] != ranked[1][1]:
            raise RuntimeError(
                f"WanGP model match ambiguous for {candidate.model_id}: {ranked[:3]}"
            )
        return best[1], [f"dynamic WanGP discovery match={best[2]!r} score={best[0]:.3f}"]

    async def generate(
        self,
        request: CapabilityRequest,
        settings: dict[str, Any],
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        decision = self.scheduler.route(request)
        failures: list[str] = []
        for candidate in decision.candidates:
            backend = self.backends.get(candidate.engine_id)
            if backend is None:
                failures.append(f"{candidate.engine_id}:{candidate.model_id}: no media backend")
                continue
            if not await backend.health():
                failures.append(f"{candidate.engine_id}:{candidate.model_id}: backend unhealthy")
                continue
            try:
                runtime_type, resolve_notes = await self._resolve_model_type(
                    candidate, settings.get("model_type")
                )
                payload = dict(settings)
                payload["model_type"] = runtime_type
                model = self.registry.models[candidate.model_id]
                async with self.gpu.lease(
                    owner=f"{candidate.engine_id}:{runtime_type}", exclusive=model.exclusive_gpu
                ):
                    evicted = await self.residency.release_llama()
                    result = await backend.generate(payload, timeout_s=timeout_s)
                if evicted:
                    resolve_notes.append(
                        "evicted llama.cpp models before media job: " + ", ".join(evicted)
                    )
                actual = decision.model_copy(update={"selected": candidate})
                return {
                    "route": actual.model_dump(),
                    "runtime_model_type": runtime_type,
                    "resolution_notes": resolve_notes,
                    "result": result,
                    "fallbacks": failures,
                }
            except Exception as exc:
                failures.append(
                    f"{candidate.engine_id}:{candidate.model_id}: {type(exc).__name__}: {exc}"
                )
        raise RuntimeError("All media routes failed: " + " | ".join(failures or decision.warnings))
