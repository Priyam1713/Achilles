# Architecture

## North star

Build the best useful local AI system this workstation can sustain, not the largest model zoo it can store.

A component earns its place only if it improves at least one of: **capability, quality, reliability, security, or efficiency on this exact machine**.

## Planes

```text
                         EXPERIENCE
  desktop • voice • API • CLI • web • rooms • inbox • agent roster
                             │
                             ▼
┌────────────────────────────────────────────────────────────┐
│                  AGENCY / ROSTER DOMAIN                    │
│ profiles • roles • teams • inboxes • delegation • presence│
│ schedules • budgets • private/shared scoped context       │
└─────────────────────────────┬──────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────┐
│                         AI KERNEL                          │
│ jobs • runs • state • policy • routing • transactions    │
│ checkpoints • provenance • audit • recovery • events     │
│ workflow DAGs • grants • approvals • leases • secrets    │
└───────────────┬────────────────┬────────────────┬──────────┘
                │                │                │
                ▼                ▼                ▼
         INTELLIGENCE        EXECUTION          MEMORY
         agent loops         OpenShell          episodic
         fast brain          Docker fallback    semantic
         deep brain          computer ctrl      procedural
         specialists         tools              knowledge
                │                │                │
                └────────────────┼────────────────┘
                                 ▼
┌────────────────────────────────────────────────────────────┐
│                     CAPABILITY FABRIC                      │
│ text • vision • GUI • audio • documents • image • video  │
│ retrieval • data • science • formal proof • geometry     │
└───────────────────────────────┬────────────────────────────┘
                                ▼
┌────────────────────────────────────────────────────────────┐
│                      INFERENCE FABRIC                      │
│ llama.cpp • vLLM • SGLang • HF workers • WanGP • Pulsar │
└───────────────────────────────┬────────────────────────────┘
                                ▼
┌────────────────────────────────────────────────────────────┐
│                       RESOURCE FABRIC                      │
│             12 GB VRAM ↔ 32 GB RAM ↔ NVMe                │
│ residency • eviction • cache • quant • prefetch          │
└────────────────────────────────────────────────────────────┘

               VERIFICATION → LEARNING/EVAL
```

## Persistent agency and the roster domain

An agent is a durable logical coworker, not a permanently running model or process. An
`AgentProfile` may outlive every model, harness, prompt, skill version and sandbox assigned
to it. When idle, it consumes durable storage only; the kernel allocates computation for a
specific run when an event, schedule or delegation creates work.

The roster is a domain view backed by kernel primitives, not a second authority plane:

- `AgentProfile` stores identity, role, routing preferences, memory scopes, budgets and
  maximum authority ceilings.
- `Job` records the requested outcome; `Run` records one attempt with an exact model,
  agent-loop adapter, prompt/skill versions, workspace and resource leases.
- `Delegation` is a structured parent-child contract with inputs, expected artifacts,
  acceptance tests, requested authority, deadline and budget.
- `CapabilityGrant`, `WorkspaceLease` and `ResourceLease` are explicit, expiring, run-scoped
  kernel decisions. A profile's authority ceiling never grants authority by itself.
- mailboxes and presence are projections of the append-only event journal. Presence is
  derived from active runs and health evidence, not self-asserted by a model.
- collaboration identities are channel addresses that reference an agent profile; they do
  not become a second identity database.

Room messages may propose work, but only the kernel can validate a delegation, issue grants,
create a run or resolve an approval. Rooms render job/delegation/verification cards as views
of canonical kernel records rather than becoming the execution source of truth.

Models and harnesses are allocated per run. Ten rostered agents should normally mean zero,
one or two active inference streams on this workstation—not ten resident LLMs.

## Primary human experience

The intended primary human surface is a local desktop control center, informed by selected
Apache-licensed interaction and component patterns from Block Buzz but backed only by the
sovereign kernel. The existing web control surface remains the bootstrap/recovery UI; the
CLI remains the operator, scripting and diagnostics interface.

The desktop renderer is never an authority. Agent profiles, jobs/runs, rooms, approvals,
workflows, memory, audit, resources and computer sessions are typed kernel views and commands.
Any Buzz-derived component has its relay/Nostr assumptions replaced with kernel view models;
the Buzz backend, identity, workflow, job and storage systems are not imported.

## Why no single agent framework is the foundation

Agent frameworks change much faster than the invariants of a trustworthy local system. The kernel keeps these invariant concerns outside the harness:

1. authority and trust
2. resource allocation
3. secret handling
4. job durability
5. transaction boundaries
6. verification
7. audit/provenance
8. capability routing
9. model/runtime benchmarking

DeepSeek Harness, OpenClaw-like gateways, AgentArk-like learning loops, coding agents, research agents and future frameworks can register an `AgentLoop` adapter. None receives implicit host authority.

## Native collaboration plane

The fun, useful collaboration patterns are implemented locally without adopting another
application runtime. SQLite-backed rooms contain humans, routed local agents, threads,
reactions and a shared Markdown canvas. Mentioning an agent creates an ordinary durable
kernel job; the generated response is appended to the originating thread.

Each room is an append-only event stream with a SHA-256 hash chain. This makes accidental
or malicious history edits detectable without requiring a network relay, blockchain,
Postgres, Redis or an external identity provider. Logical membership controls who can post,
but membership never grants execution authority.

The collaboration plane is deliberately above the kernel:

```text
room message / mention
  ↓ untrusted_collaboration
durable kernel job → capability router → model
  ↓ untrusted_model_output
threaded room response
```

Conversation can propose work. Only policy, explicit authority and verification can commit it.

## System 1 / System 2 cognition

The manifest contains two general brains for different economics:

- **Qwen3.5-9B**: intended resident control-loop brain. Cheap repeated decisions, tool routing, visual reasoning, lightweight synthesis.
- **Qwen3.8-27B**: heavyweight quality brain. Difficult planning, coding, research,
  vision, synthesis and verifier/judge roles. UD-Q4_K_M is the measured-fit starting point
  for 12 GB VRAM/32 GB RAM; its MTP draft head remains a benchmark candidate.

Deterministic code runs before both whenever a deterministic solution exists.

## Routing sequence

```text
request
  ↓
normalize capability + license context + modality + risk
  ↓
filter by verified source / status / license / available engine
  ↓
read resource snapshot
  ↓
load local benchmark aggregate if available
  ↓
score quality × reliability × latency utility
  ↓
choose model + engine + profile
  ↓
execute
  ↓
verify result/post-condition
  ↓
record benchmark/outcome
```

Internet leaderboard scores are only bootstrap priors. Once local measurements exist, this machine's measurements win.

## Computer use hierarchy

Never use pixel clicking when structured control exists:

```text
native API
  ↓
CLI
  ↓
application plugin
  ↓
browser DOM / Playwright
  ↓
Windows accessibility/UI Automation
  ↓
vision GUI agent (UI-TARS-class fallback)
  ↓
brokered raw input
  ↓
human takeover
```

The vision GUI model is a universal fallback, not the default automation interface.
MCP is an interoperability transport across these capabilities, not an authority boundary or
a separate fallback tier. Direct Playwright is the canonical browser control contract. Local
Chromium is the required full-fidelity backend; Cloudflare Kitesurf is an opt-in external
backend for public, non-sensitive, stateless work only. The detailed selected stack and
implementation gates are in [AUTOMATION.md](AUTOMATION.md).

## Memory

Four logical classes:

- working: current context and active job state
- episodic: what happened
- semantic: durable facts and beliefs
- procedural: learned workflows / how-to knowledge

Every stored memory is designed to carry provenance fields: source, trust, confidence, timestamp, project, sensitivity, expiry and supersession. Text and visual retrieval are separate first-stage indexes, then reranked before context assembly.

## Transaction semantics

Mutation workflows use a saga-style transaction manager when no native ACID transaction exists:

```text
snapshot/precondition
  ↓
action 1 → verify
  ↓
action 2 → verify
  ↓
...
  ↓
commit
```

Failure triggers reverse-order undo handlers. Git/database/container-native transactions should be preferred where available.

## Process isolation

The base Python kernel intentionally contains no Torch/CUDA model dependencies. Specialist models run in isolated workers/environments. This prevents one model's pinned CUDA/Torch/Transformers versions from destabilizing the entire AI OS.

## Provenance and update strategy

Every install writes lock metadata. Updates are treated as experiments:

1. resolve new model/runtime version
2. install side-by-side
3. run capability-specific benchmark suite
4. compare quality/reliability/resource metrics
5. promote only if it wins
6. preserve prior lock for rollback

No component is promoted because it is newer.

Discovery is deliberately separate from promotion. The release radar tracks official
model, package, repository and documentation endpoints. It may report that announced
weights have appeared, but installation still requires license review, immutable source
resolution, hardware-fit analysis, engine support and a side-by-side local benchmark.

The living rationale and upstream evaluation ledger is
[knowledge/research.md](../knowledge/research.md). Architecture documents describe the
current design; the ledger preserves why choices were made, what was declined, and which
evidence may justify revisiting them.
