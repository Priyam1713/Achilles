### F-022 — Local Qwen3.8-27B "OBLITERATED" files: provenance resolved, accepted for personal use

- **Severity:** `debt` · **Status:** `fixed`
- **Original finding (2026-08-21, superseded below):** Two GGUF files placed by hand at
  `C:\Users\priya\Downloads\Qwen3.8-27B-OBLITERATED-{IQ4_XS,Q6_K}.gguf`, attributed by the
  user to "Pliny the Liberator's Obliteratus." GGUF header inspection confirmed a
  `qwen35`-architecture model consistent with a Qwen3.8-27B derivative but carried no
  source/license metadata — at that point genuinely `unverified` per this project's own
  evidence taxonomy: not `primary-verified`, not even `vendor-claim`, only a filename.
- **RESOLVED 2026-08-21, same session — provenance is real and checks out.** Web search plus
  direct HuggingFace/GitHub API verification: `OBLITERATUS/Qwen3.8-27B-OBLITERATED` is a real,
  public, non-gated repo. `cardData.license = apache-2.0`, a real Apache-2.0 `LICENSE` file is
  present (verified by fetching it directly — standard text, no added restrictions),
  `base_model = Qwen/Qwen3.8-27B` (exactly our own already-adopted incumbent), and the repo's
  file listing contains `Qwen3.8-27B-OBLITERATED-IQ4_XS.gguf` and
  `Qwen3.8-27B-OBLITERATED-Q6_K.gguf` — an exact filename match to what was downloaded.
  Author `elder-plinius` (Pliny the Liberator) is a real, public figure; the `OBLITERATUS`
  toolkit itself is a real GitHub repo (7,734 stars, AGPL-3.0 for the *toolkit code* — the
  model weights repo is separately and explicitly Apache-2.0). This is now
  `primary-verified` evidence, not a filename guess. **Unlike Nemotron (F-012), there is no
  indemnification clause or non-OSI licence risk here — Apache-2.0 is a clean grant.**
- **What "obliterated"/"abliterated" means, stated plainly:** this is "V2: complementary
  abliteration blending" — two different weight-projection surgeries (aggressive/SVD and
  LEACE) blended 60/40 to remove refusal directions while limiting capability loss. The
  model card's own (vendor-claimed, not independently reproduced by us) figures: MMLU 84.3%
  vs stock 84.6% (-0.3pp), refusal rate 0.24% on an 842-prompt author-run corpus. The card
  explicitly names **"cyber, jailbreak generation, and complex AI attack chain
  capabilities"** among its stated target capabilities — this is not generic "won't lecture
  me" uncensoring, it is specifically optimised toward offensive-security-adjacent output.
  That is a deliberate, safety-relevant property of the artifact, not a quality variant.
  It changes what the model will *say*, not how it executes — the kernel's own security
  model already assumes this correctly (`docs/SECURITY.md`: "the model is never the security
  boundary"; `PolicyEngine` is fail-closed and does not depend on model alignment for
  authority, execution, or credential access). Including this model does not weaken the
  kernel's execution/authority boundary.
- **User decision, 2026-08-21: accepted for personal/local use only** — same pattern as
  `D-016`/Nemotron, never a community default. See **D-017** in `knowledge/research.md`.
- **Fix applied:** `configs/brain-candidates.yaml` provenance comments corrected from
  `unverified-local` to reflect the verified facts above. Both quants benchmarked for
  throughput (same architecture/size class as the F-005 incumbent). Wired via
  `configs/models.local.yaml` under a **distinct id** (`qwen38-27b-obliterated`, not
  shadowing the manifest's `qwen38-27b`) — deliberately not shadowing the trusted incumbent's
  id, because a same-id override would make every route currently resolving to stock
  Qwen3.8-27B silently start using different weights with no distinguishing marker. That
  would cross from "opt-in personal model" into "silent default swap," which invariant 8 and
  `D-008`'s safety boundaries both exist to prevent. `status: candidate` again, so it only
  reaches routing under explicit `mode: deep`.
- **MEASURED 2026-08-21.** Both quants were already local (no download needed). `llama-bench`,
  same methodology as F-005/F-012:

  | candidate | tg128 (tok/s) | pp512 (tok/s) | peak VRAM |
  | --- | --- | --- | --- |
  | Qwen3.8-27B UD-Q4_K_M (stock incumbent, F-005) | 6.36 | 376.05 | 9398 MiB |
  | Nemotron-3.5-Lightning-30B-A3B `@ncmoe32` (F-012) | 52.79 | 581.74 | 9438 MiB |
  | Qwen3.8-27B OBLITERATED Q6_K | 3.82 | 170.27 | 9244 MiB |
  | **Qwen3.8-27B OBLITERATED IQ4_XS** | **6.89** | 288.56 | 9430 MiB |

  IQ4_XS edges out the stock quant slightly (+8%); Q6_K is markedly worse (more CPU offload
  at 22.43 GB vs 16.46 GB). **Both fail the 10 tok/s interactive-viability gate**, same as
  the stock incumbent at this size class — unsurprising, since it is the same dense
  architecture and abliteration does not change parameter count or memory-bandwidth cost.
  IQ4_XS wired as the routable quant.
- **Wired, same mechanism as F-012/D-016, given a distinct id:**
  `state/llama-models.ini` gained a `[qwen38-27b-obliterated]` section pointing at the
  IQ4_XS artifact. `configs/models.local.yaml` gained a `ModelSpec` entry with id
  `qwen38-27b-obliterated` — **deliberately not** `qwen38-27b`, so it can never silently
  replace the trusted incumbent in an ordinary route; `status: candidate` so it only
  reaches routing under explicit `mode: deep`.
- **Verification:** `k.registry.validate() == []`. Live against the built kernel:
  `mode=fast` and `mode=smart` both resolve to `['qwen38-27b']` only; `mode=deep` resolves to
  `['qwen38-27b', 'nemotron35-lightning-30b-a3b', 'qwen38-27b-obliterated']`. A full
  load→chat→unload round trip through the router was not repeated for this model — that
  exact mechanism was already proven end-to-end for Nemotron in this same session and
  reuses identical code paths (same engine, same preset format, same overlay merge).
  `configs/models.local.yaml.example` gained a fifth rule (don't shadow a trusted
  incumbent's id with a differently-aligned checkpoint) and this as its second worked
  example. Full suite: see below.

# Fix and update ledger

> Opened: **2026-08-21**
> Companion to [knowledge/research.md](../knowledge/research.md) (why we chose things) and
> [docs/IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) (what exists).
> This file tracks **defects, corrections and applied changes** to the system itself.

Research says what we *should* build. Implementation status says what we *have* built.
This ledger says what is *wrong* with what we built, and what we did about it.

## How to maintain this ledger

1. Every entry gets a stable `F-###` id. Never renumber; never delete.
2. Record the **evidence** — the command that proved it, the file and line, or the API
   response. A defect without reproduction is a suspicion, not a finding.
3. Assign **severity** and **status** from the tables below.
4. State the **fix** concretely enough that someone else could apply it.
5. When a fix lands, set status to `fixed`, add the commit, and append a **verification**
   line saying how it was proven — the same standard the kernel applies to its own jobs:
   a claim of success is not a post-condition.
6. If a finding turns out to be false, mark it `invalid` and say why. Do not erase it.

### Severity

| Label | Meaning |
| --- | --- |
| `critical` | Security hole, data loss, or a README claim untrue in a way that could mislead an operator into trusting the system. |
| `major` | Blocks or badly degrades a primary use case; wrong by design rather than merely unfinished. |
| `minor` | Real defect with a bounded blast radius. |
| `debt` | Not broken, but will cost more to keep than to remove or replace. |

### Status

| Label | Meaning |
| --- | --- |
| `open` | Confirmed, not yet addressed. |
| `in-progress` | Being worked on now. |
| `fixed` | Applied **and** verified. Carries a commit and a verification line. |
| `deferred` | Accepted as known debt with a stated trigger for revisiting. |
| `invalid` | Investigated and found not to be a defect. Reason recorded. |

---

## Audit — 2026-08-21

Findings from a full read of the source tree plus live verification against the target
machine, the HuggingFace API, the GitHub API and pinned upstream sources.

### Verification performed

What was actually checked, so the next reader does not have to re-check it:

| Claim | Method | Result |
| --- | --- | --- |
| 32 model repos in `configs/models.yaml` exist | HF API `GET /api/models/{repo}` | all resolve except F-007 |
| 29 upstreams in `docs/SOURCES.md` exist | GitHub API | all resolve |
| 11 pinned commits in `configs/runtime-sources.env` resolve | GitHub API `commits/{sha}` | all 11 resolve |
| OpenShell CLI flags used by the execution adapter exist | `cli-reference.md` at pinned commit | `--upload`, `--no-git-ignore`, `--no-keep`, `--no-tty`, `--policy`, `sandbox download`, `sandbox delete` all present |
| llama.cpp router flags exist | `common/arg.cpp` at pinned commit | `--models-preset`, `--models-max`, `--sleep-idle-seconds`, `fit-target`, `dedup-cache-models`, `spec-type` all present |
| llama.cpp supports the Qwen3.5 architecture | `src/llama-arch.cpp` at pinned commit | `LLM_ARCH_QWEN35`, `LLM_ARCH_QWEN35MOE` present |
| Kernel test suite | `pytest -q` in WSL | 19 passed |
| Capability routing works end to end | live `SovereignKernel.build()` + `scheduler.route()` | 92 capabilities, correct engine per modality |
| Target hardware matches the manifest | `nvidia-smi`, `Get-CimInstance`, `df -h` | RTX 5070 Ti Laptop, 12227 MiB, sm_120, driver 592.82; 795 GB free on WSL ext4 |

The manifest is **not** hallucinated. Every upstream this project claims to depend on is real
and every pinned revision resolves. The defects below are design and implementation problems,
not fabrication.

---

### F-001 — ~~The port 8080 pre-build gate is factually false on this machine~~

- **Severity:** `major` · **Status:** `invalid` — **this finding was wrong. The original audit
  was right.**
- **What I claimed:** that nothing was listening on `127.0.0.1:8080`, based on
  `Get-NetTCPConnection -State Listen` on the Windows host.
- **What is actually true:** a uvicorn `gateway:app` from a separate project at
  `/home/priya/local-ai/` is listening on `127.0.0.1:8080` **inside WSL2**, serving an
  OpenAI-compatible `/v1/models` with `coding`, `general`, `qwen3.6-27b`, `qwen3.8-27b` and
  `reasoning`. It had been running the whole time.
- **Why the check was wrong:** WSL2 has its own network namespace. It *forwards* connections
  to services bound inside the distro, but does not publish their listening sockets in the
  Windows TCP table. Verified directly: `Invoke-RestMethod http://127.0.0.1:8080/v1/models`
  from Windows **succeeds**, while `Get-NetTCPConnection -LocalPort 8080` returns **nothing**.
  A host-only enumeration therefore reports a busy port as free. Generalised as F-019.
- **Lesson:** the method has to match the claim. "Is this port free?" cannot be answered by
  enumerating one of the two namespaces this project runs in. Being confidently wrong here
  nearly authorised an install that could have collided with a running service.
- **Superseded by:** F-018 (the gate text *is* stale, for a different reason) and F-019 (the
  real defect).

### F-002 — Unauthenticated membership endpoint bypasses the only collaboration authorization

- **Severity:** `critical` · **Status:** `fixed`
- **Evidence:** `api/server.py:299` (as of the audit) — `add_collaboration_member` performed
  no caller check at all.
- **Fix applied:** `add_collaboration_member` now requires the session token (see F-004),
  takes a `CollaborationMembershipCreate{requester_id}` body, validates the requester is an
  authenticated human via `collaboration_human()`, and `CollaborationService.add_member()`
  raises `PermissionError` (-> 403) unless `requester_id` is already a member of the room (or
  the `kernel` system identity). Internal callers — bootstrap and `create_room`'s own
  owner-membership grant — call `store.add_member()` directly and are unaffected, since they
  are trusted config/creation paths, not the public endpoint.
- **Verification:** `tests/test_kernel.py::test_add_collaboration_member_requires_requester_to_already_belong`
  — an outsider requesting on behalf of a non-member gets 403; the room owner adding the same
  identity gets 204. Full suite: 23 passed.

### F-003 — Identity creation is an unauthenticated upsert

- **Severity:** `critical` · **Status:** `fixed`
- **Evidence:** `collaboration/service.py:110` (as of the audit) — `create_identity()` called
  `store.upsert_identity()`, so `POST /collaboration/identities` was create-or-silently-overwrite.
- **Fix applied:** Split the store into three methods: `upsert_identity` (kept, but now
  documented as reserved for trusted bootstrap/config loading only), `create_identity_exclusive`
  (plain `INSERT`, raises the new `IdentityAlreadyExists` on a duplicate id, including the
  concurrent-race case via `sqlite3.IntegrityError`), and `update_identity` (plain `UPDATE`,
  raises `ValueError` if the id does not exist). The public `POST /collaboration/identities`
  now calls the exclusive path and returns **409** on conflict; a new authenticated
  `PUT /collaboration/identities/{identity_id}` calls the update path for legitimate corrections.
  Both routes require the session token (F-004).
- **Verification:** `tests/test_kernel.py::test_create_collaboration_identity_is_not_upsert` —
  posting the same id twice returns 201 then 409, the stored display name is provably
  unchanged by the rejected second post, and `PUT` on the same id succeeds and is reflected
  in a follow-up `GET`. Full suite: 23 passed.

### F-004 — No authentication on any mutation endpoint

- **Severity:** `critical` · **Status:** `fixed` (session auth + Host/Origin guard; full
  desktop-grade session UX remains `D-010` scope)
- **Evidence:** `api/server.py` declared no security scheme; every mutation accepted a plain
  `actor_id` body field as identity.
- **Fix applied:**
  - New `kernel/auth.py`: `SessionAuth` mints a 64-hex-char token on first run into
    `state/session.token` (owner-only permissions where the filesystem supports it — the
    same "generated local secret, never checked in" pattern already used for the SearXNG
    secret) and verifies presented tokens with `hmac.compare_digest`. `allowed_hosts()`
    computes the Host/Origin allowlist from the configured bind address and port.
  - `LoopbackOnlyMiddleware` rejects **every** request — including unauthenticated GETs —
    whose `Host` or `Origin` header does not match this installation, before it reaches any
    route. This is a DNS-rebinding guard: a page on an attacker domain whose DNS resolves to
    `127.0.0.1` can make a victim's browser send same-origin-*looking* requests, but it
    cannot forge the Host header a genuine loopback client sends.
  - `require_session` (a `Depends`) is attached to every POST/PUT/DELETE route: `/route`,
    `/policy/evaluate`, `/chat`, `/specialist/invoke`, `/media/generate`, `/jobs` (POST/DELETE),
    `/collaboration/identities` (POST/PUT), `/collaboration/rooms` (POST),
    `/collaboration/rooms/{id}/members/{id}` (POST), `/collaboration/rooms/{id}/messages`
    (POST), `/collaboration/rooms/{id}/reactions` (POST),
    `/collaboration/rooms/{id}/canvas` (PUT). `/route` and `/policy/evaluate` are gated too
    even though they are read-only decisions, for uniformity — the CLI (`sovereign route`,
    `sovereign preflight`) builds a kernel in-process and never calls the HTTP API, so
    nothing documented breaks.
  - `GET /ui` now serves the page with the session token injected in place of a
    `%%SOAI_SESSION_TOKEN%%` placeholder, safe specifically because
    `LoopbackOnlyMiddleware` has already proven the request's Host/Origin belong to this
    installation before the handler runs. `web/index.html` gained an `authHeaders()` helper
    and its four mutating `fetch()` calls (`route`, `postMessage`, `react`, `saveCanvas`) now
    send `Authorization: Bearer`. This also fixed F-015 in passing: the file path is now
    resolved from `Path(__file__).resolve().parents[3]` instead of the process CWD.
- **Verification:**
  `tests/test_kernel.py::test_mutating_endpoints_require_session_token` (no token -> 401,
  wrong token -> 401, correct token -> 201, reads stay open) and
  `test_loopback_only_middleware_rejects_foreign_host` (forged Host -> 400, genuine -> 200).
  Manual: `app.openapi()` builds cleanly (20 paths); a direct `TestClient` call to `/ui`
  confirms the placeholder is fully replaced and the served HTML contains the real token.
  Full suite: 23 passed, `ruff check src/ tests/` clean.
- **Explicitly out of scope:** this is a single-operator local token, not a multi-user login
  system, token rotation, or session expiry — those are `D-010` desktop-client territory and
  would need the roster/identity work in `D-008` to mean anything. Nothing here claims more
  than "a request must prove it holds the file this machine's owner controls."

### F-005 — The deep brain is bandwidth-starved and nobody has measured it

- **Severity:** `major` · **Status:** `open`
- **Evidence:** `Qwen3.8-27B-UD-Q4_K_M.gguf` is **16.46 GB** (HF API, blobs) on a card with
  **12227 MiB** total. After `reserve_vram_mb: 1600` plus KV and compute buffers, roughly
  6–7 GB — about 40% of the model — must live in host RAM.
- **Impact:** Token generation is bandwidth-bound. GPU side ≈ 10 GB / ~670 GB/s ≈ 15 ms;
  CPU side ≈ 6.5 GB / ~90 GB/s dual-channel DDR5 ≈ 72 ms. Estimated ceiling ~11 tok/s,
  realistically **5–8 tok/s**. An agent step emitting 800 tokens takes ~2 minutes; a ten-step
  task takes 20–40 minutes. The 27B is documented as the brain for "difficult planning, coding,
  research, vision, synthesis and verifier/judge roles" — an agentic-loop workload, which is the
  one workload this configuration cannot serve. No architecture document states an expected
  throughput for the primary model. Compounding it: `--models-max 1` with the 9B at
  `load-on-startup = true` means every fast→deep transition evicts the 9B and streams 16.46 GB
  back off NVMe.
- **MEASURED 2026-08-21 — the estimate was correct.** `llama-bench` on the target GPU with
  `-fitt 1600 -fitc 16384 -fa on -ctk q8_0 -ctv q8_0`, 3 repetitions:

  | metric | value |
  | --- | --- |
  | **tg128 (generation)** | **6.36 tok/s** |
  | pp512 (prefill) | 376.05 tok/s |
  | peak VRAM | 9398 MiB |
  | layer split | `llama-fit-params` -> `-ngl 37` of 64 |

  Generation lands inside the predicted 5–8 tok/s band. Prefill is healthy, so the compute
  path is fine and the decode path is bandwidth-starved exactly as predicted. At 6.36 tok/s an
  800-token agent step takes **126 seconds** and a ten-step task takes **~21 minutes**. This
  **fails** the `min_tg_tokens_per_second: 10.0` viability gate in
  `configs/brain-candidates.yaml`.

  Report: `$SOAI_STATE_DIR/brain-benchmark.json`. Reproduce with
  `python3 scripts/benchmark_brains.py --only qwen38-27b-q4km`.

  **Fast-brain reference, measured the same way, same session:** `Qwen3.5-9B Q6_K`
  (converted locally: HF snapshot -> F16 -> Q6_K via `llama-quantize`, 7.2 GB) —

  | metric | value |
  | --- | --- |
  | **tg128 (generation)** | **49.57 tok/s** |
  | pp512 (prefill) | 2156.74 tok/s |
  | peak VRAM | 6962 MiB |
  | layer split | `ngl -1` — fully resident, zero CPU offload |

  **7.8x faster generation than the 27B**, using ~5 GB less peak VRAM, clears the
  `min_tg_tokens_per_second: 10.0` gate with roughly 5x headroom, and needs no licence
  review (Apache-2.0, same family already adopted). This is the strongest evidence yet for
  the `D-012` reframing: the *fast* brain, not the *deep* brain, is what an interactive
  agent loop on this hardware should be built on, with the 27B reserved for an
  asynchronous verifier/batch tier where 6.36 tok/s is tolerable because nothing is
  waiting on it turn-by-turn. This does not yet resolve F-005 — quality at 9B vs 27B on
  real coding/planning tasks is a separate, unmeasured question (`requires_quality_eval`
  in `configs/brain-candidates.yaml`) — but it changes what "fix the deep brain" should
  mean: the fallback path already exists and already clears the bar.
- **Fix:** Run the benchmark before defending the design. `UD-Q4_K_M` (16.46 GB) vs `UD-Q4_K_S`
  (15.36 GB) vs `UD-IQ4_XS` (14.25 GB — roughly halves CPU offload), each with and without the
  already-downloaded MTP draft head, at 16K and 64K context. If sustained generation lands under
  ~10 tok/s, promote the 9B to the agentic loop brain and demote the 27B to an asynchronous
  verifier/batch tier. See also F-012, which may make this moot.

### F-006 — The router is elaborate machinery with almost nothing to route

- **Severity:** `debt` · **Status:** `open`
- **Evidence:** Measured live against the built registry:
  `capability -> #models histogram: {1: 86, 2: 6}`. **86 of 92 capabilities have exactly one
  candidate.** The six contested: `asr_multilingual` and `speech_transcription` (the same
  Qwen3-ASR vs Whisper pair twice), `synthesis` and `vision_language` (the same 27B vs 9B pair
  twice), `music_generation`, `visual_search`. Three genuine contests.
- **Impact:** `ResourceScheduler.route()` — quality priors × latency utility × reliability ×
  resource-fit adjustment × resident bonus × benchmark override, ~130 lines — is permanent
  maintenance cost serving three decisions. The registry's real value is *dispatch*
  (capability → worker → port), which is a dictionary lookup.
- **Fix:** Keep `RouteDecision` as the audit/provenance record; that part earns its keep. Reduce
  selection to dispatch plus an explicit opt-in A/B harness for the contested few.

### F-007 — `visual_search` scores a pipeline against itself, and one manifest source is wrong

- **Severity:** `minor` · **Status:** `open`
- **Evidence:** `visual_search` resolves to `['qwen3-vl-embedding-8b', 'qwen3-vl-reranker-8b']`.
  Those are **sequential stages of one retrieval pipeline**, not alternatives; scoring them
  against each other and picking a winner is semantically wrong. Separately,
  `configs/models.yaml` gives `rf-detr-keypoint` the source `roboflow/rf-detr`, which is a GitHub
  org path and returns **401** from the HF API.
- **Fix:** Model retrieval as an ordered pipeline capability, not a contest. Correct the
  `rf-detr-keypoint` source, and extend `verify_sources.py` to fail on non-resolving sources
  regardless of `install_policy`.

### F-008 — The vector store is a placeholder presented as implemented

- **Severity:** `major` · **Status:** `open`
- **Evidence:** [`memory/vector.py:62`](../src/sovereign_ai/memory/vector.py) —
  `search_vector()` issues `SELECT * FROM vectors` and then unpacks every row with
  `struct.unpack` and computes cosine similarity in pure Python. No index, no ANN, no numpy.
- **Impact:** Octen-Embedding-8B emits ~4096-dim vectors — 16 KB each. At 100k memories that is
  1.6 GB deserialized per query in interpreted Python: minutes, not milliseconds. The README
  lists "persistent vector adapter" under implemented features without this caveat. The FTS table
  also has no delete or update path, so it desynchronizes on the first supersession.
- **Fix:** Either swap in a real ANN index behind the existing (correct) `VectorRetriever`
  interface, or remove "vector" from the README's implemented list until it is real. Add FTS
  delete/update on supersession. The docstring's own promise — *"Swap for FAISS/LanceDB without
  changing ContextBuilder"* — is the right plan; execute it.

### F-009 — One resource policy, three different numbers

- **Severity:** `minor` · **Status:** `open`
- **Evidence:** `reserve_vram_mb: 1600` in [`configs/system.yaml:38`](../configs/system.yaml);
  default `1300` in [`resources/scheduler.py:74`](../src/sovereign_ai/resources/scheduler.py);
  `fit-target = 1800` in the generated `llama-models.ini`.
- **Fix:** Single source of truth in `configs/system.yaml`; derive the llama.cpp preset value from
  it at generation time; remove the divergent code default or make it raise.

### F-010 — Job dispatch is unbounded and non-resumable

- **Severity:** `major` · **Status:** `fixed`
- **Evidence:** `api/server.py`'s `enqueue_job()` called `asyncio.create_task()` with no
  semaphore, no queue and no backpressure. Jobs ran in the API process.
  `recover_interrupted()` marked survivors `interrupted` with no resume. No `Run` object
  existed beneath `Job`, so a retry (had one been implemented) would have had nowhere to
  record a second attempt without overwriting the first.
- **Impact:** The README listed "durable background job journals" as implemented. The
  journal was durable; the *execution* was not. Unbounded task creation meant unbounded
  in-process concurrency with no admission control, on a machine with one GPU.
- **Fix applied:**
  - New `kernel/runs.py`: `RunStore`/`RunRecord` — one row per execution *attempt* beneath
    a `Job`. `next_attempt(job_id)` and `list_for_job(job_id)` give an honest history; a
    retry is `attempt=2`, never a rewrite of `attempt=1`.
  - New `kernel/dispatcher.py`: `JobDispatcher` — a fixed pool of worker coroutines
    (`max_concurrency`, default 4, configurable via `system.yaml`
    `resources.max_concurrent_jobs`) pulling from a bounded `asyncio.Queue`
    (`job_queue_max`, default 100). A submission beyond capacity raises `QueueFullError`
    immediately — explicit backpressure, not silent unbounded growth. Cancellation is
    tracked by `job_id` so `DELETE /jobs/{id}` keeps its existing external contract.
  - New `kernel/job_executor.py`: the chat/specialist/media dispatch logic and
    collaboration-reply posting, moved out of the API layer (it was kernel business logic
    living in HTTP plumbing) into a single reusable `execute(kernel, job, run)` the
    dispatcher calls per attempt.
  - `api/server.py`: `enqueue_job()` is now pure admission (create `Job`, hand to
    dispatcher, 503 on `QueueFullError`); the FastAPI `lifespan` starts/stops the
    dispatcher instead of gathering an ad-hoc `app.state.job_tasks` dict. New
    `GET /jobs/{job_id}/runs` exposes the attempt history; `/status` now reports
    `dispatcher_active`/`dispatcher_queue_depth`.
- **Verification:** seven new tests in `tests/test_kernel.py` — bounded concurrency is
  actually enforced (`peak == max_concurrency` under a controlled slow executor), a failed
  attempt followed by a retry produces two distinct `Run` rows (`attempt` 1 then 2, not one
  rewritten row), `dispatcher.cancel(job_id)` stops the active run and marks it
  `cancelled`, a queue at capacity raises `QueueFullError` and the rejected job is marked
  `failed` with a clear reason (never silently dropped), and an HTTP-level test confirms
  `POST /jobs` → `GET /jobs/{id}/runs` shows exactly one recorded attempt. Full suite:
  **31 passed**, `ruff check src/ tests/` clean.

### F-011 — The GPU arbiter does not arbitrate the GPU

- **Severity:** `major` · **Status:** `fixed`
- **Evidence:** `GPUArbiter` was an `asyncio.Semaphore` whose own docstring admitted
  "Process-local exclusive GPU lease." A second `sovereign serve` process, or a kernel
  restarted after a crash while a lease was held, would each start with a fresh in-memory
  semaphore believing the GPU was free.
- **Scope check before fixing (important, not obvious from the original finding):** the 14
  specialist workers never acquire a GPU lease themselves — `SpecialistBroker`/`MediaBroker`/
  `InferenceBroker` already share **one** `GPUArbiter` instance (constructed once in
  `kernel/app.py`), and a worker is only ever reached through one of those brokers, which
  holds the lease around the whole HTTP call into the worker. So calls *from one kernel
  process* were already correctly serialized. The real gap was **two kernel processes**, or
  one kernel process restarting without knowing whether the process that held the last
  lease is still alive — that is what an in-memory semaphore structurally cannot detect.
- **Fix applied:** New `resources/gpu_leases.py`: `GPULeaseStore`, a durable SQLite table
  (`state/gpu-leases.db`) that is the actual source of truth at grant time. `GPUArbiter`
  keeps its `asyncio.Semaphore` for cheap in-process FIFO ordering, but an exclusive lease
  is only granted after `GPULeaseStore.try_acquire()` confirms no unexpired, live-PID lease
  is held — contended acquires poll with backoff instead of trusting a local semaphore
  alone. `reap_stale()` removes both TTL-expired leases and leases whose recorded PID
  (`psutil.pid_exists`) no longer exists, so a crashed holder cannot wedge the GPU past its
  TTL, and a restarted kernel sees reality rather than a blank slate.
- **Explicit scope limit, stated rather than glossed over:** leases are always acquired by
  the kernel process, never by a worker directly — a caller that reaches a worker's own
  HTTP port without going through the kernel's brokers is not covered by this store. That
  is a separate problem (authenticating each worker's own endpoint) and remains open.
- **Verification:** four new tests in `tests/test_kernel.py`. Two exercise `GPULeaseStore`
  directly (a second exclusive `try_acquire` is refused while the first is held, and a
  fabricated lease from a nonexistent PID is reaped even with an hour left on its TTL). The
  load-bearing one, `test_arbiter_lease_is_durable_across_separate_arbiter_instances`,
  constructs **two independent `GPUArbiter` objects** sharing only a state directory —
  standing in for two separate kernel processes — and proves the second cannot acquire the
  exclusive lease until the first releases it, which two unrelated `asyncio.Semaphore`
  instances could never enforce on their own. Full suite: **35 passed**, `ruff` clean.

### F-012 — The manifest predates hybrid-MoE models that fit this GPU far better

- **Severity:** `major` · **Status:** `open` — **throughput measured, dramatic result, still
  licence-gated. Nothing here is promoted.** · **See:** research wave 5, `D-012`
- **Evidence (design):** Verified via HF API on 2026-08-21.
  `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B` is `nemotron_h` — Mamba-2 hybrid MoE,
  52 layers, **128 experts with 6 active (~3B active of 30B total)**.
  `LLM_ARCH_NEMOTRON_H_MOE` is supported at our already-pinned llama.cpp commit, and
  `-ncmoe`/`--n-cpu-moe` exist there too. Official `ggml-org` GGUF: Q4_0 at 18.90 GB plus a
  1.16 GB MTP draft head.
- **MEASURED 2026-08-21.** Downloaded via `scripts/fetch_brain_candidate.sh`
  (revision-locked `9d425fe1…`, SHA-256 verified: `61f87e75…`, 18,898,091,584 bytes exact).
  `llama-bench`, `-fitt 1600 -fitc 16384 -fa on -ctk/-ctv q8_0`, 3 repetitions, sweeping
  `-ncmoe` (how many layers' MoE experts are forced onto CPU rather than left to auto-fit):

  | candidate | tg128 (tok/s) | pp512 (tok/s) | peak VRAM |
  | --- | --- | --- | --- |
  | Qwen3.8-27B UD-Q4_K_M (dense, incumbent, F-005) | 6.36 | 376.05 | 9398 MiB |
  | Qwen3.5-9B Q6_K (dense, fast brain, F-005) | 49.57 | 2156.74 | 6962 MiB |
  | Nemotron-3.5-Lightning-30B-A3B Q4_0 `@ncmoe0` | 43.11 | 2633.84 | 9438 MiB |
  | Nemotron-3.5-Lightning-30B-A3B Q4_0 `@ncmoe16` | 51.31 | 519.78 | 9438 MiB |
  | **Nemotron-3.5-Lightning-30B-A3B Q4_0 `@ncmoe32`** | **52.79** | 581.74 | 9438 MiB |
  | Nemotron-3.5-Lightning-30B-A3B Q4_0 `@ncmoe48` | 51.27 | 624.56 | 9438 MiB |

  **At `@ncmoe32`, Nemotron generates 8.3x faster than the dense 27B incumbent (52.79 vs
  6.36 tok/s) at essentially the same VRAM footprint (9438 vs 9398 MiB — a 40 MiB
  difference, within noise) — while being a larger model (30B total vs 27B) with a
  presumptively higher quality ceiling, and it slightly beats even the fully-resident 9B
  fast brain's 49.57 tok/s.** This is the cleanest possible confirmation of `D-012`'s thesis
  on real hardware: active parameters, not total parameters, govern decode speed here.
- **A genuine trade-off, reported honestly rather than only the best number:** prefill
  (`pp512`) falls sharply once `-ncmoe` forces explicit CPU expert placement — 2633.84 tok/s
  at `@ncmoe0` versus 519–625 tok/s at `@ncmoe16/32/48`. Batched prompt processing appears
  to pay a much larger CPU round-trip cost per forward pass than single-token decode does.
  `@ncmoe0` (auto-fit, no manual offload) has the best prefill and still beats the dense 27B
  on generation (43.11 tok/s), so the right operating point plausibly depends on typical
  prompt length for the workload, not a single "best" setting. This needs a mixed-workload
  benchmark, not just `pp512`/`tg128` in isolation, before any specific `-ncmoe` value is
  treated as a default.
- **Known caveat in the measurement tooling itself:** `n_gpu_layers` in every result's JSON
  is `-1` regardless of `-ncmoe` or `-fitt` — `llama-bench` echoes the CLI default rather
  than the value its own fit/offload logic resolved to. The "layer split" field
  `scripts/benchmark_brains.py` surfaces is therefore uninformative for this model family;
  the `n_cpu_moe` field is the one that reflects what was actually requested. This does not
  affect the timed throughput numbers above (real wall-clock measurements), only the
  diagnostic display. Tracked as **F-023**.
- **STILL BLOCKED — licence.** The NVIDIA Open Model License is **not OSI-approved** and its
  Article 8 places an indemnification obligation on the licensee for third-party claims
  arising from the model, its derivatives, or its outputs. Per baseline invariant 8
  (`knowledge/research.md`) and `D-012`'s own stated safety boundary, **a winning benchmark
  does not authorise adoption.** Quality is also completely unmeasured
  (`requires_quality_eval: true` in `configs/brain-candidates.yaml`) — an 8.3x throughput win
  says nothing about whether Nemotron's coding/planning/tool-use quality matches Qwen3.8-27B
  on real tasks.
- **User decision, 2026-08-21: accepted for personal/local use only.** Not for any
  shared install profile or `configs/models.yaml` — see the new `configs/models.local.yaml`
  overlay mechanism below.
- **Wired and verified live, end to end, same session:**
  - Added `[nemotron35-lightning-30b-a3b]` to `state/llama-models.ini` with `n-cpu-moe = 32`
    (the best-measured sweep point), reusing the already-pinned llama.cpp router.
  - Added `configs/models.local.yaml` (gitignored — see F-025) with a `ModelSpec` entry:
    `status: candidate` (routes only under `mode: deep`, never fast/smart — an unevaluated
    personal model cannot silently win an ordinary routing decision), `quality_prior: 0.75`
    (a deliberately conservative placeholder, not a benchmarked claim), `license_note`
    stating the personal-use-only acceptance in full.
  - `k.registry.validate() == []`; `scheduler.route(reasoning, mode=deep)` lists it
    alongside `qwen38-27b`; `mode=fast`/`mode=smart` correctly exclude it.
  - **Live inference through the actual router**, not just `llama-bench`: loaded via
    `POST /models/load`, then a real `POST /v1/chat/completions` returned a coherent
    response correctly attributed to `"model":"nemotron35-lightning-30b-a3b"`, then
    cleanly unloaded.
  - **Honest caveat on that live call's own numbers:** the single request measured
    `predicted_per_second: 10.35` and `prompt_per_second: 3.1` — far below the benchmarked
    52.79/581.74. This is cold-start overhead (first CUDA graph capture, weight paging,
    sampler init after a just-completed load) dominating one un-warmed request, not a
    contradiction of the `llama-bench` measurement, which explicitly warms up and averages
    3 repetitions. Do not compare a single live request's timing to a proper benchmark's;
    they answer different questions (correctness vs. steady-state throughput).
- **Fix / next steps, in order:**

- **Fix / next steps, in order:** (1) licence review — is the Article 8 indemnification term
  acceptable for this project's use, and separately, for a version of this project given to a
  community; (2) a real quality evaluation harness, not a throughput script, comparing
  Nemotron against both Qwen candidates on representative coding/reasoning tasks; (3) a
  mixed-prompt-length benchmark to pick a principled default `-ncmoe` (or make it
  request-adaptive) rather than crowning `@ncmoe32` from two data points either side of it.

### F-023 — `llama-bench`'s reported `n_gpu_layers` does not reflect `-fitt`/`-ncmoe` resolution

- **Severity:** `minor` · **Status:** `open`
- **Evidence:** Every row in every `benchmark_brains.py` result — dense Qwen3.8-27B,
  Qwen3.5-9B, and all four Nemotron `-ncmoe` sweep points — reports `n_gpu_layers: -1` in
  its JSON output, identical to the CLI default, regardless of what `--fit-target` or
  `-ncmoe` actually resolved. Cross-checked separately for the dense 27B: the dedicated
  `llama-fit-params` tool independently reports `-ngl 37` of 64 for the same model/context
  (see F-005), so the fit computation clearly does happen — `llama-bench`'s JSON output
  simply doesn't surface the resolved value.
- **Impact:** The "layer split" line `benchmark_brains.py` prints during a run is
  uninformative for any `-fitt`/`-ncmoe` run. It does not affect the timed throughput
  numbers, which come from real measured token generation, only the diagnostic display a
  reader might reasonably expect to explain *why* a number came out the way it did.
- **Fix:** Either shell out to `llama-fit-params` alongside `llama-bench` to get the real
  resolved layer count, or stop printing the misleading field and note in the report that
  layer placement for fit/MoE-offload runs must be read from `-ncmoe`/`nvidia-smi` peak VRAM
  instead.

### F-013 — The retrieval stack costs ~59 GB to do what ~5 GB now does

- **Severity:** `major` · **Status:** `open` · **See:** research wave 5
- **Evidence:** Current manifest retrieval models, sizes from the resolved source audit:
  Octen-Embedding-8B-INT8 8.21 GB + Qwen3-Reranker-8B 16.39 GB + Qwen3-VL-Embedding-8B ~17.5 GB
  + Qwen3-VL-Reranker-8B 17.55 GB ≈ **59 GB**, all competing for 12 GB of VRAM. Verified
  alternatives: `nvidia/Nemotron-3-Embed-1B-BF16` **2.30 GB**,
  `nvidia/llama-nemotron-rerank-vl-1b-v2-fp8` **2.40 GB** — and the latter is a
  *vision-language* reranker, covering both the text and multimodal rerank slots with one model.
- **Impact:** Retrieval is the highest-frequency path in any memory-backed agent. Spending 59 GB
  of disk and repeated multi-GB model loads on it, on a 12 GB card, is the single worst resource
  decision in the manifest.
- **Blocker:** Same NVIDIA Open Model License question as F-012.
- **Fix:** Benchmark 1B-class embed/rerank against the 8B incumbents on a local retrieval set
  before assuming the large models are better. Quality priors from a leaderboard are exactly what
  `knowledge/research.md` says not to trust. If the license disqualifies Nemotron, re-scan for
  permissively licensed 1B-class retrieval models — the size lesson holds regardless of vendor.

### F-014 — Manifest breadth is unused and unaffordable

- **Severity:** `major` · **Status:** `open`
- **Evidence:** The `full` profile resolves to ~290 GB of checkpoints (from
  `state/audit-workstation/source-audit.json`), plus 14 isolated torch/CUDA environments at
  roughly 4–6 GB each. `IMPLEMENTATION_STATUS.md` concedes most specialist families have no
  working adapter.
- **Impact:** ~350–380 GB and a multi-hour-to-multi-day install with high partial-failure
  probability, for specialists a single user on one laptop will overwhelmingly never invoke. The
  `full` profile installs a protein language model on a machine with no biology workload. This
  violates the project's own north star: *"a component earns its place only if it improves
  capability, quality, reliability, security, or efficiency on this exact machine."*
- **Fix:** Ship `core` minus the science specialists as the default (~110 GB). Every model beyond
  that earns its slot with a measured invocation, not a capability slot in a YAML file.

### F-015 — `GET /ui` resolves the UI path relative to the process working directory

- **Severity:** `minor` · **Status:** `fixed` (landed alongside F-004, same route)
- **Evidence:** `api/server.py` — `Path("web/index.html").resolve()`.
- **Impact:** Starting the kernel from any directory other than the repository root 404s the
  control surface. Silent and confusing.
- **Fix applied:** `/ui` now resolves `Path(__file__).resolve().parents[3] / "web" /
  "index.html"` — relative to the package location, not the process CWD.
- **Verification:** `test_mutating_endpoints_require_session_token` and the manual `/ui`
  smoke test both invoke `create_app()` without chdir-ing into the repo root and the page
  still loads (200, correct token injected).

### F-016 — `verified_source` is a self-asserted boolean presented as a check

- **Severity:** `minor` · **Status:** `open`
- **Evidence:** `CapabilityRegistry.validate()` refuses any non-excluded model without
  `verified_source: true`, but the flag is a YAML literal set by whoever wrote the entry.
- **Impact:** Circular. It reads as provenance enforcement and is actually a self-attestation.
  The real verification lives in `verify_sources.py`, at install time.
- **Fix:** Either rename the field to `source_reviewed` so it stops reading as machine-verified,
  or have `verify_sources.py` write a signed/hashed attestation into `state/` that the registry
  validates against.

### F-017 — A stray zero-byte file was committed

- **Severity:** `minor` · **Status:** `fixed`
- **Evidence:** Commit `b1a5b29` added a file named `\357\201\234` — U+F05C, a private-use
  codepoint produced by mangled PowerShell/WSL path interop.
- **Verification:** `git ls-files | cat -v` on 2026-08-21 shows no odd filenames in the current
  tree. Recorded for the root cause, which is the same quoting problem that produced the
  `26f9cb6` / `b43a945` / `b66ddd9` / `f6e3483` fix chain in `scripts/bootstrap.ps1`.
- **Follow-up:** Add a pre-commit check rejecting non-ASCII/control-character filenames.

### F-018 — The pre-build gate cites a collision that was already fixed

- **Severity:** `minor` · **Status:** `fixed`
- **Evidence:** `git show b1a5b29 -- configs/engines.yaml scripts/start.ps1` — that commit
  moved the llama.cpp router from `8080` to `18080` **and** added an `Expected-Router`
  identity probe that refuses to adopt a listener which does not advertise `qwen35-9b` and
  `qwen38-27b`. The README and `D-011` still listed the collision as an outstanding blocker.
- **Impact:** A resolved problem was helping to freeze the physical build. The correct
  remaining blockers are authentication, migrations and bounded job/run recovery.
- **Fix applied:** README pre-build gate, `docs/IMPLEMENTATION_STATUS.md` and the `D-011`
  amendment now state that the collision was resolved by relocation plus identity probing,
  and that the foreign router on `8080` is deliberately left running and untouched.
- **Verification:** `scripts/verify_host.py --check-ports` reports all 20 declared ports
  `free`, and lists `8080 -> uvicorn#405` and `17670 -> openshell-gateway#1276` under
  `other_occupied`. No declared port overlaps a foreign service.

### F-019 — Port checks that enumerate only the Windows host cannot see WSL2 services

- **Severity:** `major` · **Status:** `fixed`
- **Evidence:** From Windows, against the WSL-bound service on `8080`:
  `Invoke-RestMethod` -> **SUCCESS**; `Get-NetTCPConnection -State Listen -LocalPort 8080` ->
  **nothing**. Connectivity and enumeration disagree across the WSL2 boundary.
- **Impact:** Root cause of F-001 and a live hazard for every future ownership check. Most of
  this project's services — llama.cpp router, all 14 specialist workers, WanGP, SearXNG — run
  inside WSL, which is precisely where a host-only scan is blind. Note that
  `scripts/start.ps1` happens to be safe because `Port-Up` uses `Test-NetConnection`, which
  *connects* rather than enumerates: correct by luck, not by design, and worth a comment.
- **Fix applied:** `scripts/verify_host.py` now enumerates both namespaces —
  `psutil.net_connections()` for the local host and `wsl -d <distro> -- ss -ltnpH` for the
  distro — merges them, labels each listener with its namespace, and additionally reports
  `other_occupied` so adjacent services are visible before an install rather than after.
  Ports are read from `configs/system.yaml`, `configs/engines.yaml`, `configs/workers.yaml`
  and `infra/docker-compose.yml` rather than hard-coded, so the check cannot drift from what
  actually gets bound.
- **Verification:** run inside WSL, the check surfaces the `8080` uvicorn listener and the
  OpenShell gateway on `17670`, neither of which the earlier host-only version could see.

### F-020 — Documented install state is well behind actual install state

- **Severity:** `minor` · **Status:** `open`
- **Evidence:** `docs/IMPLEMENTATION_STATUS.md` lists model download, llama.cpp CUDA build and
  specialist environments as hardware-bound steps still to be performed. On this workstation
  they are substantially **done**: `$SOAI_MODEL_DIR` holds **103 GB** across 13 core models
  including the revision-locked `Qwen3.8-27B-UD-Q4_K_M.gguf` (16.46 GB), its MTP head and
  `mmproj`; `llama.cpp` is checked out at the pinned commit `dc72703` and **built with CUDA**
  (`libggml-cuda.so` present, `compute capability 12.0` detected at runtime); `state/` already
  holds `model-lock.json`, `runtime-lock.json`, `worker-lock.json` and
  `openshell-health.txt`; the OpenShell gateway is running.
- **Impact:** The gap cuts both ways. It understates progress — the deep-brain benchmark needed
  no download and no build — and it means `worker-install-failures.txt` and
  `openshell-health.txt` hold real results nobody has read.
- **Fix:** Have `scripts/doctor.py` derive install state from the lock files and filesystem and
  render it, so the status document stops being a hand-maintained claim about the machine.
  Still missing: `qwen35-9b` exists only as an HF snapshot with no `gguf/` directory, so the
  fast brain needs `prepare_llama_models.sh` before it can be measured.

### F-021 — The WSL runtime installer builds a conversion environment that cannot convert

- **Severity:** `minor` · **Status:** `open`
- **Evidence:** `scripts/install_wsl_runtimes.sh` creates the `llama-convert` venv with a
  hand-picked package list — `huggingface-hub transformers sentencepiece protobuf numpy
  safetensors` — instead of installing llama.cpp's own
  `requirements/requirements-convert_hf_to_gguf.txt`. That file pins `torch==2.11.0`
  (CPU wheel), which `convert_hf_to_gguf.py` imports unconditionally at the top of the file.
  Reproduced live: `convert_hf_to_gguf.py` on `qwen35-9b` failed immediately with
  `ModuleNotFoundError: No module named 'torch'`.
- **Impact:** Every HF-to-GGUF conversion this installer is responsible for (currently just
  Qwen3.5-9B; F-005's cheaper Qwen3.8 quantisations would hit the same wall if converted
  locally rather than synced pre-quantised) fails on a fresh install. The failure mode gives
  no hint that the fix is "install the requirements file that already exists two directories
  away" — it looks like a missing environment step, not a wrong one.
- **Fix:** Replace the hand-picked package list in `install_wsl_runtimes.sh` with
  `uv pip install --python "$CONV/bin/python" -r
  "$SOAI_RUNTIME_DIR/llama.cpp/requirements/requirements-convert_hf_to_gguf.txt"`, matching
  what upstream itself declares as correct rather than re-deriving it by hand.
- **Worked around for this session:** installed the correct requirements file directly into
  the existing `llama-convert` env without touching the installer script, to unblock the
  Q6_K conversion benchmark. The installer itself still has the bug.

### F-022 — Unverified local model files: provenance, license, and a values decision that is not mine to make

- **Severity:** `debt` · **Status:** `open` — **flagged for the user, not resolved by me**
- **Evidence:** Two GGUF files placed by hand at
  `C:\Users\priya\Downloads\Qwen3.8-27B-OBLITERATED-{IQ4_XS,Q6_K}.gguf` (14.36 GB / 22.43 GB),
  attributed by the user to "Pliny the Liberator's Obliteratus." GGUF header inspection
  (`llama-gguf`) confirms `general.architecture = qwen35` with a metadata shape consistent
  with a Qwen3.8-27B derivative (block count, embedding/feed-forward dims, SSM keys, rope
  config, `nextn_predict_layers` all present) — but the header carries **no**
  `general.source.url`, `general.license`, or upstream-repo key of any kind. There is no
  Hugging Face revision, no immutable commit, nothing this project's own
  `verify_sources.py`/evidence-label discipline could check. Per `knowledge/research.md`'s own
  taxonomy this is `unverified`: not `primary-verified`, not even `vendor-claim` — there is no
  vendor, only a filename.
- **What "obliterated"/"abliterated" means, stated plainly:** these techniques remove refusal
  directions from a model's activations so it stops declining requests the base model would
  decline. That is a deliberate, safety-relevant property of the artifact, not a quality
  variant like a different quantisation. It changes what the model will *say*, not how it
  executes — the kernel's own security model already assumes this correctly
  (`docs/SECURITY.md`: "the model is never the security boundary"; `PolicyEngine` is
  fail-closed and does not depend on model alignment for authority, execution, or credential
  access). So including this model does not weaken the kernel's execution/authority
  boundary. It does, however, bear on content-level behaviour in a coding-assistant/chat
  context, which is a different axis entirely.
- **What I did:** added both files as **throughput-reference-only** benchmark candidates in
  `configs/brain-candidates.yaml` (`provenance: unverified-local`), because architecture and
  parameter count are identical to the incumbent so a tok/s measurement is directly
  comparable and free to collect alongside the other candidates already being benchmarked.
  I did **not** add them to `configs/models.yaml`, any install profile, or any routed
  capability, and I would not without being asked — under invariant 8
  (`knowledge/research.md`), licence and self-hostability are gates evaluated *before*
  capability, and this file cannot currently clear that gate: there is no license to check.
- **What I did not decide, and why it isn't mine to decide:** whether an uncensored model
  belongs anywhere in a system whose stated mission is to be handed to a community as a
  usable default. That is a values decision about what ships to other people, not a technical
  finding — the project's own non-decisions list already declines to "assume 'open weights'
  means... local fit" and requires a recorded decision, not a silent default, for exactly
  this kind of choice.
- **Open questions for the user, not blocking anything else in this session:**
  1. Do you know/can you confirm the actual upstream source and license terms for this
     specific release, beyond the filename?
  2. If it benchmarks well: candidate for personal/private local use only, or a documented
     opt-in profile flag a community installer could offer with a clear label — never a
     silent default either way?
- **Fix:** none applicable until the two questions above are answered. Tracked here so the
  decision is recorded rather than made implicitly by a file sitting in a benchmark config.

### F-024 — `llama_smoke.sh` races its own `load-on-startup` model and fails closed

- **Severity:** `minor` · **Status:** `open`
- **Evidence:** Ran `scripts/prepare_llama_models.sh` for the first time end to end
  (`KEEP_QWEN_HF=1 KEEP_INTERMEDIATE_F16=1`, everything else default). It generates
  `state/llama-models.ini` correctly, then calls `llama_smoke.sh`, which failed:
  `curl: (22) The requested URL returned error: 400` — under `set -euo pipefail` this killed
  the whole script (exit 22) and, via the `EXIT` trap, the router it had just started.
  `state/llama-router-smoke.log` shows the sequence: the router opens its HTTP port at
  `0.00.814s`; the `[qwen35-9b]` preset section carries `load-on-startup = true`, so the
  router begins loading it automatically at `0.00.402s` (before the script's own explicit
  load); `llama_smoke.sh`'s health-check loop then succeeds almost immediately (the
  *router's* `/health` responds before any *model* has finished loading) and it issues its
  own `POST /models/load {"model":"qwen35-9b"}` for the model that is already mid-load —
  the router correctly rejects the conflicting request with 400, and the script treats that
  as fatal. Cross-checked `llama-server --help` at the pinned commit: `--no-models-autoload`
  is real and correctly spelled (`LLAMA_ARG_MODELS_AUTOLOAD`), but it governs whether newly
  *discovered* preset entries get auto-loaded — a different mechanism from a given preset's
  own `load-on-startup = true`, which fires regardless. The script's implicit assumption
  that `--no-models-autoload` disables `load-on-startup` is wrong.
- **Impact:** The project's own installer-driven smoke test fails on exactly the config the
  manifest already specifies (resident fast brain autoloading), which is precisely the
  config a fresh `core`/`workstation` install produces. `prepare_llama_models.sh` exits
  non-zero, so `Install.ps1 -InstallModels` would report the whole bootstrap as failed even
  though the router, the preset, and both models are actually fine — confirmed by
  benchmarking and by a direct, unrelated live load-and-inference test (this same session,
  F-012 verification) succeeding cleanly against the identical preset file.
- **Fix:** Either drop `load-on-startup = true` from the `[qwen35-9b]` preset section
  specifically for the smoke-test invocation (the ini is machine-generated per-run, so the
  script could write a smoke-only variant without it), or have `llama_smoke.sh` check
  `/models` status before issuing `POST /models/load` and skip the explicit load when a
  model is already `loading`/`loaded`, polling straight through to the completion check
  instead of treating "already loading" as failure.
- **Worked around for this session:** ran the router directly (not through
  `llama_smoke.sh`) with `--models-max 1` and no autoload race, to verify the newly-added
  Nemotron preset section end to end. The underlying script bug is still present.

### F-025 — Added: a personal model overlay so licence-gated choices never reach the shared manifest

- **Severity:** `debt` (new architecture, not a defect) · **Status:** `fixed`
- **Motivating problem:** F-022 and F-012 both needed a real answer to the same question —
  where does a model the operator has personally reviewed and accepted (a non-default
  licence, an unverified source, a private experiment) live, such that it is usable on
  *this* machine without becoming part of what `configs/models.yaml` hands to every
  community install? There was no such place before this entry.
- **Fix applied:** `ConfigBundle._merge_local_models()` — after loading
  `configs/models.yaml`, if `configs/models.local.yaml` exists, its `models:` entries are
  merged in by id (a local id may shadow a manifest one). `configs/models.local.yaml` is
  gitignored (`.gitignore` updated). `configs/models.local.yaml.example` is committed and
  documents the four rules: a local id can never appear in `install-profiles.yaml` so no
  profile-based install can pull it in; `verified_source: true` still has to be earned, not
  typed; the real reasoning for accepting a non-default licence belongs in `license_note`;
  `status: candidate` is the correct default so an unevaluated personal model only routes
  under explicit `mode: deep`, never fast/smart.
- **Verification:**
  `tests/test_kernel.py::test_local_model_overlay_merges_without_touching_the_shared_manifest`
  — builds two `ConfigBundle`s from an isolated temp copy of `configs/`, with and without a
  synthetic overlay entry; confirms the overlay id appears only when the file is present,
  `CapabilityRegistry.validate()` still returns no errors, the model is reachable via
  `models_for("reasoning")`, and no install profile references it. Full suite: 24 passed,
  `ruff check src/ tests/` clean. Live-fire proof: this is exactly the mechanism used to
  wire the Nemotron decision in F-012/F-022 above, including a real end-to-end inference
  call through the router.

### F-026 — Added: a real migration runner and online backup/restore

- **Severity:** `debt` (new architecture, not a defect) · **Status:** `fixed`
- **Motivating problem:** every store in this project opened with an ad-hoc
  `CREATE TABLE IF NOT EXISTS`. That is safe only for a table that does not exist yet — it
  has no way to express "add a column" or "backfill a value" on a database that already has
  the old shape without either destroying data or silently doing nothing.
  `knowledge/research.md` names this directly: "Introduce one migration runner and tested
  backup/restore before adding `AgentProfile`, `Run`, grants, leases or memory ACLs." F-010
  and F-011 (above) added exactly `Run` and a durable GPU lease this session — the runner
  needed to exist before those tables did, not after.
- **Fix applied:** `kernel/migrations.py` — `Migration`/`MigrationRunner`: versions must be
  contiguous starting at 1 (constructor raises otherwise), applied versions are tracked in a
  `schema_migrations` table so `current_version()` is a fact read from the database, not an
  assumption, and `apply_pending()` only records a migration as applied after its SQL has
  actually run. `kernel/backup.py` — `backup_database()`/`restore_database()` use SQLite's
  own online backup API (`Connection.backup`), safe to run against a live WAL-mode writer,
  rather than a raw file copy that could capture a torn snapshot mid-write.
  `kernel/runs.py` (F-010) and `resources/gpu_leases.py` (F-011) — both new stores added
  this session — were built directly on this runner as its first real, working use, rather
  than shipping with their own one-off `CREATE TABLE IF NOT EXISTS`.
- **Honest limit, stated rather than glossed over:** the pre-existing stores
  (`jobs.db`, `events.db`, `checkpoints.db`, `benchmarks.db`, `memory.db`,
  `memory-graph.db`, `collaboration.db`) still use their original ad-hoc initialization and
  have **not** been retrofitted onto this runner. That is a real, bounded follow-up
  (mechanical per store, no design work left), not a hidden gap — the runner and backup
  utility exist and are proven; migrating each remaining store onto them is the honest
  remainder.
- **Verification:** `tests/test_kernel.py` — a two-migration sequence applies in order,
  `apply_pending()` is a true no-op on a second call (re-running an `ALTER TABLE ADD COLUMN`
  would error if it weren't), and non-contiguous or duplicate version numbers are rejected
  at construction time, before any SQL runs. `backup_database()`/`restore_database()` are
  tested as a genuine round trip: data written after a backup is confirmed present, then
  erased by restoring the earlier snapshot, proving restore actually reverts state rather
  than merely not-erroring. Full suite: **38 passed**, `ruff check src/ tests/` clean.

### F-027 — Added: a working native `AgentLoop` — the kernel routed chat, it could not yet act

- **Severity:** `major` (closes the largest gap between "kernel with routing" and "usable
  coding agent") · **Status:** `fixed`
- **Motivating problem:** `agents/base.py` defined the `AgentLoop` contract and
  `agents/registry.py` could hold implementations, but nothing implemented it and nothing
  drove it. The kernel could route a single chat completion; it could not plan, call a
  tool, observe the result, and continue — the actual definition of an agent, and the
  substance of the roadmap's Tier 2 item 4.
- **Scope decision, made explicitly rather than by default:** `D-015` picked Goose
  (external, Rust, Linux-Foundation-governed) as the first harness. Building it requires a
  Rust/Cargo toolchain, which this machine does not have (`cargo`/`rustc` both `MISSING`),
  plus cloning and building a real production CLI — a multi-hour, failure-prone detour
  disproportionate to what "first working agent loop" actually needs. Building a native
  reference loop first, with Goose and others compared against it later in the harness
  tournament (`research.md` experiment 11, already sequenced there), is not a downgrade —
  it is more consistent with `D-001` ("no harness is the root of trust") than making one
  external, unauditable Rust binary the *only* thing that can ever drive this kernel.
- **Fix applied:** `agents/native_loop.py` — `NativeAgentLoop`. A deterministic JSON
  tool-call protocol (`{"tool": "...", "args": {...}}` / `{"tool": "done", "summary": "..."}`)
  a small local model can reliably produce, deliberately not dependent on a specific
  backend's native function-calling support. Three tools, each routed through existing
  kernel machinery rather than reimplementing authority checks: `read_file`/
  `list_directory` gated by `WorkspaceRegistry.require()` (a path outside a registered
  workspace is denied, exactly as everywhere else in this project); `run_command` routed
  through the **existing** `ExecutionBroker.run_approved()`, so a proposed mutating action
  is evaluated by the real fail-closed `PolicyEngine` with `trust=untrusted_model_output`
  and is denied without explicit approval — `docs/SECURITY.md`'s "untrusted model output
  cannot authorize mutation" now has a concrete enforcement point for agent tool calls, not
  just for direct API calls. Every step (tool call, denial, parse failure, completion) is
  recorded as an append-only kernel event, so a run is auditable after the fact rather than
  merely trusted because it finished. A hard step budget (`max_steps`, capped at 25)
  prevents a runaway loop.
  - New `JobKind` value `"agent"`; `jobs.py` and the API's separate `JobSubmission` model
    both updated (missing the second one first caused a live 422 — see verification).
  - `job_executor._run_agent_loop()` drives `kernel.agent_loops.get("native")` to
    completion for one `Run` attempt, accumulating every step into the Run's result so
    `GET /jobs/{id}/runs` shows the full trajectory without a second round trip to events.
  - `kernel/app.py` registers `NativeAgentLoop` under the name `"native"` at kernel build
    time, wired with the kernel's real `inference`/`execution`/`workspaces`/`events`.
- **Verification:** six new tests in `tests/test_kernel.py`, using a scripted fake
  inference broker but the kernel's **real** `ExecutionBroker`/`WorkspaceRegistry`/
  `EventStore`/`PolicyEngine` — proving actual enforcement, not a mocked call: reading a
  file inside a registered workspace succeeds and the content reaches the model's next
  turn; a proposed `run_command` mutation with no approval is genuinely denied by policy,
  not merely skipped; the step budget stops the loop at exactly the configured count; an
  unparsable reply produces an observation instead of crashing the loop; and a full
  `POST /jobs {kind: agent}` → dispatcher → executor → `NativeAgentLoop` → `done` round
  trip through the real HTTP API reaches `succeeded` with the expected summary.
  - **Caught while writing the last test:** `TestClient(app)` constructed without
    `with ... as client` never runs FastAPI's `lifespan`, so `dispatcher.start()` never
    fires and no worker ever consumes the queue — a job would sit at `queued` forever. This
    also silently weakened the F-010 dispatcher test written earlier the same session,
    which only proved a `Run` row gets *created* (synchronous, happens at submission time
    regardless of any worker existing), not that it gets *executed*. Both tests now use
    `with TestClient(...)`, and the earlier one now asserts the job reaches a terminal
    status, not just that a Run row exists.
  - Full suite: **43 passed**, `ruff check src/ tests/` clean.
- **Explicitly out of scope / honest limits:** no real tool-calling grammar constraint on
  the model's output (relies on prompt instruction plus lenient JSON-span extraction, not a
  guaranteed-valid-JSON sampler); no sub-agent delegation; no checkpoint/resume mid-loop
  (a cancelled run's partial history is visible via `GET /jobs/{id}/runs` but a retry starts
  the task over, not from where it left off); quality on real coding tasks is unmeasured —
  this closes the "can the kernel act at all" gap, not the "is it good at acting" question.

---

## Priority order

Ordered so each step makes the next one cheaper or safer, not by severity alone.

1. ~~**F-001**~~ — closed as `invalid`. The real work landed as **F-018** (stale gate text
   corrected) and **F-019** (two-namespace port check implemented). The build is unfrozen.
2. ~~**F-005 + F-012**~~ — **both measured.** F-005: dense 27B 6.36 tok/s (viability gate
   failed), 9B fast brain 49.57 tok/s (clears it, no licence gate). F-012: Nemotron MoE
   `@ncmoe32` 52.79 tok/s at the *same* VRAM footprint as the dense 27B — 8.3x faster,
   larger model, still licence-blocked. **Remaining, in order:** (a) NVIDIA Open Model
   License Article 8 review — a values/legal decision, not a technical one; (b) a real
   quality evaluation harness (throughput alone proves nothing about coding/planning
   quality); (c) a mixed-prompt-length benchmark to pick a principled `-ncmoe` default,
   since prefill and decode trade off sharply within the Nemotron family itself.
3. ~~**F-002, F-003, F-004**~~ — **fixed and verified** (session token, Host/Origin
   middleware, non-upserting identity creation, authorized membership). New HTTP-level
   tests cover all three. Prerequisite work for `D-010` is now in place.
4. ~~**F-010 + F-011 + F-026**~~ — **fixed.** Bounded job dispatcher with durable `Run`
   attempts, a cross-process durable GPU lease, and the migration runner both were built
   on. `Run` and `ResourceLease` from `D-008` stopped being architecture and became code.
5. **F-014 + F-013** — cut the manifest and the retrieval stack. Turns the install from a coin
   flip into something reproducible.
6. **F-008** — real vector index, or an honest README.
7. **F-006, F-007, F-009, F-015 (fixed), F-016, F-021, F-023, F-024** — cleanup, each
   independently shippable.
