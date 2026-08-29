# Benchmark contract

Achilles benchmarks complete compositions: model, inference runtime, agent loop, context
strategy, governed tools, execution backend and verifier. A result belongs to that tuple. It
is not evidence that any one component is universally best.

## Harness suites

`scripts/harness_tournament.py` exposes versioned task families instead of silently growing
one mutable list:

| Suite | Tasks | Purpose |
| --- | ---: | --- |
| `micro` | 12 | Historical read, context, safety and edit-format baseline. `TASKS` remains an alias to this suite for report comparability. |
| `software-engineering` | 8 | Small repository bug-fix, feature, multi-file, security and robustness tasks with held-out executable contracts. |
| `all` | 20 | Both suites in manifest order. Useful for coverage, not as a single scalar leaderboard. |

List or select tasks without loading a model:

```bash
uv run python scripts/harness_tournament.py --suite software-engineering --list
uv run python scripts/harness_tournament.py --suite software-engineering \
  --task swe-safe-join --task swe-config-precedence --loop native
uv run python scripts/harness_tournament.py --suite all --category bug_fix --repeats 3
```

The first engineering slice intentionally uses dependency-free Python repositories. This
keeps the initial contest about repository reasoning and tool-loop behaviour rather than
package installation or network access. It is not the finished Agent Olympics: realistic
multi-language repositories, test repair, resume/kill, research, memory, prompt injection,
delegation and browser tracks remain separate additions.

## Held-out verification boundary

Engineering fixtures visible to the harness contain the broken repository, but not the
verifier. After the loop terminates, the runner:

1. copies the candidate workspace into a separate verification directory;
2. writes the trusted held-out verifier there;
3. registers that directory read-only;
4. executes the verifier through the normal hardened OpenShell/Docker broker with sync-back
   disabled; and
5. removes the directory from the workspace allow-list.

Candidate code is never imported into the tournament coordinator. Verifiers use only the
standard library and execute without network access. The verification directory remains as
an auditable artefact, but it is not available to the candidate loop while it works.

## Result provenance

Schema version 3 reports include:

- suite, ordered task manifest and manifest hash;
- objective, fixture, checker and verifier hashes, grants and maximum steps;
- Git commit and dirty state;
- loop order, model/capability/mode variables and repeats;
- Python and platform identity;
- token availability, outcome, safety denials, wall time and verifier evidence per attempt;
- per-loop category counts, outcome distribution, pass rate and median/total latency; and
- `promotion_performed: false`.

Long campaigns are written atomically after every completed cell. `--output PATH` chooses a
checkpoint and `--resume` continues it only when the suite manifest, Git revision, loops,
model variables, repetitions and deterministic cell order produce the same campaign hash.
Loop position rotates across tasks and repetitions so one contender is not always first on a
cold machine or last on a warm one. A partial report says `campaign_complete: false`; it is
recoverable evidence, never a finished scorecard.

The default remains `micro` so an old command cannot quietly produce an incomparable report.
Use at least three attempts per stochastic task and hold the model endpoint, tool plane and
workspace fixture constant when comparing loops. `--attempt-timeout` applies one recorded
whole-attempt budget to every loop; subprocess adapters terminate and reap their child before
the coordinator deadline. Do not collapse categories into one winner:
a composition advances only when its task profile improves enough to justify its latency,
memory, authority surface and operational footprint, with no safety regression.

## Admission and promotion

A candidate is admitted when its adapter can run the selected suite through kernel-governed
tools. Admission is not promotion. Promotion additionally requires repeated local evidence,
correct cancellation and failure behaviour, no bypass around grants/workspaces, compatible
licensing, recorded rollback and an explicit decision outside the benchmark runner.
