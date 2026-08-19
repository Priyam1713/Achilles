from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

IdentityKind = Literal["human", "agent", "system"]


class IdentityRecord(BaseModel):
    id: str
    display_name: str
    kind: IdentityKind
    trust: str
    agent: dict[str, Any] | None = None
    created_at_ns: int


class RoomRecord(BaseModel):
    id: str
    name: str
    purpose: str
    created_at_ns: int


class CollaborationEvent(BaseModel):
    seq: int
    event_id: str
    room_id: str
    event_type: str
    actor_id: str
    payload: dict[str, Any]
    trust: str
    parent_event_id: str | None = None
    created_at_ns: int
    previous_hash: str
    event_hash: str


class AgentDispatch(BaseModel):
    agent_id: str
    room_id: str
    source_event_id: str
    capability: str
    mode: str
    messages: list[dict[str, Any]] = Field(default_factory=list)

