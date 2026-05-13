"""Impact analysis service.

Combines Neo4j graph traversal with AI reasoning to assess the blast radius
of a proposed API change.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.api_spec import ApiEndpoint
from app.models.knowledge import Flow, ImpactReport
from app.schemas.impact import (
    BlastRadius,
    BlastRadiusEdge,
    BlastRadiusNode,
    ImpactResponse,
    ImpactedEndpoint,
    ImpactedFlow,
)
from app.services.ai_service import AIService
from app.services.graph_service import GraphService

logger = get_logger(__name__)

_RISK_LEVEL_SCORE = {"low": 10, "medium": 30, "high": 60, "critical": 90}

_CHANGE_TYPE_WEIGHT = {
    "breaking": 1.0,
    "deprecation": 0.7,
    "security": 0.9,
    "additive": 0.2,
    "patch": 0.1,
}


class ImpactService:
    """Service for running change impact analyses."""

    def __init__(self) -> None:
        self._graph_service = GraphService()

    async def analyze_impact(
        self,
        db: AsyncSession,
        neo4j_session: Any,
        ai_service: AIService,
        spec_id: uuid.UUID,
        change_desc: str,
        endpoint_id: Optional[uuid.UUID],
        change_type: str = "breaking",
    ) -> ImpactResponse:
        """Run a complete impact analysis for a proposed change.

        Steps:
            1. Graph traversal to find all downstream dependencies.
            2. Identify affected flows.
            3. AI semantic analysis of the change.
            4. Risk scoring.
            5. Blast radius calculation.
            6. Persist ImpactReport and return response.

        Args:
            db: Async SQLAlchemy session.
            neo4j_session: Neo4j async session.
            ai_service: Initialised AIService.
            spec_id: UUID of the target spec.
            change_desc: Human-readable description of the change.
            endpoint_id: UUID of the specific endpoint being changed (optional).
            change_type: Category of change (breaking|additive|deprecation|security).

        Returns:
            ImpactResponse with full analysis.
        """
        logger.info(
            "Impact analysis started",
            spec_id=str(spec_id),
            endpoint_id=str(endpoint_id) if endpoint_id else None,
            change_type=change_type,
        )

        impacted_endpoints: list[ImpactedEndpoint] = []
        impacted_flows: list[ImpactedFlow] = []
        blast_radius = BlastRadius()
        graph_nodes: list[dict[str, Any]] = []
        graph_edges: list[dict[str, Any]] = []

        # ------------------------------------------------------------------ #
        # Step 1: Graph traversal for downstream dependencies
        # ------------------------------------------------------------------ #
        if endpoint_id and neo4j_session:
            try:
                impact_graph = await self._graph_service.get_impact_graph(
                    neo4j_session, endpoint_id
                )
                graph_nodes = impact_graph.get("nodes", [])
                graph_edges = impact_graph.get("edges", [])

                # Resolve graph node IDs to ApiEndpoint records
                node_ids = [
                    uuid.UUID(n["id"])
                    for n in graph_nodes
                    if n.get("id") and n["id"] != str(endpoint_id)
                ]

                if node_ids:
                    stmt = select(ApiEndpoint).where(ApiEndpoint.id.in_(node_ids))
                    result = await db.execute(stmt)
                    downstream_endpoints = result.scalars().all()

                    for ep in downstream_endpoints:
                        # Find distance from graph
                        distance = next(
                            (
                                n.get("distance", 0)
                                for n in graph_nodes
                                if n.get("id") == str(ep.id)
                            ),
                            1,
                        )
                        impacted_endpoints.append(
                            ImpactedEndpoint(
                                id=ep.id,
                                path=ep.path,
                                method=ep.method,
                                name=ep.name,
                                risk_level=ep.risk_level,
                                impact_reason=f"Downstream dependency (depth {distance})",
                                distance=distance,
                            )
                        )

            except Exception as exc:
                logger.warning("Graph traversal failed", error=str(exc))

        # Fall back to DB-level dependency query if graph unavailable
        if not impacted_endpoints and endpoint_id:
            try:
                from app.models.api_spec import ApiDependency

                dep_stmt = select(ApiDependency).where(
                    ApiDependency.source_endpoint_id == endpoint_id
                )
                dep_result = await db.execute(dep_stmt)
                deps = dep_result.scalars().all()

                for dep in deps:
                    ep = await db.get(ApiEndpoint, dep.target_endpoint_id)
                    if ep:
                        impacted_endpoints.append(
                            ImpactedEndpoint(
                                id=ep.id,
                                path=ep.path,
                                method=ep.method,
                                name=ep.name,
                                risk_level=ep.risk_level,
                                impact_reason=f"Direct dependency ({dep.dependency_type})",
                                distance=1,
                            )
                        )
            except Exception as exc:
                logger.warning("DB dependency fallback failed", error=str(exc))

        # ------------------------------------------------------------------ #
        # Step 2: Identify affected flows
        # ------------------------------------------------------------------ #
        try:
            flow_stmt = select(Flow).where(Flow.spec_id == spec_id)
            flow_result = await db.execute(flow_stmt)
            all_flows = flow_result.scalars().all()

            # Heuristic: flows are affected if they reference the changed endpoint path
            changed_ep = None
            if endpoint_id:
                changed_ep = await db.get(ApiEndpoint, endpoint_id)

            for flow in all_flows:
                affected = False
                reason = ""

                if changed_ep and flow.steps:
                    steps_str = str(flow.steps).lower()
                    if changed_ep.path.lower() in steps_str:
                        affected = True
                        reason = f"Flow steps reference {changed_ep.path}"
                    elif (changed_ep.name or "").lower() in steps_str:
                        affected = True
                        reason = f"Flow steps reference endpoint name"

                if not affected and changed_ep:
                    # Check by flow type
                    sensitive_types = {"direct_pay", "collect_pay", "refund", "mandate"}
                    if flow.flow_type in sensitive_types and change_type in ("breaking", "security"):
                        affected = True
                        reason = f"Flow type '{flow.flow_type}' affected by {change_type} change"

                if affected:
                    impacted_flows.append(
                        ImpactedFlow(
                            id=flow.id,
                            name=flow.name,
                            flow_type=flow.flow_type,
                            impact_reason=reason,
                        )
                    )
        except Exception as exc:
            logger.warning("Flow impact detection failed", error=str(exc))

        # ------------------------------------------------------------------ #
        # Step 3: AI analysis
        # ------------------------------------------------------------------ #
        ai_analysis_text = ""
        ai_risk_factors: list[str] = []
        ai_recommendations: list[str] = []
        ai_security_implications: list[str] = []
        ai_estimated_score: float = 0.0

        try:
            context_parts = [f"Proposed change: {change_desc}\nChange type: {change_type}"]
            if changed_ep:
                context_parts.append(
                    f"Changed endpoint: {changed_ep.method} {changed_ep.path}\n"
                    f"Risk level: {changed_ep.risk_level}\n"
                    f"Auth: {changed_ep.auth_method or 'none'}"
                )
            if impacted_endpoints:
                ep_summary = "\n".join(
                    f"  - {ep.method} {ep.path} (risk: {ep.risk_level}, depth: {ep.distance})"
                    for ep in impacted_endpoints[:15]
                )
                context_parts.append(f"Directly impacted endpoints:\n{ep_summary}")
            if impacted_flows:
                flow_summary = "\n".join(f"  - {f.name} ({f.flow_type})" for f in impacted_flows[:10])
                context_parts.append(f"Affected flows:\n{flow_summary}")

            context = "\n\n".join(context_parts)
            ai_result = await ai_service.generate_impact_analysis(change_desc, context)

            ai_analysis_text = ai_result.get("analysis", "")
            ai_risk_factors = ai_result.get("risk_factors", [])
            ai_recommendations = ai_result.get("recommendations", [])
            ai_security_implications = ai_result.get("security_implications", [])
            ai_estimated_score = float(ai_result.get("estimated_risk_score", 0))

        except Exception as exc:
            logger.warning("AI impact analysis failed", error=str(exc))
            ai_analysis_text = f"AI analysis unavailable: {exc}"

        # ------------------------------------------------------------------ #
        # Step 4: Risk scoring
        # ------------------------------------------------------------------ #
        api_risk_levels = [ep.risk_level for ep in impacted_endpoints]
        risk_score = self.calculate_risk_score(
            impacted_count=len(impacted_endpoints) + len(impacted_flows),
            change_type=change_type,
            api_risk_levels=api_risk_levels,
            ai_estimated_score=ai_estimated_score,
        )

        risk_level = "low"
        if risk_score >= 75:
            risk_level = "critical"
        elif risk_score >= 50:
            risk_level = "high"
        elif risk_score >= 25:
            risk_level = "medium"

        # ------------------------------------------------------------------ #
        # Step 5: Blast radius
        # ------------------------------------------------------------------ #
        blast_radius = self.get_blast_radius(
            graph_nodes=graph_nodes,
            graph_edges=graph_edges,
            impacted_endpoints=impacted_endpoints,
            impacted_flows=impacted_flows,
        )

        # ------------------------------------------------------------------ #
        # Step 6: Persist report
        # ------------------------------------------------------------------ #
        report = ImpactReport(
            spec_id=spec_id,
            change_description=change_desc,
            change_type=change_type,
            endpoint_id=endpoint_id,
            impacted_endpoints=[
                {
                    "id": str(ep.id),
                    "path": ep.path,
                    "method": ep.method,
                    "risk_level": ep.risk_level,
                    "distance": ep.distance,
                }
                for ep in impacted_endpoints
            ],
            impacted_flows=[
                {"id": str(f.id), "name": f.name, "flow_type": f.flow_type}
                for f in impacted_flows
            ],
            risk_score=risk_score,
            blast_radius=blast_radius.model_dump(),
            ai_analysis=ai_analysis_text,
            security_implications=ai_security_implications,
        )
        db.add(report)
        await db.flush()
        await db.refresh(report)

        logger.info(
            "Impact analysis complete",
            spec_id=str(spec_id),
            risk_score=risk_score,
            impacted_endpoints=len(impacted_endpoints),
        )

        from datetime import datetime, timezone

        return ImpactResponse(
            report_id=report.id,
            spec_id=spec_id,
            change_description=change_desc,
            change_type=change_type,
            endpoint_id=endpoint_id,
            risk_score=risk_score,
            risk_level=risk_level,
            impacted_endpoints=impacted_endpoints,
            impacted_flows=impacted_flows,
            blast_radius=blast_radius,
            ai_analysis=ai_analysis_text,
            security_implications=ai_security_implications,
            recommendations=ai_recommendations,
            created_at=report.created_at,
        )

    # ---------------------------------------------------------------------- #
    # Scoring
    # ---------------------------------------------------------------------- #

    def calculate_risk_score(
        self,
        impacted_count: int,
        change_type: str,
        api_risk_levels: list[str],
        ai_estimated_score: float = 0.0,
    ) -> float:
        """Compute a composite risk score from 0.0 to 100.0.

        Formula:
            base = average risk level score of impacted endpoints
            breadth = log1p(impacted_count) / log1p(100) * 30
            change_weight = multiplier for change type
            ai_contribution = 20% weight from AI estimate
        """
        import math

        # Base: average risk of impacted endpoints
        if api_risk_levels:
            avg_level_score = sum(
                _RISK_LEVEL_SCORE.get(lvl, 10) for lvl in api_risk_levels
            ) / len(api_risk_levels)
        else:
            avg_level_score = 10.0

        # Breadth component (more impacted = higher score, capped)
        breadth = math.log1p(impacted_count) / math.log1p(100) * 30.0

        # Change type multiplier
        weight = _CHANGE_TYPE_WEIGHT.get(change_type, 0.5)

        # Weighted combination
        structural_score = (avg_level_score * 0.5 + breadth) * weight
        final_score = structural_score * 0.8 + ai_estimated_score * 0.2

        return round(min(max(final_score, 0.0), 100.0), 2)

    def get_blast_radius(
        self,
        graph_nodes: list[dict[str, Any]],
        graph_edges: list[dict[str, Any]],
        impacted_endpoints: list[ImpactedEndpoint],
        impacted_flows: list[ImpactedFlow],
    ) -> BlastRadius:
        """Build blast radius visualisation data.

        Args:
            graph_nodes: Raw Neo4j node dicts.
            graph_edges: Raw Neo4j edge dicts.
            impacted_endpoints: Resolved impacted endpoint schemas.
            impacted_flows: Resolved impacted flow schemas.

        Returns:
            BlastRadius with React-Flow-compatible nodes and edges.
        """
        nodes: list[BlastRadiusNode] = []
        edges: list[BlastRadiusEdge] = []
        seen_ids: set[str] = set()

        # Endpoint nodes
        for ep in impacted_endpoints:
            nid = str(ep.id)
            if nid not in seen_ids:
                nodes.append(
                    BlastRadiusNode(
                        id=nid,
                        label=f"{ep.method} {ep.path}",
                        type="endpoint",
                        risk_level=ep.risk_level,
                        distance=ep.distance,
                    )
                )
                seen_ids.add(nid)

        # Flow nodes
        for flow in impacted_flows:
            fid = str(flow.id)
            if fid not in seen_ids:
                nodes.append(
                    BlastRadiusNode(
                        id=fid,
                        label=flow.name,
                        type="flow",
                        distance=1,
                    )
                )
                seen_ids.add(fid)

        # Edges from graph
        for edge in graph_edges:
            src = str(edge.get("source", ""))
            tgt = str(edge.get("target", ""))
            if src in seen_ids and tgt in seen_ids:
                edges.append(
                    BlastRadiusEdge(
                        source=src,
                        target=tgt,
                        relationship=edge.get("relationship", "CALLS"),
                    )
                )

        return BlastRadius(
            nodes=nodes,
            edges=edges,
            total_affected=len(nodes),
        )
