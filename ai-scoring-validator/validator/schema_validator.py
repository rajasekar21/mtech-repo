"""
Schema validation engine.

Validates raw transaction payloads against the canonical UPI Balance Enquiry
schema and produces structured ValidationResult objects consumed by the AI scorer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from schema.upi_balance_enquiry import UPIBalEnqRequest, UPIBalEnqResponse, UPIBalEnqTransaction

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────

@dataclass
class FieldError:
    field:   str
    message: str
    value:   Any = None


@dataclass
class ValidationResult:
    txnId:          str
    source:         str
    validatedAt:    datetime
    requestValid:   bool
    responseValid:  bool
    requestErrors:  list[FieldError] = field(default_factory=list)
    responseErrors: list[FieldError] = field(default_factory=list)
    latencyMs:      int | None = None
    profile:        str | None = None   # valid / invalid / edge (from simulator)
    rawPayload:     dict | None = None

    @property
    def fully_valid(self) -> bool:
        return self.requestValid and self.responseValid

    @property
    def total_errors(self) -> int:
        return len(self.requestErrors) + len(self.responseErrors)

    def to_dict(self) -> dict:
        return {
            "txnId":         self.txnId,
            "source":        self.source,
            "validatedAt":   self.validatedAt.isoformat(),
            "requestValid":  self.requestValid,
            "responseValid": self.responseValid,
            "requestErrors": [{"field": e.field, "message": e.message} for e in self.requestErrors],
            "responseErrors":[{"field": e.field, "message": e.message} for e in self.responseErrors],
            "latencyMs":     self.latencyMs,
            "profile":       self.profile,
            "fullyValid":    self.fully_valid,
            "totalErrors":   self.total_errors,
        }


@dataclass
class BatchValidationSummary:
    totalRecords:      int
    validCount:        int
    invalidCount:      int
    results:           list[ValidationResult]
    validatedAt:       datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def compliance_rate(self) -> float:
        if self.totalRecords == 0:
            return 0.0
        return round(self.validCount / self.totalRecords * 100, 2)

    @property
    def top_errors(self) -> list[dict]:
        """Return top 10 most-frequent field errors across the batch."""
        from collections import Counter
        counter: Counter = Counter()
        for r in self.results:
            for e in r.requestErrors + r.responseErrors:
                counter[e.field] += 1
        return [{"field": f, "count": c} for f, c in counter.most_common(10)]

    def to_dict(self) -> dict:
        return {
            "totalRecords":   self.totalRecords,
            "validCount":     self.validCount,
            "invalidCount":   self.invalidCount,
            "complianceRate": self.compliance_rate,
            "topErrors":      self.top_errors,
            "validatedAt":    self.validatedAt.isoformat(),
        }


# ─────────────────────────────────────────────
# Validator
# ─────────────────────────────────────────────

class SchemaValidator:
    """
    Validates raw UPI Balance Enquiry payloads against the canonical schema.

    Accepts three input forms:
      1. UPIBalEnqTransaction  (already typed)
      2. dict with {"request": {...}, "response": {...}}
      3. simulator record dict with {"profile", "valid", "payload"}
    """

    def validate_one(self, raw: dict | UPIBalEnqTransaction) -> ValidationResult:
        now = datetime.now(timezone.utc)

        # ── normalise input ──────────────────────────────────────
        if isinstance(raw, UPIBalEnqTransaction):
            txn_id   = raw.request.txnId
            source   = raw.source
            latency  = raw.latencyMs
            profile  = None
            req_dict = raw.request.model_dump()
            res_dict = raw.response.model_dump() if raw.response else None
        elif "payload" in raw:
            # simulator record format
            payload  = raw["payload"]
            profile  = raw.get("profile")
            source   = payload.get("source", "simulator")
            latency  = payload.get("latencyMs")

            if raw.get("valid") and "request" in payload:
                # already parsed UPIBalEnqTransaction dict
                req_dict = payload["request"]
                res_dict = payload.get("response")
                txn_id   = req_dict.get("txnId", "UNKNOWN")
            else:
                # raw invalid/edge dict — treat payload as request
                req_dict = payload
                res_dict = None
                txn_id   = payload.get("txnId", "UNKNOWN")
        else:
            # plain {"request": ..., "response": ...} dict
            req_dict = raw.get("request", raw)
            res_dict = raw.get("response")
            txn_id   = req_dict.get("txnId", "UNKNOWN")
            source   = raw.get("source", "unknown")
            latency  = raw.get("latencyMs")
            profile  = None

        # ── validate request ─────────────────────────────────────
        req_errors: list[FieldError] = []
        try:
            UPIBalEnqRequest.model_validate(req_dict)
            req_valid = True
        except ValidationError as exc:
            req_valid = False
            for err in exc.errors():
                loc = ".".join(str(l) for l in err["loc"])
                req_errors.append(FieldError(field=loc, message=err["msg"], value=err.get("input")))
        except Exception as exc:
            req_valid = False
            req_errors.append(FieldError(field="__root__", message=str(exc)))

        # ── validate response (if present) ───────────────────────
        res_errors: list[FieldError] = []
        if res_dict:
            try:
                UPIBalEnqResponse.model_validate(res_dict)
                res_valid = True
            except ValidationError as exc:
                res_valid = False
                for err in exc.errors():
                    loc = ".".join(str(l) for l in err["loc"])
                    res_errors.append(FieldError(field=loc, message=err["msg"], value=err.get("input")))
            except Exception as exc:
                res_valid = False
                res_errors.append(FieldError(field="__root__", message=str(exc)))
        else:
            # absence of response is acceptable for in-flight requests
            res_valid = True

        return ValidationResult(
            txnId=txn_id,
            source=source,
            validatedAt=now,
            requestValid=req_valid,
            responseValid=res_valid,
            requestErrors=req_errors,
            responseErrors=res_errors,
            latencyMs=int(latency) if latency is not None else None,
            profile=profile,
            rawPayload=req_dict if not req_valid else None,
        )

    def validate_batch(self, records: list[dict | UPIBalEnqTransaction]) -> BatchValidationSummary:
        results: list[ValidationResult] = []
        for rec in records:
            try:
                result = self.validate_one(rec)
            except Exception as exc:
                logger.warning("Unexpected error validating record: %s", exc)
                result = ValidationResult(
                    txnId="ERROR",
                    source="unknown",
                    validatedAt=datetime.now(timezone.utc),
                    requestValid=False,
                    responseValid=False,
                    requestErrors=[FieldError("__root__", str(exc))],
                )
            results.append(result)

        valid_count = sum(1 for r in results if r.fully_valid)
        return BatchValidationSummary(
            totalRecords=len(results),
            validCount=valid_count,
            invalidCount=len(results) - valid_count,
            results=results,
        )
