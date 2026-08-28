# Achilles desktop

This directory contains the early Tauri + React operator client for Achilles. It talks to the
authenticated local kernel API; it does not own policy, approvals, task state or model
lifecycle.

## Development

```bash
npm ci
npm run build
npm run tauri dev
```

The Achilles kernel must be running locally for live data:

```powershell
../scripts/start.ps1
```

The desktop client is pre-alpha. See the root [implementation status](../docs/IMPLEMENTATION_STATUS.md)
for supported and incomplete surfaces.
