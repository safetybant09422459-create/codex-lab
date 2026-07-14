from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable

from .conversation_state import ConversationTurnState


class ContextAssemblyError(ValueError):
    """Raised when fixed context metadata alone exceeds the byte budget."""


@dataclass(frozen=True)
class ContextAssemblyConfig:
    max_turns: int = 5
    max_observations: int = 5
    max_active_entities: int = 20
    max_capabilities: int = 50
    max_bytes: int = 64 * 1024
    redacted_keys: frozenset[str] = frozenset(
        {"api_key", "authorization", "password", "secret", "token"}
    )
    redaction_marker: str = "[REDACTED]"

    def __post_init__(self) -> None:
        for name in (
            "max_turns",
            "max_observations",
            "max_active_entities",
            "max_capabilities",
            "max_bytes",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be at least 1")


class ConversationContextBuilder:
    """Mechanically projects bounded Conversation State into LLM context.

    The builder does not inspect natural-language values. It preserves input
    order, applies explicit limits and policy filters, and never summarizes or
    selects a topic, provider, operation, or clarification.
    """

    VERSION = "1"

    def __init__(self, config: ContextAssemblyConfig | None = None) -> None:
        self.config = config or ContextAssemblyConfig()

    def build(
        self,
        *,
        session_id: str,
        channel: str,
        conversation_started_at: str,
        previous_turns: Iterable[ConversationTurnState],
        capabilities: Iterable[dict[str, Any]],
        allowed_visibilities: frozenset[str],
    ) -> dict[str, Any]:
        turns = list(previous_turns)[-self.config.max_turns :]
        last_turn = turns[-1] if turns else None
        trusted_last_turn = (
            last_turn if last_turn and last_turn.source == "server_turn" else None
        )
        context = {
            "context_version": self.VERSION,
            "session_info": {
                "session_id": session_id,
                "channel": channel,
                "conversation_started_at": conversation_started_at,
            },
            "conversation_context": [
                {
                    "user_input": turn.user_input,
                    "assistant_final_response": turn.assistant_final_response,
                    "source": turn.source,
                }
                for turn in turns
            ],
            "conversation_state": {
                "last_llm_action": (
                    trusted_last_turn.last_llm_action if trusted_last_turn else None
                ),
                "last_observations": (
                    trusted_last_turn.last_observations[
                        -self.config.max_observations :
                    ]
                    if trusted_last_turn
                    else []
                ),
                "active_entities": (
                    trusted_last_turn.active_entities[
                        -self.config.max_active_entities :
                    ]
                    if trusted_last_turn
                    else []
                ),
            },
            "capability_context": list(capabilities)[: self.config.max_capabilities],
        }
        context = self._redact(context)
        self._filter_visibility(context, allowed_visibilities)
        self._apply_byte_limit(context)
        return deepcopy(context)

    def _redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: (
                    self.config.redaction_marker
                    if key.casefold() in self.config.redacted_keys
                    else self._redact(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        return deepcopy(value)

    @staticmethod
    def _visible_items(
        items: list[Any], allowed_visibilities: frozenset[str]
    ) -> list[Any]:
        return [
            item
            for item in items
            if not isinstance(item, dict)
            or "visibility" not in item
            or item["visibility"] in allowed_visibilities
        ]

    def _filter_visibility(
        self, context: dict[str, Any], allowed_visibilities: frozenset[str]
    ) -> None:
        state = context["conversation_state"]
        state["last_observations"] = self._visible_items(
            state["last_observations"], allowed_visibilities
        )
        state["active_entities"] = self._visible_items(
            state["active_entities"], allowed_visibilities
        )
        context["capability_context"] = self._visible_items(
            context["capability_context"], allowed_visibilities
        )

    def _apply_byte_limit(self, context: dict[str, Any]) -> None:
        removable_lists = (
            context["conversation_context"],
            context["conversation_state"]["last_observations"],
            context["conversation_state"]["active_entities"],
            context["capability_context"],
        )
        while self._byte_size(context) > self.config.max_bytes:
            for items in removable_lists:
                if items:
                    del items[0]
                    break
            else:
                if context["conversation_state"]["last_llm_action"] is not None:
                    context["conversation_state"]["last_llm_action"] = None
                else:
                    raise ContextAssemblyError(
                        "Fixed context metadata exceeds the configured byte limit"
                    )

    @staticmethod
    def _byte_size(context: dict[str, Any]) -> int:
        return len(
            json.dumps(
                context, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            ).encode("utf-8")
        )
