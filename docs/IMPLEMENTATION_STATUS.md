# Implementation status

This file exists to prevent the architecture from being mistaken for capabilities that have not yet been exercised on the target workstation.

Known defects in what *has* been built — with evidence, severity and fix order — are tracked
separately in [FIXES.md](FIXES.md). This file says what exists; that one says what is wrong
with it.

## Implemented and locally tested in this artifact

- configuration/model/capability registry validation
- source/license/hardware metadata parsing
- deterministic capability routing with local-benchmark override support
- GPU-heavy-job arbitration in the kernel inference path
- OpenAI-compatible inference adapter and llama.cpp model aliases
- Windows-to-WSL OpenShell execution adapter plus Docker fallback
- explicit writable-workspace capability registry
- fail-closed trust/authority policy checks
- OS keyring secret references
- append-only event store
- checkpoint persistence store (automatic runner reconstruction/resume is pending)
- provenance-aware lexical memory, persistent vector store and relationship graph
- transaction journal and rollback hooks
- deterministic verification interfaces
- contextual tool registry/discovery
- hierarchical computer-control abstraction
- watcher/event bus
- local API and control UI (loopback-only but not yet authenticated)
- one-shot Windows/WSL bootstrap scripts
- exact Hugging Face revision locks and post-install runtime Git commit records; immutable
  pre-install Git/package/container pins are pending
- isolated specialist dependency environments
- llama.cpp Qwen artifact/conversion preset generation and target-machine smoke-test script
- generated local-search secret rather than a checked-in credential
- WSL-native model/runtime/cache layout with a native Windows control plane
- core/workstation/full installation profiles and profile-aware dependency installation
- durable background job journal, cancellation, status API and restart interruption detection;
  bounded dispatch with a durable per-attempt `Run` journal is implemented (FIXES.md F-010).
  Retrying an interrupted or failed job is a real, durable operation (a new `Run` attempt,
  never mutating the old one) but is not automatic — a caller (human or API) still has to
  resubmit; nothing resumes a job on its own after a restart
- pre-download upstream source/revision/size audit for every installation profile
- official-source release radar with explicit installed/developer-preview/announced lifecycles
- native collaboration rooms, logical identities, membership, threads, reactions and canvases
- mention-to-durable-job dispatch with threaded agent results and hash-chain verification
- persistent-agency roster domain: durable `AgentProfile`, `Delegation`, `CapabilityGrant`,
  `ApprovalRequest` and `WorkspaceLease`, coordinated through the existing `PolicyEngine`
  (FIXES.md F-031), plus mailbox/presence read-models over existing events, leases and job
  state (FIXES.md F-032) — see "Persistent agency" below for what's still open in this domain

The current control UI is a browser-served single-page bootstrap/control surface, not the
planned Tauri desktop product.

The final pre-build audit also found that the folder had no Git baseline, mutation endpoints
had no local session authentication, SQLite stores had no general migration runner, job
submission created unbounded in-process tasks, and startup accepted any process listening on a
configured port. All five are now fixed: the Git baseline exists; session-token plus
Host/Origin authentication covers every mutation endpoint (F-004); a real
`MigrationRunner` plus online backup/restore exists (F-026); job submission goes through a
bounded `JobDispatcher` with a durable per-attempt `Run` journal (F-010); and port ownership
is verified across both the Windows and WSL2 namespaces (F-018/F-019). See
[FIXES.md](FIXES.md) for evidence and verification of each.

The audit's port-collision finding was **real and has been fixed**. Another local model
router (a uvicorn gateway from a separate project) does listen on `127.0.0.1:8080`. Commit
`b1a5b29` moved this installation's llama.cpp router to `18080` and added a service-identity
probe to `scripts/start.ps1`, so startup will not adopt a listener it did not create. The
foreign router is untouched. Port ownership is now verified by
`scripts/verify_host.py --check-ports`, which scans both the Windows host and the WSL2
namespace. See `docs/FIXES.md` F-018 and F-019.

The source-level test suite passes in the build environment.

## Hardware-bound steps performed by the one-shot bootstrap on the target workstation

These cannot be truthfully pre-certified from a different machine:

1. CUDA/driver/Blackwell compatibility on the installed host.
2. Building the current llama.cpp CUDA backend.
3. Downloading the selected upstream checkpoints and resolving their exact revisions.
4. Converting Qwen3.5 to Q6_K and verifying the revision-locked Qwen3.8 UD-Q4_K_M,
   vision-projector and MTP artifacts.
5. Loading each Qwen profile through the real llama.cpp router and producing a smoke response.
6. Creating each isolated specialist environment and confirming Torch can see the target GPU.
7. Later capability benchmarks that replace manifest priors with measurements from the real workstation.

A failed hardware-bound step is a failed install; it is not silently promoted to `working`.

**This list describes what a fresh install must get through, not this machine's current
state** — that distinction is exactly what went stale here once (FIXES.md F-020: this file
kept describing model download, the CUDA build and specialist environments as work still
to be performed on a workstation where all three were long since done). For the real,
mechanically-derived state of *this* install — which runtime commits are checked out versus
locked, which specialist worker environments exist, which manifest models are on disk and
GGUF-converted, and whether OpenShell reports healthy — run `python3 scripts/doctor.py`
after `source scripts/runtime_env.sh`. It reads only lock files and the filesystem; nothing
in its output is hand-maintained prose.

## Interfaces intentionally present but not falsely marked complete

The kernel has capability boundaries for specialist workers, media workers, agent loops and computer-control providers. Not every third-party model has a production worker service wired to the kernel yet. In particular, installing a checkpoint/environment is not the same as implementing and validating its model-specific request/response adapter.

The worker supervisor and JSON/HTTP worker contract are now implemented, including
on-demand launch, health checks, unload, profile-aware installation and supported-family
prewarming. Remaining work after the first physical build is capability-specific integration:

- concrete adapters/smoke tests for specialist families still marked unsupported by the shared worker
- live Playwright/UIA/UI-TARS computer-control providers behind the existing hierarchy
- capability-specific quality benchmark suites and automatic promotion/demotion reports
  (a real quality-eval harness exists — `scripts/evaluate_brain_quality.py` — but promotion
  itself stays a human decision by design, matching D-001)
- persistent recurring schedules/watch definitions (ordinary background job controls are implemented)

Two items formerly listed here are done:
- the embedding → rerank → context path is wired end to end
  (`memory/retrieval_adapter.py`'s `SpecialistVectorRetriever`/`MemoryIndexer`, FIXES.md
  F-030), using the real downloaded retrieval models, not a stub
- a working reference `AgentLoop` exists (`agents/native_loop.py`, FIXES.md F-027) — a
  native JSON tool-calling loop built instead of a DeepSeek Harness integration, since that
  harness requires a Rust/Cargo toolchain this workstation doesn't have. DeepSeek Harness
  itself (or another external harness) remains unintegrated if one is wanted later; the
  kernel-side `AgentLoop` contract it would plug into already exists and is exercised by
  the native implementation.

The persistent-agency domain's safety-critical core is now implemented (FIXES.md F-031):
`AgentProfile` (`kernel/agent_profiles.py`) is a durable logical coworker with an authority
*ceiling* — the most a run acting for it could ever be granted, never authority by itself.
`Delegation` (`kernel/delegations.py`), `CapabilityGrant` (`kernel/capability_grants.py`)
and `ApprovalRequest` (`kernel/approvals.py`) exist as real, tested stores, coordinated by
`kernel/roster.py`'s `RosterService`: proposing a delegation never grants authority by
itself — every requested grant is run through the same, unmodified `PolicyEngine.evaluate()`
every other action in this kernel goes through, and becomes an active grant only when
policy allows it outright or a human resolves the `ApprovalRequest` policy required.
`WorkspaceLease` (`resources/workspace_leases.py`) mirrors the GPU lease's TTL-based
design, layered on top of the existing `WorkspaceRegistry` allow-list rather than
replacing it. Collaboration `IdentityRecord`s can now optionally link to an `AgentProfile`
via `agent_profile_id` — a channel address that references a profile, not a second
identity database — though most identities today still have no link, which is fully
supported (an unlinked identity just has no roster-domain authority ceiling to check).

A `Run` record exists beneath every `Job` (`kernel/runs.py`, FIXES.md F-010) as a true
durable attempt log — the request, result, error and timing of every attempt, retrying
without rewriting history — and the GPU lease is a durable, cross-process `GPULeaseStore`
with TTL-based staleness recovery (`resources/gpu_leases.py`, FIXES.md F-011), not
process-local.

Mailbox and presence are also implemented (FIXES.md F-032), as read-models rather than new
mutable state: `CollaborationService.mailbox(identity_id)` splits an identity's events
(scoped to rooms it currently belongs to) into `inbox` (events mentioning it) and `outbox`
(events it authored) — the same `mentions` field `_dispatches` already uses for paging, not
a new definition of "addressed to". `kernel/presence.py`'s `PresenceService.compute()`
derives `active`/`idle` purely from whether the subject holds an active `CapabilityGrant`,
an active `WorkspaceLease`, or a delegation with a `queued`/`running` job — no self-asserted
status, no new liveness signal invented.

Memory scope filtering is implemented as a real, enforced mechanism (FIXES.md F-033):
`MemoryStore.search_lexical()` and `LocalVectorStore.search_vector()` both accept an
`allowed_projects` filter (unscoped memories always visible; a non-empty list adds those
specific projects; an empty list means unscoped-only — the fail-closed reading for zero
granted scopes), and `ContextBuilder.retrieve_text()` threads it through both the lexical
and vector retrieval stages. What remains open is propagation, not the mechanism: nothing
currently calls it with an actual `AgentProfile.memory_scopes` value, because no code path
yet knows which profile a given call is acting for — the same gap already named below for
`Run` identity.

`WorkspaceLease` is now an opt-in enforced gate in `ExecutionBroker.run_approved()`
(FIXES.md F-034): a caller that supplies `subject_id`/`workspace_lease_id` gets four real
checks (lease exists and is held by that exact subject; its `root_path` covers the target
`cwd`; a mutating call is refused through a read-only lease) before the existing
policy/backend logic runs. No existing caller passes these yet, so this is additive, not a
behavior change — verified by the full suite passing unchanged the moment the parameters
were wired, before any new test existed.

Still pending, genuinely unbuilt (not started, not just unwired):

- propagating `AgentProfile` identity through `NativeAgentLoop`/`job_executor` so calls
  into `ContextBuilder.retrieve_text()` (memory scope, F-033) and `ExecutionBroker
  .run_approved()` (workspace lease, F-034), and `Run` records (F-031), actually know
  which profile they are acting for — one propagation gap, named three times because it
  blocks three different opt-in mechanisms from ever firing automatically
- versioned workflow DAGs and recurring triggers that create ordinary jobs
- the skill-candidate evaluation/promotion pipeline (`SkillCandidate`/`SkillVersion`/
  `AgentEvaluation`)
- `collaboration/store.py`'s full retrofit onto `MigrationRunner` (F-026) — the
  `agent_profile_id` column was added via a targeted, idempotent `ALTER TABLE` instead,
  since that store is hash-chain integrity-critical and a full retrofit is real, separate
  surgery

These should be implemented as migrations and kernel services before adding Hermes Bot Mode,
A2A ingress or a roster UI, so no compatibility surface becomes the authoritative store.

For automation specifically, the optional Playwright package is locked but no Playwright
controller is registered. There is no managed browser-profile store, Kitesurf adapter,
Playwright MCP bridge, Browser Use strategy, Windows FlaUI broker, Windows Graphics Capture,
`SendInput` provider, human-takeover channel, UI-TARS worker adapter or Tauri shell yet. The
selected contracts, security boundary and implementation order are documented in
[AUTOMATION.md](AUTOMATION.md).

The architecture is designed so those integrations do not change the install topology, model manifest, security boundary or kernel contracts.
