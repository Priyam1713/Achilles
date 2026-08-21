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
