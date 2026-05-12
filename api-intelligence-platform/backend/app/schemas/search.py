"""Pydantic schemas for semantic and hybrid search."""
from __future__ import annotations

import uuid
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    """Optional filter parameters for search queries."""

    chunk_type: Optional[str] = None  # api | flow | schema | security | general
    method: Optional[str] = None
    risk_level: Optional[str] = None
    tags: Optional[List[str]] = None


class SearchRequest(BaseModel):
    """Payload for a semantic or hybrid search request."""

    query: str = Field(min_length=1, max_length=2000)
    filters: Optional[SearchFilters] = None
    top_k: int = Field(default=10, ge=1, le=100)
    spec_id: Optional[uuid.UUID] = None
    search_type: str = Field(default="hybrid")  # semantic | hybrid | keyword


class SearchResult(BaseModel):
    """A single search result item."""

    chunk_id: uuid.UUID
    content: str
    score: float
    chunk_type: str
    metadata: Optional[dict[str, Any]] = None
    endpoint: Optional[dict[str, Any]] = None
    flow: Optional[dict[str, Any]] = None
    spec_id: Optional[uuid.UUID] = None
    spec_name: Optional[str] = None


class SearchResponse(BaseModel):
    """Response containing ranked search results."""

    query: str
    results: List[SearchResult]
    total: int
    search_type: str
    spec_id: Optional[uuid.UUID] = None


class SuggestRequest(BaseModel):
    """Autocomplete suggestion request."""

    prefix: str = Field(min_length=1, max_length=200)
    spec_id: Optional[uuid.UUID] = None
    limit: int = Field(default=10, ge=1, le=50)


class SuggestResponse(BaseModel):
    """Autocomplete suggestions response."""

    suggestions: List[str]
    prefix: str
