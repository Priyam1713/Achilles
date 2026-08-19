from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from sovereign_ai.kernel.types import TrustLabel


class DataEnvelope(BaseModel):
    """Information and authority travel separately. Content never upgrades its own trust."""

    data: Any
    source: str
    trust: TrustLabel
    confidence: float = 1.0
    content_hash: str | None = None
    license: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
