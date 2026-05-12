"""Pydantic schemas for the API catalog."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# --------------------------------------------------------------------------- #
# Generic pagination wrapper
# --------------------------------------------------------------------------- #

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated list response."""

    items: List[T]
    total: int
    page: int
    size: int
    pages: int

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# ApiSpec schemas
# --------------------------------------------------------------------------- #

class ApiSpecCreate(BaseModel):
    """Payload for creating a new API spec record (without file)."""

    name: str = Field(min_length=1, max_length=500)
    version: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    source_type: str = Field(default="openapi")

    class Config:
        from_attributes = True


class ApiSpecUpdate(BaseModel):
    """Partial update payload for an API spec."""

    name: Optional[str] = Field(default=None, max_length=500)
    version: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None


class ApiSpecResponse(BaseModel):
    """Serialised API spec resource."""

    id: uuid.UUID
    org_id: Optional[uuid.UUID]
    name: str
    version: Optional[str]
    description: Optional[str]
    source_type: str
    source_file_path: Optional[str]
    status: str
    error_message: Optional[str]
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApiSpecDetailResponse(ApiSpecResponse):
    """Extended spec response including endpoints."""

    endpoints: List["ApiEndpointResponse"] = Field(default_factory=list)
    endpoint_count: int = 0

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# ApiEndpoint schemas
# --------------------------------------------------------------------------- #

class ApiEndpointResponse(BaseModel):
    """Serialised API endpoint resource."""

    id: uuid.UUID
    spec_id: uuid.UUID
    name: Optional[str]
    path: str
    method: str
    description: Optional[str]
    request_schema: Optional[dict[str, Any]]
    response_schema: Optional[dict[str, Any]]
    auth_method: Optional[str]
    tags: Optional[list[str]]
    risk_level: str
    is_deprecated: bool
    parameters: Optional[dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiEndpointFilter(BaseModel):
    """Query filter parameters for endpoint listing."""

    method: Optional[str] = None
    tag: Optional[str] = None
    risk_level: Optional[str] = None
    is_deprecated: Optional[bool] = None
    search: Optional[str] = None


# --------------------------------------------------------------------------- #
# ApiDependency schemas
# --------------------------------------------------------------------------- #

class ApiDependencyResponse(BaseModel):
    """Serialised dependency relationship."""

    id: uuid.UUID
    source_endpoint_id: uuid.UUID
    target_endpoint_id: uuid.UUID
    dependency_type: str
    strength: float
    created_at: datetime

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# ApiVersion schemas
# --------------------------------------------------------------------------- #

class ApiVersionResponse(BaseModel):
    """Serialised API version record."""

    id: uuid.UUID
    spec_id: uuid.UUID
    version_number: str
    changelog: Optional[dict[str, Any]]
    is_current: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class VersionCompareRequest(BaseModel):
    """Request payload to compare two API spec versions."""

    spec_id_a: uuid.UUID
    spec_id_b: uuid.UUID


class VersionCompareResponse(BaseModel):
    """Structured diff between two API spec versions."""

    added_endpoints: List[ApiEndpointResponse] = Field(default_factory=list)
    removed_endpoints: List[ApiEndpointResponse] = Field(default_factory=list)
    modified_endpoints: List[dict[str, Any]] = Field(default_factory=list)
    breaking_changes: List[str] = Field(default_factory=list)
    summary: str = ""
