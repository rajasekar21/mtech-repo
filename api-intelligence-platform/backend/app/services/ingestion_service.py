"""Ingestion pipeline orchestrator.

Processes uploaded API spec documents through:
  1. Parse -> 2. Chunk -> 3. Embed -> 4. Extract APIs -> 5. Extract Dependencies
  6. Extract Flows -> 7. Extract Entities -> 8. Security Findings
  9. Neo4j Graph -> 10. Mark ready
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.api_spec import ApiDependency, ApiEndpoint, ApiSpec
from app.models.knowledge import (
    ArchitectureEntity,
    DocumentChunk,
    Flow,
    SecurityFinding,
)
from app.services.ai_service import AIService
from app.services.document_service import DocumentService

logger = get_logger(__name__)


class IngestionService:
    """Orchestrates the full document ingestion pipeline."""

    def __init__(self) -> None:
        self._doc_service = DocumentService()

    async def ingest_document(
        self,
        db: AsyncSession,
        neo4j_session: Any,
        ai_service: AIService,
        spec_id: uuid.UUID,
        file_path: str,
        source_type: str,
    ) -> None:
        """Run the complete ingestion pipeline for an uploaded document.

        Steps:
            1. Parse the document into sections.
            2. Chunk sections into overlapping text chunks.
            3. Generate embeddings and persist DocumentChunk records.
            4. Extract API endpoints and persist ApiEndpoint records.
            5. Extract dependencies and persist ApiDependency records.
            6. Extract flows and persist Flow records.
            7. Extract architecture entities and persist ArchitectureEntity records.
            8. Extract security findings and persist SecurityFinding records.
            9. Build Neo4j graph nodes and relationships.
            10. Update spec status to "ready".

        Args:
            db: Async SQLAlchemy session.
            neo4j_session: Neo4j async session (or None if unavailable).
            ai_service: Initialised AIService instance.
            spec_id: UUID of the ApiSpec being processed.
            file_path: Absolute path to the uploaded file.
            source_type: One of pdf|openapi|xml|swagger|asyncapi.
        """
        logger.info("Ingestion started", spec_id=str(spec_id), source_type=source_type)

        # Update status to processing
        spec = await db.get(ApiSpec, spec_id)
        if not spec:
            logger.error("ApiSpec not found", spec_id=str(spec_id))
            return

        spec.status = "processing"
        await db.flush()

        full_text = ""
        parsed_openapi: Optional[dict[str, Any]] = None

        # ------------------------------------------------------------------ #
        # Step 1: Parse
        # ------------------------------------------------------------------ #
        sections: list[dict[str, Any]] = []
        try:
            file_content = Path(file_path).read_bytes()

            if source_type == "pdf":
                sections = await self._doc_service.parse_pdf(file_path)
                full_text = "\n\n".join(s["content"] for s in sections)

            elif source_type in ("openapi", "swagger", "asyncapi"):
                parsed_openapi = await self._doc_service.parse_openapi(file_content)
                # Convert OpenAPI info + paths into sections for chunking
                import json
                full_text = json.dumps(parsed_openapi.get("raw", parsed_openapi), indent=2)
                sections = [{"content": full_text, "type": "openapi", "page": 1, "metadata": {}}]
                # Update spec with parsed content
                spec.parsed_content = parsed_openapi
                spec.version = parsed_openapi.get("info", {}).get("version") or spec.version
                spec.description = (
                    parsed_openapi.get("info", {}).get("description") or spec.description
                )

            elif source_type == "xml":
                xml_parsed = await self._doc_service.parse_xml(file_content)
                import json
                full_text = json.dumps(xml_parsed, indent=2)
                sections = [{"content": full_text, "type": "xml", "page": 1, "metadata": {}}]

            else:
                # Plain text fallback
                full_text = file_content.decode("utf-8", errors="replace")
                sections = [{"content": full_text, "type": "text", "page": 1, "metadata": {}}]

            await db.flush()
            logger.info("Step 1 complete: document parsed", spec_id=str(spec_id), sections=len(sections))

        except Exception as exc:
            logger.error("Step 1 failed: parse", spec_id=str(spec_id), error=str(exc))
            await self._mark_failed(db, spec, str(exc))
            return

        # ------------------------------------------------------------------ #
        # Step 2: Chunk
        # ------------------------------------------------------------------ #
        try:
            if parsed_openapi:
                chunks = await self._doc_service.chunk_openapi_spec(parsed_openapi)
            else:
                chunks = await self._doc_service.chunk_document(sections)
            logger.info("Step 2 complete: chunked", spec_id=str(spec_id), chunks=len(chunks))
        except Exception as exc:
            logger.error("Step 2 failed: chunk", spec_id=str(spec_id), error=str(exc))
            chunks = [{"chunk_index": 0, "content": full_text[:4000], "chunk_type": "general", "metadata": {}}]

        # ------------------------------------------------------------------ #
        # Step 3: Embed + persist DocumentChunks
        # ------------------------------------------------------------------ #
        chunk_records: list[DocumentChunk] = []
        try:
            texts = [c["content"] for c in chunks]
            embeddings = await ai_service.embed_texts(texts)

            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                db_chunk = DocumentChunk(
                    spec_id=spec_id,
                    chunk_index=chunk.get("chunk_index", i),
                    content=chunk["content"],
                    chunk_type=chunk.get("chunk_type", "general"),
                    chunk_metadata=chunk.get("metadata"),
                    embedding=embedding if embedding else None,
                )
                db.add(db_chunk)
                chunk_records.append(db_chunk)

            await db.flush()
            logger.info("Step 3 complete: embeddings stored", spec_id=str(spec_id), chunks=len(chunk_records))
        except Exception as exc:
            logger.error("Step 3 failed: embeddings", spec_id=str(spec_id), error=str(exc))

        # ------------------------------------------------------------------ #
        # Step 4: Extract API endpoints
        # ------------------------------------------------------------------ #
        endpoint_records: list[ApiEndpoint] = []
        try:
            if parsed_openapi:
                extracted_endpoints = self._extract_endpoints_from_openapi(parsed_openapi)
            else:
                extracted_endpoints = await ai_service.extract_apis_from_text(full_text)

            for ep_data in extracted_endpoints:
                endpoint = ApiEndpoint(
                    spec_id=spec_id,
                    name=ep_data.get("summary") or ep_data.get("name") or ep_data.get("path"),
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
            logger.info("Step 4 complete: endpoints", spec_id=str(spec_id), count=len(endpoint_records))
        except Exception as exc:
            logger.error("Step 4 failed: endpoints", spec_id=str(spec_id), error=str(exc))

        # ------------------------------------------------------------------ #
        # Step 5: Extract dependencies
        # ------------------------------------------------------------------ #
        try:
            if len(endpoint_records) > 1 and parsed_openapi:
                deps = self._infer_dependencies_from_openapi(parsed_openapi, endpoint_records)
                for dep_data in deps:
                    dep = ApiDependency(**dep_data)
                    db.add(dep)
                await db.flush()
                logger.info("Step 5 complete: dependencies", spec_id=str(spec_id), count=len(deps))
        except Exception as exc:
            logger.error("Step 5 failed: dependencies", spec_id=str(spec_id), error=str(exc))

        # ------------------------------------------------------------------ #
        # Step 6: Extract flows
        # ------------------------------------------------------------------ #
        try:
            extracted_flows = await ai_service.extract_flows_from_text(full_text[:8000])
            for flow_data in extracted_flows:
                flow = Flow(
                    spec_id=spec_id,
                    name=flow_data.get("name", "Unnamed Flow"),
                    flow_type=flow_data.get("type"),
                    description=flow_data.get("description"),
                    steps=flow_data.get("steps", []),
                    mermaid_diagram=flow_data.get("mermaid_diagram"),
                )
                db.add(flow)

            await db.flush()
            logger.info("Step 6 complete: flows", spec_id=str(spec_id), count=len(extracted_flows))
        except Exception as exc:
            logger.error("Step 6 failed: flows", spec_id=str(spec_id), error=str(exc))

        # ------------------------------------------------------------------ #
        # Step 7: Extract architecture entities
        # ------------------------------------------------------------------ #
        try:
            extracted_entities = await ai_service.extract_entities_from_text(full_text[:8000])
            for ent_data in extracted_entities:
                entity = ArchitectureEntity(
                    spec_id=spec_id,
                    name=ent_data.get("name", "Unknown"),
                    entity_type=ent_data.get("entity_type", "other"),
                    properties=ent_data.get("properties"),
                )
                db.add(entity)

            await db.flush()
            logger.info("Step 7 complete: entities", spec_id=str(spec_id), count=len(extracted_entities))
        except Exception as exc:
            logger.error("Step 7 failed: entities", spec_id=str(spec_id), error=str(exc))

        # ------------------------------------------------------------------ #
        # Step 8: Security findings
        # ------------------------------------------------------------------ #
        try:
            security_findings = await ai_service.extract_security_rules(full_text[:8000])
            for finding_data in security_findings:
                # Try to find a matching endpoint
                endpoint_id = None
                affected = finding_data.get("affected_endpoints", [])
                if affected and endpoint_records:
                    path = affected[0]
                    for ep in endpoint_records:
                        if ep.path == path:
                            endpoint_id = ep.id
                            break

                finding = SecurityFinding(
                    spec_id=spec_id,
                    endpoint_id=endpoint_id,
                    severity=finding_data.get("severity", "medium"),
                    category=finding_data.get("category"),
                    title=finding_data.get("title", "Security Finding"),
                    description=finding_data.get("description"),
                    recommendation=finding_data.get("recommendation"),
                )
                db.add(finding)

            await db.flush()
            logger.info("Step 8 complete: security findings", spec_id=str(spec_id), count=len(security_findings))
        except Exception as exc:
            logger.error("Step 8 failed: security", spec_id=str(spec_id), error=str(exc))

        # ------------------------------------------------------------------ #
        # Step 9: Build Neo4j graph
        # ------------------------------------------------------------------ #
        try:
            if neo4j_session is not None:
                from app.services.graph_service import GraphService

                # Fetch flows and entities persisted in this session
                flow_result = await db.execute(
                    select(Flow).where(Flow.spec_id == spec_id)
                )
                flows = list(flow_result.scalars().all())

                entity_result = await db.execute(
                    select(ArchitectureEntity).where(ArchitectureEntity.spec_id == spec_id)
                )
                entities = list(entity_result.scalars().all())

                dep_result = await db.execute(
                    select(ApiDependency).where(
                        ApiDependency.source_endpoint_id.in_(
                            [ep.id for ep in endpoint_records]
                        )
                    )
                )
                dependencies = list(dep_result.scalars().all())

                graph_service = GraphService()
                await graph_service.build_graph_from_spec(
                    neo4j_session,
                    spec_id=spec_id,
                    endpoints=endpoint_records,
                    dependencies=dependencies,
                    flows=flows,
                    entities=entities,
                )
                logger.info("Step 9 complete: Neo4j graph built", spec_id=str(spec_id))
        except Exception as exc:
            logger.error("Step 9 failed: Neo4j graph", spec_id=str(spec_id), error=str(exc))

        # ------------------------------------------------------------------ #
        # Step 10: Mark ready
        # ------------------------------------------------------------------ #
        try:
            spec.status = "ready"
            await db.flush()
            logger.info("Ingestion complete", spec_id=str(spec_id))
        except Exception as exc:
            logger.error("Step 10 failed: mark ready", spec_id=str(spec_id), error=str(exc))
            await self._mark_failed(db, spec, str(exc))

    # ---------------------------------------------------------------------- #
    # Helpers
    # ---------------------------------------------------------------------- #

    async def _mark_failed(
        self,
        db: AsyncSession,
        spec: ApiSpec,
        error_message: str,
    ) -> None:
        """Mark a spec as failed with an error message."""
        spec.status = "failed"
        spec.error_message = error_message[:2000]
        await db.flush()

    def _extract_endpoints_from_openapi(
        self,
        parsed: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Convert parsed OpenAPI paths to a list of endpoint dicts."""
        endpoints: list[dict[str, Any]] = []
        paths = parsed.get("paths", {})
        raw = parsed.get("raw", {})

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method, operation in path_item.items():
                if method.lower() in ("parameters", "summary", "description", "servers"):
                    continue
                if method.startswith("x-"):
                    continue
                if not isinstance(operation, dict):
                    continue

                # Extract auth method from security
                auth_method = None
                security = operation.get("security") or raw.get("security", [])
                if security and isinstance(security, list) and security:
                    first_sec = security[0]
                    if isinstance(first_sec, dict) and first_sec:
                        auth_method = list(first_sec.keys())[0]

                # Request schema
                req_schema = None
                req_body = operation.get("requestBody", {})
                if req_body and isinstance(req_body, dict):
                    content = req_body.get("content", {})
                    for ct, ct_data in content.items():
                        if isinstance(ct_data, dict):
                            req_schema = ct_data.get("schema")
                            break

                # Response schema
                resp_schema = None
                responses = operation.get("responses", {})
                for code in ("200", "201", "202"):
                    if code in responses:
                        resp = responses[code]
                        if isinstance(resp, dict):
                            content = resp.get("content", {})
                            for ct, ct_data in content.items():
                                if isinstance(ct_data, dict):
                                    resp_schema = ct_data.get("schema")
                                    break
                        break

                # Risk level heuristic
                risk = "low"
                path_lower = path.lower()
                method_upper = method.upper()
                if any(kw in path_lower for kw in ["payment", "transfer", "refund", "debit", "credit", "mandate"]):
                    risk = "high"
                elif method_upper in ("DELETE", "PUT") or "admin" in path_lower:
                    risk = "medium"

                endpoints.append(
                    {
                        "path": path,
                        "method": method.upper(),
                        "summary": operation.get("summary"),
                        "name": operation.get("operationId") or f"{method.upper()} {path}",
                        "description": operation.get("description"),
                        "parameters": operation.get("parameters"),
                        "request_schema": req_schema,
                        "response_schema": resp_schema,
                        "auth_method": auth_method,
                        "tags": operation.get("tags", []),
                        "risk_level": risk,
                        "is_deprecated": operation.get("deprecated", False),
                    }
                )

        return endpoints

    def _infer_dependencies_from_openapi(
        self,
        parsed: dict[str, Any],
        endpoints: list[ApiEndpoint],
    ) -> list[dict[str, Any]]:
        """Infer endpoint dependencies from shared schemas and path prefixes."""
        dependencies: list[dict[str, Any]] = []
        path_to_endpoint: dict[str, dict[str, ApiEndpoint]] = {}

        for ep in endpoints:
            path_to_endpoint.setdefault(ep.path, {})[ep.method] = ep

        # Auth dependency: all non-auth endpoints depend on auth endpoint
        auth_endpoints = [ep for ep in endpoints if any(
            kw in (ep.path or "").lower()
            for kw in ["/auth", "/login", "/token", "/oauth"]
        )]
        non_auth_endpoints = [ep for ep in endpoints if ep not in auth_endpoints]

        for auth_ep in auth_endpoints:
            for ep in non_auth_endpoints[:20]:  # Limit to prevent explosion
                dependencies.append(
                    {
                        "source_endpoint_id": ep.id,
                        "target_endpoint_id": auth_ep.id,
                        "dependency_type": "authenticates_with",
                        "strength": 0.8,
                    }
                )

        return dependencies
