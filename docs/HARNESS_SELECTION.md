# Harness selection report — 2026-08-30

## Decision

**NativeAgentLoop remains the provisional incumbent, not a final universal winner.** Arena v2
has now screened Prime Agent, DeepSeek Harness/Cordis and mini-SWE-agent. None produced a
statistically significant paired correctness difference at 24 observations, while Native kept
a material efficiency advantage in every screen. OpenHands, Aider, oh-my-pi and SWE-agent are
still untested under v2 and must be screened before a final.

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

## Limits and next trigger

The v2 screen is still small and local-model-specific. Native and Prime must defend their
positions in a 20–30 task × 3 finalist league after the remaining harnesses are screened.
Larger mixed repositories, test repair, interruption/resume, research, memory, prompt injection,
delegation and browser work remain separate leagues. Harness selection is deliberately open.
