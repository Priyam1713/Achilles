# Harness research — the field, dissected

> Opened **2026-08-23**. Companion to [research.md](research.md); that file is the decision
> ledger, this one is the field notebook. Nothing here is a decision until it is written into
> `research.md` as a `D-` record.

## Why this file exists

`research.md` waves 6–8 established that the harness layer is the binding constraint on
capability, and wave 8's honest reckoning is that we then partly reimplemented what the field
already ships. This file is the correction: **a surgical, per-harness dissection of ~21 open
harnesses, recording what can be taken directly, what should only be learned from, and what to
leave alone.**

### The one constraint that ranks everything here

Every harness in this file was built for a model that is fast, cheap, and has a large context.
**Ours is none of those.** The deep brain measures 6.36 tok/s under offload, the fast brain
49.57 tok/s, and the operating context is 16K (`docs/FIXES.md` F-005, F-012).

So the ranking function for this project is not "which harness is most capable". It is:

> **minimum context consumed per turn × minimum turns per task × maximum tool success rate
> for a weak model.**

That single reordering puts a harness almost nobody lists first — **Pi** — at the top, and
demotes several famous ones to reference material.

### Evidence labels

Same vocabulary as `research.md`. In this file specifically:

| Label | Means |
| --- | --- |
| `primary-verified` | The repository, spec or paper was fetched and read in this pass. |
| `landscape` | Third-party reporting, consistent across sources, **not** inspected by us. Design evidence only; never a basis for an install. |
| `vendor-claim` | A number the project itself publishes. Recorded because it is directional, never as local truth. |

### The licence gate, applied before anything else

Baseline invariant 8 is a gate, not a footnote. Applied to this list it already disqualifies
two entries that look open at a glance:

- **Crush** is **FSL-1.1-MIT** (Functional Source License) — *source-available*, not
  OSI-approved. It converts to MIT after a delay. **Declined as a dependency**; readable as
  design reference only.
- **Open Interpreter** is AGPL-family. Usable, but AGPL is viral across a network boundary,
  which matters for anything we expose as a service. **Declined as a linked dependency**;
  fine as a separate process if ever needed.

---

## Corrections to the input list

Four entries in the list this research started from are stale or imprecise. Recording them
first, because a plan built on them would waste weeks.

| Entry | Correction | Evidence |
| --- | --- | --- |
| **Roo Code** — "✅ Major" | **Dead.** Announced shutdown 2026-04-21; extension and repository archived 2026-05-15. Its ideas (multi-mode, Boomerang Tasks) live on in **Kilo Code**, which was built to fill the vacuum. Migrating *to* Roo would be building on an archive. | `landscape`, consistent across sources |
| **Continue** — "✅ Active" | **Effectively end-of-life as an independent project.** Acqui-hired by Cursor, announced 2026-06-16; final release `v2.0.0-vscode` on 2026-06-19. | `landscape` |
| **Crush** — "OSS" | **FSL-1.1-MIT**, source-available, not OSI. Fails invariant 8 as a dependency. | `primary-verified` (repo) |
| **"ACP"** — used ambiguously | **Three different things share the initials.** See below. `D-024` adopted the right one, but the ledger never disambiguated it, and Qwen Code uses "ACP" for something else. | `landscape`, multiple sources |

### The ACP disambiguation, once, precisely

- **Agent Client Protocol (Zed).** Editor ↔ coding agent, JSON-RPC over stdio, explicitly
  modelled on LSP. Created June 2025; headline feature of Zed 1.0 (2026-04-29); in JetBrains
  since December 2025; public agent registry with JetBrains from 2026-01-28. **This is the one
  `D-024` adopted, and it is still the right one.**
- **Agent Communication Protocol (IBM).** Agent ↔ agent pipeline coordination. **Merged into
  A2A under the Linux Foundation in August 2025; repository archived.** Dead as a separate
  standard.
- **A2A (Agent2Agent).** Agent ↔ agent across organisations. v1.0 March 2026, Linux Foundation,
  150+ organisations. Adjacent layer to Zed's ACP, not a competitor. `research.md` already has
  A2A `adopted` at the external trust boundary (wave 3) — that record stands and does not
  conflict.

**Rule for this project:** any future mention of "ACP" must name which one, or it is
`unverified`.

---

## Tier 1 — the harnesses that should change our design

### Pi (`earendil-works/pi`) — MIT — `primary-verified` repo, `landscape` architecture

Mario Zechner and Armin Ronacher. Three packages: `pi-coding-agent` (CLI), `pi-agent-core`
("agent runtime with tool calling and state management"), `pi-ai` ("unified multi-provider LLM
API"), plus a terminal UI library and telemetry contracts.

**Why it is first here despite being the smallest thing on the list:** a Databricks internal
benchmark (August 2026, `vendor-claim` via reporting) found Pi had **the highest pass rate of
any harness tested at significantly lower cost**, because it sent **roughly 3× less context per
turn** and finished tasks in fewer runs. That is the exact objective function our hardware
imposes, and Pi optimised for it by construction rather than by accident.

The mechanisms, each of which is separable:

| Mechanism | What it is | Take it? |
| --- | --- | --- |
| **Sub-1000-token system prompt** | The base prompt is deliberately tiny; project detail arrives via `SYSTEM.md`/`AGENTS.md`, not globally | **Steal outright.** Ours is a fixed constant plus the whole tool roster. On 16K, the system prompt is rent we pay every single turn. |
| **Four core tools** | Task intake, context management, tool execution, loop control as primitives; everything else is an extension | **Learn.** Our 13 tools are justified (they reach the specialist plane), but the *prompt-visible* set per turn should be four-ish, selected by `ToolRegistry.discover`. |
| **25+ in-process hooks** | TypeScript extensions inject messages before a turn, filter history, wire RAG, implement memory | **Steal the shape.** This is Claude Code's hook idea without the subprocess cost — and in-process matters at our latency. |
| **Tree-structured sessions (DAG)** | Sessions branch rather than append; failed paths become branches; retries do not lose context | **Steal.** Maps onto `Job`→`Run` almost exactly: today a retry is a new `Run` but the tree is not navigable. |
| **Compaction as an extension point** | Default auto-summarises; teams replace it with topic-based, code-aware, or cheaper-model strategies | **Steal the seam.** We built one fixed deterministic compactor (F-049). Making it pluggable is small and unlocks tuning. |
| **Skills demand-loaded** | Capabilities load on demand to keep the prompt cache hot | **Steal.** Directly compatible with `SKILL.md` (`D-022`). |
| **Batched-tool interrupt semantics** | A human steering message interrupts remaining batched tools; follow-ups queue until completion | **Steal.** Avoids context-thrashing mid-run re-planning. |

**What Pi deliberately omits** — and this is the instructive part — MCP, sub-agents, plan mode,
permission popups, built-in todos, background bash. It treats those as *product opinion*, not
harness scaffolding. **We should not copy the omissions**: several of them (permissions, plan
mode) are the kernel's whole reason to exist. But the *separation* is the lesson: scaffolding
is ours, opinion is configurable.

**Verdict: `trial` as the reference architecture for our loop's shape, and the harness to beat
in the tournament.** It is MIT, TypeScript, and small enough to read end to end.

### oh-my-pi (`can1357/oh-my-pi`) — MIT — `primary-verified` repo

A Pi-derived, aggressively optimised terminal agent. **The most directly stealable engineering
in this entire file**, because every one of its ideas is a token-efficiency or
success-rate optimisation for *weak* models — which is our exact situation.

| Mechanism | Detail | Value to us |
| --- | --- | --- |
| **Hash-anchored edits ("hashline")** | The model points at content by **hash anchor** instead of retyping lines. Stale patches are **rejected before corrupting the file**, eliminating string-not-found failures. `vendor-claim`: 61% fewer output tokens on the same work (Grok 4 Fast) | **The single highest-value steal in this document.** It supersedes our `edit_file` exact-match approach: same safety property (refuse rather than mis-edit), far fewer output tokens — and output tokens are literally our 6.36 tok/s bottleneck |
| **`read` that summarises rather than dumps** | The read tool returns structure, not the whole file | **Steal.** Our `read_file` dumps up to 20,000 chars into a 16K context. That is a self-inflicted wound |
| **Parallel ripgrep** | `grep` returns instantly via parallel invocation | **Steal.** Our `GrepTool` is a pure-Python `rglob` + regex walk. Correct, portable, and slow on a real repo |
| **LSP as first-class tools** | Including `workspace/willRenameFiles`, so re-exports, barrel files and aliased imports update *before* a move | **Steal via MCP/Serena first.** This is the difference between editing text and editing code |
| **`task` fan-out with schema-validated results** | Subagents return typed objects, not prose | **Steal.** Our `Delegation` has the contract; the schema-validated return is the missing half |
| **`advisor` role** | A separate, cheaper model watches every turn and injects concerns mid-stream **without paying context tax** | **Steal — this is our idle fast brain.** It is simultaneously wave 7's "classifier pre-screen" and wave 8's `D-037` quarantine, in a shape someone has already shipped |
| **`browser` + `computer` tools** | Headless Chromium *or* relay into your existing Chrome; screenshots, native input, OS accessibility tree | **Reference.** Matches `docs/AUTOMATION.md`'s design; our tiering (API → CLI → DOM → UIA → vision) is stricter and should stay |

**The number that should end any remaining debate:** `vendor-claim` that tool-harness tuning
lifted edit pass rate from **6.7% to 68.3%** on a weak model (Grok Code Fast). Same model. Same
task. Tenfold, from interface design alone. That is SWE-agent's ACI thesis, measured on a
current weak model, and it is the strongest argument in this file that **our harness work is
worth doing — but only if it is this kind of work.**

**Verdict: `trial`, and the first source to port from.** Hash-anchored edits, summarising read,
parallel grep and the advisor role are four separable wins.

### DeepSeek Harness / Cordis — MIT — `primary-verified` repo, `landscape` internals

"Everything is a plugin." **The model adapter, the tool registry, the session log and the agent
loop itself are all plugins.** Powered by **Cordis**, an independent plugin kernel by Shigma
(Yifan Shi), previously the kernel behind the Koishi chatbot framework since 2019 — i.e. a
runtime with six years of production hardening, not a fresh abstraction.

Cordis is a "meta-framework of spatiotemporal composability": components **declare
dependencies**, **register reversible side effects**, and can be **loaded, unloaded or
hot-reloaded without restarting**. It is formalised in an 88-page paper (Shi, Zhang, Cui;
2026-08-13) that lifts *effects* and *coeffects* from compile-time type theory into runtime
mechanisms — temporal composability (fully reverting a component's effects) and spatial
composability (declaring and reactively managing inter-component dependencies).

**Honest limitation of this pass:** the README defers architecture detail to
`docs/architecture.md`, which was not retrieved. The event-journal design specifically remains
`unverified`. Anything built on it must read that document first.

**What is genuinely valuable to us:**

- **Reversible side effects as a runtime contract.** This is the same idea as our
  `TransactionManager` and rollback hooks, generalised to *every component*. Our execution
  plane has transactions; our plugin/adapter plane does not.
- **Hot-swappable model adapter and tool registry.** We have adapters behind interfaces but
  they are wired at `SovereignKernel.build()` and require a restart. On a machine where model
  load is tens of seconds, hot-swap is a real user-visible win.
- **The agent loop as a plugin.** This is `D-001` taken to its logical end. It is the strongest
  available validation that our "no harness is the root of trust" invariant is the right
  architecture — DeepSeek reached it independently.

**Verdict: `watch` closely, `reference` now.** Developer preview with explicit
compatibility-breaking warnings; we cannot take a runtime dependency on it. But if one
architecture in this file deserves a careful read before we finalise our own plugin seam, it is
Cordis.

### OpenCode (`anomalyco/opencode`) — MIT — `primary-verified` repo

200.3k stars, 25.9k forks. **The strongest mature provider-neutral open coding harness.**
Client/server architecture, `packages/`, `sdks/vscode`, `infra/`, `specs/`. CLI via npm,
Homebrew and system packages, plus a beta desktop app for macOS/Windows/Linux.

Agent model worth copying exactly:

- **build agent** — default, full access
- **plan agent** — read-only analysis; **denies file edits by default** and asks before bash
- **general subagent** — complex searches and multi-step tasks
- **Tab toggles between them.**

Plus LSP integration, a permissions system, multi-session management, configurable keybindings,
vim mode, themes, and session sharing.

**What to take:**

1. **The client/server split is our shape already.** The kernel is the server; the TUI, desktop
   and web are clients. OpenCode proves the ergonomics work at scale, and its TUI is a client
   of a local server — meaning **adopting OpenCode as a front-end does not require giving up
   the kernel**.
2. **Plan/build as first-class agents with different tool permissions**, toggled by one key.
   Our `CapabilityGrant` can express this far more precisely than a mode flag; what we lack is
   the one-keystroke ergonomics.
3. **`specs/`** as a directory — a harness that keeps its own specifications in-repo is one you
   can build a compatible client against.

**Verdict: `trial` as the primary external `AgentLoop` candidate, and the leading candidate to
*inherit* a TUI, diff view, LSP and session management from** rather than build them.

---

## Tier 2 — proven mechanisms worth porting

### ForgeCode — OSS (`landscape`; licence not verified in this pass)

**Top of Terminal-Bench 2.0 at 81.8%**, above Claude Code, Codex and Gemini CLI (`vendor-claim`
via reporting). Three specialised agents: **Muse** (planning), **Forge** (execution), **Sage**
(research). Sub-50ms startup. `forge.yaml` workflows. MCP. Live repository index. 300+ models
including self-hosted.

**The mechanism to steal is not the agent split — it is `join_all()`.** Reporting singles out
**parallel tool execution**: most harnesses run tool calls sequentially; ForgeCode fires
independent calls simultaneously. On a machine where each turn costs seconds of generation,
**collapsing three sequential reads into one parallel batch is a direct multiplier on wall
time**, and it composes with everything else in this file.

Our `NativeAgentLoop` executes exactly one action per turn. That is the most conservative
possible design and it was right for a first loop; it is now the cheapest available speedup.

**Verdict: `trial`. Steal parallel tool dispatch and the schema shape that makes it safe.**
Licence must be verified at primary source before any code is taken.

### OpenHands (`All-Hands-AI/OpenHands`) — MIT — `landscape` (V1 SDK paper + docs)

Mid-migration from V0 (monolithic, sandbox-centric) to **V1**, a modular SDK; V0 removal was
scheduled for 2026-04-01. Four packages: `openhands.sdk`, `openhands.tools`,
`openhands.workspace`, `openhands.agent_server`.

The V1 core, quoted because it is startlingly close to ours:

> a stateless **Agent** that emits **Actions**, a **Conversation** that runs the loop and stores
> an append-only **EventLog**, a **Workspace** (local process or Docker container) that executes
> Actions and returns **Observations**, and an LLM wrapped for provider portability.

> Everything else — **memory compression, microagent knowledge, sub-agent delegation, security
> review, stuck detection** — is a small auxiliary service hanging off the event stream.

**This is the most important architectural validation in the file.** We independently built an
append-only event store, an execution broker returning observations, and a stateless loop. What
we did *not* build is the last sentence: **auxiliary services hanging off the event stream.**
Our verification engine, policy checks and (future) stuck-detection are called inline or not at
all.

Also worth taking:

- **Event-sourced state with deterministic replay.** We have the journal; we do not have replay.
  This is the substrate for wave 7's authority-legibility run inspector.
- **Condensers** — history summarisation as a named, swappable component; `vendor-claim` of up
  to 2× cost reduction without performance loss.
- **CodeAct** (already recorded, wave 6): the action space *is* code; `landscape` claims ~30%
  fewer turns and ~20% higher success versus one JSON tool call per turn.
- **Microagents / skills**: `.openhands/microagents/*.md` loaded on demand.

**Verdict: `adopted` as an architectural pattern (auxiliary services on the event stream,
deterministic replay, condensers as components). `trial` as an `AgentLoop`.**

### SWE-agent (Princeton) — MIT — `primary-verified` (NeurIPS 2024 paper)

Not a product to adopt — **the theory that justifies everything in Tier 1**. The
Agent-Computer Interface thesis: *LM agents are a new class of end user and deserve interfaces
built for them.*

Its design principles, which read as a specification for our tool plane:

1. **Simplicity** — few options, concise documentation, so no demonstrations or fine-tuning are
   needed to use a tool correctly.
2. **Compactness** — consolidate important operations (file navigation, editing) into **as few
   actions as possible**, so an agent makes meaningful progress in a single step.
3. **Concise feedback** — observations sized for a context window, not for a human reading logs.
4. **Error guardrails** — the interface refuses malformed operations instead of letting them
   corrupt state.
5. **History collapsing** — explicit context management to mitigate the window limit.

Measured: 12.47% pass@1 on SWE-bench, 87.7% on HumanEvalFix (2024 numbers; the absolute values
are stale, the *principle* is not).

**Audit our tool plane against these five and it fails three.** `read_file` dumps 20,000 chars
(violates 3). One action per turn (violates 2). `run_command` has an open-ended `argv` with no
guardrail beyond policy (violates 1 and 4).

**Verdict: `adopted` as design law. Every tool we add gets checked against these five points.**

### Cline — Apache-2.0 — `landscape`

Three named mechanisms, all directly portable:

- **Focus Chain.** A todo list generated at task start and **re-injected on a cadence (default
  every 6 messages)**, described as "a north star that cuts through accumulating context
  noise". Enabled by default since v3.25.
- **Auto-Compact.** Summarise-and-continue at the context limit; `vendor-claim` that a task
  needing 5M tokens completes in a 200k window.
- **Deep Planning.** A four-step workflow: silent codebase investigation → targeted clarifying
  questions → comprehensive implementation plan → **fresh task handoff for execution**.
- **Memory Bank** (product intent, system patterns, tech context, active context, progress as
  Markdown in the repo) and `.clinerules` — version-controlled instructions the agent reads and
  can edit on request.

**Focus Chain is the cheapest high-value item in this file.** It is a list in the prompt,
refreshed periodically. On a 16K context with deterministic elision (F-049), a persistent
re-injected objective is exactly the thing that stops a compacted run from forgetting its own
goal. We already elide history; we do not re-inject intent.

**Deep Planning's fourth step — fresh task handoff — is the one to note.** Planning and
execution do not share a context. That is `D-025`'s context-isolated child run, with a workflow
around it.

**Verdict: steal Focus Chain immediately; adopt Deep Planning's four steps as a workflow
definition (we already have `WorkflowDefinition`); Memory Bank is `AGENTS.md` plus our memory
store and needs no new format.**

### Codex CLI — Apache-2.0 — `primary-verified` (repo + patch-format docs)

Already dissected in `research.md` wave 6. What this pass adds is the **exact V4A grammar**:

```
*** Begin Patch
*** Add File: path        (every following line is a + line)
*** Delete File: path     (nothing follows)
*** Update File: path     (optionally followed by *** Move to: newpath)
@@ [optional hunk header]
 context line
-removed line
+added line
*** End Patch
```

`HunkLine := (" " | "-" | "+") text NEWLINE`, three lines of context above and below by default.

**And the sentence that changes our decision:** V4A is *"a purpose-built patch grammar that
OpenAI's models have been specifically trained to produce."*

That **retroactively justifies F-047's recorded deviation**. We chose unique-match
search/replace over V4A because it is what a 9B-class local model gets right. V4A's advantage
is largely a *training* advantage that our models do not share. The correct conclusion is not
"adopt V4A" but **"edit format is a per-model property"** — which is Aider's position, and which
our model registry can express as a field.

Sandboxing remains best-in-class and worth porting per-platform when `D-035` lands: Landlock +
seccomp + bubblewrap on Linux, Seatbelt on macOS, AppContainer/restricted tokens on Windows.

### Aider — Apache-2.0 — `landscape`

Two things, both already recorded, now with detail:

- **Edit formats, chosen per model**: `whole` (simple, slow, costly), `diff` (search/replace
  blocks), `udiff` (unified-diff variant, introduced specifically to stop GPT-4-Turbo's "lazy
  coding" elisions), `patch`, and `architect`/`editor` split where the editor gets a simpler
  prompt focused only on applying the edit. Defaults are per-model-family.
- **Repo map**: tree-sitter symbol graph across 100+ languages, ranked by **PageRank over the
  definition/reference graph**, emitted inside a token budget.

**The architect/editor split deserves more attention than we gave it.** A strong-but-slow model
plans; a fast model applies. That is *exactly* our dual-brain topology — deep brain plans at
6.36 tok/s, fast brain edits at 49.57 — and it is the same shape as the FastApply idea from
wave 8, but achievable with models we already have and no new download.

**Verdict: repo map `adopted` (already); architect/editor split promoted from "interesting" to
`trial` — it is the highest-value use of our two-brain hardware.**

### Goose (`block/goose`) — Apache-2.0 — `primary-verified` repo

Rust, Apache-2.0, governed by the **Agentic AI Foundation at the Linux Foundation**. 15+
providers including Ollama, 70+ MCP extensions, desktop + CLI + API, and — new since our last
pass — **connects to Claude/ChatGPT/Gemini subscriptions via ACP providers**.

We already have `GooseAgentLoop` and a working MCP bridge (F-043, F-045). Its governance
remains the strongest anti-capture argument of any harness here (`D-015`).

**Verdict: unchanged — `trial`, and now the *incumbent* external loop to beat, since the
adapter already exists and works.**

---

## Tier 3 — specific ideas worth lifting, whole projects not adopted

### Qwen Code — Apache-2.0 — `primary-verified` repo

Forked from Gemini CLI v0.8.2, then diverged into a **multi-protocol, multi-platform agent
framework**. Notable for how many surfaces one codebase serves: interactive CLI, headless,
IDE plugins (VS Code/JetBrains/Zed), desktop app, **daemon (`qwen serve`)**, and SDKs in
TypeScript/Python/Java. Protocols: MCP, ACP (daemon mode — *which* ACP is unverified), LSP.
Features `SubAgents, Agent Teams, Dynamic Workflows` and `Auto-Memory, Auto-Skills`.

**What to take: the daemon-plus-many-clients topology.** It is the same conclusion OpenCode
reached and the same shape our kernel already has. This is now three independent projects
converging on "one local server, many thin clients" — strong evidence we should stop treating
the desktop as *the* product and start treating the kernel API as the product.

### Kilo Code — MIT (CLI) — `landscape`

Roo Code's successor; now part of Anaconda. Five modes (Architect, Code, Debug, Ask,
Orchestrator), VS Code + JetBrains + CLI + cloud + Slack, 500+ models.

- **Orchestrator mode / Boomerang Tasks** (inherited from Roo): a parent spawns a specialised
  subtask in a different mode, **the parent pauses**, and on completion **the parent resumes
  with only the summary**. That last clause is the whole point — it is context isolation with a
  defined return contract, and it is what `D-025` asks for.
- **Per-mode model routing**: expensive model for implementation, cheap model for questions.
  Our `ResourceScheduler` already routes by capability; per-*role* routing is a small extension
  with a direct cost/latency payoff on our hardware.

### Gemini CLI — Apache-2.0 — `landscape`

Two things worth noting, one of which is a straight validation:

- **CLI/Core split** — UI and history separated from model orchestration and tool execution.
  Same conclusion again.
- **Checkpointing via a shadow git repository** at `~/.gemini/history/<project_hash>`, committed
  before any file-modifying tool is approved. **This is what we built independently in F-049**,
  down to the shadow-repo-keyed-by-project-hash detail. Two independent arrivals at the same
  design is about as good as validation gets.

### Plandex — OSS — `landscape`

Built for large projects: 2M-token effective context, 20M-token indexing via **tree-sitter
project maps**, and — the interesting part — a **cumulative diff sandbox**: AI changes
accumulate *outside* the project files across a session and are **applied atomically when the
developer approves the batch**.

**This is a genuinely different answer to our approval problem.** Today an agent needs a
`write:workspace` grant to touch anything, and the human approves *authority in advance*. A
diff sandbox lets the agent work freely in a staging area and the human approve *the actual
change after seeing it* — which is wave 7's X-03 (evidence-bearing approvals) and X-04 (no diff
view) solved by the same mechanism.

It does not replace grants — a sandboxed agent can still run commands and reach the network —
but for **file mutations specifically it is strictly better UX at equal safety**, and it makes
the diff view trivial because the diff already exists as an object.

**Verdict: `trial`, and a candidate to change `D-021`/`D-028`.** Possibly the best single idea
in Tier 3.

### Crush (Charmbracelet) — **FSL-1.1-MIT, not OSI** — `primary-verified` repo

Go. Session-based with multiple sessions per project, LSP for context, MCP over
stdio/HTTP/SSE with OAuth, provider abstraction allowing **model switching mid-session**,
permissions requiring explicit approval by default with `--yolo` to disable, and a Bash-based
`crushrc` that runs before the agent initialises.

**Declined as a dependency on licence.** Two ideas are still worth learning: *switching model
mid-session without losing the session*, and *config as an executable shell script* (powerful,
and a security consideration we would have to reject in that form).

### Open Interpreter — AGPL-family — `landscape`

Local code interpreter plus **OS Mode** — visual control of the machine via mouse/keyboard with
a vision model, supporting local vision models through llamafile/LM Studio/Jan. Now describes
itself as "a coding agent for open models".

Its own documentation is the citation we should keep: it *"has actual control of your machine
(mouse, keyboard, file system), and without proper sandboxing, a hallucination could be
destructive."* That is the argument for `docs/AUTOMATION.md`'s tiering and for `D-009`
(deterministic control first, vision last), made by the project that went furthest without it.

**Declined as a dependency (AGPL + no containment model). Reference for computer-use only.**

### fast-agent (`evalstate/fast-agent`) — MIT — `landscape`

Notable for one specific thing: **the first framework with complete, end-to-end tested MCP
feature support, including Sampling and Elicitations** — the two MCP features almost every
client skips.

*Elicitations* matter to us more than they look: they are the protocol-level way a server asks
the human a question mid-call. That is our `ApprovalRequest`, expressed in a protocol other
tools already speak. If we build an MCP client (`D-023`), supporting elicitations makes our
approval plane reachable *by other people's tools*.

**Verdict: `reference` for MCP client completeness; specifically, implement elicitations.**

### Hermes Agent (Nous Research) — OSS — `landscape`, already in `research.md` wave 3

Unchanged decision (`trial` after roster/run contracts, run under containment). One new
observation from this pass: its issue tracker shows both **an ACP server-mode request** and **a
PageRank repo-map request modelled on Aider** — i.e. the field is converging on exactly the two
adoptions we have queued. Independent corroboration of the priority order, not new capability.

### Continue — Apache-2.0 — `landscape` — **acqui-hired by Cursor, EOL June 2026**

The idea that outlives it: **YAML blocks and composition**, where assistants, agents, rules and
prompts are self-contained units, defined locally *or* pulled from a hub, and composed by an
"unrolling" process into the final runtime config, with `.continue/config.yaml` committed and
reviewed like any other config.

**That is the right shape for our `configs/` plane**, and it is how a community shares
configuration without sharing a runtime. Worth taking even though the project is ending.

### LLMling-Agent — **`unverified`**

Could not be located at primary source in this pass. **No decision, no adoption, not counted.**
Recorded here only so the gap is visible rather than silently dropped.

---

## The synthesis — what the greatest local harness is made of

Composed from the above, filtered by our constraint (16K context, 6–52 tok/s, 12 GB VRAM), and
excluding anything our kernel already owns.

| Layer | Take from | Why |
| --- | --- | --- |
| **Loop shape** | Pi (minimal prompt, four visible tools, hooks) + OpenHands (stateless agent, actions/observations, auxiliary services on the event stream) | Both minimise per-turn context; the second is already our architecture |
| **Edit format** | oh-my-pi hash-anchored edits, **per-model** (Aider's law), with Codex V4A only for models trained on it | Output tokens are our hardest bottleneck |
| **Read/search** | oh-my-pi summarising `read`, parallel ripgrep `grep` | Our current versions actively waste the context they exist to save |
| **Turn count** | ForgeCode parallel tool dispatch; OpenHands CodeAct as a second loop mode | Wall time is turns × tokens; this attacks turns |
| **Objective persistence** | Cline Focus Chain (re-inject todos on a cadence) | Cheapest possible fix for post-compaction drift |
| **Planning** | Cline Deep Planning (4 steps, fresh handoff) + Aider architect/editor split | Uses our two brains for what each is good at |
| **Subtasks** | Kilo/Roo Boomerang (parent pauses, resumes with summary only) + oh-my-pi schema-validated returns | Context isolation with a real return contract |
| **Review & undo** | Plandex cumulative diff sandbox; Gemini CLI/Cline shadow-git (already built) | Solves approval evidence and the missing diff view in one mechanism |
| **Oversight** | oh-my-pi `advisor` on a second model | Our fast brain is idle during deep-brain turns; this is `D-037` + wave 7's classifier pre-screen |
| **Code intelligence** | Serena/LSP via MCP; Aider repo map | Structure instead of text |
| **Surfaces** | OpenCode / Qwen Code / Gemini CLI daemon-plus-thin-clients; Zed ACP for editors | Three independent projects converged here; so did we, by accident |
| **Config** | Continue's YAML blocks + composition | Community-shareable configuration without a shared runtime |
| **Plugin runtime** | Cordis' reversible effects and hot-reload, as a *design* | Generalises our transaction/rollback idea to every component |
| **Tool design law** | SWE-agent ACI five principles | The theory under all of the above |

### What none of them have — and this is the answer to "was it worth it"

Not one harness in this file has: a policy engine, expiring capability grants, structured
approvals with evidence, workspace and resource leases, durable `Job`/`Run` with per-attempt
journals, hash-chained tamper-evident audit, memory scope ACLs, GPU arbitration with VRAM
fitting, or capability routing that can be overridden by local benchmarks.

**Every one of them assumes a fast, cheap, remote model and a trusting user.** The closest
anything comes is Crush's per-tool permissions and OpenCode's plan-agent restrictions — both of
which are session-scoped flags, not durable, expiring, auditable authority.

So the honest verdict stands and sharpens: **build none of the harness; build all of the
kernel.** The correct product is our authority plane with the field's best loop mechanics
plugged into it — and the fastest route to that is to make our tools reachable *by their
harnesses* (MCP server, already 122 lines away) while porting the four or five mechanisms above
that are genuinely about surviving on 16K and 6 tok/s.

---

## Ranked adoption order

Effort is rough and assumes the kernel stays as-is.

| # | Item | Source | Effort | Why this rank |
| --- | --- | --- | --- | --- |
| 1 | Widen the MCP bridge from 3 to all 13 tools | ours | ~1 day | Every harness in Tier 1–2 becomes able to run on our governed tools. Highest leverage line-for-line in the project |
| 2 | Run the harness tournament for real: Pi vs OpenCode vs Goose vs native, all bridged | ours | days | The project's own rule, never applied to its most important decision. Everything below should be decided by its result |
| 3 | Summarising `read` + parallel ripgrep `grep` | oh-my-pi | ~1 day | Immediate context savings; no new dependency |
| 4 | Focus Chain (re-injected todo list) | Cline | ~1 day | Cheapest fix for compaction drift |
| 5 | Parallel tool dispatch | ForgeCode | ~2 days | Direct multiplier on wall time |
| 6 | Hash-anchored edits, per-model edit format | oh-my-pi + Aider | ~3 days | Biggest output-token saving; needs care to keep the refuse-don't-corrupt property |
| 7 | Advisor role on the fast brain | oh-my-pi | ~3 days | Oversight without context tax; first concrete step toward `D-037` |
| 8 | Cumulative diff sandbox | Plandex | ~1 week | Solves approval evidence + diff view together; may amend `D-021`/`D-028` |
| 9 | MCP client with elicitations | fast-agent | ~1 week | Unlocks Serena/LSP and makes our approvals reachable by other tools |
| 10 | Architect/editor split across our two brains | Aider | ~3 days | Best use of the hardware we already have |
| 11 | Boomerang-style subtasks with schema-validated returns | Kilo + oh-my-pi | ~1 week | Context isolation with a contract |
| 12 | ACP (Zed) server | Zed | ~1 week | Every editor, one implementation |
| 13 | Auxiliary services on the event stream + deterministic replay | OpenHands | ~1 week | Substrate for the authority-legibility inspector |
| 14 | Hooks as in-process extension points | Pi | ~1 week | Our hook story is currently "the policy engine", which is not user-programmable |

Items 1–2 gate everything. Items 3–7 are all "make a weak model succeed more often per token"
and should be measured against the tournament baseline, individually.

## Open questions this research did not settle

- **Cordis' event-journal and session-log design** — `docs/architecture.md` was not retrieved.
  Required reading before we finalise any plugin seam.
- **ForgeCode's licence** — reported as OSS, not verified at primary source. No code may be
  taken until it is.
- **Does hash-anchored editing survive a model that was never trained on it?** The
  `vendor-claim` is from Grok-family models. Our models are Qwen/Nemotron. This must be
  measured, not assumed — the same trap V4A represents.
- **Which "ACP" does Qwen Code's daemon mode speak?** Affects whether it is an editor
  integration or an agent-to-agent one.
- **Is Pi's 3× context advantage transferable, or an artifact of its provider mix?** The
  benchmark used frontier models; our regime is different and could amplify *or* erase it.
- **LLMling-Agent** — does it exist under another name?

## Primary sources consulted (2026-08-23)

- [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) and its README
- [anomalyco/opencode](https://github.com/anomalyco/opencode)
- [earendil-works/pi](https://github.com/earendil-works/pi)
- [can1357/oh-my-pi](https://github.com/can1357/oh-my-pi)
- [QwenLM/qwen-code](https://github.com/QwenLM/qwen-code)
- [block/goose](https://github.com/block/goose)
- [charmbracelet/crush](https://github.com/charmbracelet/crush)
- [SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering (NeurIPS 2024)](https://arxiv.org/abs/2405.15793)
- [SWE-agent ACI documentation](https://swe-agent.com/0.7/background/aci/)
- [Codex apply_patch tool instructions](https://github.com/openai/codex/blob/main/codex-rs/apply-patch/apply_patch_tool_instructions.md)
- [Aider edit formats](https://aider.chat/docs/more/edit-formats.html)
- [Cline context management](https://deepwiki.com/cline/cline/3.5-context-management) and [subagents/focus chain](https://deepwiki.com/cline/cline/3.6-subagents-and-focus-chain)
- [OpenHands Software Agent SDK paper](https://arxiv.org/pdf/2511.03690)
- [Gemini CLI checkpointing](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/checkpointing.md)
- [plandex-ai/plandex](https://github.com/plandex-ai/plandex)
- [evalstate/fast-agent](https://github.com/evalstate/fast-agent)
- [Roo Code Boomerang Tasks](https://docs.roocode.com/features/boomerang-tasks)
- [Zed Agent Client Protocol](https://zed.dev/acp)
- [Cordis explained](https://agentatlas.org/blog/cordis-explained-how-deepseek-harness-plugin-framework-works/) — `landscape`
- [Pi harness guide](https://explainx.ai/blog/pi-minimal-agent-harness-mario-zechner-guide-2026) — `landscape`
- [ForgeCode on Terminal-Bench](https://www.tensorlake.ai/blog/forgecode-terminal-bench) — `landscape`
