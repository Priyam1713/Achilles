from __future__ import annotations

import httpx


class ResidencyCoordinator:
    """Coordinates VRAM ownership across otherwise independent inference runtimes."""

    def __init__(self, llama_router_url: str = "http://127.0.0.1:8080", timeout: float = 30.0):
        self.llama_router_url = llama_router_url.rstrip("/")
        self.timeout = timeout

    async def release_llama(self) -> list[str]:
        """Unload active llama.cpp router models before another runtime claims the GPU.

        Sleeping models already have their model/KV memory unloaded, so they are left alone.
        A missing llama router is not an error: specialist/media runtimes can still operate.
        """
        unloaded: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.get(f"{self.llama_router_url}/models")
                if r.status_code >= 500:
                    return unloaded
                r.raise_for_status()
                models = r.json().get("data", [])
                for item in models:
                    status = (item.get("status") or {}).get("value")
                    model_id = item.get("id")
                    if status not in {"loaded", "loading"} or not model_id:
                        continue
                    out = await client.post(
                        f"{self.llama_router_url}/models/unload", json={"model": model_id}
                    )
                    out.raise_for_status()
                    unloaded.append(str(model_id))
        except (httpx.HTTPError, OSError, ValueError):
            return unloaded
        return unloaded
