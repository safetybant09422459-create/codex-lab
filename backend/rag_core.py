from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# Provider-owned opaque value. Core must not enumerate Travel or other domain types.
RagEntityType = str


class RagModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RagDocument(RagModel):
    """Skill-neutral recall index entry; never the canonical entity record."""

    id: str = Field(min_length=1, max_length=512)
    source_skill: str = Field(min_length=1, max_length=120)
    entity_type: RagEntityType
    entity_id: str = Field(min_length=1, max_length=512)
    text: str = Field(min_length=1, max_length=50_000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    visibility: str = Field(min_length=1, max_length=120)
    updated_at: datetime


class RagSearchResult(RagModel):
    document: RagDocument
    score: float = Field(ge=0.0, le=1.0)
    matched_terms: list[str] = Field(default_factory=list)
    reason: str
