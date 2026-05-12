"""Pydantic schemas for governance validation."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class GovernanceRequest(BaseModel):
    """Request payload to trigger governance validation for a spec."""

    spec_id: uuid.UUID


class GovernanceRuleResult(BaseModel):
    """Result of evaluating a single governance rule."""

    rule_id: str
    name: str
    category: str
    passed: bool
    score: float = Field(ge=0.0, le=100.0)
    details: str = ""
    affected_endpoints: List[str] = Field(default_factory=list)
    severity: str = "medium"  # critical | high | medium | low | info


class GovernanceScorecard(BaseModel):
    """Scorecard breakdown by governance category."""

    naming_conventions: float = 0.0
    auth_security: float = 0.0
    response_codes: float = 0.0
    versioning: float = 0.0
    documentation: float = 0.0
    error_handling: float = 0.0
    overall: float = 0.0


class GovernanceResponse(BaseModel):
    """Full governance validation report."""

    report_id: uuid.UUID
    spec_id: uuid.UUID
    overall_score: float = Field(ge=0.0, le=100.0)
    grade: str  # A | B | C | D | F
    scorecard: GovernanceScorecard
    passed_rules: List[GovernanceRuleResult] = Field(default_factory=list)
    failed_rules: List[GovernanceRuleResult] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    summary: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


class GovernanceRule(BaseModel):
    """Metadata describing an available governance rule."""

    rule_id: str
    name: str
    category: str
    description: str
    severity: str
    auto_fixable: bool = False


class GovernanceRulesResponse(BaseModel):
    """Response listing all available governance rules."""

    rules: List[GovernanceRule]
    total: int


class GovernanceReportListItem(BaseModel):
    """Lightweight governance report list item."""

    id: uuid.UUID
    spec_id: uuid.UUID
    overall_score: float
    grade: str
    passed_count: int
    failed_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
