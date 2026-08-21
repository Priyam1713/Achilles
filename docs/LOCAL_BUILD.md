# Local build plan for this workstation

## Verified target

- Windows host with Ubuntu 24.04 on WSL2
- NVIDIA GeForce RTX 5070 Ti Laptop GPU, 12,227 MiB VRAM
- 32 GB physical host RAM; WSL currently exposes about 25 GiB RAM plus 32 GiB swap
- repository drive: about 294 GB free
- WSL ext4 volume: about 923 GB free

The correct topology is therefore hybrid:

- Windows: kernel API, policy, Credential Manager, future UI Automation
- WSL ext4 (`~/.local/share/sovereign-ai`): checkpoints, GGUFs, CUDA runtimes,
  caches, isolated ML environments and generated media
- repository: source, manifests, documentation and the static UI only

Windows and Linux Python environments are deliberately outside the repository so they
cannot overwrite one another.

## Installation profiles

- `core` (default and recommended; ~78 GB of current checkpoint downloads; requires at
  least 150 GB free): cognition, text retrieval/reranking, documents, speech, TTS,
  perception and basic forecasting.
- `workstation` (~212 GB additional on top of `core`, ~290 GB total; requires at least
  500 GB): adds multimodal retrieval, advanced audio, creative media, segmentation,
  tabular modelling, medical vision and the GUI-fallback/computer-use model (`ui-tars-1.5-7b`,
  33.19 GB — moved out of `core` in `docs/FIXES.md` F-014 because no computer-control
  provider is wired up in any profile yet, so it cannot currently be invoked regardless of
  which profile installs it).
- `full` (requires at least 700 GB): every final manifest model, including niche protein,
  materials, Earth-observation and formal-proof specialists.

Profiles control both checkpoint downloads and isolated dependency environments. Gated
checkpoints still require accepting their upstream terms; the installer never accepts them.

## Build sequence

Do not execute the heavyweight build sequence until the D-011 pre-build gates in
[the research ledger](../knowledge/research.md) pass. In particular, pin mutable runtime,
specialist, package and container inputs; establish service identity/configurable ports; and
preserve the unrelated router currently listening on port 8080 (`docs/FIXES.md` F-018/F-019
resolved the collision itself, but the general rule still governs new installs). The first
physical run after those corrections should use `core` -- now the default, not an
intermediate step -- establish a benchmark/recovery baseline, and only then deliberately
expand to `workstation` if that broader coverage is actually wanted.

Run from PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
$env:HF_TOKEN = "YOUR_TOKEN_AFTER_ACCEPTING_REQUIRED_MODEL_TERMS"
./Install.ps1
```

To install `workstation` instead, deliberately:

```powershell
./Install.ps1 -Profile workstation
```

To avoid gated models on either profile, add `-WithoutGatedModels`:

```powershell
./Install.ps1 -WithoutGatedModels
```

The installer performs these gates in order:

1. verifies WSL2 and installs Windows Python 3.12 if missing;
2. creates separate Windows control-plane and WSL tool environments;
3. provisions Docker/OpenShell prerequisites;
4. builds current llama.cpp with CUDA and records exact runtime commits;
5. installs isolated specialist environments;
6. checks that heavyweight storage is WSL-native and sufficiently large;
7. checks official release sources, audits every selected upstream/artifact source, reports
   its current size, resolves exact Hugging Face revisions and downloads the selected profile;
8. syncs Qwen3.8 UD-Q4_K_M/MTP/mmproj artifacts and converts Qwen3.5 to Q6_K;
9. loads every cognition profile and requires a real inference response;
10. prewarms supported specialists, validates the registry, runs tests and runs the doctor.

Start afterward with `./Run.ps1`; open `http://127.0.0.1:7788/ui`. Long work can be
submitted through `POST /jobs` and inspected or cancelled through `/jobs/{id}`.

After the router is running, compare the optional MTP path on this exact build with:

```powershell
uv run python scripts/benchmark_qwen38_mtp.py
```

The report is written to `state/qwen38-mtp-benchmark.json`; it never changes routing.

## Resource policy

Only one GPU-heavy job runs at once. llama.cpp keeps the 9B control brain resident when
possible and unloads before large specialist/media work. Its preset currently targets 1.8 GB
free VRAM while the kernel scheduler reserves 1.6 GB; unify this into one tested policy value
before the build. Qwen3.8-27B uses UD-Q4_K_M with partial GPU offload,
16K context and Q8 KV by default. The MTP preset is opt-in until it wins a local A/B run.
