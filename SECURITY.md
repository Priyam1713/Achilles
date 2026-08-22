# Security policy

This file is the **vulnerability reporting policy**. The system's security *architecture* —
trust labels, capability grants, approvals, sandboxing, secret handling — is documented
separately in [`docs/SECURITY.md`](docs/SECURITY.md).

## Reporting a vulnerability

**Do not open a public issue for a security problem.** Report it privately through GitHub's
private vulnerability reporting on this repository ("Security" → "Report a vulnerability"),
which creates a confidential advisory visible only to maintainers.

Please include: what an attacker can do, the smallest reproduction you have, the commit or
release you tested, and your platform (Windows/WSL2 version, GPU, install profile). A working
proof of concept is welcome but not required.

You will get an acknowledgement within a week. Because this is a small project, please assume
good faith and slower timelines than a commercial vendor; if a report is genuinely urgent, say
so explicitly in the first message.

## Scope

Achilles runs untrusted model output against a real machine, so the interesting boundaries are
worth naming.

**In scope, and taken seriously:**

- Any path by which model output, retrieved content, a tool description, an MCP server, a
  skill file or a collaboration message causes an action the policy engine did not authorise.
- Escapes from the execution sandbox (OpenShell or the Docker fallback) to the host.
- Reading, exfiltrating or logging a secret that the secret-handle design is meant to keep out
  of prompts, events and configuration.
- Bypassing local API authentication, the Host/Origin checks, or an approval requirement.
- Memory scope violations: retrieving content a scope ACL should have excluded.
- Tampering with the append-only event chain or the audit record without detection.

**Known and documented, not vulnerabilities in themselves:**

- Indirect prompt injection into untrusted content. The kernel's design assumption is that
  this *will* happen; the defence is that untrusted content cannot authorise action. Reports
  showing an injection that leads to an *unauthorised action* are in scope and valuable.
  Reports showing only that a model can be talked into saying something are not.
- A model producing wrong, biased or unsafe *text*. Model alignment is not this project's
  security boundary; what the kernel lets a model *do* is.
- Anything requiring an attacker who already has your user account on your machine — the local
  API is loopback-only and authenticated with a file only that user can read.

## Supported versions

The project is pre-1.0 and only the current `main` branch receives fixes. There is no
backport policy yet.

## Model weights

Model weights are downloaded from third-party upstreams and are not part of this repository.
Vulnerabilities in an upstream model or runtime should be reported to that project; tell us
too if Achilles's use of it makes the impact worse.
