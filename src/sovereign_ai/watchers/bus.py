from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class Event:
    topic: str
    payload: dict[str, Any]


Handler = Callable[[Event], Awaitable[None]]


class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[Handler]] = {}
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._running = False

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._handlers.setdefault(topic, []).append(handler)

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        await self._queue.put(Event(topic, payload))

    async def run(self) -> None:
        self._running = True
        while self._running:
            event = await self._queue.get()
            for handler in self._handlers.get(event.topic, []) + self._handlers.get("*", []):
                await handler(event)
            self._queue.task_done()

    def stop(self) -> None:
        self._running = False
