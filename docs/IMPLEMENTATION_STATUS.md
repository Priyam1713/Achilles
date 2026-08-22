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
- harness tournament scoring infrastructure (`scripts/harness_tasks.py`/
  `harness_tournament.py`, FIXES.md F-041), run for real against `native` and, once a
  WSL-side Rust/Cargo toolchain became available mid-session, a real compiled `goose`
  binary registered as a second `AgentLoop` (FIXES.md F-043) — see "Tier 6" below for
  what that comparison does and does not yet prove
- remote provider pool plug-and-play seam: `EngineSpec`/`CapabilityRequest` local-only
  exclusion gate, `RemoteQuotaLedger` (request/token/cost budgets plus a circuit
  breaker, every call attempt recorded for provenance), and `RemoteOpenAICompatibleBackend`
  resolving its credential from the OS keyring at call time (FIXES.md F-042) — no
  provider is actually enabled; see "Tier 6" below
- `desktop/`: a Tauri + React desktop app with an authenticated `KernelClient` (session
  token read directly off disk, never over the network) and real Roster/Jobs/Approvals/
  Collaboration views against the Tier 5 API (FIXES.md F-044) — a first vertical slice,
  not full feature parity; see "Tier 6" below for what is and is not yet built

The browser-served single-page control surface (`web/index.html`) remains the
loopback-only recovery/operator surface `D-010` always intended it to stay; the Tauri
desktop app above is now the primary human product's first real slice, not just a plan.

## Tier 6: harness tournament, desktop product, remote provider pool

- **Harness tournament** — infrastructure, `native`'s baseline, and now a second real
  `AgentLoop` are all real (F-041, F-043). A WSL-side Rust/Cargo toolchain turned out to
  already be present (an earlier check that found it absent had not sourced
  `~/.cargo/env` in a non-login shell); building Goose from source needed one additional
  system package (`libclang-dev`, for `bindgen`) and otherwise completed cleanly.
  `GooseAgentLoop` defaults to running the compiled binary with `--no-profile` and no
  extensions (genuinely zero filesystem/shell tool access) unless `enable_tools=True` is
  passed — a deliberate scope decision, not an oversight, made when the tool bridge
  itself did not exist yet. It now does: `agents/mcp_bridge.py` (FIXES.md F-045) exposes
  the same policy-gated `read_file`/`list_directory`/`run_command` tools to Goose via its
  own `--with-extension` mechanism, held to the identical `PolicyEngine`/
  `CapabilityGrant` gate the reference loop uses, live-verified through a real `goose`
  invocation both for a successful read and a correctly-denied mutation attempt (the
  target file reread from disk afterward to confirm, not just trusted from Goose's own
  report). `enable_tools` still defaults off everywhere existing (`kernel/app.py`'s
  registration included) since it needs the optional `harness` extra most installs will
  not have; the earlier "comparable evidence exists only for what a zero-tool Goose can
  attempt" limit from the first live run therefore still describes that run specifically,
  not a remaining architectural gap. A real live run against both loops (real local
  inference, no scripted responses) was genuinely inconclusive: three of four tasks timed
  out on both loops because the only "coding"-capable local model, `qwen38-27b`, is
  already known too slow under CPU offload (F-005/F-012); the fourth passed on both loops
  but for different reasons (native was actually denied by policy;
  Goose simply had no tool to attempt anything with).
- **Desktop product** — a real first vertical slice (F-044), reached only after the user
  installed Windows Rust/Node manually: two automated attempts had each hit a genuine
  dead end (a winget MSI install stuck on a UAC prompt this session had no rights to
  approve; the official per-user `rustup-init.exe`, which needs no elevation, removed by
  Windows Defender as a virus/PUP immediately after download) that this session correctly
  did not work around. `desktop/` is a Tauri + React app with a genuinely authenticated
  `KernelClient` (its Rust side reads `state/session.token` directly off disk — the same
  file the browser `/ui` page already uses, never sent over a network) and real
  Roster/Jobs/Approvals/Collaboration views against endpoints already built across Tier
  5. Deliberately skipped a literal Buzz source extraction (`D-010`'s own revisit trigger
  permits this) in favor of porting the interaction design `web/index.html` had already
  natively rebuilt. Live-verified: the actual running native window connected to the
  real kernel API and rendered the Overview tab end to end, confirmed in the server's own
  request log. Caught and fixed a real CORS bug in the same pass — the DNS-rebinding
  guard (F-004) was rejecting the webview's own origin outright, fixed with a second,
  still-precise origin allowlist. "Computer views" are honestly not built: no
  `ComputerController` in this codebase has a single registered controller yet.
- **Remote provider pool** — the plug-and-play seam this pool needs (data-classification/
  local-only exclusion gate, request/token/cost/quota/circuit-breaker accounting,
  secret-handle credential resolution, provenance recording — `knowledge/research.md`'s
  own stated preconditions) is built and tested (F-042). No provider is enabled: doing
  so needs real external credentials no session can supply itself, and is worth
  confirming rather than assuming — this project's own mission is local, open-source,
  subscription-free sovereignty, so whether, and which, remote providers belong in scope
  at all remains a decision for the user, not a default to build toward.

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

The identity-propagation gap named above is now closed for `Run` records and
`ExecutionBroker` (FIXES.md F-035): `AgentPayload` carries `agent_profile_id`/
`workspace_lease_id`, `NativeAgentLoop._run_command` forwards them into
`execution.run_approved()`, and `RosterService`'s delegation-spawned jobs set
`agent_profile_id` to the delegating subject — which lands on the `Run` row for free,
since `JobDispatcher.submit()` already snapshots the whole job request onto it. Memory
scope (F-033) is a separate story: nothing in production code calls
`ContextBuilder.retrieve_text()` at all yet, so there is no call site to propagate into.

Writing F-035's own tests surfaced that, as of that fix, holding an active
`CapabilityGrant` or a genuinely matching `WorkspaceLease` did not let a
`NativeAgentLoop`-issued `run_command` succeed at all — `PolicyEngine`'s untrusted-content
gate returned `allowed=False` unconditionally for `action="execute"` from the
`UNTRUSTED_MODEL_OUTPUT` trust `_run_command` always uses, and `ExecutionBroker` raised on
that before ever reaching the `approval_required`/`approved` check (FIXES.md F-036,
flagged for a decision rather than resolved unilaterally, since an existing pre-session
test explicitly asserted the denial as correct). The user chose to wire
`CapabilityGrant` into `ExecutionBroker` as the real authorization path (FIXES.md F-037):
`run_approved()` now checks `CapabilityGrantStore.is_active(subject_id, "execute",
"workspace")` before calling `PolicyEngine.evaluate()` at all, and a genuine match
bypasses the untrusted-content gate entirely. `RosterService`'s approval pipeline is now
load-bearing for execution — a delegation whose `execute:workspace` grant gets approved
can make a real `NativeAgentLoop` run actually execute a command, not just record that it
was allowed to.

Versioned workflow DAGs are implemented, the DAG-execution half of what was pending here
(FIXES.md F-038): `WorkflowDefinitionStore` holds immutable, `(name, version)`-keyed,
cycle-validated step graphs (Kahn's algorithm, not a heuristic); `WorkflowInstanceStore`
tracks one execution's per-step status; `WorkflowService.start()`/`advance()` create the
`Job` row for whichever steps just became ready. `job_executor.execute()`'s completion
hook is what makes this a real executor rather than an inert data structure: a step's job
succeeding automatically creates and submits its now-ready downstream step's job through
the real dispatcher, verified end to end via a full HTTP round trip, not just unit-tested
in isolation.

Recurring/scheduled triggers are also implemented now (FIXES.md F-039):
`RecurringTriggerStore` tracks an interval and next-due time per `WorkflowDefinition`;
`TriggerScheduler` (mirroring `JobDispatcher`'s own background-task shape) polls for due
triggers and calls the same `WorkflowService.start()` a manual
`POST /workflows/definitions/{id}/start` uses — no separate execution path for scheduled
vs. manual starts. Interval-only scheduling (no cron expressions or time-of-day rules).

The skill-candidate evaluation/promotion pipeline is also implemented now (FIXES.md
F-040), closing every object `docs/ARCHITECTURE.md`'s persistent-agency object-boundary
table named — **this completes Tier 5**. `SkillCandidateStore` extracts a proposal only
from a genuinely `succeeded` `Run`'s real recorded trajectory (never from a failed or
still-running attempt); `AgentEvaluationStore` records a `pass`/`fail` verdict plus
evidence; `SkillVersionStore` is `(name, version)`-keyed and genuinely immutable, and
`promote()` requires a passing evaluation already on record and is not repeatable.
Deliberately does not include a "replay this skill" execution engine — a promoted
`SkillVersion` is inert data until something else chooses to consult it; building an
engine that re-drives an `AgentLoop` against a stored trajectory is real, separate,
considerably larger work than the propose/evaluate/promote pipeline itself.

Still pending, genuinely unbuilt (not started, not just unwired):

- `collaboration/store.py`'s full retrofit onto `MigrationRunner` (F-026) — the
  `agent_profile_id` column was added via a targeted, idempotent `ALTER TABLE` instead,
  since that store is hash-chain integrity-critical and a full retrofit is real, separate
  surgery
- a "replay this skill" execution engine consuming a promoted `SkillVersion`'s trajectory
  (see F-040's own honest limits — the evaluation/promotion pipeline is built, execution
  from a stored trajectory is not)

These should be implemented as migrations and kernel services before adding Hermes Bot Mode,
A2A ingress or a roster UI, so no compatibility surface becomes the authoritative store.

For automation specifically, the optional Playwright package is locked but no Playwright
controller is registered. There is no managed browser-profile store, Kitesurf adapter,
Playwright MCP bridge, Browser Use strategy, Windows FlaUI broker, Windows Graphics Capture,
`SendInput` provider, human-takeover channel, UI-TARS worker adapter or Tauri shell yet. The
selected contracts, security boundary and implementation order are documented in
[AUTOMATION.md](AUTOMATION.md).

The architecture is designed so those integrations do not change the install topology, model manifest, security boundary or kernel contracts.
