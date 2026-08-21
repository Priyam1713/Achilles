# Local Sovereign AI

A hardware-aware local AI kernel whose defining rule is:

```text
THE MODEL IS A COMPONENT. THE KERNEL IS THE SYSTEM.
```

No model, harness, sandbox, inference engine or UI owns the architecture. The kernel owns policy, state, capability routing, resource arbitration, transactions, verification, provenance, checkpoints and audit. Everything fast-moving sits behind adapters.

## What is implemented

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
- contextual tool discovery
- deterministic post-condition verification
- hierarchical computer-control interface: API → CLI → plugin → DOM → UIA → vision GUI
- watcher/event bus
- durable background job journals with cancellation, result/error records and restart
  interruption detection (automatic resume/retry is not implemented yet)
- native collaboration rooms with human/agent identities, threads, reactions, shared canvases,
  mention-to-job dispatch and per-room tamper-evident history
- local SearXNG deployment option
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

From PowerShell in the repository root. The recommended `workstation` profile is
matched to this RTX 5070 Ti Laptop GPU; heavy artifacts are stored on WSL ext4,
not the smaller/slower `D:` filesystem:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
$env:HF_TOKEN="YOUR_TOKEN_IF_NEEDED"
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

## Run

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
