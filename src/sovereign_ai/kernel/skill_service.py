from __future__ import annotations

from typing import Any

from .runs import RunStore
from .skills import (
    AgentEvaluationRecord,
    AgentEvaluationStore,
    EvaluationVerdict,
    SkillCandidateRecord,
    SkillCandidateStore,
    SkillPromotionError,
    SkillVersionRecord,
    SkillVersionStore,
)


class SkillService:
    """Coordinates the propose -> evaluate -> promote pipeline (docs/ARCHITECTURE.md's
    object-boundary table; `knowledge/research.md`: "A successful trajectory becomes an
    untrusted `SkillCandidate`, then replay/evaluation -- not automatic durable
    automation"; FIXES.md Tier 5).

    Deliberately does not include a "replay this skill" executor -- a promoted
    `SkillVersion` is inert data (an immutable, versioned record of a trajectory that
    once worked) until something else chooses to consult it. Building an engine that
    re-drives an `AgentLoop` against a stored trajectory, handling however the world may
    have diverged since it was recorded, is real, separate, and considerably larger work
    than this pipeline's own scope.
    """

    def __init__(
        self,
        runs: RunStore,
        candidates: SkillCandidateStore,
        evaluations: AgentEvaluationStore,
        versions: SkillVersionStore,
    ):
        self.runs = runs
        self.candidates = candidates
        self.evaluations = evaluations
        self.versions = versions

    def propose_from_run(
        self, run_id: str, objective: str, proposed_by: str
    ) -> SkillCandidateRecord:
        """Propose a candidate from one successful Run's recorded trajectory.

        Requires the Run to have actually succeeded -- a candidate extracted from a
        failed or still-running attempt would be proposing a procedure that is not known
        to work, which is exactly what this pipeline exists to gate against admitting.
        """
        run = self.runs.get(run_id)
        if run is None:
            raise ValueError(f"Unknown run: {run_id}")
        if run.status != "succeeded":
            raise ValueError(
                f"Run {run_id} has status {run.status!r}, not 'succeeded' -- only a "
                "run known to have worked can seed a skill candidate"
            )
        steps = (run.result or {}).get("steps")
        if not isinstance(steps, list) or not steps:
            raise ValueError(
                f"Run {run_id}'s result has no non-empty 'steps' trajectory to propose from"
            )
        return self.candidates.create(run_id, objective, steps, proposed_by)

    def record_evaluation(
        self,
        candidate_id: str,
        verdict: EvaluationVerdict,
        evaluated_by: str,
        *,
        evidence: dict[str, Any] | None = None,
    ) -> AgentEvaluationRecord:
        candidate = self.candidates.get(candidate_id)
        if candidate is None:
            raise ValueError(f"Unknown skill candidate: {candidate_id}")
        evaluation = self.evaluations.create(candidate_id, verdict, evaluated_by, evidence=evidence)
        if candidate.status == "proposed":
            self.candidates.set_status(candidate_id, "evaluated")
        return evaluation

    def promote(self, candidate_id: str, name: str, promoted_by: str) -> SkillVersionRecord:
        """Promote requires a passing evaluation already on record -- there is no path
        that produces a `SkillVersion` without one. This is the "signed promotion"
        `docs/ARCHITECTURE.md` describes: not cryptographic signing (this codebase has no
        such infrastructure), but an auditable, evidence-gated, non-repeatable decision
        with a recorded `promoted_by` and the exact `evaluation_id` that justified it.
        """
        candidate = self.candidates.get(candidate_id)
        if candidate is None:
            raise ValueError(f"Unknown skill candidate: {candidate_id}")
        if candidate.status == "promoted":
            raise SkillPromotionError(f"Skill candidate {candidate_id} was already promoted")
        if candidate.status == "rejected":
            raise SkillPromotionError(f"Skill candidate {candidate_id} was rejected")
        evaluation = self.evaluations.latest_for_candidate(candidate_id)
        if evaluation is None or evaluation.verdict != "pass":
            raise SkillPromotionError(
                f"Skill candidate {candidate_id} has no passing evaluation on record"
            )
        version = self.versions.create(
            name, candidate_id, evaluation.id, candidate.trajectory, promoted_by
        )
        self.candidates.set_status(candidate_id, "promoted")
        return version

    def reject(self, candidate_id: str) -> SkillCandidateRecord:
        candidate = self.candidates.get(candidate_id)
        if candidate is None:
            raise ValueError(f"Unknown skill candidate: {candidate_id}")
        if candidate.status == "promoted":
            raise SkillPromotionError(f"Skill candidate {candidate_id} was already promoted")
        return self.candidates.set_status(candidate_id, "rejected")
