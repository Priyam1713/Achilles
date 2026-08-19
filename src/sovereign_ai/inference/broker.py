from __future__ import annotations

from typing import Any

from sovereign_ai.kernel.registry import CapabilityRegistry
from sovereign_ai.kernel.types import CapabilityRequest, RouteCandidate
from sovereign_ai.resources.arbiter import GPUArbiter
from sovereign_ai.resources.scheduler import ResourceScheduler

from .openai_compat import OpenAICompatibleBackend


class InferenceBroker:
    """Routes capabilities, not brands. Engines remain replaceable adapters.

    The scheduler ranks candidates using quality/resource evidence. The broker then
    applies *runtime truth*: dead or unimplemented engines are skipped instead of
    turning a good manifest decision into a failed request.
    """

    def __init__(self, registry: CapabilityRegistry, scheduler: ResourceScheduler, gpu: GPUArbiter):
        self.registry = registry
        self.scheduler = scheduler
        self.gpu = gpu
        self.backends: dict[str, OpenAICompatibleBackend] = {}
        for engine_id, spec in registry.engines.items():
            if spec.kind == "openai_compatible" and spec.base_url:
                self.backends[engine_id] = OpenAICompatibleBackend(spec.base_url, spec.health_url)

    def _runtime_model_id(self, candidate: RouteCandidate, request: CapabilityRequest) -> str:
        engine = self.registry.engines[candidate.engine_id]
        runtime_model_id = candidate.model_id
        alias = engine.model_aliases.get(candidate.model_id)
        if isinstance(alias, dict):
            runtime_model_id = alias.get(request.mode.value, alias.get("smart", candidate.model_id))
        elif isinstance(alias, str):
            runtime_model_id = alias
        return runtime_model_id

    async def chat(
        self,
        request: CapabilityRequest,
        messages: list[dict[str, Any]],
        model_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        decision = self.scheduler.route(request)
        if not decision.candidates:
            raise RuntimeError(f"No inference route for {request.capability}: {decision.warnings}")

        payload = dict(model_overrides or {})
        failures: list[str] = []

        for candidate in decision.candidates:
            backend = self.backends.get(candidate.engine_id)
            if backend is None:
                failures.append(
                    f"{candidate.engine_id}:{candidate.model_id}: specialist adapter required"
                )
                continue
            if not await backend.health():
                failures.append(f"{candidate.engine_id}:{candidate.model_id}: backend unhealthy")
                continue

            runtime_model_id = self._runtime_model_id(candidate, request)
            model = self.registry.models[candidate.model_id]
            try:
                # All GPU-heavy model traffic is serialized at the kernel boundary.
                # This avoids cross-model residency races when a router has to evict
                # one model to make room for another on a single consumer GPU.
                async with self.gpu.lease(
                    owner=f"{candidate.engine_id}:{runtime_model_id}",
                    exclusive=model.exclusive_gpu,
                ):
                    result = await backend.chat(runtime_model_id, messages, **payload)
                actual_decision = decision.model_copy(update={"selected": candidate})
                return {
                    "route": actual_decision.model_dump(),
                    "runtime_model_id": runtime_model_id,
                    "result": result,
                    "fallbacks": failures,
                }
            except Exception as exc:
                failures.append(
                    f"{candidate.engine_id}:{runtime_model_id}: {type(exc).__name__}: {exc}"
                )

        raise RuntimeError(
            "All compatible inference backends failed or are not yet implemented: "
            + " | ".join(failures)
        )
