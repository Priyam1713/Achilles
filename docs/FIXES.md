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

---

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
**Tier 6 (F-041 through F-043) is two-thirds done, one genuinely blocked:** the harness
tournament has real infrastructure, a real second `AgentLoop` (Goose, F-043), and a real
live run — inconclusive for two disclosed reasons (no MCP tool bridge yet, and the only
"coding"-capable local model is already known too slow), not a code defect. The remote
provider pool's plug-and-play seam is real and tested (F-042); no provider is enabled,
since that needs real external credentials this session cannot supply and is a values
question given the project's own open-source, no-subscription mission. The Tauri desktop
product remains genuinely blocked: a WSL-side toolchain turned out to already work (it
built Goose), but Windows-side Rust hit two independent dead ends in the same session —
a winget MSI install hung on a UAC prompt this session has no rights to approve, and the
official per-user `rustup-init.exe` was removed by Windows Defender as a virus/PUP
immediately after download. Neither was worked around (no AV exclusion, no elevation
bypass); both are reported to the user rather than guessed past.
