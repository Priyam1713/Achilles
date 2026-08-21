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
  bounded dispatch plus automatic retry/resume are pending
- pre-download upstream source/revision/size audit for every installation profile
- official-source release radar with explicit installed/developer-preview/announced lifecycles
- native collaboration rooms, logical identities, membership, threads, reactions and canvases
- mention-to-durable-job dispatch with threaded agent results and hash-chain verification

The current control UI is a browser-served single-page bootstrap/control surface, not the
planned Tauri desktop product.

The final pre-build audit also found that the folder has no Git baseline, mutation endpoints
have no local session authentication, SQLite stores have no general migration runner, job
submission creates unbounded in-process tasks, and startup accepts any process listening on a
configured port. The Git baseline now exists. The remaining items are tracked as F-004, F-010
and the migration gate in [FIXES.md](FIXES.md).

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

## Interfaces intentionally present but not falsely marked complete

The kernel has capability boundaries for specialist workers, media workers, agent loops and computer-control providers. Not every third-party model has a production worker service wired to the kernel yet. In particular, installing a checkpoint/environment is not the same as implementing and validating its model-specific request/response adapter.

The worker supervisor and JSON/HTTP worker contract are now implemented, including
on-demand launch, health checks, unload, profile-aware installation and supported-family
prewarming. Remaining work after the first physical build is capability-specific integration:

- concrete adapters/smoke tests for specialist families still marked unsupported by the shared worker
- end-to-end embedding → rerank → context path using the downloaded retrieval models
- live Playwright/UIA/UI-TARS computer-control providers behind the existing hierarchy
- agent-loop adapters (DeepSeek Harness or alternatives) behind the kernel contract
- capability-specific quality benchmark suites and automatic promotion/demotion reports
- persistent recurring schedules/watch definitions (ordinary background job controls are implemented)

The newly adopted persistent-agency domain is also architectural, not yet implemented.
Current collaboration `IdentityRecord` objects are lightweight room addresses, not complete
agent profiles, and a durable job currently contains one execution lifecycle rather than
separate attempts. Pending kernel objects include:

- `AgentProfile` plus profile-linked collaboration identities and scoped memberships
- addressed mailbox/presence projections over the event journal
- `Run` records beneath `Job`, including exact loop/model/skill/prompt and verification data
- structured `Delegation`, `CapabilityGrant` and `ApprovalRequest` records
- durable expiring workspace/resource leases; the current GPU lease is process-local
- versioned workflow DAGs and recurring triggers that create ordinary jobs
- scoped memory access enforcement and the skill-candidate evaluation/promotion pipeline

These should be implemented as migrations and kernel services before adding Hermes Bot Mode,
A2A ingress or a roster UI, so no compatibility surface becomes the authoritative store.

For automation specifically, the optional Playwright package is locked but no Playwright
controller is registered. There is no managed browser-profile store, Kitesurf adapter,
Playwright MCP bridge, Browser Use strategy, Windows FlaUI broker, Windows Graphics Capture,
`SendInput` provider, human-takeover channel, UI-TARS worker adapter or Tauri shell yet. The
selected contracts, security boundary and implementation order are documented in
[AUTOMATION.md](AUTOMATION.md).

The architecture is designed so those integrations do not change the install topology, model manifest, security boundary or kernel contracts.
