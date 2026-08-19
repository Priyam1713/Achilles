from __future__ import annotations

from typing import Any

import httpx

from .base import InferenceBackend


class OpenAICompatibleBackend(InferenceBackend):
    def __init__(self, base_url: str, health_url: str | None = None, timeout: float = 600.0):
        self.base_url = base_url.rstrip("/")
        self.health_url = health_url
        self.timeout = timeout

    async def health(self) -> bool:
        target = self.health_url or self.base_url.replace("/v1", "")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(target)
                return resp.status_code < 500
        except Exception:
            return False

    async def chat(
        self, model: str, messages: list[dict[str, Any]], **kwargs: Any
    ) -> dict[str, Any]:
        payload = {"model": model, "messages": messages, **kwargs}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", json=payload)
            resp.raise_for_status()
            return resp.json()
