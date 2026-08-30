# Harness selection report — 2026-08-30

## Decision

**NativeAgentLoop remains the provisional incumbent, not a final universal winner.** Arena v2
has now screened Prime Agent and found no statistically significant correctness difference.
Prime remains a finalist candidate; DeepSeek/Cordis, mini-SWE-agent, OpenHands, Aider,
oh-my-pi and SWE-agent are still untested under v2 and must be screened before a final.

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

## Limits and next trigger

The v2 screen is still small and local-model-specific. Native and Prime must defend their
positions in a 20–30 task × 3 finalist league after the remaining harnesses are screened.
Larger mixed repositories, test repair, interruption/resume, research, memory, prompt injection,
delegation and browser work remain separate leagues. Harness selection is deliberately open.
