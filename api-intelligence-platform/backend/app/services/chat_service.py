"""RAG-powered chat service.

Combines semantic search, graph context, and conversation history to answer
user questions about API specs.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.knowledge import AiConversation
from app.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatSource,
    ConversationListItem,
    ConversationResponse,
)
from app.services.ai_service import AIService
from app.services.search_service import SearchService

logger = get_logger(__name__)


class ChatService:
    """RAG chat service with persistent conversation history."""

    async def chat(
        self,
        db: AsyncSession,
        neo4j_session: Any,
        ai_service: AIService,
        search_service: SearchService,
        user_id: uuid.UUID,
        org_id: Optional[uuid.UUID],
        request: ChatRequest,
    ) -> ChatResponse:
        """Process a chat message and return an AI response with sources.

        Steps:
            1. Load or create conversation.
            2. Embed the user message.
            3. Hybrid search for relevant context.
            4. Optionally enrich with graph context.
            5. Build RAG prompt and call AI.
            6. Save updated conversation.
            7. Return response with citations.

        Args:
            db: Async SQLAlchemy session.
            neo4j_session: Neo4j session (may be None).
            ai_service: Initialised AIService.
            search_service: Initialised SearchService.
            user_id: UUID of the requesting user.
            org_id: UUID of the user's organisation.
            request: Validated ChatRequest payload.

        Returns:
            ChatResponse with message, sources, and conversation_id.
        """
        # ------------------------------------------------------------------ #
        # Step 1: Load or create conversation
        # ------------------------------------------------------------------ #
        conversation = await self._get_or_create_conversation(
            db, user_id, org_id, request.conversation_id, request.spec_id
        )
        messages: list[dict[str, Any]] = conversation.messages or []

        # ------------------------------------------------------------------ #
        # Step 2: Embed user message
        # ------------------------------------------------------------------ #
        query_embedding: list[float] = []
        try:
            embeddings = await ai_service.embed_texts([request.message])
            if embeddings:
                query_embedding = embeddings[0]
        except Exception as exc:
            logger.warning("Embedding failed, proceeding without vector search", error=str(exc))

        # ------------------------------------------------------------------ #
        # Step 3: Retrieve relevant context chunks
        # ------------------------------------------------------------------ #
        context_str = ""
        sources: list[ChatSource] = []

        try:
            context_str = await search_service.get_context_for_chat(
                db=db,
                query=request.message,
                query_embedding=query_embedding,
                spec_id=request.spec_id,
                top_k=request.top_k,
            )

            # Build source citations from hybrid search results
            search_results = await search_service.hybrid_search(
                db=db,
                query=request.message,
                query_embedding=query_embedding,
                spec_id=request.spec_id,
                top_k=request.top_k,
            )

            for result in search_results:
                sources.append(
                    ChatSource(
                        chunk_id=result.chunk_id,
                        content=result.content[:500],
                        score=result.score,
                        chunk_type=result.chunk_type,
                        spec_name=result.spec_name,
                        metadata=result.metadata,
                    )
                )

        except Exception as exc:
            logger.warning("Context retrieval failed", error=str(exc))
            context_str = "Context retrieval unavailable."

        # ------------------------------------------------------------------ #
        # Step 4: Graph context enrichment
        # ------------------------------------------------------------------ #
        if neo4j_session and request.spec_id:
            try:
                graph_context = await self._get_graph_context(
                    neo4j_session, request.message, request.spec_id
                )
                if graph_context:
                    context_str += f"\n\n--- Graph Context ---\n{graph_context}"
            except Exception as exc:
                logger.debug("Graph context enrichment skipped", error=str(exc))

        # ------------------------------------------------------------------ #
        # Step 5: Build RAG prompt and call AI
        # ------------------------------------------------------------------ #
        # Reconstruct conversation history for LLM
        history_for_llm = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages[-10:]  # last 10 messages for context window
            if msg.get("role") in ("user", "assistant")
        ]

        try:
            ai_response = await ai_service.answer_with_context(
                question=request.message,
                context=context_str,
                conversation_history=history_for_llm,
            )
        except Exception as exc:
            logger.error("AI chat completion failed", error=str(exc))
            ai_response = (
                "I apologise, I was unable to generate a response. "
                "Please try again or rephrase your question."
            )

        # ------------------------------------------------------------------ #
        # Step 6: Save conversation
        # ------------------------------------------------------------------ #
        now = datetime.now(timezone.utc)

        messages.append(
            {
                "role": "user",
                "content": request.message,
                "timestamp": now.isoformat(),
            }
        )
        messages.append(
            {
                "role": "assistant",
                "content": ai_response,
                "timestamp": now.isoformat(),
            }
        )

        conversation.messages = messages
        conversation.updated_at = now

        # Auto-generate title from first user message
        if len(messages) <= 2 and not conversation.title:
            conversation.title = request.message[:100]

        await db.flush()

        logger.info(
            "Chat message processed",
            conversation_id=str(conversation.id),
            user_id=str(user_id),
            sources=len(sources),
        )

        return ChatResponse(
            message=ai_response,
            sources=sources,
            conversation_id=conversation.id,
        )

    # ---------------------------------------------------------------------- #
    # Conversation management
    # ---------------------------------------------------------------------- #

    async def get_conversation(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[ConversationResponse]:
        """Fetch a conversation by ID, checking ownership.

        Args:
            db: Async session.
            conversation_id: UUID of the conversation.
            user_id: UUID of the requesting user.

        Returns:
            ConversationResponse or None if not found / not owned.
        """
        stmt = select(AiConversation).where(
            AiConversation.id == conversation_id,
            AiConversation.user_id == user_id,
        )
        result = await db.execute(stmt)
        conv = result.scalar_one_or_none()

        if not conv:
            return None

        messages = [
            ChatMessage(
                role=m["role"],
                content=m["content"],
                timestamp=m.get("timestamp"),
            )
            for m in (conv.messages or [])
        ]

        return ConversationResponse(
            id=conv.id,
            user_id=conv.user_id,
            org_id=conv.org_id,
            title=conv.title,
            messages=messages,
            spec_context_id=conv.spec_context_id,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=len(messages),
        )

    async def list_conversations(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        page: int = 1,
        size: int = 20,
    ) -> list[ConversationListItem]:
        """List conversations for a user, most recent first.

        Args:
            db: Async session.
            user_id: UUID of the requesting user.
            page: 1-based page number.
            size: Items per page.

        Returns:
            List of ConversationListItem.
        """
        stmt = (
            select(AiConversation)
            .where(AiConversation.user_id == user_id)
            .order_by(AiConversation.updated_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await db.execute(stmt)
        convs = result.scalars().all()

        return [
            ConversationListItem(
                id=conv.id,
                title=conv.title or "Untitled conversation",
                spec_context_id=conv.spec_context_id,
                message_count=len(conv.messages or []),
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
            for conv in convs
        ]

    async def delete_conversation(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Delete a conversation, checking ownership.

        Args:
            db: Async session.
            conversation_id: UUID of the conversation to delete.
            user_id: UUID of the requesting user.

        Returns:
            True if deleted, False if not found.
        """
        stmt = select(AiConversation).where(
            AiConversation.id == conversation_id,
            AiConversation.user_id == user_id,
        )
        result = await db.execute(stmt)
        conv = result.scalar_one_or_none()

        if not conv:
            return False

        await db.delete(conv)
        await db.flush()
        logger.info("Conversation deleted", conversation_id=str(conversation_id))
        return True

    # ---------------------------------------------------------------------- #
    # Helpers
    # ---------------------------------------------------------------------- #

    async def _get_or_create_conversation(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        org_id: Optional[uuid.UUID],
        conversation_id: Optional[uuid.UUID],
        spec_id: Optional[uuid.UUID],
    ) -> AiConversation:
        """Load an existing conversation or create a new one."""
        if conversation_id:
            stmt = select(AiConversation).where(
                AiConversation.id == conversation_id,
                AiConversation.user_id == user_id,
            )
            result = await db.execute(stmt)
            conv = result.scalar_one_or_none()
            if conv:
                return conv

        # Create new conversation
        conv = AiConversation(
            user_id=user_id,
            org_id=org_id,
            spec_context_id=spec_id,
            messages=[],
        )
        db.add(conv)
        await db.flush()
        await db.refresh(conv)
        return conv

    async def _get_graph_context(
        self,
        neo4j_session: Any,
        query: str,
        spec_id: uuid.UUID,
    ) -> str:
        """Extract brief graph context relevant to the user's query."""
        query_lower = query.lower()

        # Try to find mentioned endpoint paths or flow names in the query
        result = await neo4j_session.run(
            """
            MATCH (s:ApiSpec {spec_id: $spec_id})-[:HAS_ENDPOINT]->(e:Endpoint)
            WHERE toLower(e.path) CONTAINS $query_fragment
               OR toLower(e.name) CONTAINS $query_fragment
            RETURN e.path AS path, e.method AS method, e.risk_level AS risk, e.name AS name
            LIMIT 5
            """,
            {
                "spec_id": str(spec_id),
                "query_fragment": query_lower[:50],
            },
        )
        records = await result.data()

        if not records:
            return ""

        lines = ["Related endpoints from knowledge graph:"]
        for rec in records:
            lines.append(
                f"  {rec.get('method', '')} {rec.get('path', '')} "
                f"(risk: {rec.get('risk', 'unknown')}) — {rec.get('name', '')}"
            )

        return "\n".join(lines)
