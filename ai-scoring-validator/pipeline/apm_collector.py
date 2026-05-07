"""
APM metrics collector — supplementary scoring signal.

Collects performance metrics from the UPI Balance Enquiry service:
  - End-to-end latency percentiles (p50, p95, p99)
  - Error rate
  - Throughput (TPS)
  - Availability

These metrics contribute 15 points to the AI scoring model and help the
deployment gate distinguish between a functionally correct but slow deployment
(REVIEW) vs a broken deployment (BLOCK).

Supports two modes:
  1. Prometheus scrape (production)
  2. Computed from validation results (no external dependency)
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass
from typing import Any

from validator.schema_validator import BatchValidationSummary, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class APMMetrics:
    """Snapshot of UPI service health metrics for one scoring window."""
    latencyP50Ms:    float | None = None
    latencyP95Ms:    float | None = None
    latencyP99Ms:    float | None = None
    errorRatePct:    float | None = None    # % of failed transactions
    tps:             float | None = None    # transactions per second
    availabilityPct: float | None = None    # service uptime %
    source:          str = "computed"       # "prometheus" | "computed" | "mock"

    def to_dict(self) -> dict[str, Any]:
        return {
            "latencyP50Ms":    self.latencyP50Ms,
            "latencyP95Ms":    self.latencyP95Ms,
            "latencyP99Ms":    self.latencyP99Ms,
            "errorRatePct":    self.errorRatePct,
            "tps":             self.tps,
            "availabilityPct": self.availabilityPct,
            "source":          self.source,
        }


class APMCollector:
    """
    Computes APM metrics from validation results or scrapes from Prometheus.
    """

    def __init__(self, prometheus_url: str | None = None):
        self._prometheus_url = prometheus_url

    # ── from validation results (no external dep) ──

    def from_batch(self, summary: BatchValidationSummary, window_seconds: int = 30) -> APMMetrics:
        """Compute APM metrics directly from a validated batch."""
        latencies = [
            r.latencyMs for r in summary.results if r.latencyMs is not None
        ]

        if latencies:
            sorted_lat = sorted(latencies)
            n = len(sorted_lat)
            p50 = sorted_lat[int(n * 0.50)]
            p95 = sorted_lat[min(int(n * 0.95), n - 1)]
            p99 = sorted_lat[min(int(n * 0.99), n - 1)]
        else:
            p50 = p95 = p99 = None

        error_rate = (
            summary.invalidCount / summary.totalRecords * 100
            if summary.totalRecords > 0 else None
        )
        tps = summary.totalRecords / window_seconds if window_seconds > 0 else None

        return APMMetrics(
            latencyP50Ms=float(p50) if p50 is not None else None,
            latencyP95Ms=float(p95) if p95 is not None else None,
            latencyP99Ms=float(p99) if p99 is not None else None,
            errorRatePct=round(error_rate, 2) if error_rate is not None else None,
            tps=round(tps, 2) if tps is not None else None,
            availabilityPct=round(100 - (error_rate or 0), 2),
            source="computed",
        )

    # ── from Prometheus ───────────────────────

    def from_prometheus(self, metric_prefix: str = "upi_bal_enq") -> APMMetrics | None:
        """
        Scrape latency / error metrics from a Prometheus endpoint.
        Returns None if Prometheus is unreachable.
        """
        if not self._prometheus_url:
            return None
        try:
            import urllib.request
            url = f"{self._prometheus_url}/api/v1/query"

            def _query(q: str) -> float | None:
                import json, urllib.parse
                full = f"{url}?query={urllib.parse.quote(q)}"
                with urllib.request.urlopen(full, timeout=5) as r:
                    data = json.loads(r.read())
                    results = data.get("data", {}).get("result", [])
                    if results:
                        return float(results[0]["value"][1])
                return None

            return APMMetrics(
                latencyP50Ms=_query(f'histogram_quantile(0.50, rate({metric_prefix}_latency_bucket[2m])) * 1000'),
                latencyP95Ms=_query(f'histogram_quantile(0.95, rate({metric_prefix}_latency_bucket[2m])) * 1000'),
                latencyP99Ms=_query(f'histogram_quantile(0.99, rate({metric_prefix}_latency_bucket[2m])) * 1000'),
                errorRatePct=_query(f'rate({metric_prefix}_errors_total[2m]) / rate({metric_prefix}_requests_total[2m]) * 100'),
                tps=_query(f'rate({metric_prefix}_requests_total[2m])'),
                availabilityPct=_query(f'avg_over_time(up{{job="{metric_prefix}"}}[5m]) * 100'),
                source="prometheus",
            )
        except Exception as exc:
            logger.warning("Prometheus scrape failed: %s", exc)
            return None
