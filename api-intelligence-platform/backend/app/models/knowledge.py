"""Knowledge graph and AI-derived artefact SQLAlchemy models."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

try:
    from pgvector.sqlalchemy import Vector  # type: ignore[import]

    _VECTOR_AVAILABLE = True
except ImportError:
    _VECTOR_AVAILABLE = False


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Flow(Base):
    """A payment or business flow extracted from an API spec."""

    __tablename__ = "flows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    spec_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_specs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    flow_type: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # direct_pay | collect_pay | balance_enquiry | mandate | refund
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    steps: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)
    mermaid_diagram: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )


class ArchitectureEntity(Base):
    """An architectural entity (PSP, bank, switch, etc.) identified in a spec."""

    __tablename__ = "architecture_entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    spec_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_specs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    entity_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # psp | bank | npci | switch | merchant | customer
    properties: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )


class SecurityFinding(Base):
    """A security finding discovered during spec analysis."""

    __tablename__ = "security_findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    spec_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_specs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    endpoint_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_endpoints.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium"
    )  # critical | high | medium | low | info
    category: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )


class GovernanceReport(Base):
    """Governance validation report for an API spec."""

    __tablename__ = "governance_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    spec_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_specs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    passed_rules: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)
    failed_rules: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)
    recommendations: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)
    rule_details: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )


class ImpactReport(Base):
    """Impact analysis report produced when a change is evaluated."""

    __tablename__ = "impact_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    spec_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_specs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    change_description: Mapped[str] = mapped_column(Text, nullable=False)
    change_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    endpoint_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_endpoints.id", ondelete="SET NULL"),
        nullable=True,
    )
    impacted_endpoints: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)
    impacted_flows: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    blast_radius: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    ai_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    security_implications: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )


class AiConversation(Base):
    """Persistent AI chat conversation with RAG context."""

    __tablename__ = "ai_conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    messages: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True, default=list)
    spec_context_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_specs.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )


class DocumentChunk(Base):
    """A text chunk from a parsed document, stored with its embedding vector."""

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    spec_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_specs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="general"
    )  # api | flow | schema | security | general
    chunk_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata", JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    if _VECTOR_AVAILABLE:
        embedding: Mapped[Optional[list[float]]] = mapped_column(
            Vector(1536), nullable=True
        )
    else:
        embedding: Mapped[Optional[list[float]]] = mapped_column(JSON, nullable=True)
