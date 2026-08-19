from __future__ import annotations

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "infra" / "searxng" / "settings.yml.template"
TARGET = ROOT / "infra" / "searxng" / "settings.yml"


def main() -> None:
    if TARGET.exists():
        print(f"SearXNG settings already exist: {TARGET}")
        return
    text = TEMPLATE.read_text(encoding="utf-8")
    secret = secrets.token_urlsafe(48)
    TARGET.write_text(text.replace("__SEARXNG_SECRET__", secret), encoding="utf-8")
    print(f"Generated private SearXNG settings: {TARGET}")


if __name__ == "__main__":
    main()
