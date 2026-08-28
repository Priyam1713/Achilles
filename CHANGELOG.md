# Changelog

All notable public changes to Achilles will be documented here. The project follows
[Semantic Versioning](https://semver.org/) once release tags begin; during pre-alpha,
interfaces and state formats may change without compatibility guarantees.

## [Unreleased]

### Added

- Public-source project documentation, community health files and security analysis workflow.
- Reproducible upstream llama.cpp versus ik_llama.cpp runtime tournament with raw samples,
  robust summaries, resource telemetry and counterbalanced execution order.
- Physical backing-volume checks for sparse WSL2 VHDX model stores.

### Changed

- Reconciled agent harness, routing, durability, memory, observability and computer-control
  candidates into an incumbent-versus-challenger architecture.
- Kept upstream llama.cpp as the dense-GGUF incumbent; IQ4_XS directionally favored upstream,
  while Q6_K throughput remains explicitly inconclusive.

### Fixed

- Included the MCP bridge dependency in the development extra so the complete test suite runs
  in a clean contributor or CI environment.
- Kept lexical memory retrieval available without a specialist worker by avoiding query
  embedding when the scoped vector index is empty.
- Kept mandatory kernel CI on its proven Linux/WSL execution surface while validating the
  Tauri desktop separately on Windows, instead of presenting a hanging native-Windows matrix
  as meaningful coverage.

## [0.1.0] - 2026-08-28

Initial public development baseline: authority kernel, governed tool plane, durable runs and
workflows, resource leases, memory, collaboration, agent-loop adapters, local interfaces,
evaluation harnesses and workstation provisioning.

[Unreleased]: https://github.com/Priyam1713/Achilles/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Priyam1713/Achilles/releases/tag/v0.1.0
