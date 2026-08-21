from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class TrustLabel(StrEnum):
    TRUSTED_USER = "trusted_user"
    TRUSTED_LOCAL = "trusted_local"
    UNTRUSTED_WEB = "untrusted_web"
    UNTRUSTED_EMAIL = "untrusted_email"
    UNTRUSTED_DOCUMENT = "untrusted_document"
    UNTRUSTED_MODEL_OUTPUT = "untrusted_model_output"
    UNTRUSTED_COLLABORATION = "untrusted_collaboration"
    EXECUTION_RESULT = "execution_result"
    VERIFIED_RESULT = "verified_result"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ModelStatus(StrEnum):
    FINAL = "final"
    CANDIDATE = "candidate"
    EXCLUDED = "excluded"


class RoutingMode(StrEnum):
    FAST = "fast"
    SMART = "smart"
    DEEP = "deep"


class CapabilityRequest(BaseModel):
    capability: str
    mode: RoutingMode = RoutingMode.SMART
    modality: str | None = None
    expected_input_tokens: int = 0
    expected_output_tokens: int = 0
    requires_vision: bool = False
    requires_audio: bool = False
    requires_tool_use: bool = False
    license_context: Literal["personal", "research", "commercial"] = "personal"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelSpec(BaseModel):
    id: str
    name: str
    source: str | None = None
    source_type: str
    source_reviewed: bool = False
    status: ModelStatus
    install_policy: str
    capabilities: list[str]
    preferred_engines: list[str]
    profiles: dict[str, dict[str, Any]] = Field(default_factory=dict)
    quality_prior: float = 0.5
    resident_priority: int = 0
    license_note: str | None = None
    notes: str | None = None
    estimated_vram_mb: int = 0
    can_cpu_offload: bool = False
    exclusive_gpu: bool = True
    commercial_allowed: bool | None = None
    allow_patterns: list[str] = Field(default_factory=list)
    artifact: dict[str, Any] | None = None
    runtime_managed: bool = False


class EngineSpec(BaseModel):
    id: str
    kind: str
    enabled: bool = True
    base_url: str | None = None
    health_url: str | None = None
    manages_residency: bool = False
    notes: str | None = None
    model_aliases: dict[str, Any] = Field(default_factory=dict)


class ResourceSnapshot(BaseModel):
    timestamp: float
    gpu_name: str | None = None
    vram_total_mb: int = 0
    vram_used_mb: int = 0
    vram_free_mb: int = 0
    ram_total_mb: int = 0
    ram_used_mb: int = 0
    ram_free_mb: int = 0
    disk_total_gb: float = 0
    disk_free_gb: float = 0


class RouteCandidate(BaseModel):
    model_id: str
    engine_id: str
    score: float
    quality: float
    latency_score: float
    reliability: float
    reasons: list[str] = Field(default_factory=list)


class RouteDecision(BaseModel):
    request: CapabilityRequest
    selected: RouteCandidate | None
    candidates: list[RouteCandidate]
    resource_snapshot: ResourceSnapshot
    warnings: list[str] = Field(default_factory=list)


class ActionRequest(BaseModel):
    action: str
    scope: str
    trust: TrustLabel
    description: str
    mutates_state: bool = False
    uses_credentials: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyDecision(BaseModel):
    allowed: bool
    approval_required: bool
    risk: RiskLevel
    verifier: str | None = None
    reveal_secret_to_model: bool = False
    reason: str
