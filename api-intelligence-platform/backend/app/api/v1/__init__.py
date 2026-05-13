"""API v1 routes.

This module intentionally hosts a minimal but functional API surface so the
frontend can start integrating against real backend data during early
development.
"""
from __future__ import annotations

import re
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
from app.models.api_spec import ApiDependency, ApiEndpoint
from app.models.knowledge import DocumentChunk, Flow
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.schemas.catalog import ApiSpecCreate
from app.services.catalog_service import CatalogService
from app.services.document_service import DocumentService
from app.services.ingestion_service import IngestionService

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
document_service = DocumentService()
ingestion_service = IngestionService()


def _spec_to_frontend(
    spec: Any,
    endpoint_count: int | None = None,
    endpoints_override: list[Any] | None = None,
) -> dict[str, Any]:
    """Map ApiSpec ORM object to the frontend shape."""
    if endpoints_override is not None:
        endpoints = list(endpoints_override)
    else:
        loaded_endpoints = getattr(spec, "__dict__", {}).get("endpoints")
        endpoints = list(loaded_endpoints or []) if loaded_endpoints is not None else []
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
        "endpoints_count": endpoint_count if endpoint_count is not None else len(endpoints),
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


def _extract_endpoints_from_text(text: str) -> list[dict[str, Any]]:
    """Extract method/path pairs from semi-structured PDF text."""
    pattern = re.compile(
        r"\b(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\b\s+(/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%{}-]*)",
        re.IGNORECASE,
    )
    seen: set[tuple[str, str]] = set()
    endpoints: list[dict[str, Any]] = []

    for match in pattern.finditer(text):
        method = match.group(1).upper()
        path = match.group(2).rstrip(").,;:")
        key = (method, path)
        if key in seen:
            continue
        seen.add(key)

        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        if line_end == -1:
            line_end = len(text)
        line = text[line_start:line_end].strip()
        context = text[max(0, match.start() - 160) : min(len(text), match.end() + 160)]
        context_lower = context.lower()

        risk_level = "low"
        if any(keyword in path.lower() for keyword in ["payment", "transfer", "refund", "settle"]):
            risk_level = "high"
        elif method in {"DELETE", "PUT", "PATCH"}:
            risk_level = "medium"

        auth_method = None
        if "bearer" in context_lower or "jwt" in context_lower:
            auth_method = "bearer"
        elif "api key" in context_lower:
            auth_method = "api_key"

        endpoints.append(
            {
                "path": path,
                "method": method,
                "summary": line or f"{method} {path}",
                "description": line if line and line != f"{method} {path}" else "",
                "auth_method": auth_method,
                "tags": ["pdf-import"],
                "risk_level": risk_level,
                "is_deprecated": False,
                "parameters": [],
                "request_schema": None,
                "response_schema": {},
            }
        )

    return endpoints


async def _ingest_pdf_spec(
    *,
    spec: Any,
    file_path: Path,
    provided_name: str,
    provided_version: str | None,
    provided_description: str,
    db: AsyncSession,
) -> list[ApiEndpoint]:
    """Parse a PDF and persist searchable chunks without AI dependencies."""
    sections = await document_service.parse_pdf(str(file_path))
    full_text = "\n\n".join(section.get("content", "") for section in sections).strip()

    metadata = await document_service.extract_metadata(full_text)
    chunks = await document_service.chunk_document(sections) if sections else []
    endpoint_records: list[ApiEndpoint] = []

    spec.name = (
        provided_name.strip()
        or metadata.get("title")
        or Path(file_path.name).stem
        or "Uploaded PDF Spec"
    )
    normalized_version = (provided_version or "").strip()
    spec.version = normalized_version or metadata.get("version") or spec.version
    spec.description = (
        provided_description.strip()
        or metadata.get("description")
        or spec.description
        or ""
    )
    spec.parsed_content = {
        "type": "pdf",
        "metadata": metadata,
        "section_count": len(sections),
        "preview": full_text[:4000],
    }

    for index, chunk in enumerate(chunks):
        db.add(
            DocumentChunk(
                spec_id=spec.id,
                chunk_index=chunk.get("chunk_index", index),
                content=chunk["content"],
                chunk_type=chunk.get("chunk_type", "general"),
                chunk_metadata=chunk.get("metadata"),
                embedding=None,
            )
        )

    for ep_data in _extract_endpoints_from_text(full_text):
        endpoint = ApiEndpoint(
            spec_id=spec.id,
            name=ep_data.get("summary") or ep_data.get("path"),
            path=ep_data["path"],
            method=ep_data["method"],
            description=ep_data.get("description"),
            request_schema=ep_data.get("request_schema"),
            response_schema=ep_data.get("response_schema"),
            auth_method=ep_data.get("auth_method"),
            tags=ep_data.get("tags", []),
            risk_level=ep_data.get("risk_level", "low"),
            is_deprecated=bool(ep_data.get("is_deprecated", False)),
            parameters=ep_data.get("parameters"),
        )
        db.add(endpoint)
        endpoint_records.append(endpoint)

    spec.status = "ready"
    await db.flush()
    return endpoint_records


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
    name: str = Form(default=""),
    version: str = Form(default=""),
    description: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Upload a spec file and create a catalog record.

    OpenAPI uploads are parsed immediately so the catalog becomes usable
    without requiring the full AI ingestion stack.
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

    resolved_name = name.strip() or Path(file.filename or "spec").stem or "Uploaded Spec"

    created = await catalog_service.create_spec(
        db=db,
        spec_data=ApiSpecCreate(
            name=resolved_name,
            version=version.strip() or None,
            description=description,
            source_type=source_type,
        ),
        user_id=current_user.id,
        org_id=current_user.org_id,
        file_path=str(target_path),
    )

    endpoint_records: list[ApiEndpoint] = []
    if source_type in {"openapi", "swagger", "asyncapi"}:
        try:
            parsed_openapi = await document_service.parse_openapi(content)
            created.parsed_content = parsed_openapi
            created.version = (
                parsed_openapi.get("info", {}).get("version") or created.version
            )
            created.description = (
                parsed_openapi.get("info", {}).get("description") or created.description
            )

            extracted_endpoints = ingestion_service._extract_endpoints_from_openapi(
                parsed_openapi
            )
            for ep_data in extracted_endpoints:
                endpoint = ApiEndpoint(
                    spec_id=created.id,
                    name=ep_data.get("summary")
                    or ep_data.get("name")
                    or ep_data.get("path"),
                    path=ep_data.get("path", "/"),
                    method=(ep_data.get("method") or "GET").upper(),
                    description=ep_data.get("description"),
                    request_schema=ep_data.get("request_schema"),
                    response_schema=ep_data.get("response_schema"),
                    auth_method=ep_data.get("auth_method"),
                    tags=ep_data.get("tags", []),
                    risk_level=ep_data.get("risk_level", "low"),
                    is_deprecated=bool(ep_data.get("is_deprecated", False)),
                    parameters=ep_data.get("parameters"),
                )
                db.add(endpoint)
                endpoint_records.append(endpoint)

            await db.flush()

            if len(endpoint_records) > 1:
                dependencies = ingestion_service._infer_dependencies_from_openapi(
                    parsed_openapi, endpoint_records
                )
                for dep_data in dependencies:
                    db.add(ApiDependency(**dep_data))

            created.status = "ready"
            await db.flush()
        except Exception as exc:
            created.status = "failed"
            created.error_message = f"OpenAPI parse failed: {exc}"[:2000]
            await db.flush()
    elif source_type == "pdf":
        try:
            endpoint_records = await _ingest_pdf_spec(
                spec=created,
                file_path=target_path,
                provided_name=name,
                provided_version=version,
                provided_description=description,
                db=db,
            )
        except Exception as exc:
            created.status = "failed"
            created.error_message = f"PDF parse failed: {exc}"[:2000]
            await db.flush()

    return _spec_to_frontend(
        created,
        endpoint_count=len(endpoint_records),
        endpoints_override=endpoint_records,
    )


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
