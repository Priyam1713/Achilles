# Automation and desktop experience plan

> Status: architecture selected; concrete browser, Windows UI and desktop-shell providers
> are not yet implemented. See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

## What exists today

The repository already contains:

- the ordered `ComputerController` interface and tiers for API, CLI, plugin, browser DOM,
  accessibility and vision GUI;
- fail-closed policy evaluation and explicit approvals for risky actions;
- an OpenShell execution adapter with hardened Docker fallback;
- a writable-workspace registry;
- durable jobs, events, checkpoints, transactions, verification interfaces and audit data;
- an optional locked Playwright dependency;
- a small browser-served control surface with routing, resources and collaboration rooms.

No concrete computer controller is registered yet. Direct Playwright automation, browser
profiles, Playwright MCP, a Windows UIA broker, human takeover, UI-TARS execution and a
Tauri desktop application remain planned work.

## Strategy hierarchy

Choose the most structured, deterministic, least privileged mechanism that can satisfy the
post-condition:

```text
native application API / library
  ↓
CLI, scripting interface, application plugin or structured protocol
  ↓
browser DOM + accessibility through direct Playwright
  ↓
Windows UI Automation through the host broker
  ↓
vision-guided GUI action
  ↓
raw brokered mouse/keyboard input
  ↓
human takeover
```

MCP is not a rung in this ladder. It is an interoperability transport that may expose an API,
CLI, Playwright operation or another capability to a harness. A published MCP tool never
grants authority; the kernel still checks identity, run grants, workspace, data class,
secrets, budgets, approval and verification.

## Selected automation stack

| Concern | Selected implementation | Current state |
| --- | --- | --- |
| HTTP/API | `httpx` and generated clients where a stable OpenAPI schema exists | Base dependency present; capability adapters pending |
| Command execution | OpenShell-controlled Bash/PowerShell; Docker fallback | Broker implemented; target-machine exercise pending |
| Browser control contract | Direct typed Playwright worker | Selected; optional dependency locked; provider pending |
| Full local browser | Dedicated Playwright Chromium contexts/profiles | Selected; pending |
| Harness compatibility | Official `@playwright/mcp` adapter | Optional; pending; never a security boundary |
| Stateless public web | Cloudflare Kitesurf or Quick Actions | Optional external backend, disabled by default |
| Exploratory browsing | Browser Use | Benchmark-only strategy that returns untrusted trajectories |
| Windows structured UI | FlaUI UIA3 with UIA2 compatibility fallback | Selected; .NET broker pending |
| Windows host boundary | Unelevated per-user interactive-session .NET broker | Selected; pending |
| Visual GUI | Locally runnable UI-TARS-class model behind the broker | Benchmark candidate |
| Raw input | Windows `SendInput`, one brokered action at a time | Last-resort provider; pending |
| Capture | Playwright screenshots/traces and Windows Graphics Capture | Pending |
| Human intervention | Local observe/pause/takeover/approval surface | Pending |
| Primary human UI | Sovereign Tauri desktop informed by selected Buzz UI patterns | Design/extraction spike pending |
| Recovery/operator UI | Existing local web UI and CLI | Web/CLI implemented at basic level |

## Browser capability

Playwright is the canonical control layer; Chromium and Kitesurf are selectable execution
backends, not competing agent APIs.

```text
kernel BrowserCapability
  ├─ direct Playwright worker (default internal contract)
  │    ├─ local dedicated Chromium
  │    └─ Cloudflare Kitesurf over CDP (optional external/public/stateless)
  ├─ official Playwright MCP (harness compatibility)
  └─ Browser Use strategy (exploration only)
```

The direct worker owns deterministic commands, timeouts, downloads, traces, network events,
post-conditions and backend-independent result schemas. Agents do not receive raw Playwright
objects or CDP access.

### Browser modes

| Mode | Model involvement | Typical use |
| --- | --- | --- |
| deterministic | none after a procedure is promoted | Known recurring form/report workflow |
| semantic DOM | small model selects among bounded accessible candidates | “Download the latest invoice” |
| exploratory | sandboxed agent loop controls typed browser operations | Unfamiliar public site |
| visual | vision model proposes one coordinate action | Canvas/inaccessible/remote visual surface |

An exploratory success becomes a `SkillCandidate`, not executable trusted automation. The
system extracts selectors/actions, replays them in an isolated profile, injects layout and
network failures, verifies post-conditions and only then promotes a signed `SkillVersion`.

### Backend routing

Kitesurf is eligible only when all of these are established:

- target URLs and submitted content are public;
- no private workspace data, credential, cookie or authenticated state is required;
- the target does not depend on localhost, the private LAN, video, WebGL, a real browser TLS
  fingerprint, pixel fidelity or a long-lived session;
- external processing is enabled by user policy;
- the Cloudflare credential and quota are available;
- the operation has a local fallback or an honest external-only failure result.

Uncertainty routes to local Chromium. Kitesurf remains disabled in strict-local mode. Its
vendor-reported CPU/RAM advantages are hypotheses until benchmarked on our actual workload.

### Browser profiles and authentication

Never automate the user's everyday Chrome/Edge profile. Use kernel-managed profile records
and dedicated user-data directories for anonymous research, named services and ephemeral
high-risk work.

Each profile has:

- a scope owner and permitted agent/run roles;
- allowed data classifications and domain/network policy;
- isolated cookies/storage, download quarantine and audit history;
- an expiry/rotation policy and a single-writer session lease;
- credential references resolved only by the broker;
- encrypted or OS-protected storage because browser state contains bearer tokens.

For login, the agent navigates to the site and pauses. The user takes over to enter passwords,
OTP, passkeys or solve a challenge. Agents receive the resulting page capability, not the
credential or raw cookie store. Sensitive or irreversible actions still require approval.

## Windows automation broker

FlaUI is the selected UIA wrapper because it supports both UIA3 and UIA2 across common
Windows application types. UIA3 is preferred; UIA2 is a compatibility fallback for
applications whose accessibility trees behave better there.

The broker must run unelevated in the active user's interactive session. A normal Windows
service runs in non-interactive session 0, and a different account/session cannot simply
control the visible desktop. Elevated-window interaction is denied initially; `UIAccess`
would require signing and secure installation and is not assumed.

```text
kernel run + expiring CapabilityGrant
  ↓ local authenticated named pipe with logon-SID DACL
WindowsAutomationBroker (interactive user, unelevated)
  ↓ validate schema / nonce / process / window / action / expiry
FlaUI UIA3 → UIA2 fallback → one SendInput action if explicitly granted
  ↓
structured before/after state + screenshot/hash + post-condition
```

The broker accepts a closed typed schema, never PowerShell, arbitrary code, arbitrary paths
or raw secret values. Every action binds to a run, capability grant, expected process/window,
deadline and post-condition. It rejects stale/replayed nonces, disallowed executables,
unexpected focus/window ownership, elevation boundaries and actions outside the active grant.

Raw coordinate actions additionally require stable window bounds and a visual anchor. They
are one-action leases; the broker recaptures state before another action is considered.

## Application-specific control

Structured application interfaces remain ahead of GUI automation:

| Surface | Preferred route |
| --- | --- |
| Git | Git CLI/library in an isolated worktree |
| VS Code | CLI, extension/LSP or filesystem operations |
| LibreOffice | UNO API/headless CLI, then UIA |
| Blender | Blender Python API |
| GIMP | procedure database/CLI where available |
| Images | ImageMagick/OpenCV |
| Video/audio | FFmpeg/SoX |
| PDF/documents | document libraries, Poppler/OCR, then LibreOffice |
| Databases | native drivers and transactions |
| Docker | Docker API/CLI through the execution broker |
| Email/calendar/contacts | provider API or IMAP/SMTP/CalDAV/CardDAV |
| Windows services | narrow service-management adapter with approval |
| Websites | API first, direct Playwright second |

## Vision GUI boundary

Use the underlying UI-TARS-class model/SDK as a vision provider, not UI-TARS Desktop as our
product or authority. Its desktop project is still evolving and its current documentation
does not provide a stable Windows foundation for us.

The vision model receives a redacted screenshot and bounded goal, proposes one action, and
cannot execute it. Policy checks the target process/window, sensitive regions, coordinate,
action and active grant before the Windows broker acts. A fresh capture and post-condition
follow every action.

The resource scheduler may have to unload/offload Qwen, load the GUI specialist, perform the
bounded workflow, release it and restore the normal brain. Visual control is therefore the
expensive fallback.

## Primary desktop experience

The product's primary human surface should become a local desktop control center. The CLI is
for installation, recovery, headless runs, scripting, SSH and diagnostics. The existing web
UI remains a lightweight recovery/bootstrap surface.

Planned desktop areas are: Today, Chat, Agent Roster, Rooms, Jobs/Runs, Workflows, Computers,
Browser Activity, Memory, Models/Resources, Approvals, Audit/Evaluation and Settings. Every
view talks to a typed kernel client; no renderer owns durable state, policy or credentials.

Block Buzz is an Apache-2.0 design and code source, not an application dependency. Before
copying code, run a pinned-commit extraction spike that classifies each candidate component:

- portable presentation component with clean inputs/outputs;
- reusable after replacing Nostr/Buzz types with kernel view models;
- too coupled to Buzz relay/auth/events and better rebuilt from the interaction pattern.

Copied/adapted files retain required notices and source provenance. The likely reusable
targets are the Tauri/React shell patterns, virtual timeline, Markdown/code/diff rendering,
rooms/threads/reactions, canvas interactions, notifications/tray and E2E setup. The Nostr
client, relay, identity, workflow, job, permissions, audit and storage layers are excluded.

The Tauri shell must authenticate to the local kernel with an installation/session token or
an equivalent protected IPC channel. Binding a privileged unauthenticated API to loopback is
not sufficient.

## Implementation order

1. Add controller conformance tests and a typed browser action/result schema.
2. Implement read-only ephemeral local Chromium: navigate, inspect accessibility/DOM,
   screenshot and trace.
3. Add deterministic actions, downloads/uploads, network policy and post-condition checks.
4. Add managed profiles, OS-protected state, session leases and human takeover.
5. Add official Playwright MCP compatibility without bypassing kernel grants.
6. Add optional Kitesurf for public stateless work and benchmark it against local Chromium.
7. Build the Windows broker first in inspect-only mode, then allow bounded UIA actions.
8. Add one-action `SendInput` and capture only after UIA verification tests exist.
9. Benchmark Browser Use exploration and the UI-TARS-class visual provider; promotion paths
   produce evaluated skills rather than silently learned automation.
10. Build a thin Tauri kernel client/shell and perform the Buzz component extraction spike;
    grow the UI by stable backend vertical slices rather than mock screens.

## Explicit exclusions for the first implementation

- control of the user's normal browser profile;
- CAPTCHA bypass, cookie extraction or model-visible passwords;
- arbitrary PowerShell/code through the Windows broker;
- elevated desktop automation or `UIAccess` assumptions;
- Selenium, Puppeteer, Cypress or another duplicate browser-control foundation;
- Browser Use, Stagehand, Skyvern, UI-TARS Desktop, n8n or Buzz as a second kernel;
- Kitesurf for private/authenticated/local-network tasks;
- a Buzz relay/protocol bridge as the final desktop architecture;
- visual/raw-input sessions with unbounded multi-action authority.
