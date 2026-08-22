from __future__ import annotations

from typing import Any

import httpx

from sovereign_ai.kernel.secrets import SecretStore

from .base import InferenceBackend


class RemoteOpenAICompatibleBackend(InferenceBackend):
    """An OpenAI-compatible backend reached over the network rather than localhost.

    Identical wire protocol to `OpenAICompatibleBackend`; the only real differences are the
    ones research.md's remote-inference policy calls out: the API key is a secret handle
    resolved from `SecretStore` at call time, never a literal value in config or in
    anything a model sees, and a much shorter default timeout than a local GPU call needs,
    since a hung remote provider should fail fast rather than tie up the kernel's serialized
    GPU lease path (remote calls never need to -- they hold no GPU lease at all).
    """

    def __init__(
        self,
        base_url: str,
        api_key_secret: str,
        secrets: SecretStore,
        health_url: str | None = None,
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key_secret = api_key_secret
        self.secrets = secrets
        self.health_url = health_url
        self.timeout = timeout

    def _api_key(self) -> str:
        key = self.secrets.get(self.api_key_secret)
        if not key:
            raise RuntimeError(
                f"remote engine credential '{self.api_key_secret}' is not set in the OS "
                "credential store; this engine cannot be used until an operator provides it"
            )
        return key

    async def health(self) -> bool:
        if not self.health_url:
            # No provider-specific health endpoint configured: a missing credential is
            # itself the honest "not usable yet" signal, checked without a network call.
            try:
                self._api_key()
                return True
            except RuntimeError:
                return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    self.health_url, headers={"Authorization": f"Bearer {self._api_key()}"}
                )
                return resp.status_code < 500
        except Exception:
            return False

    async def chat(
        self, model: str, messages: list[dict[str, Any]], **kwargs: Any
    ) -> dict[str, Any]:
        payload = {"model": model, "messages": messages, **kwargs}
        headers = {"Authorization": f"Bearer {self._api_key()}"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions", json=payload, headers=headers
            )
            resp.raise_for_status()
            return resp.json()
