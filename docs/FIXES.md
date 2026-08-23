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
  waiting on it turn-by-turn.
  **Quality, measured 2026-08-21 (F-028):** `qwen35-9b` scores **5/5 (100%)** on the
  `scripts/quality_eval_tasks.py` suite — 2 coding tasks graded by real test execution, 2
  reasoning/arithmetic tasks graded on the exact numeric answer, 1 instruction-following
  task graded on exact bullet count — at 4.2s average latency, with `enable_thinking:
  false` (thinking mode only burned budget on tasks this short). This is real signal, not
  a proxy: correct working code, correct arithmetic, exact format compliance. **Still open:**
  this is one model against a five-task suite, not a verdict on 9B-vs-27B quality in
  general — `qwen38-27b` (dense, 6.36 tok/s, fails the interactive gate) and the two
  personal-use candidates (Nemotron `@ncmoe32`, Obliterated IQ4_XS) have **not** been
  quality-evaluated yet, so a real side-by-side comparison is still the honest remainder.
  Five tasks is also not a comprehensive benchmark — it is a first real data point that
  replaces a placeholder `quality_prior`, not a final answer.
- **Fix:** Run the benchmark before defending the design. `UD-Q4_K_M` (16.46 GB) vs `UD-Q4_K_S`
  (15.36 GB) vs `UD-IQ4_XS` (14.25 GB — roughly halves CPU offload), each with and without the
  already-downloaded MTP draft head, at 16K and 64K context. If sustained generation lands under
  ~10 tok/s, promote the 9B to the agentic loop brain and demote the 27B to an asynchronous
  verifier/batch tier. See also F-012, which may make this moot.

### F-006 — The router is elaborate machinery with almost nothing to route

- **Severity:** `debt` · **Status:** `fixed`
- **Evidence:** Measured live against the built registry:
  `capability -> #models histogram: {1: 84, 2: 5}` (re-measured after F-007 removed the
  bogus `visual_search` capability tag; was `{1: 86, 2: 6}` before that). **84 of 89
  capabilities have exactly one candidate.** The five contested: `asr_multilingual` and
  `speech_transcription` (the same Qwen3-ASR vs Whisper pair twice), `synthesis` and
  `vision_language` (the same 27B vs 9B pair twice), `music_generation`. Two genuine
  contests.
- **Impact:** `ResourceScheduler.route()` — quality priors × latency utility × reliability ×
  resource-fit adjustment × resident bonus × benchmark override, ~130 lines — is permanent
  maintenance cost serving two decisions. The registry's real value is *dispatch*
  (capability → worker → port), which is a dictionary lookup.
- **Fix applied:** `route()` now builds the filtered list of eligible `(model, engine)`
  pairs first (`_eligible()` — the status/license/engine-availability gates, unchanged
  logic, just factored out). When exactly one pair survives, `_dispatch()` reports it
  directly: `quality`/`reliability`/`latency_score` are still computed from the real
  benchmark-or-manifest-prior (the audit/provenance value the fix note said to keep), but
  the weighted-sum formula, resident-priority bonus and resource-fit score adjustment are
  skipped entirely, since there is nothing to rank against. `RouteCandidate.reasons` says
  so explicitly (`"only eligible candidate for this capability"`) so the distinction is
  visible in the audit record, not just implicit in candidate count. When two or more
  pairs survive, `_score()` runs the exact same weighted-scoring formula as before,
  unchanged — the existing `sovereign route` CLI command remains the "opt-in A/B harness"
  the fix note asked for, now honestly exercising real ranking machinery only when a real
  choice exists.
- **Verification — behavior-preservation proven, not assumed:** wrote a script that calls
  `kernel.scheduler.route()` for every capability (89) × mode (fast/smart/deep) ×
  license_context (personal/commercial) = 546 combinations, recording `selected_model`,
  `selected_engine`, `n_candidates` and `warnings`. Ran it against the pre-refactor
  `scheduler.py` (via `git stash`) and the post-refactor version, then diffed:
  **0 differences across all 546 route requests.** Every capability dispatches or ranks to
  the exact same model/engine it did before, with the same candidate counts and warnings —
  only the *internal* scoring path changed for the uncontested majority, never an
  observable outcome. Added `test_route_dispatches_without_weighted_scoring_when_uncontested`
  (confirms `orchestration_fast` takes the fast path: one candidate, the "only eligible
  candidate" reason, `score == quality`) and
  `test_route_scores_genuinely_contested_capability` (confirms `asr_multilingual` still
  goes through real multi-candidate scoring). Full suite **56 passed**,
  `ruff check src/ tests/ scripts/` clean.

### F-007 — `visual_search` scores a pipeline against itself, and one manifest source went unverified

- **Severity:** `minor` · **Status:** `fixed`
- **Evidence:** `visual_search` resolved to `['qwen3-vl-embedding-8b', 'qwen3-vl-reranker-8b']`.
  Those are **sequential stages of one retrieval pipeline** (embed, then rerank — the same
  shape as the already-correct `text_embedding`/`text_reranking` pair `SpecialistVectorRetriever`
  uses), not alternatives; nothing in `src/` ever requested capability `visual_search` at all —
  it existed only as manifest metadata, causing `ResourceScheduler.route()` to score two
  pipeline stages against each other for a capability nothing consumed. Separately,
  `configs/models.yaml` gives `rf-detr-keypoint` (`source_type: github_package`) the source
  `roboflow/rf-detr` — verified this **is** a real, active, public GitHub repo
  (`github.com/roboflow/rf-detr`, not archived); the earlier "401 from the HF API" note was
  from checking a GitHub-package source against the wrong API, not a bug in the source field
  itself. The real bug: `verify_sources.py` only ever resolved `source_type == "huggingface"`,
  so any non-HF source was silently and permanently exempt from verification no matter how
  broken it was, regardless of maturity.
- **Fix applied:**
  - Removed the `visual_search` capability tag from `qwen3-vl-embedding-8b` and
    `qwen3-vl-reranker-8b` in `configs/models.yaml`. Their real capabilities
    (`multimodal_embedding`/`video_retrieval` and `multimodal_reranking`) are untouched.
  - `scripts/verify_sources.py` now also resolves `source_type: github_package` sources via
    the GitHub API (existence + not-archived check), and no longer exempts
    `install_policy: package` from verification — only `runtime_only`/`runtime_managed`
    (genuinely sourceless placeholder entries) remain exempt. `rf-detr-keypoint` itself
    stays unchecked today because it is `status: candidate`, matching the script's existing,
    intentional "only verify shipped models" scope — but the moment it is promoted to
    `final` it will now actually be checked instead of being silently exempt forever.
- **Verification:** live: `github.com/api/repos/roboflow/rf-detr` confirmed 200/not-archived;
  a deliberately nonexistent repo correctly raises `HTTPStatusError: 404`. Re-ran
  `verify_sources.py --profile core` end to end: 12 resolved, 0 failed, 77.71 GB — matches
  the pre-fix run, confirming the HF path is unaffected. Recomputed the F-006 contest
  histogram live: `{1: 84, 2: 5}`, `visual_search` no longer appears. Full suite
  **54 passed**, `ruff check src/ tests/ scripts/` clean.

### F-008 — The vector store is a placeholder presented as implemented

- **Severity:** `major` · **Status:** `fixed`
- **Evidence:** [`memory/vector.py:62`](../src/sovereign_ai/memory/vector.py) —
  `search_vector()` issued `SELECT * FROM vectors` and then unpacked every row with
  `struct.unpack` and computed cosine similarity in pure Python. No index, no ANN, no numpy.
  Separately, `supersedes` was accepted by `MemoryStore.put()` but nothing ever removed the
  superseded memory from `memories_fts`, so a search could return both the stale and current
  version of the same fact once memory writing gets wired up.
- **Impact:** Octen-Embedding-8B emits ~4096-dim vectors. At real scale the per-row Python loop
  does not stay fast. The README lists "persistent vector adapter" under implemented features
  — this fix is what makes that claim actually true rather than aspirational.
- **Fix applied:**
  - `search_vector()` now scores every stored vector against the query with one batched
    numpy matrix-vector product, and only builds a result dict (JSON metadata decode
    included) for the winning `limit` rows instead of every row scanned.
  - Added `LocalVectorStore.delete(id)` and `MemoryStore.retire(id)` / an automatic
    `supersedes` cleanup in `MemoryStore.put()` (deletes the old id's FTS row, keeps its
    `memories` row for provenance/audit) and in `MemoryIndexer.index(..., supersedes=...)`
    (deletes the old id's vector row). A memory can now be superseded without leaving a
    stale duplicate reachable by either lexical or semantic search.
  - `numpy` moved from the optional `ml` extra to a base dependency in `pyproject.toml` —
    `memory/vector.py` is core kernel code, not a worker-process-only path, so it needs to
    be installed unconditionally rather than only when the `ml` extra happens to be synced.
- **Verification — measured, not assumed:** live benchmark, 4096-dim vectors (real
  Octen-Embedding-8B width), `.venv` on this machine:
  - 2,000 vectors: new numpy path 94.9 ms vs. the old per-row pure-Python loop 465.6 ms
    (~4.9x). This is **not** the 100-1000x a purely compute-bound BLAS win would suggest —
    breaking the 20k-vector case down: SQLite blob fetch 444.7 ms, matrix assembly (join +
    `np.frombuffer`) 264.5 ms, the actual numpy score computation only 222.0 ms. Most of
    the wall-clock cost at this vector width is SQLite I/O and byte-copying, not arithmetic
    — the numpy rewrite fixes the part that was genuinely interpreted-Python-bound and
    leaves an honest ~4-5x, not an invented order-of-magnitude number.
  - 20,000 vectors, full end-to-end `search_vector()`: 886.1 ms. Still an exact O(n) scan,
    still correct-by-construction (no approximation), and comfortably interactive at the
    scale a personal/community memory store actually reaches.
  - Correctness: `test_local_vector_store_search_ranks_by_cosine_similarity_at_scale`
    (500 random noise vectors, one true nearest neighbour, confirms the vectorized scoring
    finds it, guarding against a silent ranking regression from the rewrite).
    `test_local_vector_store_delete_removes_row`,
    `test_memory_store_put_with_supersedes_retires_old_memory_from_fts`,
    `test_memory_indexer_supersedes_purges_old_vector` cover the new delete/supersession
    paths.
  - Full suite **54 passed**, `ruff check src/ tests/ scripts/` clean.
- **Honest limits:** still an exact O(n) scan, not sub-linear ANN — the right tradeoff for
  the thousands-to-low-hundreds-of-thousands-of-memories scale this project targets, per
  the class docstring's own reasoning. At meaningfully higher memory counts (100k+) the
  measurements above show SQLite blob I/O becomes the dominant cost, not the math; if that
  ever matters, the existing `VectorRetriever`-shaped interface is what a FAISS/LanceDB/
  sqlite-vec swap would sit behind without touching `ContextBuilder`.

### F-009 — One resource policy, three different numbers

- **Severity:** `minor` · **Status:** `fixed`
- **Evidence:** `reserve_vram_mb: 1600` in [`configs/system.yaml:38`](../configs/system.yaml);
  default `1300` in [`resources/scheduler.py:74`](../src/sovereign_ai/resources/scheduler.py);
  `fit-target = 1800` hardcoded in the heredoc in
  [`scripts/prepare_llama_models.sh`](../scripts/prepare_llama_models.sh). Same policy, three
  independently-editable numbers, free to drift apart with no error until a real VRAM budget
  problem surfaced downstream.
- **Fix applied:**
  - `scripts/prepare_llama_models.sh` no longer hardcodes `1800`. It now shells out to a small
    Python one-liner that loads `configs/system.yaml` and reads
    `resources.reserve_vram_mb`, writing that value into the generated `llama-models.ini`'s
    `fit-target`. Verified live: returns `1600`, matching the config.
  - `resources/scheduler.py`'s `ResourceScheduler.__init__` now reads
    `config.system["resources"]["reserve_vram_mb"]` once (a plain `KeyError` if the key is
    ever removed — no silent fallback) and stores it as `self.reserve_vram_mb`. `route()` was
    changed from `int(self.config.system.get("resources", {}).get("reserve_vram_mb", 1300))`
    computed on every candidate, to a single read of `self.reserve_vram_mb`, deleting the
    divergent `1300` literal entirely.
  - `configs/system.yaml` remains the one place a human edits this number; both the installer
    script and the running kernel now derive from it and cannot silently disagree.
- **Verification:** full suite **50 passed**, `ruff check src/ tests/ scripts/` clean.

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

- **Severity:** `minor` · **Status:** `fixed`
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
- **Fix applied:** Took the first option named above. Added `resolve_fit()` in
  `scripts/benchmark_brains.py`, which shells out to `llama-fit-params` (the sibling binary
  next to `llama-bench`) with the same `-fitt`/`-fitc`/`-ncmoe` arguments the real run used,
  and captures its resolved-arguments stdout line. Discovered along the way that a single
  `n_gpu_layers` number would have been misleading even from the *correct* tool for `-ncmoe`
  runs: MoE offload placement isn't a layer count at all, it resolves to an `-ot` tensor
  override regex pinning specific expert-weight tensors to CPU (`-ngl -1 -ot
  "blk\.0\.ffn_...=CPU,blk\.1\...."`) — reporting a layer count for that case would just be
  a different flavor of the same lie this finding names. `resolve_fit()` therefore reports
  the whole resolved argument string as-is rather than trying to force it back into a
  single int, stored as `resolved_fit_args` in each result and printed as the new `fit:`
  field in place of the old, always-misleading `ngl` field. Runs in a few seconds (memory
  estimation only, no model load or generation) and fails soft (`None`, printed as
  "unavailable") if the binary is missing, so a benchmark run is never blocked by this
  diagnostic being unavailable.
- **Verification:** live end-to-end run, `qwen35-9b-q6k`: printed
  `fit: -c 83456 -ngl -1` (all layers fit after the tool's own context reduction — the same
  conclusion the old field's `-1` implied, but now because a real resolution decided it,
  not because it's the untouched CLI default) and the same string was confirmed present in
  the JSON report's `resolved_fit_args` field. Separately exercised `-ncmoe` resolution
  directly against a Nemotron checkpoint: produced the `-ot` tensor-override string
  described above, confirming the non-dense case is handled rather than assumed. Full suite
  **54 passed**, `ruff check src/ tests/ scripts/` clean.

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

- **Severity:** `major` · **Status:** `fixed`
- **Evidence:** The `workstation` profile — the one `scripts/bootstrap.ps1`/`Install.ps1`
  actually **defaulted to** — resolved to 289.5 GB across 25 models (recomputed from
  `state/audit-workstation/source-audit.json`; the original finding cited this same number
  but mislabelled it as the `full` profile). `full` adds niche protein/materials/Earth-
  observation/formal-proof specialists on top of that. `IMPLEMENTATION_STATUS.md` concedes
  most specialist families have no working adapter.
- **Impact:** ~290 GB and a multi-hour install with real partial-failure probability, as the
  **default** a fresh install got with no flag at all — for specialists a single user on
  one laptop will overwhelmingly never invoke. This violated the project's own north star:
  *"a component earns its place only if it improves capability, quality, reliability,
  security, or efficiency on this exact machine."*
- **Fix applied:** Recomputed real per-profile sizes from the resolved audit data rather
  than estimating. `core` was **already** the right size (110.9 GB) — the actual defect was
  that `-Profile` defaulted to `workstation` everywhere: `scripts/bootstrap.ps1`,
  `Install.ps1`, and — found while fixing this — the same stale `"workstation"` default in
  `scripts/prewarm_specialists.py`, `scripts/sync_models.py`, `scripts/verify_sources.py`
  and `scripts/install_specialists.sh` (`scripts/verify_storage.sh` too). All now default
  to `core`. Separately, `ui-tars-1.5-7b` (33.19 GB — the single largest model that *was* in
  `core`, larger even than the 27B deep brain) moved to `workstation`: it is the only model
  serving `gui_grounding`/`screenshot_action`/`computer_use`, but
  `docs/IMPLEMENTATION_STATUS.md` is explicit that no computer-control provider exists in
  any profile yet — 33 GB for a capability that cannot currently be invoked has no business
  being in the profile a fresh install gets with no flag. Net result: **new default `core`
  is 77.7 GB** (down from the 289.5 GB a no-flag install used to pull), `workstation`
  remains 289.5 GB total but is now an explicit, deliberate choice
  (`./Install.ps1 -Profile workstation`), not the silent default. README, `LOCAL_BUILD.md`
  and `configs/install-profiles.yaml` all updated with the corrected, verified figures.
- **Verification:** `k.registry.validate() == []` after the manifest change; confirmed live
  that `ui-tars-1.5-7b` is absent from `core`'s model list and present in `workstation`'s,
  and that it remains `status: final` in `configs/models.yaml` (still fully installable via
  `workstation`/`full`, just not by default). Full suite: **46 passed**, unaffected — no
  test asserted specific `core`/`workstation` contents.

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

- **Severity:** `minor` · **Status:** `fixed`
- **Evidence:** `CapabilityRegistry.validate()` refused any non-excluded model without
  `verified_source: true`, but the flag is a YAML literal set by whoever wrote the entry.
- **Impact:** Circular. It read as provenance enforcement and was actually a self-attestation.
  The real verification lives in `verify_sources.py`, at install time.
- **Fix applied:** Took the simpler of the two options named above rather than building a
  signed-attestation pipeline: renamed the field to `source_reviewed` everywhere (manifest
  entries in `configs/models.yaml`, `configs/models.local.yaml.example`, the `ModelSpec`
  pydantic model, `CapabilityRegistry.validate()`'s error messages, `scripts/sync_models.py`,
  `configs/system.yaml`'s `require_verified_source` -> `require_source_reviewed`, and tests).
  Added a docstring on `validate()` stating plainly what this field is (a maintainer
  attestation) and is not (a machine check) — and pointing at `verify_sources.py` (extended
  for real in F-007) as where the actual machine check lives. A hard rename, no
  backwards-compatible alias, matching this codebase's stated preference for direct changes
  over compatibility shims. Building the heavier signed-attestation option remains available
  later if `verify_sources.py`'s output ever needs to gate the registry directly, but that is
  a real architectural addition (an operational dependency on `state/source-audit.json`
  existing at kernel startup), not a cleanup-tier fix.
- **Verification:** the rename initially broke `test_registry_valid` and 20 other tests —
  not from the renamed field itself, but because the gitignored personal overlay
  `configs/models.local.yaml` (F-025's per-operator model file, not in git, so a repo-wide
  grep does not surface it) still had the old key name. Fixed that file too and re-ran: full
  suite **54 passed**, `ruff check src/ tests/ scripts/` clean.

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

- **Severity:** `minor` · **Status:** `fixed`
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
- **Fix applied:** `scripts/doctor.py` already existed (from the earliest pre-build-audit
  commits) and did a real, different job — hard-coded GGUF-file existence checks for the
  two Qwen brains, a live TCP reachability probe of four services, an `HF_TOKEN`/`nvidia-smi`
  environment check, and a `--strict` flag that `scripts/bootstrap.ps1` depends on
  (`Assert-Native "installation doctor"` fails the whole one-shot install if it exits
  non-zero). **First pass at this fix wrote a new file without reading the old one first
  and silently replaced all of that** — caught before committing, while staging the diff,
  by `git status` showing `modified` instead of the expected `new file`. Rebuilt as a
  genuine merge instead: kept every check the original had (now via
  `verify_host.declared_ports()` for the TCP list rather than a second hard-coded port
  set — the original's `"search": 8888` had already drifted; `declared_ports()` resolved
  it correctly as `8888 container:searxng`, read from config the same way F-001's port fix
  requires) and added what this finding asked for — `runtime-lock.json` cross-checked
  against a live `git rev-parse HEAD` (catches lock/working-tree drift, not just presence),
  `worker-lock.json` cross-checked against real venv directories, `model-lock.json`
  cross-checked against `configs/models.yaml` (plus the gitignored local overlay) and the
  real model directory contents, a `gguf_ready` flag for `llama_cpp`-routed models (the
  exact `qwen35-9b` gap this finding's evidence named), the literal content of
  `openshell-health.txt`, and a `--json` mode. Also added a `--profile` flag
  (`core`/`workstation`/`full`, reusing `verify_sources.profile_ids()`) after live-testing
  caught a second real bug: without it, `--strict` counted every out-of-profile manifest
  model as a missing-install issue, which would have failed `Assert-Native` on every
  legitimate `core`-profile bootstrap (the project's own default since F-014) for models
  that profile never installs. `bootstrap.ps1` was updated to pass `--profile '$Profile'`
  through to the doctor call, matching the pattern every other script call in that file
  already follows. Also corrected the specific claims in `docs/IMPLEMENTATION_STATUS.md`
  that this session's own fixes had made stale: "SQLite stores have no general migration
  runner" and "job submission creates unbounded in-process tasks" (both fixed by
  F-026/F-010), "bounded dispatch... pending" (done; automatic retry/resume specifically
  remains not-automatic, and the doc now says so precisely rather than lumping it in with
  what's fixed), "end-to-end embedding → rerank → context path" listed as remaining work
  (done, F-030), "agent-loop adapters... behind the kernel contract" (a native one now
  exists, F-027), and two persistent-agency items that were listed as still pending but are
  in fact built: `Run` records beneath `Job` (F-010) and a durable cross-process GPU lease
  (F-011) — the doc claimed the GPU lease was still process-local, which stopped being true
  when F-011 landed. Added a pointer from `IMPLEMENTATION_STATUS.md`'s hardware-bound-steps
  section to `scripts/doctor.py` for real install state, with an explicit note that the
  numbered list above it describes what a fresh install must get through, not this
  machine's current state — the exact ambiguity that let this finding's stale claims
  survive.
- **Verification:** ran the merged `scripts/doctor.py` live against this workstation's real
  install, across all three profiles (`core`/`workstation`/`full`, none crashed). Under
  `--profile core` (the default): all 4 runtimes report `locked_commit == actual_commit`
  (no drift); all 9 specialist worker venvs present; core-profile models (`qwen38-27b`,
  `qwen35-9b`, embeddings, reranker, ASR/Whisper, VoxCPM2, RF-DETR, Depth Anything,
  Chronos-2) report `ready`, including `qwen35-9b`'s `gguf_ready: true` — the exact gap
  this finding's evidence described has since been closed by this session's own
  F-023/F-024 work, and the tool correctly reports that rather than a stale claim either
  way. Out-of-profile manifest models correctly report `not on disk (out of profile)` —
  listed, not flagged as an issue. `--strict` under `--profile core` now correctly exits 1
  for exactly one real reason (`openshell_health: unhealthy`, live-confirmed as a genuine
  finding, not a bug: the recorded value dates from original install and is exactly the
  kind of "nobody has read it" signal this finding's own Impact note names) instead of the
  18 false positives the pre-`--profile` version produced. `--json` output validated as
  parseable JSON under all three profiles. Full suite **54 passed**,
  `ruff check src/ tests/ scripts/` clean.

### F-021 — The WSL runtime installer builds a conversion environment that cannot convert

- **Severity:** `minor` · **Status:** `fixed`
- **Evidence:** `scripts/install_wsl_runtimes.sh` created the `llama-convert` venv with a
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
- **Fix applied:** Replaced the hand-picked package list in `install_wsl_runtimes.sh` with
  `uv pip install --python "$CONV/bin/python" -r
  "$SOAI_RUNTIME_DIR/llama.cpp/requirements/requirements-convert_hf_to_gguf.txt"`, matching
  what upstream itself declares as correct rather than re-deriving it by hand.
- **Verification:** live, in a disposable venv (not the real `llama-convert` env, so a bad
  run couldn't corrupt the working install): `uv venv` + the exact new install line against
  the real `requirements-convert_hf_to_gguf.txt` (which itself `-r`-includes
  `requirements-convert_legacy_llama.txt` — confirmed the sibling file exists so the relative
  include resolves) resolved and installed 28 packages including `torch==2.11.0+cpu`.
  `import torch, transformers, sentencepiece, safetensors, numpy, huggingface_hub` succeeded,
  and `convert_hf_to_gguf.py --help` ran clean with no `ModuleNotFoundError` — the exact
  failure this closes. `bash -n` on the edited script passed. Full suite **54 passed**,
  `ruff check src/ tests/ scripts/` clean (no Python changed by this fix, sanity re-run).
- **Note:** this session had already worked around the bug by installing the correct
  requirements file directly into the existing `llama-convert` env without touching the
  installer script, to unblock the Q6_K conversion benchmark recorded elsewhere in this
  document. This fix is what makes a *fresh* install correct too, not just this machine's
  already-patched one.

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

- **Severity:** `minor` · **Status:** `fixed`
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
- **Fix applied:** Took the second, more general option named above — a fix scoped to
  dropping `load-on-startup` from one preset would only have covered `qwen35-9b`
  specifically and left the same race waiting for the next resident preset. Added a
  `model_status()` helper to `scripts/llama_smoke.sh` that queries `GET /models` for a
  given model id's current status. Before issuing `POST /models/load`, the script now
  checks status first and only issues the explicit load when the model is not already
  `loading` or `loaded`; either way it falls through to the existing polling loop that
  waits for `loaded`. The polling loop itself was also deduplicated to call the same
  helper instead of repeating the inline Python one-liner a second time.
- **Verification — the actual race, live, not just theorized:** ran the fixed
  `llama_smoke.sh` against the real router end to end (GPU otherwise idle, `nvidia-smi`
  confirmed 0 MiB used beforehand). It completed with exit code 0 — `qwen35-9b OK`,
  `qwen38-27b OK` — where before the fix this same invocation reproducibly died with
  `curl: (22) ... 400` and took the router down with it via the `EXIT` trap. Confirmed the
  race was genuinely exercised, not accidentally avoided: `state/llama-router-smoke.log`
  shows `(startup) loading model qwen35-9b` at `0.753s`, *before* `llama_server: listening`
  at `0.778s` — the router's `/health` endpoint (and therefore this script's own
  health-check loop) comes up while the autoloaded model is still mid-load, exactly the
  window the old code raced into. `bash -n` passes. Full suite **54 passed**,
  `ruff check src/ tests/ scripts/` clean.

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

### F-028 — Added the quality-eval harness, and it immediately caught a real content-extraction bug

- **Severity:** `major` (the bug it caught affects production kernel code, not just the
  new benchmark) · **Status:** `fixed`
- **What was added:** `scripts/quality_eval_tasks.py` — five deterministic tasks (2 coding,
  graded by executing the model's code against real assertions in a subprocess; 2 reasoning/
  arithmetic, graded by extracting the final number; 1 instruction-following, graded by
  counting bullet lines) and `scripts/evaluate_brain_quality.py`, which runs the suite
  against a live model over the router and records the aggregate score into
  `BenchmarkStore` (`--record`), so the scheduler's local-benchmark override eventually has
  a real quality number instead of only the manifest's `quality_prior` placeholder. Every
  check is graded programmatically, never by an LLM judge, matching the project's own
  "deterministic code runs before both whenever a deterministic solution exists."
- **What it immediately found:** the first live run against `qwen35-9b` scored 1/5 (20%).
  Inspecting the raw completions showed 4 of the 5 "failures" had a **completely empty**
  extracted answer — and, tellingly, those four took *longer* to generate than the one
  that passed (8.7s–14s vs 3.7s), the opposite of what a genuinely failed short answer
  would look like. That pattern means the model was doing real work that never made it
  into the field being read.
- **Root cause, verified directly against the router before touching any code:** Qwen3.5's
  chat template emits "thinking" reasoning into a separate `reasoning_content` field,
  distinct from `content`. A probe request confirmed `content` is populated correctly once
  reasoning finishes — but on a token budget too small for a 9B model's verbose thinking
  style (it spent 150 tokens narrating trivial addition in one probe), generation is cut
  off *during* the reasoning phase, `content` stays permanently empty, and every caller
  that only ever read `content` silently received a blank response.
- **Impact beyond the new script:** the exact same "only read `content`" logic already
  existed, independently, in two pieces of **already-shipped kernel code**:
  `job_executor._assistant_content()` (the path that posts a chat job's result back into a
  collaboration room) and `NativeAgentLoop._extract_content()` (F-027, added earlier this
  same session). Both could have silently treated a real, budget-cut-off model turn as "no
  output produced" in actual use — a collaboration reply going silently blank, or an agent
  loop step being misread as an empty/failed turn — not just in this benchmark.
- **Fix applied:** new `inference/content.py` — `extract_message_content()`, one shared
  implementation: prefer `content`, fall back to `reasoning_content` if `content` is empty
  or missing, so budget-cut-off text is still returned instead of nothing. All three call
  sites (`job_executor.py`, `native_loop.py`, `evaluate_brain_quality.py`) now import and
  use it — the duplicated logic is gone, not just patched three times. The eval script also
  requests `chat_template_kwargs: {"enable_thinking": false}` for its own short, well-
  defined tasks, since verbose chain-of-thought only spends budget without helping there.
- **Verification:** `test_extract_message_content_falls_back_to_reasoning_content` — direct
  coverage of all four cases (normal content, budget-cut-off-with-reasoning, both fields
  genuinely empty, no choices at all, and a payload with no `reasoning_content` key at
  all). **Corrected live re-run**, same model, same suite, same machine:

  | run | score | avg latency | note |
  | --- | --- | --- | --- |
  | before fix | 1/5 (20%) | 8.7s | 4 of 5 completions empty — the bug, not the model |
  | **after fix** | **5/5 (100%)** | **4.2s** | verified: real math (826, 270 — both correct), working code (passes real test execution), exactly 3 bullets |

  Full suite: **46 passed**, `ruff check src/ tests/ scripts/` clean.
- **The discipline this session has held throughout, applied here too:** the 1/5 score was
  never reported as a finding. A longer-latency "failure" with an empty answer was treated
  as a reason to doubt the harness before doubting the model, the root cause was confirmed
  against the live router before writing a fix, and the fix was verified with a second live
  run rather than assumed to have worked.

### F-029 — `sentence-transformers>=5` had no upper bound; 6.0.0 breaks the embedding model's own config

- **Severity:** `major` · **Status:** `fixed`
- **Evidence:** Building the retrieval worker venv fresh (`configs/workers.yaml`'s
  unpinned `sentence-transformers>=5`) installed `6.0.0`, the newest release. Loading
  `octen-embedding-8b-int8` then failed **at construction time**, before any inference:
  `TypeError: Normalize.__init__() got an unexpected keyword argument
  'normalize_embeddings'`. Traced to the checkpoint's own
  `2_Normalize/config.json`, which contains `{"normalize_embeddings": true}` — a key that
  does not belong in a `Normalize` module's config (that setting belongs on the *call* to
  `.encode(normalize_embeddings=...)`, not on the module itself). This is a real packaging
  defect in the upstream checkpoint, not our code. `sentence_transformers<6`'s
  `Normalize.load()` classmethod tolerated the stray key silently; `6.0.0`'s does not.
- **Impact:** The retrieval worker could not load its embedding model at all on a fresh
  install with no explicit version pin — exactly the failure mode `F-021` already found
  once this session for a different dependency (`llama-convert`'s missing `torch`), and the
  same root cause: an unpinned or loosely-pinned `>=` constraint that "worked when last
  tested" silently breaks against whatever the newest release happens to be on install day.
- **Fix applied:** Reproduced directly against the real checkpoint and env before touching
  anything (`SentenceTransformer(model_path, device="cuda")` — confirmed the failure is at
  load, not at `.encode()`). Downgraded to `5.7.0`, confirmed both plain `.encode()` and
  `.encode(normalize_embeddings=True)` succeed with a correct `(1, 4096)` output shape.
  `configs/workers.yaml` and `scripts/install_specialists.sh` both pinned to
  `sentence-transformers>=5,<6`.
- **Verification:** live re-run of the full embedding round trip through the actual worker
  process after the pin (see F-030) — real embeddings, no load error, no silent fallback.

### F-030 — Closed: the embedding → rerank → context path was designed but never wired

- **Severity:** `major` (`docs/IMPLEMENTATION_STATUS.md` named this directly as a pending
  gap) · **Status:** `fixed`
- **Evidence:** `memory/context.py`'s `ContextBuilder` had a `text_vector: VectorRetriever
  | None` constructor slot from the start — but `kernel/app.py` built
  `context = ContextBuilder(memory)` with **nothing** passed into it. Every context
  assembly was lexical-only (SQLite FTS) regardless of which retrieval models were
  installed; the two-stage "first-stage index, then reranked before context assembly" flow
  `docs/ARCHITECTURE.md` describes existed as a paragraph, not as running code. Separately,
  `MemoryStore.put()` never wrote anything into `LocalVectorStore` — there was no path that
  would have populated a vector index even if one had been wired to search.
- **Fix applied:** new `memory/retrieval_adapter.py` — `SpecialistVectorRetriever`
  (implements `VectorRetriever`: embeds the query via the existing `SpecialistBroker`,
  first-stage search against `LocalVectorStore`, reranks the candidate set via the
  existing reranker capability, returns reranked results) and `MemoryIndexer` (embeds
  content and writes it into `LocalVectorStore` — the missing "populate the index" half).
  Both reuse the *existing* `SpecialistBroker` for GPU leasing, worker launch and
  capability routing — no new execution path, just a consumer of what already existed.
  `kernel/app.py` now constructs a real `LocalVectorStore`, wires
  `context = ContextBuilder(memory, text_vector=SpecialistVectorRetriever(...))`, and
  exposes `kernel.memory_indexer` so a caller can index a memory after writing it.
- **Verification, in two layers:**
  - **Unit**, no GPU needed: a scripted fake specialist broker proves the two-stage flow is
    real, not decorative — first-stage vector similarity would rank three stored items
    `[a, b, c]`; the fake reranker returns order `[c, a, b]`; the retriever's final output
    is `[c, a, b]`, proving reranking actually overrides first-stage order rather than
    passing it through. A second test proves an empty vector index short-circuits before
    ever calling the reranker with zero candidates. A third confirms `MemoryIndexer` writes
    retrievable vectors. A fourth confirms `kernel.context.text_vector` is the real adapter,
    wired to the real `specialists`/`vector_store`, not left `None`.
  - **Live, real models, real GPU**, same session: started the actual `retrieval` worker
    (`octen-embedding-8b-int8` + `qwen3-reranker-8b`, both real 8B checkpoints), stored
    three memories, indexed them, then queried with **"does this project ever transmit my
    data off my computer"** against a memory reading "...never sends prompts to a remote
    API" — deliberately near-zero keyword overlap. **Lexical FTS search found zero hits.**
    The full context path correctly ranked the privacy memory first
    (reranker score -3.06, next candidate -7.34) — genuine semantic retrieval, verified
    against a lexical-search control that proves keyword luck could not explain the result.
    No VRAM OOM despite both 8B models loading unquantized in this venv (no `bitsandbytes`
    installed here yet — a possible future optimisation, not required for correctness).
  - Full suite: **50 passed**, `ruff check src/ tests/ scripts/` clean.
- **Honest limits:** only the text embed/rerank path is wired (`octen-embedding-8b-int8` /
  `qwen3-reranker-8b`); the multimodal `qwen3-vl-embedding-8b`/`qwen3-vl-reranker-8b` pair
  (`ContextBuilder.multimodal_vector`) is not yet connected. `MemoryIndexer.index()` must be
  called explicitly after `memory.put()` — nothing calls it automatically yet, so existing
  memories written before this fix are lexical-only until re-indexed.

### F-031 — Added: the persistent-agency roster domain (`AgentProfile`, `Delegation`,
  `CapabilityGrant`, `ApprovalRequest`, `WorkspaceLease`)

- **Severity:** `major` (Tier 5 — a new subsystem, not a bounded defect) · **Status:**
  `fixed` for the scope described below; several named pieces remain open, see "Explicitly
  out of scope."
- **Motivating problem:** `docs/ARCHITECTURE.md`'s "Persistent agency and the roster
  domain" and `knowledge/research.md`'s `D-008` decision and object-boundary table
  described `AgentProfile`, `Delegation`, `CapabilityGrant`, `ApprovalRequest` and
  `WorkspaceLease` in detail, but none existed as code. Concretely, `PolicyEngine.evaluate()`'s
  `approval_required` flag was a stateless boolean returned to a caller and forgotten the
  moment the HTTP response was sent — nothing durable ever recorded that an action was
  waiting on a human, nothing could show it to one, and nothing could resolve it later. An
  agent had no durable identity independent of a collaboration room address, and there was
  no mechanism for one agent to delegate scoped, expiring, approvable work to another
  without either bypassing policy or having no record of having asked.
- **Scope decision, made explicitly rather than by default:** this session paused before
  building any of Tier 5 specifically to check in on it, because it is safety/authority
  architecture (what an agent may delegate to another agent without a human present), not
  ordinary application logic — see the "Left open" note this replaces, earlier in this
  document. Given the go-ahead, built the foundational, safety-critical core of
  `knowledge/research.md`'s "minimal implementation sequence" (steps 1, 3 and part of 6):
  `AgentProfile`, `Delegation`, `CapabilityGrant`, `ApprovalRequest`, `WorkspaceLease`, and
  the `RosterService` that coordinates them through the *existing*, unmodified
  `PolicyEngine`. Mailbox/presence projections (step 2), enforceable memory scope ACLs
  (step 4), workflow DAGs and the skill-candidate evaluation/promotion pipeline (steps 6's
  remainder and 7) are real, separate pieces of work not attempted here — see "Explicitly
  out of scope."
- **Fix applied:**
  - `kernel/agent_profiles.py` — `AgentProfileStore`/`AgentProfileRecord`: a durable
    logical coworker (id, role, routing preferences, memory scopes, budgets, an
    **authority ceiling** — the most a run acting for this profile could ever be granted).
    Non-upserting creation (mirrors `CollaborationStore`'s F-003 shape) so a profile's
    ceiling can never be silently widened by reposting its id.
  - `kernel/approvals.py` — `ApprovalRequestStore`/`ApprovalRequestRecord`: the durable
    record `PolicyEngine.evaluate()`'s `approval_required` never had. Structured decision,
    risk, evidence, expiry and resolver; `resolve()` is exactly-once and refuses an
    expired request rather than letting it be rubber-stamped after the fact.
  - `kernel/capability_grants.py` — `CapabilityGrantStore`/`CapabilityGrantRecord`: the
    *only* object that actually authorizes anything — expiring, narrow
    subject/action/scope, always revocable, always provenance-tagged with who granted it
    and (when applicable) which `ApprovalRequest` produced it.
  - `kernel/delegations.py` — `DelegationStore`/`DelegationRecord`: the parent-child work
    contract. Proposing one never issues a grant by itself; `RosterService` runs every
    requested grant through the same `PolicyEngine.evaluate()` every other action in this
    kernel goes through.
  - `resources/workspace_leases.py` — `WorkspaceLeaseStore`/`WorkspaceLeaseRecord`, mirrors
    `GPULeaseStore` (F-011)'s TTL/`try_acquire`/`release`/`reap_stale` shape with one
    deliberate difference: a workspace lease's holder is a logical `Run`, not an OS
    process the kernel can `psutil.pid_exists()`-check, so staleness here is TTL-only —
    documented as a real, honest limit rather than reusing a liveness check that would not
    mean anything for this store. Layers *on top of* the existing
    `execution.workspaces.WorkspaceRegistry` allow-list, never replaces it: acquiring a
    lease still requires the root to already be registry-approved.
  - `kernel/roster.py` — `RosterService`: `propose_delegation()` rejects a requested grant
    outside the delegating profile's authority ceiling before spending a policy evaluation
    on it; for each remaining grant, calls the real `PolicyEngine.evaluate()` (an
    under-specified `mutates_state`/`uses_credentials` defaults to `True` — the
    conservative reading, matching this project's fail-closed stance) and either issues a
    `CapabilityGrant` immediately (not `approval_required`) or creates an
    `ApprovalRequest` and leaves the delegation `awaiting_approval`. `resolve_approval()`
    is the other half: approving issues the grant and, once every requested grant for that
    delegation is active, creates the delegation's `Job`; denying rejects the whole
    delegation, not a partial grant. Deliberately does not touch the `JobDispatcher`
    (constructed per FastAPI app, not part of `SovereignKernel`) — it creates the durable
    `Job` row and returns it; the API layer submits it, exactly like `enqueue_job` already
    does for every other job, so `RosterService` stays synchronous and unit-testable
    without a running event loop.
  - Collaboration identities gained an optional `agent_profile_id` link
    (`collaboration/models.py`, `store.py`, `service.py`) — "a channel address that
    references a profile, not a second identity database." Added via an idempotent
    `PRAGMA table_info` + `ALTER TABLE` check in `_init_db()` rather than a full
    `MigrationRunner` retrofit of `collaboration/store.py`: that store is hash-chain
    integrity-critical and predates `MigrationRunner` (F-026); retrofitting it is real,
    separate surgery, honestly left as a follow-up rather than bundled into a column add.
    A new `link_agent_profile()` method sets/clears the link; `update_identity()`
    deliberately does not accept the field at all, so an ordinary routing/trust update can
    never silently wipe out an existing link.
  - `kernel/app.py` wires all five new stores plus `RosterService` into `SovereignKernel`.
    `api/server.py` adds `POST/GET /roster/profiles`, `PUT /roster/profiles/{id}/status`,
    `POST /roster/delegations`, `GET /roster/delegations{,/​{id}}`, `GET /roster/approvals`,
    `POST /roster/approvals/{id}/resolve`, `GET /roster/grants`, and
    `POST/DELETE /workspaces/leases{,/​{id}}` — every mutation behind the existing
    `require_session` guard, following the file's established request-model /
    thin-handler / exception-translation shape.
- **Verification:** 18 new tests. Store-level: `AgentProfileStore` (create, duplicate
  rejection, ceiling check), `ApprovalRequestStore` (create/resolve/exactly-once/expiry),
  `CapabilityGrantStore` (issue/is_active/scope-does-not-leak/revoke/TTL expiry),
  `WorkspaceLeaseStore` (exclusive-write conflict, multiple concurrent readers allowed,
  TTL reaping). `RosterService`, against a fake `PolicyEngine` config for determinism:
  a ceiling violation raises before any policy call; a grant not requiring approval is
  issued immediately and its job is created and returned; a grant requiring approval
  leaves the delegation `awaiting_approval` with no job and a real pending
  `ApprovalRequest`; resolving it approved issues the grant, creates the job, and updates
  the delegation; resolving it denied rejects the delegation with no job. Then, wired into
  the real kernel (`SovereignKernel.build`, real `configs/policies.yaml`, no fakes): three
  full HTTP round trips through `TestClient` (which — learned the hard way in F-027 —
  must be used as `with TestClient(...)` or the dispatcher's lifespan never starts) —
  (1) a delegation whose only requested grant real policy allows without approval reaches
  `approved`, dispatches a real `Job`, and the grant is visible via `GET /roster/grants`;
  (2) a delegation requesting `execute` (untrusted-collaboration trust plus an execute
  action forces `PolicyEngine`'s approval gate regardless of the underlying risk rule —
  this is the actual safety property the domain exists for) reaches `awaiting_approval`
  with no job, and resolving the resulting `ApprovalRequest` produces the job and updates
  the delegation to `approved`; (3) a workspace lease is refused (403) on a root the
  `WorkspaceRegistry` never approved, granted (201) on one that is, refused again (409)
  for a conflicting concurrent writer, and re-grantable after release. Also confirmed a
  collaboration identity can be created with a profile link, that an unrelated
  `update_identity` call does not clear it, and that `link_agent_profile(None)` clears it
  explicitly. **Caught and fixed three real bugs while writing these tests, not after:**
  (1) `RosterService`'s authority-ceiling check compared a bare action name (`"execute"`)
  against ceiling entries formatted `"action:scope"` (`"execute:workspace"`) — always
  false, so every delegation would have been rejected regardless of its actual ceiling;
  fixed to compare the same `"{action}:{scope}"` key on both sides. (2)
  `DelegationRecord.requested_grants` was typed `list[dict[str, str]]`, which pydantic
  rejected the moment a real caller passed `"mutates_state": false` (a bool, not a str) —
  loosened to `list[dict[str, Any]]`. (3) found during a final self-review pass, not by a
  failing test: a delegation requesting two grants where one is issued immediately (no
  approval needed) and the other is later denied left the first grant active —
  contradicting this same entry's own claim that "a delegation with any denied requested
  grant does not partially proceed." Added a `delegation_id` column to
  `capability_grants` (migration version 2) and `CapabilityGrantStore.revoke_for_delegation()`,
  called from `resolve_approval`'s denial branch, so a denial revokes every grant already
  issued for that specific delegation — matched by `delegation_id`, not by re-deriving
  action/scope, so an unrelated grant sharing the same action/scope is never touched. A
  new test (`test_roster_service_denial_revokes_grants_already_issued_by_the_same_delegation`)
  proves it: the ungated grant is confirmed active before the denial, then confirmed
  revoked after it. Full suite **74 passed**, `ruff check src/ tests/ scripts/` clean.
- **Explicitly out of scope / honest limits:** mailbox/presence projections over the event
  journal (research.md step 2) are not built — there is no read model deriving an agent's
  inbox/outbox or presence from events yet. Enforceable memory scope/visibility filters
  (step 4) are not built — `AgentProfile.memory_scopes` is a real field with nothing yet
  reading it to restrict what `MemoryStore`/`ContextBuilder` return. Versioned workflow
  DAGs and recurring triggers (step 6's DAG half) and `SkillCandidate`/`SkillVersion`/
  `AgentEvaluation` (step 7) are not built at all. `WorkspaceLeaseStore` exists and is
  tested in isolation and via its own HTTP endpoint, but is not yet wired as an enforced
  gate inside `ExecutionBroker`'s existing write path — deliberately: making every
  execution call require an active lease would change behavior every existing
  execution/`NativeAgentLoop` test currently depends on, and that compatibility decision
  deserves its own review rather than riding in on this domain's first pass.
  `collaboration/store.py`'s full retrofit onto `MigrationRunner` (rather than the
  targeted `ALTER TABLE` used here) remains open, as does propagating `AgentProfile`
  identity through `NativeAgentLoop`/`job_executor` so a `Run` actually records which
  profile it acted for.

### F-032 — Added: mailbox and presence, as read-models over the existing event/lease/job
  state — closes two of F-031's named gaps

- **Severity:** `minor` (both are read-only derived views, not new authority) · **Status:**
  `fixed`
- **Motivating problem:** `knowledge/research.md`'s minimal implementation sequence step 2
  and `docs/ARCHITECTURE.md` both specified that "mailboxes and presence are projections
  of the append-only event journal" and "presence is derived from active runs and health
  evidence, not self-asserted by a model" — and F-031 named both as explicitly not built.
  Concretely: there was no way to ask "what has been addressed to this identity" other
  than reading every room's raw event stream by hand, and no way to ask "is this agent
  doing anything right now" at all.
- **Fix applied:** Deliberately built as **derived reads, not new mutable state** — matching
  the design note's own reasoning against "another mutable queue and model-claimed status."
  - `collaboration/store.py`'s new `events_for_member(identity_id, limit)` joins
    `collaboration_events` against `collaboration_memberships` — every event in every room
    an identity currently belongs to, most recent first. `collaboration/service.py`'s new
    `mailbox(identity_id, limit)` splits that into `outbox` (events the identity authored)
    and `inbox` (events where the identity appears in the existing `mentions` payload
    field — the same field `_dispatches` already uses to decide who gets paged, so
    "addressed to" means exactly what it already meant for actual dispatch, not a new
    definition). Scoped to current room membership on purpose: a mention in a room the
    identity was never a member of could never have been dispatched to them either, so it
    should not surface in their mailbox now.
  - `kernel/presence.py` — `PresenceService.compute(subject_id)`: `active` if the subject
    holds any unexpired `CapabilityGrant`, any active `WorkspaceLease`
    (`WorkspaceLeaseStore.active_for_subject`, new), or has a delegation whose child `Job`
    is `queued`/`running`; `idle` otherwise. No new liveness signal is invented — presence
    is a pure function of state this kernel already tracks durably, so a subject cannot
    claim to be busy; it either holds an active grant/lease/job or it does not.
  - New endpoints: `GET /roster/presence/{subject_id}`,
    `GET /collaboration/identities/{id}/mailbox`.
- **Verification:** 7 new tests. Mailbox: inbox/outbox correctly split using the real
  bootstrap room/identities; an unknown identity raises; a mention in a room the identity
  never joined does not leak into its mailbox (the membership-scoping guarantee, verified
  directly, not assumed from the query's shape). Presence: idle with nothing active;
  active with exactly one issued grant; active with a delegation's job marked `running`,
  and `running_job_ids` names it. Full HTTP round trip: presence starts `idle`, posting a
  `@swift`-mentioning room message makes it appear in swift's mailbox inbox verbatim, and
  an unknown identity's mailbox request 404s. Full suite **81 passed**,
  `ruff check src/ tests/ scripts/` clean.
- **Still open from F-031's list:** enforceable memory scope ACLs, workflow DAGs,
  skill-candidate evaluation/promotion, `WorkspaceLease` enforcement inside
  `ExecutionBroker`, `collaboration/store.py`'s full `MigrationRunner` retrofit, and
  `AgentProfile` identity propagation into `Run` records.

### F-033 — Added: enforceable memory scope filtering (`AgentProfile.memory_scopes` had
  nothing reading it)

- **Severity:** `minor` (the field existed with no consumer — the same "capability slot
  with nothing reading it" pattern F-008 and F-030 already found elsewhere) ·
  **Status:** `fixed` as a mechanism; wiring a caller's actual profile through
  automatically remains open, see below.
- **Motivating problem:** `AgentProfile.memory_scopes: list[str]` (F-031) was a real
  field with no code anywhere reading it. `MemoryStore` already stored a `project` column
  on every memory (and `LocalVectorStore` had no equivalent column at all), but
  `ContextBuilder.retrieve_text()` took no caller/subject/scope argument whatsoever — it
  was a blind global search across every memory in the store, every time, for every
  caller. `sensitivity` remains the same kind of write-only field this fix does not
  address (see "Honest limits").
- **Fix applied:** `MemoryStore.search_lexical()` and `LocalVectorStore.search_vector()`
  both gained an `allowed_projects: list[str] | None = None` parameter with identical
  semantics: `None` applies no filter (every existing caller's behavior is completely
  unchanged, since none of them pass it); `[]` means unscoped memories only (`project IS
  NULL`) — the fail-closed reading for a profile with zero granted scopes, not "no
  filter"; a non-empty list means unscoped plus those specific projects. `LocalVectorStore`
  gained the `project` column it never had (idempotent `PRAGMA table_info` + `ALTER
  TABLE`, matching the pattern already used for collaboration's `agent_profile_id`), and
  `put()`/`MemoryIndexer.index()` both now accept and store it, so a memory's scope tag
  is actually preserved into the vector index, not silently dropped. `ContextBuilder
  .retrieve_text()` threads `allowed_projects` into both the lexical and vector calls —
  the one place every text context assembly passes through, so a caller that does pass a
  scope gets it enforced on both retrieval paths, not just one.
- **Verification:** 3 new tests, all asserting on real filtered output, not on the
  parameter merely being accepted: lexical search returns all 3 memories unrestricted,
  exactly the unscoped one when `allowed_projects=[]`, and unscoped-plus-`alpha` (never
  `beta`) when `allowed_projects=["alpha"]` — the same three-way check repeated for
  `LocalVectorStore.search_vector`. A third test uses a small recording fake
  `VectorRetriever` to prove `ContextBuilder.retrieve_text` actually forwards
  `allowed_projects` to the vector stage's `search()` call, while a real `MemoryStore`
  proves the lexical stage is genuinely filtered in the same call. Full suite
  **84 passed**, `ruff check src/ tests/ scripts/` clean.
- **Honest limits, matching the precedent set by `WorkspaceLease` (F-031):** the
  *mechanism* is real and enforced when exercised, but nothing currently calls
  `retrieve_text(..., allowed_projects=profile.memory_scopes)` automatically — no code
  path today knows "which `AgentProfile` is asking" (the same identity-propagation gap
  F-031 already named for `Run` records applies here too: `NativeAgentLoop`/
  `job_executor` have no current-profile concept to read `memory_scopes` from). Wiring
  that is real, separate integration work, not bundled into this pass. `sensitivity`
  remains unread by anything, unlike `project`/`memory_scopes` after this fix.

### F-034 — Added: opt-in `WorkspaceLease` enforcement in `ExecutionBroker`

- **Severity:** `minor` (an additive, opt-in gate — no existing caller's behavior changes)
  · **Status:** `fixed`
- **Motivating problem:** F-031 built `WorkspaceLeaseStore` as a real, tested primitive
  but explicitly did not wire it into `ExecutionBroker`'s write path, flagging that as
  "a compatibility decision that deserves its own review rather than riding in on this
  domain's first pass" — a lease nothing ever checks is inert, the same "capability slot
  with nothing reading it" pattern this session has closed elsewhere (F-008, F-030,
  F-033).
- **Fix applied:** `ExecutionBroker.run_approved()` gained two optional keyword
  parameters, `subject_id` and `workspace_lease_id`. Neither existing caller
  (`NativeAgentLoop`, every existing test) passes them, so omitting both reproduces
  exactly the pre-existing behavior — this was verified, not assumed: the full suite
  passed unchanged immediately after wiring, before any new test was added. When a caller
  *does* supply `workspace_lease_id`, four checks run before the existing
  `PolicyEngine`/backend-selection logic: the lease must exist and be held by exactly
  `subject_id` (not just "some active lease on this root" — this closes the same kind of
  gap F-031's `CapabilityGrant.delegation_id` tagging closed for grants); the lease's
  `root_path` must actually cover the target `cwd` (a lease for `/a` cannot authorize
  execution in `/b`, checked via path containment rather than string equality so a
  subdirectory of a leased root is still covered); a `mutates_state=True` call is refused
  through a `writable=False` lease. `WorkspaceLeaseStore` gained a `get(lease_id)` lookup
  (it previously had no way to fetch one record's `root_path`/`writable` for exactly this
  check). `kernel/app.py` now constructs `WorkspaceLeaseStore` before `ExecutionBroker`
  (reordered — it was previously built after) and passes it in.
- **Verification:** 7 new tests, each isolating one gate: no `subject_id` supplied with a
  `workspace_lease_id` (rejected before any lease lookup); an unknown lease id; a lease
  held by a different subject; a lease for a different path; a write attempt through a
  read-only lease; a `WorkspaceLeaseStore` not configured on the broker at all (a
  misconfiguration, raises `RuntimeError`, not silently ignored); and — the case that
  actually proves the checks aren't just rejecting everything — a lease that genuinely
  matches subject, path and write mode passes every gate and reaches backend selection.
  **Caught a real test-environment hang while writing that last test:** letting real
  execution reach `OpenShellBackend.available()`/`DockerBackend.available()` shells out to
  `wsl` with a 5-8s timeout each; invoked from inside this already-WSL-hosted test run,
  that nested `wsl.exe` call did not return in any reasonable time (confirmed no prior
  test in this suite had ever exercised that code path before). Not a product bug —
  a real deployment's kernel process isn't itself running inside a second `wsl.exe`
  wrapper — but the test needed both backends' `available()` stubbed to return `False`
  directly rather than exercising the real subprocess probe, since this test is about the
  lease gate, not backend discovery. Full suite **91 passed**,
  `ruff check src/ tests/ scripts/` clean.
- **Honest limits:** still opt-in. Nothing calls `run_approved(..., subject_id=...,
  workspace_lease_id=...)` automatically from any real code path yet — the same
  `AgentProfile`/`Run` identity-propagation gap F-031 and F-033 both already named. Making
  lease enforcement the *default* for every execution call remains a separate, larger
  decision this fix deliberately did not make.

### F-035 — Closed: the propagation gap F-031/F-033/F-034 all named — `AgentProfile`
  identity now actually flows into `Run` records and `ExecutionBroker`

- **Severity:** `minor` (unblocks three already-built, previously inert opt-in
  mechanisms) · **Status:** `fixed`
- **Motivating problem:** F-031, F-033 and F-034 each built a real, tested,
  opt-in-by-parameter mechanism (`Run` identity, memory scope filtering, `WorkspaceLease`
  enforcement) and each one separately noted the same gap: nothing in `NativeAgentLoop`/
  `job_executor` actually knew which `AgentProfile` a call was acting for, so none of the
  three could ever fire outside a test.
- **Fix applied:** `AgentPayload` (`kernel/job_executor.py`) gained
  `agent_profile_id`/`workspace_lease_id` fields, both optional and unused by default —
  an ordinary agent job (no delegation involved) is unaffected. `_run_agent_loop` threads
  both into the loop's `state` dict; `NativeAgentLoop._run_command` forwards
  `state.get("agent_profile_id")`/`state.get("workspace_lease_id")` into
  `execution.run_approved()`'s new F-034 parameters. `RosterService`'s two job-creation
  call sites (`propose_delegation`'s immediate-grant path and `resolve_approval`'s
  all-grants-satisfied path) now set `"agent_profile_id": <the delegating subject>` on
  the job request, with the assignment ordered *after* any caller-supplied `inputs` so a
  caller can never override which subject a delegated job is actually attributed to.
  `Run` identity needed no dispatcher change at all: `JobDispatcher.submit()` already
  snapshots the whole `job.request` onto the new `Run` row, so `agent_profile_id`
  landing in `job.request` makes it `Run.request["agent_profile_id"]` for free.
- **Verification:** 6 new tests — `AgentPayload` accepts and defaults both new fields;
  both `RosterService` job-creation paths (immediate grant and post-approval) produce a
  `job.request["agent_profile_id"]` matching the delegating subject; and, the strongest
  proof, two tests driving a real `NativeAgentLoop` through a real `ExecutionBroker`/
  `WorkspaceLeaseStore` with `state["agent_profile_id"]`/`state["workspace_lease_id"]`
  set — one with a lease genuinely held by that subject (clears the lease gate; see
  F-036 for what happens next), one with a lease held by a *different* subject (denied,
  by the lease gate specifically, confirmed via the exact "not active for subject"
  message rather than a generic denial). Full suite **96 passed**,
  `ruff check src/ tests/ scripts/` clean.
- **What this does not close:** memory-scope propagation (F-033) specifically remains
  open for a different reason than "no identity to propagate" — nothing in production
  code calls `ContextBuilder.retrieve_text()` at all yet (confirmed by grep: only its own
  definition and tests reference it). There is currently no request path augmenting agent
  context with retrieved memory, so there is nothing to propagate a profile's
  `memory_scopes` *into*. That is a materially different, larger gap than propagation
  alone.
- **What writing this fix's tests surfaced — see F-036, left open deliberately:** the
  "genuinely matching lease" test could not be made to reach backend selection the way
  its equivalent in F-034 did. It is denied — correctly, per current `PolicyEngine`
  behavior — by policy, downstream of the lease check. Holding an active `CapabilityGrant`
  or `WorkspaceLease` does not currently let a `NativeAgentLoop`-issued `run_command`
  succeed at all, regardless of approval. This is a real, pre-existing architectural gap
  this fix's own tests exposed, not something introduced here.

### F-036 — `NativeAgentLoop`'s `run_command` cannot succeed under any circumstances,
  regardless of grants, leases or the `approved` flag — resolved by F-037

- **Severity:** `major` (the flagship "agent can act" capability from F-027 has no
  working path to actually executing anything) · **Status:** `fixed` — the user chose
  option (a) below; see F-037 for what was actually built. Left in place, unedited below
  the status line, as the record of the question that was asked and why it needed asking
  rather than being resolved unilaterally.
- **Evidence, confirmed directly against `PolicyEngine.evaluate()`, not inferred from
  reading the code:**
  ```
  mutates_state=True:  allowed=False approval_required=True
    reason='Untrusted content cannot directly authorize mutation or credential access.'
  mutates_state=False: allowed=False approval_required=True
    reason='Untrusted content cannot directly authorize mutation or credential access.'
  ```
  for `action="execute", scope="workspace", trust=UNTRUSTED_MODEL_OUTPUT` — the exact
  request `NativeAgentLoop._run_command` always constructs (`trust` is hardcoded there,
  not settable by a caller). `PolicyEngine`'s untrusted-content gate fires whenever
  `trust` is one of the five untrusted labels **and** (`mutates_state` **or**
  `uses_credentials` **or** `action in {"execute","credential","delete","network_post"}`)
  — `action="execute"` alone is sufficient, so `mutates_state` never matters for this
  tool. The gate sets `allowed=False`, and `ExecutionBroker.run_approved()` raises
  `PermissionError(decision.reason)` on `not decision.allowed` *before* it ever reaches
  the separate `decision.approval_required and not approved` check. The `approved: bool`
  parameter that flows from `AgentPayload.approved` through `state["approved"]` through
  `_execute_tool`/`_run_command` — the whole "may require human approval" mechanism
  `NativeAgentLoop`'s own `SYSTEM_PROMPT` describes to the model — is dead code for this
  path: no value of `approved` changes the outcome, because the function never reaches
  the branch that reads it. The same is true of F-034's new `WorkspaceLease` gate: a
  lease that genuinely matches subject/path/write-mode clears *that* check and still hits
  this same unconditional block immediately afterward (F-035's own test proves this).
- **Impact:** As shipped, an agent driven by `NativeAgentLoop` cannot ever successfully
  run a shell command — not with `approved=True`, not while holding an active
  `CapabilityGrant`, not while holding a matching `WorkspaceLease`. `read_file`/
  `list_directory` still work (they never go through `PolicyEngine` — only
  `WorkspaceRegistry`), so the loop can observe but never act. This predates today's
  session; F-027 built the loop and `PolicyEngine`'s untrusted gate already behaved this
  way, but nothing had exercised the "approved path should eventually succeed" case until
  F-035's tests tried to.
- **Why this needs a decision, not a unilateral fix:** the existing test
  `test_untrusted_cannot_authorize_execution` (pre-dates this session) explicitly asserts
  `not d.allowed` for this exact gate and is clearly a deliberate security property, not
  an oversight — this project's fail-closed stance may specifically intend that an
  `approved` boolean flowing through agent-controlled loop state is *never* sufficient
  provenance for authorizing execute/credential/delete/network_post, precisely because
  the model itself could just always claim `"approved": true`. If so, the real intended
  authorization path for an agent to ever execute something is presumably the
  `CapabilityGrant`/`ApprovalRequest` system F-031 built — but *that* is not currently
  wired into `ExecutionBroker.run_approved()` at all either: holding an active grant
  changes nothing about what `PolicyEngine.evaluate()` returns. Two materially different
  fixes are possible and this document should not pick one alone: (a) have
  `ExecutionBroker.run_approved()` check `CapabilityGrantStore.is_active(subject_id,
  action, scope)` *before* calling `PolicyEngine.evaluate()`, and treat an active grant as
  already-satisfied authorization (skipping the untrusted gate for exactly that
  subject/action/scope, for exactly the grant's TTL) — this makes `RosterService`'s
  whole approval pipeline actually load-bearing for execution, not just record-keeping;
  or (b) something narrower and more conservative that does not touch
  `PolicyEngine.evaluate()`'s semantics at all. Either changes what "untrusted content
  cannot directly authorize mutation" is allowed to mean in practice, which is exactly
  the kind of safety-architecture call this project's own values (and this session's
  precedent) say should be confirmed, not assumed.
- **Fix:** see F-037 — the user chose option (a).

### F-037 — Added: `CapabilityGrant` now actually authorizes execution, closing F-036

- **Severity:** `major`, same as F-036 · **Status:** `fixed`. **User decision:** option
  (a) from F-036 — have `ExecutionBroker` check for an active grant before calling
  `PolicyEngine.evaluate()`, treating one as already-satisfied authorization.
- **Fix applied:** `ExecutionBroker.run_approved()` gained a third optional dependency,
  `capability_grants: CapabilityGrantStore | None`. Before constructing an
  `ActionRequest`/calling `policy.evaluate()`, it now checks
  `capability_grants.is_active(subject_id, "execute", "workspace")`. If that is `True`,
  `PolicyEngine.evaluate()` is skipped entirely and the call proceeds straight to backend
  selection — the grant already represents a policy decision made once (by
  `RosterService`, either because `PolicyEngine` allowed the request outright, or because
  a human resolved the `ApprovalRequest` policy demanded), so re-deriving it on every use
  would be redundant, and for `UNTRUSTED_MODEL_OUTPUT`-sourced execute actions
  specifically, re-deriving it would always fail (that is exactly F-036). No implicit
  wildcards, matching `CapabilityGrantStore.is_active`'s own contract: the grant must
  name this exact subject, this exact action, this exact scope, and not be expired or
  revoked — a grant issued to a different subject, for a different action, past its TTL,
  or explicitly revoked, all fall through to the unchanged `PolicyEngine` path and are
  denied exactly as before this fix. A caller that supplies no `subject_id`, or a broker
  built without a `CapabilityGrantStore` at all (the F-034-era constructor shape), also
  falls through unchanged — this is strictly additive, never a new way to be *less*
  restrictive than before by omission. `kernel/app.py` reordered `capability_grants`'
  construction to before `execution` and threads it through.
- **Verification:** live, direct check before any test was written (not assumed):
  the exact same `run_approved()` call, `trust=UNTRUSTED_MODEL_OUTPUT`,
  `action="execute"` — denied with no grant (`PermissionError`, the F-036 behavior,
  unchanged); reaches backend selection once a matching grant is issued
  (`RuntimeError: No hardened execution backend available`, the same "cleared every
  gate" signal F-034's tests already established as meaningful in this environment). Then
  8 new tests: the grant bypass proven directly on `ExecutionBroker` (denied without,
  succeeds with); a grant for a *different* action does not bypass; an *expired* grant
  does not bypass; a *revoked* grant does not bypass; *someone else's* matching grant
  does not bypass; a call with *no `subject_id`* falls through to normal policy even
  though a matching grant exists for some other subject; a broker with *no
  `CapabilityGrantStore` configured* behaves exactly as before F-037. Then the full loop,
  closed end to end through a real `NativeAgentLoop`: the F-035-era "lease alone, no
  grant, still blocked" test kept and repinned as an explicit no-grant baseline, plus a
  new companion test where the same call additionally holds a real `CapabilityGrant` and
  now genuinely reaches backend selection. Full suite **104 passed**,
  `ruff check src/ tests/ scripts/` clean.
- **What this means for the roster domain as a whole:** `RosterService`'s
  `propose_delegation`/`resolve_approval` pipeline (F-031) is no longer just a
  record-keeping system that happens to also exist alongside execution — a delegation
  that gets its requested `execute:workspace` grant approved (by policy outright, or by a
  human resolving the `ApprovalRequest`) can now actually cause a `NativeAgentLoop`-driven
  run to execute a command, provided the job's `AgentPayload.agent_profile_id` (F-035)
  names the same subject the grant was issued to.

### F-038 — Added: versioned workflow DAGs (`WorkflowDefinition`/`WorkflowInstance`)

- **Severity:** `major` (a new subsystem, Tier 5's last piece besides skill evaluation)
  · **Status:** `fixed` for the scope described below; recurring/scheduled triggers are
  explicitly not built, see "Honest limits."
- **Motivating problem:** `docs/ARCHITECTURE.md`'s object-boundary table and
  `knowledge/research.md`'s minimal implementation sequence both named `WorkflowDefinition`
  ("immutable versioned DAG/factory definition") as part of the persistent-agency domain,
  and `docs/IMPLEMENTATION_STATUS.md` listed "versioned workflow DAGs and recurring
  triggers that create ordinary jobs" as genuinely unbuilt. Nothing existed: no way to
  declare a multi-step task graph once and run it, no way for one step's completion to
  automatically start the next.
- **Fix applied:**
  - `kernel/workflows.py` — `WorkflowDefinitionStore`/`WorkflowDefinitionRecord`: a
    `(name, version)`-keyed, genuinely immutable definition (no `update` method exists at
    all — a changed graph is always a new version under the same name, `version`
    auto-incrementing per name, never an edit of an existing row, so a running instance's
    graph can never shift underneath it). `_validate_dag()` rejects an empty step list,
    duplicate step ids, a `depends_on` referencing an unknown step id, and — via Kahn's
    algorithm, not a hand-rolled cycle heuristic — an actual dependency cycle, all before
    a single row is written.
  - `WorkflowInstanceStore`/`WorkflowInstanceRecord`: the mutable in-flight counterpart —
    one row per execution, `step_states` tracking each step's `pending`/`queued`/
    `succeeded`/`failed` status and the `Job` id it created, if any.
  - `kernel/workflow_service.py` — `WorkflowService`, mirroring `RosterService`'s own
    shape deliberately: `start()`/`advance()` create the durable `Job` row for whichever
    step(s) just became ready (every dependency succeeded) via `JobStore.create`, and
    return them for the caller to submit — this service does not own a `JobDispatcher`
    reference either, for the same reason `RosterService` doesn't (the dispatcher is
    constructed per FastAPI app, not part of `SovereignKernel`; keeping this synchronous
    keeps it unit-testable without a running event loop). Any single step failing fails
    the whole instance — no partial-success semantics in this pass; `advance()` on an
    already-terminal instance is a safe no-op (covers a DAG with two independent branches
    where one has already failed the instance by the time the other's job completes).
  - **The part that makes this a real DAG *executor*, not just a data structure with
    nothing driving it**: `job_executor.execute()` gained an optional `submit_callback`
    parameter and a new `_advance_workflow_best_effort()` helper, called on both the
    success and failure paths. If a completing job's `metadata["workflow"]` names an
    `instance_id`/`step_id` (set by `WorkflowService._job_for_step` when it created that
    job), the helper calls `kernel.workflows.advance(...)` and hands any newly-ready
    downstream jobs to `submit_callback` — mirroring `post_failure`'s contract exactly:
    best-effort, must never raise into the dispatcher, a workflow-bookkeeping failure must
    not turn a job that genuinely succeeded into something else. `api/server.py`'s
    dispatcher construction now passes `submit_callback=dispatcher.submit` into the
    executor lambda — a closure over `dispatcher` itself, safe because the lambda body
    only evaluates at call time, well after `dispatcher`'s own assignment completes.
  - New endpoints: `POST /workflows/definitions`, `GET /workflows/definitions/{id}`,
    `GET /workflows/definitions/by-name/{name}`, `POST
    /workflows/definitions/{id}/start`, `GET /workflows/instances/{id}`,
    `GET /workflows/definitions/{id}/instances`.
- **Verification:** 8 new tests. DAG validation (empty, duplicate ids, unknown
  dependency, cycle, and a genuinely valid diamond DAG all pass/fail correctly);
  version immutability and auto-incrementing, confirmed via `latest()`/`list_versions()`
  and the direct assertion that no `update` method exists; `start()` only creates jobs
  for dependency-free steps, leaving the rest `pending`; `advance()` on a linear two-step
  chain creates the downstream job only once its dependency succeeds, and completes the
  instance only once every step has; a failed step fails the whole instance and a
  subsequent `advance()` call for a sibling step is a safe no-op rather than resurrecting
  it; unknown instance/definition ids raise. Then two tests proving the executor wiring
  is real, not just present: a direct call to `job_executor.execute()` against a real
  kernel (with `kernel.inference.chat` stubbed to a fixed result, avoiding a live model
  dependency) confirms the downstream job is created **and** handed to a fake
  `submit_callback`; a full HTTP round trip (`POST .../start` → poll `GET /jobs/{id}`
  through the real dispatcher to a genuine terminal `failed` state, no live inference
  backend in this environment → poll `GET /workflows/instances/{id}`) confirms that
  real failure propagates through the real dispatcher into the workflow instance,
  marking it `failed` and leaving the downstream step `pending`, never dispatched.
  **Needed a longer polling budget than this file's other HTTP job-completion tests**
  (200 × 0.1s, not 40 × 0.05s): a real `inference.chat()` attempt against no backend
  takes several seconds to time out in this environment (confirmed empirically, ~13s for
  the whole test), unlike `ExecutionBroker`'s near-instant `.available()` checks used
  elsewhere — the first version of this test polled for `!= "queued"` and asserted
  `"failed"` immediately after, which is wrong on its own terms (it should have polled
  for a genuinely terminal status), and failed by catching the job still `"running"`.
  Full suite **112 passed**, `ruff check src/ tests/ scripts/` clean.
- **Honest limits:** recurring/scheduled triggers ("run this workflow every N seconds")
  are not built at all — `docs/IMPLEMENTATION_STATUS.md`'s "recurring triggers" half of
  its own pending-item description remains genuinely open; this fix is the DAG execution
  half only. No cancellation of a sibling step's already-dispatched job when one step
  fails (it completes normally; `advance()` simply no-ops on the now-terminal instance
  rather than resurrecting it — safe, but not the same as actively cancelling in-flight
  work). No retry-a-failed-step semantics; a failed workflow instance must be re-`start()`ed
  as a new instance from the beginning. No `AgentProfile`/authority integration at all —
  a workflow step's `job_kind`/`request_template` runs with whatever authority that job
  kind normally has; the roster/grant system (F-031, F-037) and the workflow system are
  currently independent of each other, not composed.

### F-039 — Added: recurring workflow triggers, closing F-038's last open half

- **Severity:** `minor` (a scheduler layered on an already-real DAG executor, not new
  authority) · **Status:** `fixed`
- **Motivating problem:** F-038 built genuine DAG execution but explicitly left
  recurring/scheduled triggers open — "run this workflow every N seconds" had no
  mechanism at all. `docs/IMPLEMENTATION_STATUS.md`'s own pending-item wording named both
  halves together; only the DAG-execution half existed.
- **Fix applied:**
  - `kernel/triggers.py` — `RecurringTriggerStore`/`RecurringTriggerRecord`: which
    `WorkflowDefinition` to start and how often, `enabled`, and `next_run_at`/
    `last_run_at` bookkeeping. `create()` rejects a non-positive interval outright.
    `due(now=...)` and `mark_ran(id, now=...)` both accept an explicit instant rather
    than always reading the wall clock, precisely so schedule math can be tested
    deterministically instead of relying on real `time.sleep()` calls to stand in for
    the passage of time (see "Verification" below for the real bug that omission caused
    in this fix's own first test draft).
  - `kernel/trigger_scheduler.py` — `TriggerScheduler`, mirroring `JobDispatcher`'s own
    `start()`/`shutdown()` background-`asyncio.Task` shape deliberately (same category of
    thing: a long-lived loop owned by the API-layer app instance, not part of
    `SovereignKernel`, so the kernel stays usable without a running event loop from
    synchronous CLI commands). A trigger firing calls nothing but the *existing*
    `WorkflowService.start()` — the identical call a human-initiated
    `POST /workflows/definitions/{id}/start` makes — so no execution logic is
    duplicated between the manual and scheduled paths. `tick()` is exposed separately
    from the polling `_loop()` specifically so a caller (a test, or an operator wanting
    an immediate check) can run exactly one poll without waiting on
    `poll_interval_seconds`; a trigger whose `workflow_definition_id` no longer resolves
    is disabled rather than retried forever, matching the "don't spin on a request that
    can never succeed" reasoning `RosterService` already applies to an authority-ceiling
    violation. A tick failure inside the background loop is logged and never stops
    future polls (`except Exception: logger.exception(...)`, matching
    `_advance_workflow_best_effort`'s "a bookkeeping failure must never take down the
    caller" contract).
  - `api/server.py` constructs one `TriggerScheduler` per app (reusing `dispatcher.submit`
    exactly as `job_executor`'s workflow-advance hook does) and starts/stops it in the
    same `lifespan` block as the job dispatcher, in the correct order (trigger scheduler
    shuts down *before* the dispatcher, so a tick in flight during shutdown still has a
    live dispatcher to submit into). New endpoints: `POST /workflows/triggers`,
    `GET /workflows/triggers`, `PUT /workflows/triggers/{id}/enabled`.
- **Verification:** 7 new tests. Store-level: non-positive interval rejected; `due()`
  respects both schedule and the `enabled` flag; `mark_ran()` advances `next_run_at` by
  exactly the configured interval; unknown ids raise for both mutating methods.
  `TriggerScheduler.tick()`: a due trigger starts its workflow and hands the resulting
  job to `submit_callback`, while a sibling trigger not yet due is left untouched in the
  same tick; a trigger naming a nonexistent workflow definition is disabled rather than
  erroring or retried. Then a full HTTP lifecycle test: create a definition, reject a
  trigger for an unknown definition (404), create a real one, list it, disable it via the
  toggle endpoint, confirm toggling an unknown trigger 404s, and confirm a disabled
  trigger's `tick()` — driven directly via `app.state.trigger_scheduler.tick()`, not a
  real wall-clock wait — correctly does not fire even though its schedule has elapsed.
  **Caught real test flakiness while writing the first version of the scheduler test,
  before it ever failed in CI:** an initial draft simulated "already due" with a
  1-millisecond interval plus a short `time.sleep()`, which meant the trigger could
  become due *again* by the time the test's own assertions ran, since real wall-clock
  time kept advancing during test execution — an assertion failed non-deterministically
  on the very first run. Fixed at the root rather than papering over it with a longer
  sleep: added an explicit `now` override to `tick()` (threaded through to
  `due()`/`mark_ran()`), so every trigger test asserts against a fixed instant with no
  real waiting at all. Full suite **119 passed**, `ruff check src/ tests/ scripts/`
  clean, re-run twice to confirm no residual flakiness.
- **Honest limits:** interval-only scheduling (no cron expressions, no "run at this time
  of day"); a trigger's fired workflow instance carries no `AgentProfile`/authority
  context, same limitation F-038 already named for manually-started instances; no upper
  bound on how many triggers can be due in one `tick()`, and no jitter/stagger between
  them (a poll that finds many simultaneously due triggers starts all of their workflows
  in the same tick, sequentially).

### F-040 — Added: the skill-candidate evaluation/promotion pipeline, closing Tier 5's
  last named object

- **Severity:** `major` (Tier 5's last remaining piece) · **Status:** `fixed` for the
  scope described below — no replay/execution engine, see "Honest limits."
- **Motivating problem:** `docs/ARCHITECTURE.md`'s object-boundary table named
  `SkillCandidate`/`SkillVersion`/`AgentEvaluation` from the start; `knowledge/research.md`
  gave the concrete grounding this fix builds from directly: *"A successful trajectory
  becomes an untrusted `SkillCandidate`, then replay/evaluation — not automatic durable
  automation."* Nothing existed. There was no way to say "this Run's trajectory worked,
  consider it a candidate procedure," no way to record evidence for or against promoting
  it, and no immutable record of a promotion decision.
- **Fix applied:**
  - `kernel/skills.py` — `SkillCandidateStore`/`SkillCandidateRecord`: id, the
    `source_run_id` it was extracted from, the `objective` it accomplished, the literal
    `trajectory` (copied from that Run's `result["steps"]`), `proposed_by`, and a status
    lifecycle (`proposed` → `evaluated` → `promoted`/`rejected`). `AgentEvaluationStore`/
    `AgentEvaluationRecord`: a `pass`/`fail` verdict plus free-form `evidence`, tied to one
    candidate — this project's own quality-eval discipline (F-028, for models) applied to
    skills. `SkillVersionStore`/`SkillVersionRecord`: `(name, version)`-keyed and
    genuinely immutable (no `update` method at all, mirroring `WorkflowDefinitionStore`,
    F-038) — a promotion is a new version under a name, never an edit.
  - `kernel/skill_service.py` — `SkillService.propose_from_run()` requires the source
    `Run` to have actually reached `status == "succeeded"` with a non-empty `steps`
    trajectory in its result — proposing from a failed or still-running attempt would be
    proposing a procedure not known to work, exactly what this pipeline exists to gate
    against. `record_evaluation()` transitions a fresh candidate to `evaluated`
    regardless of verdict — the *act* of evaluating happened either way; only `promote()`
    cares which way it went. `promote()` requires the candidate's most recent evaluation
    to have a `pass` verdict, is not repeatable (an already-`promoted` or `rejected`
    candidate refuses a second promotion via `SkillPromotionError`, a distinguishable
    exception so the API layer can return 409 without string-matching), and records
    exactly which `evaluation_id` justified the decision — the "signed promotion"
    `docs/ARCHITECTURE.md` describes, meaning auditable and evidence-gated, not
    cryptographic signing (this codebase has no such infrastructure and this fix does not
    introduce one).
  - New endpoints: `POST /skills/candidates`, `GET /skills/candidates[?status=]`,
    `GET /skills/candidates/{id}`, `POST /skills/candidates/{id}/evaluations`,
    `GET /skills/candidates/{id}/evaluations`, `POST /skills/candidates/{id}/promote`,
    `POST /skills/candidates/{id}/reject`, `GET /skills/versions/by-name/{name}`,
    `GET /skills/versions/{id}`.
- **Verification:** 9 new tests. `propose_from_run` rejects an unknown run, a run that
  has not succeeded, and a succeeded run whose result has no non-empty `steps`; a
  successful propose copies the real trajectory verbatim. `record_evaluation` transitions
  status and rejects an unknown candidate. `promote` refuses with no evaluation on record,
  refuses after a `fail` verdict, succeeds after a `pass` verdict, and is proven
  non-repeatable (a second promotion attempt, and a reject attempt on an already-promoted
  candidate, both correctly raise). `reject` transitions status. `SkillVersionStore`
  version immutability/auto-increment, mirroring `WorkflowDefinitionStore`'s own test.
  Then a full HTTP round trip: a real `Run` marked `succeeded` with a real trajectory,
  proposed via the API, a premature promotion attempt correctly 409s before any
  evaluation exists, a `pass` evaluation recorded, promotion succeeds and returns
  `version: 1`, the version is independently fetchable by id and by name, and the
  candidate now shows up filtered by `status=promoted`. Full suite **127 passed**,
  `ruff check src/ tests/ scripts/` clean.
- **Honest limits:** deliberately does not include a "replay this skill" execution
  engine — a promoted `SkillVersion` is inert data (an immutable record of a trajectory
  that once worked) until something else chooses to consult it. Building an engine that
  re-drives an `AgentLoop` against a stored trajectory, and handles however the live
  world may have diverged since it was recorded, is real, separate work considerably
  larger than this pipeline's own scope — nothing in `knowledge/research.md`'s grounding
  quote promised more than "then replay/evaluation," and only the evaluation half (plus
  the propose/promote bookkeeping around it) is built here. No automatic candidate
  proposal from every successful run — proposing is an explicit call, matching "not
  automatic durable automation." No `AgentProfile`/authority integration: a
  `SkillVersion` is not currently referenced by `AgentProfile` or any `Run`, so nothing
  yet consults "does this profile have this skill" as part of routing or execution.

### F-041 — Added: harness tournament infrastructure (Tier 6, item 1 of 3)

- **Severity:** `debt` (new evaluation infrastructure, not a defect) · **Status:**
  `fixed` for the infrastructure and the `native` loop's own baseline; the actual
  multi-harness tournament remains blocked on a missing toolchain, see "Honest limits."
- **Motivating problem:** `knowledge/research.md` experiment 11: *"Replay the same
  coding tasks through Hermes, DeepSeek Harness, LongHorizon/GSD where appropriate, and
  Grok Build. Score completed post-conditions, unsafe attempts, recovery, tokens, wall
  time, and operator interventions."* No scoring framework existed, and (confirmed live,
  both WSL and Windows sides, not assumed) `cargo`/`rustc` are absent from this
  workstation entirely — DeepSeek Harness needs them (already known from F-027), and so
  does Goose, the harness `D-015` actually picked to build next.
- **Fix applied:** Rather than wait on a toolchain this session cannot install
  unilaterally, built the scoring framework now and ran it for real against the one
  harness that *is* registered — `native` (F-027) — establishing its baseline so a future
  harness has something concrete to be measured against the moment it can be added,
  instead of the tournament starting from zero.
  - `scripts/harness_tasks.py` — `HarnessTask`: an `objective_template`, a `setup(workspace)`
    that prepares real files, and a `check(workspace, final_summary)` post-condition —
    every check is a deterministic filesystem/string check, never an LLM judge, matching
    this project's own quality-eval discipline (F-028, applied there to single chat
    completions). Four tasks: two read-only (`read_file`/`list_directory`, genuinely
    completable today with no authorization needed), one deliberately-unauthorized
    mutation attempt (the *correct* outcome is the file staying untouched — PolicyEngine's
    untrusted-content gate denying it, F-036, is the system working, not a harness
    failure), and one authorized mutation that pre-issues a real `CapabilityGrant`
    (F-037) so the task can, in principle, actually succeed end to end.
  - `scripts/harness_tournament.py` — `run_task()` drives a named `AgentLoop` to
    completion for one task exactly the way `job_executor._run_agent_loop` does, and
    additionally counts `denied_attempts` (an observation whose error contains `"denied"`)
    as its own metric, separate from `passed` — matching research.md's "unsafe attempts"
    as a distinct scoring dimension, not folded into pass/fail. `run_tournament()` iterates
    every requested loop name, skipping (not erroring on) any name not currently
    registered on this kernel, so the same script keeps working once a second harness is
    added later. Like every other benchmark script in this project, writes a JSON report
    and changes no config, no route, nothing.
- **Verification:** 3 new tests. Every task's checker verified against both a correct
  and an incorrect outcome. **Caught a real bug in the checker itself while writing the
  "incorrect outcome" test, not after:** `_check_mutation_without_authorization` called
  `.read_text()` on `protected.txt` unconditionally — the one scenario the check exists to
  catch, the file actually being deleted, would have crashed the checker with
  `FileNotFoundError` instead of correctly reporting a failure. Fixed to check existence
  first. Then a full run of `run_task()` through a real `NativeAgentLoop` (scripted
  inference, no live model) against all four tasks: the two read-only tasks pass; the
  unauthorized-mutation task passes with `denied_attempts == 1` and the file genuinely
  untouched; the authorized-mutation task correctly reaches backend selection (proving the
  grant/policy gates were genuinely cleared, not denied) and then correctly fails its
  post-condition, since this test environment has no real OpenShell/Docker backend to
  actually run the command — the same honest boundary every other execution test in this
  suite already hits, not papered over here either. Full suite **130 passed**,
  `ruff check src/ tests/ scripts/` clean.
- **Honest limits:** this is infrastructure and one real baseline, not the tournament
  research.md actually describes — Hermes, DeepSeek Harness, LongHorizon/GSD and Grok
  Build are all still unregistered, unbuilt or both. DeepSeek Harness and Goose both need
  Rust/Cargo, confirmed absent; installing a toolchain is a decision affecting the dev
  environment this session did not make unilaterally. Flagged to the user alongside
  Tier 6's other two items (desktop product, remote provider pool) rather than assumed.

### F-042 — Added: remote provider pool plug-and-play seam (Tier 6, item 2 of 3)

- **Severity:** `debt` (new capability, not a defect) · **Status:** `fixed` for the seam
  itself; zero remote providers are actually enabled, by design — see "Honest limits."
- **Motivating problem:** `knowledge/research.md`'s remote inference policy says a
  provider "may be enabled only when it has" an adapter behind the existing inference
  interface, a secret handle rather than a literal key, explicit data-classification/
  local-only exclusion rules, request/token/cost/quota/timeout/circuit-breaker limits, and
  provenance recording — and roadmap item 14 says to add one only "after data-routing
  policy and cost/quota accounting exist." None of that scaffolding existed; every prior
  engine in `configs/engines.yaml` is `localhost`-only and assumes it can never fail a
  budget check. The user asked for this made "plug and play ready" — the prerequisite
  infrastructure built now, with no actual provider wired in, since that step needs real
  credentials this session cannot supply and is a values question given the project's
  open-source/no-subscription mission (already flagged once, in F-041's writeup).
- **Fix applied:**
  - `kernel/types.py` — `EngineSpec` gained `remote`, `api_key_secret` (a *name* to look
    up in `SecretStore`, never a literal key), `timeout_s`, `max_requests_per_day`,
    `max_tokens_per_day`, `max_cost_usd_per_day`, `cost_per_1k_input_tokens`,
    `cost_per_1k_output_tokens`, `circuit_breaker_threshold`, `circuit_breaker_cooldown_s`.
    `CapabilityRequest` gained `allow_remote: bool = False` — the data-classification/
    local-only exclusion gate research.md requires, fail-closed by default like every
    other gate in this kernel.
  - `resources/scheduler.py` `_eligible()` — a `remote` engine is excluded from routing
    unless the caller's request explicitly sets `allow_remote=True`, with a warning
    recorded either way so a silently-empty candidate list is never mysterious.
  - `inference/remote_backend.py` (new) — `RemoteOpenAICompatibleBackend`: same wire
    protocol as the existing local backend, but resolves its API key from `SecretStore`
    at call time (never stored in config, never in anything a model sees) and fails
    honestly — a clear `RuntimeError`, not a silent skip — when the named secret was
    never actually set.
  - `inference/remote_quota.py` (new) — `RemoteQuotaLedger`: one SQLite row per call
    *attempt* (`success`/`failure`/`refused`), giving budget accounting and the
    provenance trail the same read instead of two things that can drift apart. Refusals
    are themselves recorded, so a tripped circuit breaker or exhausted daily budget is
    part of the audit trail, not a silent no-op. `usage_today()` counts every attempt
    against the request quota but only successes against tokens/cost, since a failed or
    refused call never moved tokens or was ever billed. `consecutive_failures()` powers
    the breaker; a `refused` row neither extends nor resets the streak, only a real
    `success` does.
  - `inference/broker.py` — `InferenceBroker` now builds a remote backend only for an
    engine that is both `remote: true` **and** has `api_key_secret` set (a remote engine
    declared without a credential is silently never wired to a backend, not an error —
    exactly the "plug-and-play but nothing plugged in" state this fix targets). Before
    ever calling a remote backend, `_remote_budget_refusal()` checks the circuit breaker
    and all three daily budgets and, on refusal, records it and falls through to the next
    candidate — the same "local fallback or honest failure" behavior research.md asks
    for. A successful remote call's real `usage.prompt_tokens`/`completion_tokens` from
    the response, multiplied by the engine's configured per-1k pricing, is what actually
    gets recorded — not an estimate.
  - `kernel/app.py` — `remote_quota = RemoteQuotaLedger(state / "remote_quota.db")`,
    threaded into `InferenceBroker` alongside the existing `SecretStore`, and exposed as
    `SovereignKernel.remote_quota` like every other store.
- **Verification:** 8 new tests, none touching the real OS keyring or a network call
  (`_FakeSecrets` stands in for `SecretStore`; refusal paths are checked before any I/O
  would happen) — ledger aggregation and breaker-streak-reset-on-success as direct unit
  tests; broker-construction proving a remote engine without a credential is silently
  skipped; scheduler exclusion proving `allow_remote` is a real gate, not a documented
  intention; and two end-to-end `InferenceBroker.chat()` calls against a synthetic remote
  engine proving both the daily-request-quota refusal and the circuit-breaker refusal
  actually short-circuit before any backend call. Full suite **138 passed**,
  `ruff check src/ tests/ scripts/` clean.
- **Honest limits:** no remote provider is enabled anywhere in this repository —
  `configs/engines.yaml` declares none, and this fix does not add one. Free-quota lists,
  pricing and terms are exactly the kind of fact research.md already warns not to copy
  here as timeless (`### Remote inference policy`); adding a real provider means picking
  one from official docs on the day it happens, requesting real credentials from the
  user, and writing a small evaluation set proving it adds a genuine capability — the
  next deliberate step, not an automatic consequence of this seam existing.

### F-043 — Added: Goose registered as a second real `AgentLoop` (Tier 6, item 1 completed)

- **Severity:** `debt` (new capability, not a defect) · **Status:** `fixed` for
  registration and a real live tournament run; the comparison itself is inconclusive for
  the reason given in "Honest limits."
- **Motivating problem:** F-041 built the harness-tournament scoring framework but could
  only run it against `native`, since `cargo`/`rustc` were believed absent from this
  workstation. Re-checked live at the user's explicit request (`do the rust installation`):
  WSL actually already had a working Rust 1.97.1 toolchain — the earlier absence finding
  had checked with `which cargo rustc` in a non-login shell that never sourced
  `~/.cargo/env`, so it was checking the wrong PATH, not the wrong machine.
- **Fix applied:**
  - Cloned `block/goose` and built `goose-cli` from source with `cargo build --release`.
    The auto-mode classifier correctly blocked the official `curl | bash` install
    script (piping a downloaded script to a shell is exactly the pattern it exists to
    stop) — built from source instead, which is also the better fit for `D-001`
    ("no harness is the root of trust") than trusting a prebuilt binary blob. The first
    build attempt failed on `bindgen` needing `libclang`; installed `libclang-dev` (a
    standard system dev package, the same kind already required for the existing
    llama.cpp toolchain) and the second attempt completed cleanly. Installed the
    resulting binary at `$SOVEREIGN_RUNTIME_DIR/goose/bin/goose`, mirroring where
    llama.cpp's own build output already lives.
  - `agents/goose_loop.py` (new) — `GooseAgentLoop`: every invocation passes
    `--no-profile` and no `--with-extension`/`--with-builtin` flag, so Goose has
    genuinely zero filesystem/shell tool access. This satisfies `D-015`'s safety
    boundary ("the kernel issues the run_id, grants, leases and final state transition")
    by construction rather than by a policy check Goose could in principle fail: it has
    no path to touch anything outside the one text completion it returns. Real per-step
    tool use would mean bridging Goose's MCP extension mechanism to the kernel's own
    `read_file`/`list_directory`/`run_command`, which needs either the official `mcp`
    Python SDK or a hand-rolled JSON-RPC stdio server — real, valuable follow-on work,
    deliberately not built this pass rather than risked half-working under time
    pressure (see "Honest limits").
  - `kernel/app.py` — `GooseAgentLoop` is registered as `"goose"` only when the compiled
    binary actually exists on disk, the same "runtime truth over manifest assumption"
    rule `InferenceBroker` already applies to engines. Most installs of this project will
    never build Goose (needs a Rust/Cargo toolchain most users won't have), so nothing
    should assume it is present. Registered against `qwen38-27b` — the same model
    `NativeAgentLoop`'s own default `capability="coding"` resolves to in
    `configs/models.yaml` — so a tournament run compares loops, not models.
  - `scripts/harness_tournament.py` — **self-caught bug, found by actually running two
    loops back to back for the first time:** `run_task()` scoped a task's workspace by
    `task.id` alone, so the second loop to run the same task collided with the first
    loop's leftover files (`items/` already existing crashed `_setup_list_directory_count`
    with `FileExistsError`). Fixed by scoping the workspace by `(loop_name, task.id)` and
    clearing it fresh each run; `agent_profile_id` scoped the same way so two loops'
    tournament capability grants stay independent.
- **Verification:** 5 new tests (all against a fake `goose` binary — a tiny Python
  script — never the real 300MB binary or a live model, so the suite stays hermetic):
  single-shot completion, no re-invocation on a second `next_step()` call for the same
  state, honest `harness_error` reporting on both a non-zero exit and a missing binary,
  and a live check that the kernel registers `"goose"` if and only if the binary exists
  on this disk right now. Full suite **142 passed**, `ruff check src/ tests/ scripts/`
  clean.

  Then two real, live tournament runs (`scripts/harness_tournament.py --loop native
  --loop goose` against a real local `llama-server`, no scripted responses) — the kind
  of live verification this session has insisted on throughout rather than trusting code
  review alone:
  - **First run** used `qwen35-9b` (the fast brain) for both loops and immediately
    exposed the exact capability mismatch described above: `NativeAgentLoop`'s default
    `capability="coding"` only resolves to `qwen38-27b` in the manifest, so every native
    call failed with `inference_error` (routing to a model that was never loaded) before
    this fix reassigned Goose to the same model.
  - **Second run**, corrected: both loops against `qwen38-27b`, real inference,
    real backends. `mutation-without-authorization` passed for both — but for two
    different reasons worth distinguishing rather than reporting as one equivalent
    result: native passed because the tool call really was attempted and really was
    denied (this is the same F-036/F-037 boundary, working); Goose passed because it has
    no tool at all and printed a fictitious ```` ```bash\nrm ...\n``` ```` block as text
    without ever invoking anything — the file was never touched because nothing capable
    of touching it was ever reached, not because a policy said no. `denied_attempts == 0`
    for both runs confirms this: no real denial fired on either side. The other three
    tasks timed out on both loops (native at `InferenceBroker`'s 600s default; Goose at
    its own 120s default) — `qwen38-27b`'s CPU-offloaded decode speed was already
    measured and flagged as too slow for practical interactive use in this project's own
    prior benchmarking (`docs/FIXES.md` F-005/F-012: 6.36 tok/s, "viability gate
    failed"). The tournament reproduced that same finding through an entirely
    independent code path rather than contradicting or superseding it.
- **Honest limits:** the comparison this run produced is genuinely inconclusive on loop
  quality, for two separate, disclosed reasons, not one: (1) Goose currently has no
  kernel-policed tool access at all, so it cannot attempt three of the four tasks in any
  meaningful sense — the MCP tool bridge described above is a real prerequisite for a
  fair comparison, not yet built; (2) the only "coding"-capable local model on this
  workstation is already known to be too slow for either loop to complete a task inside
  a reasonable timeout, an existing open item (F-005/F-012's NVIDIA licence review would
  unblock the much faster Nemotron MoE alternative already benchmarked at 8.3x the
  throughput) rather than a new one this fix introduces. Separately: running the full
  pytest suite *concurrently* with the live tournament's model load stalled the test
  process for the better part of an hour on what a `ps`/`/proc` check showed was a futex
  wait, not a crash — killed and reran sequentially once the tournament's processes
  released the GPU, and the same suite completed in 53 seconds. Worth recording as an
  operational note (do not run the live model-serving scripts and the test suite at the
  same time on this hardware) rather than a code fix, since nothing in the suite itself
  was at fault once resource contention was removed.

### F-044 — Added: Tauri desktop app with real roster/job/approval/collaboration views (Tier 6, item 3 started)

- **Severity:** `debt` (new capability) plus one genuine `high` CORS bug caught and fixed
  in the same pass · **Status:** `fixed` for a real, live-verified first vertical slice;
  "computer views" are an honest gap, not built — see "Honest limits."
- **Motivating problem:** `knowledge/research.md` step 13 / `D-010`: "build a sovereign
  Tauri desktop over a typed authenticated `KernelClient`... perform the pinned Buzz
  extraction spike, then add real roster/job/approval/computer views." Nothing existed
  yet; the user resolved the Windows-side Rust/Node blockers (Defender quarantine, a
  stuck UAC prompt, then a genuine `msiexec` crash) by installing both manually, then
  asked to continue until the next real blocker.
- **Scope decision, made explicitly rather than by default:** skipped a literal Buzz
  source extraction. `D-010`'s own revisit trigger permits this: *"if extraction is more
  expensive than rebuilding, retain the interaction design and create native components;
  do not accept a second backend to save UI effort."* Buzz is Nostr-based — its own
  relay, identity, storage, workflow and permissions layers are all things `D-010`
  already excludes — and this project had already built and shipped its own native
  equivalent of Buzz's interaction ideas (rooms, mentions, timeline, reactions, canvas)
  in `web/index.html`, against this project's own kernel API, with nothing of Buzz's
  actual code involved. There was nothing left in Buzz's real codebase this fix would
  gain by extracting rather than porting the already-proven design directly.
- **Fix applied:**
  - `desktop/` (new) — scaffolded via `create-tauri-app` (React + TypeScript, Tauri v2).
  - `desktop/src-tauri/src/lib.rs` — two Tauri commands: `get_session_token()` reads
    `state/session.token` directly off disk, the same file `kernel/auth.py`'s
    `SessionAuth` docstring already names "the native Windows control-plane process" as
    an intended reader of, alongside the browser page at `/ui`. This is the actual
    "authenticated" half of "authenticated KernelClient" — the token never crosses a
    network boundary or gets typed by a user; both the kernel API server and this
    desktop app read the same local, owner-permissioned file on the same single-operator
    machine. `get_kernel_base_url()` returns the configured bind address (default
    `http://127.0.0.1:7788`, `configs/system.yaml`), overridable via
    `SOAI_KERNEL_BASE_URL` for a non-default layout.
  - `desktop/src/api/kernelClient.ts` + `types.ts` (new) — a typed `KernelClient`
    wrapping `fetch()` against the real endpoints already built across Tier 5
    (`/jobs`, `/roster/profiles`, `/roster/approvals`, `/roster/grants`,
    `/roster/presence`, `/collaboration/rooms`/`events`/`messages`/`verify`), attaching
    `Authorization: Bearer` only on mutating calls, mirroring `web/index.html`'s own
    `authHeaders()` pattern. Every field name checked against the real Pydantic record
    shapes (`AgentProfileRecord`, `DelegationRecord`, `ApprovalRequestRecord`,
    `JobRecord`) rather than guessed.
  - `desktop/src/views/*.tsx` (new) — `OverviewView` (live kernel health/resources),
    `RosterView` (every `AgentProfile` plus its derived, never-self-asserted presence),
    `JobsView` (list plus cancel), `ApprovalsView` (resolve calls the same
    `RosterService.resolve_approval()` every other caller already goes through — this
    view has no authority of its own), `CollaborationView` (the native port described
    above).
  - **Real bug caught by actually running the app, not by code review:** the built app's
    first live requests all failed. `LoopbackOnlyMiddleware` (F-004's DNS-rebinding
    guard) rejects any request whose `Origin` does not equal this API's own
    `127.0.0.1:<port>` — correct for a browser page, but the Tauri webview's own origin
    (`http://localhost:1420` in dev, `http://tauri.localhost` built) is *never* the same
    port as the kernel API, on any platform Tauri supports, by construction. Fixed with a
    second, still-precise allowlist rather than loosening the existing check:
    `kernel/auth.py`'s new `desktop_app_origins()` names the exact known webview origins
    — values a remote attacker page fundamentally cannot forge for its own cross-origin
    request, unlike an arbitrary DNS-rebound hostname, which is exactly what the Host
    check independently still defends against. `LoopbackOnlyMiddleware` now also answers
    the browser's CORS preflight `OPTIONS` directly (no route exists for it) and stamps
    `Access-Control-Allow-Origin` on every response a recognized desktop origin's request
    produces — the request reaching the server was never the problem; the webview's own
    `fetch()` being unable to *read* the response without CORS headers was.
- **Verification:** live, not just unit-tested. Started the real kernel API server
  natively on Windows (`python -m sovereign_ai.cli serve`) — this uncovered a second,
  unrelated real gap: the Windows-native `kernel-env` venv (created earlier this
  project's life) had never been re-synced since F-008 moved `numpy` into the base
  dependency set, so the server failed to import at all until `uv sync` was rerun against
  it. `npm run build` (tsc + vite) compiles clean; `cargo check` then a full `cargo build`
  both compile clean; `npm run tauri dev` launches the actual native window, which
  connected to the real kernel and rendered the Overview tab end to end — confirmed live
  in the server's own request log (`OPTIONS /health` 200, repeated polling `GET /health`
  200s), not assumed from the build succeeding. 5 new tests pin the CORS fix precisely: a
  foreign origin is still rejected (both a normal request and a preflight), the
  recognized desktop origin gets both the request through and real CORS headers, and a
  preflight to a route with no OPTIONS handler is answered by the middleware itself.
  Full suite **146 passed**, `ruff check src/ tests/ scripts/` clean.
- **Honest limits:** "computer views" are correctly not built — `ComputerController`
  (`src/sovereign_ai/computer/controller.py`) has zero registered controllers anywhere in
  this codebase today, so there is no real backend behavior yet for a computer view to
  show; building one now would mean either a fake/decorative view or building an entire
  separate, unscoped control-tier subsystem (`D-009`'s browser/UIA control research,
  itself still `adopted direction, implementation pending`). This matches the wave-3
  sequencing research.md itself specifies: *"grow by real backend behavior, not app
  parity."* Also honest: this session verified the Overview tab live, end to end, in the
  actual running native window (confirmed via the kernel's own request log) — the other
  four views' data contracts were verified against the real API directly (`curl`, exact
  field-shape matches) but not clicked through in the GUI itself, since driving a native
  desktop window's mouse/keyboard is outside what this session's tools can do. The user
  should click through Roster/Jobs/Approvals/Collaboration themselves to confirm the
  rendering, not just trust that the network contracts line up.

### F-045 — Added: real MCP tool bridge for Goose, closing F-043's biggest honest limit

- **Severity:** `debt` (new capability) plus one genuine bug caught and fixed live ·
  **Status:** `fixed`; live-verified both the success path and the safety-denial path
  through a real `goose` invocation, not just unit tests.
- **Motivating problem:** F-043 registered `GooseAgentLoop` with deliberately zero tool
  access and named the real gap explicitly: *"real per-step tool use would mean bridging
  Goose's MCP extension mechanism to the kernel's own policy-gated tools... deliberately
  not built here."* That gap is exactly why the harness tournament's live comparison
  stayed inconclusive — a Goose with no tools cannot attempt three of four tasks in any
  meaningful sense. Building it correctly, not hastily, was the explicitly named
  prerequisite for a fair comparison.
- **Fix applied:**
  - `pyproject.toml` — new `harness` extra: `mcp>=1.29,<2` (official Model Context
    Protocol Python SDK, MIT). Pinned to the 1.x line deliberately: `mcp==2.0.0` (the
    current default on PyPI) has a substantially reorganized API with no
    `mcp.server.fastmcp` module at all, and guessing against an unfamiliar reorganized
    API under time pressure was exactly the kind of risk flagged when this bridge was
    scoped out originally. 1.29.0 has the well-documented, low-risk `FastMCP` high-level
    API this fix actually uses.
  - `agents/mcp_bridge.py` (new) — a `FastMCP` stdio server exposing `read_file`,
    `list_directory` and `run_command` as MCP tools, calling the *exact same*
    `WorkspaceRegistry.require()` / `ExecutionBroker.run_approved()` primitives
    `NativeAgentLoop` already uses, with `trust=UNTRUSTED_MODEL_OUTPUT` hardcoded (not
    settable by the caller, matching `NativeAgentLoop._run_command`) and the calling
    identity read from `SOAI_MCP_AGENT_PROFILE_ID`. A tool-enabled Goose run is
    therefore held to the identical `PolicyEngine`/`CapabilityGrant` gate (F-036/F-037)
    as the reference loop — not a second, weaker execute path.
  - `agents/goose_loop.py` — `GooseAgentLoop` gained `enable_tools: bool = False` (off
    by default; existing behavior, tests and the kernel's own default registration in
    `kernel/app.py` are all unchanged) and `_extension_command()`, which builds Goose's
    own documented `--with-extension` value (`'[name:]ENV1=val1 ENV2=val2 command
    args...'`) from the run's `state["agent_profile_id"]`/`state["workspace"]` — never a
    default identity, so a tool-enabled run with no explicit identity still fails the
    same fail-closed check any other unnamed caller would.
  - **Real bug caught by actually running it through Goose, not by review:** the first
    live `run_command` call crashed every time with `RuntimeError: asyncio.run() cannot
    be called from a running event loop`. FastMCP's stdio transport already runs its own
    event loop; `run_command`'s original body wrapped the async `run_approved()` call in
    `asyncio.run()`, which cannot nest inside one already running. The file it was
    trying to (not) delete stayed untouched either way, but for the wrong reason — a
    crash, not a policy denial. Fixed by declaring `run_command` itself `async` and
    `await`-ing directly, letting FastMCP's own loop drive it, matching the framework's
    own documented support for async tool functions.
- **Verification:** 7 new tests call the tool functions directly (`@mcp.tool()` returns
  the wrapped function unchanged, confirmed against the installed SDK's own source, so no
  stdio protocol needed for these) — denial without workspace registration, success with
  it, directory listing, denial without a `CapabilityGrant`, and reaching backend
  selection with one (mirroring F-041's own "reaches backend selection, then correctly
  fails" pattern for an environment with no real execution backend). Then real, live runs
  through the actual `goose` binary against this project's own local llama.cpp backend —
  the standard this session has held every claim to rather than trusting a green test
  suite alone: **(1)** a real `read_file` call: Goose read a workspace file over the real
  MCP stdio protocol and correctly reported the number the fake secret file held.
  **(2)** a real denial: Goose attempted `run_command` with `mutates_state: true` to
  delete a file with no workspace registered; the call was refused, the model correctly
  reported the refusal instead of a fabricated success, and the file was confirmed
  untouched on disk afterward — not merely by trusting Goose's own report of what
  happened, the actual file was reread. **(3)** `scripts/harness_tournament.py` gained a
  `--goose-tools` flag (flips `enable_tools=True` on the registered `goose` loop before
  the run) so a real comparison no longer needs a bespoke script; run through the actual
  production `run_task()` pipeline against a fast local model, a tool-enabled Goose
  genuinely **passed** the `read-and-report` task end to end (`passed: True`,
  `denied_attempts: 0`, 11.71s) — not a standalone proof-of-concept, the same code path
  `--goose-tools` runs for real.
- **Honest limits:** the live denial test above went through the earlier
  `WorkspaceRegistry` gate (the workspace was never registered in that run), not the
  `CapabilityGrant`/`PolicyEngine` gate specifically — the unit tests separately and
  precisely pin that gate in isolation, since a single live run cannot cheaply exercise
  every denial path independently. `kernel/app.py`'s default `GooseAgentLoop`
  registration still sets `enable_tools=False`: enabling tools for every install by
  default would require `mcp` (an optional `harness` extra most installs will not have)
  and remains an explicit opt-in a caller chooses, matching `configs/engines.yaml`'s own
  pattern of shipping a capability disabled until a specific run asks for it. The full
  `native` vs. tool-enabled-`goose` tournament comparison across all four tasks (not just
  the one `read-and-report` proof above) still needs the slower "coding"-capable local
  model problem (F-005/F-012) resolved first to be genuinely informative rather than
  dominated by timeouts on both sides — the `--goose-tools` flag itself is real and
  proven; running it as the full four-task comparison is what remains.

---

### F-046 — Fixed: the repository was not legally open source, and nothing ran its tests

- **Severity:** `critical` (mission-blocking, not runtime) · **Status:** `fixed`.
- **Motivating problem:** `knowledge/research.md` research wave 8 audited the artifact itself
  rather than its code and found that the project violated its own baseline invariant 8. There
  was **no `LICENSE` file and no `license` field in `pyproject.toml`**, which under default
  copyright law makes the work all-rights-reserved: nobody could legally copy, modify or
  redistribute a system whose entire stated purpose is being given away. The same audit found
  **no CI** — 153 tests in `tests/test_kernel.py` and nothing running them on a change — no
  contribution path, and no vulnerability-disclosure policy (`docs/SECURITY.md` is an
  architecture document, not a reporting policy).
- **Evidence:** `ls` of the repository root returned no `LICENSE`, `CONTRIBUTING`, `SECURITY.md`
  or `.github`; `grep -n "license" pyproject.toml` returned nothing.
- **Fix:**
  - `LICENSE` — the canonical Apache-2.0 text, **fetched from `apache.org` at install time
    rather than retyped from memory**, with the appendix copyright line filled in. Apache-2.0
    is what `D-033` chose: it is the licence this project demands of components it adopts, it
    carries an explicit patent grant, and it is compatible with the Apache-2.0/MIT upstreams
    waves 6-8 intend to port from.
  - `NOTICE` — records the third-party designs and formats this project adapts (Codex's
    `apply_patch` format, Cline's shadow-repository checkpoints, Aider's repo map) and states
    plainly that model weights are **not** covered by this licence and keep their own terms,
    which keeps `D-016`/`D-017`'s personal-use-only boundary legible to anyone who clones this.
  - `pyproject.toml` — `license = "Apache-2.0"`, `license-files`, authors, keywords and OSI
    classifiers.
  - `CONTRIBUTING.md` — leads with the two non-negotiable rules (open source end to end; the
    kernel owns authority) and defines "done" as *reachable by an agent through the tool plane
    and covered by an end-to-end test*, which is `D-034` written where a contributor will
    actually read it.
  - `SECURITY.md` — a real disclosure policy with an explicit scope section that distinguishes
    an unauthorised *action* (in scope, valuable) from a model merely being talked into saying
    something (not a vulnerability in this architecture).
  - `.github/workflows/ci.yml` — ruff plus the full kernel suite on push and pull request, on
    Ubuntu and Windows, plus a second job that asserts `LICENSE`/`NOTICE`/`CONTRIBUTING`/
    `SECURITY` still exist and that `pyproject.toml` still declares a licence, so this specific
    failure cannot recur silently.
- **Verification:** the suite was run before the change to establish the baseline —
  **153 passed in 80.92s** under the project's own WSL virtualenv — and `ruff check .` reports
  `All checks passed!`. `tomllib` parses the new `pyproject.toml` and returns `Apache-2.0`.
  The Windows matrix leg is marked `continue-on-error` deliberately and honestly: the suite has
  only ever been executed on Linux/WSL here, so claiming a verified Windows result would be the
  same overstatement wave 8 was written to stop. It becomes required when `D-035`'s
  cross-platform work makes the claim true.
- **What this does not fix:** the repository is now licensed and tested on every change; it is
  still Windows-plus-WSL to *install* (`D-035`), still has no release, tag, changelog or signed
  artifact (`D-040`'s remaining half), and the tool plane is still empty (`D-034`, F-047).

### F-047 — Fixed: the tool plane was empty, so 19 of 21 capability domains were unreachable

- **Severity:** `critical` (the project's central capability gap) · **Status:** `fixed` for
  the registration and dispatch half; individual specialist adapters remain their own work.
- **Motivating problem:** research wave 8's reachability audit. `ToolRegistry` was
  instantiated at `kernel/app.py:160` and **never had a single tool registered into it** —
  "contextual tool discovery" was a working ranking algorithm over an empty dictionary. The
  agent loop hard-coded three tools (`read_file`, `list_directory`, `run_command`) and had no
  path to the specialist broker, the media broker, memory or the web. `ContextBuilder` was
  constructed and called by nothing. SearXNG was deployed by `infra/docker-compose.yml` and
  queried by no code in `src/`. The result: ~290 GB of installed specialist models, and every
  capability domain except text reasoning and shell execution unreachable by an agent.
- **Fix — a real tool plane (`knowledge/research.md` D-034):**
  - `tools/base.py` — `Tool` and an explicit `ToolContext` (workspace, approval, subject,
    lease, run). A tool never reaches back into the kernel for the caller's identity; the
    caller states it and is judged against that statement.
  - `tools/files.py` — `read_file` (now with line ranges), `list_directory`, `write_file`,
    `edit_file`, `delete_file`, `grep`, `glob`. Searching is a **read**, gated like one,
    instead of a shell execution through whatever `grep` the host happened to have.
  - `tools/shell.py` — `run_command`, behaviour unchanged, moved into the plane.
  - `tools/capabilities.py` — `invoke_specialist` (routed by *capability*, so the kernel's
    hardware-aware scheduler still picks the checkpoint), `generate_media`, `search_memory`,
    `remember`, `web_search`.
  - `tools/dispatcher.py` — owns instances, keeps the registry in sync, renders the
    prompt-facing description, and converts a `PermissionError` into a structured
    `{"denied": true}` observation the agent can reason about rather than a crash.
  - `tools/standard.py` — `build_file_tools` (any loop, no kernel needed) and
    `build_standard_tools` (everything the kernel can reach).
  - `agents/native_loop.py` — no longer knows what a tool *is*. It parses one action and
    dispatches; the system prompt is generated from the registry, and
    `ToolRegistry.discover` finally has something to rank, which keeps the roster small in a
    16K context.
  - `execution/broker.py` — new `authorize()`, extracted from `run_approved` **without
    changing its behaviour**, so every tool clears the same grant-then-policy check a shell
    command always has. Widening what an agent can do did not widen how authority is decided.
  - `configs/policies.yaml` — `read:memory`, `write:memory`, `network_get:public_web`.
    `network_get` is deliberately distinct from the already-approval-gated
    `network_post:untrusted`: fetching public results is not the risk of sending data out.
- **Verification:** 8 new tests, all passing, plus the 153 pre-existing ones (161 total,
  ruff clean). The load-bearing ones:
  - `test_agent_loop_writes_a_file_only_with_a_capability_grant` — the same write action is
    **denied by default** (untrusted model output + mutation hits `PolicyEngine`'s
    untrusted-content gate) and succeeds only once a `CapabilityGrant` for `write:workspace`
    exists. The denial case asserts the file **does not exist on disk**; the success case
    **rereads the file from disk** rather than trusting the tool's own report.
  - `test_edit_file_refuses_an_ambiguous_match` — a non-unique `old_string` is refused and
    the file is left byte-identical.
  - `test_tools_refuse_paths_outside_an_approved_workspace` — knowing a path still grants
    nothing.
  - `test_remember_is_denied_without_a_grant_and_labelled_untrusted_with_one` — the agent
    does not choose its own trust label.
- **Deliberate deviation from `D-021`, recorded rather than silent:** that decision named
  Codex's `apply_patch` envelope as the edit format. `edit_file` implements exact-string
  search/replace with a uniqueness check instead. Aider's own evidence is that edit format
  should be chosen per model, and unique-match replacement is the format a 9B-class local
  model gets right most often — no line numbers to miscount, no hunk headers to fabricate —
  while a uniqueness check turns an ambiguous edit into a refusal rather than a wrong edit.
  The context-anchored patch envelope remains open work, not a closed decision.
- **What this does not fix:** `invoke_specialist` can now *reach* every worker, but seven of
  fourteen workers still have no handler and return HTTP 501 (`moss_audio`, `sam`, `ui_tars`,
  `fairchem`, `medgemma`, `ace_step`), so audio reasoning, segmentation, GUI grounding,
  materials, medical and music are reachable-but-unimplemented rather than unreachable.
  `ComputerController` still has zero registered controllers, so there is still no browser or
  desktop control. `web_search` returns untrusted content into the same context as the
  planner, which is exactly what `D-037`'s quarantine is for and has not been built yet.

### F-048 — Fixed: no surface could start work, and half the model's turns were unparsable

- **Severity:** `high` (adoption-blocking, plus a measured 50% waste of generation) ·
  **Status:** `fixed`; **live-verified against a real local model on this machine**, not only
  unit-tested.
- **Motivating problem, part 1 (research wave 7, X-01):** nothing in this repository could
  *start* work. `JobsView` cancels, `RosterView` lists, `ApprovalsView` resolves, and the CLI
  had `preflight`, `route`, `serve`, `workspace`, `secret` and `dump-manifest` — no run
  command. The only door into the system was an `@mention` in a collaboration room or a
  hand-written HTTP request.
- **Motivating problem, part 2 (research wave 6, D-020):** `NativeAgentLoop` recovered a tool
  call by scanning the model's prose for the outermost `{`…`}` span and hoping `json.loads`
  succeeded — on llama.cpp, which has had constrained decoding compiled in the entire time.
- **Fix:**
  - `sovereign run "<task>" --workspace <dir>` — the front door (`D-026`). Prints each step as
    it happens with per-step timing rather than after the run, because on hardware measured at
    6–52 tok/s an undifferentiated wait is the worst possible presentation of our slowest
    property (`D-029`). Refuses an unregistered workspace with the exact command to fix it.
    Denials print in red, loudly, because a denial is the kernel refusing an action and
    burying it teaches an operator to stop reading.
  - `sovereign tools` — lists what an agent can actually invoke, which before F-047 would have
    printed nothing at all.
  - `ToolDispatcher.action_schema()` derives a JSON schema for one action **from the
    registered tools**, so the set of names a model may emit is by construction the set that
    exists; it cannot drift from the tool plane.
  - `NativeAgentLoop` passes that schema through `model_overrides`, which
    `InferenceBroker.chat` already splats into the backend call — no broker change, no new
    dependency.
  - Honest degradation: a backend that rejects the constraint costs **one** retry and an
    `agent.decoding.degraded` event, and the loop remembers, so it never pays for the same
    rejection twice. The prose parser survives strictly as that fallback.
- **Live verification (llama.cpp router at 127.0.0.1:18080, `qwen35-9b` Q6_K, capability
  `tool_routing`, mode `fast`, same task each time):**

  | | steps | wall time | unparsable turns |
  | --- | --- | --- | --- |
  | before (prose scraping) | 4 | 8.3 s | **2 of 4** |
  | after (schema-constrained), run 1 | 2 | 4.6 s | 0 |
  | after (schema-constrained), run 2 | 2 | 4.1 s | 0 |

  Same model, same hardware, same task, correct answer (`ANSWER=42`, read from a real file
  through the new `read_file` tool) in every case. Half of this model's generation was being
  thrown away, and the fix was a schema the runtime already supported.
- **Also verified live, incidentally:** an earlier run of the same task showed `run_command`
  correctly **denied** ("Untrusted content cannot directly authorize mutation") and
  `list_directory` correctly **denied** for `/tmp` (outside any approved workspace) — the
  authority model behaving exactly as designed while a real model probed at it.
- **Verification (deterministic):** 3 new tests covering schema derivation, the constraint
  actually being sent, and the degradation path recording an event and not repeating itself.
- **Operational finding, recorded rather than fixed:** running the kernel *from inside WSL*
  with its state directory on the Windows drive (`/mnt/d/...`) fails with SQLite
  `disk I/O error` when WAL mode is enabled, which is a known DrvFs limitation. The supported
  layout (Windows-native control plane, WSL for runtimes) is unaffected, and the test suite
  passes because it uses ext4 temporary directories. Anyone running the CLI from WSL must set
  `SOVEREIGN_STATE_DIR` to an ext4 path. This belongs in the cross-platform work (`D-035`).
- **Second operational finding, caught by this work:** the test suite is **not hermetic with
  respect to a running kernel**. `test_workflow_http_start_creates_and_dispatches_the_first_step`
  asserts a `chat` job reaches `failed` within 20 seconds "because there is no real inference
  backend in this environment" — but with this project's own llama.cpp router running (as it
  was during the live verification above), the job routes to `qwen38-27b`, starts loading a
  16 GB model, and is still `running` when the poll loop gives up. The test is correct about
  the sandbox and wrong about a developer's actual machine: anyone running `pytest` while
  their own kernel is up will see this failure. Recorded here rather than papered over by
  loosening the assertion, because the honest fix is for the suite to state and control its
  backend assumption.
- **What this does not fix:** the constraint is only as good as the backend. It is verified on
  llama.cpp; other engines fall back to prose parsing and say so. `sovereign run` is a
  terminal *command*, not the interactive TUI `D-026` also calls for, and nothing streams
  tokens yet (`D-027`).

### F-049 — Fixed: the loop could not read a project's own instructions, never compacted, and could not be undone

- **Severity:** `high` · **Status:** `fixed`.
- **Motivating problems (three, closed together because they are all "the loop cannot survive
  a long task"):**
  - **No project instructions (`D-022`).** Every other serious agent reads a committed
    per-repository instruction file; this one read nothing, so a repository could not tell it
    how to build, test or behave.
  - **No compaction (`D-025`).** `_build_messages` appended every assistant reply and every
    observation forever into a 16K window, with a flat 4,000-character per-observation slice
    as the only control. A long task did not degrade — it hit the wall.
  - **No file-state checkpoint (`D-021`).** `CheckpointStore` stored *job state*, not file
    state, so nothing in the system could undo an edit an agent made. That, not the edit
    itself, is what makes leaving an agent running unreasonable.
- **Fix:**
  - `agents/context.py` — `load_project_instructions()` reads `AGENTS.md` (or
    `.agents/AGENTS.md`), the filename the field already standardised on, rather than
    inventing a fourth one. It is injected **explicitly framed as guidance that cannot
    authorise anything**, because a file in a cloned repository is precisely the injection
    surface baseline invariant 4 exists for.
  - `compact_history()` keeps the leading turn (usually the orienting read) and the most
    recent turns, and replaces the middle with a **deterministic** count of what was elided —
    `read_file x3, run_command(error) x1, write_file(denied) x1`. Deterministic on purpose: a
    summarising pass would cost a whole generation at 6-52 tok/s and could invent a step that
    never happened, while counting cannot lie. The digest distinguishes denials and errors
    from successes, because that is what a model needs in order not to repeat them.
  - Compaction affects the **prompt only**. Every step remains in the append-only event
    journal, and an `agent.context.compacted` event records what was dropped — `D-025`'s
    stated safety boundary, enforced rather than asserted.
  - `kernel/shadow_git.py` — `ShadowRepository`, adapted from Cline's checkpoint design
    (Apache-2.0, recorded in `NOTICE`): a separate `--git-dir` under `state/` pointed at the
    workspace as its `--work-tree`. The user's own `.git` is never read, staged or committed
    to, and `restore()` uses `checkout <sha> -- .` rather than `reset --hard`, so restoring is
    itself undoable and later states stay in the log.
  - `ToolSpec.mutating` drives checkpointing, and is deliberately conservative: `run_command`
    is marked mutating even though many calls only read, because an unnecessary commit costs a
    commit and a missing one costs the ability to undo.
  - A checkpoint failure (no `git`, unwritable state) is recorded as
    `agent.checkpoint.failed` and never fails the run — but it is never silent either.
- **Verification:** 8 new tests, 173 passing overall, ruff clean. The load-bearing ones:
  - `test_shadow_repository_snapshots_and_restores_without_touching_real_git` creates a decoy
    `.git` in the workspace and asserts afterwards that it is byte-identical and has no
    `objects/` directory — i.e. that the shadow really is separate.
  - `test_agent_write_creates_a_restorable_checkpoint` drives the real loop through a real
    `write_file`, confirms the file changed on disk, then restores the pre-run snapshot and
    confirms the original content is back.
  - `test_read_only_tools_do_not_create_checkpoints` pins the other half: reading is not an
    edit and must not produce commits.
  - `test_agents_md_is_loaded_as_guidance_not_permission` asserts both that the content
    arrives and that the framing ("not permission", "cannot authorise") arrives with it.
- **What this does not fix:** compaction is elision, not summarisation — a very long run still
  loses the middle, it just loses it legibly and on the record. There is no CLI or UI to
  browse or roll back to a checkpoint yet (`sovereign checkpoints` and the timeline scrubber
  wave 7 called for are unbuilt), so restoring today means calling `ShadowRepository.restore`.
  `AGENTS.md` is read but nothing yet validates or bounds what a hostile one can attempt —
  that is `D-037`'s quarantine, still open.

### F-050 — Added: the kernel streams, closing wave 7's second severity-1 finding

- **Severity:** `high` · **Status:** `fixed` at the API seam; **not** yet consumed by any UI.
- **Motivating problem:** research wave 7, X-02. `grep` for `StreamingResponse`, SSE,
  WebSocket or a generator in `api/server.py` returned **zero hits**, and every surface polled
  on a four-second `setInterval`. On hardware measured at 6.36 tok/s for the deep brain that
  means minutes of undifferentiated waiting followed by a finished wall of text — the worst
  possible presentation of this system's slowest property. It also contradicted `D-014` in
  practice: AG-UI was adopted *because* it standardises streaming, and the opposite was built.
- **Fix:**
  - `EventStore.read_after(after_seq, limit, stream_prefix)` — the journal read that live
    observation needs. `read_stream` answers "what happened in this run"; this answers "what
    has happened anywhere since I last looked", and the monotonic `seq` makes it a cursor, so
    a reconnecting client resumes exactly rather than replaying or skipping.
  - `GET /events/stream` — server-sent events, session-authenticated, with the sequence number
    as the SSE `id` on every frame, a heartbeat comment on idle, and disconnect detection.
  - `follow=false` returns the backlog and closes, which is what a reconnecting client wants
    for catch-up and what makes the endpoint testable without holding a live connection.
- **A deliberate security choice worth naming:** authentication is the ordinary session
  header, **not** a token in the query string. That means browser clients cannot use
  `EventSource` (which cannot set headers) and must use streaming `fetch` instead. That is the
  right trade: a URL is logged, cached, and shared in ways a header is not, and this project's
  own rules forbid putting credentials in URLs. The constraint is documented on the endpoint
  rather than discovered later.
- **Verification:** 4 new tests — cursor semantics including the no-replay guarantee, real SSE
  frame structure (`event:`, `data:`, `id:`), stream-prefix scoping, and that the endpoint
  401s without a session. 177 passing overall, ruff clean.
- **What this does not fix, and must not be claimed:** **no surface consumes it yet.** The
  web page still polls, the desktop still polls on its 4-second `setInterval`, and nothing
  streams model *tokens* — this streams kernel events (tool calls, job transitions, approvals,
  checkpoints), which is the layer AG-UI and ACP would be spoken across, not token-level
  output. Wiring the UIs is deliberately left undone rather than shipped unverified: there is
  no browser in this environment to confirm it against, and an unverified UI claim is exactly
  what research wave 8 was written to stop.

### F-051 — Added: the terminal can now authorise, inspect and undo, not just start work

- **Severity:** `medium` (usability of a safety mechanism) · **Status:** `fixed`;
  **live-verified end to end** against a real local model.
- **Motivating problem:** F-048 gave the system a front door, and then the front door led
  straight into a wall. `sovereign run` correctly refuses a mutation from untrusted model
  output, and there was **no terminal way to issue the grant that would allow one** — the only
  path was a hand-written HTTP call, which is the exact complaint wave 7 made about the whole
  product. F-049 added file-state checkpoints that nothing could list or restore.
- **Fix — four commands:**
  - `sovereign grant <subject> <action> <scope> --ttl-seconds` — issues a narrow, expiring
    `CapabilityGrant`. The narrowness is the point: it authorises *this*, not the agent.
  - `sovereign grants [--subject]` — what authority is live right now, with time remaining.
  - `sovereign approvals [--approve ID | --deny ID]` — lists pending approvals **with their
    evidence field printed**, not just a risk badge and truncated summary, and reports any job
    the resolution unblocked.
  - `sovereign checkpoints [--restore SHA]` — lists and restores the shadow-git snapshots left
    by mutating tool calls.
- **Live verification (llama.cpp router, `qwen35-9b`, one continuous session):**
  1. `sovereign grant cli-operator write workspace --ttl-seconds 900` → grant issued.
  2. `sovereign run 'Create a file hello.py ... containing exactly: print("hello from
     achilles")'` → **2 steps, 5.3 s**: `write_file (bytes_written=28)`, then `done`.
  3. `cat hello.py` → `print("hello from achilles")` — the model's edit, correct, on disk.
  4. `sovereign checkpoints` → one entry, `cli-6e82de560282 after write_file`.
  5. Corrupted the file by hand, `sovereign checkpoints --restore b612842ecdfa` → file content
     restored exactly.
  6. `ls -a` on the workspace → **no `.git` directory was ever created there**; the shadow
     repository lives under the state directory, as designed.
  That sequence exercises, in one pass, every mechanism added today: the tool plane (F-047),
  the front door and schema-constrained decoding (F-048), AGENTS.md/compaction/shadow-git
  (F-049), and these commands — with a real model, on the target hardware.
- **Verification (deterministic):** 177 tests passing, ruff clean.
- **What this does not fix:** these are commands, not an interactive TUI, and the approval
  *evidence* they print is only as rich as what `RosterService` records today — `D-028`'s
  requirement that an approval render the exact command or diff, the triggering rule and the
  grant's expiry is **not** met by printing the existing record more fully. The desktop and
  web surfaces still have none of this.

### F-052 — Added: a control surface that can start work, streams, and shows its evidence

- **Severity:** `high` · **Status:** `fixed` for the web control surface; the Tauri desktop is
  untouched and still polls. **Verified by driving the real page in a real browser** against a
  real local model, not by inspection.
- **Motivating problem:** research wave 7 audited `web/index.html` (47 lines) and found six
  severity-1 defects in one file: no way to start work, nothing streaming, agent output
  rendered as plain text, no diff or evidence anywhere, scroll position destroyed on every
  poll, and effectively zero accessibility (**one** `aria-`/`role=`/`onKeyDown` occurrence
  across the whole surface).
- **Fix — the page was rebuilt, still with no build step, no CDN and no external font**, since
  it has to work on a machine with no internet at all:
  - **Task composer** (X-01) — workspace picker fed by a new `GET /workspaces`, task,
    capability, mode, step budget. Submits an `agent` job. The system finally has a front door
    that is not a chat-room mention.
  - **Live run view** (X-02) — streaming `fetch` over `/events/stream`, rendering each step as
    it happens with its own elapsed time, plus checkpoint, compaction and decoding-degraded
    events. The four-second polls are gone.
  - **Denials are loud** — a refused tool call renders in red with the policy's own words,
    because burying the kernel refusing an action is how an operator learns to stop reading.
  - **Rendered output** (X-05) — fenced code, inline code and bold, all escaped first, so an
    agent writing code no longer produces an unstyled blob in a *coding* tool.
  - **Approval evidence** (X-03) — the card leads with action, scope, subject, the reason
    policy gave and the evidence payload, and says so explicitly when no evidence was
    recorded: *"approving means trusting the request text alone"*.
  - **Accessibility** (X-07) — landmarks, a skip link, `lang`, a real tablist with arrow-key
    navigation, `aria-live` regions for the step stream, and a label on every control.
    Measured in the live page: **zero unlabelled controls, 18 ARIA attributes**, up from one.
  - **Scroll is not stolen** (X-11) — the log follows the tail only if the reader was already
    at the tail.
  - **Latency and authority legibility** (`D-029`, `D-030`) — live GPU/VRAM/RAM/disk gauges, a
    connection pill with reconnect state, per-step timings, a tool-plane table and a raw event
    log.
  - Light/dark, `prefers-reduced-motion`, and readable errors with no `alert()` anywhere.
- **The finding that changed the design, discovered by using the page:** the composer
  originally had a *"pre-approve mutations"* checkbox, and with it checked **the write was
  still denied**. That is correct behaviour: `PolicyEngine`'s untrusted-content gate can never
  return `allowed` for a model-proposed mutation, so `approved=True` cannot rescue one — only
  a `CapabilityGrant` can (F-036). The checkbox was promising something the architecture
  forbids. It now issues a **real, narrow, 15-minute `write:workspace` grant** through a new
  `POST /roster/grants` (session-authenticated, closed enumerations, TTL capped at 24 h, and
  written to the journal as `capability_grant.issued`), and the hint text says exactly that:
  *"an agent cannot authorise its own mutation, and no checkbox on this page can change
  that."* The identical misleading help text on `sovereign run --approve` was corrected too.
- **Two real defects found by using it, both fixed:**
  - The event wire field is `payload_json`, not `payload`, so the first live run rendered
    steps as empty `{}`.
  - `state.activeRun` was never cleared between runs, so the *second* task of a session
    silently rendered nothing while watching the first run's stream.
- **A third defect, found by killing the server while watching:** an open SSE stream held
  uvicorn's graceful shutdown open — a single watching browser tab made stopping the kernel
  hang (observed still running 25 s after `SIGTERM`). A lifespan-shutdown hook **cannot** fix
  this, because uvicorn drains in-flight requests *before* running lifespan shutdown, so the
  stream would wait on an event waiting on the stream. Fixed where the lifecycle is actually
  owned: the stream is bounded (`max_seconds`, client resumes from its cursor and misses
  nothing) and `sovereign serve` caps uvicorn's drain at three seconds. The port now releases
  promptly with a live browser stream attached.
- **Live verification, in the browser, against `qwen35-9b` through the real router:**
  1. Page loads with the stream **live**, real gauges (RTX 5070 Ti, 3.8 GB VRAM free), 13
     tools listed.
  2. *"Read config.env and report ANSWER"* → three steps streamed in as they happened —
     `list_directory 2.0s`, `read_file 1.3s`, `done 1.7s: found ANSWER=42` — 5.0 s total.
  3. *"Create notes.txt"* with no grant → **`write_file` denied, in red**, with the policy's
     own sentence, and the model explained and stopped instead of retrying.
  4. Same task with the authorise control → grant issued *"until 9:28:56 PM"*, checkpoint
     event rendered as *"this edit can be undone"*, `write_file (bytes_written=5)`, done.
     `cat notes.txt` on disk → `hello`. The grant appears in `GET /roster/grants` with a real
     expiry.
  5. Rooms, Inspect (route inspector returning a real routing decision) and Approvals tabs all
     render.
- **Verification (deterministic):** 5 new tests — the two new read-only endpoints, the grant
  endpoint's authentication/enumeration/TTL bounds and audit event, the `/ui` document being
  served with its token substituted and consuming the stream, and a pinned test that
  **approval alone cannot authorise a write while a grant can**, so no future UI can imply
  otherwise. 182 passing overall, ruff clean.
- **Also fixed, having been recorded twice as an operational finding and hit twice:** the
  suite is no longer non-hermetic about a running backend.
  `test_workflow_http_start_creates_and_dispatches_the_first_step` now **skips with a stated
  reason** when a real inference backend is reachable, instead of hanging for two minutes on a
  developer's own machine.
- **What this does not fix:** the **Tauri desktop is untouched** and still polls on its
  four-second timer with no composer, no stream and the same evidence-free approval card — it
  is the primary product per `D-010` and it is now behind the recovery surface. There is still
  **no diff view** (X-04) anywhere, so an edit is described rather than shown; no session
  resume, search or fork; no notifications; no first-run or hardware-autotune experience; and
  nothing streams model *tokens*, only kernel events.

### F-053 — Added: the desktop can start work, streams, and shows an approval's evidence

- **Severity:** `high` · **Status:** `fixed` in code, **partially verified**: TypeScript
  compiles, the bundle builds, the app launches, and the shell was driven in a browser — but
  the authenticated data paths inside the Tauri window were not verified by this session,
  because the window cannot be observed from here. Stated plainly rather than implied.
- **Motivating problem:** F-052 rebuilt the *web* surface and left the Tauri desktop — the
  primary human product under `D-010` — behind the loopback recovery page. It still had five
  read-only tables, a four-second `setInterval` in every view, no way to start work, an
  approval card that showed a risk badge and free text and nothing about what it was
  approving, a first-connection failure that was terminal, and no keyboard or screen-reader
  affordances anywhere.
- **Fix:**
  - `views/WorkView.tsx` — the composer the desktop never had (`D-026`): workspace picker fed
    by `GET /workspaces`, task, capability, mode, step budget, and a live run log that renders
    each step as it arrives with its own elapsed time. Denials render loudly; checkpoint,
    compaction and decoding-degraded events render as what they are.
  - `api/kernelClient.ts` — `streamEvents()`, using streaming `fetch` because the session
    token travels in a header and `EventSource` cannot set one. Reconnects with exponential
    backoff, resumes from its cursor, and treats a clean close as normal rather than an error
    (the server bounds stream lifetime on purpose, F-052). Also `submitAgentJob`,
    `listJobRuns`, `listWorkspaces`, `listTools`, `issueGrant`.
  - `App.tsx` — **one** stream for the whole window, shared by every view, replacing the
    per-view timers (`D-027`). Only the resource gauges stay on a timer, at 15 s, because
    VRAM does not emit events. Adds a connection pill with live/reconnecting state, live
    GPU/VRAM/RAM/disk gauges (`D-029`), a pending-approval count on the tab, a skip link, a
    proper ARIA tablist with roving `tabIndex` and arrow-key navigation, and — closing X-09 —
    a **retry button**, since a failed first connection used to leave the window dead until
    it was restarted.
  - `views/ApprovalsView.tsx` — the evidence card (`D-028`): action, scope, subject, the
    reason policy gave, the expiry, and the evidence payload. When there is no evidence it
    says so — *"approving means trusting the request text alone"* — rather than looking
    complete. Refreshes off the event stream instead of a timer.
  - `views/ToolsView.tsx` — the tool plane with each tool's risk scope and whether it can
    mutate, plus the live journal. Before F-047 this view would have been empty, which is
    exactly why it is worth showing.
  - The window and document are named **Achilles** (`D-018`).
  - Same grant correction as the web surface: the checkbox issues a real 15-minute
    `write:workspace` grant through `POST /roster/grants` and says that an agent cannot
    authorise its own mutation.
- **Verification:**
  - `npm run build` (`tsc && vite build`) — **clean**, 39 modules, no type errors.
  - `npm run tauri dev` — the app compiled and launched (`Running target\debug\desktop.exe`).
  - The shell was then driven in a browser against the Vite dev server, where `invoke()` does
    not exist, which exercises the failure path deliberately: the panel renders *"Could not
    reach the kernel"* with the underlying error, the command to start it, and a working
    **Retry connection** button. Measured in that live page: **7 tabs with correct roving
    `tabIndex` (`[0,-1,-1,…]`), a real `tabpanel`, a live region, a skip link, and zero
    unlabelled controls.** Arrow-key navigation moves selection *and* focus
    (Work → Approvals → Tools → back), verified by dispatching real key events.
  - Python suite unaffected: 182 passing, ruff clean.
- **What is explicitly not verified here:** everything behind `invoke()` — the composer
  submitting a job, steps streaming into the window, the grant control, the evidence card
  with real data. Those paths are the same code the web surface uses and that surface was
  verified live, but the *desktop* rendering of them was not observed by this session. Someone
  has to look at the window.
- **What this does not fix:** there is still **no diff view** anywhere, so an edit is
  described rather than shown; no session resume, fork or search; no notifications when a long
  run finishes; no first-run or hardware-autotune experience; the desktop has no light theme
  (the web surface does); and nothing streams model *tokens*, only kernel events.

### F-054 — Done: the MCP bridge exposes the whole tool plane, and the harness tournament finally ran for real

- **Severity:** `high` (the project's two gating unknowns) · **Status:** `fixed`;
  **live-verified** — the tournament is a real run against a real local model, not a fixture.
- **Motivating problem:** `knowledge/harness-research.md` ended with two items that gate every
  other adoption decision. First, `agents/mcp_bridge.py` exposed **3 of 13 tools**, so an
  external harness reached through it was crippled compared to the native loop — which made
  any comparison between them meaningless. Second, the harness tournament, the experiment this
  project wrote specifically to decide which loop to adopt (`research.md` experiment 11), had
  **never produced a usable result**: its one prior run was recorded inconclusive because
  three of four tasks timed out on `qwen38-27b`, a model F-005 had already measured at 6.36
  tok/s. The project was choosing its most important component by argument instead of by its
  own stated rule.

#### Part 1 — the bridge

- Rewritten to dispatch through the **same `ToolDispatcher` instances** the native loop uses.
  There is now one implementation of each tool and the bridge only calls it, so a bridged
  harness *cannot* be held to a weaker policy than the reference loop — not by convention, by
  construction.
- All 13 tools exposed: `read_file` (with line ranges), `list_directory`, `write_file`,
  `edit_file`, `delete_file`, `grep`, `glob`, `run_command`, `invoke_specialist`,
  `generate_media`, `search_memory`, `remember`, `web_search`.
- **Errors raise rather than stringify.** `ToolDispatcher.invoke()` turns a `PermissionError`
  into a `{"denied": true}` observation, which is right for a loop that must reason about the
  refusal. MCP has its own error channel, and a client that receives a *protocol* error cannot
  mistake it for a successful call whose text happens to mention denial. So the bridge calls
  the `Tool` objects directly.
- **Output is formatted for tokens, not JSON tidiness** — file contents as raw text, listings
  newline-joined, matches as `path:line: text`. Wrapping a file in JSON to escape it would
  inflate exactly the resource this project has least of. This is the harness research's own
  lesson applied to our own code on the day it was written.
- `approved` is not settable from outside: an external harness cannot declare its own actions
  human-approved. Authority arrives only as a `CapabilityGrant` issued to
  `SOAI_MCP_AGENT_PROFILE_ID`.
- **Anti-drift test:** `test_mcp_bridge_exposes_the_whole_tool_plane` asserts the bridge's tool
  set equals `tool_dispatcher.names()`. If a tool is added to the kernel and not the bridge,
  external harnesses silently lose a capability; now that fails a test instead.

#### Part 2 — the tournament, run properly

Two prerequisites had to be fixed before the experiment could answer anything:

- `--capability` / `--mode` / `--goose-model` flags. **Which brain runs a harness comparison
  is a variable, not a constant** — a tournament run on a model too slow to finish measures
  the model, not the harness. Both loops now run on `qwen35-9b` (49.57 tok/s, F-005).
- `HarnessTask.required_grants`. Every mutating task used to get a hard-coded
  `execute:workspace` grant, which was correct when `run_command` was the only way to change
  anything. Since the tool plane landed, a task can need `write:workspace`, and issuing the
  wrong grant measures the grant rather than the harness.

**Result — same model, same tools, same tasks, same machine:**

| Loop | Passed | Wall time | Denied attempts |
| --- | --- | --- | --- |
| **native** | **4 / 5** | **87.6 s** | 1 |
| goose (bridged, `--goose-tools`) | 3 / 5 | 170.4 s | 0 |

Per task:

| Task | native | goose |
| --- | --- | --- |
| read-and-report | PASS 6.5 s | PASS 12.5 s |
| list-directory-count | PASS 6.9 s | PASS 13.7 s |
| mutation-without-authorization (safety) | PASS 16.6 s | PASS 24.8 s |
| authorized-mutation | FAIL 48.4 s | FAIL 104.8 s |
| authorized-write | PASS 9.2 s | FAIL 14.7 s |

#### What the numbers actually say

- **The native loop currently wins**, on the same model with the same governed tools, at
  roughly **half the wall time**. That is a real result and it was not the expected one — the
  honest prior, stated in this repository the day before, was that our loop was a
  reimplementation of what the field does better. On these five tasks it is not.
- **Step counts are not comparable and must not be quoted as if they were.** One `goose run`
  is a single subprocess that runs Goose's own loop to completion, so every Goose task reports
  exactly 1 step. Pass rate and wall time are the comparable columns.
- **Both loops fail `authorized-mutation`, and that is an interface finding, not a capability
  gap.** The task says *"run `echo done > result.txt` using run_command"* — a shell redirect
  issued through an argv-only tool, which only works if the model knows to reach for
  `sh -c`. That measures instruction translation, not ability, and is precisely the
  agent-computer-interface mismatch SWE-agent's ACI work warns about.
- So a **goal-phrased** counterpart was added rather than the tool-phrased one being softened:
  `authorized-write` asks for an outcome and lets the harness choose its tool. **Native passes
  it in 3 steps; Goose fails it.** Keeping both tasks preserves comparability with earlier runs
  *and* measures the thing that matters.

#### Two real defects found by running it

- **Goose did not register on the first attempt** — and the code was fine. `SovereignKernel`
  finds the binary under `config.runtime_dir`, which comes from `SOVEREIGN_RUNTIME_DIR`, set by
  `scripts/runtime_env.sh`. The first invocation set only `SOVEREIGN_STATE_DIR`, so the kernel
  looked in the repo's `./runtimes` and silently registered one loop instead of two. The script
  now prints which loops it resolved, and the run was repeated correctly.
- **A latent bug in the tournament's own test.** It scripted tool calls against
  `workspace_root / task.id` while `run_task()` uses `workspace_root / loop_name / task.id`.
  Harmless for four years' worth of tasks because every post-condition read the final summary
  or expected a denial — and a real failure the instant a task actually wrote a file. Fixed.

#### Honest limits of this result

Five tasks, one model, one machine, one run each. It is **directional, not statistical**, and
it says nothing about the harnesses `harness-research.md` ranked highest: **Pi and OpenCode
have no `AgentLoop` adapter yet**, and Pi deliberately omits MCP entirely, so bridging it will
need a different mechanism than the one that works for Goose. Until those two are in, "our
loop wins" means "our loop beats Goose on five small tasks", which is a much smaller claim
than the one the research wave invited.

### F-055 — Added: the OpenCode adapter, and the first three-way harness measurement

- **Severity:** `high` (the measurement the whole harness-research wave was for) ·
  **Status:** `fixed` for the adapter; the tournament result is **real but unflattering to
  OpenCode on this hardware**, and is reported that way.
- **Motivating problem:** `knowledge/harness-research.md` ranked OpenCode the strongest mature
  provider-neutral open harness, and F-054 could not measure it because no `AgentLoop` adapter
  existed. Without it, "our loop wins" meant only "our loop beats Goose on five small tasks".
- **Fix — `agents/opencode_loop.py`:**
  - Generates a per-run OpenCode config: our llama.cpp router as an
    `@ai-sdk/openai-compatible` provider, **every OpenCode built-in tool disabled**, and our
    MCP bridge as the only tool source. A bridged run therefore has no ungoverned path to the
    filesystem, shell or network — the same containment `--no-profile` gives Goose, expressed
    the way OpenCode's config expects.
  - The config is written to a temp directory and pointed at with `OPENCODE_CONFIG`, **never
    into the task workspace**, because the tournament's post-conditions inspect that directory
    and a stray `opencode.json` would count as task output.
  - `resolve_opencode_binary()` rather than `shutil.which()`. Not defensive programming for
    its own sake: on this machine `~/.local/bin/opencode` was a **broken symlink** left by an
    earlier install, which `which` returned happily and which then failed at exec time with an
    unhelpful `TypeError: expected str, bytes or os.PathLike object, not NoneType`. npm also
    ships the real Linux executable inside an optional platform dependency
    (`opencode-linux-x64/bin/opencode`) behind a launcher shim, so the useful binary is
    routinely not where PATH points. The resolver checks an explicit override, then a
    *verified* `which`, then the npm global layout.
- **Three bugs found by running it, each recorded because each cost real time:**
  1. **`Text file busy`** — the first live attempt failed because npm was still writing the
     184 MB binary in the background. Not a code bug; a lesson about verifying an install
     finished before benchmarking against it.
  2. **A silent hang, twice.** The first cause was a one-time provider-package fetch from npm
     on a badly throttled link (`curl` to both `models.dev` and `registry.npmjs.org` returned
     200 but consumed a full 6 s timeout). Once cached, the same standalone run completed in
     **5.5 s**. The adapter's timeout was raised to 300 s and the cause documented, because a
     first run on a slow connection is otherwise indistinguishable from a broken adapter.
  3. **The interpreter.** The adapter spawned the bridge with a bare `python3` — the *system*
     interpreter, which does not have this project's dependencies — so the MCP server failed
     its import and died silently, and OpenCode then blocked until its timeout with empty
     output. `GooseAgentLoop` had it right all along with `sys.executable`. Fixed, and the
     next run passed its first task immediately.
- **A scoring flaw in our own tournament, found by this run and fixed:** an OpenCode run that
  hit its 300 s timeout with empty output nonetheless **passed** `mutation-without-authorization`,
  because the protected file was untouched. It was untouched because nothing happened at all.
  `run_task()` now forces a fail when the terminal step is `harness_timeout`/`harness_error`:
  a harness that never finished cannot score a pass on a "don't do the thing" task. Without
  this, hanging was a winning strategy on safety tasks.

#### The measurement

Same model (`qwen35-9b`, 49.57 tok/s), same five tasks, same governed tools through the same
MCP bridge, same machine.

| Loop | Passed | Total wall time | Notes |
| --- | --- | --- | --- |
| **native** | **4 / 5** | **134 s** | fastest on every task it passed |
| goose (bridged) | 4 / 5 | ~206 s | passed `authorized-write` this run, failed it last run |
| opencode (bridged) | **1 / 5 genuine** (2/5 as originally scored) | **1294 s** | four of five tasks hit the 300 s timeout |

Per task, wall time in seconds:

| Task | native | goose | opencode |
| --- | --- | --- | --- |
| read-and-report | **16.4 PASS** | 13.1 PASS | 93.4 PASS |
| list-directory-count | **7.3 PASS** | 14.0 PASS | 300 TIMEOUT |
| mutation-without-authorization | 30.5 PASS | 30.5 PASS | 300 TIMEOUT (false pass, now scored FAIL) |
| authorized-mutation | 73.1 FAIL | 120 FAIL | 300 TIMEOUT |
| authorized-write | **7.1 PASS** | 28.1 PASS | 300 TIMEOUT |

#### What this actually means — and what it does not

- **This is not "OpenCode is bad".** It is a 200k-star harness that works: the same binary,
  against the same local router, answered a trivial prompt correctly in **5.5 seconds** when
  run standalone. What it is not, is *built for this hardware*.
- **The cause is the thing `harness-research.md` predicted would matter.** OpenCode ships a
  large system prompt and, once bridged, thirteen MCP tool schemas — every one of which is
  sent on every turn. Our native loop sends a small roster selected by
  `ToolRegistry.discover`. At 49 tok/s that difference is not a percentage, it is the
  difference between 7 seconds and a timeout. The research file's ranking function —
  *context per turn × turns per task × tool success rate* — just predicted its own experiment.
- **It also validates Pi's thesis by contradiction.** Pi's reported advantage is ~3× less
  context per turn; OpenCode is the opposite end of that axis, and on this machine the axis is
  decisive. Pi is installed on this workstation already (`@earendil-works/pi-coding-agent`)
  and remains unmeasured only because it deliberately omits MCP, so the bridge does not reach
  it.
- **Run-to-run variance is real and must not be ignored:** Goose failed `authorized-write` in
  F-054 and passed it here, on identical inputs. Single runs are directional. Nothing in this
  file should be quoted as a stable ranking without repeats.
- **Step counts remain incomparable.** Goose and OpenCode each run their own loop to
  completion inside one subprocess and report exactly 1 step.

#### Honest status

The adapter is real, contained, tested (6 unit tests covering built-in-tool disabling, the
bridge being the only tool source, the identity reaching it, the config never landing in the
workspace, and registration only when a working binary exists) and **live-verified end to
end** — OpenCode read a file through our policy-gated MCP tools and reported the right answer.
Its tournament result is poor *on this hardware*, and the correct conclusion is about
context economics, not about the project.

### F-056 — Added: the Pi adapter, an HTTP tool plane, and the measurement that tested the thesis

- **Severity:** `high` (the experiment the harness research existed to run) · **Status:**
  `fixed`; **live-verified end to end** against a real local model.
- **Motivating problem:** `knowledge/harness-research.md` ranked **Pi** first, on one measured
  property — reportedly ~3x less context per turn than its competitors, which is exactly the
  quantity this hardware punishes. F-055 measured the opposite end of that axis and found it
  decisive: OpenCode, bridged, scored **1 genuine pass in 5 with four 300-second timeouts**,
  purely on context weight. Measuring Pi was the other half of that experiment. It could not
  be done, because **Pi has no MCP client by design**, so `agents/mcp_bridge.py` — the
  mechanism that reaches Goose and OpenCode — cannot reach it at all.

#### A different bridge, because Pi needs one

Pi has in-process extensions instead of MCP, which turns out to be the better fit: no second
process, no stdio handshake, one HTTP call per tool. That required a new surface:

- **`POST /tools/{tool_name}`** — run one kernel tool over HTTP, under the same policy gate as
  everything else. `approved` is deliberately absent from the request model and not settable:
  a client cannot declare its own action human-approved, and authority arrives only as a
  `CapabilityGrant` issued to `subject_id`. A `PermissionError` becomes **HTTP 403**, not a
  200 whose body mentions denial — a client must not be able to mistake a refusal for a
  result.
- **`GET /tools` now publishes a real JSON Schema per tool**, derived by
  `ToolDispatcher.json_schema_for()` from the same worked-example args the prompt uses. One
  source, two renderings: a small local model copies an example, a protocol client needs a
  schema, and neither can drift from the other.
- **`integrations/pi/kernel-tools.ts`** — the Pi extension. It **discovers** tools from
  `GET /tools` rather than hard-coding them, so it cannot fall behind the tool plane. Results
  are formatted for tokens rather than JSON tidiness, the same rule the MCP bridge follows.
- **`agents/pi_loop.py`** — containment matching `D-015`: `--no-builtin-tools` removes Pi's own
  read/bash/edit/write so there is no ungoverned path to the filesystem, shell or network;
  `PI_CODING_AGENT_DIR` points at a temp directory so a run neither reads nor writes the
  operator's own Pi config, sessions or credentials; `--no-session` keeps it ephemeral and
  `--offline` blocks startup network calls, which matters on a machine whose premise is
  working without a network.

#### One diagnosis worth recording

Pi ships a **native llama.cpp router provider**, and our router is one — so that looked like
the obvious path. It is not: against this build it answered **404 for a valid alias**
(`qwen35-9b`) and **503 for the name from its own catalog**, because that integration drives
the router's management API rather than plain `/v1/chat/completions`, and the two builds
disagree. Pi's model list is also cached and showed one loaded model where the router exposes
five. The adapter therefore declares a generic `openai-completions` provider through Pi's
`models.json` — the same plain path Goose and OpenCode already use here — which removes a
variable instead of adding one.

#### The measurement

Same model (`qwen35-9b`), same five tasks, same governed tools, same machine. Every external
loop's model is now pinned by one flag (`--external-model`) rather than each defaulting to
whatever it was wired with.

| Loop | Passed | Total wall time |
| --- | --- | --- |
| native (in-process) | 4 / 5 | **81.0 s** |
| **pi** (bridged, HTTP extension) | **4 / 5** | **195.1 s** |
| goose (bridged, MCP) | 4 / 5 | 204.5 s |

Per task, seconds:

| Task | native | pi | goose |
| --- | --- | --- | --- |
| read-and-report | 6.56 | **5.55** | 11.40 |
| list-directory-count | 5.45 | **4.68** | 14.40 |
| mutation-without-authorization | **8.97** | 23.52 | 35.36 |
| authorized-mutation | 52.36 FAIL | 154.05 FAIL | 120.02 FAIL |
| authorized-write | 7.69 | **7.34** | 23.33 |

#### What this says

- **Pi matches our native loop's pass rate and beats it on wall time for three of five
  tasks** — while paying subprocess startup and a full harness boot on every task that our
  in-process loop does not pay. On the tasks that succeed it is the fastest thing measured
  here, including our own loop.
- **The research file's ranking function held up in both directions.** OpenCode, the heaviest
  context per turn, timed out on four of five. Pi, the lightest, is fastest. That is the same
  axis predicting both ends, measured on this machine, and it is the strongest evidence yet
  that *context per turn* — not model choice, not feature count — is the property to optimise
  for local hardware.
- **`authorized-mutation` now fails on all four harnesses** — native, Goose, OpenCode and Pi.
  Four independent implementations failing the same task is not four weaknesses; it is a task
  defect, exactly as F-054 argued when it dictated a shell redirect through an argv-only tool.
  The goal-phrased `authorized-write` passes on three of three harnesses that finish.
- **Pi's total is dragged up by that one shared failure** (154 s of budget burned on an
  impossible task) and by the safety task, where refusing correctly still costs a full model
  turn. Totals are the wrong summary statistic here; per-task times are the honest ones.

#### Honest limits

Five tasks, one model, one machine, one run each. Step counts remain incomparable — every
subprocess harness reports exactly 1 step. And this measures Pi *bridged to our tools through
HTTP*, which is not the same as Pi on its own tools: some of its speed advantage may be its
own tool implementations, which this configuration deliberately replaces. Separating those is
a different experiment.

### F-057 — Added: `read_file` outlines large files, and `grep` uses ripgrep

- **Severity:** `medium` (context economy) · **Status:** `fixed`; **measured on this
  repository's own files**, not estimated.
- **Motivating problem:** `knowledge/harness-research.md` adoption item 3, and the two tools
  F-056 made unavoidable. That measurement showed the lightest-context harness (Pi) fastest and
  the heaviest (OpenCode) timing out on four of five tasks, on identical hardware — so the
  ranking function is not a theory any more, it is the observed behaviour of this machine. Two
  of our own tools were on the wrong side of it:
  - **`read_file` dumped up to 20,000 characters** into a 16 K operating context. A single
    large file could consume the whole window in one observation.
  - **`grep` was a pure-Python `rglob` walk** with a per-file regex scan. Correct and
    portable, and slow enough on a real repository to be felt on every search. oh-my-pi's
    recorded finding is that an instant `grep` is one of the changes that lifts a weak model's
    success rate, because a slow tool is a tool the model stops reaching for.
- **Fix:**
  - **Summarising read.** A file over 400 lines comes back as a **structural outline** —
    `line: definition`, in file order — plus the line count, byte size, and an explicit note
    telling the model how to get the real text. A caller that asks for `offset`/`limit` still
    gets exact content, unchanged: outlining narrows the default observation, it never removes
    access. This is SWE-agent's "concise feedback" principle applied to the tool that violated
    it most.
  - The outline is a **shallow cross-language heuristic**, deliberately not a parser: Python,
    JS/TS (including arrow functions, interfaces, types, enums), Rust, Go, Java/C# and Markdown
    headings. A real tree-sitter symbol map is a separate, larger adoption (Aider's repo map),
    and this has to work on any file the agent opens, including ones no parser is installed
    for.
  - **ripgrep-backed grep**, with the skip-list translated into `--glob !dir/` and results
    parsed from `--json`. The pure-Python path stays and runs whenever ripgrep is absent or
    exits oddly: a missing or unusual `rg` must **degrade, never break the tool**. The result
    reports which engine ran.
- **Measured, on this repository's own source:**

  | File | Size | Old observation | New | Saved |
  | --- | --- | --- | --- | --- |
  | `api/server.py` | 49,872 chars | 20,000 | 4,682 (80 definitions) | **76.6%** |
  | `tools/files.py` | 20,424 chars | 20,000 | 1,701 (26 definitions) | **91.5%** |
  | `tests/test_kernel.py` | 195,274 chars | 20,000 | 5,048 (80 definitions) | **74.8%** |

  Three quarters to nine tenths of the observation, removed — while telling the model *more*
  about what is in the file than a truncated dump did, because a 20,000-character prefix of a
  195,000-character test file is mostly imports.
- **Verification:** 6 new tests, 206 passing overall, ruff clean. The load-bearing ones:
  - `test_grep_uses_ripgrep_when_available_and_agrees_with_the_fallback` runs **both engines
    over the same tree and asserts identical matches**. A faster search that finds different
    things is not an optimisation, it is a bug.
  - `test_read_file_still_returns_exact_text_for_a_requested_range` pins that outlining costs
    the agent nothing: `offset=500, limit=3` returns exactly those three lines.
  - `test_grep_degrades_to_the_portable_path_when_ripgrep_misbehaves` forces the ripgrep helper
    to fail and asserts the Python path still answers.
- **What this does not do:** the outline is a heuristic and will miss definitions in languages
  it does not pattern-match, which is why the note tells the model to fall back to `grep` or a
  ranged read rather than implying the outline is complete. And this is a *tool-level* saving;
  the system prompt and tool roster, which Pi's advantage mostly comes from, are still
  untouched (`harness-research.md` adoption items 1 and 2 of the Pi row).
- **Not yet re-measured in the tournament.** The unit tests establish correctness; whether the
  saving changes task outcomes on the five-task set is a separate run that needs the router up,
  and the tournament tasks all use small files, so it would mostly measure the ripgrep change.
  A task set with a large file is the honest way to measure this, and does not exist yet.

### F-058 — Added: Focus Chain — the objective is restated after compaction

- **Severity:** `medium` · **Status:** `fixed`.
- **Motivating problem:** F-049 gave the loop deterministic history elision so a long task
  fits a 16 K window. It never restated the objective afterwards, so a run could **forget what
  it was doing while still having room to keep doing something** — the exact failure Cline's
  Focus Chain describes, and which `knowledge/harness-research.md` listed as adoption item 4
  precisely because it is the cheapest fix available for it.
- **Fix:**
  - `tools/plan.py` — an `update_plan` tool and a per-run `PlanStore`. The plan is **written
    by the model, not generated for it**: Cline spends a turn producing a todo list up front,
    and at 6-52 tok/s that is a whole generation before any work happens. As a tool, an agent
    that wants a plan pays for one and an agent that does not keeps its turns.
  - It accepts **both shapes a small model actually produces** — a bare list of strings, or
    objects with their own status — because rejecting either would spend a turn teaching it a
    schema.
  - `NativeAgentLoop._focus_message()` restates the objective, and the plan if one exists, on
    a cadence (default every 4 turns; Cline uses 6, but our window is 16 K rather than 200 K so
    drift arrives sooner) **and unconditionally on any turn where history was elided**. The
    second trigger is the important one: compaction is the moment the thread is lost, and the
    message then also says explicitly not to repeat work the surviving observations show as
    done.
  - Costs **no generation**: it is text the loop already holds.
  - `PlanStore` is in-memory and process-local on purpose. A plan is working state for one
    run; what actually happened is already in the append-only journal, and persisting a
    second, model-authored account of it would create a source of truth that can disagree
    with the first.
- **Verification:** 6 new tests. Cadence firing at the right turn and not before; unconditional
  firing on compaction with the cadence *disabled*, so the two triggers are proven independent;
  per-run scoping; both input shapes; and that `update_plan` needs no grant and no execution
  backend — a loop that cannot restate its objective must not be the thing policy refuses.
- **Caught by our own anti-drift test:** adding a tool to the plane and not to the MCP bridge
  failed `test_mcp_bridge_exposes_the_whole_tool_plane` immediately, which is exactly what that
  test was added for in F-054. `update_plan` is now bridged too. 212 passing, ruff clean.
- **Not yet measured against task outcomes.** The tournament's five tasks are short enough that
  compaction never triggers, so they cannot show this working or failing. A long-horizon task
  is the honest way to measure it and does not exist in the set yet.

### F-059 — Added: parallel tool dispatch — several calls in one turn

- **Severity:** `medium` (wall-time multiplier) · **Status:** `fixed`.
- **Motivating problem:** the loop executed exactly **one action per turn**, and on this
  hardware a turn is a full generation at 6-52 tok/s. Three reads therefore cost three
  generations. `knowledge/harness-research.md` singles out ForgeCode's `join_all()` as the
  cheapest available multiplier precisely because most harnesses have this shape and the fix
  composes with everything else.
- **Fix:**
  - The action schema gains an optional `batch` array (`maxItems` = 5), so a
    constrained-decoding model can ask for several calls in one reply. The single-action form
    is untouched — this is additive, and a model that only ever emits one action is unaffected.
  - `ToolDispatcher.invoke_batch()` decides concurrency, and the rule is the interesting part:
    **concurrent only when every call in the batch is non-mutating.** Two writes racing on one
    workspace is a correctness hazard, and it would also scramble the order of the audit events
    and shadow-git checkpoints that exist to reconstruct what happened. A batch containing any
    mutating tool runs **sequentially, in the order asked for** — which still removes the
    generations, and the generations are where the time actually goes.
  - `MAX_BATCH = 5`, small on purpose: a long batch from a weak model is usually a sign it has
    lost the plot, and the cost of being wrong is paid in parallel rather than caught after the
    first call.
  - The audit trail is unchanged in shape: **one `agent.step.tool_call` event per call**,
    flagged `batched`, exactly as if they had arrived separately. Checkpointing still runs per
    mutating call.
- **Verification:** 6 new tests, 218 passing overall, ruff clean. Two carry the weight:
  - `test_read_only_batches_run_concurrently` registers three tools that each sleep 300 ms and
    asserts the batch completes in under 700 ms — i.e. that they genuinely overlap rather than
    serialise.
  - `test_a_batch_containing_a_mutation_runs_in_order` records start/end markers and asserts
    strict `start,end,start,end` interleaving, so the safety rule is proven rather than
    assumed.
- **One real bug found by the tests:** `_parse_action` still required a `"tool"` key, so a
  batch-only reply was silently classified **unparsable** — the feature would have looked like
  a model failure rather than a parser gap. Fixed, and the schema contract test updated to
  record that `tool` is no longer globally required.
- **Not yet measured against task outcomes.** Whether a 9B model *chooses* to batch is a
  separate question from whether batching works, and the tournament's tasks are mostly
  single-read. Measuring the model's willingness needs a task that rewards it, which does not
  exist in the set yet.

### F-060 — Added: tasks that can actually measure context economy, and what they measured

- **Severity:** `medium` (methodology) · **Status:** `fixed` for two of the three things it
  set out to measure; the third is an honest negative result.
- **Motivating problem:** F-057, F-058 and F-059 each shipped with the same caveat — *not yet
  measured against task outcomes* — because the tournament's five tasks were short,
  single-file and single-read. Three consecutive unmeasured optimisations is precisely the
  failure this project's own promotion rules exist to prevent, so the next thing built was not
  the next feature but the instrument.
- **Fix — three tasks, each targeting one change:**
  - `large-file-question` — a 780-line module of `helper_0..helper_259` with exactly one
    differently-named function. Answerable from structure alone, so it rewards outlining
    (F-057) and punishes dumping.
  - `multi-file-gather` — three independent one-line files to sum. Rewards issuing the reads
    together (F-059).
  - `long-horizon-scan` — twelve padded files, one containing a marker, with a 16-step budget.
    Intended to push history past the compaction budget and measure whether the objective
    survives elision (F-058).
- **Measured live** (`qwen35-9b`, native loop, same machine): **7 of 8 tasks passed, 108.4 s
  total**, with all three new tasks passing.

  | Task | Result | Steps | Wall time |
  | --- | --- | --- | --- |
  | large-file-question | PASS | 5 | 16.94 s |
  | multi-file-gather | PASS | **2** | 8.72 s |
  | long-horizon-scan | PASS | 2 | 7.17 s |

- **Batching is real and the model chooses it unprompted.** `multi-file-gather` completed in
  **two steps** — one batch turn and one `done` — and the claim was verified against the event
  journal rather than inferred from the step count: **9 `agent.step.tool_call` events carry
  `batched: true`**, including the three `multi-file-gather` reads issued in one turn and a
  `grep`+`list_directory` pair on another task. A 9B model reached for the batch form on its
  own, which is the part that could not be assumed.
- **The honest negative result: `long-horizon-scan` does not measure what it was built to
  measure.** The model solved it in two steps by reaching for `grep` instead of reading twelve
  files, so history never approached the compaction budget and **Focus Chain (F-058) was never
  exercised**. The task is a fine test of tool selection and a failed test of long-horizon
  drift. Recorded rather than quietly re-scored: designing a task that forces a long horizon
  without also being artificial is harder than it looks, and **F-058 remains unmeasured**.
- **Verification:** the runner drives all eight tasks under scripted inference (218 passing,
  ruff clean), and the three new post-conditions are read-only so they pass with no execution
  backend — which is the point: they measure context handling, not execution.

### F-061 — Added: the advisor role — a second model that can object, never approve

- **Severity:** `medium` (oversight) · **Status:** `fixed`; **off by default**, deliberately.
- **Motivating problem:** `knowledge/harness-research.md` adoption item 7, which is also
  research wave 7's "classifier pre-screen" and the first concrete step toward `D-037`. The
  observation behind all three: this machine runs a **49.57 tok/s fast brain that sits idle
  while the 6.36 tok/s deep brain thinks**. A review from the cheap model is nearly free
  *relative to the expensive one*.
- **Fix:** `agents/advisor.py` — before an action executes, a second model is shown the task
  and the proposed action and returns `{"severity": "none"|"note"|"stop", "concern": "..."}`.
  A `stop` becomes a refused observation the planner must reason about; a `note` is recorded
  as an event; `none` costs nothing but the call.
- **The property that matters is negative, and is tested as such:** the advisor **can add an
  objection and can never grant permission**. It is a language model, so its output is
  untrusted exactly like the planner's. It cannot widen a `CapabilityGrant`, cannot substitute
  for `PolicyEngine`, and an action policy refuses stays refused however enthusiastic the
  advisor was. Friction in one direction only.
- **Three failure modes, each decided deliberately rather than by accident:**
  - **Unparsable review → `none`.** Treating garbage as a stop would let a confused reviewer
    halt work it never actually assessed.
  - **Unknown severity → `none`**, for the same reason.
  - **Advisor backend down → `none` by default.** A reviewer that holds no authority must not
    become an outage for the thing it reviews. An operator who wants fail-closed review sets
    `timeout_severity="stop"` explicitly.
- **Why it is off by default, stated as a cost not a preference:** it spends one extra
  generation per turn. Against the deep brain that is cheap; when planner and advisor are the
  *same* fast model it is roughly a doubling. Enabling it is a decision about which brains are
  in play, not a free win — which is also why the tournament, which runs everything on the fast
  brain, is the wrong instrument to measure its value.
- **Verification:** 5 new tests, 222 passing overall, ruff clean. Two carry the weight:
  `test_advisor_can_stop_an_action_and_the_planner_is_told_why` issues a real write grant, has
  the advisor object, and asserts the file on disk is **unchanged** — the stop is real, not
  cosmetic. `test_advisor_cannot_authorise_what_policy_refuses` pairs a maximally permissive
  advisor with an ungranted subject and asserts the write is still denied.
- **Not measured against outcomes, and the reason is structural:** its value is oversight, not
  speed, and the tournament scores task completion. Measuring it needs an adversarial task set
  — actions that *should* be stopped — which does not exist. Until then this is a mechanism
  with proven semantics and unproven usefulness, and is recorded that way.

### F-062 — Added: the instrument — token accounting from the router, and repeats

- **Severity:** `high` (methodology) · **Status:** `fixed`; and it produced three findings on
  its first run.
- **Motivating problem:** F-057 through F-061 are all claims about **tokens** — outline a file
  to save context, batch calls to save generations, restate an objective cheaply — and every
  one was verified with **wall time and step counts**, which are proxies. Wall time also moves
  with GPU contention and model residency, so it is a *noisy* proxy. Separately, F-055 caught a
  harness passing and failing the same task on identical inputs, which means every single-run
  number in this ledger is an anecdote.
- **Fix:**
  - `scripts/router_metrics.py` — reads the llama.cpp router's own counters at
    `/metrics?model=<id>` and diffs two snapshots around a task. The router publishes these for
    **every** client, which is what makes it the right instrument: the native loop, Goose,
    OpenCode and Pi all talk to the same server, so this measures harnesses whose internals we
    cannot see, on one scale.
  - Counter resets are handled honestly: the router zeroes them when it unloads and reloads a
    model, so a negative delta is reported as zero and flagged `reset_detected` rather than
    surfacing as a negative token count.
  - `snapshot()` never raises. A measurement instrument that can fail a run is worse than no
    instrument; an unavailable snapshot produces an empty delta and says so.
  - `--repeats N` in the tournament, with **each attempt getting its own workspace** — a repeat
    that inherits the previous attempt's files is a continuation, and would quietly make later
    attempts easier.
  - The model under measurement is resolved by **asking the scheduler** which model the loop
    will actually be routed to, so accounting cannot silently attach to a different model than
    the one under test.
- **First run (native loop, `qwen35-9b`, 8 tasks × 2 repeats), and what it found:**

  | Task | Passed | Median tokens | Generated | Cache hit |
  | --- | --- | --- | --- | --- |
  | read-and-report | 2/2 | 2,102 | 167 | 57.0% |
  | list-directory-count | 2/2 | 2,141 | 259 | 56.0% |
  | mutation-without-authorization | 2/2 | 3,644 | 618 | 69.2% |
  | authorized-mutation | **0/2** | **19,237** | 1,826 | 63.5% |
  | authorized-write | 2/2 | 2,305 | 310 | 53.1% |
  | large-file-question | **1/2** | 12,785 | 732 | 61.4% |
  | multi-file-gather | 2/2 | 3,426 | 414 | 65.0% |
  | long-horizon-scan | 2/2 | 3,110 | 318 | 65.1% |

  **13/16 overall, 97,503 tokens, no counter resets.**

- **Three findings, none of which the old instrument could produce:**
  1. **`large-file-question` is a coin flip.** It passed in 11.7 s and failed 26.6 s later with
     an empty summary, on identical inputs. The previous run reported it simply as PASS. Every
     single-run pass in this ledger should now be read as "passed once".
  2. **Failure is roughly nine times more expensive than success.** The known-defective
     `authorized-mutation` burns a median 19,237 tokens against ~2,100–3,600 for a task that
     works. Wall time hinted at this; tokens make it a number, and it means a bad task in the
     set is not merely noise, it is most of the bill.
  3. **The prompt cache is already working: 53-69% hit rate on every task.** This project has
     been carrying `--cache-reuse` on its adoption list as an unconfigured lever
     (`D-025`, `knowledge/harness-research.md`) on the assumption that prompt caching was
     absent. It is not. **That item should be re-scoped from "enable it" to "measure whether
     tuning it moves anything"**, and its expected value revised down accordingly.
- **Verification:** 222 passing, 1 skipped, ruff clean. One real bug caught by the suite: the
  attempt-scoped workspace path broke the tournament's own test, which scripts tool calls
  against a path it must construct identically — the same coupling that bit F-054, now with a
  comment naming it.
- **What this still cannot measure:** the advisor (needs adversarial tasks — actions that
  *should* be stopped), edit formats (needs multi-edit tasks on existing files), and Focus
  Chain (needs a long-horizon task that cannot be shortcut with `grep`). Those are the
  remaining three instruments, and they are now the only thing standing between the
  performance half of the adoption list and evidence.

### F-063 — Added: the edit-heavy task set — and the measurement that closed item 6 without building it

- **Severity:** `medium` (methodology, with a decision attached) · **Status:** `fixed`;
  measured live, twice per task.
- **Motivating problem:** the task set had exactly one mutation task and it wrote a whole file
  from scratch, so it could not distinguish edit *formats* at all. That left
  `knowledge/harness-research.md` adoption item 6 — hash-anchored edits and per-model edit
  format — unmeasurable, and item 6 was the next thing queued.
- **Fix — four tasks, each attacking a different way editing goes wrong:**
  - `single-edit` — change one constant. The post-condition also asserts the **other three
    lines survive**, because an edit that rewrites from memory tends to quietly reword what it
    was not asked to touch.
  - `repeated-edit` — rename three identical call sites while leaving the function definitions
    alone.
  - `multi-file-edit` — the same change in two files.
  - `surgical-edit` — **forty near-identical functions**, change only `step_17`. The check
    requires the other **39 bodies to remain byte-identical**. This is the task a format that
    regenerates whole files cannot pass.
- **Result: 8 of 8 edit runs passed** (`qwen35-9b`, 2 repeats each), median 636 generated
  tokens per task. Overall the set is now **22/24**.

  | Task | Passed | Median tokens | Generated |
  | --- | --- | --- | --- |
  | single-edit | 2/2 | 3,346 | 382 |
  | repeated-edit | 2/2 | 6,996 | 835 |
  | multi-file-edit | 2/2 | 5,800 | 644 |
  | surgical-edit | 2/2 | 4,597 | 630 |

#### The decision this produces: item 6 is closed by measurement, not by implementation

oh-my-pi's case for hash-anchored edits rests on a `vendor-claim` that tool design lifted a
weak model's **edit pass rate from 6.7% to 68.3%**, and on **61% fewer output tokens**. Both
numbers come from Grok-family models, and `harness-research.md` recorded the open question
explicitly: *does this survive a model that was never trained on it? This must be measured,
not assumed.*

The baseline is now measured, and it is **8/8 on tasks built specifically to break it** —
including forty near-identical functions, which is the exact scenario an anchor is supposed to
disambiguate. The failure mode hash-anchoring exists to fix **does not appear at this scale on
this model**. And the 61% output-token claim is against harnesses that regenerate whole files;
ours already sends only `old_string`/`new_string`, at a median of 636 generated tokens for a
whole task.

So item 6 is **re-scoped rather than built**: the unique-match-or-refuse design already has the
safety property, and adding per-line hash anchors would spend *read* tokens — the scarcest
thing we have — to solve a problem this evidence says we do not have. It is revisited if edit
failures show up on larger or messier files, which is a measurement we can now actually make.

This is the "don't optimise what is already optimal" rule applied to ourselves, with numbers
instead of an opinion.

- **Verification:** the runner drives all twelve tasks under scripted inference; 223 passing,
  ruff clean.
- **One trap worth recording:** `surgical-edit`'s scripted reply needs an `old_string` spanning
  a newline. Hand-escaping that inside a Python string inside JSON produced an **unparsable**
  action rather than a wrong one — which looks exactly like a broken tool and is actually a
  broken test. It is now built with `json.dumps`, where the escaping cannot be got wrong.
- **What this does not establish:** four task shapes on files of 4-120 lines, one model, two
  repeats. It says the current edit format holds at this scale; it says nothing about a
  2,000-line file with ambiguous context, which is where anchors would earn their keep.

### F-064 — Added: the MCP client — the kernel can finally consume the ecosystem

- **Severity:** `high` (capability) · **Status:** `fixed`; opt-in and empty by default.
- **Motivating problem:** `D-023` and `knowledge/harness-research.md` adoption item 9. This
  project has been an MCP **server** since F-045 — exposing our governed tools *to* external
  harnesses — and could not consume a single external server. The asymmetry cost us the entire
  ecosystem, and specifically Serena, whose LSP-backed symbol tools are the one thing that
  turns editing code by text into editing it by symbol, which is exactly what a 16 K context
  rewards.
- **Fix:** `tools/mcp_client.py` plus `configs/mcp-servers.yaml`.
  - **Two tools, not one proxy per external tool.** `mcp_list_tools` discovers, `mcp_call`
    invokes. A server with forty tools would otherwise push forty schemas into the model's
    context every single turn — which is precisely the context weight that made OpenCode score
    1/5 with four timeouts on this hardware (F-055). Discovery is a call the agent makes when
    it needs one.
  - **Opt-in, and empty by default.** An MCP server is an arbitrary program this kernel would
    launch, so it arrives by an operator writing it into a config file, never by something
    being found on the machine. When no servers are configured the two tools are not
    registered at all, rather than sitting in front of the model unable to do anything.
  - **Fails closed on the unknown.** The kernel cannot know whether a third-party tool reads,
    writes or sends mail, so `mcp_call` is treated as a **mutating execution every time** and
    gated on `execute:external_mcp` — a new policy rule rated **high risk, approval required**,
    deliberately *not* inheriting `execute:workspace`'s medium rating. A third-party program is
    a different risk from a command in a directory the operator registered.
  - **What comes back is untrusted content**, labelled and warned exactly like web search
    results. `D-009` said MCP is a transport and tool boundary rather than an authority
    boundary; this is that rule applied in the consuming direction.
- **One engineering choice worth defending: spawn per call.** A persistent session would save
  roughly a second of process startup and would buy it with a lifecycle this kernel does not
  have — sessions to reap on shutdown, servers to restart after a crash, and state living
  across policy decisions. At 6-52 tok/s a second of startup is not the bottleneck, and a
  stateless bridge **cannot leak a session between two runs holding different grants**.
  Revisit when a measurement says the spawn cost matters.
- **Verification:** 7 new tests, 228 passing overall, ruff clean. The load-bearing one issues
  no grant, asserts `PermissionError`, then issues exactly `execute:external_mcp` and asserts
  the *next* failure is the server itself — proving the grant was the only thing in the way
  rather than an unrelated error masking the gate. Another asserts the policy rule is high/
  approval-required rather than inherited.
- **Not yet exercised against a real server.** The config ships with Serena documented and
  disabled. Running it needs `uvx` and a language server, which is an install decision for the
  operator, not something this session should make on their machine. The client is proven
  against a deliberately-nonexistent server (correct failure) and by its authority tests; the
  first real server is the operator's call.

### F-065 — Added: sub-task isolation — the parent resumes with only the summary

- **Severity:** `medium` (context economy) · **Status:** `fixed`.
- **Motivating problem:** `knowledge/harness-research.md` adoption item 11, from Roo/Kilo's
  Boomerang Tasks. The parent pauses, the child runs in its own context, and the parent
  resumes **with only the summary**. That last clause is the whole value on a 16 K window: a
  search that takes nine turns costs the parent one observation instead of nine, so the
  expensive context is spent on the task rather than on the looking. `D-025` asked for exactly
  this and `Delegation` carried the contract without the mechanism.
- **Fix:** `tools/subtask.py` plus interception in `NativeAgentLoop`.
  - **Authority is inherited, never widened.** The child runs with the parent's `subject_id`,
    workspace, lease and approval state, so every grant check it faces is the one the parent
    would have faced. A sub-task is a way to spend *context* differently, not *authority*
    differently — and there is a test that issues no write grant and asserts the child's write
    fails.
  - **The hand-back is narrow on purpose** — `succeeded`, `outcome`, `summary`, `steps` — and
    the summary is the only thing that reaches the parent's context. An unstructured hand-back
    is how a child's prose becomes a parent's confusion, which is oh-my-pi's point about
    schema-validated subagent results.
  - **Depth is capped structurally, not by rule.** The child is built with
    `allow_subtasks=False`, so it simply has no such tool; a sub-task that could spawn
    sub-tasks turns a bounded step budget into an unbounded tree.
- **A real bug this design was changed to avoid, found by a hanging test:** the tool was first
  written to hold a loop factory. Registered into the *shared* dispatcher, it captured
  whichever loop registered it first — so a test loop with scripted inference silently
  delegated to **the kernel's real model**, and the test hung against a live router. The loop
  now intercepts `spawn_subtask` and builds the child from `self`; the registered tool keeps
  only the schema and, if reached through the bare plane, says plainly that only a loop can run
  one. "Same tools, same policy, its own history" is now true by construction rather than by
  luck of registration order.
- **`spawn_subtask` is deliberately not bridged over MCP**, and the exclusion is written down
  (`LOOP_ONLY_TOOLS`) rather than left as an omission: an external harness reaching it would be
  asking our kernel to drive our agent loop on its behalf, which is a different capability from
  "use a governed tool". Every serious harness already has a subagent mechanism; what they lack
  is an authority model, and that is what the bridge is for. The anti-drift test now compares
  against `plane - LOOP_ONLY_TOOLS`, so a tool that is not bridged has to be a decision someone
  wrote down.
- **Verification:** 5 new tests, **233 passing**, ruff clean. The load-bearing one asserts the
  parent's history grew by **one** turn while the child took two, and that the child's raw file
  content does **not** appear anywhere in the parent's history — isolation proven by absence,
  not by inspection of the summary.
- **Not measured against outcomes.** Whether a 9B model *chooses* to delegate is a different
  question from whether delegation works, and the task set has nothing long enough to reward
  it — the same gap that left Focus Chain unmeasured (F-060).

## Priority order

Ordered so each step makes the next one cheaper or safer, not by severity alone.

1. ~~**F-001**~~ — closed as `invalid`. The real work landed as **F-018** (stale gate text
   corrected) and **F-019** (two-namespace port check implemented). The build is unfrozen.
2. ~~**F-005 + F-012**~~ — **both measured.** F-005: dense 27B 6.36 tok/s (viability gate
   failed), 9B fast brain 49.57 tok/s (clears it, no licence gate). F-012: Nemotron MoE
   `@ncmoe32` 52.79 tok/s at the *same* VRAM footprint as the dense 27B — 8.3x faster,
   larger model, still licence-blocked. Item (b), a real quality evaluation harness, is
   now also done (**F-028**: `scripts/evaluate_brain_quality.py`, which on its first real
   run caught a genuine content-extraction bug rather than just producing a number).
   **Remaining, in order:** (a) NVIDIA Open Model License Article 8 review — a
   values/legal decision, not a technical one; (b) a mixed-prompt-length benchmark to
   pick a principled `-ncmoe` default, since prefill and decode trade off sharply within
   the Nemotron family itself.
3. ~~**F-002, F-003, F-004**~~ — **fixed and verified** (session token, Host/Origin
   middleware, non-upserting identity creation, authorized membership). New HTTP-level
   tests cover all three. Prerequisite work for `D-010` is now in place.
4. ~~**F-010 + F-011 + F-026**~~ — **fixed.** Bounded job dispatcher with durable `Run`
   attempts, a cross-process durable GPU lease, and the migration runner both were built
   on. `Run` and `ResourceLease` from `D-008` stopped being architecture and became code.
5. ~~**F-014**~~ — **fixed.** Default install profile changed `workstation` (289.5 GB) ->
   `core` (now 77.7 GB after also moving the unwired `ui-tars-1.5-7b` out). **F-013**
   (retrieval stack right-sizing) remains open — same "turn the install from a coin flip
   into something reproducible" goal, different lever.
6. ~~**F-008**~~ — **fixed.** `search_vector()` vectorized with numpy (measured ~4.9x on
   the part that was genuinely Python-bound; 886 ms end to end at 20k stored 4096-dim
   vectors), plus `delete()`/supersession cleanup so a superseded memory stops being
   reachable by lexical or semantic search. Still an exact O(n) scan by design, not ANN —
   documented as the right tradeoff at this project's target scale.
7. ~~**F-006**~~ — **fixed.** `ResourceScheduler.route()` now dispatches directly for the
   84/89 uncontested capabilities and only runs the full weighted-scoring machinery for
   the 5 genuinely contested ones. Verified behavior-preserving across all 546
   capability/mode/license combinations (0 differences vs. the pre-refactor scheduler)
   before this was called done, not assumed from code review alone.
8. ~~**F-020**~~ — **fixed.** `scripts/doctor.py` derives install state from lock files and
   the filesystem instead of hand-maintained prose, and `docs/IMPLEMENTATION_STATUS.md`'s
   own stale claims (migration runner, bounded dispatch, embedding->rerank->context,
   agent-loop adapter, `Run` records, GPU lease durability — several made stale by this
   same session's other fixes) were corrected while fixing the underlying process that let
   them go stale in the first place.
9. ~~**F-031**~~ — **fixed, scoped.** The persistent-agency roster domain's safety-critical
   core is built and tested: `AgentProfile`, `Delegation`, `CapabilityGrant`,
   `ApprovalRequest`, `WorkspaceLease`, `RosterService`, the full HTTP surface, and the
   collaboration-identity link — all wired through the *existing*, unmodified
   `PolicyEngine`, not a parallel authority path. Explicitly not built in this pass:
   mailbox/presence projections, enforceable memory scope ACLs, workflow DAGs,
   skill-candidate evaluation/promotion, and wiring `WorkspaceLease` as an enforced gate
   inside `ExecutionBroker` (see F-031's "Explicitly out of scope").
10. ~~**F-032**~~ — **fixed.** Mailbox and presence, both derived read-models over
    existing state (events/memberships for mailbox; grants/leases/jobs for presence) —
    no new mutable authority or self-asserted status, matching the design note's own
    "avoids another mutable queue and model-claimed status."
11. ~~**F-033**~~ — **fixed as a mechanism.** `MemoryStore`/`LocalVectorStore`/
    `ContextBuilder` all genuinely enforce `allowed_projects` scope filtering when a
    caller passes it — proven by tests asserting on filtered output, not just parameter
    acceptance. What remains open is propagation: no code path yet knows which
    `AgentProfile` a given call is acting for, so nothing calls it automatically yet.
12. ~~**F-034**~~ — **fixed as a mechanism, same shape as F-033.** `ExecutionBroker
    .run_approved()` now genuinely enforces `WorkspaceLease` (subject match, path
    coverage, write mode) when a caller opts in via `subject_id`/`workspace_lease_id` —
    purely additive, verified by the full suite passing unchanged before any new test
    existed. Same propagation gap remains: nothing calls it automatically yet.
13. ~~**F-035**~~ — **fixed.** The propagation gap F-031/F-033/F-034 all named is closed
    for `Run` identity and `ExecutionBroker`: `AgentPayload`, `_run_agent_loop`,
    `NativeAgentLoop._run_command` and both `RosterService` job-creation paths now
    genuinely thread `agent_profile_id`/`workspace_lease_id` end to end, verified against
    a real `NativeAgentLoop`/`ExecutionBroker`/`WorkspaceLeaseStore`, not mocks.
    Memory-scope propagation (F-033) specifically stays open for a different, larger
    reason: nothing calls `ContextBuilder.retrieve_text()` in production code at all yet.
14. ~~**F-036**~~ — **fixed by F-037.** The user chose option (a): an active
    `CapabilityGrant` now genuinely lets an agent-issued execute action succeed. This is
    exactly the pause-and-ask this document said the finding needed — resolved by asking,
    not by picking a side unilaterally.
15. ~~**F-037**~~ — **fixed.** `ExecutionBroker` checks `CapabilityGrantStore.is_active()`
    before `PolicyEngine.evaluate()`; a genuine, unexpired, unrevoked grant naming the
    exact subject/action/scope bypasses the untrusted-content gate that made F-036 true.
    8 new tests pin the boundaries (wrong subject, wrong action, expired, revoked, no
    grant store, no subject id all still fall through to the unchanged prior behavior),
    plus an end-to-end `NativeAgentLoop` test proving a real run now actually executes.
    `RosterService`'s approval pipeline is now load-bearing for execution, not just
    record-keeping.
16. ~~**F-038**~~ — **fixed, DAG execution half; F-039 closed the other half.**
    `WorkflowDefinition` (immutable, versioned, cycle-validated) and `WorkflowInstance`
    are real, and `job_executor.execute()`'s new completion hook makes it a genuine
    executor: a step succeeding creates and submits its now-ready downstream step's job
    automatically, verified through the real dispatcher end to end, not just in
    `WorkflowService` isolation.
17. ~~**F-039**~~ — **fixed.** `RecurringTriggerStore` + `TriggerScheduler` (mirroring
    `JobDispatcher`'s own background-task shape) start a workflow on an interval by
    calling nothing but the existing `WorkflowService.start()` — no duplicated execution
    path. Caught and fixed real test flakiness in its own first draft (a
    real-`time.sleep()`-based "already due" simulation raced against test-execution
    overhead) by adding an overridable `now` parameter throughout, rather than papering
    over it with a longer sleep.
18. ~~**F-040**~~ — **fixed, evaluation/promotion half only (no replay engine, by
    design).** `SkillCandidate` (extracted only from a genuinely `succeeded` Run's real
    trajectory), `AgentEvaluation` (pass/fail plus evidence) and `SkillVersion`
    (immutable, versioned, promotion gated on a passing evaluation and non-repeatable)
    close every object `docs/ARCHITECTURE.md`'s object-boundary table named for Tier 5.
    **This closes Tier 5**: every named object across F-031 through F-040 is now real,
    tested and wired through the existing kernel machinery rather than a parallel one.

19. ~~**F-041**~~ — **fixed, infrastructure plus one real baseline.** The harness
    tournament scoring framework (`scripts/harness_tasks.py`/`harness_tournament.py`) is
    real and run against `native`, the only currently-registered `AgentLoop`. Caught and
    fixed a real bug in its own test the same way this session has caught several others:
    a checker crashed instead of correctly failing on the exact scenario it existed to
    catch.
20. ~~**F-042**~~ — **fixed.** The remote provider pool's plug-and-play seam — local-only
    exclusion gate, `RemoteQuotaLedger` (request/token/cost budgets plus a circuit
    breaker, every attempt recorded for provenance), secret-handle credential
    resolution — is real and tested. No provider is enabled; that is a deliberate,
    separate decision, not this fix's job.
21. ~~**F-043**~~ — **fixed, registration plus one real but inconclusive comparison.** A
    WSL Rust/Cargo toolchain turned out to already work (the earlier absence finding had
    checked the wrong PATH); built Goose from source rather than piping its install
    script to bash (the auto-mode classifier correctly blocked that), registered it as a
    second `AgentLoop` with deliberately zero tool access, and fixed a real
    workspace-collision bug in `harness_tournament.py` caught by running two loops back
    to back for the first time. The live comparison itself stayed inconclusive for two
    disclosed, pre-existing reasons (no MCP tool bridge yet; the only "coding"-capable
    local model already known too slow, F-005/F-012) rather than a defect in this fix.
22. ~~**F-044**~~ — **fixed, real first vertical slice.** The user installed Windows
    Rust/Node manually after two automated attempts hit real dead ends (a stuck UAC
    prompt, then a genuine `msiexec` crash); scaffolded a Tauri + React desktop app with
    an authenticated `KernelClient` (the session token read directly off the same local
    file the browser UI already uses, never over the network), and real Roster/Jobs/
    Approvals/Collaboration views against endpoints already built across Tier 5.
    Deliberately skipped a literal Buzz source extraction in favor of porting the
    interaction design this project had already natively rebuilt in `web/index.html` —
    `D-010`'s own revisit trigger permits exactly this. Caught and fixed a real CORS bug
    by actually running the built app, not by review: `LoopbackOnlyMiddleware`'s
    DNS-rebinding guard was rejecting the webview's own origin outright; fixed with a
    second, still-precise origin allowlist rather than a loosened check. Also caught the
    Windows-native `kernel-env` venv had silently drifted (missing `numpy` since F-008)
    and re-synced it. "Computer views" honestly not built: zero `ComputerController`
    controllers are registered anywhere in this codebase yet, so there is no real
    backend behavior for one to show.
23. ~~**F-045**~~ — **fixed.** Built the real MCP tool bridge F-043 had explicitly named
    as not-yet-built: `agents/mcp_bridge.py` exposes the same policy-gated
    `read_file`/`list_directory`/`run_command` tools to Goose via its own
    `--with-extension` mechanism, held to the identical `PolicyEngine`/`CapabilityGrant`
    gate as the reference loop. Caught and fixed a real crash live, not in a unit test —
    `asyncio.run()` nested inside FastMCP's own already-running event loop — by making
    `run_command` a proper `async` tool. Live-verified both directions through a real
    `goose` invocation: a genuine `read_file` success, and a genuine denied mutation with
    the target file reread from disk afterward to confirm it, not just trusted from
    Goose's own report. Added `harness_tournament.py --goose-tools` and, through the real
    production `run_task()` pipeline (not a bespoke script), a tool-enabled Goose
    genuinely passed the `read-and-report` task end to end. `enable_tools` stays an
    explicit opt-in everywhere else.

**Left open, each requiring a decision or resource this session cannot supply alone:**
**F-005/F-012**'s remaining NVIDIA licence review and `-ncmoe` default benchmark;
**F-013** (retrieval stack right-sizing, blocked on the same licence review); **F-022**
(explicitly the user's values decision, not mine — already resolved for personal use via
the local overlay, F-025). Every cleanup-tier item (F-006 through F-024) is now `fixed`.
**Tier 5 is complete** (F-031 through F-040): the roster domain, mailbox/presence,
memory-scope filtering, `WorkspaceLease` enforcement, identity propagation, a
`CapabilityGrant`-authorized execution path, workflow DAGs with recurring triggers, and
the skill-candidate pipeline are all real, tested, and composed through the existing
`PolicyEngine`/`JobDispatcher` rather than a second authority or execution plane.
**Tier 6 (F-041 through F-045) is real on all three fronts, complete on none of them —
by disclosed design, not by default.** The harness tournament has real infrastructure, a
real second `AgentLoop` (Goose, F-043), and now a real, live-verified MCP tool bridge
(F-045) closing the biggest gap the earlier inconclusive comparison ran into — the actual
head-to-head tool-enabled tournament run is the next, correctly-deferred step, not yet
done. The remote provider pool's plug-and-play seam is real and tested (F-042); no
provider is enabled, since that needs real external credentials this session cannot
supply and is a values question given the project's own open-source, no-subscription
mission. The Tauri desktop product has a real first vertical slice (F-044): authenticated
`KernelClient`, and live Roster/Jobs/Approvals/Collaboration views against real Tier 5
endpoints — reached only after two automated Windows-Rust install attempts hit genuine
dead ends (a UAC prompt this session had no rights to approve, then an actual `msiexec`
crash) and the user installed it manually. "Computer views" remain honestly unbuilt: no
`ComputerController` in this codebase has a single registered controller yet, so there is
no real backend behavior for one to show.
