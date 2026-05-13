"""Pydantic schemas for AI chat (RAG) conversations."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single message in a conversation thread."""

    role: str = Field(description="user or assistant")  # user | assistant | system
    content: str = Field(min_length=1)
    timestamp: Optional[datetime] = None


class ChatRequest(BaseModel):
    """Request payload for a chat message."""

    message: str = Field(min_length=1, max_length=10000)
    conversation_id: Optional[uuid.UUID] = None
    spec_id: Optional[uuid.UUID] = None
    top_k: int = Field(default=5, ge=1, le=20)


class ChatSource(BaseModel):
    """A document chunk referenced in the AI response."""

    chunk_id: uuid.UUID
    content: str
    score: float
    chunk_type: str
    spec_name: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class ChatResponse(BaseModel):
    """AI response with source citations and conversation tracking."""

    message: str
    sources: List[ChatSource] = Field(default_factory=list)
    conversation_id: uuid.UUID
    role: str = "assistant"


class ConversationResponse(BaseModel):
    """Serialised conversation record."""

    id: uuid.UUID
    user_id: uuid.UUID
    org_id: Optional[uuid.UUID]
    title: Optional[str]
    messages: List[ChatMessage] = Field(default_factory=list)
    spec_context_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class ConversationListItem(BaseModel):
    """Lightweight conversation list item."""

    id: uuid.UUID
    title: Optional[str]
    spec_context_id: Optional[uuid.UUID]
    message_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
