from __future__ import annotations

from dataclasses import dataclass

from sovereign_ai.kernel.benchmarks import BenchmarkStore
from sovereign_ai.kernel.config import ConfigBundle
from sovereign_ai.kernel.registry import CapabilityRegistry
from sovereign_ai.kernel.types import CapabilityRequest, ModelStatus, RouteCandidate, RouteDecision
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

    def route(self, req: CapabilityRequest) -> RouteDecision:
        resources = snapshot(self.config.state_dir)
        weights = self._weights(req.mode.value)
        candidates: list[RouteCandidate] = []
        warnings: list[str] = []

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
                if not engine or not engine.enabled:
                    continue
                bench = self.benchmarks.aggregate(model.id, engine_id, req.capability)
                if bench:
                    quality = bench["quality"]
                    reliability = bench["reliability"]
                    latency_score = self._latency_score(bench["latency_ms"])
                    reasons = [f"local benchmark n={bench['samples']}"]
                else:
                    quality = model.quality_prior
                    reliability = 0.72 if model.status == ModelStatus.CANDIDATE else 0.88
                    latency_score = 0.45
                    reasons = ["manifest prior; no local benchmark yet"]

                # Hardware-fit is a planning prior, never a substitute for local benchmarks.
                usable_total = (
                    max(1, resources.vram_total_mb - self.reserve_vram_mb)
                    if resources.vram_total_mb
                    else 11000
                )
                if not model.estimated_vram_mb:
                    resource_fit = 0.7
                elif model.estimated_vram_mb <= usable_total:
                    resource_fit = 1.0
                elif model.can_cpu_offload:
                    resource_fit = 0.55
                    reasons.append("requires CPU/RAM offload on target VRAM")
                else:
                    resource_fit = 0.15
                    reasons.append(
                        "estimated VRAM exceeds target; route only if benchmark proves viable"
                    )

                # Resident loop models get a small preference on low-latency modes.
                resident_bonus = (
                    min(model.resident_priority / 1000.0, 0.10) if req.mode.value != "deep" else 0.0
                )
                resource_adjustment = (resource_fit - 0.5) * (
                    0.10 if req.mode.value != "deep" else 0.04
                )
                score = (
                    weights.quality * quality
                    + weights.latency * latency_score
                    + weights.reliability * reliability
                    + resident_bonus
                    + resource_adjustment
                )
                candidates.append(
                    RouteCandidate(
                        model_id=model.id,
                        engine_id=engine_id,
                        score=round(score, 6),
                        quality=quality,
                        latency_score=latency_score,
                        reliability=reliability,
                        reasons=reasons,
                    )
                )

        candidates.sort(key=lambda c: c.score, reverse=True)
        limit = int(self.config.system["routing"].get("max_candidates", 8))
        candidates = candidates[:limit]
        selected = candidates[0] if candidates else None
        if not selected:
            warnings.append(f"No routable model for capability={req.capability}")
        return RouteDecision(
            request=req,
            selected=selected,
            candidates=candidates,
            resource_snapshot=resources,
            warnings=warnings,
        )
