"""
Deployment Gate — decides whether a UPI Balance Enquiry service build
is promoted to the next environment based on AI scoring results.

Promotion tiers:
  ┌──────────────┬───────────────────┬──────────────────────────────────┐
  │ Score range  │ Verdict           │ Action                           │
  ├──────────────┼───────────────────┼──────────────────────────────────┤
  │  >= 85       │ PROMOTE           │ Automatic promotion              │
  │  70 – 84     │ REVIEW            │ Manual approval required         │
  │  50 – 69     │ BLOCK             │ Blocked; fix defects             │
  │  < 50        │ BLOCK (CRITICAL)  │ Blocked; escalate immediately    │
  └──────────────┴───────────────────┴──────────────────────────────────┘

A gate decision also records which environment pair is involved
(e.g. dev→staging, staging→prod) and a full audit trail.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from scorer.ai_scorer import ScoringResult

logger = logging.getLogger(__name__)

PROMOTE_THRESHOLD = 85.0
REVIEW_THRESHOLD  = 70.0


@dataclass
class GateDecision:
    verdict:          str                   # PROMOTE / REVIEW / BLOCK
    score:            float
    riskLevel:        str
    fromEnv:          str
    toEnv:            str
    rationale:        str
    recommendations:  list[str]
    scoringResult:    ScoringResult
    decidedAt:        datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    overriddenBy:     str | None = None     # set if a human overrides the gate
    overrideReason:   str | None = None

    @property
    def promoted(self) -> bool:
        return self.verdict == "PROMOTE"

    @property
    def blocked(self) -> bool:
        return self.verdict == "BLOCK"

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict":         self.verdict,
            "score":           round(self.score, 2),
            "riskLevel":       self.riskLevel,
            "fromEnv":         self.fromEnv,
            "toEnv":           self.toEnv,
            "rationale":       self.rationale,
            "recommendations": self.recommendations,
            "decidedAt":       self.decidedAt.isoformat(),
            "overriddenBy":    self.overriddenBy,
            "overrideReason":  self.overrideReason,
            "scoring":         self.scoringResult.to_dict(),
        }

    def summary_line(self) -> str:
        icon = {"PROMOTE": "✅", "REVIEW": "⚠️", "BLOCK": "❌"}.get(self.verdict, "?")
        return (
            f"{icon} [{self.verdict}] {self.fromEnv}→{self.toEnv} | "
            f"score={self.score:.1f}/100 risk={self.riskLevel}"
        )


class DeploymentGate:
    """
    Evaluates a ScoringResult and produces a GateDecision.

    Allows human override for REVIEW-tier decisions where a release manager
    can approve or reject with a reason.
    """

    def __init__(
        self,
        promote_threshold: float = PROMOTE_THRESHOLD,
        review_threshold:  float = REVIEW_THRESHOLD,
    ):
        self._promote_threshold = promote_threshold
        self._review_threshold  = review_threshold

    def evaluate(
        self,
        scoring: ScoringResult,
        from_env: str = "staging",
        to_env:   str = "production",
    ) -> GateDecision:
        score   = scoring.totalScore
        verdict = scoring.promotionVerdict

        # Guard against model hallucination — recompute verdict from score
        if score >= self._promote_threshold:
            verdict = "PROMOTE"
        elif score >= self._review_threshold:
            verdict = "REVIEW"
        else:
            verdict = "BLOCK"

        decision = GateDecision(
            verdict=verdict,
            score=score,
            riskLevel=scoring.riskLevel,
            fromEnv=from_env,
            toEnv=to_env,
            rationale=scoring.rationale,
            recommendations=scoring.recommendations,
            scoringResult=scoring,
        )

        logger.info(decision.summary_line())
        return decision

    def human_override(
        self,
        decision: GateDecision,
        new_verdict: str,
        overridden_by: str,
        reason: str,
    ) -> GateDecision:
        """
        Allow a release manager to override a REVIEW decision.
        BLOCK decisions cannot be overridden via this method for safety —
        they require a new scoring run after fixes.
        """
        if decision.verdict == "BLOCK":
            raise ValueError(
                "BLOCK decisions cannot be overridden. Fix the defects and re-run validation."
            )
        if new_verdict not in ("PROMOTE", "BLOCK"):
            raise ValueError("Override verdict must be PROMOTE or BLOCK.")

        decision.verdict       = new_verdict
        decision.overriddenBy  = overridden_by
        decision.overrideReason = reason
        logger.warning(
            "Gate decision overridden by %s: %s → %s (%s)",
            overridden_by, decision.verdict, new_verdict, reason,
        )
        return decision


class GateAuditLog:
    """
    In-memory audit log of all gate decisions in the current session.
    In production, persist to a database or append to a log file.
    """

    def __init__(self):
        self._decisions: list[GateDecision] = []

    def record(self, decision: GateDecision) -> None:
        self._decisions.append(decision)

    @property
    def all_decisions(self) -> list[GateDecision]:
        return list(self._decisions)

    @property
    def promote_count(self) -> int:
        return sum(1 for d in self._decisions if d.verdict == "PROMOTE")

    @property
    def block_count(self) -> int:
        return sum(1 for d in self._decisions if d.verdict == "BLOCK")

    @property
    def review_count(self) -> int:
        return sum(1 for d in self._decisions if d.verdict == "REVIEW")

    def summary(self) -> dict:
        return {
            "total":   len(self._decisions),
            "promote": self.promote_count,
            "review":  self.review_count,
            "block":   self.block_count,
            "recentDecisions": [d.to_dict() for d in self._decisions[-5:]],
        }
