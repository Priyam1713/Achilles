from __future__ import annotations

import time
from typing import Any

from sovereign_ai.kernel.registry import CapabilityRegistry
from sovereign_ai.kernel.secrets import SecretStore
from sovereign_ai.kernel.types import CapabilityRequest, EngineSpec, RouteCandidate
from sovereign_ai.resources.arbiter import GPUArbiter
from sovereign_ai.resources.scheduler import ResourceScheduler

from .base import InferenceBackend
from .openai_compat import OpenAICompatibleBackend
from .remote_backend import RemoteOpenAICompatibleBackend
from .remote_quota import RemoteQuotaLedger


class InferenceBroker:
    """Routes capabilities, not brands. Engines remain replaceable adapters.

    The scheduler ranks candidates using quality/resource evidence. The broker then
    applies *runtime truth*: dead or unimplemented engines are skipped instead of
    turning a good manifest decision into a failed request.
    """

    def __init__(
        self,
        registry: CapabilityRegistry,
        scheduler: ResourceScheduler,
        gpu: GPUArbiter,
        secrets: SecretStore | None = None,
        remote_quota: RemoteQuotaLedger | None = None,
    ):
        self.registry = registry
        self.scheduler = scheduler
        self.gpu = gpu
        self.secrets = secrets
        self.remote_quota = remote_quota
        self.backends: dict[str, InferenceBackend] = {}
        for engine_id, spec in registry.engines.items():
            if spec.kind != "openai_compatible" or not spec.base_url:
                continue
            if spec.remote:
                # A remote engine can be declared in configs/engines.yaml (the plug-and-play
                # seam) without ever being usable: no credential is written into config, so
                # the backend below fails honestly at call time rather than silently, per
                # RemoteOpenAICompatibleBackend's own health()/chat() contract.
                if not spec.api_key_secret or secrets is None:
                    continue
                self.backends[engine_id] = RemoteOpenAICompatibleBackend(
                    spec.base_url,
                    spec.api_key_secret,
                    secrets,
                    spec.health_url,
                    timeout=spec.timeout_s,
                )
            else:
                self.backends[engine_id] = OpenAICompatibleBackend(spec.base_url, spec.health_url)

    def _remote_budget_refusal(self, engine: EngineSpec) -> str | None:
        """None if `engine` may be called now; otherwise the reason it may not.

        Defense in depth alongside the scheduler's `allow_remote` gate (F-scheduler `_eligible`):
        a candidate only reaches here at all when a caller explicitly opted into remote
        routing, so this method only ever needs to enforce budget and circuit-breaker limits,
        never the local-only gate itself.
        """
        if not engine.remote or self.remote_quota is None:
            return None
        breaker_streak = self.remote_quota.consecutive_failures(engine.id)
        if breaker_streak >= engine.circuit_breaker_threshold:
            last_failure = self.remote_quota.last_failure_at(engine.id)
            if last_failure is not None and time.time() - last_failure < engine.circuit_breaker_cooldown_s:
                return (
                    f"circuit breaker open: {breaker_streak} consecutive failures, "
                    f"cooldown {engine.circuit_breaker_cooldown_s}s"
                )
        usage = self.remote_quota.usage_today(engine.id)
        if engine.max_requests_per_day is not None and usage["requests"] >= engine.max_requests_per_day:
            return f"daily request quota exhausted ({usage['requests']}/{engine.max_requests_per_day})"
        if engine.max_tokens_per_day is not None and usage["tokens"] >= engine.max_tokens_per_day:
            return f"daily token quota exhausted ({usage['tokens']}/{engine.max_tokens_per_day})"
        if engine.max_cost_usd_per_day is not None and usage["cost_usd"] >= engine.max_cost_usd_per_day:
            return f"daily cost quota exhausted (${usage['cost_usd']:.4f}/${engine.max_cost_usd_per_day})"
        return None

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

        route_reason = f"capability={request.capability} mode={request.mode.value}"

        for candidate in decision.candidates:
            engine = self.registry.engines[candidate.engine_id]
            backend = self.backends.get(candidate.engine_id)
            if backend is None:
                failures.append(
                    f"{candidate.engine_id}:{candidate.model_id}: specialist adapter required"
                )
                continue
            refusal = self._remote_budget_refusal(engine)
            if refusal is not None:
                failures.append(f"{candidate.engine_id}:{candidate.model_id}: {refusal}")
                if self.remote_quota is not None:
                    self.remote_quota.record(
                        engine.id, candidate.model_id, status="refused", route_reason=refusal
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
                if engine.remote and self.remote_quota is not None:
                    usage = result.get("usage", {}) if isinstance(result, dict) else {}
                    prompt_tokens = int(usage.get("prompt_tokens", 0))
                    completion_tokens = int(usage.get("completion_tokens", 0))
                    cost_usd = (
                        prompt_tokens / 1000.0 * engine.cost_per_1k_input_tokens
                        + completion_tokens / 1000.0 * engine.cost_per_1k_output_tokens
                    )
                    self.remote_quota.record(
                        engine.id,
                        runtime_model_id,
                        status="success",
                        route_reason=route_reason,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        cost_usd=cost_usd,
                    )
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
                if engine.remote and self.remote_quota is not None:
                    self.remote_quota.record(
                        engine.id,
                        runtime_model_id,
                        status="failure",
                        route_reason=f"{route_reason} error={type(exc).__name__}",
                    )

        raise RuntimeError(
            "All compatible inference backends failed or are not yet implemented: "
            + " | ".join(failures)
        )
