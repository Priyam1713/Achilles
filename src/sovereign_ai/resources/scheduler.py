from __future__ import annotations

from dataclasses import dataclass

from sovereign_ai.kernel.benchmarks import BenchmarkStore
from sovereign_ai.kernel.config import ConfigBundle
from sovereign_ai.kernel.registry import CapabilityRegistry
from sovereign_ai.kernel.types import (
    CapabilityRequest,
    ModelSpec,
    ModelStatus,
    ResourceSnapshot,
    RouteCandidate,
    RouteDecision,
)
from sovereign_ai.resources.telemetry import snapshot


@dataclass
class Weights:
    quality: float
    latency: float
    reliability: float


class ResourceScheduler:
    def __init__(
        self, config: ConfigBundle, registry: CapabilityRegistry, benchmarks: BenchmarkStore
    ):
        self.config = config
        self.registry = registry
        self.benchmarks = benchmarks
        # FIXES.md F-009: reserve_vram_mb has exactly one source of truth --
        # configs/system.yaml. Read it once here and fail loudly if it is ever
        # missing rather than silently falling back to a hardcoded number that
        # can drift from the value scripts/prepare_llama_models.sh derives.
        self.reserve_vram_mb = int(config.system["resources"]["reserve_vram_mb"])

    def _weights(self, mode: str) -> Weights:
        raw = self.config.system["routing"]["modes"][mode]
        return Weights(raw["quality_weight"], raw["latency_weight"], raw["reliability_weight"])

    @staticmethod
    def _latency_score(ms: float) -> float:
        # Saturating, bounded utility: 1 at ~0ms, ~0.5 around 1s, lower thereafter.
        return 1.0 / (1.0 + max(ms, 0.0) / 1000.0)

    def _eligible(
        self, req: CapabilityRequest, warnings: list[str]
    ) -> list[tuple[ModelSpec, str]]:
        """Models/engines that survive status, license and engine-availability filters.

        This is the part of routing that is always real work regardless of how many
        candidates a capability has: a candidate has to clear these gates before it is
        even eligible to be dispatched to, let alone ranked.
        """
        eligible: list[tuple[ModelSpec, str]] = []
        for model in self.registry.models_for(req.capability, include_candidates=True):
            if model.status == ModelStatus.CANDIDATE and req.mode.value != "deep":
                # Preview/experimental checkpoints are allowed only when deep mode explicitly tolerates them,
                # until benchmarks promote them.
                continue
            if req.license_context == "commercial":
                if model.commercial_allowed is False:
                    warnings.append(f"{model.id} excluded: non-commercial license")
                    continue
                if model.commercial_allowed is None:
                    warnings.append(
                        f"{model.id} excluded: commercial license status not explicitly verified"
                    )
                    continue
            for engine_id in model.preferred_engines:
                engine = self.registry.engines.get(engine_id)
                if engine and engine.enabled:
                    eligible.append((model, engine_id))
        return eligible

    def _quality_reliability_latency(
        self, model: ModelSpec, engine_id: str, req: CapabilityRequest
    ) -> tuple[float, float, float, list[str]]:
        bench = self.benchmarks.aggregate(model.id, engine_id, req.capability)
        if bench:
            return (
                bench["quality"],
                bench["reliability"],
                self._latency_score(bench["latency_ms"]),
                [f"local benchmark n={bench['samples']}"],
            )
        reliability = 0.72 if model.status == ModelStatus.CANDIDATE else 0.88
        return model.quality_prior, reliability, 0.45, ["manifest prior; no local benchmark yet"]

    def _resource_fit(self, model: ModelSpec, resources: ResourceSnapshot) -> tuple[float, list[str]]:
        # Hardware-fit is a planning prior, never a substitute for local benchmarks.
        usable_total = (
            max(1, resources.vram_total_mb - self.reserve_vram_mb)
            if resources.vram_total_mb
            else 11000
        )
        if not model.estimated_vram_mb:
            return 0.7, []
        if model.estimated_vram_mb <= usable_total:
            return 1.0, []
        if model.can_cpu_offload:
            return 0.55, ["requires CPU/RAM offload on target VRAM"]
        return 0.15, ["estimated VRAM exceeds target; route only if benchmark proves viable"]

    def _dispatch(
        self, model: ModelSpec, engine_id: str, req: CapabilityRequest, resources: ResourceSnapshot
    ) -> RouteCandidate:
        """No ranking to do: exactly one eligible model/engine survived filtering.

        FIXES.md F-006: 84 of 89 capabilities in the current manifest have exactly one
        eligible candidate once status/license/engine filters are applied -- weighing that
        one candidate against weights, resident-priority bonuses and a resource-fit
        adjustment cannot change the outcome, only cost cycles and reading effort. This is
        dispatch (capability -> the one model that can serve it), not a routing decision;
        `_score` below is reserved for the genuine multi-candidate case.
        """
        quality, reliability, latency_score, reasons = self._quality_reliability_latency(
            model, engine_id, req
        )
        _, fit_reasons = self._resource_fit(model, resources)
        return RouteCandidate(
            model_id=model.id,
            engine_id=engine_id,
            score=round(quality, 6),
            quality=quality,
            latency_score=latency_score,
            reliability=reliability,
            reasons=[*reasons, *fit_reasons, "only eligible candidate for this capability"],
        )

    def _score(
        self,
        model: ModelSpec,
        engine_id: str,
        req: CapabilityRequest,
        resources: ResourceSnapshot,
        weights: Weights,
    ) -> RouteCandidate:
        """Genuine A/B ranking between two or more eligible candidates for one capability.

        Only reached when `_eligible` returns more than one (model, engine) pair -- a real
        minority of capabilities today (FIXES.md F-006). This is where the full weighted
        scoring this module exists for actually earns its keep.
        """
        quality, reliability, latency_score, reasons = self._quality_reliability_latency(
            model, engine_id, req
        )
        resource_fit, fit_reasons = self._resource_fit(model, resources)
        reasons = [*reasons, *fit_reasons]

        # Resident loop models get a small preference on low-latency modes.
        resident_bonus = (
            min(model.resident_priority / 1000.0, 0.10) if req.mode.value != "deep" else 0.0
        )
        resource_adjustment = (resource_fit - 0.5) * (0.10 if req.mode.value != "deep" else 0.04)
        score = (
            weights.quality * quality
            + weights.latency * latency_score
            + weights.reliability * reliability
            + resident_bonus
            + resource_adjustment
        )
        return RouteCandidate(
            model_id=model.id,
            engine_id=engine_id,
            score=round(score, 6),
            quality=quality,
            latency_score=latency_score,
            reliability=reliability,
            reasons=reasons,
        )

    def route(self, req: CapabilityRequest) -> RouteDecision:
        resources = snapshot(self.config.state_dir)
        warnings: list[str] = []
        eligible = self._eligible(req, warnings)

        if not eligible:
            warnings.append(f"No routable model for capability={req.capability}")
            return RouteDecision(
                request=req, selected=None, candidates=[], resource_snapshot=resources, warnings=warnings
            )

        if len(eligible) == 1:
            model, engine_id = eligible[0]
            candidates = [self._dispatch(model, engine_id, req, resources)]
        else:
            weights = self._weights(req.mode.value)
            candidates = [
                self._score(model, engine_id, req, resources, weights) for model, engine_id in eligible
            ]
            candidates.sort(key=lambda c: c.score, reverse=True)
            limit = int(self.config.system["routing"].get("max_candidates", 8))
            candidates = candidates[:limit]

        return RouteDecision(
            request=req,
            selected=candidates[0],
            candidates=candidates,
            resource_snapshot=resources,
            warnings=warnings,
        )
