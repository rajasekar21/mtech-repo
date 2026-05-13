"""Catalog service — CRUD and query operations for API specs and endpoints."""
from __future__ import annotations

import math
import uuid
from typing import Any, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.api_spec import ApiDependency, ApiEndpoint, ApiSpec, ApiVersion
from app.schemas.catalog import (
    ApiSpecCreate,
    PaginatedResponse,
    VersionCompareResponse,
)

logger = get_logger(__name__)


class CatalogService:
    """Service for managing the API spec catalog."""

    # ---------------------------------------------------------------------- #
    # ApiSpec
    # ---------------------------------------------------------------------- #

    async def create_spec(
        self,
        db: AsyncSession,
        spec_data: ApiSpecCreate,
        user_id: uuid.UUID,
        org_id: Optional[uuid.UUID] = None,
        file_path: Optional[str] = None,
    ) -> ApiSpec:
        """Create a new API spec record.

        Args:
            db: Async database session.
            spec_data: Validated spec creation payload.
            user_id: UUID of the creating user.
            org_id: Organisation UUID.
            file_path: Path to the uploaded file, if any.

        Returns:
            The newly created ApiSpec ORM instance.
        """
        spec = ApiSpec(
            org_id=org_id,
            name=spec_data.name,
            version=spec_data.version,
            description=spec_data.description,
            source_type=spec_data.source_type,
            source_file_path=file_path,
            status="pending",
            created_by=user_id,
        )
        db.add(spec)
        await db.flush()  # get the generated ID
        await db.refresh(spec)
        logger.info("ApiSpec created", spec_id=str(spec.id), name=spec.name)
        return spec

    async def get_specs(
        self,
        db: AsyncSession,
        org_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        source_type: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> PaginatedResponse:
        """Return a paginated list of API specs.

        Args:
            db: Async session.
            org_id: Filter by organisation.
            status: Filter by ingestion status.
            source_type: Filter by source type.
            search: Full-text search on name/description.
            page: 1-based page number.
            size: Items per page.

        Returns:
            PaginatedResponse containing ApiSpec items.
        """
        filters = []
        if org_id:
            filters.append(ApiSpec.org_id == org_id)
        if status:
            filters.append(ApiSpec.status == status)
        if source_type:
            filters.append(ApiSpec.source_type == source_type)
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    ApiSpec.name.ilike(pattern),
                    ApiSpec.description.ilike(pattern),
                )
            )

        count_stmt = select(func.count()).select_from(ApiSpec)
        if filters:
            count_stmt = count_stmt.where(and_(*filters))

        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        stmt = select(ApiSpec).order_by(ApiSpec.created_at.desc())
        if filters:
            stmt = stmt.where(and_(*filters))
        stmt = stmt.offset((page - 1) * size).limit(size)

        result = await db.execute(stmt)
        specs = result.scalars().all()

        return PaginatedResponse(
            items=list(specs),
            total=total,
            page=page,
            size=size,
            pages=math.ceil(total / size) if total else 0,
        )

    async def get_spec(
        self,
        db: AsyncSession,
        spec_id: uuid.UUID,
    ) -> Optional[ApiSpec]:
        """Fetch a single API spec with its endpoints eagerly loaded.

        Args:
            db: Async session.
            spec_id: UUID of the spec.

        Returns:
            ApiSpec instance or None if not found.
        """
        stmt = (
            select(ApiSpec)
            .options(selectinload(ApiSpec.endpoints))
            .where(ApiSpec.id == spec_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_spec_status(
        self,
        db: AsyncSession,
        spec_id: uuid.UUID,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """Update the processing status of a spec."""
        spec = await db.get(ApiSpec, spec_id)
        if spec:
            spec.status = status
            if error_message:
                spec.error_message = error_message
            await db.flush()

    # ---------------------------------------------------------------------- #
    # ApiEndpoint
    # ---------------------------------------------------------------------- #

    async def get_endpoints(
        self,
        db: AsyncSession,
        spec_id: uuid.UUID,
        method: Optional[str] = None,
        tag: Optional[str] = None,
        risk_level: Optional[str] = None,
        is_deprecated: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ) -> PaginatedResponse:
        """Return a paginated list of endpoints for a spec."""
        filters = [ApiEndpoint.spec_id == spec_id]

        if method:
            filters.append(ApiEndpoint.method == method.upper())
        if risk_level:
            filters.append(ApiEndpoint.risk_level == risk_level)
        if is_deprecated is not None:
            filters.append(ApiEndpoint.is_deprecated == is_deprecated)
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    ApiEndpoint.path.ilike(pattern),
                    ApiEndpoint.name.ilike(pattern),
                    ApiEndpoint.description.ilike(pattern),
                )
            )

        count_stmt = select(func.count()).select_from(ApiEndpoint).where(and_(*filters))
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        stmt = (
            select(ApiEndpoint)
            .where(and_(*filters))
            .order_by(ApiEndpoint.path, ApiEndpoint.method)
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await db.execute(stmt)
        endpoints = result.scalars().all()

        return PaginatedResponse(
            items=list(endpoints),
            total=total,
            page=page,
            size=size,
            pages=math.ceil(total / size) if total else 0,
        )

    async def get_endpoint(
        self,
        db: AsyncSession,
        endpoint_id: uuid.UUID,
    ) -> Optional[ApiEndpoint]:
        """Fetch a single endpoint by ID."""
        return await db.get(ApiEndpoint, endpoint_id)

    async def search_endpoints(
        self,
        db: AsyncSession,
        query: str,
        spec_id: Optional[uuid.UUID] = None,
    ) -> list[ApiEndpoint]:
        """Simple text search across endpoint paths, names, and descriptions."""
        pattern = f"%{query}%"
        filters = [
            or_(
                ApiEndpoint.path.ilike(pattern),
                ApiEndpoint.name.ilike(pattern),
                ApiEndpoint.description.ilike(pattern),
            )
        ]
        if spec_id:
            filters.append(ApiEndpoint.spec_id == spec_id)

        stmt = (
            select(ApiEndpoint)
            .where(and_(*filters))
            .order_by(ApiEndpoint.path)
            .limit(50)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    # ---------------------------------------------------------------------- #
    # ApiDependency
    # ---------------------------------------------------------------------- #

    async def get_dependencies(
        self,
        db: AsyncSession,
        spec_id: uuid.UUID,
    ) -> list[ApiDependency]:
        """Return all dependencies for endpoints in a given spec."""
        # Sub-select endpoint IDs belonging to this spec
        endpoint_ids_stmt = select(ApiEndpoint.id).where(
            ApiEndpoint.spec_id == spec_id
        )
        stmt = select(ApiDependency).where(
            ApiDependency.source_endpoint_id.in_(endpoint_ids_stmt)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    # ---------------------------------------------------------------------- #
    # ApiVersion
    # ---------------------------------------------------------------------- #

    async def get_versions(
        self,
        db: AsyncSession,
        spec_id: uuid.UUID,
    ) -> list[ApiVersion]:
        """Return all version records for a spec."""
        stmt = (
            select(ApiVersion)
            .where(ApiVersion.spec_id == spec_id)
            .order_by(ApiVersion.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def compare_versions(
        self,
        db: AsyncSession,
        spec_id_a: uuid.UUID,
        spec_id_b: uuid.UUID,
    ) -> VersionCompareResponse:
        """Compare endpoints between two API spec versions.

        Args:
            db: Async session.
            spec_id_a: UUID of the baseline spec.
            spec_id_b: UUID of the comparison spec.

        Returns:
            VersionCompareResponse with added, removed, and modified endpoints.
        """
        # Load endpoints for both specs
        stmt_a = select(ApiEndpoint).where(ApiEndpoint.spec_id == spec_id_a)
        stmt_b = select(ApiEndpoint).where(ApiEndpoint.spec_id == spec_id_b)

        result_a = await db.execute(stmt_a)
        result_b = await db.execute(stmt_b)

        endpoints_a = {
            f"{ep.method.upper()} {ep.path}": ep for ep in result_a.scalars().all()
        }
        endpoints_b = {
            f"{ep.method.upper()} {ep.path}": ep for ep in result_b.scalars().all()
        }

        keys_a = set(endpoints_a.keys())
        keys_b = set(endpoints_b.keys())

        added_keys = keys_b - keys_a
        removed_keys = keys_a - keys_b
        common_keys = keys_a & keys_b

        added = [endpoints_b[k] for k in sorted(added_keys)]
        removed = [endpoints_a[k] for k in sorted(removed_keys)]

        modified = []
        breaking_changes = []

        for key in sorted(common_keys):
            ep_a = endpoints_a[key]
            ep_b = endpoints_b[key]
            diffs: dict[str, Any] = {}

            if ep_a.description != ep_b.description:
                diffs["description"] = {"old": ep_a.description, "new": ep_b.description}
            if ep_a.auth_method != ep_b.auth_method:
                diffs["auth_method"] = {"old": ep_a.auth_method, "new": ep_b.auth_method}
                breaking_changes.append(f"Auth method changed on {key}")
            if ep_a.request_schema != ep_b.request_schema:
                diffs["request_schema"] = "changed"
                breaking_changes.append(f"Request schema changed on {key}")
            if ep_a.response_schema != ep_b.response_schema:
                diffs["response_schema"] = "changed"
            if ep_a.is_deprecated != ep_b.is_deprecated and ep_b.is_deprecated:
                diffs["is_deprecated"] = True
                breaking_changes.append(f"Endpoint deprecated: {key}")

            if diffs:
                modified.append(
                    {
                        "endpoint_key": key,
                        "endpoint_id_a": str(ep_a.id),
                        "endpoint_id_b": str(ep_b.id),
                        "differences": diffs,
                    }
                )

        return VersionCompareResponse(
            added_endpoints=added,
            removed_endpoints=removed,
            modified_endpoints=modified,
            breaking_changes=breaking_changes,
            summary=(
                f"Added: {len(added)}, Removed: {len(removed)}, "
                f"Modified: {len(modified)}, Breaking: {len(breaking_changes)}"
            ),
        )
