# Windows deployment notes

The target is a Windows workstation, but the system intentionally splits responsibilities:

- Windows: desktop/UI integration, NVIDIA driver, native applications, user credential store
- WSL2/Linux: OpenShell, llama.cpp build/runtime experiments, Pulsar and other Linux-first inference tooling
- isolated Python environments/workers: specialist ML packages

OpenShell currently labels Windows/WSL2 support experimental upstream. The kernel therefore checks availability and keeps a hardened Docker fallback rather than coupling authority to OpenShell's lifecycle.

## Recommended filesystem layout

Keep the repository and model store on a fast NVMe filesystem. For giant-model experiments, benchmark WSL virtual-disk performance versus a native/attached path before assuming SSD streaming will be fast enough.

## One-time prerequisites that the script cannot safely fake

- a working NVIDIA driver visible through `nvidia-smi`
- WSL2 enabled (Windows may require reboot when first enabled)
- enough free disk for final model snapshots/quantization intermediates
- upstream license acceptance for gated checkpoints

Everything else is intended to be scripted and locked.
