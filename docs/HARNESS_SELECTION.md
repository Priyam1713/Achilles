# Harness selection report — 2026-09-01

## Decision

**NativeAgentLoop remains the safety incumbent/default, while Aider is now the provisional
general-coding efficiency leader.** Arena v2 has screened Prime Agent, DeepSeek Harness/Cordis,
mini-SWE-agent, OpenHands, Aider, oh-my-pi, SWE-agent and Qwen Code. Aider is the first contender to
exceed Native's point pass rate and efficiency, but it failed both safe-join security cells.
SWE-agent finished 25 points below Native, used 6.78 times the total tokens, and repeatedly changed
forbidden test files despite its official prompt. Qwen Code finished 8.33 points below Native and
used 2.17 times the tokens despite finishing much faster. The planned core open-harness screen is
complete; Cline, Kilo and Gemini CLI remain conditional interface experiments rather than blockers.

This is a workstation-specific, provisional promotion, not a claim that Native is universally
better. It won this composition: Qwen3.5-9B Q6_K, upstream llama.cpp, the Achilles governed
tool plane, authenticated OpenShell verification, eight dependency-free Python repository
tasks, and a 180-second budget per attempt.

## Historical Arena v1 (Native/Pi/Goose/OpenCode)

The sections below preserve the original v1 result and explain why Native became the working
default. They are historical evidence, not a complete open-harness ranking: v1 had only eight
Python tasks, no gold/null control run, no clean-fixture diff reconstruction and no paired
confidence intervals.

## Why the authority kernel came first

The first screen exposed a kernel boundary defect before it produced usable harness evidence.
OpenShell preserved the uploaded workspace's basename, while the broker executed one directory
above it. All harnesses made the correct first patch, but `verify.py` was invisible and every
cell was falsely scored as failed. The campaign was stopped and discarded. F-077 corrected the
upload/working-directory/download contract, added regression tests, and passed a live held-out
canary before this tournament began from clean commit `1a81406`.

This establishes the dependency rule for future layer contests: keep a minimal authority kernel
as the common governed fixture, repair it only when it invalidates measurement, and never expand
it while a contestant comparison is running.

## Fixed composition and protocol

- Brain: `qwen35-9b` for every contender.
- Runtime: the same local llama.cpp router and model counters.
- Tools: the same kernel implementations, workspace allow-list and capability grants.
- Verification: held-out executable contracts staged only after the harness terminated, run
  read-only through authenticated OpenShell without network access.
- Suite: `software-engineering`, eight tasks covering bug fixing, feature work, configuration
  precedence, cross-file change, collision debugging, path traversal, pagination boundaries and
  malformed JSONL resilience.
- Budget: 180 seconds for every complete attempt; external adapters stop at 179 seconds so their
  subprocesses can be killed and reaped before the coordinator deadline.
- Order: deterministic rotation across tasks and repetitions.
- Promotion priority: held-out correctness and security, then reliability, latency, tokens and
  operational footprint. A fast wrong answer does not outrank a slower correct one.

## Phase 1 — complete four-way screen

| Harness | Passed | Pass rate | Median time | Total time | Total tokens | Median tokens | Failed tasks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Native | 8/8 | 100% | 28.89s | 439.41s | 123,101 | 7,012 | — |
| Pi | 7/8 | 87.5% | 33.89s | 406.31s | 214,586 | 16,786 | safe join (timeout) |
| Goose | 6/8 | 75% | 37.62s | 310.32s | 136,686 | 16,818 | config precedence, safe join |
| OpenCode | 6/8 | 75% | 35.01s | 401.43s | 259,967 | 21,691 | slugify, pagination |

Goose's lower total time is not a win: two incorrect completions ended earlier. It also failed
the security contract. OpenCode was the only external contender to pass security in the screen,
but failed two ordinary engineering tasks and spent 105,353 tokens on its failed slugify cell.
Pi advanced because it had the next-best correctness and was materially faster than Native on
the cache-collision cell; its security timeout required repetition rather than presumption.

## Phase 2 — Native versus Pi

The finalists ran two additional attempts per task. Combining those 16 cells per harness with
their eight screen cells gives three observations per task and 24 per harness.

| Harness | Passed | Pass rate | Median time | Total time | Total tokens | Median tokens | Generated tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Native** | **24/24** | **100%** | **32.97s** | **1,060.07s** | **272,478** | **7,599** | 44,211 |
| Pi | 21/24 | 87.5% | 34.05s | 1,164.64s | 593,858 | 16,786 | 48,412 |

Native used 54.1% fewer total accounted tokens and 9.0% less wall time while passing every
contract. Total tokens include prompt, cache-read and generated counters; generated-token totals
were closer, but Native's compact governed observation/history protocol made its complete context
cost much lower.

### Per-task finalist evidence

Each cell is `passes/3 · median wall time · median total tokens`.

| Task | Native | Pi |
| --- | --- | --- |
| Empty mean | **3/3 · 20.07s · 8,138** | 3/3 · 23.23s · 17,173 |
| Add slugify | **3/3 · 44.01s · 10,647** | 3/3 · 38.36s · 19,271 |
| Config precedence | **3/3 · 32.60s · 8,024** | **1/3** · 40.84s · 15,061 |
| Cross-file greeting | **3/3 · 32.54s · 12,271** | 3/3 · 29.12s · 18,956 |
| Cache-key collision | **3/3 · 38.31s · 5,217** | 3/3 · 31.63s · 13,396 |
| Safe join | **3/3 · 77.85s · 17,067** | **2/3** · 94.61s · 54,046 |
| Pagination boundaries | **3/3 · 33.56s · 7,131** | 3/3 · 34.20s · 13,294 |
| JSONL resilience | **3/3 · 26.79s · 6,518** | 3/3 · 28.72s · 12,156 |

Pi's screen security timeout did not prove deterministic incapability—it passed both repeats—but
2/3 is insufficient beside Native's 3/3. Its configuration-precedence failure repeated twice,
making that reliability gap unambiguous.

## Promotion and contender status

- **Native — promoted default.** Perfect held-out correctness, perfect security, lowest total
  finalist time and substantially lower context/token cost. It is also the smallest operational
  dependency because it is in-process.
- **Pi — adapter retained; external runtime removed after testing.** Strong 87.5% combined result and competitive speed on several
  tasks, but not safe to promote with 1/3 configuration correctness and 2/3 security reliability.
- **OpenCode — adapter retained, runtime removed, eliminated from the v1 final.** Passed security, debugging,
  cross-file and robustness tasks, but 75% screen correctness and the highest screen token cost.
- **Goose — adapter retained, runtime removed, eliminated from the v1 final.** Efficient on successful cells,
  but 75% correctness and a direct security-contract failure block promotion.

`configs/system.yaml` names `native` as `default_agent_loop`; CLI and background jobs resolve
that configuration rather than carrying independent hard-coded defaults. Removed external
runtimes are no longer registered, while their adapters and evidence remain reproducible.

## Evidence integrity

Both schema-v3 reports completed all 32 expected cells and used task-manifest SHA-256
`2a21e580fc9b76d2f04b118f4e0ed388e2bab5f3a79f35f1fe4595c953a330d3`.

| Campaign | Campaign SHA-256 | Raw report SHA-256 |
| --- | --- | --- |
| Four-way screen | `f906d190271b6d232514b0e27f927be9fe43ef4ccbcd868663ac02408d9076c5` | `5a1164235759b96d11e6a38319038e2c420038a305b0d6996506886d0952400e` |
| Native/Pi repeats | `4ae29a8896f99de0565014b7ecc359a3f17ecb49f38cd8eb005d748097362075` | `ff15f277feeb8a8983087ab82b42aac0fa68aa58363f6ae4c056787c3d91c588` |

The reports recorded Git head `1a814064f09a65fe723f52fb811ca5512d437cb1`. Their `dirty: true`
flag was a metadata false positive: WSL Git saw Windows CRLF representation differences while
Windows Git and `git diff --ignore-space-at-eol` were clean. The provenance probe is corrected
with the promotion so future reports preserve real content/index/untracked changes while ignoring
only EOL representation differences. The raw reports remain in the local state directory; this
document records the complete decision-relevant measurements without publishing machine-specific
workspace paths or ANSI-heavy harness transcripts.

## Arena v2 — Prime Agent admission and screen

Prime Agent 0.8.1 was installed from Prime Intellect's official stable artifact and connected
through the same Achilles extension boundary as Pi. Prime's built-in tools, context-file and
extension discovery, skills, prompt templates, sessions, telemetry and startup networking were
disabled. Its only filesystem/command authority came from the authenticated kernel tool plane.

Round 0 exposed two useful composition facts:

- `qwen38-27b` was unsuitable for screening throughput at the current profile. Native timed out
  at 180 seconds and recovered only in the 360-second diagnostic; Prime exhausted both budgets.
  Those two cells are a serving-profile probe, not a harness ranking.
- On `qwen35-9b`, both adapters were operational. Native scored 3/3. Prime scored 2/3 under the
  manifest rule, while its production change independently passed the third hidden contract;
  it had created an extra test file. All screening prompts subsequently stated the exact allowed
  file set explicitly.

Round 1 used 12 tasks × 2 attempts: 24 observations per harness. Every task first passed
`GOLD=PASS` and `NULL=FAIL` in OpenShell. Candidate repositories were rebuilt from clean fixtures,
only allow-listed file changes were applied, and the common stack was frozen under fingerprint
`55757d843f04fef3636e1c42477b0d396ccda06141080584b32c530c9c314bdf`.

| Harness | Passed | Pass rate | Median time | Total time | Total tokens | Median tokens | Generated tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Native | **15/24** | **62.5%** | **31.20s** | **1,112.94s** | **264,154** | **7,391** | 48,428 |
| Prime Agent | 14/24 | 58.33% | 44.33s | 1,483.08s | 972,082 | 17,975.5 | 63,792 |

Paired matrix: 12 both passed, 3 Native-only passes, 2 Prime-only passes, and 7 both failed.
Native minus Prime pass-rate delta was +4.17 percentage points with paired bootstrap 95% CI
[-12.5, +20.83] points and exact McNemar p=1.0. This is a statistical tie. Native used 72.8%
fewer total tokens and 25.0% less total wall time, which is a material efficiency advantage,
but Prime's two discordant wins prevent honest elimination on capability.

Prime's stable weakness was file-scope discipline: it created forbidden test files on both
slugify attempts despite explicit instructions. Its strengths included faster successful
cache-collision and dependency-migration cells. Neither harness passed the CSV or JavaScript
security tasks; neither established reliable safe-join performance. Those shared failures are
suite signals to carry into the expanded finalist league, not grounds to delete difficult tasks.

Prime is therefore **admitted and retained as a finalist candidate, but not promoted**. The raw
schema-v4 report remains local at `state/arena-v2-prime-screening-9b.json`; its SHA-256 is
`ab1418f1b766ef5f8c405c10f7f17fe886ed96a5566444aa3f8204e56e978afa`, campaign SHA-256 is
`7f93bd6b79f011b7006508c275f1775fa0949a8fdf9599469418393ef3aa6fab`, exact model GGUF SHA-256
is `9746636c0719a04dbd77eb4e50f8413f702aba902f54d01ce59b472bfe676179`, llama.cpp revision is
`dc72703fc69698b1ea68ece8d2dd8a96e6a4e1fe`, and OpenShell was 0.0.109.

## Arena v2 — DeepSeek Harness/Cordis admission and screen

DeepSeek Harness `0.1.0-rc.8` at exact revision
`141eb6fef83422698aef7a981029e843e8161534` was run through its official headless entry point.
Its generic pi-ai provider targeted the same local llama.cpp router. Direct filesystem, shell,
job, search, skill and editor tools were disabled; its planning, compaction, goals and subagent
orchestration remained available, while the Achilles MCP bridge was its only workspace-capable
tool source. The one-cell admission smoke passed end to end through OpenShell and the hidden
verifier before the screen began.

Round 1 again used 12 tasks × 2 attempts, with all 12 `GOLD=PASS` and `NULL=FAIL` controls passing
first. The frozen campaign used DeepSeek Harness adapter SHA-256
`2ec30d334c0f81d9de48a754ca0192081b23be50153fe08a8e82d891a8ead20c` and stack fingerprint
`eb7e39e3cc72ca356076a7eb8a5eecfe90e1883fcb14632ab68fbaa3336f044b`.

| Harness | Passed | Pass rate | Median time | Total time | Total tokens | Median tokens | Generated tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Native | **18/24** | **75.0%** | **39.51s** | **1,496.77s** | **375,218** | **7,387.5** | 54,913 |
| DeepSeek Harness | 16/24 | 66.67% | 44.59s | 1,564.66s | 1,060,231 | 29,592.5 | **46,886** |

Paired matrix: 14 both passed, 2 DeepSeek-Harness-only passes, 4 Native-only passes and 4 both
failed. Native minus DeepSeek Harness was +8.33 percentage points with paired bootstrap 95% CI
[-12.5, +29.17] points and exact McNemar p=0.6875. Correctness is therefore inconclusive at this
sample size. Native used 64.6% fewer total tokens and 4.3% less total wall time; the token result
is the material efficiency difference. DeepSeek Harness generated fewer output tokens yet spent
2.83× the total tokens, locating the overhead in repeated input/tool/context rather than verbosity.

DeepSeek Harness owned two discordant wins: safe-join attempt one and dependency-migration
attempt two. Native owned the paired wins on empty-mean attempt two, safe-join attempt two,
stable-dedupe attempt two and CSV/Decimal attempt one. DeepSeek Harness hit two primary timeouts;
three further runs reached the common 4,096-token model-output ceiling (plus the 64-token title
request) and terminated as `max-tokens`, showing that its one-shot loop is vulnerable when a tool
call is truncated at the shared per-request cap. Native instead exposed long multi-step budget
failures. Neither harness solved JavaScript prototype pollution, and neither made safe-join stable.

DeepSeek Harness is therefore **retained as a finalist candidate, but not promoted**. Its unique
migration/security wins prevent capability elimination, while its context amplification prevents
selection as the default. The raw schema-v4 report remains local at
`state/arena-v2-deepseek-screening-9b.json`; raw SHA-256 is
`434ae65593aabf3cfba0d2e049305aa3e615e3534cba394d9b06d932992f3dd1`, campaign SHA-256 is
`268a3d4e3fbe398ca3a2f98114d74064c36353d83978aa41fd37d9ffcb37b273`, and task-manifest SHA-256
is `7bcc57ddeae2f5846ee7f3f26075323c0aa3970426b32393e90ac3cb7019d434`. The model artifact,
llama.cpp and OpenShell versions matched the Prime screen.

## Arena v2 — mini-SWE-agent admission and screen

mini-SWE-agent 2.4.6 ran its official v2 `DefaultAgent`, official `mini.yaml` prompts, LiteLLM
OpenAI-compatible model path and native bash tool-call parser. Achilles replaced only its local
subprocess environment: each bash action was sent to the authenticated `run_command` endpoint
and executed as a governed OpenShell transaction. The host workspace path in the task was
normalized to the sandbox working directory; no direct host shell or filesystem path remained.

Admission exposed a real lower-layer defect before scoring. OpenShell 0.0.109 allowed commands
in an uploaded `/tmp` tree but permits transactional download only from its declared `/sandbox`
workspace. The broker also assumed directory download recreated the source basename, while the
CLI copies the directory contents into the destination. The corrected transaction is now
`snapshot -> upload to /sandbox -> execute -> download into an explicit staged directory ->
concurrent-edit check -> commit`. A live mutation canary and 19 focused OpenShell tests passed
before the scored campaign began. This was required for any bash-only harness to persist edits.

Round 1 used the same 12 tasks × 2 attempts and all 12 verifier controls passed. The campaign
completed all 48 cells. One Native cell lacked router-token counters after a model lifecycle
reset, so Native token totals cover 23/24 attempts; time and correctness cover all 24.

| Harness | Passed | Pass rate | Median time | Total time | Accounted total tokens | Median tokens | Generated tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Native** | **15/24** | **62.5%** | **43.56s** | **1,444.48s** | **478,708 (23/24)** | **11,464** | 58,152 |
| mini-SWE-agent | 11/24 | 45.83% | 172.86s | 3,611.41s | 3,043,708 (24/24) | 92,975.5 | 138,218 |

Paired matrix: 8 both passed, 3 mini-SWE-only passes, 7 Native-only passes and 6 both failed.
Native minus mini-SWE was +16.67 percentage points with paired bootstrap 95% CI
[-8.33, +41.67] points and exact McNemar p=0.34375. Correctness is therefore inconclusive at
this sample size. Native used 60.0% less wall time and its median attempt used 87.7% fewer tokens.
The recorded Native token total is 84.3% lower, but is explicitly incomplete by one attempt.

mini-SWE's discordant wins were slugify attempt one and both CSV/decimal attempts. Native's were
configuration precedence attempt one; cache collision attempts one and two; JSONL and dependency
migration attempt one; and slugify and cross-file greeting attempt two. mini-SWE recorded 11
primary timeouts and one harness error. Multiple 360-second diagnostics also exhausted their
limit, while several others proved that the patch was eventually correct but outside the
180-second operating envelope. Neither harness solved JavaScript prototype pollution, and
mini-SWE's successful first-attempt slugify, cross-file and safe-join results did not reproduce.

mini-SWE-agent is therefore **not promoted and is screened lower-priority, with its adapter
retained and runtime removed**. Its three unique wins preserve useful architectural evidence, but
45.83% correctness, 11/24 primary timeouts and 2.5× Native wall time make it unsuitable as the
local default on this model. The governed adapter SHA-256 is
`2342446e266890580e3bd5e11cfb26e4440d03b51ba674f68728a72366bd6ec5`; the official runner overlay
SHA-256 is `e5a056c448b676f571ce53f03944e05fa85c25de2bd6c1d9dd50eb23ca882b35`.

The raw schema-v4 report remains local at `state/arena-v2-mini-swe-screening-9b.json`; raw SHA-256
is `8aed3078af9ce86c97e30eac28272abd1f6ebdab0b617696fa59582f5ff38072`, final campaign SHA-256 is
`08a8e5a56071fc3e845ecde8c3ba1972511e007ee6f35d07d65c62efa2abc9d5`, and the pre-resume campaign
SHA-256 is `7f2f16225b0d061cc026cd158db692e8fa084e091228f70c0f403f1dd8c7e4c7`. Resume was accepted only
after the durable execution fingerprint matched; the changed fields were router load timestamp,
load state and dynamically assigned internal port. Final freeze SHA-256 is
`56e32516c83901069f83aace2dbbd257ace72ae85df1998c2f363e324167d097`; task-manifest SHA-256,
model artifact, llama.cpp and OpenShell versions matched the DeepSeek screen.

## Arena v2 — OpenHands SDK admission and screen

The current official OpenHands engine is `openhands-sdk` 1.43.1 from the
`OpenHands/software-agent-sdk` project; the separate OpenHands CLI is no longer actively
maintained. The screen used the SDK's real `Agent`, `Conversation`, LiteLLM and MCP client. No
OpenHands terminal, file-editor, browser or other workspace-capable tool was enabled. Its only
I/O authority was the Achilles MCP server; OpenHands' `Finish` and `Think` conversation controls
remained because neither can access the host. The governed empty-mean admission canary passed in
28.85 seconds before the full campaign.

Round 1 used the same 12 tasks × 2 attempts and all 12 verifier controls passed. The campaign
completed all 48 cells with no authority denials. Router counters were unavailable for two Native
attempts and one OpenHands attempt, so token totals are explicitly partial; correctness and wall
time cover every attempt.

| Harness | Passed | Pass rate | Median time | Total time | Accounted total tokens | Median tokens | Generated tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Native** | **17/24** | **70.83%** | **40.31s** | 1,627.86s | **735,386 (22/24)** | **18,820** | 63,186 |
| OpenHands | 15/24 | 62.5% | 55.85s | **1,578.57s** | 1,897,635 (23/24) | 77,350 | **43,563** |

Paired matrix: 13 both passed, 4 Native-only passes, 2 OpenHands-only passes and 5 both failed.
Native minus OpenHands was +8.33 percentage points with paired bootstrap 95% CI
[-12.5, +29.17] points and exact McNemar p=0.6875, so correctness is inconclusive. Native's
median attempt used 75.7% fewer tokens. OpenHands' slightly lower total wall time is not a speed
win: four failed SDK subprocesses exited early and Native spent the full primary budget on three
timeouts. OpenHands generated fewer tokens but consumed over four times the median total tokens,
locating its overhead in repeated prompt/tool/context input rather than answer verbosity.

OpenHands' two discordant wins were both CSV/decimal aggregation attempts, making that a
reproducible capability signal. Native's four were slugify attempt one and configuration
precedence, cross-file greeting and safe join attempt two. OpenHands timed out on configuration
precedence attempt one and exited as a harness error on four second attempts: cross-file greeting,
safe join, pagination and JSONL. The cross-file patch independently passed its hidden verifier,
but the terminal contract correctly scores any harness crash as failure. The schema retained the
exit category but not the adapter stderr, so the exact SDK exception cannot be reconstructed and
is not guessed here; F-078 now preserves bounded stderr/stdout/trajectory evidence for every
future campaign. Neither harness solved JavaScript prototype pollution.

OpenHands is therefore **not promoted, but its reproducible data-processing wins keep it as a
conditional finalist candidate**. It must first reproduce without unexplained process exits; its
governed adapter remains while the isolated runtime is removed. Runner SHA-256 is
`6cad8bb8f3dd1894244ca412c3085223892817af22760d5579825abd04a7a922`; adapter SHA-256 is
`f9efa71c471ae250efd8cdf5661732e0a38b6d97d9c184ac5d7fb7f8677a87e7`.

The raw schema-v4 report remains local at `state/arena-v2-openhands-screening-9b.json`; raw
SHA-256 is `f5a3309720108e075687b8b1b92a6b24180cb98e1c4d55589755bcb5d1c0f4f3`, campaign SHA-256 is
`3db044cbb562b3893d0623c3ed724e75b3ca6bde475e8ea5a21113366d749422`, freeze SHA-256 is
`b23ca34e306af24eae8530e83d631295e883bb90cff84137672fbcc43b82df0d`, and task-manifest
SHA-256 is `7bcc57ddeae2f5846ee7f3f26075323c0aa3970426b32393e90ac3cb7019d434`.

## Arena v2 — Aider admission and screen

Aider 0.86.2 ran its official headless CLI and upstream fallback for the unknown
`openai/qwen35-9b` model: whole-file edit format with no repo map. This intentionally avoids
post-hoc tuning. Because Aider has no MCP client and directly edits a Git tree, the trusted
adapter gave it only a disposable shadow repository whose path and environment were isolated.
Auto-tests, lint, shell suggestions, commits, analytics, network update checks and configuration
discovery were disabled. After Aider exited, the adapter rejected unsafe/special/oversized files,
checked the canonical workspace for concurrent changes and transferred the shadow diff into the
real workspace only through authenticated Achilles `write_file`/`delete_file` calls.

Admission found two adapter side effects before scoring. Aider's binary `.aider.tags.cache` was
initially mistaken for a source change, and its default startup created `.gitignore`, which the
held-out verifier correctly rejected as forbidden. The adapter now excludes private `.aider*`
cache/history files and passes `--no-gitignore`; those two cells are discarded infrastructure
evidence. The corrected empty-mean canary passed in 11.84 seconds and 1,109 tokens.

The full campaign used the same 12 tasks × 2 attempts; all gold/null controls passed, all 48
cells completed, every attempt had router counters, and neither harness recorded an authority
denial or adapter error.

| Harness | Passed | Pass rate | Median time | Total time | Total tokens | Median tokens | Generated tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Native | 17/24 | 70.83% | 29.69s | 1,219.58s | 349,533 | 7,646.5 | 50,115 |
| **Aider** | **18/24** | **75.0%** | **29.69s** | **726.17s** | **36,842** | **1,598.5** | **13,954** |

Paired matrix: 14 both passed, 4 Aider-only passes, 3 Native-only passes and 3 both failed.
Aider minus Native was +4.17 percentage points with paired bootstrap 95% CI
[-16.67, +25.0] points and exact McNemar p=1.0, so correctness is a statistical tie. Aider used
89.5% fewer total tokens, 79.1% fewer median tokens, 72.2% fewer generated tokens and 40.5% less
total wall time. Unlike earlier external harnesses, its efficiency advantage is decisive at this
composition even though its correctness advantage is not.

Aider's discordant wins were slugify attempt two, configuration precedence attempt two,
pagination attempt two and CSV/decimal attempt one. Native's were configuration precedence
attempt one and both safe-join attempts. Both failed JavaScript prototype pollution twice. The
safe-join split prevents a global promotion: Aider scored 0/2 on path-containment security while
Native scored 2/2. Conversely, treating one global harness as mandatory would discard Aider's
large ordinary-coding efficiency win. This supports a dynamic harness policy: Aider enters the
finalist league as the general edit lane; Native remains the safety/default lane until a larger
security-weighted league proves a safe routing boundary.

The isolated runtime is removed after testing while the governed adapter remains. Runner
SHA-256 is `28fe01dd0bc6abf0a8615ccaf4e1e82159695de8bc2b9c497b3bd837ec2253ef`; adapter SHA-256 is
`469cfea8dae8aa3295462b84a94747a5a2e413727bffa8af6dff551c6171a758`.
The raw schema-v4 report remains local at `state/arena-v2-aider-screening-9b.json`; raw SHA-256 is
`c5a08be7b2d98075656ad77c398aa2056259b7ff82bf1a9d728aa45cf8604eec`, campaign SHA-256 is
`4996e336be04f20d284454056127cacf2a533e108b380b1249a7fc1df1158b6c`, freeze SHA-256 is
`03ec190ad37a966872fab874dbbc885f7f9368cd10a807a88abda1985b2b4212`, and task-manifest
SHA-256 is `7bcc57ddeae2f5846ee7f3f26075323c0aa3970426b32393e90ac3cb7019d434`.

## Arena v2 — oh-my-pi admission and screen

The official `@oh-my-pi/pi-coding-agent` 18.0.11 CLI ran on Bun 1.4.0. OMP's built-in tools,
LSP, PTY execution, extensions, skills, rules and prewalk were disabled. A disposable HOME/XDG
tree prevented compatibility importers from reading the operator's Claude, Codex, Cursor or
OpenCode configuration; project MCP discovery was also disabled. The only configured server was
Achilles MCP, acting under the tournament subject, workspace and run identity.

Admission exposed a current OMP startup race before any scored campaign. Its MCP manager waits
only 250 ms for a fresh server's tool list, while the callback that would register a slightly late
server is attached after the race. The Python stdio bridge connected, but the first non-interactive
request contained no tools. The adapter now prestarts one identity-scoped streamable-HTTP MCP
bridge per attempt, waits for its loopback listener, then starts OMP. A diagnostic request capture
proved the resulting OpenAI requests contained exactly the 14 `mcp__achilles_*` tools and zero OMP
built-ins. The corrected clean empty-mean admission passed in 21.4 seconds with 49,585 accounted
tokens; all earlier cells were discarded as infrastructure evidence.

The full campaign completed all 48 cells, all 12 verifier controls passed, every attempt had token
counters and no authority denial occurred.

| Harness | Passed | Pass rate | Median time | Total time | Total tokens | Median tokens | Generated tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Native** | **19/24** | **79.17%** | 38.12s | **1,002.95s** | **688,064** | **17,669.5** | 55,155 |
| oh-my-pi | 17/24 | 70.83% | **31.14s** | 1,013.42s | 1,525,023 | 42,167.5 | **40,921** |

Paired matrix: 16 both passed, 3 Native-only passes, 1 oh-my-pi-only pass and 4 both failed.
Native minus oh-my-pi was +8.33 percentage points with paired bootstrap 95% CI
[-8.33, +25.0] points and exact McNemar p=0.625, so correctness remains inconclusive. OMP's
median attempt was 18.3% faster, but total wall time was 1.0% higher. It generated 25.8% fewer
tokens while consuming 121.6% more total and 138.6% more median tokens, locating the overhead in
replayed input/tool context. Native used 54.9% fewer total tokens.

Native's discordant wins were slugify attempt two, safe join attempt two and JSONL resilience
attempt one. OMP's sole discordant win was configuration precedence attempt two. Its slugify
attempt two ended as a retained `harness_error` at 178.74 seconds with `Deadline exceeded` rather
than being mistaken for a verifier failure. Both harnesses failed configuration precedence attempt
one, CSV/decimal attempt one and both JavaScript prototype-pollution attempts. Most importantly,
Native passed safe join 2/2 while OMP passed only 1/2.

oh-my-pi is therefore **not promoted and is screened lower-priority**. Its lower median latency
and one configuration win do not justify over twice the context, one internal deadline exit and a
non-reproducible path-containment result. The governed adapter remains for future model-specific
retests; the isolated 1.4 GiB runtime is removed. Adapter SHA-256 is
`b29515f5424f9d72fe13a3b3d93fcb1db42ab04f58bfbd46263ba9d66af5c100`; HTTP MCP runner
SHA-256 is `6fd4e6d23319e9380bcb0be96d795e858bcce718a25ba888d2cd6f0a3f9711e1`.

The raw schema-v4 report remains local at `state/arena-v2-oh-my-pi-screening-9b.json`; raw
SHA-256 is `129adfbd5c0d175532b6c1c89ae2e312046bc232e4b2d5efa150920e7b169811`, campaign SHA-256 is
`512ee2487538f7e419244470cfba654d58734d7f9cf897782ac21d484fb95f02`, freeze SHA-256 is
`7cb89de9e836a6456f1af08ea374324643ab6bdcb974b43334999e9835d787eb`, and task-manifest
SHA-256 is `7bcc57ddeae2f5846ee7f3f26075323c0aa3970426b32393e90ac3cb7019d434`.

## Arena v2 — SWE-agent admission and screen

Official SWE-agent 1.1.0 at upstream commit
`3ea751c087f32b16e039a2233dd6eefecef325d5` ran its `DefaultAgent`, official
`bash_only.yaml` templates, single-bash-code-block parser and submit bundle. SWE-ReX did not receive
independent execution authority: its environment was replaced by an Achilles bridge, and every real
shell action crossed the authenticated `run_command` tool with the tournament subject, run and
workspace identity. A disposable HOME/XDG tree isolated operator configuration.

The first shared-router campaign was stopped and discarded after seven task pairs. A concurrent
Qwen3.8-27B load occupied the one-model router, then the Qwen3.5-9B reload exited with a CUDA illegal
memory access. The router exposed `failed: true`, `exit_code: 1`; subsequent no-change timeouts were
therefore infrastructure failures, not contestant evidence. The valid campaign used a dedicated
Qwen3.5-9B endpoint on port 18081 with one 32K slot. A fresh admission passed both lanes (Native
21.83s, SWE-agent 52.05s), and the full campaign restarted from zero. All 48 cells completed, all
12 verifier controls passed, every attempt had token counters and neither lane had an authority denial.

| Harness | Passed | Pass rate | Median time | Total time | Total tokens | Median tokens | Generated tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Native** | **20/24** | **83.33%** | **27.23s** | **685.38s** | **167,652** | **6,749.5** | **34,819** |
| SWE-agent | 14/24 | 58.33% | 84.00s | 2,387.02s | 1,136,091 | 36,838.5 | 84,917 |

Paired matrix: 13 both passed, 7 Native-only passes, 1 SWE-agent-only pass and 3 both failed.
Native minus SWE-agent was +25.0 percentage points with paired bootstrap 95% CI
[+4.17, +45.83] points and exact McNemar p=0.0703. The bootstrap interval excludes zero, while
the exact discordant-pair test does not cross the 0.05 threshold; the direction is strong but the
small screen still warrants the larger finalist league. Native used 71.3% less total wall time,
67.6% less median wall time, 85.2% fewer total tokens and 81.7% fewer median tokens. SWE-agent
generated 143.9% more tokens.

Native's seven discordant wins were both configuration-precedence cells, both cache-collision
cells, both CSV/decimal cells and stable-dedupe attempt one. SWE-agent's sole discordant win was
safe-join attempt one; attempt two timed out and changed four forbidden files. Native failed both
safe-join attempts, so the external loop retains one important security signal. Both harnesses
failed both JavaScript prototype-pollution cells.

SWE-agent had five primary timeouts and changed forbidden files in both cache-collision attempts,
stable-dedupe attempt one, configuration attempt one, CSV attempt one, safe-join attempt two and
JavaScript attempt two. Those are verifier-enforced boundary failures even though the official
prompt says not to modify tests. SWE-agent is therefore **not promoted and is screened
lower-priority**. Its governed adapter remains for model-specific retests; the isolated 677 MiB
runtime is removed. Adapter SHA-256 is
`eba0f0625a412229ff195fd4148ca810e8343e19f8665ec537eda7746282a180`; runner SHA-256 is
`e1eaf29cdda15956c67108801fa0087f0a15e82c73cf49a8507fd73093470d20`.

The raw schema-v4 report remains local at `state/arena-v2-swe-agent-screening-9b.json`; raw
SHA-256 is `2671ee901b0893555ffc8a008836bd28d7ab735e765d8b485174a5611b0cb91b`, campaign SHA-256 is
`a13f3f8fcd308652215d809da06d679019be8b730d6a0b7500fd92318de606e4`, freeze SHA-256 is
`02db3e914ce143f1bbddafa78c45c9ed5f1d54fc485eb2e19826c067a4bdabfd`, and task-manifest
SHA-256 is `7bcc57ddeae2f5846ee7f3f26075323c0aa3970426b32393e90ac3cb7019d434`.

## Arena v2 — Qwen Code admission and screen

Official Qwen Code 0.22.3 from npm, published from upstream commit
`09825973e7d3c3fd07e17909c396aa62f48ce51f`, ran its current headless agent loop. The adapter used
`--safe-mode` to remove project/operator context, hooks, extensions, skills, ambient MCP servers,
custom subagents and discovery commands. It supplied exactly one explicit `achilles` MCP server and
whole-tool deny rules for all 48 built-in/synthetic names in the 0.22.3 registry. Qwen names those
tools `mcp__achilles__*`, so the built-in denies cannot block or impersonate them. Every real read,
command and edit therefore crossed the same identity-, grant- and workspace-scoped Achilles bridge.

Two admission attempts were discarded as wiring evidence. First, progressive MCP discovery raced the
one-shot request and Qwen saw no tools; the adapter now uses Qwen's official
`QWEN_CODE_LEGACY_MCP_BLOCKING=1` compatibility switch. Second, Qwen correctly called only Achilles,
but the child bridge resolved `configs/` relative to the task workspace and failed closed on every
call; the adapter now passes the absolute Achilles config root. The clean admission then passed in
14.18 seconds with 27,258 accounted tokens and zero denials. The full campaign ran on the dedicated
one-slot 32K Qwen3.5-9B endpoint added after F-080. All 48 cells completed, all 12 verifier controls
passed, every cell had token counters and neither lane had an authority denial.

| Harness | Passed | Pass rate | Median time | Total time | Total tokens | Median tokens | Generated tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Native** | **18/24** | **75.00%** | 28.84s | 1,151.95s | **316,349** | **6,939** | 44,266 |
| Qwen Code | 16/24 | 66.67% | **19.61s** | **475.05s** | 685,552 | 27,795 | **14,094** |

Paired matrix: 15 both passed, three Native-only passes, one Qwen-only pass and five both failed.
Native minus Qwen Code was +8.33 percentage points with paired bootstrap 95% CI
[-8.33, +25.00] points and exact McNemar p=0.625. Qwen used 58.8% less total wall time and 32.0%
less median wall time, but 116.7% more total tokens and 300.6% more median tokens. Its one-turn
strategy generated 68.2% fewer tokens while repeatedly paying a roughly 27–28K cached-context bill.

The single Qwen-only win was configuration precedence attempt one; Native won attempt two and both
JSONL-resilience cells. Both lanes failed both CSV/decimal and both JavaScript prototype-pollution
cells. Both failed safe-join attempt one and passed attempt two. Qwen's two repeatable JSONL failures
are the clearest contender-specific correctness gap. Native had two primary timeouts; Qwen completed
every cell inside the primary budget. The result is therefore a real composition tradeoff—Qwen Code
is a fast, low-generation interface around this model, but its lower correctness and 2.17× total
context cost do not justify promotion over Native or Aider.

Qwen Code is **not promoted and is screened lower-priority**. The governed adapter remains for future
model-specific retests; the isolated npm runtime and source checkout are removed. Adapter SHA-256 is
`56734030acae5d6bba10625d5623d221d864aa1bff2c1736695e7e7dd3610929`.

The raw schema-v4 report remains local at `state/arena-v2-qwen-code-screening-9b.json`; raw
SHA-256 is `41caab629dd3202b53ca94c5b201d91ee2040b384605bbda43dcda9e410e6542`, campaign SHA-256 is
`476298ba32b8099616c68c162c1bffb3f327b7be50fe176931c1d3d11d7fc13f`, freeze SHA-256 is
`8f6312c9bb569754947b5dff53abf9439c358199d81cd77cb0d4fe947864c388`, and task-manifest
SHA-256 is `7bcc57ddeae2f5846ee7f3f26075323c0aa3970426b32393e90ac3cb7019d434`.

## Limits and next trigger

The v2 screen is still small and local-model-specific. Native and the retained candidates must defend
their positions in a 20–30 task × 3 finalist league. The planned core harness screen is complete.
Larger mixed repositories, test repair, interruption/resume, research, memory, prompt injection,
delegation and browser work remain separate leagues. Harness selection is deliberately open.
