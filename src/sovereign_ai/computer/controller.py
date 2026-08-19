from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Protocol


class ControlTier(IntEnum):
    NATIVE_API = 10
    CLI = 20
    APPLICATION_PLUGIN = 30
    BROWSER_DOM = 40
    ACCESSIBILITY = 50
    VISION_GUI = 60


@dataclass
class ComputerAction:
    goal: str
    app: str | None = None
    destructive: bool = False
    metadata: dict[str, Any] | None = None


class Controller(Protocol):
    tier: ControlTier

    async def can_handle(self, action: ComputerAction) -> bool: ...
    async def execute(self, action: ComputerAction) -> dict[str, Any]: ...


class ComputerController:
    """Always prefers structured control. Screenshot/mouse/keyboard is the universal fallback, not default."""

    def __init__(self):
        self.controllers: list[Controller] = []

    def register(self, controller: Controller) -> None:
        self.controllers.append(controller)
        self.controllers.sort(key=lambda c: int(c.tier))

    async def execute(self, action: ComputerAction) -> dict[str, Any]:
        attempted: list[str] = []
        for controller in self.controllers:
            attempted.append(controller.__class__.__name__)
            if await controller.can_handle(action):
                result = await controller.execute(action)
                return {
                    "controller": controller.__class__.__name__,
                    "tier": int(controller.tier),
                    "result": result,
                }
        raise RuntimeError(f"No computer controller can handle action. Attempted: {attempted}")
