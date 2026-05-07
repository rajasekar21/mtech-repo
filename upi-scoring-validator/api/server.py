"""
FastAPI REST server — exposes scoring, simulation, and gate endpoints.

Endpoints:
  POST /simulate          — generate synthetic transactions and validate them
  POST /validate          — validate a raw batch of transactions
  POST /score             — run AI scoring on a validation summary
  POST /gate/evaluate     — full pipeline: simulate → validate → score → gate
  GET  /gate/history      — audit log of past gate decisions
  GET  /health            — liveness probe
"""

from __future__ import annotations

import logging
import sys
import os

# Allow imports from project root when running from any directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config.settings import settings
from gate.deployment_gate import DeploymentGate, GateAuditLog
from pipeline.apm_collector import APMCollector
from scorer.ai_scorer import AIScorer
from simulator.upi_simulator import UPISimulator
from validator.schema_validator import SchemaValidator

logger = logging.getLogger(__name__)

app = FastAPI(
    title="UPI Balance Enquiry Scoring Validator",
    description=(
        "AI-powered deployment gate for UPI Balance Enquiry API. "
        "Validates transaction schemas, scores quality, and decides promotion."
    ),
    version="1.0.0",
)

# ── singletons (shared across requests) ───────────────────────────────────────
_validator   = SchemaValidator()
_apm         = APMCollector(prometheus_url=settings.PROMETHEUS_URL)
_gate        = DeploymentGate(settings.PROMOTE_THRESHOLD, settings.REVIEW_THRESHOLD)
_audit_log   = GateAuditLog()

def _get_scorer() -> AIScorer:
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not configured")
    return AIScorer(api_key=settings.ANTHROPIC_API_KEY)


# ── request / response models ─────────────────────────────────────────────────

class SimulateRequest(BaseModel):
    count:        int   = 100
    validPct:     float = 0.75
    invalidPct:   float = 0.15
    edgePct:      float = 0.10

class ValidateRequest(BaseModel):
    records: list[dict]

class GateEvaluateRequest(BaseModel):
    count:    int = 100
    from_env: str = settings.FROM_ENV
    to_env:   str = settings.TO_ENV

class OverrideRequest(BaseModel):
    decision_index: int
    new_verdict:    str
    overridden_by:  str
    reason:         str


# ── routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/simulate")
def simulate(req: SimulateRequest):
    """Generate synthetic UPI Balance Enquiry transactions."""
    total = req.validPct + req.invalidPct + req.edgePct
    if abs(total - 1.0) > 0.01:
        raise HTTPException(status_code=400, detail="Profile percentages must sum to 1.0")

    sim = UPISimulator(profile_weights={
        "valid":   req.validPct,
        "invalid": req.invalidPct,
        "edge":    req.edgePct,
    })
    records = sim.generate(req.count)
    return {
        "generated":     len(records),
        "validProfiles": sum(1 for r in records if r["profile"] == "valid"),
        "records":       records[:10],          # return sample; full list is large
        "note":          f"Showing 10 of {len(records)} records. POST /validate with full list.",
    }


@app.post("/validate")
def validate(req: ValidateRequest):
    """Validate a batch of raw transaction records against the canonical schema."""
    summary = _validator.validate_batch(req.records)
    return summary.to_dict()


@app.post("/score")
def score(req: ValidateRequest):
    """Validate a batch and run AI scoring on the results."""
    summary = _validator.validate_batch(req.records)
    apm     = _apm.from_batch(summary)
    scorer  = _get_scorer()
    result  = scorer.score(summary, apm.to_dict())
    return result.to_dict()


@app.post("/gate/evaluate")
def gate_evaluate(req: GateEvaluateRequest):
    """
    Full pipeline:
      1. Simulate synthetic transactions
      2. Validate against canonical schema
      3. Collect APM metrics
      4. AI scoring
      5. Gate decision
    """
    sim = UPISimulator()
    records = sim.generate(req.count)

    summary = _validator.validate_batch(records)
    apm     = _apm.from_batch(summary)
    scorer  = _get_scorer()
    scoring = scorer.score(summary, apm.to_dict())
    decision = _gate.evaluate(scoring, from_env=req.from_env, to_env=req.to_env)
    _audit_log.record(decision)

    return {
        "decision":        decision.to_dict(),
        "batchSummary":    summary.to_dict(),
        "apmMetrics":      apm.to_dict(),
    }


@app.get("/gate/history")
def gate_history():
    """Return audit log of all gate decisions in this session."""
    return _audit_log.summary()


@app.post("/gate/override")
def gate_override(req: OverrideRequest):
    """Human override of a REVIEW-tier gate decision."""
    decisions = _audit_log.all_decisions
    if req.decision_index < 0 or req.decision_index >= len(decisions):
        raise HTTPException(status_code=404, detail="Decision index out of range")
    try:
        updated = _gate.human_override(
            decisions[req.decision_index],
            new_verdict=req.new_verdict,
            overridden_by=req.overridden_by,
            reason=req.reason,
        )
        return updated.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
