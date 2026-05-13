"""API v1 routes.

This module intentionally hosts a minimal but functional API surface so the
frontend can start integrating against real backend data during early
development.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    get_current_user,
    verify_password,
)
from app.db.database import get_db
from app.models.api_spec import ApiEndpoint
from app.models.knowledge import Flow
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.schemas.catalog import ApiSpecCreate
from app.services.catalog_service import CatalogService

async def require_database_ready(request: Request) -> None:
    """Return a clear 503 when the API is running without database access."""
    if not getattr(request.app.state, "database_ready", False):
        detail = getattr(
            request.app.state,
            "database_error",
            "Database is unavailable.",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {detail}",
        )


router = APIRouter(dependencies=[Depends(require_database_ready)])
catalog_service = CatalogService()


def _spec_to_frontend(spec: Any, endpoint_count: int = 0) -> dict[str, Any]:
    """Map ApiSpec ORM object to the frontend shape."""
    endpoints = list(getattr(spec, "endpoints", []) or [])
    risk_rank = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    max_risk = "low"
    for ep in endpoints:
        level = (ep.risk_level or "low").lower()
        if risk_rank.get(level, 1) > risk_rank.get(max_risk, 1):
            max_risk = level

    auth_methods = sorted(
        {ep.auth_method for ep in endpoints if getattr(ep, "auth_method", None)}
    )

    return {
        "id": str(spec.id),
        "name": spec.name,
        "version": spec.version or "1.0.0",
        "description": spec.description or "",
        "status": "active" if spec.status == "ready" else "draft",
        "tags": [],
        "base_url": None,
        "openapi_version": None,
        "endpoints_count": endpoint_count or len(endpoints),
        "flows_count": 0,
        "dependencies_count": 0,
        "governance_score": None,
        "risk_level": max_risk,
        "auth_methods": auth_methods or ["none"],
        "uploaded_by": str(spec.created_by) if spec.created_by else "system",
        "created_at": spec.created_at.isoformat(),
        "updated_at": spec.updated_at.isoformat(),
    }


def _endpoint_to_frontend(endpoint: ApiEndpoint) -> dict[str, Any]:
    """Map ApiEndpoint ORM object to the frontend shape."""
    return {
        "id": str(endpoint.id),
        "spec_id": str(endpoint.spec_id),
        "path": endpoint.path,
        "method": endpoint.method.upper(),
        "operation_id": endpoint.name,
        "summary": endpoint.name or f"{endpoint.method.upper()} {endpoint.path}",
        "description": endpoint.description or "",
        "tags": endpoint.tags or [],
        "risk_level": (endpoint.risk_level or "low").lower(),
        "auth_required": bool(endpoint.auth_method),
        "auth_method": endpoint.auth_method or "none",
        "deprecated": endpoint.is_deprecated,
        "request_body": endpoint.request_schema,
        "responses": endpoint.response_schema or {},
        "parameters": endpoint.parameters or [],
        "security_findings": [],
        "created_at": endpoint.created_at.isoformat(),
        "updated_at": endpoint.created_at.isoformat(),
    }


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Authenticate and return JWT token."""
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(
        subject=user.id,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra_claims={
            "role": user.role,
            "org_id": str(user.org_id) if user.org_id else None,
        },
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/auth/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the authenticated user profile."""
    return UserResponse.model_validate(current_user)


@router.get("/specs")
async def list_specs(
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
) -> dict[str, Any]:
    """List API specs with lightweight frontend-compatible shape."""
    paginated = await catalog_service.get_specs(
        db=db,
        search=search,
        page=page,
        size=page_size,
    )
    items = []
    for spec in paginated.items:
        endpoint_count = len(getattr(spec, "endpoints", []) or [])
        items.append(_spec_to_frontend(spec, endpoint_count=endpoint_count))
    return {
        "items": items,
        "total": paginated.total,
        "page": page,
        "page_size": page_size,
        "has_next": page * page_size < paginated.total,
        "has_prev": page > 1,
    }


@router.get("/specs/{spec_id}")
async def get_spec(spec_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Get one API spec."""
    spec = await catalog_service.get_spec(db, spec_id)
    if not spec:
        raise HTTPException(status_code=404, detail="Spec not found")
    return _spec_to_frontend(spec, endpoint_count=len(spec.endpoints))


@router.get("/specs/{spec_id}/endpoints")
async def list_spec_endpoints(
    spec_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    search: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    auth_method: str | None = Query(default=None),
    deprecated: bool | None = Query(default=None),
) -> dict[str, Any]:
    """List endpoints for a given spec."""
    paginated = await catalog_service.get_endpoints(
        db=db,
        spec_id=spec_id,
        risk_level=risk_level,
        is_deprecated=deprecated,
        search=search,
        page=page,
        size=page_size,
    )
    items = []
    for endpoint in paginated.items:
        if auth_method and (endpoint.auth_method or "none") != auth_method:
            continue
        items.append(_endpoint_to_frontend(endpoint))
    total = len(items) if auth_method else paginated.total
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": page * page_size < total,
        "has_prev": page > 1,
    }


@router.get("/specs/{spec_id}/dependencies")
async def list_spec_dependencies(
    spec_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List endpoint dependency edges for a spec."""
    deps = await catalog_service.get_dependencies(db, spec_id)
    return [
        {
            "id": str(dep.id),
            "source_spec_id": str(spec_id),
            "target_spec_id": str(spec_id),
            "source_endpoint_id": str(dep.source_endpoint_id),
            "target_endpoint_id": str(dep.target_endpoint_id),
            "relationship_type": dep.dependency_type.upper(),
            "weight": dep.strength,
            "description": None,
            "created_at": dep.created_at.isoformat(),
        }
        for dep in deps
    ]


@router.get("/specs/{spec_id}/flows")
async def list_spec_flows(
    spec_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List extracted flows for a spec."""
    result = await db.execute(select(Flow).where(Flow.spec_id == spec_id))
    flows = result.scalars().all()
    return [
        {
            "id": str(flow.id),
            "spec_id": str(flow.spec_id),
            "name": flow.name,
            "description": flow.description or "",
            "type": flow.flow_type or "generic",
            "mermaid_diagram": flow.mermaid_diagram or "",
            "steps": flow.steps or [],
            "involved_apis": [],
            "involved_endpoints": [],
            "created_at": flow.created_at.isoformat(),
            "updated_at": flow.created_at.isoformat(),
        }
        for flow in flows
    ]


@router.post("/specs/upload")
async def upload_spec(
    file: UploadFile = File(...),
    name: str = Form(...),
    version: str = Form(...),
    description: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Upload a spec file and create a catalog record.

    Ingestion is not started in this bootstrap endpoint yet.
    """
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{uuid.uuid4()}_{file.filename or 'spec'}"
    target_path = upload_dir / file_name
    content = await file.read()
    target_path.write_bytes(content)

    source_type = "openapi"
    suffix = (Path(file.filename or "").suffix or "").lower()
    if suffix == ".pdf":
        source_type = "pdf"
    elif suffix in {".yaml", ".yml", ".json"}:
        source_type = "openapi"
    elif suffix == ".xml":
        source_type = "xml"

    created = await catalog_service.create_spec(
        db=db,
        spec_data=ApiSpecCreate(
            name=name,
            version=version,
            description=description,
            source_type=source_type,
        ),
        user_id=current_user.id,
        org_id=current_user.org_id,
        file_path=str(target_path),
    )
    return _spec_to_frontend(created, endpoint_count=0)


@router.post("/search")
async def search(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Simple keyword search bootstrap endpoint for frontend integration."""
    query = str(payload.get("query", "")).strip()
    spec_id_raw = payload.get("spec_id")
    spec_id = uuid.UUID(spec_id_raw) if spec_id_raw else None
    if not query:
        return {"results": [], "total": 0, "query": "", "processing_time_ms": 0}

    endpoints = await catalog_service.search_endpoints(
        db=db,
        query=query,
        spec_id=spec_id,
    )
    results = [
        {
            "chunk": {
                "id": str(endpoint.id),
                "spec_id": str(endpoint.spec_id),
                "content": endpoint.description or endpoint.name or endpoint.path,
                "chunk_type": "endpoint",
                "endpoint_id": str(endpoint.id),
                "metadata": {
                    "path": endpoint.path,
                    "method": endpoint.method,
                },
            },
            "score": 1.0,
            "endpoint": _endpoint_to_frontend(endpoint),
            "spec": None,
        }
        for endpoint in endpoints
    ]
    return {
        "results": results,
        "total": len(results),
        "query": query,
        "spec_id": str(spec_id) if spec_id else None,
        "processing_time_ms": 1,
    }
