from __future__ import annotations

from collections import defaultdict

from .config import ConfigBundle
from .types import EngineSpec, ModelSpec, ModelStatus


class CapabilityRegistry:
    def __init__(self, config: ConfigBundle):
        self.config = config
        self.models: dict[str, ModelSpec] = {}
        self.engines: dict[str, EngineSpec] = {}
        self.by_capability: dict[str, list[str]] = defaultdict(list)
        self._load()

    def _load(self) -> None:
        for raw in self.config.models.get("models", []):
            model = ModelSpec.model_validate(raw)
            self.models[model.id] = model
            if model.status != ModelStatus.EXCLUDED:
                for capability in model.capabilities:
                    self.by_capability[capability].append(model.id)

        for engine_id, raw in self.config.engines.get("engines", {}).items():
            self.engines[engine_id] = EngineSpec(id=engine_id, **raw)

    def models_for(self, capability: str, include_candidates: bool = True) -> list[ModelSpec]:
        result = []
        for model_id in self.by_capability.get(capability, []):
            model = self.models[model_id]
            if model.status == ModelStatus.FINAL or include_candidates:
                result.append(model)
        return result

    def capabilities(self) -> list[str]:
        return sorted(self.by_capability)

    def validate(self) -> list[str]:
        """Manifest self-consistency checks, not a source-authenticity check.

        `source_reviewed` (FIXES.md F-016, formerly named `verified_source`) is a
        maintainer attestation set by whoever wrote the manifest entry -- it proves a
        human looked at the source, not that a machine confirmed it resolves. The actual
        machine check of whether a source still resolves lives in `verify_sources.py`,
        run at install time.
        """
        errors: list[str] = []
        for model in self.models.values():
            if model.status != ModelStatus.EXCLUDED and not model.source_reviewed:
                errors.append(f"{model.id}: non-excluded model lacks source_reviewed=true")
            if model.install_policy == "artifact":
                artifact = model.artifact or {}
                if not artifact.get("source"):
                    errors.append(f"{model.id}: artifact install policy lacks artifact source")
                if not artifact.get("source_reviewed"):
                    errors.append(f"{model.id}: artifact source lacks source_reviewed=true")
            for engine in model.preferred_engines:
                if engine not in self.engines:
                    errors.append(f"{model.id}: references unknown engine {engine}")
        profiles = self.config.install_profiles.get("profiles", {})
        for profile_id, profile in profiles.items():
            parent = profile.get("extends")
            if parent and parent not in profiles:
                errors.append(f"install profile {profile_id}: unknown parent {parent}")
            for model_id in profile.get("models", []):
                model = self.models.get(model_id)
                if model is None:
                    errors.append(f"install profile {profile_id}: unknown model {model_id}")
                elif model.status == ModelStatus.EXCLUDED:
                    errors.append(
                        f"install profile {profile_id}: includes excluded model {model_id}"
                    )
        return errors
