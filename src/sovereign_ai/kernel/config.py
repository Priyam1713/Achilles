from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


class ConfigBundle:
    """Loads the shared manifest, then merges an optional gitignored local overlay.

    ``configs/models.local.yaml`` lets one operator add models to their own machine --
    something licensed outside the community-shippable set (see
    ``configs/models.local.yaml.example`` and ``knowledge/research.md`` invariant 8), a
    model still under personal evaluation, or simply a checkpoint nobody else has -- without
    touching ``configs/models.yaml``, the file every community install shares. A local model
    id can shadow a manifest one; it cannot appear in ``install-profiles.yaml``, so it is
    never pulled in by a profile-based install, only reached by explicit local routing.
    """

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or os.getenv("SOVEREIGN_CONFIG_ROOT", "./configs")).resolve()
        self.system = self._load("system.yaml")
        self.models = self._load("models.yaml")
        self._merge_local_models()
        self.engines = self._load("engines.yaml")
        self.policies = self._load("policies.yaml")
        self.install_profiles = self._load("install-profiles.yaml")
        self.collaboration = self._load("collaboration.yaml")
        # Optional, and absent means none: consuming the MCP ecosystem is opt-in,
        # because each entry is an arbitrary program this kernel would launch.
        self.mcp_servers = self._load_optional("mcp-servers.yaml")

    def _load(self, filename: str) -> dict[str, Any]:
        path = self.root / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing configuration: {path}")
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _load_optional(self, filename: str) -> dict[str, Any]:
        """Like `_load`, but a missing file is a legitimate configuration."""
        path = self.root / filename
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _merge_local_models(self) -> None:
        path = self.root / "models.local.yaml"
        if not path.exists():
            return
        with path.open("r", encoding="utf-8") as f:
            local = yaml.safe_load(f) or {}
        local_models = local.get("models") or []
        if not local_models:
            return
        by_id = {model["id"]: model for model in self.models.get("models", [])}
        for model in local_models:
            by_id[model["id"]] = model
        self.models["models"] = list(by_id.values())

    def _path(self, key: str, default: str, env_name: str) -> Path:
        """Resolve a configured data path without tying it to the process cwd.

        Environment variables deliberately win over YAML so Windows/WSL launchers
        can share one manifest while keeping large artifacts on WSL's ext4 disk.
        Relative YAML paths remain repository-relative for backwards compatibility.
        """
        raw = os.getenv(env_name) or self.system["system"].get(key, default)
        expanded = Path(os.path.expandvars(os.path.expanduser(str(raw))))
        if not expanded.is_absolute():
            expanded = self.root.parent / expanded
        expanded.mkdir(parents=True, exist_ok=True)
        return expanded.resolve()

    @property
    def state_dir(self) -> Path:
        return self._path("state_dir", "./state", "SOVEREIGN_STATE_DIR")

    @property
    def model_dir(self) -> Path:
        return self._path("model_dir", "./models", "SOVEREIGN_MODEL_DIR")

    @property
    def cache_dir(self) -> Path:
        return self._path("cache_dir", "./cache", "SOVEREIGN_CACHE_DIR")

    @property
    def runtime_dir(self) -> Path:
        return self._path("runtime_dir", "./runtimes", "SOVEREIGN_RUNTIME_DIR")
