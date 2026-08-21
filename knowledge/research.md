# Living research and architecture ledger

> Last consolidated: **2026-08-21**  
> Target: Windows host + Ubuntu 24.04/WSL2, RTX 5070 Ti Laptop GPU (12 GB VRAM),
> 32 GB host RAM  
> Architecture truth: [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)  
> Implementation truth: [docs/IMPLEMENTATION_STATUS.md](../docs/IMPLEMENTATION_STATUS.md)

This is the project's durable memory for **what we learned, what we decided, and why**.
It is not a news feed or a wishlist. A repository or model appearing here does not make it
an installation dependency, and an upstream benchmark does not make it locally proven.

## How to maintain this ledger

Whenever research or an architecture change matters:

1. Date the finding and link its primary source.
2. Record whether the source was inspected, merely announced, or still unverified.
3. Map it to a concrete problem and an existing kernel seam.
4. Choose `adopted`, `trial`, `watch`, `reference`, `declined`, or `superseded`.
5. State the reason, the risk, and the measurable promotion gate.
6. Update the current snapshot if the decision changes.
7. Append a decision-history entry; never erase the earlier reasoning.
8. If code changes, also update implementation status and the relevant architecture/security
   document. Research alone must never be described as implemented.

Before installing any moving upstream, resolve an immutable commit or artifact revision,
review its license and install path, and preserve a rollback route.

### Evidence labels

| Label | Meaning |
| --- | --- |
| `primary-verified` | Official repository, model card, paper, or vendor documentation was inspected. |
| `independent-verified` | A claim was reproduced by us or a credible independent party. |
| `vendor-claim` | Real primary source, but the performance/security claim is not independently proven. |
| `announced` | Official announcement exists; ordinary public artifact or weights do not yet. |
| `unverified` | Do not use for architecture or installation decisions. |

### Decision labels

| Label | Meaning |
| --- | --- |
| `adopted` | It is part of the intended architecture. Check implementation status separately. |
| `trial` | A bounded, reversible experiment is justified. Not the default path. |
| `watch` | Track releases; do not integrate yet. |
| `reference` | Mine ideas or use as a comparison, without taking the runtime dependency. |
| `declined` | It does not currently earn its complexity/cost. Revisit only on a stated trigger. |
| `superseded` | A newer recorded decision replaced it. |

## Finalized baseline

These are the decisions new research must fit rather than silently overthrow.

1. **The model is a component; the kernel is the system.** The local kernel owns authority,
   policy, secrets, durable jobs, state, routing, resources, transactions, provenance,
   verification, recovery, and audit.
2. **No harness is the root of trust.** DeepSeek Harness, Grok Build, GSD, Codex, or any
   future agent loop can be an adapter. None receives implicit host authority.
3. **Local-first is a privacy and availability policy, not a purity test.** Remote models may
   be explicit escalation targets for tasks the machine cannot do well, subject to data
   classification, quotas, consent, and an auditable route decision.
4. **Conversation is not authorization.** Collaboration messages, web content, retrieved
   documents, model output, and tool descriptions remain untrusted until policy and a
   verifier say otherwise.
5. **Only verified progress becomes trusted durable state.** A model saying that work
   succeeded is evidence to inspect, not a post-condition.
6. **Fast-moving systems sit behind replaceable interfaces.** Model, inference, harness,
   memory, gateway, sandbox, and collaboration implementations can be changed independently.
7. **This workstation's measurements win.** Source/license checks, exact-machine quality,
   latency, VRAM/RAM, failure recovery, and security tests decide promotion.
8. **The system is open source, end to end, and is meant to be given away.** Every component
   in the critical path must be self-hostable and openly licensed. Closed-source software,
   subscription-gated services, and hosted commercial inference APIs are not candidates —
   not as defaults, not as fallbacks. The audience is people who cannot or will not rely on
   a subscription, and the deliverable is something they can run on their own hardware and
   adapt. A component that is best-in-class but proprietary does not qualify. "Open weights"
   is not the same as open source, and the distinction is a gate, not a footnote.

## Current architecture snapshot

| Concern | Current owner/default | State | Why |
| --- | --- | --- | --- |
| Authority, policy, jobs, audit | Native sovereign kernel | `adopted`, implemented | These are long-lived invariants and cannot belong to a model or harness. |
| Agent loops | `AgentLoop` adapters; none promoted as the system | `adopted`, adapters pending | Lets us compare harnesses without architectural capture. |
| Fast cognition | Qwen3.5-9B Q6_K via llama.cpp | `adopted`, hardware test pending | Economical repeated routing/tool decisions. |
| Deep cognition | Qwen3.8-27B UD-Q4_K_M, partial offload, initial 16K context | `adopted`, hardware test pending | Largest sensible quality tier for 12 GB VRAM + 32 GB RAM. |
| Remote escalation | Provider pool behind the inference interface | `trial`, not implemented | Gives access to models that cannot fit locally without making cloud availability mandatory. |
| Execution | NVIDIA OpenShell preferred; hardened Docker fallback | `adopted`, adapter implemented | Policy-enforced isolation with a fail-closed replaceable fallback. |
| Memory | Native provenance-aware lexical/vector/graph stores | `adopted`, implemented | Canonical state remains local, inspectable, deletable, and independent of one memory vendor. |
| Collaboration | Native Buzz-inspired rooms and canvases | `adopted`, implemented | Keeps the fun shared-workspace ideas without importing a second authority/runtime stack. |
| Protocol edge | Kernel adapters directly | `adopted`; agentgateway `trial` | A gateway becomes valuable when MCP/A2A/remote-provider traffic grows, not merely because it exists. |
| Endpoint observation | Kernel audit plus Numbat candidate | Native audit implemented; Numbat `trial` | Internal intent and external endpoint facts are complementary evidence. |
| Capability models | Replaceable specialists in isolated workers | `adopted`, family-specific work remains | Avoids one Torch/CUDA dependency graph poisoning the control plane. |

### Intended provider seams

```text
experience / native collaboration
                 │
                 ▼
        SOVEREIGN AI KERNEL
 policy • authority • jobs • state • verification • audit
     │             │              │              │
     ▼             ▼              ▼              ▼
 AgentLoop     ProtocolEdge   Execution      MemoryProvider
 adapters       adapter       provider        adapters
     │             │              │              │
 DSH/GSD/      direct or      OpenShell       native stores
 LongHorizon/  agentgateway   BoxLite trial   Hindsight trial
 Grok Build                   Docker fallback
```

Omnigent, Eve, QM, and Buzz are valuable comparisons around this diagram; none becomes a
second kernel.

## Research wave 1 — models, harnesses, collaboration, security, and remote capacity

Consolidated on 2026-08-19 from official sources and the first repository pass.

| Finding | Evidence | Decision | Reason and boundary |
| --- | --- | --- | --- |
| [Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B) | `primary-verified` | `adopted` as heavy local brain | Vision, thinking control, and agent capability are useful; UD-Q4_K_M with CPU offload is the fit candidate. Native maximum context is not our operating context. |
| [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B) | `primary-verified` | `adopted` as fast brain | A 27B model for every routing and summarization turn wastes time, RAM, and energy. |
| [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) | `primary-verified` developer preview | `trial` as an `AgentLoop`; `declined` as the whole system | Its plugin/event-log design is excellent, but its lifecycle and authority must remain below our kernel. |
| [Prime Agent](https://github.com/PrimeIntellect-ai/prime-agent) | `primary-verified` | `reference` with a future sandboxed trial | Programmatic tool composition and a persistent computation environment are useful. Unrestricted self-rewriting is outside policy. |
| [Block Buzz](https://github.com/block/buzz) | `primary-verified` | `reference`; selected concepts already implemented natively | Rooms, mentions, threads, reactions, canvases, visible work, and event history are useful. Its app/relay/identity stack duplicates our single-machine system. |
| [Perplexity Numbat](https://github.com/perplexityai/numbat) | `primary-verified` | `trial` as an external observer/blocker | Endpoint telemetry and forensic reconstruction can catch what an internal harness trace misses. It must not replace kernel policy or sandboxing. |
| Frontier/cloud-only models | Mixed official release states | `watch`/explicit remote escalation | GLM, DeepSeek, Kimi, Qwen hosted, and other frontier tiers can add capacity without local weights. Availability, licenses, data policy, and names change quickly. |
| Free/limited API collections | Provider terms are mutable | `reference` for discovery only | A collection can seed candidates, but the kernel must integrate providers individually from official docs and never trust a third-party list for quota, privacy, or credentials. |

### Remote inference policy

Candidate providers discovered in the first pass included Cerebras, Groq, OpenRouter,
Gemini, GitHub Models, Cloudflare Workers AI, Vercel AI Gateway, and OVH AI Endpoints.
Free quotas and available models are intentionally **not copied here as timeless facts**.
They must be rechecked against official terms on the day a provider is configured.

A provider may be enabled only when it has:

- an adapter behind the existing inference interface;
- a secret handle, never a key in prompts or configuration committed to source;
- explicit data-classification rules and local-only exclusions;
- request, token, cost, quota, timeout, and circuit-breaker limits;
- provenance recording of provider, model, endpoint, and route reason;
- a local fallback or an honest failure mode;
- a small evaluation set proving it adds a capability or quality tier.

Remote inference is not durable memory, a root of trust, or permission to upload private
workspace contents.

## Research wave 2 — runtime, memory, governance, and durable project execution

All ten repositories below were present, public, active, and inspected at their official
GitHub source on **2026-08-19**. Their default branches are mutable; pin a commit before any
trial.

| Repository | License at review | What is genuinely useful to us | Decision now | Promotion gate / caveat |
| --- | --- | --- | --- | --- |
| [NVIDIA/OpenShell](https://github.com/NVIDIA/OpenShell) | Apache-2.0 | Declarative filesystem/network/process/inference policy, credential providers, controlled egress, and isolated sandboxes | `adopted` execution provider | Upstream calls it alpha. Keep Docker fallback; pass WSL lifecycle, deny-by-default egress, secret non-disclosure, restart, and escape tests. |
| [omnigent-ai/omnigent](https://github.com/omnigent-ai/omnigent) | Apache-2.0 | A broad harness/sandbox/provider compatibility matrix, common harness control, policy scopes, session mobility, and existing OpenShell/BoxLite/Hindsight integrations | `reference`; possible interoperability fixture | It overlaps heavily with our kernel. Windows supports its server/SDK harnesses, but stronger filesystem/network isolation requires WSL/Linux. Do not nest its authority over ours. |
| [vectorize-io/hindsight](https://github.com/vectorize-io/hindsight) | MIT | Retain/recall/reflect, temporal/entity-aware hybrid retrieval, memory banks, mental models, MCP/HTTP clients | high-priority `trial` behind `MemoryProvider` | Begin in shadow mode. Native memory stays canonical. Measure recall precision, contradiction/supersession, deletion, provenance retention, latency, local-model compatibility, and failure recovery. Reflection can propose knowledge, never change policy. |
| [boxlite-ai/boxlite](https://github.com/boxlite-ai/boxlite) | Apache-2.0 | Embeddable, persistent OCI micro-VMs with a separate kernel, controlled networking, and secret placeholders | `trial` execution provider after OpenShell | On this PC it requires WSL2 with working KVM access. First trial CPU/tool sandboxes only. Compare cold/warm start, persistence, cleanup, filesystem escape, egress, RAM, and operational complexity. |
| [AMAP-ML/LongHorizon-Harness](https://github.com/AMAP-ML/LongHorizon-Harness) | MIT | Manager–executor–auditor separation, fresh execution contexts, independent inspection, and admission of verified progress only | `adopted` as a control-loop pattern; runtime `trial` | Implement the semantics in kernel jobs/checkpoints first. Compare its adapter on interrupted multi-hour tasks; no role may approve its own output or bypass kernel authority. |
| [vercel/eve](https://github.com/vercel/eve) | Apache-2.0 | Filesystem-first agents, inspectable instructions/tools/skills/channels/schedules, durable resumable sessions, human-in-the-loop patterns | `reference` | It is beta and currently brings a Node/Vercel-oriented application stack. Borrow conventions only where they simplify our files; do not introduce a second scheduler, state store, or policy plane. |
| [agentgateway/agentgateway](https://github.com/agentgateway/agentgateway) | Apache-2.0 | One MCP/A2A/LLM chokepoint for authentication, RBAC, rate limits, routing/failover, guardrails, and OpenTelemetry | high-priority `trial` at `ProtocolEdge` | Start in observe-only mode. Kernel policy remains authoritative. Promote only if MCP/remote traffic justifies the process and it fails closed without breaking local operation. |
| [open-gsd/gsd-pi](https://github.com/open-gsd/gsd-pi) | MIT | DB-authoritative project state, human-readable Markdown projections, worktree isolation, resumable auto mode, scoped verification commands, and parallel task dependency handling | `reference`; coding-project adapter `trial` | Borrow verification receipts/state projections. Test on one disposable repository; require diff/test receipts and recovery after interruption. It does not own global memory, secrets, or policy. |
| [yc-software/qm](https://github.com/yc-software/qm) | MIT | Durable per-person/per-room scopes containing memory, files, permissions, schedules, key views, and persistent computers; implementations sit behind interfaces | `reference` | Excellent future multi-user pattern, excessive as our current single-user Slack/web platform. Borrow scope IDs and durable-by-default rules; revisit when independent users or tenants exist. |
| [xai-org/grok-build](https://github.com/xai-org/grok-build) | Apache-2.0 | Production-shaped Rust CLI/TUI, headless mode, checkpoints, MCP, ACP editor integration, and a serious coding-agent runtime | `trial` as a benchmark competitor | Released binaries support Windows, but building this synced source tree is best supported on Linux/macOS and external contributions are closed. Benchmark task success, recovery, edits, tool safety, local/remote model flexibility, and resource cost against DSH—not branding. |

### What changed because of wave 2

The earlier phrase “DeepSeek Harness as the base harness candidate” is superseded. The
correct design is:

- **sovereign kernel:** stable authority and durable truth;
- **replaceable agent kernels/loops:** DeepSeek Harness, LongHorizon, GSD, Grok Build, and
  future adapters;
- **replaceable execution providers:** OpenShell, BoxLite, and hardened Docker;
- **replaceable memory providers:** native stores remain canonical; Hindsight may derive and
  retrieve richer memories;
- **optional protocol gateway:** agentgateway governs MCP/A2A/LLM traffic at the edge while
  kernel policy remains authoritative;
- **verified project controller:** manager/executor/auditor roles, fresh contexts, worktrees,
  and verification receipts are kernel orchestration features, not the property of one
  harness.

This is composition, not a stack of nested applications. We take the best independently
testable mechanism from each project and keep one authority, one durable job truth, and one
audit vocabulary.

## Research wave 3 — persistent coworkers, delegation, and agent interoperability

Consolidated on 2026-08-19 after comparing the proposal with the actual kernel code and
checking the named products against primary sources.

### Verdict

The missing abstraction is real: the repository has room identities, durable jobs, a minimal
`AgentLoop`, workspace registration, and an exclusive GPU arbiter, but it does **not** yet
have persistent agent profiles, job attempts/runs, mailboxes, delegation contracts, workflow
DAGs, durable workspace/resource leases, structured approvals, or evaluated skill versions.

Adopt the persistent roster concept with these corrections:

1. **Roster is a domain, not a new authority.** Its state is owned by kernel stores and
   policy; the roster/UI is a projection and command surface.
2. **An authority ceiling is not a grant.** A profile may say what an agent can potentially
   request. The kernel issues a narrower, expiring `CapabilityGrant` to one run after policy
   and approvals.
3. **Rooms display work; they do not own it.** `job.created`, delegation, approval and
   verification cards reference canonical kernel records. The room event chain is not a
   competing job database.
4. **Mailbox and presence are derived.** Addressed immutable events form the inbox/outbox;
   active leases, run state and health checks determine presence. This avoids another mutable
   queue and model-claimed status.
5. **Escalation cannot trust raw model confidence.** Verifier disagreement, repeated
   post-condition failure, measured task/risk classification and benchmark evidence are valid
   triggers. A confidence threshold is usable only after local calibration.

### Authoritative object boundaries

| Object | Owns | Must not own |
| --- | --- | --- |
| `AgentProfile` | Durable role, preferences, route policy, memory access policy, budgets, authority ceiling | A running model, live credentials, or active permissions |
| `Job` | Requested outcome, origin, priority, acceptance contract | One harness-specific trajectory |
| `Run` | One attempt; exact loop/model/prompt/skills, checkpoints, leases, result and verification receipt | The long-lived coworker identity |
| `Delegation` | Parent-child objective, artifacts, tests, requested grants, deadline and budget | Authority merely because one agent requested it |
| `CapabilityGrant` | Expiring subject/action/resource scope and approval provenance | A reusable secret or unbounded host permission |
| `WorkspaceLease` | Run-scoped isolated workspace or approved persistent volume | Permanent agent ownership of an arbitrary host path |
| `ResourceLease` | Time-bounded GPU/RAM/CPU/disk/cloud allocation with heartbeat/expiry | Indefinite reservation by an idle agent |
| `ApprovalRequest` | Structured decision, risk, evidence, expiry and resolver | A chat reaction interpreted as permission |
| `WorkflowDefinition` | Immutable versioned DAG/factory definition | Mutable in-flight state; instances/runs record that separately |
| `SkillCandidate` / `SkillVersion` | Untrusted proposal versus evaluated, signed promotion | Permission to change its own evaluator, policy or authority |
| `AgentEvaluation` | Local evidence tied to profile/loop/model/skill versions | Vendor benchmark claims treated as local truth |

`AgentMailbox` and agent presence should initially be read models over the event journal,
not independent authoritative objects. Generic scope membership should back rooms, teams,
projects and agents so memory and authority do not acquire several incompatible ACL systems.

### Integration assessment

| Candidate | Verification | Decision | Boundary and correction |
| --- | --- | --- | --- |
| [NousResearch Hermes Agent](https://github.com/NousResearch/hermes-agent) | `primary-verified` | `trial` after roster/run contracts | Its messaging gateway, cron, memory, skills, subagents, programmatic tools and learning loop are real. Keep agent-loop/tool execution and optional experience adapters; translate or mirror the overlapping state into kernel jobs, schedules, delegations, memory candidates and events. |
| [NVIDIA NemoClaw](https://github.com/NVIDIA/NemoClaw) | `primary-verified` | preferred containment path for the Hermes trial | NVIDIA documents Hermes as tested in OpenShell, but explicitly does not assert production parity with its default OpenClaw path. Pin versions and use the execution conformance suite. |
| [A2A Protocol](https://github.com/a2aproject/A2A) | `primary-verified`, published 1.0 specification | `adopted` at the external trust boundary; implementation later | Map authenticated external Agent Cards, tasks, messages and artifacts into zero-authority identity/delegation proposals. Internal agents retain richer kernel-native contracts. Discovery never grants capability. |
| [Cloudflare Kitesurf](https://developers.cloudflare.com/browser-run/kitesurf/) | `primary-verified` beta | optional cloud `BROWSER_DOM` backend | It is lightweight, stateless and CDP/MCP-compatible, but not pixel-perfect and currently unsuitable for persistent authenticated sessions, video or WebGL. Use local Playwright first for private/authenticated work. |
| [Warp software factories](https://www.warp.dev/blog/software-factory-build-guide) | `primary-verified` concept; product surface moving/early | `reference` | Adopt versioned triage→spec→implement→review→verify workflow ideas, not a second cloud job/policy system. Build the minimal kernel DAG only after `Run` and delegation semantics exist. |
| Grok Bot | `unverified` as a standalone public integration contract | `watch` only | Keep separate from the verified open-source [Grok Build](https://github.com/xai-org/grok-build) harness and any Grok inference model. Add an external adapter only when an official API/A2A contract exists. |
| “Grok 4.6” | `unverified` in official xAI model sources checked on 2026-08-19 | `declined` as a current configuration name | Never create a route for a name that cannot be resolved in official model/API documentation. |
| “OpenAI Presence” | `unverified` in official OpenAI documentation checked on 2026-08-19 | `reference` idea only, no dependency | Presence, policy, escalation and evaluation concepts stand on their own; do not cite a product that official documentation does not establish. |

### Minimal implementation sequence

1. Introduce schema-versioned `AgentProfile` and `Run`; migrate each room agent identity to
   reference a profile without duplicating IDs or configuration.
2. Extend the event vocabulary and build mailbox/presence projections. Keep kernel jobs and
   runs canonical; room events carry references and safe summaries.
3. Add structured `Delegation`, `ApprovalRequest` and expiring `CapabilityGrant`; make every
   delegated child an ordinary job with a bounded grant set.
4. Add enforceable memory scope/visibility filters before agents receive private/shared
   context. The current memory store has a project field but no general scope ACL.
5. Replace the process-local-only resource picture with durable lease records plus TTL,
   heartbeat and restart reconciliation; retain in-process semaphores for live exclusion.
6. Add workspace leases/templates and approved persistent volumes above the existing
   workspace registry and OpenShell/Docker execution providers.
7. Expand `AgentLoop` carefully: keep a small required start/step contract and advertise
   optional interrupt/checkpoint/resume/skill-extraction capabilities rather than forcing a
   fat interface every harness must fake.
8. Trial Hermes through NemoClaw/OpenShell. Translate Hermes cron, subagents, memory and
   skills; never let it schedule/retry/approve the same work independently.
9. Add immutable workflow definitions/instances, then render task, handoff, approval,
   artifact and verification cards in native rooms.
10. Add A2A/agentgateway ingress and optional Kitesurf only after the internal contracts and
    zero-authority mapping tests exist.

### Split-brain invariant

For every job, identity, schedule, memory item, approval and workspace there is exactly one
authoritative owner. A subordinate harness may cache or mirror state, but the kernel issues
the `run_id`, grants, leases and final state transition. If a harness cannot surrender an
overlapping control point, run it as a fully subordinate sandbox and treat all returned state
as untrusted evidence.

## Research wave 4 — deterministic automation and the primary desktop

Consolidated on 2026-08-19 after inspecting the current controller, execution, dependency and
web-UI code and verifying the proposed upstreams from their primary sources. The detailed
selected design is [docs/AUTOMATION.md](../docs/AUTOMATION.md).

### Truth correction

“No automation code exists” is false for this repository. The ordered computer-control
interface, kernel policy, OpenShell/Docker execution broker, workspace allowlist, durable
jobs/events/checkpoints, verification boundaries and basic local web UI are implemented.

The honest statement is: **the automation substrate exists, but no concrete browser,
Windows UIA or vision controller is registered, and the rich desktop experience is not
built.** Playwright is present only as an optional locked dependency.

### Decisions and corrections

| Proposal | Decision | Correction / boundary |
| --- | --- | --- |
| Direct Playwright | `adopted` canonical browser control | Use typed kernel operations and a direct worker for deterministic state, traces, downloads and verification. |
| Official [Playwright MCP](https://github.com/microsoft/playwright-mcp) | `trial` compatibility adapter | Upstream explicitly says it is not a security boundary. It cannot bypass kernel grants or become the internal browser contract. |
| Local dedicated Chromium | `adopted` required backend | Never automate the user's daily browser profile. Profile state is sensitive bearer-token material and requires scope, protection, expiry and a session lease. |
| [Cloudflare Kitesurf](https://developers.cloudflare.com/browser-run/kitesurf/) | `trial`, external/public/stateless only | It is a remote beta engine accessible over CDP, not self-hosted local infrastructure. Vendor CPU/RAM results are priors; local workload benchmarks decide. |
| [Browser Use](https://github.com/browser-use/browser-use) | `trial` exploratory strategy | Its agent loop must be subordinate. A successful trajectory becomes an untrusted `SkillCandidate`, then replay/evaluation—not automatic durable automation. |
| [FlaUI](https://github.com/FlaUI/FlaUI) UIA3→UIA2 | `adopted` Windows structured-control choice | Run through a typed host broker; UIA3 is preferred while UIA2 handles compatibility cases. |
| Separate low-privilege service/account | `superseded` by per-user broker | A normal Windows service is isolated in session 0 and cannot control the interactive desktop. Start an unelevated broker in the active user session with a named-pipe logon-SID DACL. Elevated UI is denied initially. |
| [UI-TARS](https://github.com/bytedance/UI-TARS) | `trial` model/SDK only | Do not adopt UI-TARS Desktop as the product or authority; its current Windows story is not a sufficiently stable foundation. Model proposes one action, broker executes after policy. |
| MCP as hierarchy level | `declined` | MCP is a transport/tool boundary that can expose several hierarchy levels. It does not rank above or below Playwright and grants no authority. |
| Buzz-derived Tauri desktop | `adopted` direction, extraction spike first | Desktop becomes the primary human product; existing web/CLI remain recovery/operator surfaces. Reuse only components that can shed Nostr/relay types cleanly. |
| Buzz protocol bridge | `declined` as final architecture | It produces two event/identity/job systems. Acceptable only as a disposable prototype if explicitly chosen later. |

### Windows broker hardening

The broker is an unelevated process in the active interactive session, not a session-0
service. It accepts a closed command schema over a local named pipe protected by an explicit
logon-SID DACL; Windows defaults are insufficient because default pipe descriptors may grant
broader read access than intended. Each command binds to a run, expiring grant, nonce,
process/window, action, deadline and post-condition. No arbitrary code, shell, raw credential
or unbounded coordinate loop crosses this boundary.

### Desktop reuse boundary

[Block Buzz](https://github.com/block/buzz) verifies the value of a Tauri/React desktop,
rooms, threads, reactions, canvas, diff/media surfaces, presence and E2E tests. It also
confirms the coupling risk: its desktop is part of a relay/Nostr/auth/workflow ecosystem and
its current source is moving rapidly.

The next action is therefore a pinned-source extraction matrix, not a fork commitment. For
each candidate component we measure Nostr/Buzz imports, Tauri command dependencies, state
ownership, accessibility, test portability, bundle cost and replacement effort. Clean
presentation components may be adapted with Apache notices; coupled features are rebuilt
against typed kernel view models. The kernel backend remains singular.

### Automation implementation order

1. Typed browser action/result contract and conformance tests.
2. Read-only ephemeral local Chromium vertical slice.
3. Deterministic writes/downloads/uploads, trace and post-condition verification.
4. OS-protected profiles, single-writer session leases and human login/takeover.
5. Playwright MCP compatibility and Kitesurf public/stateless benchmark.
6. Windows broker inspect-only slice, then bounded FlaUI actions.
7. One-action raw input/capture and UI-TARS/Browser Use benchmarks.
8. Thin authenticated Tauri kernel client plus Buzz extraction spike; grow by real backend
   vertical slices rather than mock control-center screens.

## Final pre-build audit — 2026-08-19

### Verdict

No new architectural plane, framework category or model family is required before work
starts. The design is sufficiently complete. The remaining gaps are concrete reliability,
security and reproducibility work in the kernel spine; they must not trigger another round of
framework collecting.

The repository passed its current source checks: 19 tests, Ruff, Python byte-compilation,
PowerShell parsing, Bash parsing, YAML parsing, UI JavaScript syntax, registry validation and
Markdown-link validation. The local source audits resolved all 13 core and 25 workstation
model sources with no failures (approximately 110.89 GB and 289.51 GB of checkpoint
downloads respectively). WSL2 sees the intended RTX 5070 Ti Laptop GPU with 12,227 MiB VRAM
and sufficient WSL-native storage.

### Gates discovered by the audit

| Gate | Evidence | Required correction |
| --- | --- | --- |
| Recoverable source baseline | The workspace is not a Git repository. | Initialize version control, expand ignores for generated runtimes/caches, and create a reviewed baseline before edits or large installs. |
| Reproducible supply chain | Hugging Face downloads resolve immutable revisions, but runtime/specialist Git repositories pull their current branch and many packages/install scripts are mutable; the resulting commit is recorded only after installation. SearXNG also uses a floating image tag. | Add an immutable source manifest with Git commits, package/lock inputs, container digest and installer checksum/signature verification; install exactly those versions and preserve rollback metadata. |
| Service ownership and ports | Startup treats any listening TCP port as the intended service. Port 8080 is currently occupied by another local model router. Stop logic also identifies processes by broad command patterns. | Make ports configurable, verify a service identity/version/instance token before reuse, record owned PIDs/instances and stop only owned services. Never overwrite or kill the existing router implicitly. |
| Local API authority | The OpenAPI document has no authentication scheme and every mutation endpoint is unauthenticated. Human identity is supplied as an `actor_id`; identity/room creation uses upsert-like behavior and membership changes have no caller authorization. | Add an OS-protected installation secret and short-lived session, Host/Origin checks, typed authorization and non-upserting public creation semantics before the API becomes a privileged desktop/control boundary. |
| Schema evolution | SQLite stores create tables ad hoc and have no schema version, migration journal, backup/restore gate or downgrade policy. | Introduce one migration runner and tested backup/restore before adding `AgentProfile`, `Run`, grants, leases or memory ACLs. |
| Durable execution truth | Jobs are journaled, but restart marks queued/running work `interrupted`; checkpoints are stored but no runner reconstructs or resumes work. Job submission also creates an unbounded in-process task per request. | Correct the documentation, add `Run` attempts, idempotency, a bounded durable dispatcher, retry/resume policy, cancellation races, leases/heartbeats and forced-restart tests. |
| Resource/config consistency | The scheduler reserves 1,600 MiB while the llama.cpp preset uses a 1,800 MiB fit target; API bodies/queues have no global quota or backpressure. | Use one resource-policy source and add request, queue, time, disk and concurrency budgets suitable for 32 GB host RAM. |
| Boundary test coverage | Existing tests exercise registries, policy, stores, staging and collaboration, but not authenticated HTTP mutations, migrations, recovery, queue pressure, service identity or installer reproducibility. | Add these as release gates before agent harness, browser, remote-provider or desktop work. |

Missing model/runtime locks, GGUFs, specialist workers and most services are expected
pre-install state, not architecture defects. Windows Python, WSL pnpm and OpenShell can be
provisioned by the installer after its mutable-source behavior is corrected.

### Corrected first work order

1. Create the recoverable source baseline and immutable install/source manifest.
2. Add service identity, configurable ports and owned-process lifecycle; preserve the existing
   router on port 8080.
3. Add schema migrations plus backup/restore tests.
4. Add authenticated local sessions and endpoint authorization.
5. Introduce `Run` beneath `Job` with a bounded durable dispatcher and honest
   interrupted/retry/resume semantics.
6. Run a minimal physical core build and record real inference, resource and recovery
   baselines before installing the workstation model set.
7. Continue with persistent agency, scoped memory, automation and desktop vertical slices in
   the previously recorded order.

## Research wave 5 — the open-source mandate, hybrid MoE, and the experience plane

Consolidated on **2026-08-21**, two days after the initial ledger. Two things changed: the
project acquired an explicit open-source-only mission (baseline invariant 8), and the model
landscape moved underneath the manifest. This wave records both, plus the first real
inspection of the experience-layer upstreams.

### Truth correction

The 2026-08-19 ledger is not wrong, but it is already **incomplete in one load-bearing way**:
it evaluated harnesses, memory, sandboxes and collaboration exhaustively, and evaluated the
*model architecture question* only through the Qwen family. In the intervening days the
relevant axis turned out not to be "which vendor" but "**dense versus hybrid-MoE with low
active parameter count**", which is the variable that actually decides whether a quality-tier
model is usable on 12 GB of VRAM. See `docs/FIXES.md` F-005 and F-012.

Second correction: `docs/SOURCES.md` and this ledger both treated licensing as a per-model
metadata field. Under invariant 8 it is a **gate applied before capability is considered**,
and it applies to runtimes and applications as well as weights.

### The licensing gate, stated concretely

| Tier | Meaning | Status |
| --- | --- | --- |
| OSI-approved (Apache-2.0, MIT, BSD, CC-BY) | Unrestricted for our purposes and for downstream community use. | `adopted` without further review |
| Open weights, non-OSI vendor license (NVIDIA Open Model License, Llama Community, Gemma) | Redistributable and commercially usable, but carries vendor-specific terms. | requires explicit review and a recorded decision **per model** |
| Non-commercial / research-only | Usable by an individual, not shippable as a community default. | `declined` for default profiles; opt-in only, clearly labelled |
| Closed source, hosted API, subscription-gated | — | `declined` unconditionally |

**NVIDIA Open Model License:** `primary-verified` that it grants a perpetual, worldwide,
non-exclusive, royalty-free licence including derivative models and makes no ownership claim
on outputs. Also `primary-verified` that it is **not OSI-approved**, and that Article 8 places
an indemnification obligation on the licensee for third-party claims arising from use of the
model, derivatives or outputs. That indemnity is unusual relative to OSI licences and is the
specific clause to resolve before shipping Nemotron weights in a default profile.

### Model layer — hybrid MoE is the architecture that fits this machine

| Finding | Evidence | Decision | Reason and boundary |
| --- | --- | --- | --- |
| [Nemotron 3.5 Lightning 30B-A3B](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16) and [Nemotron 3 Nano 30B-A3B](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16) | `primary-verified` — `config.json` read directly: `model_type: nemotron_h`, 52 layers, `n_routed_experts: 128`, `num_experts_per_tok: 6`, `hybrid_override_pattern` with ~6 attention layers | high-priority `trial` as deep-brain candidate, **pending licence review** | ~3B active of 30B total. A dense 27B reads its whole weight set per token; this reads a fraction. On a 12 GB card that is the difference between offload being fatal and offload being cheap. |
| `llama.cpp` already supports it | `primary-verified` — `LLM_ARCH_NEMOTRON_H_MOE` in `src/llama-arch.cpp`, and `-ncmoe` / `--n-cpu-moe` / `--spec-draft-n-cpu-moe` in `common/arg.cpp`, **at our already-pinned commit `dc72703`** | `adopted` capability | No runtime change, no new pin, no new build. The expert-offload flag we need is already compiled into the router we already selected. |
| Official [`ggml-org` GGUF](https://huggingface.co/ggml-org/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF) | `primary-verified` — Q4_0 at 18.90 GB plus a 1.16 GB MTP draft head | `trial` artifact | First-party GGUF from the llama.cpp org, with the speculative-decoding sidecar in the same repo. |
| 1B-class retrieval models | `primary-verified` — `nvidia/Nemotron-3-Embed-1B-BF16` 2.30 GB; `nvidia/llama-nemotron-rerank-vl-1b-v2-fp8` 2.40 GB and vision-language capable | high-priority `trial`, **pending licence review** | Replaces ~59 GB of 8B embed/rerank models with ~5 GB, and collapses the separate text and multimodal rerank slots into one model. See F-013. |
| `nvidia/parakeet-tdt-0.6b-v3` | `primary-verified`, **CC-BY-4.0** | `trial` ASR candidate | Notable because it is the one high-traffic NVIDIA speech model on a genuinely OSI-compatible licence, so it passes the gate without review. |
| Speculative-decoding sidecar formats | `primary-verified` — `llama.cpp` `spec-type` accepts `draft-mtp`, `draft-eagle3`, `draft-dflash`, `draft-dspark`; NVIDIA publishes `-DSpark` and `-DFlash` variants | `watch` | Broadens the draft-model options beyond MTP. Relevant to F-005: speculative decoding is precisely the technique that helps a memory-bound generation loop. |

**The generalisable lesson, independent of vendor:** on 12 GB VRAM, prefer *sparse-active
hybrid* architectures (Mamba/linear attention + MoE) over dense models of similar total size.
Total parameters set disk and RAM cost; **active** parameters set token latency. The manifest
currently optimises the wrong one. If the Nemotron licence review fails, this lesson stands and
we re-scan for an Apache-2.0 or MIT model with the same shape rather than reverting to dense.

### Experience layer — the part we said we wanted and had not inspected

| Upstream | Evidence | Decision | Boundary and correction |
| --- | --- | --- | --- |
| [block/buzz](https://github.com/block/buzz) | `primary-verified` — README inspected 2026-08-21 | `reference` for interaction design; **`declined` as backend**, confirming `D-010` | Tauri + React desktop, Rust `buzz-relay` on Axum — but the runtime is **Nostr (NIP-01/42/34) over PostgreSQL + Redis + S3/MinIO**. Agents are "members, not bots" with their own keys and audit trail, which is a genuinely good idea we should adopt *semantically*. Importing the stack would give us a second identity system, a second event log and three new services. The extraction spike remains the correct move. |
| [CopilotKit/openbot](https://github.com/CopilotKit/openbot) | `primary-verified` — README inspected 2026-08-21 | `reference` only; **`declined` as a dependency** under invariant 8 | Its governance design is close to ours and worth studying: a gateway that resolves the target, evaluates **CEL-based policy**, "writes audit entries first, then executes or refuses with rule explanations", and gives each bot a container with its own browser profile, its own `/workspace` volume and optional gVisor. That is `CapabilityGrant` + `WorkspaceLease` + verification, independently arrived at. **Disqualified as a dependency:** it requires a CopilotKit Intelligence project (hosted) for durable threads, and ships no local model support — only OpenAI/Anthropic/Google credentials. MIT, alpha. |
| [AG-UI protocol](https://github.com/ag-ui-protocol/ag-ui) | `primary-verified` — README inspected 2026-08-21 | `trial` at the experience seam | MIT, ~16 event types, transport-agnostic (SSE/WebSocket/webhook), SDKs in 8 languages. It standardises *agent → frontend* streaming, state sync and human-in-the-loop — the seam between our kernel and any UI. Adopting it would let a community member swap our desktop for their own without touching the kernel. It is a **rendering/streaming contract, not an authority boundary**; the same rule we applied to MCP applies here. |
| [block/goose](https://github.com/block/goose) | `primary-verified` — README inspected 2026-08-21 | high-priority `trial` as the first `AgentLoop` adapter | Apache-2.0, Rust, **governed by the Agentic AI Foundation at the Linux Foundation** since 2026-04-07. Desktop + CLI + API, 70+ MCP extensions, explicit Ollama/local-provider support. Vendor-neutral governance materially lowers the capture risk that `D-001` exists to prevent — this is the harness least likely to be pulled out from under a community project. Same Block lineage as Buzz, and Buzz ships a `buzz-acp` harness bridge, so the two compose. |
| OpenCode, OpenHands, Cline, Aider | `unverified` at primary source in this wave — landscape reporting only | `watch`, candidates for the harness tournament | Reported as the most-starred open coding agent (OpenCode), the strongest sandboxed/CI runner (OpenHands), and Git-native editing (Aider), all with local-model support. **Do not treat these characterisations as verified.** They enter the tournament in experiment 11; they do not enter the architecture. |

### Memory layer — recheck

Reported LongMemEval standings put Hindsight ≈ 91%, Zep ≈ 64%, Mem0 ≈ 49%, with a product
called OMEGA claiming ≈ 95% fully-local. **All of these are `unverified` here**: the numbers
come from vendor and aggregator comparison pages, several of which are selling one of the
entrants. `D-002` already requires shadow-mode evaluation against our own data before any
memory provider is promoted, and this wave changes nothing about that — it only adds
[cognee](https://github.com/topoteretes/cognee) (Apache-2.0, self-hosted, no paid tier) and
[Letta](https://github.com/letta-ai/letta) to the shadow-mode candidate list alongside
Hindsight. The relevant near-term work is F-008, which is ours, not a vendor's.

### Execution layer — recheck

`libkrun` is confirmed as the embeddable KVM library behind microsandbox and Podman's VM mode,
which gives the `D-004` BoxLite/micro-VM trial a second implementation path if WSL2 KVM proves
unreliable. gVisor remains the middle tier between hardened containers and true micro-VMs. No
change to the OpenShell-preferred, Docker-fallback decision.

### What changed because of wave 5

1. **Licence became a gate, not metadata** (baseline invariant 8). Applies to weights,
   runtimes and applications alike.
2. **The deep-brain question reopened.** Not "Qwen versus someone else" but "dense versus
   sparse-active hybrid". `D-012`.
3. **The retrieval stack is the biggest resource win available**, and it is available now.
   `D-013`.
4. **The experience plane gained a protocol seam.** AG-UI decouples our kernel from any
   particular UI, which is what makes "customise it for your hardware, the rest stays the
   same" actually true for a community. `D-014`.
5. **Goose is the first harness worth adapting**, primarily because of who governs it.
   `D-015`.
6. **OpenBot validated our governance design and failed our licence gate** — the most useful
   possible outcome for a `reference`.

## Decision records

### D-001 — The sovereign kernel, not DeepSeek Harness, is the foundation

- **Date:** 2026-08-19
- **Status:** `adopted`; supersedes the earlier base-harness wording.
- **Reason:** No inspected harness is best at policy, isolation, memory, collaboration,
  verification, and project durability simultaneously. Harness churn must not migrate our
  root of trust.
- **Consequence:** DeepSeek Harness and competitors implement `AgentLoop`; the kernel owns
  their job envelope, workspace capability, secrets, resource lease, and verifier.
- **Revisit trigger:** only if a mature upstream exposes all required boundaries without
  claiming root authority and wins our recovery/security suite.

### D-002 — Canonical memory remains local and provider-independent

- **Date:** 2026-08-19
- **Status:** `adopted`.
- **Reason:** Hindsight's derived facts, temporal retrieval, entity resolution, and reflection
  are materially richer than plain vector chat history, but derived memory can be wrong and
  an upstream schema can change.
- **Consequence:** Hindsight starts as a shadow index. Canonical events, decisions,
  provenance, sensitivity, deletion, and supersession remain native. Promotion is per memory
  operation, not an all-or-nothing replacement.

### D-003 — Verified state is the bridge across fresh agent contexts

- **Date:** 2026-08-19
- **Status:** `adopted`, implementation extension pending.
- **Reason:** Long tasks fail when one expanding context is planner, executor, narrator, and
  judge. LongHorizon and GSD independently reinforce fresh execution contexts plus durable,
  externally checked progress.
- **Consequence:** A manager proposes the next bounded unit, an executor acts, and an auditor
  checks artifacts/post-conditions. Only the verification receipt advances trusted state.

### D-004 — OpenShell stays preferred; BoxLite is a complementary micro-VM trial

- **Date:** 2026-08-19
- **Status:** `adopted` + `trial`.
- **Reason:** OpenShell offers policy and credential-aware control; BoxLite offers appealing
  persistent hardware isolation. Neither is mature enough to be the sole recoverability path.
- **Consequence:** One `ExecutionProvider` contract, explicit capabilities, Docker fallback,
  and provider-specific conformance tests. Persistence is granted per workspace, never by
  default.

### D-005 — Add a protocol-edge seam before adding a permanent gateway

- **Date:** 2026-08-19
- **Status:** `adopted` seam; agentgateway `trial`.
- **Reason:** MCP/A2A/LLM traffic benefits from centralized identity, observability, quotas,
  and failover, but an always-on gateway is unnecessary overhead for a single direct local
  connection.
- **Consequence:** Direct mode remains possible. Agentgateway begins observe-only and must
  fail closed for protected routes while leaving fully local fallback usable.

### D-006 — Borrow durable scopes; do not import a second collaboration product

- **Date:** 2026-08-19
- **Status:** `adopted` pattern.
- **Reason:** QM's per-user/per-room computers and Buzz's shared rooms are strong designs, but
  their complete applications duplicate our current single-user native collaboration plane.
- **Consequence:** Every future user, room, project, or workspace gets an explicit scope ID
  across memory, files, permissions, secrets, schedules, and execution. Scope does not imply
  authority.

### D-007 — Remote capacity is optional escalation, never silent substitution

- **Date:** 2026-08-19
- **Status:** `adopted` policy; provider implementation pending.
- **Reason:** Limited free APIs provide capabilities and model sizes this workstation cannot
  host, while quotas, privacy terms, and availability can change without notice.
- **Consequence:** Routing records consent/data class/provider/model/cost. Sensitive tasks
  stay local unless an explicit policy allows otherwise. Exhausted quota degrades honestly.

### D-008 — Persistent agents are logical profiles; computation belongs to runs

- **Date:** 2026-08-19
- **Status:** `adopted`, implementation pending.
- **Reason:** Current room identities provide personalities and routes, but cannot safely
  express durable roles, scoped memory, delegation, budgets, attempts, leases, schedules or
  evaluated evolution. Binding identity directly to a process/model would also waste this
  workstation's constrained resources.
- **Consequence:** Add the kernel-backed roster domain and distinguish `AgentProfile` →
  `Job` → `Run`. Models, loops, prompts, skills, grants, workspaces and resources are selected
  or leased per run. Idle agents are rows and event projections, not resident processes.
- **Safety boundary:** profiles declare preferences and ceilings; only kernel policy creates
  active grants. Collaboration identity references a profile and never grants execution.
- **Revisit trigger:** the names/schema may evolve during implementation, but the identity /
  requested outcome / execution attempt separation is invariant.

### D-009 — Deterministic automation is primary; model-guided control is a fallback

- **Date:** 2026-08-19
- **Status:** `adopted`, concrete providers pending.
- **Reason:** APIs, typed browser commands and UIA expose inspectable state and verifiable
  post-conditions at lower cost and risk than open-ended visual control.
- **Consequence:** direct Playwright controls local Chromium and optional Kitesurf; FlaUI runs
  through an interactive-session Windows broker; Browser Use and UI-TARS produce bounded,
  untrusted proposals. MCP is compatibility transport, never permission.
- **Safety boundary:** isolated browser profiles, explicit data classification, per-run grants,
  one-action raw input, human takeover and state-based verification.

### D-010 — Desktop is the product; Buzz is an accelerator, not the backend

- **Date:** 2026-08-19
- **Status:** `adopted` direction; extraction spike pending.
- **Reason:** A persistent roster, jobs, approvals, memory, computers and audit need a coherent
  visual home. The CLI and current small web UI are valuable operator/recovery surfaces but
  are not the intended daily product.
- **Consequence:** build a sovereign Tauri desktop over a typed authenticated `KernelClient`.
  Evaluate pinned Buzz components for selective adaptation with provenance/notices; exclude
  its relay, Nostr identity, storage, workflow, permissions, jobs and agent authority.
- **Revisit trigger:** if extraction is more expensive than rebuilding, retain the interaction
  design and create native components; do not accept a second backend to save UI effort.

### D-011 — Stabilize the kernel spine before the heavyweight bootstrap

- **Date:** 2026-08-19
- **Status:** `adopted` after the final pre-build audit.
- **Reason:** A 290 GB install is the wrong first irreversible experiment while upstream
  runtime inputs are mutable, source has no version-control baseline and the local API is
  unauthenticated.
- **Amended 2026-08-21:** The Git baseline and immutable runtime pins now exist, and the
  port-collision clause is **resolved rather than withdrawn**. The finding was correct: a
  separate local model router does listen on `127.0.0.1:8080`. Commit `b1a5b29` moved our
  llama.cpp router to `18080` and added a service-identity probe, so the foreign router is
  left alone. An earlier attempt to retire this clause on 2026-08-21 claimed the port was
  free; that claim came from a Windows-host-only scan, which cannot see WSL2-bound sockets
  (`docs/FIXES.md` F-001, F-019). The remaining blockers are local authentication, migrations
  and bounded job/run recovery.
- **Consequence:** first work is the small, testable baseline/pinning/service/auth/migration/job
  slice above. Then run the core physical build and measure it before expanding to the
  workstation profile. Existing local services are preserved unless explicitly adopted.
- **Revisit trigger:** none for the invariant; exact mechanisms may change, but heavy installs
  and privileged surfaces always require provenance, ownership, recovery and authentication.

### D-012 — Active parameters, not total parameters, decide the deep brain

- **Date:** 2026-08-21
- **Status:** `adopted` principle; specific model `trial` pending licence review.
- **Reason:** Token generation on this machine is memory-bandwidth bound, not compute bound.
  A dense 27B at Q4 must read ~16 GB per token and cannot fit 12 GB, so ~40% streams from
  host RAM at roughly an eighth of VRAM bandwidth. A 30B-A3B hybrid MoE reads roughly 3B
  parameters' worth per token and keeps its few attention layers resident. Total parameters
  set disk and RAM cost; active parameters set latency. The manifest optimised the former.
- **Consequence:** The deep-brain slot is now contested. `Qwen3.8-27B UD-Q4_K_M` and
  `Nemotron-3.5-Lightning-30B-A3B Q4_0 + MTP under -ncmoe` are benchmarked head to head on
  identical tasks before either is treated as final. Quantisation variants
  (`UD-Q4_K_S`, `UD-IQ4_XS`) are part of the same sweep, since halving CPU offload is a
  cheaper lever than changing models.
- **Safety boundary:** Nemotron ships under a non-OSI vendor licence with an indemnification
  clause. A winning benchmark does not authorise adoption; the licence review under invariant
  8 is a separate and blocking gate.
- **Revisit trigger:** If the licence review fails, the principle survives the model — re-scan
  for a permissively licensed sparse-active hybrid rather than defaulting back to dense.
- **Measured 2026-08-21 (fast-brain reference):** `docs/FIXES.md` F-005. `Qwen3.8-27B
  UD-Q4_K_M` generates at **6.36 tok/s** (37/64 layers resident, 9398 MiB peak) — below the
  10 tok/s interactive viability gate. `Qwen3.5-9B Q6_K`, converted locally the same
  session, generates at **49.57 tok/s**, fully resident (6962 MiB peak), no licence review
  needed.
- **Measured 2026-08-21 (Nemotron challenger):** `docs/FIXES.md` F-012. Downloaded and
  SHA-256-verified against a locked revision, then swept `-ncmoe` on `llama-bench`.
  **At `@ncmoe32`: 52.79 tok/s at 9438 MiB peak VRAM — 8.3x the dense 27B's generation
  speed at essentially the same VRAM footprint (9438 vs 9398 MiB), from a larger model with
  a presumptively higher quality ceiling, and slightly ahead of even the 9B fast brain.**
  This is the strongest available confirmation of the principle on real hardware. It does
  **not** settle the deep-brain question by itself: quality on real coding/planning tasks is
  unmeasured for all three candidates, and the NVIDIA Open Model License's Article 8
  indemnification clause remains an unresolved, blocking gate under invariant 8 — a winning
  benchmark does not authorise adoption. Prefill throughput trades off sharply against
  `-ncmoe` (2633.84 tok/s at `@ncmoe0` versus ~520-625 tok/s once experts are forced to
  CPU), so even the operating point within the Nemotron family needs a mixed-workload
  benchmark, not a single number, before being treated as a default.

### D-013 — Retrieval is the highest-frequency path and must be sized accordingly

- **Date:** 2026-08-21
- **Status:** `adopted` principle; specific models `trial` pending licence review.
- **Reason:** The manifest spends ~59 GB on four 8B embed/rerank models, each of which must
  contend for the same 12 GB of VRAM as the brain it is serving. Retrieval runs on nearly
  every turn; the brain does not. Verified 1B-class alternatives are ~2.3 GB each, and the
  vision-language reranker covers the text and multimodal slots with one model.
- **Consequence:** Benchmark 1B-class embed/rerank against the 8B incumbents on a local
  retrieval set drawn from our own corpus. Leaderboard position is a prior, not evidence —
  the same rule that governs every other promotion here.
- **Safety boundary:** Same licence gate as `D-012`. If it fails, re-scan for permissively
  licensed 1B-class retrieval models; the sizing lesson is vendor-independent.
- **Revisit trigger:** Measured recall or rerank quality loss large enough to change task
  outcomes, not merely benchmark deltas.

### D-014 — Adopt a protocol seam between the kernel and any user interface

- **Date:** 2026-08-21
- **Status:** `adopted` seam; AG-UI `trial` as the implementation.
- **Reason:** The mission is a system other people run on their own hardware and adapt.
  That only works if the UI is genuinely replaceable, and it is only genuinely replaceable if
  the contract between kernel and frontend is a published protocol rather than our internal
  types. AG-UI is MIT, transport-agnostic, has multi-language SDKs, and standardises exactly
  the hard parts: streaming, state synchronisation and human-in-the-loop interrupts.
- **Consequence:** Kernel views and commands are exposed over a typed seam that AG-UI can be
  spoken across. Our Tauri desktop becomes one client among possible others rather than the
  privileged one. A community member can put their own frontend on the same kernel.
- **Safety boundary:** AG-UI is a **rendering and streaming contract, not an authority
  boundary** — the identical rule already applied to MCP in `D-009`. Nothing arriving over it
  authorises a mutation. Approvals resolve against kernel records, never against a UI event.
- **Revisit trigger:** If AG-UI's event model cannot express approvals, delegations and
  verification receipts without lossy translation, keep the seam and replace the protocol.

### D-015 — Goose is the first agent-loop adapter, chosen on governance as much as capability

- **Date:** 2026-08-19; **amended 2026-08-21** (`docs/FIXES.md` F-027)
- **Status:** `trial` as an external `AgentLoop`. **Superseded as "the first concrete
  `AgentLoop`"** by a native reference implementation — see amendment below.
- **Reason:** `D-001` exists to stop harness churn from moving our root of trust. The strongest
  available defence against that is a harness that no single vendor can withdraw or relicense.
  Goose is Apache-2.0 and governed by the Agentic AI Foundation at the Linux Foundation, runs
  local models, speaks MCP, and shares lineage with Buzz — whose ACP bridge already
  demonstrates the composition we want.
- **Consequence:** Implement `AgentLoop` against Goose first, and use that work to discover
  the *minimum* required loop contract. Do not widen the interface to accommodate one harness;
  advertise optional interrupt/checkpoint/resume capabilities instead, per the wave-3 sequence.
- **Safety boundary:** Subordinate like every other loop. The kernel issues the `run_id`,
  grants, leases and final state transition. Anything Goose reports is untrusted evidence
  until a verifier says otherwise.
- **Amended 2026-08-21:** Goose requires a Rust/Cargo toolchain, absent on the target
  workstation; building it from source was a multi-hour, failure-prone detour disproportionate
  to what "one working agent loop" needs right now. `agents/native_loop.py`
  (`NativeAgentLoop`) is now the first working `AgentLoop`: a deterministic JSON tool-call
  protocol, policy-gated tool execution reusing the existing `ExecutionBroker`/
  `WorkspaceRegistry`, and an append-only event per step. This is a better fit for `D-001`
  than the original plan, not a compromise of it — a self-authored, fully auditable
  reference loop is the correct thing to compare external harnesses against, including Goose,
  in the harness tournament (experiment 11), rather than adopting the first external harness
  as the only thing that can drive the kernel.
- **Revisit trigger:** The harness tournament (experiment 11) may produce a better performer
  than the native loop, Goose included, once a Rust toolchain is available to build it.
  Governance neutrality is a tiebreaker, not an exemption from measurement.

### D-016 — Nemotron accepted for personal use only, behind a new local-overlay seam

- **Date:** 2026-08-21
- **Status:** `adopted`. Personal-machine scope only; explicitly **not** extended to
  `configs/models.yaml` or any shared install profile.
- **Reason:** `D-012`'s benchmark landed decisively: `Nemotron-3.5-Lightning-30B-A3B`
  `@ncmoe32` measures 52.79 tok/s at 9438 MiB peak VRAM — 8.3x the dense Qwen3.8-27B
  incumbent's 6.36 tok/s at essentially the same VRAM footprint (`docs/FIXES.md` F-012).
  The NVIDIA Open Model License remains non-OSI-approved with an Article 8 indemnification
  clause that invariant 8 treats as a blocking gate for anything shipped to the community.
  Presented with the throughput result and the specific clause, the user chose: accept the
  license for their own personal/local use, never as a community default.
- **Consequence:** This is the first real use of a distinction the project needed but had
  not yet built — a model an operator personally reviews and accepts is not the same thing
  as a model this project recommends to everyone. `ConfigBundle` gained
  `configs/models.local.yaml`: a gitignored overlay, documented and templated in
  `configs/models.local.yaml.example`, merged into the registry after `models.yaml` loads.
  A local model id can shadow a manifest one; no install profile can ever reference a
  local-only id, so a profile-based install can never pull one in regardless of what any
  one operator has personally accepted. `docs/FIXES.md` F-025.
- **What was actually wired, same session, not just decided:** `state/llama-models.ini`
  gained a `[nemotron35-lightning-30b-a3b]` preset section (`n-cpu-moe = 32`, the
  best-measured sweep point); `configs/models.local.yaml` carries the `ModelSpec` with
  `status: candidate` (routes only under `mode: deep`) and a `license_note` recording this
  decision in full; a live `POST /models/load` → `POST /v1/chat/completions` →
  `POST /models/unload` round trip through the actual router confirmed correct end-to-end
  routing, distinct from and not to be confused with the properly warmed-up
  `llama-bench` throughput measurement.
- **Safety boundary:** `status: candidate` is not decorative — it is the mechanism that
  keeps an unevaluated personal model from silently outranking the evaluated manifest
  incumbent in ordinary routing. Quality on real coding/planning tasks remains completely
  unmeasured; nothing here treats throughput as a proxy for it.
- **Revisit trigger:** A real quality evaluation could change the routing weight, but never
  the license scope — that requires either a new decision by the user or a different
  license entirely. If invariant 8 is ever loosened to accept indemnification clauses for
  shared defaults, that is itself a decision this ledger would need to record, not an
  automatic consequence of this one.

### D-017 — Obliterated Qwen3.8-27B accepted for personal use only, on verified provenance

- **Date:** 2026-08-21
- **Status:** `adopted`. Personal-machine scope only; explicitly **not** extended to
  `configs/models.yaml` or any shared install profile. Same pattern as `D-016`.
- **Reason:** `docs/FIXES.md` F-022 opened as `unverified` — two GGUF files with no
  discoverable source. A web search plus direct HuggingFace/GitHub API checks resolved
  this to `primary-verified`: `OBLITERATUS/Qwen3.8-27B-OBLITERATED`, Apache-2.0, base model
  exactly our own adopted Qwen3.8-27B, filenames matching exactly, author real and public.
  Unlike Nemotron there is no non-OSI licence or indemnification risk — the remaining
  question was purely fit, not law: the model card states 0.24% refusal on an 842-prompt
  corpus and explicitly names attack-chain/jailbreak-generation among its target
  capabilities. Presented with the verified facts, the user chose personal use only.
- **Consequence:** Reuses the `D-016` mechanism exactly — `configs/models.local.yaml`,
  `status: candidate` (routes only under `mode: deep`). Given a **distinct id**
  (`qwen38-27b-obliterated`) rather than shadowing the manifest's `qwen38-27b`: shadowing
  the trusted incumbent's id would make every route currently resolving to stock Qwen3.8-27B
  silently start returning different weights with no distinguishing marker, which is a
  silent default swap, not an opt-in personal model. `D-008`'s safety boundaries and
  invariant 8 both rule that out regardless of licence cleanliness.
- **Safety boundary:** The kernel's own security model does not depend on model alignment
  for authority, execution, or credential access (`docs/SECURITY.md`) — this decision
  affects content-level chat/completion output only, never what the kernel will let any
  model *do*. `status: candidate` keeps it from ever winning an ordinary routing decision
  against the evaluated incumbent.
- **Revisit trigger:** Independent reproduction of the vendor's own MMLU/refusal-rate claims
  would upgrade the evidence label from `vendor-claim` to `independent-verified` for those
  specific numbers; it would not by itself change the personal-use-only scope, which is a
  values decision distinct from a quality measurement.

## Recommended experiment order

This order adds information without destabilizing the first physical build.

1. **Pre-build reliability spine.** Create the Git baseline; pin upstream/runtime inputs; add
   service identity/owned lifecycle, migrations/backups, authenticated local sessions and a
   bounded `Job`/`Run` dispatcher with restart tests.
2. **Core physical bootstrap and baseline tests.** Record real Qwen throughput, quality,
   VRAM/RAM, recovery and worker smoke results before installing the workstation profile.
3. **Persistent-agency foundation.** Add `AgentProfile`, event-derived mailbox and
   presence, then delegation/grant/approval contracts with schema migrations and restart tests.
4. **Scoped-memory enforcement.** Add scope/visibility ACLs before connecting private agent,
   team or room memory; then run the Hindsight shadow-memory trial on non-sensitive scopes.
5. **Long-horizon verified-state slice.** Add receipt-backed manager/executor/auditor job
   transitions and test forced interruption/restart.
6. **Local browser foundation.** Implement the typed direct-Playwright read-only slice, then
   deterministic actions, verification, profiles and human takeover on dedicated Chromium.
7. **Windows inspect-only broker.** Prove per-user session placement, pipe ACLs, replay
   resistance, process/window binding and UIA inspection before permitting mutation.
8. **Hermes subordinate-runtime trial.** Run it through NemoClaw/OpenShell after kernel run,
   grant, schedule and delegation ownership is enforceable.
9. **agentgateway observe-only trial.** Route a bounded MCP/A2A and remote-model test set through
   it; compare logs, latency, policy clarity, and outage behavior.
10. **BoxLite WSL2/KVM feasibility trial.** Run the execution conformance suite without GPU
   passthrough or secrets first.
11. **Harness tournament.** Replay the same coding tasks through Hermes, DeepSeek Harness,
   LongHorizon/GSD where appropriate, and Grok Build. Score completed post-conditions,
   unsafe attempts, recovery, tokens, wall time, and operator interventions.
12. **Workflow/browser interoperability.** Add the smallest immutable workflow DAG, A2A
   boundary mapping, Playwright MCP and optional Kitesurf public-web trial only after the
   internal contracts exist.
13. **Desktop vertical slices.** Build an authenticated Tauri `KernelClient`, perform the
   pinned Buzz extraction spike, then add real roster/job/approval/computer views.
14. **Remote provider pool.** Add one provider at a time only after data-routing policy and
   cost/quota accounting exist.

## Promotion scorecard

Every new model, harness, memory engine, gateway, or sandbox must answer:

| Dimension | Required evidence |
| --- | --- |
| Capability | Which task becomes possible or materially better? |
| Quality | Repeatable task set and post-condition success, not vibes. |
| Reliability | Restart, timeout, cancellation, corrupted-output, and dependency-failure tests. |
| Security | Least privilege, denied egress, secret non-disclosure, scope isolation, and audit reconstruction. |
| Resource fit | Peak VRAM/RAM/CPU/disk, cold/warm latency, background cost on this laptop. |
| Portability | Windows/WSL behavior and an exit path through our interface. |
| Governance | License, immutable revision, provenance, update process, and rollback. |
| Complexity | New services, stores, schedulers, credentials, and operator burden it adds. |

A component is promoted only when its gain exceeds its complexity and it leaves the system
recoverable when absent.

## Explicit non-decisions

The following are **not** authorized by this research:

- replacing the sovereign kernel with DeepSeek Harness, Omnigent, Eve, QM, GSD, or Grok Build;
- treating the roster, Hermes, A2A, Warp or a room UI as another source of kernel truth;
- installing every candidate before the existing workstation build is measured;
- giving reflective/self-modifying memory permission to alter policy, tools, or security;
- making Hindsight the only copy of memory;
- making agentgateway or any remote API mandatory for local operation;
- treating a persistent sandbox as permission to retain secrets indefinitely;
- sending private workspace content to free APIs because their monetary price is zero;
- promoting vendor benchmarks without local reproduction;
- assuming “open weights” means OSI open source, unrestricted use, or local fit.
- configuring unverified “Grok 4.6,” “Grok Bot,” or “OpenAI Presence” product dependencies.
- treating Playwright MCP, a browser profile, a desktop renderer or a named pipe as a security
  boundary by itself;
- running the Windows UI broker as a normal session-0 service or granting unrestricted
  elevated/raw-input control.

## Open questions

- Can WSL2 on this exact BIOS/host expose KVM reliably enough for BoxLite?
- Does OpenShell's current alpha build remain stable across sleep, reboot, WSL shutdown, and
  GPU-heavy local inference?
- Can Hindsight preserve our provenance, sensitivity, expiry, conflict, deletion, and
  supersession semantics without a lossy side channel?
- At our scale, does agentgateway's observability/security value exceed its latency and
  operational cost?
- Which agent-loop adapter completes the same verified coding tasks most reliably with local
  Qwen, and which needs a remote model?
- Should verification receipts be first-class signed kernel events or hashes anchored into
  the existing append-only event chain?
- When multi-user use becomes real, are native scoped computers sufficient or does QM earn a
  deployment-level trial?
- Which roster objects should share one SQLite database/transaction boundary, and which are
  append-only projections over the existing event store?
- What is the smallest `AgentLoop` required protocol that supports retries and verification
  without making every adapter emulate unsupported checkpoint/interrupt features?

## Primary source registry

Checked on 2026-08-19 unless noted otherwise:

- [NVIDIA/OpenShell](https://github.com/NVIDIA/OpenShell)
- [omnigent-ai/omnigent](https://github.com/omnigent-ai/omnigent)
- [vectorize-io/hindsight](https://github.com/vectorize-io/hindsight)
- [boxlite-ai/boxlite](https://github.com/boxlite-ai/boxlite)
- [AMAP-ML/LongHorizon-Harness](https://github.com/AMAP-ML/LongHorizon-Harness)
- [vercel/eve](https://github.com/vercel/eve)
- [agentgateway/agentgateway](https://github.com/agentgateway/agentgateway)
- [open-gsd/gsd-pi](https://github.com/open-gsd/gsd-pi)
- [yc-software/qm](https://github.com/yc-software/qm)
- [xai-org/grok-build](https://github.com/xai-org/grok-build)
- [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness)
- [PrimeIntellect-ai/prime-agent](https://github.com/PrimeIntellect-ai/prime-agent)
- [block/buzz](https://github.com/block/buzz)
- [perplexityai/numbat](https://github.com/perplexityai/numbat)
- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- [NVIDIA/NemoClaw](https://github.com/NVIDIA/NemoClaw)
- [a2aproject/A2A](https://github.com/a2aproject/A2A)
- [Cloudflare Kitesurf](https://developers.cloudflare.com/browser-run/kitesurf/)
- [Warp cloud software factory build guide](https://www.warp.dev/blog/software-factory-build-guide)
- [Microsoft Playwright](https://github.com/microsoft/playwright)
- [Microsoft Playwright MCP](https://github.com/microsoft/playwright-mcp)
- [FlaUI](https://github.com/FlaUI/FlaUI)
- [Browser Use](https://github.com/browser-use/browser-use)
- [ByteDance UI-TARS](https://github.com/bytedance/UI-TARS)
- [Microsoft named-pipe security](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-security-and-access-rights)
- [Microsoft UI Automation security](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview)
- [Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B)
- [Qwen/Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)

Added 2026-08-21 (wave 5):

- [nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16)
- [nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16)
- [ggml-org/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF](https://huggingface.co/ggml-org/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF)
- [nvidia/Nemotron-3-Embed-1B-BF16](https://huggingface.co/nvidia/Nemotron-3-Embed-1B-BF16)
- [nvidia/llama-nemotron-rerank-vl-1b-v2-fp8](https://huggingface.co/nvidia/llama-nemotron-rerank-vl-1b-v2-fp8)
- [nvidia/parakeet-tdt-0.6b-v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)
- [NVIDIA Open Model License Agreement](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/)
- [ag-ui-protocol/ag-ui](https://github.com/ag-ui-protocol/ag-ui)
- [block/goose](https://github.com/block/goose)
- [CopilotKit/openbot](https://github.com/CopilotKit/openbot)
- [topoteretes/cognee](https://github.com/topoteretes/cognee)
- [letta-ai/letta](https://github.com/letta-ai/letta)

## Change history

### 2026-08-21 — Wave 5: open-source mandate, hybrid MoE, experience plane

- Added baseline invariant 8: the system is open source end to end and is meant to be given
  away. Licence became a gate applied before capability, covering weights, runtimes and
  applications alike.
- Reopened the deep-brain decision on the dense-versus-sparse-active axis after verifying
  that `nemotron_h` hybrid MoE is already supported by our pinned llama.cpp commit, together
  with the `-ncmoe` expert-offload flag.
- Recorded the retrieval stack as the largest available resource win: ~59 GB of 8B embed and
  rerank models against ~5 GB of verified 1B-class alternatives.
- Inspected Buzz, OpenBot, AG-UI and Goose at primary source. Confirmed `D-010` (Buzz is a
  design reference, not a backend), declined OpenBot as a dependency under invariant 8 while
  adopting its decide-before/record-after gateway pattern as a reference, adopted a protocol
  seam between kernel and UI, and selected Goose as the first agent-loop adapter on
  governance grounds.
- Opened `docs/FIXES.md` as the standing defect and correction ledger, with seventeen findings
  from the 2026-08-21 audit and a stated priority order.

### 2026-08-19 — Initial ledger

- Consolidated the machine-specific model/runtime architecture and earlier research.
- Recorded native adoption of selected Buzz collaboration ideas without a Buzz dependency.
- Recorded local-first remote escalation policy for limited/free API capacity.
- Verified the ten second-wave repositories from their official public sources.
- Corrected the harness decision: DeepSeek Harness is a replaceable agent kernel, not the
  sovereign system foundation.
- Added memory, protocol-edge, execution-provider, durable-scope, and verified-project-state
  seams plus their promotion gates.
- Adopted the persistent logical-agent roster, explicit `Job`/`Run` separation, contractual
  delegation, expiring grants/leases, scoped-memory enforcement and safe skill promotion.
- Verified Hermes, NemoClaw, A2A, Kitesurf and Warp's factory concept; rejected unverified
  Grok 4.6, standalone Grok Bot and OpenAI Presence names as current dependencies.
- Selected direct Playwright/local Chromium, optional public Kitesurf, a FlaUI host broker,
  bounded exploratory/vision fallbacks and human takeover for the automation hierarchy.
- Made the future Tauri desktop the primary human product while limiting Buzz to a pinned
  component extraction/design source under the sovereign kernel.
- Recorded the final pre-build audit: source checks pass and the architecture is closed, but
  baseline version control, immutable installs, service ownership, local authentication,
  migrations and honest bounded job recovery precede the heavyweight bootstrap.
