# Final capability stack for this machine

The stack is intentionally **capability-stable but checkpoint-replaceable**. A model is kept only when it adds a distinct capability or materially improves quality/reliability/efficiency on the target hardware. Local benchmark results may demote any brand.

## Harness + authority base

- **NativeAgentLoop — promoted default.** It passed 24/24 held-out software-engineering
  contracts versus Pi's 21/24, used 54.1% fewer accounted tokens and kept the smallest
  operational surface. See [the harness selection report](HARNESS_SELECTION.md).
- **Pi — first challenger; Goose and OpenCode — retained contenders.** They remain explicit
  overrides for future tracks and material version changes, not default dependencies.
- **SovereignKernel — fixed governed fixture.** Every contender reaches the same workspace
  allow-list, expiring grants, policy engine, tool implementations, checkpoints and hardened
  OpenShell/Docker execution. Kernel changes invalidate an active campaign unless they repair a
  proven measurement defect and the campaign restarts from a clean revision.

## Core cognition

- **Qwen3.5-9B Q6_K** — resident/fast control-loop brain through llama.cpp.
- **Qwen3.8-27B UD-Q4_K_M** — heavyweight reasoning/coding/research/vision gear. The
  16.46 GB model uses partial GPU offload, 16K initial context, Flash Attention and Q8 KV.
- **Qwen3.8 MTP Q4_0 candidate** — downloaded for an exact-machine A/B benchmark but not
  routed by default until throughput, draft acceptance and stability all improve.
- **Pulsar runtime only** — optional experimental giant-MoE backend. No trophy GLM/Kimi/DeepSeek checkpoint is preinstalled until a locally measured task justifies the disk and latency.

llama.cpp runs as a router with one heavy model at a time, automatic GPU-memory fitting and
idle sleep. The current preset uses a 1.8 GB fit target while the kernel scheduler reserves
1.6 GB; the final audit requires one shared resource-policy value before the physical build.
The kernel routes capabilities; llama.cpp owns only GGUF process residency.

## Retrieval + memory

- Octen-Embedding-8B INT8 — text semantic retrieval.
- Qwen3-Reranker-8B INT8 — text reranking.
- Qwen3-VL-Embedding-8B INT8 — first-stage image/screenshot/video-frame retrieval.
- Qwen3-VL-Reranker-8B INT8 — multimodal reranking.
- SQLite FTS5 lexical retrieval.
- local persistent vector adapter + memory graph.
- provenance/trust/confidence/expiry/sensitivity on memories.

## Documents + structured information

- PaddleOCR-VL-1.6 — OCR, layout, tables, formulas and document parsing.
- GLiNER2 Multi — NER, relations, classification and structured extraction.

## Speech + audio

- **Qwen3-ASR-1.7B** — primary multilingual streaming/offline ASR and language ID.
- **Whisper Large-v3-Turbo** — mature broad-language/translational fallback.
- **Qwen3 Forced Aligner 0.6B** — word/timestamp alignment; post-validate timestamps.
- **MOSS-Transcribe-Diarize 0.9B** — long-form speaker-attributed transcription/diarization/timestamps.
- **MOSS-Audio-4B-Thinking** — native non-text audio reasoning: speech/environment/music understanding.
- **VoxCPM2** — TTS, 30-language voice design and controllable voice cloning; replaces Fish S2 Pro because it actually fits this GPU class.

## Vision + computer use

- RF-DETR Large — object detection.
- RF-DETR Keypoint — candidate, not auto-promoted while upstream remains preview-quality.
- SAM 3.1 — segmentation/tracking; install is smoke-test gated because current upstream is still evolving.
- Depth Anything 3 — depth, camera pose and multiview geometry.
- UI-TARS-1.5-7B 4-bit — visual GUI fallback.

Computer control order is deterministic API → CLI → app plugin → Playwright/DOM → Windows accessibility/UIA → visual GUI agent. Pixel clicking is the fallback, never the default.

## Generative media

- FLUX.2 Klein 9B FP8/offload — image generation/editing.
- WanGP — low-VRAM media runtime for video families; exact video checkpoint is benchmark-selected rather than treated as permanent architecture.
- ACE-Step 1.5 — music/song generation.
- FFmpeg/SoX — deterministic editing/transcoding before generative models.

## Data + science

- Chronos-2 — time-series forecasting.
- TabPFN-3 — tabular foundation modelling, license/gate tagged.
- CatBoost/XGBoost/scikit-learn — deterministic baselines that must be tested against TabPFN.
- ESM3 Small Open — protein modelling, non-commercial metadata enforced.
- UMA Medium 1.1 / fairchem — atomistic/materials/molecular modelling.
- MedGemma 1.5 4B — medical multimodal specialist; decision support, never authority.
- Prithvi-EO-2.0-600M — Earth observation.
- Pythagoras-Prover-4B — Lean theorem proving/formal verification.

## Deliberately excluded checkpoints

- generic autonomous-driving VLA — no vehicle sensor/control stack.
- generic robotics VLA — install a robot-specific policy only when actual hardware exists.
- generic recommender checkpoint — train/select from real interaction data.
- generic graph checkpoint — use PyTorch Geometric/task-specific graph models.
- Fish Audio S2 Pro — its practical memory requirement is wrong for this GPU; VoxCPM2 takes the TTS slot.
- Canary-Qwen-2.5B — Qwen3-ASR now covers the primary ASR role more broadly; Whisper remains the distinct fallback.
- Hunyuan-scale image editors that cannot run usefully on the target topology.
- GLM/Kimi/DeepSeek giant weights installed only for prestige rather than measured utility.

## Runtime rule

Every model and runtime is a contestant. `state/benchmarks.db` eventually supersedes manifest priors with measurements from the real workstation. A new model is promoted only after source/license verification, capability tests, task-quality evaluation, resource measurements and rollback-safe registration.

`configs/release-radar.yaml` separately watches official Qwen, DeepSeek and Z.ai sources.
GLM-5.3 is recorded as API-available/weights-pending; a radar hit reports new weights but
cannot add them to an installation profile automatically.
