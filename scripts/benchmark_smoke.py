from __future__ import annotations

import argparse
import asyncio
import time

import httpx


async def main(url: str, model: str):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 8,
    }
    t = time.perf_counter()
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(url.rstrip("/") + "/chat/completions", json=payload)
        r.raise_for_status()
        data = r.json()
    dt = (time.perf_counter() - t) * 1000
    print({"latency_ms": round(dt, 2), "response": data})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--model", required=True)
    a = ap.parse_args()
    asyncio.run(main(a.url, a.model))
