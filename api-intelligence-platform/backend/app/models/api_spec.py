"""API Specification and Endpoint SQLAlchemy models."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ApiSpec(Base):
    """Represents an ingested API specification document."""

    __tablename__ = "api_specs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="openapi"
    )  # pdf | openapi | xml | swagger | asyncapi
    source_file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    parsed_content: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )  # pending | processing | ready | failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
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

    # Relationships
    endpoints: Mapped[list["ApiEndpoint"]] = relationship(
        "ApiEndpoint", back_populates="spec", cascade="all, delete-orphan"
    )
    versions: Mapped[list["ApiVersion"]] = relationship(
        "ApiVersion", back_populates="spec", cascade="all, delete-orphan"
    )


class ApiEndpoint(Base):
    """Represents a single API endpoint extracted from a spec."""

    __tablename__ = "api_endpoints"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    spec_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_specs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)  # GET, POST, etc.
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    request_schema: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    response_schema: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    auth_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tags: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default="low"
    )  # low | medium | high | critical
    is_deprecated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parameters: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    # Relationships
    spec: Mapped["ApiSpec"] = relationship("ApiSpec", back_populates="endpoints")
    outgoing_dependencies: Mapped[list["ApiDependency"]] = relationship(
        "ApiDependency",
        foreign_keys="ApiDependency.source_endpoint_id",
        back_populates="source_endpoint",
        cascade="all, delete-orphan",
    )
    incoming_dependencies: Mapped[list["ApiDependency"]] = relationship(
        "ApiDependency",
        foreign_keys="ApiDependency.target_endpoint_id",
        back_populates="target_endpoint",
        cascade="all, delete-orphan",
    )


class ApiDependency(Base):
    """Directed dependency relationship between two API endpoints."""

    __tablename__ = "api_dependencies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_endpoint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_endpoints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_endpoint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_endpoints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dependency_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="calls"
    )  # calls | depends_on | authenticates_with
    strength: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    # Relationships
    source_endpoint: Mapped["ApiEndpoint"] = relationship(
        "ApiEndpoint",
        foreign_keys=[source_endpoint_id],
        back_populates="outgoing_dependencies",
    )
    target_endpoint: Mapped["ApiEndpoint"] = relationship(
        "ApiEndpoint",
        foreign_keys=[target_endpoint_id],
        back_populates="incoming_dependencies",
    )


class ApiVersion(Base):
    """Version record for an API spec, enabling changelog tracking."""

    __tablename__ = "api_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    spec_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_specs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[str] = mapped_column(String(100), nullable=False)
    changelog: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    # Relationships
    spec: Mapped["ApiSpec"] = relationship("ApiSpec", back_populates="versions")
