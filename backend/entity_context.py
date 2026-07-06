from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable

from .observation import ObservationEnvelope


@dataclass(frozen=True)
class EntityContextConfig:
    max_entities: int = 20

    def __post_init__(self) -> None:
        if self.max_entities < 1:
            raise ValueError("max_entities must be at least 1")


class EntityContextBuilder:
    """Projects observed canonical entity candidates without resolving them."""

    def __init__(self, config: EntityContextConfig | None = None) -> None:
        self.config = config or EntityContextConfig()

    def build(
        self,
        observations: Iterable[ObservationEnvelope],
        existing_entities: Iterable[dict[str, Any]] = (),
    ) -> list[dict[str, Any]]:
        entities = [deepcopy(entity) for entity in existing_entities]
        entities.extend(
            deepcopy(entity)
            for observation in observations
            for entity in observation.entities
        )
        return entities[-self.config.max_entities :]
