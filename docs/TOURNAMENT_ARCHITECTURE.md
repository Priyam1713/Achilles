# Tournament architecture — evidence before incumbency

**Audit date:** 2026-08-29
**Target:** HP OMEN MAX, Ryzen AI 9 HX 375, RTX 5070 Ti Laptop 12,227 MiB,
31.29 GiB RAM, WSL2 Ubuntu 24.04

The new research is accepted as a **contender catalogue**, not as permission to install
every named service or replace the kernel by reputation. Achilles already has a thin,
tested authority plane and has measured four agent loops on this workstation. A new
component enters behind a seam, runs the same tasks, and earns promotion. No README result
is a local result.

## Project charter

Achilles is an **open-source, local-model-first systems tournament** whose primary objective
is useful software-engineering performance on this exact workstation. Coding, debugging,
repository comprehension, tool use and long-horizon development tasks carry the most weight.
Reasoning, research, memory, browser/GUI work, recovery and security remain first-class
secondary tracks because a narrow coding score cannot establish that a complete system is
capable or trustworthy.

The optimization target is the composition, not a bag of individually impressive parts. A
greedy winner at every layer can still produce a slower, less reliable system through duplicated
state, incompatible protocols, excess idle RAM, context loss or competing schedulers. Treat the
architecture as a constrained composition problem: retain several viable candidates, measure
component interactions, and promote the smallest combination that improves end-to-end task
success under the workstation's RAM, VRAM, storage, latency and safety limits.

The build rule is **reuse before invention**. Adopt or adapt a maintained open-source component
when it satisfies the layer contract. Write custom code only for a missing contract, an authority
boundary that cannot safely be delegated, or a measured opportunity to outperform every suitable
existing option at acceptable implementation cost. Existing Achilles code is an incumbent, not
an entitlement: it competes under the same evidence and deletion rules as external projects.

Remote model APIs are deferred. OpenAI-compatible protocol support currently connects local
servers and harnesses; no configured engine is remote. A future remote-provider contest requires
an explicit phase change, data-boundary review and separate budget policy.

## Non-negotiable invariants

1. Achilles owns identity, grants, approvals, policy, task/run state, resource leases,
   verification and the final state transition.
2. A harness, protocol, model, memory service or telemetry collector never authorizes an
   action. It returns untrusted evidence.
3. One canonical task ledger exists. Specialist session state is opaque adapter state;
   memory indexes and telemetry are derived views.
4. Exactly one GPU-heavy workload may be admitted at a time. Model lifecycle is governed by
   the same global lease as vision, audio, retrieval and GUI grounders.
5. Discovery, measurement and promotion are separate operations. Promotion is never
   automatic.
6. The model is not a security boundary, especially for the separately identified
   `OBLITERATED` checkpoints.

## The actual machine, not the marketing machine

| Resource | Measured fact | Operating consequence |
| --- | --- | --- |
| GPU | RTX 5070 Ti Laptop, 12,227 MiB, Blackwell SM120, 101 W cap | Keep roughly 1.6–2.0 GiB free for desktop/runtime buffers; one model or grounder at a time. |
| RAM | 31.29 GiB usable | Preserve 8–10 GiB for Windows, WSL and the control plane. Q6 is paging-sensitive. |
| CPU | Ryzen AI 9 HX 375, 12C/24T; WSL exposes 20 threads, AVX2/AVX-512 | Hybrid inference is viable but memory-bandwidth-bound. Ten benchmark threads are the current control. |
| Storage | After the 2026-08-29 cleanup, WSL reports ~189 GiB used while its D:-backed VHDX remains ~260 GiB physically allocated and D: has ~63 GiB free | `df` is unsafe as the only gate. The trimmed VHDX still needs an elevated, offline compact before its deleted blocks become Windows free space. Flash-Next cannot be downloaded into the current store. |
| Fast brain | Qwen3.5-9B Q6_K, previously measured 49.57 decode tok/s | Resident/default tool-turn candidate. |
| Deep brain | Qwen3.8-27B quants, hybrid CPU/GPU | Explicit on-demand quality gear, not the normal tool loop. |

### 2026-08-29 host cleanup baseline

The pre-tournament cleanup preserved source, Git history, benchmark evidence, active model
contenders and uncommitted experimental work. It removed reproducible Rust/Python/Node build
outputs, package caches, abandoned partial downloads, a duplicate byte-verified Qwen3.8 cache,
and Qwen3.5 raw/F16 conversion inputs after retaining the verified Q6_K. WSL logical usage fell
from roughly 258 GiB to 189 GiB; E: free space rose from 254.99 GiB to 289.50 GiB. The legacy
`local-ai` gateway and freshness timer were disabled so opening WSL no longer reserves port 8080
or starts an obsolete model plane. OpenShell remains enabled.

The Windows host could trim but could not compact the detached VHD without elevation. No risky
export/unregister/import cycle and no experimental sparse-VHD conversion was attempted. Physical
D: space therefore remains the binding constraint until an administrator runs an offline VHD
compact and re-measures the result.

## Correct topology

```text
one UI
  │
  ▼
Achilles authoritative task ledger + dispatcher
  ├──────── task/agent selector ───────► native / Pi / OpenCode / Prime / Cordis / GUI
  ├──────── model selector ────────────► fast / deep / specialist endpoint
  └──────── global resource scheduler ─► one physically resident GPU-heavy process
                                             │
                                             ▼
                                llama.cpp router / llama-swap
                                             │
                                  llama.cpp or challenger engine

fail-closed tool gateway ─► worktree/container/VM ─► deterministic verification

memory and telemetry observe this flow; they are not serial authorities inside it
```

Durability wraps the task, agent and tool steps from above. DBOS cannot sit below an opaque
agent loop and magically recover that loop's Python/REPL memory. A retryable external side
effect additionally requires an idempotency key, recorded precondition/postcondition and a
rule for whether approval survives the retry.

## Layer-by-layer tournament

| Layer | Incumbent on this machine | Admitted challengers | Current disposition and experiment |
| --- | --- | --- | --- |
| Human experience | Achilles Tauri/web/CLI | Buzz, OpenBot, Open WebUI, Goose Desktop | Keep one primary UI. Buzz is a design/code reference; its Postgres/Redis/MinIO/Docker backend duplicates state. OpenBot is an isolated-computer experiment. Open WebUI is a manual playground only. |
| Protocol boundary | Authenticated kernel HTTP/events; MCP server and client | ACP, AG-UI, A2A | Protocols are added only at real boundaries: ACP for editors, AG-UI if the frontend contract needs it, A2A for independently deployed agents. They define messages, not authority. OTel belongs to telemetry, not this row. |
| Authority/meta-kernel | Achilles | DeepSeek Harness/Cordis, Omnigent, Goose | Achilles remains incumbent because its authority model is implemented and its native loop has exact-machine wins. Cordis enters as an `AgentLoop`/composition challenger. DeepSeek calls the project developer preview, warns of breaking changes and says it is not a sole security control. |
| General agent loop | Native loop | DeepSeek Harness, Prime Agent, Pi, Goose | Pi/Goose/OpenCode are already adapted. Prime and DeepSeek must receive only kernel-governed tools and disposable workspaces. Prime's 95.5% ARC-AGI-3 result used Claude Opus 5 xhigh and a very large inference budget; it is admission evidence, not a Qwen result. |
| Coding loop | Native safety lane; Aider provisional general-edit efficiency lane | Conditional Cline/Kilo/Gemini CLI experiments; screened adapters retained for Prime, Cordis, mini-SWE-agent, OpenHands, oh-my-pi, SWE-agent and Qwen Code | Run identical edit/debug/repository tasks with the same model and tool plane. Do not install permanent services for screened contenders. |
| Task/agent routing | Deterministic Achilles dispatcher | Learned/custom classifier | Selects *which agent or tool* handles a task. This is not vLLM Semantic Router's job. Begin deterministic; shadow-score any learner before it can route. |
| Model routing | Achilles capability/mode scheduler | vLLM Semantic Router, LiteLLM-style policy | Selects a model endpoint for a model call. Semantic Router is a model-path challenger and brings Envoy/containers; it must beat the native rule set enough to justify its footprint. |
| Physical lifecycle | llama.cpp router/load-unload plus global GPU lease | llama-swap, Ollama supervisor | `llama-swap` becomes valuable when two engine processes genuinely compete. It does not replace the global lease and cannot prevent unrelated specialist processes from overcommitting VRAM. |
| GGUF inference | Pinned upstream llama.cpp | ik_llama.cpp | Both are now pinned and load-tested. IQ4 directionally favors upstream; Q6 throughput is inconclusive. ik has not cleared the promotion and correctness gates, but remains admitted for novel quants, MoE and Flash-Next. |
| GPU-specialist inference | llama.cpp when GGUF fits | ExLlamaV3/EXL3 + server | Not a runner for the downloaded GGUFs. Requires a separate conversion/download and therefore a cross-format quality comparison, not a nominal engine swap. |
| Giant MoE inference | llama.cpp `-ncmoe` for the measured Nemotron candidate | ik_llama.cpp, Pulsar, KTransformers, SSD-expert experiments | Catalogue/on-demand only. Active parameters reduce compute, not total weight storage. A runtime must prove architecture support, RAM/VRAM/storage fit and useful task quality. |
| Durable execution | Achilles Runs, checkpoints, workflow DAGs, replay | DBOS; Temporal at multi-host scale | Native recovery is already authoritative and SQLite-backed. Trial DBOS only on explicit workflows whose step/idempotency model adds value; do not create a second task ledger. |
| Persistent agent memory | Achilles canonical memory/events | Hindsight in shadow mode; Graphiti/Mem0/Letta | Hindsight can derive retain/recall/reflect views, never become the sole copy. Test recall, contradiction, poisoning, deletion, provenance, latency and recovery against no-memory/native baselines. |
| Knowledge retrieval | Native lexical/vector store + specialist embed/rerank | LanceDB, Qdrant, pgvector | Embedded remains incumbent at current scale. Promote LanceDB for measured local query/operational benefit; Qdrant only when corpus size, filters or hybrid/multivector retrieval justify a service. |
| Computer/browser use | API → CLI → MCP → DOM/CDP → UIA interface | Playwright controller, Agent S3 + local grounder, OpenBot computer | Implement deterministic browser control first. A Linux container cannot contain arbitrary clicks on the real Windows desktop; native GUI autonomy needs a disposable Windows VM or a narrowly authenticated helper. |
| Execution security | Kernel policy/grants + staged worktrees; Docker fallback | OpenShell, gVisor where Linux-compatible | OpenShell is defense in depth and remains experimental on WSL2/GPU. It cannot replace kernel authorization. Run a real sandbox smoke before marking it healthy. |
| Observability/evaluation | Append-only events, benchmark DB/reports | OTel export, OpenLIT, Langfuse | Add OTel semantics/export before a heavyweight UI. OpenLIT adds a collector and ClickHouse, so run it during evaluation unless idle footprint earns residency. Redact before export. |
| Security telemetry | Kernel audit | Numbat | Numbat observes endpoint facts and can block only covered synchronous hooks with enforce rules. It is not a universal policy boundary. |

## First engine result: upstream vs ik_llama.cpp

Both engines were compiled with CUDA for the RTX 5070 Ti and run on 2026-08-28 with the
same files, `pp512`, `tg128`, three repetitions, ten CPU threads, batch 2048, ubatch 512,
Q8_0 K/V cache and Flash Attention. GPU placement was fixed to the result of the incumbent
fit tool: 37 layers for IQ4_XS and 26 for Q6_K.

| Pass | Model | upstream pp / tg tok/s | ik pp / tg tok/s | Reading |
| --- | --- | ---: | ---: | --- |
| A, direct controlled run | OBLITERATED IQ4_XS | **456.11 / 6.392** | 317.96 / 6.031 | upstream leads |
| B, saved sequential run | OBLITERATED IQ4_XS | **233.97 / 5.429** | 221.65 / 5.273 | upstream leads |
| A, direct controlled run | OBLITERATED Q6_K | **240.24 / 3.817** | 117.18 / 3.752 | upstream decode +1.7% |
| B, saved sequential run | OBLITERATED Q6_K | 97.59 / 3.751 | **158.10 / 3.802** | ik decode +1.4% |

IQ4_XS is the only directional engine result: upstream led decode in both passes. Q6_K is
inconclusive, not an upstream win—the decode leader flipped and both margins were under 2%.
Prompt results moved dramatically with cold/warm state; the saved Q6 upstream samples ranged
from 14.30 to 145.50 tok/s, so a single mean is not a promotion-quality statistic. The runner
now records medians/ranges and start/end GPU and host-memory telemetry, and supports
`--reverse-cells` for a counterbalanced follow-up. Upstream remains incumbent because ik has
not cleared a stable promotion margin, not because every cell favored upstream.

There is an additional compatibility warning: the runtimes report different loaded parameter
counts for the same GGUF (upstream ~27.321B, ik ~26.896B). This may be differing treatment of
the embedded NextN/MTP tensors rather than wrong main-model execution, but it makes a shared
quality/correctness suite mandatory before ik can ever be promoted. `configs/runtime-tournament.yaml`
and `scripts/benchmark_runtimes.py` make the throughput comparison reproducible. The raw
saved pass is at `$SOAI_STATE_DIR/runtime-tournament.json`.

## Model policy now

| Slot | Candidate | Policy |
| --- | --- | --- |
| Fast/default | Qwen3.5-9B Q6_K | Tool turns, routing, ordinary interaction. |
| Deep/interactive challenger | Qwen3.8-27B OBLITERATED IQ4_XS | Faster of the two new files, but still below the project's 10 tok/s interactivity gate. Explicit opt-in and personal-use model id only. |
| Deep/quality laboratory | Qwen3.8-27B OBLITERATED Q6_K | 3.8 tok/s. Must win enough task quality to justify ~40% lower decode and much higher host-memory pressure. Never a default. |
| Sparse candidate | Nemotron-3.5-Lightning-30B-A3B | Throughput winner already measured; quality and non-OSI NVIDIA licence decision remain separate gates. |
| Future giant | Qwen3.8-Flash-Next | Metadata/runtime feasibility only; do not download into current storage. |

## Flash-Next: real, exciting, and not yet a workstation model

The official [Qwen3.8-Flash-Next repository](https://github.com/QwenLM/Qwen3.8-Flash-Next)
describes a 125B main model plus 51B n-gram embeddings with roughly 6B active parameters per
token. Six billion active parameters lower compute; all 176B parameters still need VRAM,
RAM or storage traffic. Idealized 2-bit weights alone are about 44 GB before quantization
metadata, scales, buffers, recurrent/KV state and runtime overhead. The model uses the custom
Qwen Community License 1.0, so it is open-weight rather than a strict OSI-open-source default.

Runtime news is better than hardware fit:

- current `ik_llama.cpp` explicitly lists Qwen-3.8-Flash-Next support;
- [llama.cpp PR #27742](https://github.com/ggml-org/llama.cpp/pull/27742) merged to master on
  2026-08-27, after the project's current pinned incumbent; NextN/MTP support was deferred;
- a stable model-serving claim still requires the exact quant, commit and end-to-end output
  checks. Architecture recognition alone is not useful quality.

The admission gate before any download is: a supported quant plus all runtime overhead must
fit roughly 22–24 GiB host memory, leave the OS/control plane safe, fit the physical backing
volume and pass a small independent quality study. SSD streaming belongs in an experimental
profile. It does not enter `core`.

## First composition-aware software-engineering suite

The historical twelve harness tasks remain the `micro` suite. On 2026-08-29 the first
separate `software-engineering` slice added eight small repositories covering bug fixes,
feature implementation, configuration semantics, a typed cross-file contract, cache-key
collisions, path traversal/symlink escape, pagination boundaries and streaming JSONL error
handling. This brings the selectable total to twenty without rewriting the meaning of any
old result.

The engineering tasks are checked after the loop by held-out standard-library verifiers in
a copied, read-only workspace through the hardened execution broker. Model-written Python is
never imported into the coordinator. The report format is now schema version 3 and records
the ordered manifest and verifier hashes, Git state, environment, model variables, repeats,
counterbalanced cell order, atomic resume checkpoints, category/outcome distributions and
median latency. It still cannot promote anything. The
full contract and commands are documented in [`docs/BENCHMARKS.md`](BENCHMARKS.md).

No live harness winner is claimed from this implementation pass. A full local contest needs
a healthy local model endpoint and at least three attempts per task; the remaining ten-plus
tasks should broaden realism and secondary capability tracks rather than pad the suite with
near-duplicate edits.

## Promotion scorecards

### Model or inference runtime

- deterministic load and output smoke on the exact GGUF;
- prompt/decode throughput, TTFT, peak VRAM, minimum available RAM, swap activity and thermals;
- same quant, context, batch, offload, cache and prompts where formats permit;
- compatibility matrix: roles, streaming, tool calls, JSON schema, images, cancellation,
  usage and context errors;
- repeated task quality and stability;
- source, license, commit/checksum and rollback recorded;
- never auto-promote.

### Agent harness

- same model endpoint, governed tool plane, workspace fixture and postconditions;
- task success first; then interventions, tokens/model calls, time to first useful result,
  wall time, denied/unsafe attempts and repeatability;
- cancellation, crash/restart, compaction, session export and malformed-tool behavior;
- no built-in filesystem/shell/network route around the kernel;
- at least three stochastic attempts per task before a winner is claimed.

### Memory, retrieval or router

- shadow mode first, with the incumbent still answering;
- latency and RAM/idle footprint measured while the normal model is resident;
- adversarial poisoning, contradiction/supersession, scope isolation, deletion and provenance;
- task-level benefit, not retrieval/router proxy scores alone;
- explicit fallback on component failure.

## Build order from here

1. Fix physical storage accounting (the sparse VHDX finding is a pre-download safety issue).
2. Keep upstream llama.cpp for the current dense GGUFs; preserve ik as a pinned on-demand
   challenger and future Flash/MoE laboratory.
3. Grow the now-separate 8-task software-engineering slice (20 total with the preserved
   micro baseline) into the planned ~30-task Olympics: add realistic multi-language work,
   research, tool choice, resume/kill, memory, injection, delegation and browser tracks.
   Unsupported tracks are explicit skips, never passes.
4. Integrate DeepSeek Harness and Prime separately behind the governed tool seam. Do not nest
   them until each independent baseline works.
5. Prove native crash/restart recovery and idempotency before trialing DBOS.
6. Trial Hindsight in shadow mode, then deterministic Playwright/CDP control.
7. Add OTel export and only then decide whether OpenLIT/Numbat earn on-demand sessions.
8. Revisit Flash-Next after storage, quant and host-memory gates—not because its release is
   interesting, but because a feasible artifact exists.

The permanent architecture is therefore deliberately small. The catalogue is large; the
resident system is not. Every additional service must increase task success enough to pay
for its RAM, state, failure modes and authority surface.
