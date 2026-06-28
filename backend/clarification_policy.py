from __future__ import annotations

import unicodedata
from typing import Any

from .chat_core import ClarificationResult, ComposeRequest


class ClarificationPolicy:
    """Turn unresolved execution facts into a bounded conversational action.

    The policy only ranks or filters candidates already returned by Runtime. It
    does not call Runtime, Search, a Resolver, or a Planner.
    """

    def evaluate(self, request: ComposeRequest) -> ClarificationResult:
        candidates = _valid_candidates(request.candidates)
        if request.outcome == "candidates" and candidates:
            return _candidate_result(candidates, reason="multiple_candidates")

        trips = _runtime_trips(request.runtime_result)
        confidence = request.plan.confidence if request.plan is not None else None
        message = _normalize(request.user_message)
        if trips:
            if "初めて" in message:
                first_trip_candidates = [
                    trip
                    for trip in trips
                    if "初旅行" in _normalize(str(trip.get("title", "")))
                ]
                if first_trip_candidates:
                    return _candidate_result(
                        first_trip_candidates,
                        reason="query_too_broad",
                        clarification=(
                            f"「初めての旅行」に近い候補が"
                            f"{len(first_trip_candidates)}件あります。どれを開きますか？"
                        ),
                    )
            if "どれか" in message or "最近" in message:
                latest = sorted(trips, key=_recency_key, reverse=True)[:3]
                return _candidate_result(
                    latest,
                    reason="query_too_broad",
                    clarification=(
                        f"最近の旅行を{len(latest)}件表示します。どれを開きますか？"
                    ),
                )
            if _is_broad_trip_request(message) or confidence == "low":
                return _candidate_result(
                    trips,
                    reason="query_too_broad",
                    clarification=f"旅行は{len(trips)}件あります。どれを開きますか？",
                )

        if request.outcome == "needs_context":
            return ClarificationResult(
                status="clarification_required",
                clarification=(
                    request.plan.reason
                    if request.plan is not None and request.plan.reason
                    else "対象をもう少し具体的に教えてください。"
                ),
                reason="missing_context",
                recommended_action="provide_context",
            )
        if confidence == "low" and request.outcome == "not_found":
            return ClarificationResult(
                status="clarification_required",
                clarification="対象をもう少し具体的に教えてください。",
                reason="low_confidence",
                recommended_action="provide_context",
            )
        return ClarificationResult(status="not_required")


def _candidate_result(
    candidates: list[dict[str, Any]],
    *,
    reason: str,
    clarification: str | None = None,
) -> ClarificationResult:
    return ClarificationResult(
        status="candidates",
        clarification=clarification
        or f"{len(candidates)}件の候補があります。どれを開きますか？",
        candidate_list=candidates,
        reason=reason,
        recommended_action="select_candidate",
    )


def _runtime_trips(runtime_result: Any) -> list[dict[str, Any]]:
    if not isinstance(runtime_result, dict):
        return []
    return _valid_candidates(runtime_result.get("trips"))


def _valid_candidates(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        item
        for item in value
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and item["id"].strip()
    ]


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if not character.isspace())


def _is_broad_trip_request(message: str) -> bool:
    if "旅行一覧" in message or "旅一覧" in message:
        return False
    value = message.rstrip("。.!！?？")
    for suffix in (
        "を開いてください",
        "開いてください",
        "を表示してください",
        "表示してください",
        "を見せてください",
        "見せてください",
        "を開いて",
        "開いて",
        "を表示して",
        "表示して",
        "を見せて",
        "見せて",
        "を開く",
        "開く",
    ):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
            break
    return value.strip("「」『』\"'") in {"旅行", "旅", "trip", "trips"}


def _recency_key(candidate: dict[str, Any]) -> tuple[str, str, str]:
    """Prefer the trip date, then stable Runtime timestamps and ID."""
    return (
        str(candidate.get("start_date") or ""),
        str(candidate.get("updated_at") or candidate.get("created_at") or ""),
        str(candidate.get("id") or ""),
    )
