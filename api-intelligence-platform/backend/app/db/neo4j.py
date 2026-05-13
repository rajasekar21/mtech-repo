"""Neo4j async driver wrapper with FastAPI dependency injection."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from neo4j.exceptions import ServiceUnavailable

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Driver singleton
# --------------------------------------------------------------------------- #
class Neo4jDriver:
    """Thin wrapper around the Neo4j async driver."""

    def __init__(self) -> None:
        self._driver: Optional[AsyncDriver] = None
        self._available: bool = False

    async def connect(self) -> None:
        """Initialise the async Neo4j driver."""
        self._available = False
        self._driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            max_connection_pool_size=50,
        )
        # Verify connectivity
        try:
            await self._driver.verify_connectivity()
            self._available = True
            logger.info("Neo4j driver connected", uri=settings.NEO4J_URI)
        except ServiceUnavailable as exc:
            logger.error("Neo4j not reachable — continuing without graph", error=str(exc))

    async def close(self) -> None:
        """Close the Neo4j driver and release all connections."""
        if self._driver:
            await self._driver.close()
            self._driver = None
            self._available = False
            logger.info("Neo4j driver closed")

    @property
    def is_available(self) -> bool:
        """Return whether connectivity verification succeeded."""
        return self._available

    @asynccontextmanager
    async def session(self, database: str = "neo4j"):
        """Async context manager that yields a Neo4j AsyncSession."""
        if self._driver is None or not self._available:
            raise RuntimeError("Neo4j driver is not initialised — call connect() first")
        async with self._driver.session(database=database) as session:
            yield session

    async def execute_query(
        self,
        query: str,
        params: Optional[dict[str, Any]] = None,
        database: str = "neo4j",
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query and return all records as plain dicts.

        Args:
            query: Cypher query string.
            params: Optional parameters dict.
            database: Target Neo4j database (default "neo4j").

        Returns:
            List of record dicts.
        """
        if self._driver is None or not self._available:
            raise RuntimeError("Neo4j driver not initialised")
        async with self._driver.session(database=database) as session:
            result = await session.run(query, params or {})
            records = await result.data()
            return records


# --------------------------------------------------------------------------- #
# Module-level singleton
# --------------------------------------------------------------------------- #
neo4j_driver = Neo4jDriver()


# --------------------------------------------------------------------------- #
# FastAPI dependency
# --------------------------------------------------------------------------- #
async def get_neo4j() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a Neo4j async session."""
    async with neo4j_driver.session() as session:
        yield session


# --------------------------------------------------------------------------- #
# Schema initialisation
# --------------------------------------------------------------------------- #
async def init_neo4j_schema() -> None:
    """Create Neo4j constraints and indexes for the graph data model.

    Nodes: API, Endpoint, Flow, PSP, Bank, NPCI, Switch, Merchant, Customer,
           AuthenticationMethod, Organization
    """
    constraints_and_indexes = [
        # Uniqueness constraints
        "CREATE CONSTRAINT api_spec_id IF NOT EXISTS FOR (n:ApiSpec) REQUIRE n.spec_id IS UNIQUE",
        "CREATE CONSTRAINT endpoint_id IF NOT EXISTS FOR (n:Endpoint) REQUIRE n.endpoint_id IS UNIQUE",
        "CREATE CONSTRAINT flow_id IF NOT EXISTS FOR (n:Flow) REQUIRE n.flow_id IS UNIQUE",
        "CREATE CONSTRAINT psp_id IF NOT EXISTS FOR (n:PSP) REQUIRE n.entity_id IS UNIQUE",
        "CREATE CONSTRAINT bank_id IF NOT EXISTS FOR (n:Bank) REQUIRE n.entity_id IS UNIQUE",
        "CREATE CONSTRAINT npci_id IF NOT EXISTS FOR (n:NPCI) REQUIRE n.entity_id IS UNIQUE",
        "CREATE CONSTRAINT switch_id IF NOT EXISTS FOR (n:Switch) REQUIRE n.entity_id IS UNIQUE",
        "CREATE CONSTRAINT merchant_id IF NOT EXISTS FOR (n:Merchant) REQUIRE n.entity_id IS UNIQUE",
        "CREATE CONSTRAINT customer_id IF NOT EXISTS FOR (n:Customer) REQUIRE n.entity_id IS UNIQUE",
        "CREATE CONSTRAINT auth_method_id IF NOT EXISTS FOR (n:AuthenticationMethod) REQUIRE n.auth_id IS UNIQUE",
        # Lookup indexes
        "CREATE INDEX endpoint_spec_idx IF NOT EXISTS FOR (n:Endpoint) ON (n.spec_id)",
        "CREATE INDEX flow_spec_idx IF NOT EXISTS FOR (n:Flow) ON (n.spec_id)",
        "CREATE INDEX endpoint_path_idx IF NOT EXISTS FOR (n:Endpoint) ON (n.path)",
        "CREATE INDEX endpoint_method_idx IF NOT EXISTS FOR (n:Endpoint) ON (n.method)",
    ]

    try:
        for statement in constraints_and_indexes:
            await neo4j_driver.execute_query(statement)
        logger.info("Neo4j schema initialised successfully")
    except Exception as exc:
        logger.warning("Neo4j schema init encountered issues", error=str(exc))
