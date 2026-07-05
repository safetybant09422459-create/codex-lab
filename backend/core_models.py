from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CoreModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConversationTurn(CoreModel):
    """One bounded, ephemeral conversation turn; never persisted as Memory."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class EntityRef(CoreModel):
    skill_id: str
    entity_type: str
    entity_id: str
    label: str
    source: str
    verified_at: datetime | None = None


class EntityCandidate(CoreModel):
    """Unverified recall/search candidate, not execution evidence."""

    entity: EntityRef
    score: float = Field(ge=0.0, le=1.0)
    matched_by: str
