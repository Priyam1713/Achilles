# Security model

## Threat model

Assume all of these can be malicious or wrong:

- web pages
- emails/messages
- retrieved documents
- model output
- MCP/tool descriptions
- downloaded code
- package install scripts
- generated shell commands
- collaboration-room messages, mentions, canvases and agent replies

The model is never the security boundary.

## Trust labels

The kernel uses explicit trust labels, including `untrusted_web`, `untrusted_document`,
`untrusted_collaboration`, `untrusted_model_output`, `execution_result`, and
`verified_result`.

Untrusted content cannot directly authorize mutation, execution or credential access.
Prompt text saying “ignore policy” has no ability to alter kernel policy.

## Collaboration rooms

The public local collaboration endpoints accept human-authored messages only; agent and
kernel identities cannot be impersonated through those endpoints. Agent mentions create
chat jobs with no tool authority. Room context is explicitly framed as untrusted data before
it reaches a model, and replies are recorded as `untrusted_model_output`.

Room events are append-only and chained using SHA-256 over canonical event content plus the
previous event hash. A separate room-head/count anchor detects edits, deletion and reordering
under normal database corruption or partial modification. It is tamper-evident, not a
substitute for an offline signed backup or a multi-party signature system.

## Secrets

Secrets live in the OS credential store. Prompts/tool plans should reference `secret://name`, not receive the raw token. The execution boundary resolves credentials only when policy permits it.

## Execution

Preferred boundary: NVIDIA OpenShell when healthy. The supplied default policy permits the sandbox working directory and `/tmp`, while ordinary outbound network policy is empty/deny-by-default. Managed inference is a separate route.

Windows/WSL2 support remains an upstream moving target, so the kernel treats OpenShell as replaceable. The Docker fallback uses no network, read-only root filesystem, all capabilities dropped, no-new-privileges, PID/memory/CPU limits and only the selected workspace mounted read/write.

## Host actions

Host-wide writes/execution, destructive GUI operations, unknown network POSTs and credential use are high-risk operations and require explicit approval under the default policy.

## Verification before commit

Mutating actions should define post-conditions. Examples:

- code: test/compiler/linter
- files: hash/diff/existence checks
- database: query/schema assertions inside native transaction
- browser: DOM assertions and/or screenshot checks
- GUI: resulting application state
- downloads: hash/MIME/signature
- formal proof: Lean verifier

## Rollback

Workflows should use native transactions where possible and saga undo handlers otherwise. A failed verifier is not “mostly done”; it is a failed transaction requiring rollback/repair.

## Workspace capabilities

The execution broker refuses to mount or execute inside arbitrary paths. Writable host directories must be explicitly registered in `state/workspaces.json` through the kernel CLI/API. The kernel source directory is not automatically authorized. This prevents an agent from converting an arbitrary `cwd` into a writable sandbox mount merely by naming it.
