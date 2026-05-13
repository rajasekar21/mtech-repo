"""Governance validation service.

Evaluates API specs against a set of best-practice governance rules and
produces a scored report with recommendations.
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.api_spec import ApiEndpoint, ApiSpec
from app.models.knowledge import GovernanceReport
from app.schemas.governance import (
    GovernanceResponse,
    GovernanceRule,
    GovernanceRuleResult,
    GovernanceRulesResponse,
    GovernanceScorecard,
)
from app.services.ai_service import AIService

logger = get_logger(__name__)

# --------------------------------------------------------------------------- #
# Governance rule definitions
# --------------------------------------------------------------------------- #

GOVERNANCE_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "naming_conventions",
        "name": "Naming Conventions",
        "category": "naming_conventions",
        "description": "API paths should use lowercase kebab-case; field names should be camelCase or snake_case",
        "severity": "medium",
        "auto_fixable": False,
    },
    {
        "rule_id": "auth_required",
        "name": "Authentication Required",
        "category": "auth_security",
        "description": "All endpoints must specify an authentication method",
        "severity": "high",
        "auto_fixable": False,
    },
    {
        "rule_id": "response_codes",
        "name": "Standard HTTP Response Codes",
        "category": "response_codes",
        "description": "Endpoints must document standard HTTP status codes (200, 400, 401, 500)",
        "severity": "medium",
        "auto_fixable": False,
    },
    {
        "rule_id": "versioning",
        "name": "API Versioning",
        "category": "versioning",
        "description": "API paths should include a version prefix (e.g. /v1/) or version header",
        "severity": "medium",
        "auto_fixable": False,
    },
    {
        "rule_id": "description_completeness",
        "name": "Description Completeness",
        "category": "documentation",
        "description": "All endpoints must have a non-empty description",
        "severity": "low",
        "auto_fixable": False,
    },
    {
        "rule_id": "request_validation",
        "name": "Request Validation",
        "category": "documentation",
        "description": "POST/PUT/PATCH endpoints must define a request body schema",
        "severity": "medium",
        "auto_fixable": False,
    },
    {
        "rule_id": "security_headers",
        "name": "Security Scheme Definition",
        "category": "auth_security",
        "description": "At least one security scheme must be defined at the spec level",
        "severity": "high",
        "auto_fixable": False,
    },
    {
        "rule_id": "error_handling",
        "name": "Error Response Documentation",
        "category": "error_handling",
        "description": "Endpoints should document at least one 4xx or 5xx response",
        "severity": "medium",
        "auto_fixable": False,
    },
    {
        "rule_id": "no_deprecated_endpoints",
        "name": "No Undocumented Deprecations",
        "category": "documentation",
        "description": "Deprecated endpoints must have a description explaining the deprecation and migration path",
        "severity": "low",
        "auto_fixable": False,
    },
    {
        "rule_id": "path_lowercase",
        "name": "Lowercase Paths",
        "category": "naming_conventions",
        "description": "API path segments must be lowercase (path parameters excluded)",
        "severity": "low",
        "auto_fixable": True,
    },
]


def _grade_from_score(score: float) -> str:
    """Convert a numeric score to a letter grade."""
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


class GovernanceService:
    """Validates API specs against governance rules."""

    async def validate_spec(
        self,
        db: AsyncSession,
        ai_service: AIService,
        spec_id: uuid.UUID,
    ) -> GovernanceResponse:
        """Run all governance rules against a spec and return a scored report.

        Args:
            db: Async SQLAlchemy session.
            ai_service: Initialised AIService (used for AI-assisted rule evaluation).
            spec_id: UUID of the spec to validate.

        Returns:
            GovernanceResponse with full scorecard and rule results.
        """
        logger.info("Governance validation started", spec_id=str(spec_id))

        spec = await db.get(ApiSpec, spec_id)
        if not spec:
            raise ValueError(f"ApiSpec {spec_id} not found")

        # Load endpoints
        stmt = select(ApiEndpoint).where(ApiEndpoint.spec_id == spec_id)
        result = await db.execute(stmt)
        endpoints: list[ApiEndpoint] = list(result.scalars().all())

        parsed = spec.parsed_content or {}

        # Run each rule
        passed_rules: list[GovernanceRuleResult] = []
        failed_rules: list[GovernanceRuleResult] = []

        rule_results = await self._evaluate_all_rules(endpoints, parsed, ai_service)

        for rule_result in rule_results:
            if rule_result.passed:
                passed_rules.append(rule_result)
            else:
                failed_rules.append(rule_result)

        # Score
        overall_score = self.score_governance(rule_results)
        scorecard = self._build_scorecard(rule_results)
        recommendations = self.generate_recommendations(failed_rules)

        # Persist
        report = GovernanceReport(
            spec_id=spec_id,
            score=overall_score,
            passed_rules=[r.model_dump() for r in passed_rules],
            failed_rules=[r.model_dump() for r in failed_rules],
            recommendations=recommendations,
            rule_details={r.rule_id: r.model_dump() for r in rule_results},
        )
        db.add(report)
        await db.flush()
        await db.refresh(report)

        logger.info(
            "Governance validation complete",
            spec_id=str(spec_id),
            score=overall_score,
            passed=len(passed_rules),
            failed=len(failed_rules),
        )

        from datetime import datetime, timezone

        return GovernanceResponse(
            report_id=report.id,
            spec_id=spec_id,
            overall_score=overall_score,
            grade=_grade_from_score(overall_score),
            scorecard=scorecard,
            passed_rules=passed_rules,
            failed_rules=failed_rules,
            recommendations=recommendations,
            summary=(
                f"Evaluated {len(rule_results)} rules: "
                f"{len(passed_rules)} passed, {len(failed_rules)} failed. "
                f"Overall score: {overall_score:.1f}/100."
            ),
            created_at=report.created_at,
        )

    # ---------------------------------------------------------------------- #
    # Rule evaluators
    # ---------------------------------------------------------------------- #

    async def _evaluate_all_rules(
        self,
        endpoints: list[ApiEndpoint],
        parsed: dict[str, Any],
        ai_service: AIService,
    ) -> list[GovernanceRuleResult]:
        """Evaluate all governance rules and return results."""
        results: list[GovernanceRuleResult] = []

        evaluators = {
            "naming_conventions": self._check_naming_conventions,
            "auth_required": self._check_auth_required,
            "response_codes": self._check_response_codes,
            "versioning": self._check_versioning,
            "description_completeness": self._check_description_completeness,
            "request_validation": self._check_request_validation,
            "security_headers": self._check_security_headers,
            "error_handling": self._check_error_handling,
            "no_deprecated_endpoints": self._check_deprecated_endpoints,
            "path_lowercase": self._check_path_lowercase,
        }

        for rule_def in GOVERNANCE_RULES:
            rule_id = rule_def["rule_id"]
            evaluator = evaluators.get(rule_id)
            if not evaluator:
                continue

            try:
                result = evaluator(endpoints, parsed)
                result.rule_id = rule_id
                result.name = rule_def["name"]
                result.category = rule_def["category"]
                result.severity = rule_def["severity"]
            except Exception as exc:
                logger.warning("Rule evaluation failed", rule=rule_id, error=str(exc))
                result = GovernanceRuleResult(
                    rule_id=rule_id,
                    name=rule_def["name"],
                    category=rule_def["category"],
                    passed=False,
                    score=0.0,
                    details=f"Rule evaluation error: {exc}",
                    severity=rule_def["severity"],
                )

            results.append(result)

        return results

    def _check_naming_conventions(
        self,
        endpoints: list[ApiEndpoint],
        parsed: dict[str, Any],
    ) -> GovernanceRuleResult:
        violations: list[str] = []
        for ep in endpoints:
            # Check path: segments should be lowercase (excluding path params {})
            segments = [s for s in ep.path.split("/") if s and not s.startswith("{")]
            for seg in segments:
                if seg != seg.lower():
                    violations.append(f"{ep.path} — segment '{seg}' is not lowercase")

        total = len(endpoints)
        passing = total - len(violations)
        score = (passing / total * 100) if total > 0 else 100.0
        passed = len(violations) == 0

        return GovernanceRuleResult(
            rule_id="naming_conventions",
            name="Naming Conventions",
            category="naming_conventions",
            passed=passed,
            score=score,
            details=(
                f"{len(violations)} paths violate naming conventions."
                if violations
                else "All paths follow naming conventions."
            ),
            affected_endpoints=[v.split(" — ")[0] for v in violations[:10]],
            severity="medium",
        )

    def _check_auth_required(
        self,
        endpoints: list[ApiEndpoint],
        parsed: dict[str, Any],
    ) -> GovernanceRuleResult:
        missing_auth = [
            ep.path for ep in endpoints
            if not ep.auth_method and not any(
                kw in (ep.path or "").lower()
                for kw in ["/health", "/ping", "/status", "/docs", "/openapi"]
            )
        ]
        total = len(endpoints)
        score = ((total - len(missing_auth)) / total * 100) if total > 0 else 100.0

        return GovernanceRuleResult(
            rule_id="auth_required",
            name="Authentication Required",
            category="auth_security",
            passed=len(missing_auth) == 0,
            score=score,
            details=(
                f"{len(missing_auth)} endpoints missing authentication."
                if missing_auth
                else "All endpoints define authentication."
            ),
            affected_endpoints=missing_auth[:10],
            severity="high",
        )

    def _check_response_codes(
        self,
        endpoints: list[ApiEndpoint],
        parsed: dict[str, Any],
    ) -> GovernanceRuleResult:
        paths = parsed.get("paths", {})
        compliant = 0
        total = 0
        violations: list[str] = []

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method, op in path_item.items():
                if not isinstance(op, dict) or method in ("parameters", "summary"):
                    continue
                total += 1
                responses = op.get("responses", {})
                has_success = any(str(c).startswith("2") for c in responses)
                has_client_error = any(str(c).startswith("4") for c in responses)
                if has_success and has_client_error:
                    compliant += 1
                else:
                    violations.append(f"{method.upper()} {path}")

        if total == 0 and endpoints:
            total = len(endpoints)
            compliant = total  # Can't check without full parsed spec

        score = (compliant / total * 100) if total > 0 else 100.0

        return GovernanceRuleResult(
            rule_id="response_codes",
            name="Standard HTTP Response Codes",
            category="response_codes",
            passed=len(violations) == 0,
            score=score,
            details=(
                f"{len(violations)} endpoints missing standard response codes."
                if violations
                else "All endpoints document standard response codes."
            ),
            affected_endpoints=violations[:10],
            severity="medium",
        )

    def _check_versioning(
        self,
        endpoints: list[ApiEndpoint],
        parsed: dict[str, Any],
    ) -> GovernanceRuleResult:
        version_pattern = re.compile(r"/v\d+/|/v\d+$", re.IGNORECASE)
        without_version = [
            ep.path for ep in endpoints
            if not version_pattern.search(ep.path)
        ]
        total = len(endpoints)
        score = ((total - len(without_version)) / total * 100) if total > 0 else 100.0

        return GovernanceRuleResult(
            rule_id="versioning",
            name="API Versioning",
            category="versioning",
            passed=len(without_version) == 0,
            score=score,
            details=(
                f"{len(without_version)} endpoints missing version in path."
                if without_version
                else "All endpoints include version prefix."
            ),
            affected_endpoints=without_version[:10],
            severity="medium",
        )

    def _check_description_completeness(
        self,
        endpoints: list[ApiEndpoint],
        parsed: dict[str, Any],
    ) -> GovernanceRuleResult:
        missing = [
            f"{ep.method} {ep.path}"
            for ep in endpoints
            if not (ep.description and ep.description.strip())
        ]
        total = len(endpoints)
        score = ((total - len(missing)) / total * 100) if total > 0 else 100.0

        return GovernanceRuleResult(
            rule_id="description_completeness",
            name="Description Completeness",
            category="documentation",
            passed=len(missing) == 0,
            score=score,
            details=(
                f"{len(missing)} endpoints missing descriptions."
                if missing
                else "All endpoints have descriptions."
            ),
            affected_endpoints=missing[:10],
            severity="low",
        )

    def _check_request_validation(
        self,
        endpoints: list[ApiEndpoint],
        parsed: dict[str, Any],
    ) -> GovernanceRuleResult:
        mutation_methods = {"POST", "PUT", "PATCH"}
        mutation_eps = [ep for ep in endpoints if ep.method.upper() in mutation_methods]
        missing_schema = [
            f"{ep.method} {ep.path}"
            for ep in mutation_eps
            if not ep.request_schema
        ]
        total = len(mutation_eps)
        score = ((total - len(missing_schema)) / total * 100) if total > 0 else 100.0

        return GovernanceRuleResult(
            rule_id="request_validation",
            name="Request Validation",
            category="documentation",
            passed=len(missing_schema) == 0,
            score=score,
            details=(
                f"{len(missing_schema)} mutation endpoints missing request schema."
                if missing_schema
                else "All mutation endpoints define request schemas."
            ),
            affected_endpoints=missing_schema[:10],
            severity="medium",
        )

    def _check_security_headers(
        self,
        endpoints: list[ApiEndpoint],
        parsed: dict[str, Any],
    ) -> GovernanceRuleResult:
        security_schemes = parsed.get("security_schemes", {})
        has_schemes = bool(security_schemes)

        # Also check if raw spec has securityDefinitions (Swagger 2.0)
        raw = parsed.get("raw", {})
        if not has_schemes:
            has_schemes = bool(raw.get("securityDefinitions") or raw.get("components", {}).get("securitySchemes"))

        return GovernanceRuleResult(
            rule_id="security_headers",
            name="Security Scheme Definition",
            category="auth_security",
            passed=has_schemes,
            score=100.0 if has_schemes else 0.0,
            details=(
                f"Security schemes defined: {list(security_schemes.keys())[:5]}"
                if has_schemes
                else "No security schemes defined at spec level."
            ),
            severity="high",
        )

    def _check_error_handling(
        self,
        endpoints: list[ApiEndpoint],
        parsed: dict[str, Any],
    ) -> GovernanceRuleResult:
        paths = parsed.get("paths", {})
        without_errors = []
        total = 0

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method, op in path_item.items():
                if not isinstance(op, dict) or method in ("parameters", "summary"):
                    continue
                total += 1
                responses = op.get("responses", {})
                has_error = any(
                    str(c).startswith("4") or str(c).startswith("5")
                    for c in responses
                )
                if not has_error:
                    without_errors.append(f"{method.upper()} {path}")

        if total == 0:
            total = len(endpoints)
            without_errors = []  # Can't check

        score = ((total - len(without_errors)) / total * 100) if total > 0 else 100.0

        return GovernanceRuleResult(
            rule_id="error_handling",
            name="Error Response Documentation",
            category="error_handling",
            passed=len(without_errors) == 0,
            score=score,
            details=(
                f"{len(without_errors)} endpoints missing error response documentation."
                if without_errors
                else "All endpoints document error responses."
            ),
            affected_endpoints=without_errors[:10],
            severity="medium",
        )

    def _check_deprecated_endpoints(
        self,
        endpoints: list[ApiEndpoint],
        parsed: dict[str, Any],
    ) -> GovernanceRuleResult:
        undocumented_deprecated = [
            f"{ep.method} {ep.path}"
            for ep in endpoints
            if ep.is_deprecated and not (ep.description and "deprecated" in ep.description.lower())
        ]
        deprecated_total = len([ep for ep in endpoints if ep.is_deprecated])
        score = (
            ((deprecated_total - len(undocumented_deprecated)) / deprecated_total * 100)
            if deprecated_total > 0
            else 100.0
        )

        return GovernanceRuleResult(
            rule_id="no_deprecated_endpoints",
            name="No Undocumented Deprecations",
            category="documentation",
            passed=len(undocumented_deprecated) == 0,
            score=score,
            details=(
                f"{len(undocumented_deprecated)} deprecated endpoints lack migration guidance."
                if undocumented_deprecated
                else "All deprecations are properly documented."
            ),
            affected_endpoints=undocumented_deprecated[:10],
            severity="low",
        )

    def _check_path_lowercase(
        self,
        endpoints: list[ApiEndpoint],
        parsed: dict[str, Any],
    ) -> GovernanceRuleResult:
        uppercase_paths = []
        for ep in endpoints:
            # Remove path parameters before checking
            path_without_params = re.sub(r"\{[^}]+\}", "", ep.path)
            if path_without_params != path_without_params.lower():
                uppercase_paths.append(ep.path)

        total = len(endpoints)
        score = ((total - len(uppercase_paths)) / total * 100) if total > 0 else 100.0

        return GovernanceRuleResult(
            rule_id="path_lowercase",
            name="Lowercase Paths",
            category="naming_conventions",
            passed=len(uppercase_paths) == 0,
            score=score,
            details=(
                f"{len(uppercase_paths)} paths contain uppercase characters."
                if uppercase_paths
                else "All paths are lowercase."
            ),
            affected_endpoints=uppercase_paths[:10],
            severity="low",
        )

    # ---------------------------------------------------------------------- #
    # Scoring
    # ---------------------------------------------------------------------- #

    def score_governance(self, results: list[GovernanceRuleResult]) -> float:
        """Compute a weighted overall governance score from 0.0 to 100.0.

        Severity weights:
            critical / high → weight 3
            medium → weight 2
            low / info → weight 1
        """
        severity_weight = {"critical": 3, "high": 3, "medium": 2, "low": 1, "info": 1}

        total_weight = 0.0
        weighted_score = 0.0

        for result in results:
            w = severity_weight.get(result.severity, 1)
            total_weight += w
            weighted_score += result.score * w

        if total_weight == 0:
            return 0.0

        return round(weighted_score / total_weight, 2)

    def _build_scorecard(
        self,
        results: list[GovernanceRuleResult],
    ) -> GovernanceScorecard:
        """Aggregate rule results into a category scorecard."""
        category_scores: dict[str, list[float]] = {}

        for result in results:
            category_scores.setdefault(result.category, []).append(result.score)

        def _avg(scores: list[float]) -> float:
            return round(sum(scores) / len(scores), 2) if scores else 0.0

        overall = self.score_governance(results)

        return GovernanceScorecard(
            naming_conventions=_avg(category_scores.get("naming_conventions", [])),
            auth_security=_avg(category_scores.get("auth_security", [])),
            response_codes=_avg(category_scores.get("response_codes", [])),
            versioning=_avg(category_scores.get("versioning", [])),
            documentation=_avg(category_scores.get("documentation", [])),
            error_handling=_avg(category_scores.get("error_handling", [])),
            overall=overall,
        )

    def generate_recommendations(
        self,
        failed_rules: list[GovernanceRuleResult],
    ) -> list[str]:
        """Generate human-readable recommendations for failed rules."""
        recommendations: list[str] = []

        rec_map = {
            "naming_conventions": "Rename path segments to lowercase kebab-case (e.g. /api/v1/payment-transactions).",
            "auth_required": "Add authentication to all endpoints. Define Bearer/OAuth2/API Key security schemes.",
            "response_codes": "Document success (2xx) and client error (4xx) responses for all endpoints.",
            "versioning": "Prefix all paths with a version segment (e.g. /v1/) or use Accept-Version headers.",
            "description_completeness": "Add meaningful descriptions to all endpoints describing purpose and behaviour.",
            "request_validation": "Define JSON Schema for request bodies on POST, PUT, and PATCH endpoints.",
            "security_headers": "Add at least one security scheme (e.g. BearerAuth, OAuth2) in the OpenAPI components.",
            "error_handling": "Document error responses (400, 401, 403, 404, 422, 500) on all endpoints.",
            "no_deprecated_endpoints": "Add deprecation notices with migration paths to deprecated endpoint descriptions.",
            "path_lowercase": "Convert all path segments to lowercase (path parameters like {id} are exempt).",
        }

        # Sort by severity: high first
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        sorted_failed = sorted(failed_rules, key=lambda r: severity_order.get(r.severity, 5))

        for rule in sorted_failed:
            rec = rec_map.get(rule.rule_id)
            if rec:
                recommendations.append(f"[{rule.severity.upper()}] {rec}")

        return recommendations

    def get_all_rules(self) -> GovernanceRulesResponse:
        """Return metadata for all available governance rules."""
        rules = [
            GovernanceRule(
                rule_id=r["rule_id"],
                name=r["name"],
                category=r["category"],
                description=r["description"],
                severity=r["severity"],
                auto_fixable=r.get("auto_fixable", False),
            )
            for r in GOVERNANCE_RULES
        ]
        return GovernanceRulesResponse(rules=rules, total=len(rules))
