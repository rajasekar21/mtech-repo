"""Semantic and hybrid search service using pgvector."""
from __future__ import annotations

import math
import uuid
from typing import Any, Optional

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.knowledge import DocumentChunk
from app.schemas.search import SearchResult

logger = get_logger(__name__)

_PGVECTOR_AVAILABLE = True
try:
    from pgvector.sqlalchemy import Vector  # noqa: F401
except ImportError:
    _PGVECTOR_AVAILABLE = False


class SearchService:
    """Vector and keyword search over document chunks."""

    # ---------------------------------------------------------------------- #
    # Semantic search
    # ---------------------------------------------------------------------- #

    async def semantic_search(
        self,
        db: AsyncSession,
        query_embedding: list[float],
        spec_id: Optional[uuid.UUID] = None,
        top_k: int = 10,
        chunk_type: Optional[str] = None,
    ) -> list[SearchResult]:
        """Perform cosine similarity search against stored embeddings.

        Args:
            db: Async session.
            query_embedding: Dense vector for the query.
            spec_id: Optional spec filter.
            top_k: Number of results to return.
            chunk_type: Optional filter on chunk_type column.

        Returns:
            Ranked list of SearchResult objects.
        """
        if not _PGVECTOR_AVAILABLE or not query_embedding:
            return await self._keyword_fallback(db, "", spec_id, top_k, chunk_type)

        try:
            filters = []
            if spec_id:
                filters.append(DocumentChunk.spec_id == spec_id)
            if chunk_type:
                filters.append(DocumentChunk.chunk_type == chunk_type)

            # Build the cosine distance expression using pgvector operator <=>
            # We cast the embedding list to a vector literal via raw SQL param
            embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

            stmt = text(
                f"""
                SELECT
                    id,
                    spec_id,
                    chunk_index,
                    content,
                    chunk_type,
                    metadata,
                    1 - (embedding <=> :embedding::vector) AS score
                FROM document_chunks
                WHERE embedding IS NOT NULL
                {"AND spec_id = :spec_id" if spec_id else ""}
                {"AND chunk_type = :chunk_type" if chunk_type else ""}
                ORDER BY embedding <=> :embedding::vector
                LIMIT :top_k
                """
            )

            params: dict[str, Any] = {
                "embedding": embedding_str,
                "top_k": top_k,
            }
            if spec_id:
                params["spec_id"] = str(spec_id)
            if chunk_type:
                params["chunk_type"] = chunk_type

            result = await db.execute(stmt, params)
            rows = result.fetchall()

            return [
                SearchResult(
                    chunk_id=row.id,
                    content=row.content,
                    score=float(row.score) if row.score else 0.0,
                    chunk_type=row.chunk_type,
                    metadata=row.metadata,
                    spec_id=row.spec_id,
                )
                for row in rows
            ]

        except Exception as exc:
            logger.warning(
                "Semantic search failed, falling back to keyword",
                error=str(exc),
            )
            return []

    # ---------------------------------------------------------------------- #
    # Keyword fallback / BM25-like search
    # ---------------------------------------------------------------------- #

    async def _keyword_fallback(
        self,
        db: AsyncSession,
        query: str,
        spec_id: Optional[uuid.UUID],
        top_k: int,
        chunk_type: Optional[str],
    ) -> list[SearchResult]:
        """PostgreSQL full-text search fallback when vectors are unavailable."""
        if not query:
            return []

        filters = []
        if spec_id:
            filters.append(DocumentChunk.spec_id == spec_id)
        if chunk_type:
            filters.append(DocumentChunk.chunk_type == chunk_type)

        pattern = f"%{query}%"
        filters.append(DocumentChunk.content.ilike(pattern))

        stmt = (
            select(DocumentChunk)
            .where(and_(*filters))
            .limit(top_k)
        )
        result = await db.execute(stmt)
        chunks = result.scalars().all()

        return [
            SearchResult(
                chunk_id=chunk.id,
                content=chunk.content,
                score=0.5,
                chunk_type=chunk.chunk_type,
                metadata=chunk.chunk_metadata,
                spec_id=chunk.spec_id,
            )
            for chunk in chunks
        ]

    # ---------------------------------------------------------------------- #
    # Hybrid search (RRF)
    # ---------------------------------------------------------------------- #

    async def hybrid_search(
        self,
        db: AsyncSession,
        query: str,
        query_embedding: list[float],
        spec_id: Optional[uuid.UUID] = None,
        top_k: int = 10,
        chunk_type: Optional[str] = None,
        rrf_k: int = 60,
    ) -> list[SearchResult]:
        """Combine semantic and keyword search using Reciprocal Rank Fusion.

        Args:
            db: Async session.
            query: Raw text query for keyword matching.
            query_embedding: Dense embedding for semantic search.
            spec_id: Optional spec filter.
            top_k: Number of final results.
            chunk_type: Optional chunk type filter.
            rrf_k: RRF constant (default 60).

        Returns:
            Reranked list of SearchResult objects.
        """
        # Run both searches in parallel candidates pool
        semantic_results = await self.semantic_search(
            db, query_embedding, spec_id, top_k * 2, chunk_type
        )
        keyword_results = await self._keyword_fallback(
            db, query, spec_id, top_k * 2, chunk_type
        )

        # Build RRF scores
        rrf_scores: dict[uuid.UUID, float] = {}
        result_map: dict[uuid.UUID, SearchResult] = {}

        for rank, result in enumerate(semantic_results, start=1):
            cid = result.chunk_id
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (rrf_k + rank)
            result_map[cid] = result

        for rank, result in enumerate(keyword_results, start=1):
            cid = result.chunk_id
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (rrf_k + rank)
            result_map[cid] = result

        # Sort by RRF score descending
        sorted_ids = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)

        reranked: list[SearchResult] = []
        for cid in sorted_ids[:top_k]:
            result = result_map[cid]
            # Replace score with normalised RRF score (0-1 range)
            max_rrf = 1.0 / (rrf_k + 1)
            reranked.append(
                SearchResult(
                    chunk_id=result.chunk_id,
                    content=result.content,
                    score=min(rrf_scores[cid] / max_rrf, 1.0),
                    chunk_type=result.chunk_type,
                    metadata=result.metadata,
                    spec_id=result.spec_id,
                    endpoint=result.endpoint,
                    flow=result.flow,
                    spec_name=result.spec_name,
                )
            )

        return reranked

    # ---------------------------------------------------------------------- #
    # RAG context builder
    # ---------------------------------------------------------------------- #

    async def get_context_for_chat(
        self,
        db: AsyncSession,
        query: str,
        query_embedding: list[float],
        spec_id: Optional[uuid.UUID] = None,
        top_k: int = 5,
    ) -> str:
        """Build a RAG context string from the top-k most relevant chunks.

        Args:
            db: Async session.
            query: User query text.
            query_embedding: Dense embedding of the query.
            spec_id: Optional spec filter.
            top_k: Number of context chunks to include.

        Returns:
            Formatted multi-chunk context string for the LLM prompt.
        """
        results = await self.hybrid_search(
            db,
            query=query,
            query_embedding=query_embedding,
            spec_id=spec_id,
            top_k=top_k,
        )

        if not results:
            return "No relevant context found in the knowledge base."

        parts: list[str] = []
        for i, result in enumerate(results, start=1):
            chunk_type_label = result.chunk_type.upper()
            parts.append(
                f"[{i}] [{chunk_type_label}] (relevance: {result.score:.2f})\n{result.content}"
            )

        return "\n\n---\n\n".join(parts)

    # ---------------------------------------------------------------------- #
    # Autocomplete suggestions
    # ---------------------------------------------------------------------- #

    async def get_suggestions(
        self,
        db: AsyncSession,
        prefix: str,
        spec_id: Optional[uuid.UUID] = None,
        limit: int = 10,
    ) -> list[str]:
        """Return autocomplete suggestions based on stored chunk content.

        Args:
            db: Async session.
            prefix: Search prefix string.
            spec_id: Optional spec filter.
            limit: Maximum suggestions to return.

        Returns:
            List of suggestion strings.
        """
        from app.models.api_spec import ApiEndpoint

        pattern = f"{prefix}%"
        filters = [ApiEndpoint.path.ilike(pattern)]
        if spec_id:
            filters.append(ApiEndpoint.spec_id == spec_id)

        stmt = (
            select(ApiEndpoint.path)
            .where(and_(*filters))
            .distinct()
            .limit(limit)
        )
        result = await db.execute(stmt)
        paths = [row[0] for row in result.fetchall()]

        # Also search names
        name_filters = [ApiEndpoint.name.ilike(f"%{prefix}%")]
        if spec_id:
            name_filters.append(ApiEndpoint.spec_id == spec_id)

        name_stmt = (
            select(ApiEndpoint.name)
            .where(and_(*name_filters))
            .distinct()
            .limit(limit)
        )
        name_result = await db.execute(name_stmt)
        names = [row[0] for row in name_result.fetchall() if row[0]]

        combined = list(dict.fromkeys(paths + names))[:limit]
        return combined
