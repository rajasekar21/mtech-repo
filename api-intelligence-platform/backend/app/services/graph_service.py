"""Neo4j graph service for building and querying the API dependency graph."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from app.core.logging import get_logger
from app.models.api_spec import ApiDependency, ApiEndpoint
from app.models.knowledge import ArchitectureEntity, Flow

logger = get_logger(__name__)


class GraphService:
    """Build and query the Neo4j knowledge graph for API specs."""

    # ---------------------------------------------------------------------- #
    # Graph construction
    # ---------------------------------------------------------------------- #

    async def build_graph_from_spec(
        self,
        session: Any,
        spec_id: uuid.UUID,
        endpoints: list[ApiEndpoint],
        dependencies: list[ApiDependency],
        flows: list[Flow],
        entities: list[ArchitectureEntity],
    ) -> None:
        """Create or merge all nodes and relationships for a spec into Neo4j.

        Args:
            session: Neo4j async session.
            spec_id: UUID of the parent ApiSpec.
            endpoints: List of ApiEndpoint ORM instances.
            dependencies: List of ApiDependency ORM instances.
            flows: List of Flow ORM instances.
            entities: List of ArchitectureEntity ORM instances.
        """
        spec_id_str = str(spec_id)

        # -- ApiSpec node --
        await session.run(
            """
            MERGE (s:ApiSpec {spec_id: $spec_id})
            SET s.updated_at = datetime()
            """,
            {"spec_id": spec_id_str},
        )

        # -- Endpoint nodes --
        for ep in endpoints:
            await session.run(
                """
                MERGE (e:Endpoint {endpoint_id: $endpoint_id})
                SET e.spec_id = $spec_id,
                    e.path = $path,
                    e.method = $method,
                    e.name = $name,
                    e.risk_level = $risk_level,
                    e.auth_method = $auth_method,
                    e.is_deprecated = $is_deprecated,
                    e.tags = $tags
                WITH e
                MATCH (s:ApiSpec {spec_id: $spec_id})
                MERGE (s)-[:HAS_ENDPOINT]->(e)
                """,
                {
                    "endpoint_id": str(ep.id),
                    "spec_id": spec_id_str,
                    "path": ep.path,
                    "method": ep.method,
                    "name": ep.name or f"{ep.method} {ep.path}",
                    "risk_level": ep.risk_level,
                    "auth_method": ep.auth_method or "",
                    "is_deprecated": ep.is_deprecated,
                    "tags": ep.tags or [],
                },
            )

        # -- Dependency relationships --
        for dep in dependencies:
            rel_type = self._dep_type_to_cypher(dep.dependency_type)
            await session.run(
                f"""
                MATCH (src:Endpoint {{endpoint_id: $src_id}})
                MATCH (tgt:Endpoint {{endpoint_id: $tgt_id}})
                MERGE (src)-[r:{rel_type}]->(tgt)
                SET r.strength = $strength,
                    r.dependency_type = $dep_type
                """,
                {
                    "src_id": str(dep.source_endpoint_id),
                    "tgt_id": str(dep.target_endpoint_id),
                    "strength": dep.strength,
                    "dep_type": dep.dependency_type,
                },
            )

        # -- Flow nodes --
        for flow in flows:
            await session.run(
                """
                MERGE (f:Flow {flow_id: $flow_id})
                SET f.spec_id = $spec_id,
                    f.name = $name,
                    f.flow_type = $flow_type,
                    f.description = $description
                WITH f
                MATCH (s:ApiSpec {spec_id: $spec_id})
                MERGE (s)-[:HAS_FLOW]->(f)
                """,
                {
                    "flow_id": str(flow.id),
                    "spec_id": spec_id_str,
                    "name": flow.name,
                    "flow_type": flow.flow_type or "",
                    "description": flow.description or "",
                },
            )

        # -- Architecture entity nodes --
        entity_type_map = {
            "psp": "PSP",
            "bank": "Bank",
            "npci": "NPCI",
            "switch": "Switch",
            "merchant": "Merchant",
            "customer": "Customer",
            "gateway": "Gateway",
            "regulator": "Regulator",
        }

        for entity in entities:
            node_label = entity_type_map.get(entity.entity_type.lower(), "Entity")
            await session.run(
                f"""
                MERGE (en:{node_label} {{entity_id: $entity_id}})
                SET en.spec_id = $spec_id,
                    en.name = $name,
                    en.entity_type = $entity_type
                WITH en
                MATCH (s:ApiSpec {{spec_id: $spec_id}})
                MERGE (s)-[:HAS_ENTITY]->(en)
                """,
                {
                    "entity_id": str(entity.id),
                    "spec_id": spec_id_str,
                    "name": entity.name,
                    "entity_type": entity.entity_type,
                },
            )

        logger.info(
            "Neo4j graph built",
            spec_id=spec_id_str,
            endpoints=len(endpoints),
            flows=len(flows),
            entities=len(entities),
        )

    # ---------------------------------------------------------------------- #
    # Graph queries
    # ---------------------------------------------------------------------- #

    async def get_dependency_graph(
        self,
        session: Any,
        spec_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Return full dependency graph data suitable for React Flow.

        Args:
            session: Neo4j async session.
            spec_id: UUID of the target spec.

        Returns:
            Dict with 'nodes' and 'edges' lists.
        """
        result = await session.run(
            """
            MATCH (s:ApiSpec {spec_id: $spec_id})-[:HAS_ENDPOINT]->(e:Endpoint)
            OPTIONAL MATCH (e)-[r]->(t:Endpoint)
            RETURN
                e.endpoint_id AS source_id,
                e.path AS source_path,
                e.method AS source_method,
                e.name AS source_name,
                e.risk_level AS source_risk,
                t.endpoint_id AS target_id,
                t.path AS target_path,
                t.method AS target_method,
                type(r) AS rel_type,
                r.strength AS strength
            """,
            {"spec_id": str(spec_id)},
        )
        records = await result.data()

        nodes: dict[str, dict] = {}
        edges: list[dict] = []

        for record in records:
            src_id = record.get("source_id")
            if src_id and src_id not in nodes:
                nodes[src_id] = {
                    "id": src_id,
                    "data": {
                        "label": f"{record['source_method']} {record['source_path']}",
                        "name": record.get("source_name", ""),
                        "risk_level": record.get("source_risk", "low"),
                        "type": "endpoint",
                    },
                    "type": "apiNode",
                }

            tgt_id = record.get("target_id")
            if tgt_id and tgt_id not in nodes:
                nodes[tgt_id] = {
                    "id": tgt_id,
                    "data": {
                        "label": f"{record['target_method']} {record['target_path']}",
                        "type": "endpoint",
                    },
                    "type": "apiNode",
                }

            if src_id and tgt_id:
                edges.append(
                    {
                        "id": f"{src_id}-{tgt_id}",
                        "source": src_id,
                        "target": tgt_id,
                        "label": record.get("rel_type", "CALLS"),
                        "data": {"strength": record.get("strength", 1.0)},
                    }
                )

        # Also include flows
        flow_result = await session.run(
            """
            MATCH (s:ApiSpec {spec_id: $spec_id})-[:HAS_FLOW]->(f:Flow)
            RETURN f.flow_id AS id, f.name AS name, f.flow_type AS flow_type
            """,
            {"spec_id": str(spec_id)},
        )
        for rec in await flow_result.data():
            fid = rec["id"]
            nodes[fid] = {
                "id": fid,
                "data": {
                    "label": rec.get("name", "Flow"),
                    "flow_type": rec.get("flow_type", ""),
                    "type": "flow",
                },
                "type": "flowNode",
            }

        return {"nodes": list(nodes.values()), "edges": edges}

    async def get_api_neighbors(
        self,
        session: Any,
        endpoint_id: uuid.UUID,
        depth: int = 2,
    ) -> dict[str, Any]:
        """Get a subgraph of neighbouring endpoints up to *depth* hops.

        Args:
            session: Neo4j async session.
            endpoint_id: Starting endpoint UUID.
            depth: Maximum traversal depth.

        Returns:
            Dict with 'nodes' and 'edges'.
        """
        result = await session.run(
            """
            MATCH path = (src:Endpoint {endpoint_id: $endpoint_id})-[*1..$depth]-(neighbor:Endpoint)
            UNWIND nodes(path) AS n
            UNWIND relationships(path) AS r
            RETURN
                n.endpoint_id AS node_id,
                n.path AS node_path,
                n.method AS node_method,
                n.risk_level AS node_risk,
                startNode(r).endpoint_id AS rel_source,
                endNode(r).endpoint_id AS rel_target,
                type(r) AS rel_type
            """,
            {"endpoint_id": str(endpoint_id), "depth": depth},
        )
        records = await result.data()

        nodes: dict[str, dict] = {}
        edges: list[dict] = []

        for rec in records:
            nid = rec.get("node_id")
            if nid and nid not in nodes:
                nodes[nid] = {
                    "id": nid,
                    "data": {
                        "label": f"{rec.get('node_method', '')} {rec.get('node_path', '')}",
                        "risk_level": rec.get("node_risk", "low"),
                    },
                }
            src = rec.get("rel_source")
            tgt = rec.get("rel_target")
            if src and tgt:
                edge_id = f"{src}-{tgt}"
                if not any(e["id"] == edge_id for e in edges):
                    edges.append(
                        {
                            "id": edge_id,
                            "source": src,
                            "target": tgt,
                            "label": rec.get("rel_type", ""),
                        }
                    )

        return {"nodes": list(nodes.values()), "edges": edges}

    async def find_shortest_path(
        self,
        session: Any,
        source_id: uuid.UUID,
        target_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Find the shortest path between two endpoints using Neo4j shortestPath.

        Args:
            session: Neo4j async session.
            source_id: Starting endpoint UUID.
            target_id: Destination endpoint UUID.

        Returns:
            Ordered list of node dicts along the path.
        """
        result = await session.run(
            """
            MATCH (src:Endpoint {endpoint_id: $source_id}),
                  (tgt:Endpoint {endpoint_id: $target_id})
            MATCH path = shortestPath((src)-[*..10]-(tgt))
            RETURN [node IN nodes(path) | {
                id: node.endpoint_id,
                path: node.path,
                method: node.method,
                risk_level: node.risk_level
            }] AS path_nodes
            """,
            {
                "source_id": str(source_id),
                "target_id": str(target_id),
            },
        )
        records = await result.data()
        if not records:
            return []
        return records[0].get("path_nodes", [])

    async def get_impact_graph(
        self,
        session: Any,
        endpoint_id: uuid.UUID,
        max_depth: int = 5,
    ) -> dict[str, Any]:
        """Return all downstream nodes reachable from *endpoint_id*.

        Used by the impact analysis service to determine blast radius.

        Args:
            session: Neo4j async session.
            endpoint_id: Starting endpoint UUID.
            max_depth: Maximum traversal depth.

        Returns:
            Dict with 'nodes' (list of node dicts) and 'edges' lists.
        """
        result = await session.run(
            """
            MATCH path = (src:Endpoint {endpoint_id: $endpoint_id})-[*1..$max_depth]->(downstream)
            UNWIND nodes(path) AS n
            UNWIND relationships(path) AS r
            RETURN DISTINCT
                n.endpoint_id AS node_id,
                n.path AS node_path,
                n.method AS node_method,
                n.risk_level AS node_risk,
                labels(n) AS node_labels,
                startNode(r).endpoint_id AS rel_source,
                endNode(r).endpoint_id AS rel_target,
                type(r) AS rel_type,
                length(path) AS distance
            ORDER BY distance
            """,
            {"endpoint_id": str(endpoint_id), "max_depth": max_depth},
        )
        records = await result.data()

        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        distances: dict[str, int] = {}

        for rec in records:
            nid = rec.get("node_id")
            if nid and nid not in nodes:
                nodes[nid] = {
                    "id": nid,
                    "path": rec.get("node_path", ""),
                    "method": rec.get("node_method", ""),
                    "risk_level": rec.get("node_risk", "low"),
                    "labels": rec.get("node_labels", []),
                    "distance": rec.get("distance", 0),
                }
                distances[nid] = rec.get("distance", 0)

            src = rec.get("rel_source")
            tgt = rec.get("rel_target")
            if src and tgt:
                edge_id = f"{src}-{tgt}"
                if not any(e["id"] == edge_id for e in edges):
                    edges.append(
                        {
                            "id": edge_id,
                            "source": src,
                            "target": tgt,
                            "relationship": rec.get("rel_type", "CALLS"),
                        }
                    )

        return {
            "nodes": list(nodes.values()),
            "edges": edges,
            "total_affected": len(nodes),
        }

    async def get_graph_stats(
        self,
        session: Any,
        spec_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Return statistics about the graph for a given spec.

        Args:
            session: Neo4j async session.
            spec_id: UUID of the target spec.

        Returns:
            Dict with counts and structural metrics.
        """
        result = await session.run(
            """
            MATCH (s:ApiSpec {spec_id: $spec_id})
            OPTIONAL MATCH (s)-[:HAS_ENDPOINT]->(e:Endpoint)
            OPTIONAL MATCH (s)-[:HAS_FLOW]->(f:Flow)
            OPTIONAL MATCH (s)-[:HAS_ENTITY]->(en)
            OPTIONAL MATCH (e)-[r]->(t:Endpoint)
            RETURN
                count(DISTINCT e) AS endpoint_count,
                count(DISTINCT f) AS flow_count,
                count(DISTINCT en) AS entity_count,
                count(DISTINCT r) AS relationship_count
            """,
            {"spec_id": str(spec_id)},
        )
        records = await result.data()
        if not records:
            return {}

        rec = records[0]

        # Centrality: endpoints with most outgoing relationships
        centrality_result = await session.run(
            """
            MATCH (s:ApiSpec {spec_id: $spec_id})-[:HAS_ENDPOINT]->(e:Endpoint)-[r]->(t:Endpoint)
            RETURN e.endpoint_id AS id, e.path AS path, e.method AS method,
                   count(r) AS out_degree
            ORDER BY out_degree DESC
            LIMIT 5
            """,
            {"spec_id": str(spec_id)},
        )
        top_nodes = await centrality_result.data()

        return {
            "endpoint_count": rec.get("endpoint_count", 0),
            "flow_count": rec.get("flow_count", 0),
            "entity_count": rec.get("entity_count", 0),
            "relationship_count": rec.get("relationship_count", 0),
            "top_connected_endpoints": top_nodes,
        }

    # ---------------------------------------------------------------------- #
    # Helpers
    # ---------------------------------------------------------------------- #

    @staticmethod
    def _dep_type_to_cypher(dep_type: str) -> str:
        """Convert a dependency type string to a valid Cypher relationship type."""
        mapping = {
            "calls": "CALLS",
            "depends_on": "DEPENDS_ON",
            "authenticates_with": "AUTHENTICATES_WITH",
        }
        return mapping.get(dep_type.lower(), "RELATES_TO")
