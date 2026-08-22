# Living research and architecture ledger

> Last consolidated: **2026-08-22** (waves 6-8)  
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
| Coding tool surface | `NativeAgentLoop`'s three read-only tools | **gap**, wave 6 `D-021` | Identified in wave 6 as the binding constraint: no edit, patch, search or glob tool exists. Adoption work, not invention. |
| Context budget | Unmanaged; history grows into a 16K window | **gap**, wave 6 `D-025` | The one major resource the kernel does not arbitrate, on the machine where it is scarcest. |
| Editor reach | None | `adopted` seam (`D-024`), ACP `trial` | AG-UI faces our own UI; ACP faces every editor we will never write a plugin for. |
| Task entry | No surface can start work | **gap**, wave 7 `D-026` | The CLI has no run command and the desktop has no composer; an `@mention` in a room is the only door. |
| Streaming | None; every view polls on a 4s timer | **gap**, wave 7 `D-027` | Contradicts `D-014` in practice, and presents our slowest property in its worst possible form. |
| Approval evidence | Risk badge and free text | **gap**, wave 7 `D-028` (safety) | An approval that hides its evidence trains the operator to rubber-stamp it. |
| Latency and authority legibility | Data exists, nothing renders it | `adopted` thesis, wave 7 `D-029`/`D-030` | The two experience categories the cloud-first field has no reason to build and we can win outright. |
| Tool plane | `ToolRegistry` holds zero tools | **gap**, wave 8 `D-034` | 19 of 21 capability domains are unreachable by the agent; registering tools is the single highest-leverage change in the project. |
| Licence of this repository | None present | **blocking gap**, wave 8 `D-033` | Invariant 8 is currently violated by us alone: with no `LICENSE`, the work is all-rights-reserved. |
| Platform coverage | Windows + WSL2 only | **gap**, wave 8 `D-035` | No Linux path, no Apple Silicon path - most of the stated audience cannot install it. |
| Untrusted-content defence | Trust labels only | **gap**, wave 8 `D-037` | Labels record provenance; they do not stop injected instructions reaching a planner that holds tools. |
| Prompt/context optimisation | Hand-written string constants | **gap**, wave 8 `D-036` | On fixed hardware the prompt is the tunable parameter, and we already own the eval harness GEPA needs. |

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

## Research wave 6 — the harness capability audit: what the field has that we do not

Consolidated on **2026-08-22**. Five waves compared harnesses **as governance objects**.
None of them compared a harness **as a coding tool**. This wave does exactly that: it reads
this repository's own agent loop against the public capability surface of Claude Code,
OpenAI Codex CLI and the open-source harness field, parameter by parameter — interface, loop
mechanics, code intelligence, tool access, system access, control, safety, distribution,
evaluation and observability — and for each one names **who already does it best**, so the
work becomes adoption rather than invention.

### Truth correction — the binding constraint is now the harness, not the kernel

The project has a control plane most of the field does not have, driving an agent loop that
essentially every member of the field beats. Read `src/sovereign_ai/agents/native_loop.py`
and `src/sovereign_ai/tools/registry.py` and the position is unambiguous:

- the loop exposes **three tools** — `read_file`, `list_directory`, `run_command`;
- there is **no edit, write, patch, search or glob tool anywhere in this repository**
  (`grep -ril "write_file\|apply_patch\|edit_file" src` returns nothing). Every file
  mutation has to be smuggled through `run_command`;
- tool calls are recovered by scanning the model's prose for the outermost `{`…`}` span and
  hoping `json.loads` succeeds — on a runtime (llama.cpp) that has had grammar-constrained
  decoding compiled in the entire time;
- conversation history grows **without compaction** into a 16K operating context, with a flat
  4,000-character truncation per observation as the only budget control;
- `CheckpointStore` snapshots **job state JSON, not file state**, so nothing in this system
  can undo an edit an agent made;
- there is no repo map, no symbol index, no MCP *client*, no project instruction file, no
  todo/plan state, no context-isolated subagent and no interactive terminal surface.

This is not a criticism of the loop, which `D-015` correctly scoped as a reference
implementation. It is the statement that **the coding-agent layer is now the binding
constraint on the whole project**, and that the largest available quality win is no longer a
model, a sandbox or a memory engine.

### The evidence rule for this wave

Claude Code is closed source and subscription-gated; under invariant 8 it can never be a
dependency. Its **mechanisms** are still legitimate design evidence, and are recorded here as
`unverified` at primary source — described consistently across independent write-ups and
vendor documentation, but not inspected by us. Codex CLI is different and more useful: the CLI
itself is **Apache-2.0** (`primary-verified`), so its *code and formats* are legitimately
readable and portable even though the service behind it is gated. Everything marked
`primary-verified` below had its repository, specification or model card fetched in this wave.

### Where we are already ahead — do not rebuild these

Recording this matters as much as the gap list, because it says where **not** to spend time.

| Parameter | Our position | Nearest comparable in the field |
| --- | --- | --- |
| Authority and policy | Kernel-owned `PolicyEngine`, expiring `CapabilityGrant`, structured `ApprovalRequest`, workspace/resource leases | Nothing in the open field is close. OpenBot's CEL gateway is the only similar design and it is hosted-dependent (wave 5) |
| Durable execution truth | `Job`/`Run` separation, per-attempt journals, migrations, backup/restore, restart reconciliation | Harnesses keep sessions on disk; none has a migrated, transactional job store |
| Audit and provenance | Append-only events with trust labels, hash-chained room history, provenance-aware memory | Cline's shadow git and OpenHands' event stream are both narrower |
| Model routing | Capability routing with hardware fit, local-benchmark override, GPU arbitration, VRAM fitting, dynamic load/unload | Aider and opencode *select* a model; none arbitrates a 12 GB card |
| Multi-store memory | Lexical + vector + graph with scope ACLs, provenance and deletion semantics | Most harnesses have a markdown file |
| Contextual tool discovery | `ToolRegistry.discover` — agents see a small relevant roster, never the whole universe | Only now appearing elsewhere as "tool search" |
| Windows-first execution | Windows→WSL2 OpenShell bridge with hardened Docker fallback | The field's sandboxing is Linux/macOS-first; Windows is its weakest platform |

### Gap matrix 1 — code intelligence and editing (the lethal category)

| Parameter | Who does it best | What they actually do | Ours today | Verdict |
| --- | --- | --- | --- | --- |
| File mutation | **Codex CLI `apply_patch`** (Apache-2.0, `primary-verified` licence) | A model-friendly freeform patch format dispatched as a first-class tool rather than a shell command, so edits are parseable, reviewable and refusable | none | **steal the format, port the applier** |
| Edit-format fit | **Aider** (Apache-2.0) | Several edit formats — whole-file, search/replace blocks, unified diff, patch, architect/editor split — *selected per model*, because weak models fail different formats | none | **steal**: the model registry already stores per-model metadata; add an `edit_format` field |
| Context selection | **Aider repo map** | tree-sitter symbol graph across 100+ languages, ranked by PageRank over the definition/reference graph, emitted inside a token budget | none | **steal outright** — the highest-value borrowed algorithm in the field |
| Symbol-level ops | **Serena** (MIT, `primary-verified`) | LSP-backed `find_symbol`, `find_referencing_symbols`, `replace_symbol_body`, `insert_before/after_symbol`, safe delete, type hierarchy, 40+ language servers; explicitly more token-efficient than text search/replace | none | **steal** — through an MCP client (`D-023`) first, vendored later if it earns it |
| Search | ripgrep-backed `grep`/`glob` tools in every serious harness; **ast-grep** for structural search | Dedicated, bounded, structured search instead of `bash grep` | `run_command` only | **build (trivial)** — a day's work that removes a whole class of failure |
| Edit application speed | **Kortix FastApply** 1.5B/7B (Apache-2.0, `primary-verified`; Qwen2.5-Coder base; ~340 tok/s at 1.5B, ~150 tok/s at 7B) | A small specialist merges a terse edit snippet into a full file, so the big model never regenerates unchanged lines | none | **adopt** — a direct answer to F-005/F-012: the deep brain must not spend its 6–52 tok/s reprinting code |
| Verify-then-commit | **Aider** | Auto-commit per edit with a generated message, `/undo`, and an automatic lint/test loop after every change | a verification engine exists but is not wired into an edit loop | **wire ours up** |

### Gap matrix 2 — loop mechanics (where small models are won or lost)

| Parameter | Who does it best | What they actually do | Ours today | Verdict |
| --- | --- | --- | --- | --- |
| Tool-call reliability | **llama.cpp GBNF / llguidance / XGrammar** (`primary-verified` capability, present in our pinned build) | Constrain decoding to a grammar so a malformed tool call becomes *impossible* rather than retried. llguidance reports ~50 µs mask computation; XGrammar reports near-zero end-to-end overhead | outermost-brace prose scraping | **adopt immediately** — the best reliability-per-line-of-code available, and free |
| Action expressiveness | **OpenHands CodeAct** (MIT; ICML 2024 paper) | The action space *is* Python/bash: loops, conditionals and variable reuse happen inside one turn. Reported ~30% fewer turns and ~20% higher success versus one JSON tool call per turn | one JSON action per turn | **steal as a second loop mode** — turn count is our dominant cost at 6–52 tok/s |
| Plan/act separation | **Cline** (Apache-2.0) plan vs act; **Aider** architect/editor; Claude Code plan mode | A read-only reasoning phase produces a plan a human approves before any mutation is possible | none (`approved` is a single boolean) | **steal** — it maps directly onto the existing `ApprovalRequest` |
| Task-state tracking | **Claude Code** todo list; **Cline** focus chain | An explicit, model-maintained checklist held in context so long tasks do not drift | none | **steal (cheap)** — disproportionately effective for small models |
| Context compaction | **Claude Code** `/compact` plus automatic microcompaction; **Cline** `ContextManager` | Summarise-and-continue with the working set preserved, plus tool-result pruning | none — unbounded growth into a 16K context | **build now** — currently the hard ceiling on task length |
| Sub-task isolation | **Claude Code** subagents; **Goose** subagents | A child run gets a *fresh context*, returns only its result, and never pollutes the parent | `Delegation` exists but carries no context discipline | **wire ours up** — the contract exists, the mechanism does not |
| Failure recovery | 2026 self-healing-orchestrator literature (`unverified`, arXiv 2606.01416) | monitor→detect→diagnose→recover→verify; reports 98.8% task success versus 94.5% for retry-only, and verifier-guided repair driving silent failures to 0% | one retry, as a new `Run` | **build on ours** — we already own the verifier the literature identifies as the difference |
| Prompt-cache economics | **llama.cpp** `--cache-reuse`, slot reuse, `--cache-ram` | Keep the stable prefix resident so each agent turn reprocesses only the changed suffix | not configured anywhere | **adopt (configuration only)** |
| Speculative decoding | llama.cpp `spec-type` family (recorded in wave 5, unused) | A draft head multiplies generation speed on a memory-bound path | recorded, unused | **promote** — it is on the critical path now, not a curiosity |

### Gap matrix 3 — control, safety and system access

| Parameter | Who does it best | What they actually do | Ours today | Verdict |
| --- | --- | --- | --- | --- |
| Deterministic hooks | **Claude Code** (`unverified`; ~30 documented lifecycle events including `PreToolUse`, `PostToolUse`, `PermissionRequest`, `PreCompact`, `SubagentStart`, `FileChanged`) | User-owned shell/HTTP/prompt handlers at fixed points that can allow, deny or annotate, returning structured JSON decisions | kernel policy only; no user-programmable layer | **steal the event vocabulary**, keep our policy as the authority |
| Permission granularity | **Claude Code** allow/deny/ask rules; **Codex** approval modes (read-only, auto, full-access) | Per-tool, per-pattern rules with a real "ask" path, plus one coarse session-wide mode | binary `approved` plus grants | **steal the surface**, back it with `CapabilityGrant` |
| Action pre-screening | **Claude Code Auto Mode** (`unverified`) — a *separate small classifier model* reviews each proposed action before it runs | A cheap model as a safety pre-filter: safe actions proceed, risky ones escalate | none | **steal the mechanism** — we already run a 49.6 tok/s fast brain that sits idle during deep-brain turns |
| OS sandboxing | **Codex CLI** (Apache-2.0): Landlock + seccomp + bubblewrap on Linux, Seatbelt on macOS, AppContainer/restricted tokens on Windows; **Microsoft Execution Containers** preview (`unverified`) targeting Windows and WSL | Kernel-enforced filesystem and network confinement, with an explicit legacy fallback path | OpenShell/WSL2 + Docker (strong), nothing for direct Windows-side execution | **watch MXC; port the AppContainer idea** — the field's Windows story is also weak, so parity here is a differentiator, not catch-up |
| Filesystem undo | **Cline checkpoints** (Apache-2.0) — a *shadow git repository*, separate from the user's own history, committed after each tool use | Restore files without losing the conversation, on an auditable trail | job-state checkpoints only | **steal outright** — small, self-contained, and it is what makes autonomy tolerable |
| Parallel isolation | **git-worktree orchestrators** (Conductor, Claude Squad, Vibe Kanban, container-use; `unverified` landscape reporting) | One worktree or container per agent, diff-first review, many agents at once | `WorkspaceLease` exists; no worktree materialisation | **finish ours** — we are roughly one function away |
| Egress control | agentgateway (already `trial`, wave 2) | — | seam exists | unchanged |

### Gap matrix 4 — surface, distribution and reach

| Parameter | Who does it best | What they actually do | Ours today | Verdict |
| --- | --- | --- | --- | --- |
| Editor integration | **Agent Client Protocol** (Apache-2.0, `primary-verified`) — JSON-RPC over stdio; Zed and JetBrains native, Neovim/Emacs/VS Code community, a registry since Jan 2026, reported 50+ agents and 11+ editors | One protocol puts an agent inside every ACP editor with no per-editor work | none | **adopt** — the highest reach-per-effort item in this wave, and complementary to AG-UI (`D-014`): ACP faces editors, AG-UI faces our own UI |
| Terminal experience | **Codex** (Ratatui TUI), **opencode**, **Aider**, **Goose** | A real interactive REPL: streaming, inline diffs, approvals, slash commands, history | Typer CLI of one-shot commands, one static web page, a Tauri slice | **build** — no daily-driver claim survives without it |
| Project instructions | **AGENTS.md** (the field's de facto standard: Codex and most open agents) | A committed per-repo file the agent loads automatically | none | **adopt the standard** — do not invent a fourth filename |
| Portable skills | **Agent Skills / SKILL.md** — public specification since 2025-12-18; reported 40+ platforms during 2026 (`unverified` count) | Filesystem-packaged procedures with progressive disclosure (~100 tokens of metadata until the skill is actually needed) | `SkillCandidate`→`SkillVersion` governance, but no portable file format | **adopt the format, keep our governance** — the rare case where we are *ahead on safety and behind on interoperability*; adopting it imports the community's skills for free |
| External tool access | **MCP client** in every serious harness (Goose ships 70+ extensions) | Thousands of existing servers become available without writing adapters | we are an MCP *server* (`agents/mcp_bridge.py`) and not a client | **build** — the asymmetry is costing us the entire tool ecosystem |
| Slash commands / prompts | Claude Code, Codex, opencode, Cline | Reusable parameterised prompts committed alongside the repository | none | **build (cheap)** |
| Session continuity | Claude Code `/resume`, fork and transcript search; Codex resume | Reattach to a prior conversation, branch it, search it | `Run` records exist; no conversational resume | **wire ours up** |
| Plugin distribution | Claude Code plugins; Cline MCP marketplace; the ACP registry | One command installs a bundle of skills, commands, hooks and servers | none | **defer** — this matters at community-release time, not before |
| Observability | **OpenTelemetry GenAI semantic conventions** (CNCF; Copilot, Codex and Claude Code reported to emit them) | Standard span/metric names for model calls, agent steps, tool calls, tokens and cost, readable in any OTLP backend | rich internal events, no export | **adopt the schema** — a mapping layer, not a dependency; our event store stays canonical |
| Benchmarking | **Terminal-Bench 2.x** and SWE-bench Verified harnesses; **Aider polyglot** | Containerised, reproducible task suites — and the published finding that the *same model* scores materially differently under different harnesses | `harness_tournament.py` + `evaluate_brain_quality.py` (good bones) | **steal the task format** — the tournament needs a public, comparable task set to be evidence rather than opinion |

### The model layer, revisited under a coding-agent lens

`D-012` and `D-016` optimised the deep brain for **throughput on general text**. The harness
lens adds a second axis this ledger has never recorded: **agentic training**. Landscape
reporting (`unverified`) puts Qwen3-Coder-Next (Apache-2.0, ~80B total with ~3B active,
released February 2026) and Devstral 2 (Apache-2.0) as the open-weight models explicitly
trained for coding-agent scaffolds and tool calling, with GLM-5.2 (MIT) leading agentic and
terminal benchmarks at a size this machine cannot host. Two consequences:

1. A model trained for tool use inside a harness is not interchangeable with a general model
   of the same speed. The tournament must vary **model × harness**, not model alone.
2. Both leading candidates are permissively licensed *and* sparse-active, so `D-012`'s
   principle and invariant 8 point at the same shortlist for once. Qwen3-Coder-Next at ~3B
   active is the first candidate satisfying the hardware constraint, the licence gate and the
   agentic-training requirement simultaneously. It is a `trial` candidate for the coding
   capability slot, not an adoption; nothing here has been measured on this machine.

### The steal order

Ordered by (impact on a *local, small-model* agent) ÷ (effort), not by novelty. Items 1–5 are
days of work each and change what the system can do at all.

1. **Grammar-constrained tool calls.** A GBNF grammar for the action schema, applied through
   the existing llama.cpp router. Retires the brace-scraping parser. Configuration plus a
   schema; no new dependency.
2. **A real tool surface.** `write_file`, patch-format `apply_patch` (Codex format), `grep`
   (ripgrep), `glob`, and `read_file` with line ranges. Every one policy-gated through the
   existing `ExecutionBroker`/`CapabilityGrant` path — the authority model does not change,
   only the vocabulary available inside it.
3. **Shadow-git checkpoints.** Cline's mechanism on our `CheckpointStore`: a separate
   repository under `state/`, a commit per mutating tool call, restore by run and step.
4. **Context management.** Compaction with a preserved working set, per-observation budgets,
   and `--cache-reuse` configured on the router.
5. **AGENTS.md + SKILL.md loading.** Read the standards the field already writes, and keep our
   candidate/evaluation/promotion governance on top of them.
6. **MCP client.** Consume the ecosystem, starting with Serena for symbol-level editing.
7. **Repo map.** tree-sitter plus PageRank, token-budgeted, cached and invalidated per file.
8. **CodeAct mode.** A second `AgentLoop` whose action space is code, measured against the
   JSON loop in the tournament rather than assumed better.
9. **FastApply specialist.** A 1.5B merge model in the existing specialist-worker plane, so
   the deep brain emits edit snippets instead of whole files.
10. **ACP server.** Achilles appears in Zed, JetBrains, Neovim and VS Code without four
    separate integrations being written.
11. **Hooks, permission modes and classifier pre-screening**, the last of these using the
    otherwise-idle fast brain.
12. **TUI**, then worktree-per-run, then OTel export, then Terminal-Bench task import.

### What this wave explicitly does not authorise

- Forking or vendoring Claude Code (closed source — mechanisms only, never code).
- Depending on the Codex *service*; only its Apache-2.0 CLI code and file formats are in scope.
- Treating any reported benchmark number in this wave as local truth.
- Replacing the kernel's authority model with any harness's permission system. Every stolen
  mechanism arrives *below* `PolicyEngine`, never beside it.
- Adopting a wider tool surface without verifiers: more power in the loop raises, not lowers,
  the bar for post-condition checks.

## Research wave 7 — the experience audit: interface, interaction, and the parts a user actually touches

Consolidated on **2026-08-22**, immediately after wave 6, because wave 6 was itself
incomplete: it treated the entire experience layer as three rows in a table ("terminal
experience", "editor integration", "session continuity") and moved on. That was wrong. For a
system whose stated ambition is to replace a daily-driver coding agent for people who cannot
buy one, **interaction design is a first-class axis, not a footnote** — and it is the axis on
which this repository is furthest behind, further behind than the harness gap wave 6 found.

This wave is written to the standard of a demanding practitioner evaluating whether to switch
to Achilles, not to the standard of "reasonable for an early open-source project".

### The one-sentence verdict

**There is no path from "I have a task" to "the agent did it" that any developer in this field
would accept**, and every surface that exists is a polling read-only table over a system that
never streams.

### What was actually inspected

`web/index.html` (47 lines), `desktop/src/App.tsx`, all five desktop views,
`desktop/src/api/kernelClient.ts`, `desktop/src/App.css` (438 lines) and
`src/sovereign_ai/cli.py`. Findings below are grep-verifiable, not impressions.

### Severity ledger

`S1` blocks daily use. `S2` makes the system feel unfinished to a demanding user. `S3` is
polish that separates a good product from a great one.

| # | Finding (verified in this repository) | Severity |
| --- | --- | --- |
| X-01 | **No surface can start work.** `JobsView` cancels, `RosterView` lists, `ApprovalsView` resolves. The CLI has `preflight`, `route`, `serve`, `workspace`, `secret`, `dump-manifest` — and no command that runs a task. The only way to make the system do anything is to `@mention` an agent in a chat room or hand-write an HTTP request. | `S1` |
| X-02 | **Nothing streams, anywhere.** No `StreamingResponse`, no SSE, no WebSocket, no generator in the API (`grep` returns zero hits). Every view is a 4-second `setInterval` poll. On hardware that generates 6–52 tok/s, a user stares at "Loading..." for minutes and then receives a finished wall of text. This also silently contradicts `D-014`: we adopted AG-UI *because* it standardises streaming, then built the opposite. | `S1` |
| X-03 | **The approval card does not show what it is approving.** It renders `subject_id`, `action:scope`, a risk badge and a free-text reason — no command, no diff, no file list, no evidence, no policy rule, no expiry countdown, no consequence-of-denial. This is not a cosmetic gap: an approval surface that hides evidence trains its operator to click Approve, which converts our strongest safety mechanism into a rubber stamp. | `S1` (safety) |
| X-04 | **No diff view exists in any surface.** When `D-021` lands there will be nowhere to review an edit. Review is the core interaction of an agentic coding tool; we have none of it. | `S1` |
| X-05 | **Agent output is rendered as plain text.** The room timeline builds message bodies with `textContent`. Markdown, code blocks, syntax highlighting, copy buttons and file links do not exist — in a *coding* assistant. | `S1` |
| X-06 | **No terminal interface.** No TUI, no REPL, not even a one-shot `sovereign run "<task>"`. The field's primary surface is absent entirely. | `S1` |
| X-07 | **Accessibility is zero.** Across the whole desktop app and web page there is exactly one `aria-`/`role=`/`onKeyDown`/`tabIndex` occurrence. No focus management, no keyboard navigation, no screen-reader labels, no reduced-motion or contrast handling. For software meant to be given to everyone, this excludes people by omission. | `S1` |
| X-08 | **Errors are raw protocol strings.** `GET /jobs -> 500: {"detail": ...}` is shown directly to the user. There is no recovery affordance, no retry, no diagnosis, no link to `doctor.py`. | `S2` |
| X-09 | **A failed connection is terminal.** `KernelClient.connect()` runs once in a `useEffect`; if the kernel is not up, the app shows an error panel with no retry and never reconnects. Restarting the app is the only recovery. | `S2` |
| X-10 | **The room shows chatter and failures only.** `renderEvents` filters to `message.posted` and `job.failed`. Job completions, approvals, delegations, grants and verification receipts — the things wave 3 principle 3 says rooms exist to display — are invisible. | `S2` |
| X-11 | **Scroll position is destroyed on every poll.** The timeline sets `scrollTop = scrollHeight` on each refresh, so reading history while an agent works is impossible. | `S2` |
| X-12 | **No session, thread, or history model in the product.** `Run` records exist in the kernel; no surface offers resume, fork, search, or "what did we do yesterday". | `S2` |
| X-13 | **No notifications.** A twenty-minute local run ends silently; the user must babysit the window. | `S2` |
| X-14 | **No live cost of the only currency we have.** No tokens/second, no context-window meter, no VRAM gauge, no KV-cache hit indicator, no model-load progress, no queue position, no "which brain answered this". The system knows all of it and shows none of it. | `S2` |
| X-15 | **No onboarding or hardware fit experience.** For a project whose entire premise is that strangers run it on hardware we have never seen, the fit story is a YAML manifest, a PowerShell installer and `doctor.py`. There is no first-run wizard, no autotune, no "here is what your GPU can actually run". | `S2` |
| X-16 | **No permission gradations in the UI.** Approve/Deny only: no "approve once", "approve for this session", "always allow this tool in this workspace". The kernel has `CapabilityGrant` with expiry and scope; the UI throws that expressiveness away. | `S2` |
| X-17 | **No theming, no light/dark, no font scaling, no i18n.** One hard-coded dark palette in 438 lines of CSS. | `S3` |
| X-18 | **No command palette, no keyboard shortcuts, no search** across jobs, runs, rooms or memory. | `S3` |
| X-19 | **Identity is inconsistent and hard-coded.** The web page injects the session token by `%%SOAI_SESSION_TOKEN%%` string replacement, every actor is the literal string `"owner"`, and the product is called three different things across surfaces. | `S3` |
| X-20 | **No lists are virtualised, no optimistic updates, no skeletons.** Fine at 50 jobs; visibly amateur at 5,000. | `S3` |

### Who does each thing best — the experience steal list

| Parameter | Who does it best | What specifically to take |
| --- | --- | --- |
| Live tool-call visibility | **Zed Agent Panel** | Tool calls stream into the panel as they happen, so the user sees *what the model is doing*, not just its final output. This is the single most trust-building interaction in the field |
| Diff review | **Zed** multi-buffer review with per-hunk keep/reject, mirrored inline in the file; **Cline** streaming diffs into the editor | Review is per hunk, in place, with the agent's change temporarily overriding the git diff — not a text blob in a chat log |
| Checkpoint navigation | **Cline** | A checkpoint per tool call, restorable independently, with the conversation preserved — pair it with `D-021`'s shadow git |
| Terminal experience | **Codex** (Ratatui) and **opencode** | Multi-session, configurable keybindings through a keybind provider, vim mode, themes, client/server split so the TUI is one client of a local server — which is exactly our kernel/API shape already |
| Terminal quality-of-life | **Claude Code** (`unverified`, mechanisms only) | Status line (model, context %, spend, branch), message queueing while the agent works, `@`-file autocomplete, image paste, completion notifications, a transcript view |
| Parallel work | **Zed Parallel Agents**, **Conductor** | Several agents in one window on separate worktrees, each with an isolated diff to inspect before merging |
| Multi-pane workspace | **OpenHands GUI** | Chat, terminal, file explorer and browser as one working surface — the closest existing analogue to what our kernel could render |
| Local-model onboarding | **LM Studio**, **Jan** | Model browser showing disk size, RAM/VRAM requirement and quantisation *before* download; side-by-side comparison; models labelled "fast / balanced / high-quality" instead of by parameter count |
| Session sharing | **opencode** | A session is a first-class, addressable, shareable object |
| Permission and trust patterns | 2026 agentic-UX literature | Layered controls over data, action, evidence, review, recovery and accountability; default to the most conservative autonomy and let the user raise it as trust builds; explanation always one interaction away, never forced |

### Where we can be better than all of them, not merely level

Two categories exist where the field has no incentive to build well and we have every
incentive, because they arise directly from being local and from being authority-first.
These are the experience equivalents of a moat.

**1. Latency legibility.** Every competing product is designed around cloud inference that is
effectively instant and effectively unlimited. Ours is not: the deep brain runs at 6.36 tok/s
under offload and the fast brain at 49.57 tok/s (F-005, F-012), models take tens of seconds
to load, and VRAM is a hard 12 GB. Cloud-first UI hides latency because it can afford to.
**We should render it instead**: live tokens/second, a context-window meter, a VRAM gauge, KV
cache hit/miss, model load progress in gigabytes, queue position, and an explicit marker of
which brain produced which turn, with a one-click "escalate this to the deep brain". A user
who can *see* why something is slow tolerates it; a user watching an undifferentiated spinner
concludes the product is broken. Nobody else will build this, because nobody else needs it.

**2. Authority legibility.** We are the only system in this comparison that *has* the data:
policy decisions with reasons, expiring capability grants, workspace and resource leases,
trust labels on every event, verification receipts, and a hash-chained journal. Rendering
that is a category nobody in the open field can enter: an approval card that shows the exact
command or diff, the rule that triggered the request, what the grant will permit and for how
long, and what happens if it is denied; a run inspector that replays every step with its trust
label and verifier result; a "why was this allowed?" answer that is one click from any action.
The 2026 UX literature says explanation is the strongest driver of trust and its absence the
strongest driver of abandonment — and we are sitting on the only substrate that can provide it.

### The experience order

1. **Make the system usable at all**: `sovereign run "<task>"` in the CLI, a "New task"
   affordance in the desktop, and a task composer that is not a chat-room mention.
2. **Stream everything**: SSE over the existing API, AG-UI event shapes (`D-014`), retire the
   4-second polls. Tool calls appear as they happen.
3. **Render the work**: markdown and syntax highlighting, per-hunk diff review with
   keep/reject, and a checkpoint timeline over `D-021`'s shadow git.
4. **Fix the approval card** into an evidence card, with grant scope, expiry, the triggering
   rule, and once/session/always gradations backed by `CapabilityGrant`.
5. **Build the TUI** as a first-class client of the kernel API — the same split opencode and
   Codex use, which our client/server shape already supports.
6. **Latency legibility**: status line and gauges wherever a run is visible.
7. **Recovery and errors**: reconnecting client, human-readable failures with a next action,
   and completion notifications.
8. **Accessibility and theming** as release gates: keyboard paths, focus management, labels,
   light/dark, font scaling.
9. **First-run experience**: hardware detection, an autotune sweep that picks the operating
   point our own benchmark scripts already know how to measure, and a model browser that
   states VRAM fit before download.
10. **Session model**: resume, fork, search, share.

### The honest framing

Wave 6 said the harness is the binding constraint. Wave 7 corrects that: **the harness is the
binding constraint on capability, and the experience layer is the binding constraint on
adoption.** A system with a perfect kernel and no way to start a task is not a product, and
the people this project exists for will not read the architecture document before deciding.

## Research wave 8 — the total capability audit: what Achilles would actually have to be

Consolidated on **2026-08-22**. Waves 6 and 7 audited the coding harness and the experience
layer. This wave audits **everything else the name implies** — audio, speech, vision,
documents, images, video, music, science, browser, computer control, memory, learning,
security, distribution and scale-out — against one standard, stated by the user and adopted
here as the bar:

> A person who finds this should be surprised it is open source rather than proprietary.

That is a demanding test and this wave applies it without generosity. Where the answer is
"they would not be surprised", it says so.

### Truth correction 1 — the manifest is not the system

`configs/models.yaml` declares 35 models spanning reasoning, coding, vision, retrieval, OCR,
NER, ASR, alignment, diarization, audio reasoning, TTS, detection, segmentation, depth, GUI
control, image generation, video, music, forecasting, tabular, protein, materials, medical,
earth observation and theorem proving. It is, on paper, the broadest capability manifest of
any open coding-agent project reviewed in this ledger. In running software:

- **`ToolRegistry` is instantiated once in `kernel/app.py:160` and never has a single tool
  registered into it.** The README's "contextual tool discovery" is a working algorithm over
  an empty dictionary. `discover()` returns nothing because there is nothing to discover.
- **The agent cannot invoke any specialist.** `NativeAgentLoop` has `read_file`,
  `list_directory`, `run_command`. There is no tool that reaches the specialist broker, the
  media broker, memory, retrieval, the computer controller or the web. Every one of the 35
  models is human-API-only.
- **`ComputerController` has zero registered controllers**, so `execute()` raises
  `RuntimeError` on every call. Browser control, Windows UIA and the vision-GUI fallback are
  an interface with no implementations. Playwright is an optional dependency nothing imports.
- **7 of 14 declared workers have no handler.** `HANDLERS` covers `retrieval`, `qwen_asr`,
  `voxcpm`, `paddleocr`, `vision`, `science_general`, `tabpfn`. Requests to `moss_audio`,
  `sam`, `ui_tars`, `fairchem`, `medgemma` and `ace_step` return **HTTP 501**. That is
  audio reasoning, diarization, segmentation, GUI grounding, materials, medical and music —
  declared, installed at ~290 GB in the workstation profile, and unreachable.
- **SearXNG is deployed and never queried.** `infra/docker-compose.yml` and
  `scripts/configure_infra.py` stand up a search engine; `grep -rn "searx" src` returns
  nothing. The system installs a web-search service it has no client for.
- **`ContextBuilder` is constructed and never called in any request path.** `job_executor`'s
  `chat` branch passes `payload.messages` straight to inference. Memory is written to and
  never consulted. A memory system outside the loop is a database, not a memory.

The honest summary: **this is a catalogue with a kernel, not yet a system with capabilities.**
Every claim in this section is a `grep` away from being reproduced.

### Truth correction 2 — the project is not, today, open source

Baseline invariant 8 says the system "is open source, end to end, and is meant to be given
away". As of this audit:

- **There is no `LICENSE` file in the repository, and no `license` field in
  `pyproject.toml`.** Under default copyright law that makes the work *all rights reserved*:
  nobody may legally copy, modify or redistribute it. The single most load-bearing invariant
  in this ledger is currently unenforceable, and the fix is five minutes of work.
- **There is no CI.** No `.github/` directory exists. 153 tests are written and nothing runs
  them on a change.
- **There is no release process**: version is `0.1.0` in `pyproject.toml`, with no changelog,
  no tags, no signed artifacts, no updater.
- **There is no contribution path**: no `CONTRIBUTING`, no code of conduct, no issue
  templates, and no vulnerability-reporting policy (`docs/SECURITY.md` is an architecture
  document, not a disclosure policy).
- **Installation is Windows-only.** `Install.ps1`, `bootstrap.ps1`, `provision_wsl.ps1` and
  `start.ps1` are PowerShell; the `.sh` scripts run *inside WSL*, not on Linux. There is no
  Linux install path and no Apple Silicon path at all — and Apple Silicon unified memory is
  currently among the best consumer hardware for local inference, while Linux is where most
  of this project's stated audience actually is.

A project cannot be "given back to the community" when the community cannot legally copy it,
cannot install it on their operating system, cannot verify it builds, and has no way to
contribute. This is not pedantry: it is the mission's own success criterion, unmet.

### Capability reachability — the table that matters

`Declared` = in `configs/models.yaml`. `Adapter` = a worker handler or broker exists.
`Agent-reachable` = the agent loop can actually invoke it. **The last column is the product.**

| Domain | Declared | Adapter | Agent-reachable | Verdict |
| --- | --- | --- | --- | --- |
| Text/code reasoning | yes | yes (llama.cpp router) | yes | the only fully connected path in the system |
| Retrieval / embedding / rerank | yes (4 models) | yes | **no** | wired to `ContextBuilder`, which nothing calls |
| Lexical / vector / graph memory | yes | yes | **no** | not in the loop |
| OCR / document parsing | yes (PaddleOCR-VL 1.6) | yes | **no** | genuinely SOTA choice, unreachable |
| NER / structured extraction | yes (GLiNER2) | yes | **no** | — |
| ASR / alignment | yes (3 models) | yes | **no** | — |
| TTS | yes (VoxCPM2) | yes | **no** | — |
| Audio reasoning / diarization | yes (MOSS ×2) | **no (501)** | no | declared, installed, unimplemented |
| Object detection / depth | yes (RF-DETR, DA3) | yes | **no** | — |
| Segmentation | yes (SAM 3.1) | **no (501)** | no | — |
| GUI grounding | yes (UI-TARS-1.5-7B) | **no (501)** | no | and no controller to act on it |
| Browser control | — | **none** | no | Playwright is an unused optional dependency |
| Windows UI control | — | **none** | no | designed in wave 4, never built |
| Image generation/editing | yes (FLUX.2 Klein) | via WanGP | **no** | — |
| Video generation | yes (LTX-2.5, MiniMax-H3) | via WanGP | **no** | — |
| Music generation | yes (ACE-Step 1.5) | **no (501)** | no | — |
| Deterministic media editing | FFmpeg/SoX named | **no** | no | not wrapped as a tool at all |
| Forecasting / tabular | yes (Chronos-2, TabPFN-3) | yes | **no** | — |
| Protein / materials / medical / earth / proving | yes (5 models) | partial (`fairchem`, `medgemma` 501) | **no** | breadth nobody else has, reachable by nobody |
| Web search | SearXNG in infra | **no client** | no | deployed, unqueryable |
| Code intelligence (LSP/symbols/repo map) | — | none | no | wave 6 `D-021`/`D-023` |

**Nineteen of twenty-one capability domains are unreachable by the agent.** This single table
explains the gap between how the architecture reads and how the system behaves.

### Gap matrix 5 — the axes waves 6 and 7 did not cover at all

| Axis | Who does it best | What we are missing | Verdict |
| --- | --- | --- | --- |
| **Automatic prompt/context optimisation** | **GEPA** (reflective prompt evolution; reported 10–20% accuracy over GRPO/MIPROv2 with up to 35× fewer rollouts, with DSPy, MCP and Terminal-Bench adapters) and **ACE** (generator–reflector–curator loop evolving a living playbook) | Nothing. Prompts are hand-written string constants in `native_loop.py`. | **the largest unexploited quality lever we have.** We are the rare project with the two things GEPA needs — an eval harness and reproducible tasks — and a model too weak to waste a single prompt token on |
| **On-device personalisation** | **Unsloth** LoRA/QLoRA (≈2× faster, ~50% less VRAM), O-LoRA-style continual adapters | No fine-tuning path at all | **differentiator**: a subscription agent can never train on your private codebase overnight on your own GPU. We can |
| **Agent-shaped serving** | **SGLang RadixAttention** (prefix reuse across turns; reported ~29% higher agent throughput, up to 6× on RAG), **vLLM PagedAttention** for concurrency | llama.cpp only, single stream, no prefix cache configured, no batching for parallel agents | **adopt as a second engine** behind the existing adapter plane — our own seam already allows it |
| **Browser agency** | **Browser Use** (~108k stars, reported 87.4% on a 200-task long-horizon web benchmark) | zero | wave 4 designed it; nothing exists |
| **GUI grounding models** | **Holo-1.5** (Apache-2.0, 3B/7B/72B), **OpenCUA** (7B/32B/72B), **UI-Venus-1.5**, **Qwen3-VL** | manifest pins UI-TARS-1.5-7B only, with no adapter | **re-scan**: the GUI-grounding field moved twice since our manifest was written, and Apache-2.0 options now exist |
| **Untrusted-content defence** | **CaMeL** (privileged/quarantined LLM split, capability sandbox, data-flow-tracking interpreter); **FIDES, Progent, RTBAS** | trust labels on events, and a plan to add web + browser + MCP + skills on top of them | **architectural gap, and it is a security one.** Labels describe provenance; they do not prevent an injected instruction from reaching a privileged planner |
| **Low-storage local RAG** | **LEANN** (pruned proximity graph + on-the-fly re-embedding: <5% storage overhead, >90% recall@3) | a conventional vector store that keeps full embeddings | **steal**: the exact problem shape of indexing a whole laptop on a 12 GB card |
| **Document conversion for RAG** | **Docling**, **MinerU 2.5**, **Marker 2/Surya 2** | PaddleOCR-VL (a strong pick) and nothing that converts a PDF into structured chunks | complete the path from document to memory |
| **Office document generation** | open libraries (`python-docx`, `openpyxl`, `python-pptx`, LaTeX/Typst) | nothing — we can *read* documents and not *produce* them | **build**: "all-rounder" fails immediately on "make me a report" |
| **Realtime voice interaction** | **Moshi** full-duplex (~160 ms), **Pipecat 1.0** / **LiveKit Agents** orchestration, **Kokoro/Orpheus/Chatterbox/Higgs/Dia2** (Apache-2.0/MIT) | batch ASR and batch TTS models with no adapter path to the agent, no duplex, no barge-in, no wake word, no voice UI | **build**: voice is the modality where local wins outright — no audio ever leaves the machine |
| **Scale-out to idle machines** | **prima.cpp** (30–70B on heterogeneous home clusters; reported 5–17× lower TPOT vs llama.cpp/exo/dllama), **llama.cpp RPC**, **exo** | single-machine only | **the sovereign answer to "your GPU is too small"**: use the other machines you already own instead of a subscription |
| **Distribution** | **Tauri 2** bundler + signed updater (MSI/NSIS, DMG, deb/rpm/AppImage) | Windows-only PowerShell, no license, no CI, no releases | blocking for the mission |

### Where Achilles can be a category of one

The honest answer to "why is this open source and not proprietary?" cannot be "it has the
features of the proprietary ones." It has to be **capabilities a subscription product cannot
offer at all**. Six exist, and every one is a direct consequence of running on the user's own
hardware under the user's own authority:

1. **It learns your codebase in the weights, not just the prompt.** Overnight LoRA on your own
   GPU. No hosted agent can do this without taking your code.
2. **It indexes your whole machine.** LEANN-class storage overhead makes a personal index of
   everything feasible locally; a cloud agent would have to upload your life first.
3. **Voice that never leaves the room.** Full-duplex local speech is the one modality where
   privacy is not a preference but a precondition — medical, legal, personal.
4. **It uses the hardware you already own.** prima.cpp-style clustering turns a laptop, a
   desktop and an old GPU box into one pool. Subscriptions cannot sell you that.
5. **It can prove what it did.** Hash-chained events, expiring grants, verification receipts
   and a replayable run inspector — an audit story a hosted product cannot give you, because
   you would have to trust their logs about their machine.
6. **It does everything, in one authority domain.** Nobody else combines code, documents,
   speech, vision, media, science and computer control behind one policy engine, one memory
   and one audit trail. That is the actual moat — and the reachability table above shows it
   is currently the least-realised part of the system.

### What must stop being claimed

Until each is reachable by an agent and smoke-tested, `README.md` and `docs/FINAL_STACK.md`
must not present these as capabilities of the system: audio reasoning, diarization,
segmentation, GUI control, browser control, music generation, materials modelling, medical
multimodal, web search, and "contextual tool discovery". They are *installed model weights and
declared intentions*. `docs/IMPLEMENTATION_STATUS.md` exists precisely to prevent this class
of overstatement and did not catch it, because it audited kernel features rather than
end-to-end reachability.

### The revised build order

Waves 6 and 7 produced two ordered lists. Wave 8 puts one item before both of them and adds a
third phase after them.

**Phase 0 — legitimacy (hours, not days).** `LICENSE` (Apache-2.0, matching what we demand of
everything we adopt), a `license` field in `pyproject.toml`, a CI workflow that runs the 153
existing tests, `CONTRIBUTING`, and a vulnerability-reporting policy. Nothing else in this
ledger is deliverable to anyone until this exists.

**Phase 1 — the tool plane (this is the unlock).** Register real tools in `ToolRegistry` and
give the agent loop a dispatcher into them: the wave-6 file tools first, then specialist
invoke, media generate, memory search, and web search against the SearXNG we already run.
Nineteen unreachable domains become reachable through *one* mechanism. This is the highest
leverage change available anywhere in the project.

**Phase 2 — waves 6 and 7 as written.** Harness parity, then experience.

**Phase 3 — the category-of-one work.** In order of (differentiation × feasibility): GEPA/ACE
prompt optimisation, quarantined-LLM injection defence before any browser or web tool ships,
browser control, LEANN-class personal index, realtime voice, prima.cpp scale-out, LoRA
personalisation, cross-platform packaging and signed releases.

### The uncomfortable summary

The kernel is genuinely excellent and genuinely rare. The manifest is genuinely ambitious. But
the system today can read a file, list a directory, run a command, and talk. Everything else is
either declared, installed, or designed — and unreachable. **The distance between this
repository and the name Achilles is not research. It is wiring, and then legitimacy.**

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

### D-018 — The system is named Achilles

- **Date:** 2026-08-22
- **Status:** `adopted` as the product name. The package/module rename is a separate,
  mechanical change and is **not** implied by this record.
- **Reason:** The user named the system after Achilles, with the stated ambition that it be
  the best of the open-source and locally runnable systems. A name is not decoration for a
  project meant to be given away: the community needs one word for the thing they install,
  distinct from the sentence that describes its architecture.
- **Consequence:** "Achilles" is the product. "Local Sovereign AI" survives as the
  description of what it is — a hardware-aware local sovereign AI kernel — and
  `sovereign_ai` remains the Python package until a deliberate rename is scheduled with its
  own migration, since a package rename touches every import, config path and state
  directory and must not be smuggled in beside research.
- **Safety boundary:** None. This changes naming, not behaviour, authority or licences.
- **Revisit trigger:** A name collision with an existing open-source project in the same
  space would force a rename before public release; check before publishing.

### D-019 — The harness layer is the binding constraint, and it is closed by adoption

- **Date:** 2026-08-22
- **Status:** `adopted` as the current priority ordering.
- **Reason:** Wave 6's audit found a kernel ahead of the field driving an agent loop behind
  every member of it: three tools, no way to edit a file, prose-scraped tool calls, no
  compaction, no undo. Meanwhile the published Terminal-Bench and SWE-bench work shows the
  *same model* scoring materially differently under different harnesses. On this machine,
  where the model is fixed by 12 GB of VRAM, the harness is the only large remaining lever.
- **Consequence:** Until the wave-6 steal order's items 1–5 are done, further model shopping,
  provider integration and desktop features are deprioritised. The parity work is explicitly
  **adoption**: formats, algorithms and mechanisms already proven in Apache-2.0 and MIT
  projects, ported rather than reinvented.
- **Safety boundary:** Adoption is of mechanism, never of authority. Every borrowed tool
  enters through `ExecutionBroker`, `PolicyEngine` and `CapabilityGrant`; a harness's own
  permission model is a UX reference, not a security control. `D-001` is unchanged.
- **Revisit trigger:** If parity work stops changing measured task outcomes in the harness
  tournament, the constraint has moved and this ordering should be re-derived.

### D-020 — Tool calls are grammar-constrained, not parsed out of prose

- **Date:** 2026-08-22
- **Status:** `adopted`; **implemented and live-verified 2026-08-22** (`docs/FIXES.md`
  F-048). The implementation is a JSON schema derived from the registered tools and passed
  through `model_overrides`, rather than a hand-written GBNF file: llama.cpp accepts it, and
  deriving it from `ToolDispatcher` means it cannot drift from the tool plane. Measured on
  `qwen35-9b`: unparsable turns went from **2 of 4 to 0**, and the same task from 4 steps /
  8.3 s to 2 steps / 4.1-4.6 s.
- **Reason:** `NativeAgentLoop` currently locates an action by taking the outermost `{`…`}`
  span of the model's reply and attempting `json.loads`. Every failure costs a full turn at
  6–52 tok/s, and small models fail this far more often than large ones — which is precisely
  the regime we operate in. Constrained decoding makes a malformed action structurally
  impossible instead of recoverable, and the capability is already compiled into the runtime
  we already pinned.
- **Consequence:** The action schema becomes a grammar. The prose parser stays only as a
  fallback for backends that cannot accept a grammar, and its use is recorded as a
  degradation rather than treated as normal operation.
- **Safety boundary:** A grammar constrains *form*, never *authority*. A perfectly formed
  action is still untrusted model output and still passes through policy. Grammar-guided
  generation has its own reported attack surface; it is not a security feature.
- **Revisit trigger:** Measured throughput loss from mask computation large enough to
  outweigh the retries it prevents, on this hardware.

### D-021 — A real editing surface, with undo, before any further autonomy

- **Date:** 2026-08-22
- **Status:** `adopted`. **Implemented 2026-08-22** (`docs/FIXES.md` F-047 for the editing
  surface, F-049 for undo): `write_file`, `edit_file`, `delete_file`, `grep`, `glob` and
  ranged `read_file` exist and are policy-gated, and `kernel/shadow_git.py` gives every
  mutating tool call a restorable file-state checkpoint in a repository separate from the
  user's own `.git`. The recorded deviation stands: `edit_file` uses unique-match
  search/replace rather than the Codex patch envelope, for small-model reliability.
- **Reason:** A coding agent that cannot write a file is not a coding agent. Shell-mediated
  mutation is also the worst available option for review: `run_command` hides *what changed*
  behind *what ran*, which defeats both the approval surface and the verifiers. Separately,
  nothing in the system can currently undo an agent's edit, which is what makes unattended
  operation unreasonable.
- **Consequence:** Adopt Codex's Apache-2.0 `apply_patch` format for edits, add `write_file`,
  ripgrep-backed `grep`, `glob` and ranged `read_file`, and adopt Cline's shadow-git
  checkpoint mechanism — a repository under `state/`, separate from the user's own history,
  committed after each mutating tool call and restorable by run and step. Aider's per-model
  edit-format selection becomes a field on the model registry rather than a global constant.
- **Safety boundary:** Every new tool is policy-gated exactly as `run_command` is today, and
  a patch is *more* reviewable than a shell line, not less. Shadow git is an undo and audit
  mechanism, not a security boundary, and must never contain secrets that policy would keep
  out of the workspace.
- **Revisit trigger:** If a patch format proves unreliable for the models we actually run,
  fall back per-model rather than globally, and record which model needed which format.

### D-022 — Adopt the field's portable agent files: AGENTS.md and SKILL.md

- **Date:** 2026-08-22
- **Status:** `adopted` as formats; our existing skill governance is unchanged.
  **`AGENTS.md` implemented 2026-08-22** (`docs/FIXES.md` F-049), injected explicitly as
  guidance that cannot authorise an action. `SKILL.md` package loading with progressive
  disclosure is not built.
- **Reason:** The project has a `SkillCandidate`→`SkillVersion` evaluation and promotion
  pipeline that almost nothing in the field has, and no way to read a skill anyone in the
  field has actually written. `AGENTS.md` is the de facto per-repository instruction file,
  and the Agent Skills/`SKILL.md` format has been a public specification since 2025-12-18
  with broad reported adoption. Inventing a fourth filename would cost us the community's
  existing work for no benefit.
- **Consequence:** Load `AGENTS.md` as project instructions and `SKILL.md` packages with
  progressive disclosure, then run them through our own candidate/evaluation/promotion gate
  before any of their content is trusted.
- **Safety boundary:** A skill file is untrusted input, exactly like web content or a tool
  description — this is baseline invariant 4 and it applies unchanged. Published research
  already describes supply-chain attacks on skill registries. An imported skill may propose
  procedure; it may never widen authority, and it is evaluated before promotion.
- **Revisit trigger:** A specification change that cannot express our provenance and
  evaluation metadata without a lossy side channel.

### D-023 — Achilles becomes an MCP client, not only an MCP server

- **Date:** 2026-08-22
- **Status:** `adopted`.
- **Reason:** `agents/mcp_bridge.py` exposes our policy-gated tools *to* an external harness,
  which is the correct half to have built first — it proved the authority path. But the
  ecosystem's value flows the other way: every serious harness consumes MCP servers, and the
  most valuable single one for our purposes is Serena (MIT), whose LSP-backed symbol tools
  cover 40+ languages and are explicitly more token-efficient than text search and replace —
  which matters more for us than for anyone with a large context budget.
- **Consequence:** Add an MCP client behind the existing tool registry so external servers
  appear as ordinary discoverable tools, subject to the same policy and grants. Serena is the
  first trial. `ToolRegistry.discover` already prevents the context blow-up that adding many
  servers would otherwise cause.
- **Safety boundary:** `D-009` is unchanged and now cuts both ways: MCP is a transport and
  tool boundary, not an authority boundary. A server's tool descriptions are untrusted text,
  a server's results are untrusted evidence, and no server is reachable outside a grant.
- **Revisit trigger:** If per-server process cost or latency outweighs the tool value on this
  laptop, vendor the two or three servers that earn it and drop the general client.

### D-024 — Adopt ACP alongside AG-UI: one seam faces editors, the other faces our UI

- **Date:** 2026-08-22
- **Status:** `adopted` seam; implementation `trial`.
- **Reason:** `D-014` adopted AG-UI so that a community member can replace our frontend. It
  does not address the other direction: developers who will never adopt our frontend at all
  because they live in Zed, JetBrains, Neovim, Emacs or VS Code. The Agent Client Protocol
  (Apache-2.0, JSON-RPC over stdio) is the field's answer, with native support in Zed and
  JetBrains and a registry since January 2026. Implementing it once is worth more reach than
  any UI work we could do in the same time.
- **Consequence:** Expose the kernel's run/approval/diff/terminal surface over ACP as a second
  client of the same typed seam AG-UI speaks across. Our Tauri desktop remains one client
  among several, exactly as `D-014` intended.
- **Safety boundary:** Identical to `D-014` and `D-009`: ACP is a rendering, streaming and
  permission-*presentation* contract. Nothing arriving over it authorises a mutation, and an
  editor's approval click resolves against a kernel `ApprovalRequest`, never against a
  protocol event on its own.
- **Revisit trigger:** If ACP cannot express approvals, delegations and verification receipts
  without lossy translation, keep the seam and replace the protocol — the same rule `D-014`
  states for AG-UI.

### D-025 — Context is a managed resource, with an explicit budget owner

- **Date:** 2026-08-22
- **Status:** `adopted`. **Implemented 2026-08-22** (`docs/FIXES.md` F-049): `ContextBudget`
  plus deterministic history elision and a per-observation budget, with an
  `agent.context.compacted` event so the prompt shrinks while the audit record does not.
  Prompt-cache reuse (`--cache-reuse`) and context-isolated child runs remain open.
- **Reason:** The loop appends every assistant reply and every observation to history with no
  compaction, into a 16 K operating context, with a flat 4,000-character truncation per
  observation as the only control. On this hardware the context window is a scarcer resource
  than disk or even VRAM, and it is currently the only major resource the kernel does *not*
  arbitrate — while it arbitrates GPU, workspaces and remote quota carefully.
- **Consequence:** Compaction with a preserved working set, per-observation budgets, repo-map
  and retrieval results counted against the same budget, context-isolated child runs so a
  subtask cannot consume the parent's window, and `--cache-reuse` configured so a stable
  prefix is not reprocessed every turn. Treat this as a resource policy in the kernel, not as
  a detail inside one loop.
- **Safety boundary:** Compaction destroys information. The summary is derived, untrusted
  model output; the append-only event journal remains the audit record, and no compaction may
  drop a verification receipt, an approval or a grant from the record — only from the prompt.
- **Revisit trigger:** A model with a materially larger usable context on this machine changes
  the budget, not the principle that someone must own it.

### D-026 — Every surface must be able to start work, and the terminal is the primary one

- **Date:** 2026-08-22
- **Status:** `adopted`. **Partially implemented 2026-08-22** (`docs/FIXES.md` F-048, F-052):
  `sovereign run "<task>"` and `sovereign tools` exist, and the web control surface now has a
  real task composer — both live-verified end to end against a real local model. The
  interactive TUI and the **desktop** task composer this decision also requires are not built.
- **Reason:** Wave 7's first finding is that no surface in this repository can start a task.
  The desktop cancels, lists and resolves; the CLI has no run command; the only door is an
  `@mention` in a chat room, which is a collaboration idea borrowed from Buzz, not a coding
  workflow. A system that cannot be asked to do something is not a product regardless of the
  quality of its kernel.
- **Consequence:** `sovereign run "<task>"` and a task composer in the desktop come before any
  further view work, and the interactive TUI becomes the primary developer surface — built as
  a client of the kernel HTTP API, exactly as opencode and Codex split their TUI from their
  server, which our architecture already supports. The chat room remains a *collaboration*
  surface, not the entry point for work.
- **Safety boundary:** A new entry point is not new authority. Every surface submits an
  ordinary `Job` and is subject to the same policy, grants and approvals; a task typed into a
  TUI is exactly as untrusted as one posted in a room.
- **Revisit trigger:** None for the requirement. Which surface is *primary* may change if
  measured usage says otherwise.

### D-027 — Streaming is a requirement, not an enhancement

- **Date:** 2026-08-22
- **Status:** `adopted`. **Kernel seam implemented 2026-08-22** (`docs/FIXES.md` F-050) and
  **consumed by the web control surface the same day** (F-052), verified live in a browser:
  agent steps, checkpoints and compaction events render as they happen and the four-second
  polls are gone. The **Tauri desktop still polls**, and nothing streams model *tokens* — only
  kernel events — so this decision is satisfied for one surface, not for the product.
- **Reason:** There is no `StreamingResponse`, SSE endpoint, WebSocket or generator anywhere
  in the API, and every view polls on a four-second timer. On hardware measured at 6.36 tok/s
  for the deep brain, that means minutes of undifferentiated waiting followed by a wall of
  text — the worst possible presentation of exactly our weakest property. It also contradicts
  `D-014` in practice: AG-UI was adopted *because* it standardises streaming and human-in-the-
  loop interrupts, and then the opposite was built.
- **Consequence:** Server-sent events over the existing API carrying AG-UI-shaped events;
  tool calls, tokens, step transitions, approvals and job state changes all arrive as they
  happen; the four-second polls are retired rather than supplemented. Zed's Agent Panel is the
  reference for what to show: the tool call as it happens, not only the final answer.
- **Safety boundary:** A streamed event is a *view* of a kernel record, never a substitute for
  one. Approvals resolve against kernel state; a client that missed an event must be able to
  reconcile by reading, and a dropped connection must never lose a durable transition.
- **Revisit trigger:** If SSE cannot express interrupts and resumption cleanly across
  reconnects, upgrade the transport — not the requirement.

### D-028 — An approval must render its own evidence

- **Date:** 2026-08-22
- **Status:** `adopted`. Treated as a **safety** requirement, not a UX preference.
  **Partially implemented 2026-08-22** (`docs/FIXES.md` F-052): the web surface's approval
  card leads with action, scope, subject, the policy's reason and the evidence payload, and
  states plainly when no evidence exists. Using the page also exposed a related lie worth
  recording — a "pre-approve mutations" checkbox that could never work, since only a grant can
  authorise an untrusted mutation; it now issues a real 15-minute scoped grant instead. Still
  missing: the exact command or diff, the triggering rule, and once/session/always
  gradations.
- **Reason:** The approval card currently shows a subject id, an `action:scope` string, a risk
  badge and free text. It does not show the command, the diff, the files, the policy rule that
  triggered the request, what the resulting grant permits, when it expires, or what denial
  costs. An operator asked repeatedly to authorise things they cannot see learns to click
  Approve, which silently converts the project's strongest safety mechanism into a rubber
  stamp. The 2026 agentic-UX literature is blunt that absent explanation is the strongest
  driver of both distrust and abandonment.
- **Consequence:** The approval surface becomes an evidence surface: exact action, rendered
  diff or command, triggering rule, requested grant scope and expiry, consequence of denial,
  and the run it belongs to. Approve/Deny gains once / this-session / always-in-this-workspace
  gradations, each backed by a real `CapabilityGrant` with a real expiry rather than by a
  client-side preference.
- **Safety boundary:** Gradations widen convenience, never scope. "Always" means a persisted,
  revocable, expiring grant with a named scope — never an unbounded permission, and never one
  a model can request into existence without a human resolution.
- **Revisit trigger:** Evidence of approval fatigue in real use (a high approve rate with low
  read time) means the *policy* is asking too often, and should be re-tuned rather than the UI
  made faster to click through.

### D-029 — Latency legibility is a differentiator, and we design for it rather than hiding it

- **Date:** 2026-08-22
- **Status:** `adopted` as an experience principle.
- **Reason:** Every competing product is designed around cloud inference that is effectively
  instantaneous and effectively unlimited, so hiding latency is rational for them. Ours is
  measured: 6.36 tok/s deep, 49.57 tok/s fast, tens of seconds of model load, a hard 12 GB
  ceiling. A spinner communicates "broken"; a tokens/second readout, a context meter, a VRAM
  gauge, a load-progress bar in gigabytes and a marker of which brain answered communicate
  "working, and here is why it costs what it costs". The kernel already knows every one of
  these numbers and displays none of them.
- **Consequence:** Status line and gauges wherever a run is visible, plus an explicit
  escalate-to-deep-brain control so the user chooses the trade rather than suffering it.
- **Safety boundary:** None, except that displayed telemetry must be measured rather than
  estimated — a fabricated progress bar is worse than none.
- **Revisit trigger:** Hardware fast enough that latency stops being perceptible would make
  this decoration; that is not this machine and will not be most of our audience's.

### D-030 — Authority legibility is the category we can win outright

- **Date:** 2026-08-22
- **Status:** `adopted` as an experience principle and a product thesis.
- **Reason:** No open competitor can render *why an action was allowed* because none of them
  has the data. We have policy decisions with reasons, expiring grants, leases, trust labels
  on every event, verification receipts and a hash-chained journal, and we render essentially
  none of it. This is the one axis where parity is not the ceiling: a run inspector that
  replays each step with its trust label and verifier result, and a "why was this allowed?"
  answer one click from any action, is something the field structurally cannot copy quickly.
- **Consequence:** The audit model becomes a first-class product surface rather than a
  forensic backend: run replay, per-step trust and verification, grant and lease inspectors,
  and provenance shown next to any answer derived from memory or the web.
- **Safety boundary:** Displaying provenance must not leak scoped or private memory into a
  context that policy would not have allowed; the inspector obeys the same memory scope ACLs
  as the agents do.
- **Revisit trigger:** None. If a competitor builds an authority model this rich, that is a
  win for the field and we will still have ours.

### D-031 — Accessibility, theming and error recovery are release gates

- **Date:** 2026-08-22
- **Status:** `adopted`.
- **Reason:** Across the entire desktop app and web page there is a single
  `aria-`/`role=`/`onKeyDown`/`tabIndex` occurrence; errors surface as raw
  `GET /path -> 500` strings; and a failed first connection leaves the app permanently dead
  with no retry. A project whose stated purpose is to be given to people underserved by
  commercial tools cannot ship an interface that excludes people by omission, and a local
  system whose backend is a set of processes on the user's own machine will fail to connect
  regularly — that is a normal state to design for, not an exception.
- **Consequence:** Keyboard paths, focus management, labelled controls, light/dark and font
  scaling, a reconnecting client, human-readable failures that name the next action (usually
  `scripts/doctor.py`), and completion notifications for long runs. These are gates on the
  first public release, not backlog polish.
- **Safety boundary:** None.
- **Revisit trigger:** None.

### D-032 — First run must include hardware autotune, because we do not know the user's machine

- **Date:** 2026-08-22
- **Status:** `adopted`; implementation `trial`.
- **Reason:** The mission is that other people run this on hardware we have never seen and
  adapt it. Today that means reading a YAML manifest, running a PowerShell installer and
  interpreting `doctor.py`. Meanwhile the local-model field has already solved the
  presentation problem: LM Studio shows disk size, RAM and VRAM requirements and quantisation
  *before* download and offers side-by-side comparison; Jan labels models "fast", "balanced"
  and "high-quality" rather than by parameter count. We have something better than either —
  `benchmark_brains.py`, the `-ncmoe` sweep methodology from F-012 and a local benchmark DB
  that already overrides internet priors — and we make the user drive it by hand.
- **Consequence:** A first-run experience that detects the machine, states plainly what it can
  run, sweeps the offload operating point the way F-012 did by hand, writes the result into the
  local benchmark DB, and presents models by what they will actually do on *this* GPU rather
  than by parameter count.
- **Safety boundary:** Autotune measures and recommends; it never accepts a licence, never
  downloads a gated checkpoint on the user's behalf, and never promotes a model past the
  existing evaluation gates. `D-016`'s personal-overlay boundary is unchanged.
- **Revisit trigger:** If sweeping proves too slow to run at install time, split it into a fast
  detection pass and a background refinement job rather than dropping it.

### D-033 — The repository carries an Apache-2.0 licence, and that comes before everything else

- **Date:** 2026-08-22
- **Status:** `adopted`, blocking. **Implemented 2026-08-22** (`docs/FIXES.md` F-046):
  `LICENSE` (canonical Apache-2.0 text, fetched from apache.org rather than retyped),
  `NOTICE`, `license`/`license-files`/classifiers in `pyproject.toml`, `CONTRIBUTING.md`
  and a disclosure-policy `SECURITY.md` distinct from the architecture document.
- **Reason:** There was no `LICENSE` file and no `license` field in `pyproject.toml`. Under
  default copyright law the work is all-rights-reserved: nobody may legally copy, modify or
  redistribute it. Baseline invariant 8 — the invariant this ledger applies as a gate to every
  other project's licence before adopting it — is therefore currently violated by us and by
  nobody else. Apache-2.0 is the correct choice because it is what we demand of the components
  we adopt, it carries an explicit patent grant, and it is compatible with the Apache-2.0 and
  MIT upstreams we intend to port from.
- **Consequence:** `LICENSE`, the `pyproject.toml` field, per-file attribution where code is
  ported (Codex's `apply_patch`, Cline's checkpoint approach, Aider's repo map), and a
  `NOTICE` recording those origins. Model weights keep their own separate licences and the
  `D-016` personal-overlay boundary is unchanged.
- **Safety boundary:** Licensing our code does not relicense anything we adopt; ported code
  keeps its own notice, and no non-OSI model weight becomes shippable because the repository
  is now licensed.
- **Revisit trigger:** None. A different OSI licence could be argued, but no licence at all
  cannot.

### D-034 — A capability is not delivered until an agent can invoke it

- **Date:** 2026-08-22
- **Status:** `adopted` as the project's definition of done. **Tool plane implemented
  2026-08-22** (`docs/FIXES.md` F-047): 13 tools registered, covering files, search,
  execution, specialists, media, memory and web. Seven specialist workers still return
  HTTP 501 and `ComputerController` still has no controllers, so those domains are now
  *reachable-but-unimplemented* rather than unreachable.
- **Reason:** Wave 8's reachability table found nineteen of twenty-one capability domains
  unreachable by the agent loop: `ToolRegistry` holds zero tools, `ComputerController` holds
  zero controllers, seven of fourteen workers return HTTP 501, SearXNG is deployed with no
  client, and `ContextBuilder` is constructed but never called. Installed weights, a worker
  port and a manifest entry are three different things, and none of them is a capability.
- **Consequence:** The tool plane becomes the product boundary. Every capability must be
  registered as a `ToolSpec`, dispatchable from the agent loop through the existing policy and
  grant path, and covered by an end-to-end smoke test that starts at an agent turn and ends at
  a verified result. `docs/IMPLEMENTATION_STATUS.md` gains a reachability column, and the
  README stops listing unreachable capabilities as features.
- **Safety boundary:** Reachability multiplies blast radius. Every newly reachable tool needs
  its risk scope, grant requirement and verifier defined *before* it is registered, not after;
  a tool that can generate media, control a computer or query the web is not equivalent to
  `read_file` and must not inherit its defaults.
- **Revisit trigger:** None.

### D-035 — Cross-platform support is a mission requirement, not a roadmap item

- **Date:** 2026-08-22
- **Status:** `adopted`; Linux first, Apple Silicon second.
- **Reason:** Every installation path is PowerShell plus WSL2; the shell scripts run *inside*
  WSL rather than on Linux. The stated audience — people who cannot or will not pay for a
  subscription — is disproportionately on Linux, and Apple Silicon's unified memory is among
  the best consumer hardware in existence for local inference. We currently serve neither. A
  system that only runs on the author's operating system is a personal tool, not a donation to
  a community.
- **Consequence:** A Linux install path that does not assume WSL, then an Apple Silicon path
  (Metal through llama.cpp, which already supports it). The Windows/WSL2 bridge remains
  first-class and stays our differentiator, since it is the platform the field serves worst.
- **Safety boundary:** Each platform needs its own execution-isolation story. OpenShell/WSL2
  does not transfer: Linux needs Landlock/seccomp/bubblewrap, macOS needs Seatbelt. A platform
  is not supported until its sandbox path is, and shipping an unsandboxed platform is worse
  than not shipping it.
- **Revisit trigger:** None.

### D-036 — Prompts are optimised by evidence, not written by hand

- **Date:** 2026-08-22
- **Status:** `adopted` principle; GEPA/ACE `trial`.
- **Reason:** The system prompt that decides whether every local model turn produces a usable
  action is a hand-written string constant in `native_loop.py`. GEPA reports 10–20% accuracy
  gains over reinforcement-learning and prompt-optimiser baselines with up to 35× fewer
  rollouts, by reflecting over execution traces; ACE evolves a persistent playbook through a
  generator–reflector–curator loop. Both need exactly two things we already have and almost
  nobody else in the open field does: **a reproducible task set and an evaluation harness**
  (`harness_tasks.py`, `harness_tournament.py`, `evaluate_brain_quality.py`). On a machine
  where the model cannot be made larger, the prompt and the context are the tunable parameters.
- **Consequence:** Prompts, tool descriptions and the playbook become versioned, evaluated
  artifacts under the existing `SkillCandidate`→`SkillVersion` governance, optimised against
  our own task set and promoted only on measured improvement.
- **Safety boundary:** An optimiser may rewrite instructions; it may never rewrite policy,
  authority, tool risk scopes or its own evaluator. An evolved playbook is a `SkillCandidate`,
  which means untrusted until evaluated — the self-modification boundary in this ledger's
  explicit non-decisions is unchanged.
- **Revisit trigger:** If optimisation gains do not survive on this machine's models, keep the
  versioned-prompt infrastructure and drop the optimiser.

### D-037 — Untrusted content needs an architectural defence before web, browser or MCP tools ship

- **Date:** 2026-08-22
- **Status:** `adopted`, blocking for the tools it names.
- **Reason:** The kernel's answer to hostile content is trust labels on events and the
  principle that conversation is not authorization. That is necessary and insufficient: a
  label records *where text came from*, it does not stop an injected instruction inside that
  text from reaching a planner that holds tools. The 2026 literature has converged on
  structural defences — CaMeL's privileged/quarantined LLM split with a data-flow-tracking
  interpreter and capability-based policy, plus FIDES, Progent and RTBAS — precisely because
  prompting-based mitigation keeps failing (a purpose-built protective model was bypassed at a
  reported 36% rate with standard encoding tricks). We are about to add a web tool, a browser,
  an MCP client and community-authored skills, which is four new injection surfaces at once.
- **Consequence:** A quarantined path for untrusted content: the model that reads web pages,
  documents, tool descriptions, MCP results and skill files does not hold tools; the
  privileged planner sees derived, typed, provenance-tagged values rather than raw hostile
  text; and tool calls are checked against a policy that knows which values are tainted. Our
  `CapabilityGrant` and `PolicyEngine` are already the reference monitor this design needs —
  we have the hard half and are missing the split.
- **Safety boundary:** This is a mitigation, not a solution; published work is explicit that no
  current defence is complete. Nothing here permits relaxing sandboxing, grants or approvals
  because a defence exists.
- **Revisit trigger:** A stronger published architecture, or measured evidence that our split
  breaks legitimate workflows badly enough to need redesign rather than tuning.

### D-038 — Memory that is not in the loop is not memory

- **Date:** 2026-08-22
- **Status:** `adopted`.
- **Reason:** `ContextBuilder` is constructed in `kernel/app.py` and never called by any
  request path; `job_executor`'s chat branch passes messages straight to inference. Four
  retrieval models totalling tens of gigabytes serve a path nothing takes. The project has
  argued about memory *providers* for five waves without connecting the one it has.
- **Consequence:** Retrieval enters the agent loop as an explicit, budgeted step — recalled
  items counted against the context budget of `D-025`, carrying provenance, and visible in the
  UI per `D-030`. Writing memory becomes an explicit tool with scope, not an invisible side
  effect. LEANN-class index economics (reported <5% storage overhead at >90% recall@3) become
  the trial target once the path exists, since indexing a whole machine is the actual goal.
- **Safety boundary:** Memory scope ACLs (F-033) apply at recall time and are enforced by the
  kernel, not by the loop. Recalled content is untrusted input and inherits `D-037`'s handling
  exactly as web content does.
- **Revisit trigger:** None for the requirement; the provider question stays open per `D-002`.

### D-039 — Voice is a first-class modality, and realtime is the point

- **Date:** 2026-08-22
- **Status:** `adopted` direction; duplex stack `trial`.
- **Reason:** The manifest carries a strong batch speech stack — Qwen3-ASR, Whisper turbo,
  forced alignment, diarization, VoxCPM2 TTS — none of it reachable by an agent and none of it
  interactive. Meanwhile the open field has full-duplex speech-to-speech at ~160 ms, mature
  orchestration frameworks (Pipecat 1.0, LiveKit Agents), and several Apache-2.0/MIT TTS
  models. Voice is also the modality where local is not a preference but a precondition:
  medical, legal and personal audio cannot be sent to a subscription service at all.
- **Consequence:** A streaming path — partial ASR, barge-in, incremental TTS — behind the
  existing worker plane, orchestrated by the kernel rather than by a second framework, and
  exposed as agent tools per `D-034`.
- **Safety boundary:** Always-on audio is a surveillance surface. Capture requires an explicit,
  revocable, visibly indicated grant with local-only retention by default; a wake word is not
  consent to record continuously, and transcripts inherit memory scope rules.
- **Revisit trigger:** If duplex quality on this hardware cannot beat cascaded ASR→LLM→TTS,
  ship the cascade and keep the seam.

### D-040 — Distribution is a feature: CI, signed releases, and an updater

- **Date:** 2026-08-22
- **Status:** `adopted`.
- **Reason:** 153 tests exist and nothing runs them on a change; there is no `.github/`, no
  tags, no changelog, no signed artifact and no update path. Tauri 2's bundler already produces
  MSI/NSIS, DMG and deb/rpm/AppImage with a cryptographically signed updater — the packaging
  problem is solved upstream and simply not adopted. For an audience installing on hardware we
  have never seen, the install and update experience *is* the product's first impression.
- **Consequence:** CI running the existing suite plus lint and link checks; versioned releases
  with a changelog; signed installers per platform; an updater; and a documented rollback.
- **Safety boundary:** An auto-updater is remote code execution by design. Signing and a
  user-visible, declinable update are requirements, not options, and the updater must never be
  able to change policy, grants or model licence scope silently.
- **Revisit trigger:** None.

### D-041 — Scale-out uses the machines the user already owns

- **Date:** 2026-08-22
- **Status:** `trial`.
- **Reason:** The ceiling on this project is 12 GB of VRAM, and the two conventional answers
  are "buy a subscription" (excluded by invariant 8) or "buy a bigger GPU" (excluded by our
  audience's circumstances). A third answer exists and is measured: prima.cpp reports running
  30–70B models across heterogeneous home clusters with 5–17× lower time-per-output-token than
  llama.cpp, exo and dllama, and llama.cpp's own RPC backend already distributes across hosts.
  Most of our audience owns more than one computer.
- **Consequence:** A distributed backend behind the existing inference adapter plane, treated
  exactly like any other engine: measured on this hardware, promoted only on evidence, and
  never required for single-machine operation.
- **Safety boundary:** Cluster members are a trust boundary. Weights and prompts crossing a
  home network need authentication and encryption, and a peer must never inherit kernel
  authority — the split-brain invariant applies to hosts as much as to harnesses.
- **Revisit trigger:** If network latency dominates on realistic home networking, record the
  negative result and close the option rather than leaving it aspirational.

### D-042 — On-device personalisation is a differentiator we should actually build

- **Date:** 2026-08-22
- **Status:** `trial` after the tool plane and harness parity.
- **Reason:** A subscription agent cannot train on a user's private codebase; we can, on the
  user's own GPU, while they sleep. Unsloth reports roughly 2× faster LoRA/QLoRA at about half
  the VRAM, and continual-adapter work (O-LoRA and successors) addresses the catastrophic
  forgetting that makes naive sequential fine-tuning useless. This is one of the few
  capabilities where open-source-and-local is strictly *more* capable, not merely cheaper.
- **Consequence:** An adapter-training job kind in the existing durable job system, with
  training data drawn only from explicitly scoped local sources, adapters versioned and
  A/B-evaluated through the existing quality harness, and promotion gated the same way models
  are.
- **Safety boundary:** Training data selection is a privacy decision, not a convenience: only
  explicitly scoped sources, never secrets, never other users' scopes, and an adapter is a
  `SkillVersion`-class artifact that cannot alter policy. A model fine-tuned on private data
  must never be shipped in a shared profile.
- **Revisit trigger:** If measured gains on real tasks do not justify hours of GPU time the
  user could spend running the model, record it and stop.

## Recommended experiment order

This order adds information without destabilizing the first physical build.

**Phase 0, added by wave 8 and preceding every item below:** add `LICENSE` (Apache-2.0) and
the `pyproject.toml` licence field, a CI workflow running the existing 153 tests, a
contribution path and a vulnerability-reporting policy (`D-033`); then register real tools in
`ToolRegistry` and give the agent loop a dispatcher into them (`D-034`), which is what makes
nineteen already-installed capability domains reachable at all.

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
15. **Harness parity slice.** Wave 6's steal order, items 1-5: grammar-constrained tool
   calls, a real edit/search tool surface, shadow-git undo, context compaction, and
   `AGENTS.md`/`SKILL.md` loading. `D-019` places this **ahead of** items 12-14 for any
   further work: they add reach to a loop that cannot yet edit a file.
16. **Ecosystem slice.** MCP client (Serena first), repo map, CodeAct mode and the FastApply
   specialist, each measured in the tournament rather than assumed.
17. **Experience slice (wave 7).** Runs *interleaved with* 15-16, not after them: task entry
   on every surface, SSE streaming replacing the polls, rendered markdown/diffs with per-hunk
   review, the approval evidence card, then the TUI. `D-026`-`D-028` are prerequisites for
   anyone but us being able to use the harness work at all.
18. **Reach slice.** ACP server, hooks/permission modes with fast-brain pre-screening,
   worktree-per-run, OTel GenAI export, Terminal-Bench task import.
19. **Adoption slice.** Latency and authority legibility surfaces, accessibility and theming
   gates, first-run hardware autotune, session resume/fork/search.
20. **Category-of-one slice (wave 8).** GEPA/ACE prompt optimisation; the quarantined-LLM
   injection defence **before** any web, browser, MCP or community-skill tool ships; browser
   control; a LEANN-class personal index; realtime voice; prima.cpp scale-out; LoRA
   personalisation; cross-platform packaging and signed releases.

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
- describing an installed checkpoint, an open worker port or a manifest entry as a capability
  of this system before an agent can invoke it and a smoke test proves it end to end (`D-034`);
- shipping a web, browser, MCP or community-skill tool before the quarantined-content defence
  exists (`D-037`);
- letting a prompt or context optimiser modify policy, authority, tool risk scopes or its own
  evaluator (`D-036`);
- training an adapter on data outside an explicitly scoped source, or shipping a
  privately-fine-tuned adapter in a shared profile (`D-042`).

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
- Does grammar-constrained decoding cost more throughput on this GPU than the retries it
  removes, and at what action-schema complexity does that flip?
- Does a code-action loop (CodeAct) beat a JSON-action loop on *our* models, or does it only
  pay off above some tool-use training threshold the local candidates do not meet?
- Can a 1.5B FastApply specialist and the deep brain be co-resident within 12 GB, or does the
  merge model have to share the fast brain's slot?
- Is one shadow-git repository per workspace enough, or does worktree-per-run need one each?
- Which of our internal event types map cleanly onto OpenTelemetry GenAI spans, and which
  would be lossy enough that exporting them would mislead?
- Does AG-UI's event vocabulary cover approval evidence, grant scope and verification
  receipts, or does authority legibility need our own events carried alongside it?
- What is the right default autonomy level on first run, given that the literature says
  overreaching on day one gets a product turned off on day two?
- Should the TUI and the desktop share one rendering model (both clients of the same event
  stream) or diverge deliberately, and what does that cost in duplicated review UI?
- Can an approval card render a diff *before* the edit is applied without giving the loop
  write access first, or does evidence-first approval require a staged-write mechanism?
- What is the right granularity for a capability tool: one `invoke_specialist` tool with a
  model argument, or a named tool per capability that `ToolRegistry.discover` filters?
- Can a quarantined-LLM split run on this hardware without doubling latency, given that both
  the privileged and quarantined roles would contend for the same 12 GB?
- Does GEPA-style optimisation transfer across models, or does every model in the registry
  need its own optimised prompt set - and if the latter, what does that cost per model?
- Which sandbox primitive replaces OpenShell on Linux and macOS, and does the execution
  conformance suite pass identically on all three?
- Is an unreachable-but-installed model worth its disk at all, or should install profiles be
  regenerated from the reachability table rather than from the manifest?

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

Added 2026-08-22 (wave 6):

- [openai/codex](https://github.com/openai/codex) — Apache-2.0 CLI, `apply_patch`, sandbox backends
- [oraios/serena](https://github.com/oraios/serena) — MIT, LSP-backed symbol tools over MCP
- [kortix-ai/fast-apply](https://github.com/kortix-ai/fast-apply) — Apache-2.0 edit-merge models
- [Kortix/FastApply-1.5B-v1.0](https://huggingface.co/Kortix/FastApply-1.5B-v1.0)
- [Agent Client Protocol](https://zed.dev/acp) — Apache-2.0 editor/agent JSON-RPC standard
- [Aider repo map with tree-sitter](https://aider.chat/2023/10/22/repomap.html)
- [OpenHands CodeAct agent](https://github.com/OpenHands/OpenHands/blob/main/openhands/agenthub/codeact_agent/README.md)
- [Executable Code Actions Elicit Better LLM Agents (CodeAct, ICML 2024)](https://arxiv.org/pdf/2402.01030)
- [cline/cline checkpoints documentation](https://github.com/cline/cline/blob/main/docs/core-workflows/checkpoints.mdx)
- [llama.cpp grammar and structured output](https://deepwiki.com/ggml-org/llama.cpp/7.3-grammar-and-structured-output)
- [guidance-ai/llguidance](https://github.com/guidance-ai/llguidance)
- [mlc-ai/xgrammar](https://github.com/mlc-ai/xgrammar)
- [llama.cpp KV cache reuse with llama-server](https://github.com/ggml-org/llama.cpp/discussions/13606)
- [Claude Code hooks reference](https://code.claude.com/docs/en/hooks) — `unverified` here; vendor documentation, not inspected
- [OpenTelemetry AI agent observability](https://opentelemetry.io/blog/2025/ai-agent-observability/)
- [Terminal-Bench v2.1 leaderboard](https://artificialanalysis.ai/evaluations/terminalbench-v2-1)
- [Self-Healing Agentic Orchestrators (arXiv 2606.01416)](https://arxiv.org/pdf/2606.01416)

Added 2026-08-22 (wave 7, experience):

- [Zed Agent Panel documentation](https://zed.dev/docs/ai/agent-panel)
- [Cline checkpoints and diff review](https://docs.cline.bot/core-workflows/checkpoints)
- [opencode TUI commands and keybindings](https://deepwiki.com/anomalyco/opencode/9.2-tui-commands-and-keybindings)
- [OpenHands multi-pane GUI and entry points](https://www.openhands.dev/blog/opencode-vs-openhands)
- [Claude Code status line documentation](https://code.claude.com/docs/en/statusline) — `unverified`; vendor documentation, not inspected
- [Local LLM tooling UX comparison (LM Studio, Jan, Ollama)](https://www.sitepoint.com/local-llms-are-getting-easier-the-complete-guide-2026/)
- [Agentic UX patterns for permission, evidence and recovery](https://mantlr.com/blog/designing-for-ai-agents-ux-patterns-2026)
- [UI design principles for AI agents, 2026](https://fuselabcreative.com/ui-design-for-ai-agents/)

Added 2026-08-22 (wave 8, total capability audit):

- [gepa-ai/gepa](https://github.com/gepa-ai/gepa) - reflective prompt evolution, DSPy/MCP/Terminal-Bench adapters
- [Agentic Context Engineering (ACE)](https://arxiv.org/pdf/2510.04618)
- [CaMeL: defeating prompt injection by design](https://arxiv.org/pdf/2505.22852)
- [CaMeLs Can Use Computers Too - system-level security for computer-use agents](https://arxiv.org/pdf/2601.09923)
- [Indirect prompt injection: 2026 state of the art](https://zylos.ai/research/2026-04-12-indirect-prompt-injection-defenses-agents-untrusted-content/)
- [tldrsec/prompt-injection-defenses](https://github.com/tldrsec/prompt-injection-defenses)
- [LEANN: a low-storage vector index for personal devices](https://arxiv.org/abs/2506.08276)
- [prima.cpp: 30-70B inference on heterogeneous home clusters](https://arxiv.org/html/2504.08791v2)
- [llama.cpp multi-GPU and distributed inference](https://deepwiki.com/ggml-org/llama.cpp/8.4-multi-gpu-and-distributed-inference)
- [Unsloth LoRA/QLoRA fine-tuning documentation](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide/lora-hyperparameters-guide)
- [OpenCUA: open foundations for computer-use agents](https://opencua.xlang.ai/)
- [Holo-1 open-weight GUI grounding models](https://nextomoro.com/holo-1/)
- [Browser Use](https://github.com/browser-use/browser-use) - leading open browser-agent framework
- [OmniDocBench document parsing benchmark](https://github.com/opendatalab/OmniDocBench)
- [PaddleOCR-VL technical report](https://arxiv.org/html/2510.14528v1)
- [LTX-2.5 open-weights video model](https://datanorth.ai/news/ltx-releases-ltx-2-5-open-weights-video-world-model)
- [SGLang structured outputs and RadixAttention](https://docs.sglang.io/docs/advanced_features/structured_outputs)
- [Pipecat and LiveKit open voice-agent stacks](https://techsy.io/en/blog/best-open-source-voice-agent-frameworks)
- [Moshi full-duplex speech](https://localaimaster.com/blog/moshi-realtime-speech-guide)
- [Tauri 2 bundler and signed updater](https://vanja.io/tauri-2-new-default/)

## Change history

### 2026-08-22 - Wave 8: the total capability audit

- Audited every modality the name implies - audio, speech, vision, documents, images, video,
  music, science, browser, computer control, memory, learning, security, distribution and
  scale-out - against the standard the user set: a person finding this should be surprised it
  is not proprietary.
- **Truth correction 1: the manifest is not the system.** `ToolRegistry` holds zero tools;
  `ComputerController` holds zero controllers; seven of fourteen workers return HTTP 501;
  SearXNG is deployed with no client; `ContextBuilder` is never called. The reachability table
  records the result: **nineteen of twenty-one capability domains cannot be invoked by the
  agent**, including every one of the ~290 GB of specialist weights the workstation profile
  installs.
- **Truth correction 2: the project is not, today, open source.** There is no `LICENSE` file
  and no licence field, which makes the work all-rights-reserved and puts us in violation of
  our own baseline invariant 8. There is also no CI for 153 existing tests, no release or
  update path, no contribution path, and no Linux or Apple Silicon install path at all.
- Added the axes waves 6 and 7 missed entirely: automatic prompt/context optimisation
  (GEPA/ACE), on-device LoRA personalisation, agent-shaped serving (SGLang RadixAttention),
  browser agency, open GUI-grounding models that now include Apache-2.0 options, architectural
  prompt-injection defence (CaMeL and successors), low-storage personal indexing (LEANN),
  document conversion and office-document *generation*, realtime duplex voice, and
  home-cluster scale-out (prima.cpp, llama.cpp RPC).
- Named the six capabilities a subscription product structurally cannot offer, as the honest
  answer to "why is this open source": weights that learn your codebase, an index of your whole
  machine, voice that never leaves the room, use of hardware you already own, provable audit,
  and every modality under one authority domain.
- Adopted `D-033` through `D-042`, and put two things ahead of every previously recorded
  priority: the licence and CI (`D-033`), then the tool plane (`D-034`).

### 2026-08-22 — Wave 7: the experience audit

- Corrected wave 6's own omission: it compressed the entire experience layer into three table
  rows. For a system meant to replace a daily-driver coding agent, interaction design is a
  first-class axis, and it is where this repository is furthest behind.
- Audited every surface against its source — `web/index.html`, all five desktop views, the
  Tauri client and the Typer CLI — and recorded twenty findings with severities. Six are `S1`:
  **no surface can start work**, **nothing streams anywhere**, **the approval card hides its
  own evidence**, no diff view exists, agent output renders as plain text, and there is no
  terminal interface at all. Accessibility measured a single attribute across the whole UI.
- Named the best-in-class source for each experience parameter — Zed for live tool-call
  visibility and per-hunk diff review, Cline for checkpoint navigation, Codex and opencode for
  the terminal, Claude Code for terminal quality-of-life mechanisms, OpenHands for the
  multi-pane workspace, LM Studio and Jan for local-model onboarding.
- Identified the two categories where we can lead rather than match: **latency legibility**
  (nobody designing for cloud inference has a reason to render tokens/second, VRAM pressure or
  model-load progress) and **authority legibility** (nobody else has grants, leases, trust
  labels and verification receipts to render at all).
- Adopted `D-026` through `D-032`: task entry on every surface with the terminal primary,
  streaming as a requirement, approval-as-evidence treated as a safety requirement, latency and
  authority legibility as product theses, accessibility/theming/recovery as release gates, and
  first-run hardware autotune.
- Revised the framing: the harness is the binding constraint on **capability**; the experience
  layer is the binding constraint on **adoption**.

### 2026-08-22 — Wave 6: the harness capability audit, and the name

- Named the system **Achilles** (`D-018`); "Local Sovereign AI" survives as the architecture
  description and `sovereign_ai` remains the package until a deliberate rename is scheduled.
- Audited this repository's own agent loop against Claude Code, Codex CLI and the open-source
  harness field across roughly thirty parameters, and recorded the correction that follows:
  **the kernel is ahead of the field and the harness is behind all of it**. The loop has three
  tools, cannot write a file, scrapes tool calls out of prose, never compacts context and
  cannot undo an edit.
- Recorded, for each parameter, who already does it best and whether to steal, build or leave
  it — plus the list of things we are already ahead on and must not rebuild.
- Adopted seven consequences: harness parity by adoption before further model or provider work
  (`D-019`), grammar-constrained tool calls (`D-020`), a real editing surface with shadow-git
  undo (`D-021`), the portable `AGENTS.md`/`SKILL.md` formats under our own skill governance
  (`D-022`), an MCP client to match the existing MCP server (`D-023`), ACP alongside AG-UI so
  the kernel reaches editors as well as our own UI (`D-024`), and context as a kernel-arbitrated
  resource (`D-025`).
- Added the agentic-training axis to the model question: Qwen3-Coder-Next and Devstral 2 are
  permissively licensed, sparse-active and explicitly trained for coding-agent scaffolds, so
  `D-012`'s hardware principle and invariant 8 point at the same shortlist for the first time.

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
