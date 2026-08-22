# Achilles

*(formerly, and still architecturally, Local Sovereign AI — see `knowledge/research.md` `D-018`.
The Python package remains `sovereign_ai` until a rename is scheduled with its own migration.)*

A hardware-aware local AI kernel whose defining rule is:

```text
THE MODEL IS A COMPONENT. THE KERNEL IS THE SYSTEM.
```

No model, harness, sandbox, inference engine or UI owns the architecture. The kernel owns policy, state, capability routing, resource arbitration, transactions, verification, provenance, checkpoints and audit. Everything fast-moving sits behind adapters.

## What is implemented

> **Read this first.** Research wave 8 (2026-08-22) found that 19 of 21 capability domains
> were unreachable by the agent: `ToolRegistry` had zero tools registered in it and the loop
> had three hard-coded ones. **That is now fixed** — 13 tools cover files, search, execution,
> specialists, media, memory and web (`docs/FIXES.md` F-047), and `sovereign run "<task>"` is
> a real front door, live-verified against a local model (F-048).
>
> What is still honestly *not* there: `ComputerController` has **no registered controllers**,
> so there is no browser or desktop control; **7 of 14 specialist workers return HTTP 501**
> (audio reasoning, segmentation, GUI grounding, materials, medical, music), so those are
> reachable-but-unimplemented; nothing **streams** yet; and there is no TUI or desktop task
> composer. See `knowledge/research.md` waves 6-8 and `docs/IMPLEMENTATION_STATUS.md`.


- capability/model registry with source, license/gating and hardware-fit metadata
- dual cognition: fast resident brain + heavyweight quality brain
- llama.cpp router integration with automatic VRAM fitting, dynamic loading/unloading and idle sleep
- heterogeneous inference adapter plane (llama.cpp; vLLM/SGLang candidates; Pulsar optional; specialist dependency islands; WanGP media)
- local benchmark DB that can override internet priors
- GPU heavy-job arbiter
- fail-closed policy engine and explicit trust labels
- Windows→WSL2 OpenShell security bridge + Docker fallback
- OS credential-store secret handles
- append-only events, checkpoint persistence primitives, transaction journal/rollback hooks
- lexical memory, persistent vector adapter, graph memory and provenance metadata
- a real tool plane: `read_file` (ranged), `list_directory`, `write_file`, `edit_file`,
  `delete_file`, `grep`, `glob`, `run_command`, `invoke_specialist`, `generate_media`,
  `search_memory`, `remember`, `web_search` — every one policy-gated, with contextual
  discovery so an agent sees a small relevant roster
- schema-constrained tool calls: the action schema is derived from the registered tools and
  enforced during decoding, with a recorded fallback when a backend cannot honour it
- `AGENTS.md` project instructions, deterministic context compaction, and shadow-git
  file-state checkpoints so an agent's edit can be undone
- deterministic post-condition verification
- hierarchical computer-control interface: API → CLI → plugin → DOM → UIA → vision GUI
  (**interface only - no controller is registered, so no computer control executes**)
- watcher/event bus
- durable background job journals with cancellation, result/error records and restart
  interruption detection (automatic resume/retry is not implemented yet)
- native collaboration rooms with human/agent identities, threads, reactions, shared canvases,
  mention-to-job dispatch and per-room tamper-evident history
- local SearXNG deployment option (**deployment only - nothing in the kernel queries it**)
- exact Hugging Face revision locks, post-install Git runtime commit records and a
  non-promoting official release radar
- isolated specialist environments so conflicting ML stacks cannot poison the kernel
- no-build local control UI
- one-go Windows bootstrap, start and stop scripts

## One-go installation

> **Pre-build gate:** do not run the heavyweight `workstation` bootstrap yet. Complete
> decision D-011 in [knowledge/research.md](knowledge/research.md) first: migrations, local
> authentication and bounded job/run recovery. Then perform the smaller `core` physical
> baseline before expanding the profile.
>
> Two of the original gate's findings are now closed. Upstream runtime inputs are pinned to
> immutable commits in `configs/runtime-sources.env`. The port collision was **resolved in
> commit `b1a5b29`**, which moved this installation's llama.cpp router from `8080` to `18080`
> and added a service-identity probe so startup refuses to adopt a foreign listener. The
> other local router on `127.0.0.1:8080` is still running and is left strictly alone.
>
> Verify before every install rather than trusting this paragraph:
>
> ```powershell
> uv run python scripts/verify_host.py --check-ports
> ```
>
> That check enumerates **both** the Windows host and the WSL2 namespace. Checking only the
> host is not a weaker check, it is the wrong one: WSL2 forwards connections to services bound
> inside the distro but does not publish their listening sockets in the Windows TCP table, so
> a host-only scan reports a busy port as free. See `docs/FIXES.md` F-019.

From PowerShell in the repository root. `core` (~78 GB) is the default and recommended
starting profile — a genuinely useful daily assistant: coding, retrieval, documents,
speech. Heavy artifacts are stored on WSL ext4, not the smaller/slower `D:` filesystem:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
$env:HF_TOKEN="YOUR_TOKEN_IF_NEEDED"
./Install.ps1
```

`workstation` adds ~212 GB more (creative/audio/vision/computer-use/data specialists, ~290
GB total) on top of `core` — install it deliberately once you know you want that coverage,
not by default (`docs/FIXES.md` F-014):

```powershell
./Install.ps1 -Profile workstation
```

The installer never accepts licenses for you. Accept upstream gated terms first and set
`HF_TOKEN`; use `-WithoutGatedModels` when you want to skip them.

Use `-WithoutGatedModels` to skip gated checkpoints. `core` is the smaller daily-assistant
profile; `full` adds niche scientific specialists. The installer can provision Python 3.12
through `winget` when Windows Python is absent and keeps Windows/WSL environments separate.

The bootstrap is designed to provision WSL dependencies, install OpenShell and replaceable
inference runtimes, create isolated CUDA/Python worker environments, check official release
sources, download revision-resolved model snapshots, prepare the Qwen GGUFs, perform actual
llama.cpp load/inference smoke tests, validate the registry and run kernel tests. Its runtime
and specialist sources must be made immutable before this path is treated as reproducible.

## Give it a task

```powershell
uv run sovereign workspace add C:\path\to\your\project
uv run sovereign run "summarise what this project does and how its tests run" --workspace C:\path\to\your\project
```

Every step prints as it happens with its own timing, because on this hardware an
undifferentiated wait is the worst possible way to present a slow model. Mutating actions are
refused unless a `CapabilityGrant` covers them or you pass `--approve`; that refusal is the
kernel working, not a bug. `uv run sovereign tools` lists what an agent can actually invoke.

## Run the control plane

```powershell
./scripts/start.ps1
```

Open the local control surface at `http://127.0.0.1:7788/ui`.

The control surface includes `Commons` and `Build Lab` rooms. Mention `@swift` for a
fast coordination response, `@sage` for careful synthesis, or `@forge` for deep
engineering review. Agent responses remain untrusted model output and cannot authorize
execution, writes or credential access.

Stop:

```powershell
./scripts/stop.ps1
```

## Useful diagnostics

```powershell
uv run sovereign preflight
uv run sovereign route reasoning --mode deep
uv run sovereign route ocr --mode smart
uv run python scripts/doctor.py --strict
uv run python scripts/check_release_radar.py
```

## Important truth about the artifact

This repository has been syntax-checked and kernel-tested here, but the hundreds of gigabytes of upstream checkpoints cannot be downloaded or benchmarked against your physical GPU from this execution environment. The bootstrap performs those hardware-dependent steps on the target workstation and writes exact locks and smoke-test artifacts into `state/`. A component is not considered locally proven until those tests pass.

See `docs/ARCHITECTURE.md`, `docs/COLLABORATION.md`, `docs/SECURITY.md`,
`docs/FINAL_STACK.md`, and `configs/models.yaml`.
The machine-specific build sequence is in `docs/LOCAL_BUILD.md`.
The selected browser, Windows UI, human-takeover and desktop-shell design is in
`docs/AUTOMATION.md`.
The dated reasoning, evaluated upstreams, rejected alternatives, and recheck triggers live
in [knowledge/research.md](knowledge/research.md).
Confirmed defects, their evidence, and the order in which they are being fixed live in
[docs/FIXES.md](docs/FIXES.md).

## Licence and contributing

Achilles is licensed under the [Apache License 2.0](LICENSE). Adapted third-party designs and
formats are recorded in [NOTICE](NOTICE); model weights are downloaded from their own
upstreams under their own terms and are not covered by this licence.

Contributions are welcome — read [CONTRIBUTING.md](CONTRIBUTING.md) first, because this
project has two non-negotiable rules (open source end to end, and the kernel owns authority)
that shape what can be merged. Security issues go through [SECURITY.md](SECURITY.md), not
public issues.
