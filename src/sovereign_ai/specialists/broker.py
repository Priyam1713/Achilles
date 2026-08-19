from __future__ import annotations

from typing import Any

import httpx

from sovereign_ai.kernel.registry import CapabilityRegistry
from sovereign_ai.kernel.types import CapabilityRequest
from sovereign_ai.resources.arbiter import GPUArbiter
from sovereign_ai.resources.residency import ResidencyCoordinator
from sovereign_ai.resources.scheduler import ResourceScheduler

from .supervisor import SpecialistSupervisor


class SpecialistBroker:
    def __init__(
        self,
        registry: CapabilityRegistry,
        scheduler: ResourceScheduler,
        gpu: GPUArbiter,
        residency: ResidencyCoordinator,
        supervisor: SpecialistSupervisor,
    ):
        self.registry = registry
        self.scheduler = scheduler
        self.gpu = gpu
        self.residency = residency
        self.supervisor = supervisor

    async def invoke(
        self,
        request: CapabilityRequest,
        operation: str,
        inputs: dict[str, Any],
        options: dict[str, Any] | None = None,
        timeout_s: float = 300.0,
    ) -> dict[str, Any]:
        decision = self.scheduler.route(request)
        failures = []
        for cand in decision.candidates:
            if cand.engine_id != "hf_worker":
                continue
            worker = self.supervisor.worker_for(cand.model_id)
            if not worker:
                failures.append(f"{cand.model_id}: no specialist worker mapping")
                continue
            model = self.registry.models[cand.model_id]
            try:
                async with self.gpu.lease(
                    f"specialist:{cand.model_id}", exclusive=model.exclusive_gpu
                ):
                    if model.estimated_vram_mb >= 2500:
                        await self.residency.release_llama()
                    url = await self.supervisor.ensure(worker)
                    async with httpx.AsyncClient(timeout=timeout_s) as client:
                        r = await client.post(
                            url + "/invoke",
                            json={
                                "model_id": cand.model_id,
                                "operation": operation,
                                "inputs": inputs,
                                "options": options or {},
                            },
                        )
                        r.raise_for_status()
                        result = r.json()
                return {
                    "route": decision.model_copy(update={"selected": cand}).model_dump(),
                    "worker": worker,
                    "result": result.get("result"),
                    "fallbacks": failures,
                }
            except Exception as exc:
                failures.append(f"{cand.model_id}/{worker}: {type(exc).__name__}: {exc}")
                await self.supervisor.unload(worker)
        raise RuntimeError(
            "All specialist routes failed: " + " | ".join(failures or decision.warnings)
        )
