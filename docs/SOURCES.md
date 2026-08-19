# Upstream verification sources

This project intentionally records upstream repos/snapshots at install time rather than trusting a static blog list. Key upstreams reviewed for this architecture include:

The dated assessment, decision status, caveats and promotion gates for moving projects live
in [knowledge/research.md](../knowledge/research.md); this file is the shorter source index.

- NVIDIA/OpenShell — execution boundary and declarative policy.
- ggml-org/llama.cpp — GGUF conversion, router-mode dynamic model loading, automatic memory fitting and idle sleep.
- Qwen/Qwen3.8-27B and Qwen/Qwen3.5-9B — core cognition.
- unsloth/Qwen3.8-27B-GGUF — exact UD-Q4_K_M, MTP and vision artifacts for this workstation.
- deepseek-ai/deepseek-harness — official agent harness, isolated as a developer-preview adapter.
- omnigent-ai/omnigent — meta-harness and interoperability reference, not a second kernel.
- vectorize-io/hindsight — retain/recall/reflect memory provider candidate.
- boxlite-ai/boxlite — persistent micro-VM execution-provider candidate for WSL2/KVM testing.
- AMAP-ML/LongHorizon-Harness — manager/executor/auditor and verified-state reference.
- vercel/eve — filesystem-first durable-agent application reference.
- agentgateway/agentgateway — optional MCP/A2A/LLM protocol-edge governance candidate.
- open-gsd/gsd-pi — DB-authoritative project state, worktrees and verification reference.
- yc-software/qm — durable scoped-computer and multi-user boundary reference.
- xai-org/grok-build — Rust coding-harness benchmark candidate.
- NousResearch/hermes-agent — persistent agent, messaging, skills, memory, scheduling and
  subagent reference; candidate subordinate `AgentLoop`/experience adapter only.
- NVIDIA/NemoClaw — official OpenShell-contained Hermes/OpenClaw onboarding reference.
- a2aproject/A2A — external agent interoperability boundary; Agent Cards do not grant trust.
- Cloudflare Kitesurf/Browser Run documentation — optional stateless cloud browser backend.
- Warp software-factory documentation — versioned workflow/DAG and verification concept
  reference; no Warp runtime dependency is selected.
- microsoft/playwright — canonical direct browser-control library.
- microsoft/playwright-mcp — optional harness compatibility surface; upstream explicitly
  states it is not a security boundary.
- FlaUI/FlaUI and Microsoft UI Automation/security documentation — Windows structured UI
  provider and interactive-session/IPC constraints.
- browser-use/browser-use — exploratory browser strategy candidate, not job/policy owner.
- bytedance/UI-TARS and UI-TARS-desktop — visual GUI model/runtime reference; only the model
  boundary is selected for a future benchmark.
- Cloudflare Browser Run/Kitesurf — opt-in public/stateless external browser backend.
- Z.ai GLM-5.3 developer documentation and zai-org Hugging Face organization — release radar;
  GLM-5.3 weights remain pending and are not an install dependency.
- block/buzz — Apache-2.0 design reference for human/agent rooms, mention-driven work,
  threaded evidence and canvases. No Buzz runtime or service is included.
- QwenLM/Qwen3-ASR — primary ASR and forced alignment.
- OpenMOSS/MOSS-Transcribe-Diarize and MOSS-Audio — diarization/audio reasoning.
- OpenBMB/VoxCPM — VoxCPM2 TTS.
- PaddlePaddle/PaddleOCR — document parsing/OCR.
- roboflow/rf-detr, facebookresearch/sam3, ByteDance-Seed/Depth-Anything-3 and UI-TARS — vision/computer use.
- deepbeepmeep/Wan2GP, black-forest-labs/FLUX.2 and ACE-Step — generative media.
- amazon-science/chronos-forecasting, PriorLabs/TabPFN, EvolutionaryScale/ESM, facebookresearch/fairchem, MedGemma, Prithvi and Pythagoras-Prover — data/science specialists.

During `sync_models.py`, both the official upstream and runtime artifact revisions are
resolved and written to `state/model-lock.json`. During runtime installation, exact Git
commits are written to `state/runtime-lock.json`. `check_release_radar.py` observes official
sources but never edits the model manifest or promotes a component.

Do not treat this file as a timeless leaderboard. The local benchmark database is the final authority for this machine.
