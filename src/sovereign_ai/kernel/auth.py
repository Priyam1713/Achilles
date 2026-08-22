from __future__ import annotations

import hmac
import os
import secrets
import stat
from pathlib import Path


class SessionAuth:
    """A generated, OS-file-protected local session token.

    Fixes FIXES.md F-004: mutation endpoints previously had no authentication at all, so
    any local process could drive the kernel. This is deliberately not a full login system
    -- there is one operator and one machine. It is the same pattern the project already
    uses for the SearXNG secret: a generated local secret rather than a checked-in
    credential, minted once and reused, not rotated per request.

    A file rather than the OS keyring, because the token must be readable by both the
    native Windows control-plane process and the browser page served at ``/ui`` -- the
    keyring backends differ across that boundary and are not the right tool for a value the
    frontend itself needs to hold.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._token = self._load_or_create()

    def _load_or_create(self) -> str:
        if self.path.exists():
            existing = self.path.read_text(encoding="utf-8").strip()
            if existing:
                return existing
        token = secrets.token_hex(32)
        self.path.write_text(token, encoding="utf-8")
        # Owner-only permissions. Best-effort: Windows filesystems ignore POSIX bits, but
        # the file already lives under the kernel's own state directory, not a shared one.
        try:
            os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        return token

    @property
    def token(self) -> str:
        return self._token

    def verify(self, presented: str | None) -> bool:
        if not presented:
            return False
        return hmac.compare_digest(presented, self._token)


def allowed_hosts(bind: str, port: int) -> set[str]:
    """Hostnames this installation should accept in the Host header.

    Used to reject DNS-rebinding attempts: a page served from a public domain whose DNS
    resolves to 127.0.0.1 can still make the victim's browser issue same-origin-looking
    requests, but it cannot control what Host header a *legitimate* loopback client sends.
    """
    loopback = {"127.0.0.1", "localhost", "[::1]", "::1"}
    if bind not in ("0.0.0.0", "::"):
        loopback.add(bind)
    return {f"{host}:{port}" for host in loopback} | loopback


def desktop_app_origins() -> set[str]:
    """Full `Origin` header values a legitimate Tauri desktop client can present.

    The Tauri desktop app (FIXES.md, Tier 6 desktop product) runs its webview on its own
    origin, distinct from the kernel API's own `127.0.0.1:<port>` -- `http://localhost:1420`
    during `tauri dev` (a Vite dev server port, not this API's port), and
    `http://tauri.localhost` for a built app on Windows (Tauri v2's WebView2 custom
    protocol origin; `tauri://localhost` is the equivalent on macOS/Linux). Both are
    browser/webview-internal origins a remote attacker page cannot forge for its own
    cross-origin request -- unlike an arbitrary DNS-rebound hostname, which is exactly
    what `allowed_hosts`'s Host-header check above still independently defends against.
    Allowlisting these specific origins for CORS is therefore a second, still-precise
    allowlist entry, not a loosening of the DNS-rebinding defense.
    """
    return {"http://localhost:1420", "http://tauri.localhost", "tauri://localhost"}
