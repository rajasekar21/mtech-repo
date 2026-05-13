"""Pydantic schemas for impact analysis."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ImpactRequest(BaseModel):
    """Request payload for running an impact analysis."""

    spec_id: uuid.UUID
    change_description: str = Field(min_length=5, max_length=5000)
    endpoint_id: Optional[uuid.UUID] = None
    change_type: str = Field(default="breaking")  # breaking | additive | deprecation | security


class ImpactedEndpoint(BaseModel):
    """Summary of an impacted endpoint."""

    id: uuid.UUID
    path: str
    method: str
    name: Optional[str]
    risk_level: str
    impact_reason: str
    distance: int = 0  # graph hops from the changed endpoint


class ImpactedFlow(BaseModel):
    """Summary of an impacted business flow."""

    id: uuid.UUID
    name: str
    flow_type: Optional[str]
    impact_reason: str


class BlastRadiusNode(BaseModel):
    """A node in the blast radius visualisation graph."""

    id: str
    label: str
    type: str  # endpoint | flow | entity
    risk_level: Optional[str] = None
    distance: int = 0


class BlastRadiusEdge(BaseModel):
    """An edge in the blast radius visualisation graph."""

    source: str
    target: str
    relationship: str


class BlastRadius(BaseModel):
    """Graph data for blast radius visualisation (React Flow compatible)."""

    nodes: List[BlastRadiusNode] = Field(default_factory=list)
    edges: List[BlastRadiusEdge] = Field(default_factory=list)
    total_affected: int = 0


class ImpactResponse(BaseModel):
    """Full impact analysis result."""

    report_id: uuid.UUID
    spec_id: uuid.UUID
    change_description: str
    change_type: str
    endpoint_id: Optional[uuid.UUID]
    risk_score: float = Field(ge=0.0, le=100.0)
    risk_level: str  # low | medium | high | critical
    impacted_endpoints: List[ImpactedEndpoint] = Field(default_factory=list)
    impacted_flows: List[ImpactedFlow] = Field(default_factory=list)
    blast_radius: BlastRadius = Field(default_factory=BlastRadius)
    ai_analysis: str = ""
    security_implications: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class ImpactReportListItem(BaseModel):
    """Lightweight impact report list item."""

    id: uuid.UUID
    spec_id: uuid.UUID
    change_description: str
    change_type: Optional[str]
    risk_score: float
    impacted_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
