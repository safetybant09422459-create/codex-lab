from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any

from .chat_core import AnswerRequest, AnswerResult, ExecutionEvidence
from .travel_chat_adapter import selected_trip_entity


NO_EVIDENCE_REPLY = "取得できた情報がないため、回答できません。"
NO_ACTIVITY_REPLY = "取得できた情報には行動内容は含まれていません。"
NO_FOOD_REPLY = "取得できた情報には食事内容は含まれていません。"

_DAY_PATTERN = re.compile(r"([0-9]+|[一二三四五六七八九十]+)日目")
_FOOD_TERMS = (
    "食事",
    "朝食",
    "昼食",
    "夕食",
    "晩ごはん",
    "ごはん",
    "ランチ",
    "ディナー",
    "カフェ",
    "レストラン",
    "寿司",
    "ラーメン",
    "うどん",
    "そば",
    "焼肉",
)
_FOOD_TYPES = {
    "food",
    "meal",
    "breakfast",
    "lunch",
    "dinner",
    "restaurant",
    "cafe",
    "dining",
    "食事",
}


class TravelAnswerGenerator:
    """Generate a direct Travel answer using acquired Evidence only.

    This component has no Runtime, Tool, permission, repository, or network
    dependency. It deliberately returns ``not_applicable`` outside the three
    v0.1 question forms so the legacy ResponseComposer behavior stays intact.
    """

    def generate(self, request: AnswerRequest) -> AnswerResult:
        answer_type, day_number = _answer_target(request)
        evidence = request.evidence or request.execution_result.evidence
        if answer_type == "not_applicable":
            return AnswerResult(
                answer="",
                confidence="low",
                answer_type=answer_type,
                source="fallback_travel_answer_generator",
            )
        if not evidence or not any(item.result is not None for item in evidence):
            return AnswerResult(
                answer=NO_EVIDENCE_REPLY,
                confidence="low",
                answer_type=answer_type,
                source="fallback_travel_answer_generator",
                evidence_used=False,
            )

        timeline_items = _timeline_items(evidence)
        if answer_type == "day":
            timeline_items = _items_for_day(
                timeline_items,
                day_number=day_number or 1,
                trip_start=_trip_start_date(evidence),
            )
        elif answer_type == "food":
            timeline_items = [item for item in timeline_items if _is_food(item)]

        used = _used_evidence(evidence, timeline_items)
        labels = _item_labels(timeline_items)
        if not labels:
            if answer_type == "food":
                answer = NO_FOOD_REPLY
            elif answer_type == "day":
                answer = (
                    f"取得できた情報には{day_number or 1}日目の行動内容は"
                    "含まれていません。"
                )
            else:
                answer = NO_ACTIVITY_REPLY
            return AnswerResult(
                answer=answer,
                confidence="low",
                answer_type=answer_type,
                source="fallback_travel_answer_generator",
                evidence_used=True,
            )

        trip_label = _trip_label(request, evidence)
        prefix = f"{trip_label}では、" if trip_label else ""
        if answer_type == "food":
            answer = f"{prefix}食事については{_join_labels(labels)}の記録があります。"
        elif answer_type == "day":
            answer = (
                f"{day_number or 1}日目は、{_join_labels(labels)}の記録があります。"
            )
        else:
            answer = f"{prefix}{_join_labels(labels)}の記録があります。"
        return AnswerResult(
            answer=answer,
            confidence="high",
            answer_type=answer_type,
            used_evidence=used,
            source="fallback_travel_answer_generator",
            evidence_used=True,
        )


def _answer_target(request: AnswerRequest) -> tuple[str, int | None]:
    day_match = _DAY_PATTERN.search(
        unicodedata.normalize("NFKC", request.user_question or "")
    )
    day_number = _parse_day(day_match.group(1)) if day_match else None
    if request.plan is None:
        return "not_applicable", None
    by_mode = {
        "summary": "activities",
        "day_summary": "day",
        "meals": "food",
    }
    answer_type = by_mode.get(request.plan.answer_mode)
    if answer_type is not None:
        return answer_type, day_number
    return "not_applicable", None


def _parse_day(value: str) -> int:
    if value.isdigit():
        return max(int(value), 1)
    digits = {
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    if value == "十":
        return 10
    if "十" in value:
        left, right = value.split("十", 1)
        return digits.get(left, 1) * 10 + digits.get(right, 0)
    return digits.get(value, 1)


def _timeline_items(evidence: list[ExecutionEvidence]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entry in evidence:
        if not isinstance(entry.result, dict):
            continue
        for key in ("items", "timeline"):
            value = entry.result.get(key)
            if isinstance(value, list):
                items.extend(item for item in value if isinstance(item, dict))
    return items


def _items_for_day(
    items: list[dict[str, Any]],
    *,
    day_number: int,
    trip_start: date | None,
) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for item in items:
        explicit_day = item.get("day_number", item.get("day"))
        if isinstance(explicit_day, int) and explicit_day == day_number:
            matched.append(item)
            continue
        if isinstance(explicit_day, str) and explicit_day.isdigit():
            if int(explicit_day) == day_number:
                matched.append(item)
            continue
        item_date = _date_from_value(item.get("start_at") or item.get("date"))
        if trip_start is not None and item_date is not None:
            if (item_date - trip_start).days + 1 == day_number:
                matched.append(item)
    return matched


def _trip_start_date(evidence: list[ExecutionEvidence]) -> date | None:
    target_trip_ids = {
        trip_id
        for entry in evidence
        if isinstance((trip_id := entry.arguments.get("trip_id")), str)
    }
    for entry in evidence:
        if not isinstance(entry.result, dict):
            continue
        trip = entry.result.get("trip")
        if isinstance(trip, dict):
            value = _date_from_value(trip.get("start_date"))
            if value is not None:
                return value
        trips = entry.result.get("trips")
        if isinstance(trips, list) and target_trip_ids:
            for candidate in trips:
                if (
                    isinstance(candidate, dict)
                    and candidate.get("id") in target_trip_ids
                ):
                    value = _date_from_value(candidate.get("start_date"))
                    if value is not None:
                        return value
    return None


def _date_from_value(value: Any) -> date | None:
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _is_food(item: dict[str, Any]) -> bool:
    typed_values = (
        item.get("category"),
        item.get("item_type"),
        item.get("experience_type"),
    )
    if any(
        isinstance(value, str) and value.casefold() in _FOOD_TYPES
        for value in typed_values
    ):
        return True
    text = " ".join(
        str(item.get(key, ""))
        for key in ("display_title", "title", "place_name", "memo")
    )
    return any(term in text for term in _FOOD_TERMS)


def _item_labels(items: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    for item in items:
        label = next(
            (
                value.strip()
                for key in ("display_title", "title", "place_name", "memo")
                if isinstance((value := item.get(key)), str) and value.strip()
            ),
            None,
        )
        if label and label not in labels:
            labels.append(label)
    return labels


def _trip_label(request: AnswerRequest, evidence: list[ExecutionEvidence]) -> str | None:
    for entry in evidence:
        if not isinstance(entry.result, dict):
            continue
        trip = entry.result.get("trip")
        if isinstance(trip, dict) and isinstance(trip.get("title"), str):
            return trip["title"].strip() or None
    selected = selected_trip_entity(request.conversation_state)
    return selected.label if selected is not None else None


def _used_evidence(
    evidence: list[ExecutionEvidence],
    selected_items: list[dict[str, Any]],
) -> list[ExecutionEvidence]:
    if not selected_items:
        return []
    selected_ids = {id(item) for item in selected_items}
    used: list[ExecutionEvidence] = []
    for entry in evidence:
        if not isinstance(entry.result, dict):
            continue
        for key in ("items", "timeline"):
            values = entry.result.get(key)
            if not isinstance(values, list):
                continue
            for item in values:
                if isinstance(item, dict) and id(item) in selected_ids:
                    used.append(
                        ExecutionEvidence(
                            tool_id=entry.tool_id,
                            arguments=entry.arguments,
                            result=item,
                        )
                    )
    return used


def _join_labels(labels: list[str]) -> str:
    if len(labels) == 1:
        return labels[0]
    return "、".join(labels[:-1]) + "、その後" + labels[-1]
