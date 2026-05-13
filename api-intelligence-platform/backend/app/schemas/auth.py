"""Pydantic schemas for authentication and user management."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #

class LoginRequest(BaseModel):
    """Credentials for the login endpoint."""

    email: EmailStr
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    """JWT access token returned after successful login."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenRefreshRequest(BaseModel):
    """Request body for token refresh."""

    refresh_token: str


# --------------------------------------------------------------------------- #
# Organization
# --------------------------------------------------------------------------- #

class OrgCreate(BaseModel):
    """Payload for creating a new organisation."""

    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    plan: str = Field(default="free")

    @field_validator("plan")
    @classmethod
    def _validate_plan(cls, v: str) -> str:
        allowed = {"free", "starter", "pro", "enterprise"}
        if v not in allowed:
            raise ValueError(f"plan must be one of {allowed}")
        return v


class OrgResponse(BaseModel):
    """Serialised organisation resource."""

    id: uuid.UUID
    name: str
    slug: str
    plan: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# User
# --------------------------------------------------------------------------- #

class UserCreate(BaseModel):
    """Payload for registering a new user."""

    email: EmailStr
    password: str = Field(min_length=8)
    full_name: Optional[str] = Field(default=None, max_length=255)
    role: str = Field(default="developer")
    org_id: Optional[uuid.UUID] = None

    @field_validator("role")
    @classmethod
    def _validate_role(cls, v: str) -> str:
        allowed = {"admin", "architect", "developer", "viewer"}
        if v not in allowed:
            raise ValueError(f"role must be one of {allowed}")
        return v


class UserResponse(BaseModel):
    """Serialised user resource (no sensitive fields)."""

    id: uuid.UUID
    email: str
    full_name: Optional[str]
    role: str
    org_id: Optional[uuid.UUID]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Partial update payload for a user profile."""

    full_name: Optional[str] = Field(default=None, max_length=255)
    role: Optional[str] = None

    @field_validator("role")
    @classmethod
    def _validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"admin", "architect", "developer", "viewer"}
        if v not in allowed:
            raise ValueError(f"role must be one of {allowed}")
        return v
