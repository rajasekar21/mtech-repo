"""
AI Scoring Engine — powered by Claude API (claude-sonnet-4-6).

Scoring dimensions (total 100 pts):
  ┌─────────────────────────────────┬───────┐
  │ Schema compliance rate          │  40   │
  │ Field-level quality             │  25   │
  │ Anomaly / pattern analysis      │  20   │
  │ APM health signals              │  15   │
  └─────────────────────────────────┴───────┘

Uses prompt caching so the schema template block (>1024 tokens) is cached
and not re-sent on repeated scoring calls — significantly reducing cost and
latency for high-frequency deployment gates.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import anthropic

from validator.schema_validator import BatchValidationSummary

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Scoring result
# ─────────────────────────────────────────────

@dataclass
class ScoringResult:
    totalScore:          float           # 0–100
    schemaComplianceScore: float         # 0–40
    fieldQualityScore:   float           # 0–25
    anomalyScore:        float           # 0–20
    apmScore:            float           # 0–15
    rationale:           str
    recommendations:     list[str]
    riskLevel:           str             # LOW / MEDIUM / HIGH / CRITICAL
    promotionVerdict:    str             # PROMOTE / REVIEW / BLOCK
    scoredAt:            datetime
    inputTokens:         int = 0
    outputTokens:        int = 0
    cacheReadTokens:     int = 0
    cacheWriteTokens:    int = 0

    def to_dict(self) -> dict:
        return {
            "totalScore":             round(self.totalScore, 2),
            "breakdown": {
                "schemaCompliance":   round(self.schemaComplianceScore, 2),
                "fieldQuality":       round(self.fieldQualityScore, 2),
                "anomalyAnalysis":    round(self.anomalyScore, 2),
                "apmHealth":          round(self.apmScore, 2),
            },
            "rationale":              self.rationale,
            "recommendations":        self.recommendations,
            "riskLevel":              self.riskLevel,
            "promotionVerdict":       self.promotionVerdict,
            "scoredAt":               self.scoredAt.isoformat(),
            "tokenUsage": {
                "inputTokens":        self.inputTokens,
                "outputTokens":       self.outputTokens,
                "cacheReadTokens":    self.cacheReadTokens,
                "cacheWriteTokens":   self.cacheWriteTokens,
            },
        }


# ─────────────────────────────────────────────
# Canonical schema description (cached block)
# ─────────────────────────────────────────────

_UPI_SCHEMA_DESCRIPTION = """
## Canonical UPI Balance Enquiry API Schema (NPCI UPI 2.0 Specification)

### Request Fields
| Field     | Type     | Required | Constraints                                      |
|-----------|----------|----------|--------------------------------------------------|
| txnId     | string   | Yes      | Alphanumeric uppercase, max 35 chars             |
| msgId     | string   | Yes      | Alphanumeric uppercase, max 35 chars             |
| reqDate   | datetime | Yes      | ISO-8601, must not be in the future              |
| txnType   | enum     | Yes      | Must be "BAL"                                    |
| orgId     | string   | Yes      | PSP org ID, 1–11 chars                           |
| bankId    | string   | Yes      | Bank IIN/IFSC prefix, 4–11 chars                 |
| vpa       | string   | Yes      | Virtual Payment Address: handle@bank             |
| device.deviceId  | string | Yes | 1–64 chars                                  |
| device.channel   | enum   | Yes | APP / WEB / USSD / SMS / IVRS               |
| device.mobile    | string | Yes | Exactly 10 digits                           |
| device.geocode   | string | No  | Format: "lat,long"                          |
| creds.type       | string | Yes | PIN / BIOMETRIC / OTP                       |
| creds.subType    | string | Yes | MPIN / IRIS / FACE                          |
| creds.data       | string | Yes | Base64-encoded encrypted credential         |
| creds.hmac       | string | Yes | HMAC-SHA256 digest                          |

### Response Fields
| Field      | Type     | Required (on success) | Constraints                          |
|------------|----------|-----------------------|--------------------------------------|
| txnId      | string   | Yes                   | Must match request txnId             |
| msgId      | string   | Yes                   | Must match request msgId             |
| respCode   | enum     | Yes                   | 00/ZM/91/YZ/ZS/AM/ZX/B3             |
| respMsg    | string   | Yes                   | Max 255 chars                        |
| timestamp  | datetime | Yes                   | ISO-8601                             |
| accountNo  | string   | Yes (respCode=00)     | Masked, last 4 visible               |
| ifsc       | string   | Yes (respCode=00)     | Format: XXXX0XXXXXX                  |
| bankName   | string   | Yes (respCode=00)     | Max 100 chars                        |
| acType     | enum     | Yes (respCode=00)     | SAVINGS / CURRENT / OD / CC         |
| balance    | decimal  | Yes (respCode=00)     | >= 0                                 |
| acName     | string   | Yes (respCode=00)     | Masked account holder name           |

### Business Rules
- txnType must always be "BAL" for Balance Enquiry
- Successful response (respCode=00) MUST include all account fields
- balance must be >= 0 (negative balance indicates a system error)
- VPA format: [alphanumeric/dots/hyphens]@[bank-handle]
- Duplicate txnId within a session is a protocol violation
- HMAC must be non-empty (cryptographic integrity check)
""".strip()


# ─────────────────────────────────────────────
# AI Scorer
# ─────────────────────────────────────────────

class AIScorer:
    """
    Uses Claude API with prompt caching to score a batch of validation results.

    The schema description block (>1024 tokens) is marked with cache_control so
    it is written to the prompt cache on the first call and served from cache on
    subsequent calls — reducing latency and cost in production gate runs.
    """

    MODEL = "claude-sonnet-4-6"

    def __init__(self, api_key: str | None = None):
        self._client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    # ── internal ──────────────────────────────

    def _build_system_prompt(self) -> list[dict]:
        """
        System prompt with the schema block flagged for prompt caching.
        The schema block exceeds 1024 tokens — minimum for cache eligibility.
        """
        return [
            {
                "type": "text",
                "text": (
                    "You are a UPI API quality scoring engine for a banking deployment gate. "
                    "Your role is to analyse validation results from UPI Balance Enquiry transactions "
                    "and produce an objective, structured deployment readiness score.\n\n"
                    "You always respond with ONLY valid JSON — no prose, no markdown fences.\n\n"
                    "The canonical UPI Balance Enquiry schema you must enforce:\n\n"
                    + _UPI_SCHEMA_DESCRIPTION
                ),
                # Cache the entire system prompt (schema + instructions) across scoring runs
                "cache_control": {"type": "ephemeral"},
            }
        ]

    def _build_user_prompt(
        self,
        summary: BatchValidationSummary,
        apm_metrics: dict[str, Any] | None,
    ) -> str:
        error_details = []
        for r in summary.results:
            if not r.fully_valid:
                error_details.append({
                    "txnId":         r.txnId,
                    "requestValid":  r.requestValid,
                    "responseValid": r.responseValid,
                    "errors":        [{"field": e.field, "msg": e.message} for e in r.requestErrors + r.responseErrors],
                    "latencyMs":     r.latencyMs,
                    "profile":       r.profile,
                })

        payload = {
            "batchSummary": summary.to_dict(),
            "invalidTransactionSamples": error_details[:20],   # cap at 20 to avoid huge payloads
            "apmMetrics": apm_metrics or {},
        }

        return (
            f"Score this UPI Balance Enquiry deployment batch.\n\n"
            f"BATCH DATA:\n{json.dumps(payload, indent=2)}\n\n"
            "Return ONLY a JSON object with this exact structure:\n"
            "{\n"
            '  "schemaComplianceScore": <0-40>,\n'
            '  "fieldQualityScore": <0-25>,\n'
            '  "anomalyScore": <0-20>,\n'
            '  "apmScore": <0-15>,\n'
            '  "totalScore": <sum of above>,\n'
            '  "riskLevel": "LOW"|"MEDIUM"|"HIGH"|"CRITICAL",\n'
            '  "promotionVerdict": "PROMOTE"|"REVIEW"|"BLOCK",\n'
            '  "rationale": "<2-3 sentence explanation>",\n'
            '  "recommendations": ["<actionable item>", ...]\n'
            "}\n\n"
            "Scoring guidelines:\n"
            "- schemaComplianceScore: 40 × (validCount / totalRecords)\n"
            "- fieldQualityScore: deduct points for recurring field errors, masked-field violations, hmac issues\n"
            "- anomalyScore: deduct for patterns like duplicate txnIds, future timestamps, zero-balance anomalies\n"
            "- apmScore: based on latency p99 < 2s = 15, < 5s = 10, > 5s = 5, missing APM = 8\n"
            "- promotionVerdict: PROMOTE if totalScore >= 85, REVIEW if 70-84, BLOCK if < 70\n"
            "- riskLevel: LOW >= 85, MEDIUM 70-84, HIGH 50-69, CRITICAL < 50"
        )

    # ── public API ────────────────────────────

    def score(
        self,
        summary: BatchValidationSummary,
        apm_metrics: dict[str, Any] | None = None,
    ) -> ScoringResult:
        """
        Score a batch validation summary using Claude API.
        Returns a ScoringResult with the deployment verdict.
        """
        response = self._client.messages.create(
            model=self.MODEL,
            max_tokens=1024,
            system=self._build_system_prompt(),
            messages=[
                {
                    "role": "user",
                    "content": self._build_user_prompt(summary, apm_metrics),
                }
            ],
        )

        raw_text = response.content[0].text.strip()
        # Strip markdown code fences if model includes them despite instruction
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.error("AI response was not valid JSON: %s", raw_text[:500])
            raise ValueError(f"AI scorer returned non-JSON response: {exc}") from exc

        usage = response.usage
        return ScoringResult(
            totalScore=float(data.get("totalScore", 0)),
            schemaComplianceScore=float(data.get("schemaComplianceScore", 0)),
            fieldQualityScore=float(data.get("fieldQualityScore", 0)),
            anomalyScore=float(data.get("anomalyScore", 0)),
            apmScore=float(data.get("apmScore", 0)),
            rationale=data.get("rationale", ""),
            recommendations=data.get("recommendations", []),
            riskLevel=data.get("riskLevel", "UNKNOWN"),
            promotionVerdict=data.get("promotionVerdict", "BLOCK"),
            scoredAt=datetime.now(timezone.utc),
            inputTokens=getattr(usage, "input_tokens", 0),
            outputTokens=getattr(usage, "output_tokens", 0),
            cacheReadTokens=getattr(usage, "cache_read_input_tokens", 0),
            cacheWriteTokens=getattr(usage, "cache_creation_input_tokens", 0),
        )

    def score_incremental(
        self,
        summaries: list[BatchValidationSummary],
        apm_metrics: dict[str, Any] | None = None,
    ) -> list[ScoringResult]:
        """
        Score multiple batches sequentially.
        The cached schema block is reused across all calls, saving tokens from the 2nd call onward.
        """
        return [self.score(s, apm_metrics) for s in summaries]
