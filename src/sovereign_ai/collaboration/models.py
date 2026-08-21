from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

IdentityKind = Literal["human", "agent", "system"]


class IdentityRecord(BaseModel):
    """A collaboration identity is a room address, not a second identity database
    (docs/ARCHITECTURE.md, "Persistent agency and the roster domain"). `agent_profile_id`
    is the optional link to the durable `AgentProfile` that actually owns this identity's
    role, routing preferences, memory scopes, budgets and authority ceiling -- an identity
    with no linked profile (the common case today) is still fully functional; it just has
    no roster-domain authority ceiling to check against."""

    id: str
    display_name: str
    kind: IdentityKind
    trust: str
    agent: dict[str, Any] | None = None
    agent_profile_id: str | None = None
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

