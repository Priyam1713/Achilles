// Mirrors the Pydantic record shapes served by src/sovereign_ai/api/server.py. Kept
// intentionally minimal -- only the fields the views below actually render, not a full
// schema mirror -- so a backend field addition never silently breaks this file's
// compile; a field this client actually needs but the backend omits fails loudly at the
// call site instead.

export interface ResourceSnapshot {
  gpu_name: string | null;
  vram_total_mb: number;
  vram_free_mb: number;
  ram_free_mb: number;
  disk_free_gb: number;
}

export interface HealthResponse {
  ok: boolean;
  resources: ResourceSnapshot;
}

export type JobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export interface JobRecord {
  id: string;
  kind: string;
  status: JobStatus;
  request: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string | null;
  cancellation_requested: boolean;
  created_at: number;
  updated_at: number;
  started_at: number | null;
  finished_at: number | null;
  metadata: Record<string, unknown>;
}

export type AgentProfileStatus = "active" | "suspended" | "retired";

export interface AgentProfileRecord {
  id: string;
  display_name: string;
  role: string;
  status: AgentProfileStatus;
  routing_preferences: Record<string, unknown>;
  memory_scopes: string[];
  budgets: Record<string, unknown>;
  authority_ceiling: string[];
  created_at: number;
  updated_at: number;
  metadata: Record<string, unknown>;
}

export type DelegationStatus =
  | "proposed"
  | "awaiting_approval"
  | "authorized"
  | "denied"
  | "completed";

export interface DelegationRecord {
  id: string;
  parent_subject_id: string;
  objective: string;
  inputs: Record<string, unknown>;
  expected_artifacts: string[];
  acceptance_tests: string[];
  requested_grants: Array<Record<string, unknown>>;
  deadline: number | null;
  budget: Record<string, unknown>;
  status: DelegationStatus;
  child_job_id: string | null;
  created_at: number;
  updated_at: number;
}

export type ApprovalStatus = "pending" | "approved" | "denied" | "expired";

export interface ApprovalRequestRecord {
  id: string;
  subject_id: string;
  action: string;
  scope: string;
  risk: string;
  reason: string;
  evidence: Record<string, unknown>;
  status: ApprovalStatus;
  resolver_id: string | null;
  resolution_reason: string | null;
  created_at: number;
  expires_at: number;
  resolved_at: number | null;
}

export interface CapabilityGrantRecord {
  id: string;
  subject_id: string;
  action: string;
  scope: string;
  granted_by: string;
  expires_at: number;
  revoked: boolean;
}

export interface PresenceRecord {
  subject_id: string;
  active: boolean;
  reasons: string[];
}

export interface CollaborationMember {
  id: string;
  kind: "human" | "agent" | "system";
  display_name: string;
}

export interface CollaborationRoom {
  id: string;
  name: string;
  purpose: string;
  members: CollaborationMember[];
}

export interface CollaborationEvent {
  event_id: string;
  event_type: string;
  actor_id: string;
  payload: Record<string, unknown>;
  parent_event_id: string | null;
  created_at_ns: string;
  event_hash: string;
}

export interface ChainVerification {
  valid: boolean;
  events: number;
  broken_at?: string | null;
}
