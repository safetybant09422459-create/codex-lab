from __future__ import annotations

from typing import Any
from urllib.parse import quote

from .chat_core import ComposeRequest, ComposeResult, ConversationState
from .openai_adapter import redact_sensitive_text
from .travel_chat_adapter import (
    compose_travel_chat_response_v1,
    conversation_state_from_runtime_trip,
)


TRIP_NOT_FOUND_REPLY = "該当する旅行が見つかりませんでした。"
MULTIPLE_TRIPS_REPLY = "候補が複数あります。"
WRITE_NOT_IMPLEMENTED_REPLY = (
    "更新操作には確認が必要です。現在は提案のみ対応しています。"
)
RUNTIME_ERROR_REPLY = "Toolの実行に失敗しました。時間をおいて再度お試しください。"
PERMISSION_DENIED_REPLY = "この操作を実行する権限がありません。"
MAX_STEPS_REPLY = "安全のため処理を中断しました。対象の旅行をもう少し具体的に指定してください。"

SUCCESS_REPLIES = {
    "get_trips": "旅行一覧を取得しました。",
    "get_trip": "旅行情報を取得しました。",
    "get_trip_timeline": "旅行タイムラインを取得しました。",
    "get_experience": "体験情報を取得しました。",
    "get_experience_photos": "体験写真を取得しました。",
    "get_experience_photo_links": "体験写真リンクを取得しました。",
    "get_experience_photo_search": "体験写真の検索結果を取得しました。",
}


class TravelResponseComposer:
    """Compose Travel results without crossing Planner, Resolver, or Runtime."""

    def compose(self, request: ComposeRequest) -> ComposeResult:
        state = request.conversation_state
        if request.outcome == "candidates":
            candidate_fallback = (
                f"{len(request.candidates)}件の候補があります。どれを開きますか？"
                if request.candidates
                else MULTIPLE_TRIPS_REPLY
            )
            clarification_reply = _answer_or_default(request, candidate_fallback)
            response = {
                "action": "needs_context",
                "reply": clarification_reply,
                "candidates": request.candidates,
                "clarification": {
                    "status": "candidates",
                    "clarification": clarification_reply,
                    "candidate_list": request.candidates,
                    "reason": "missing_context",
                    "recommended_action": "select_candidate",
                },
            }
        elif request.outcome == "success":
            response, state = self._compose_success(request, state)
        elif request.outcome == "not_found":
            response = {
                "action": "needs_context",
                "reply": TRIP_NOT_FOUND_REPLY,
            }
            if request.clear_context_on_not_found:
                state = ConversationState(active_skill="travel")
        elif request.outcome == "pending_write":
            response = {
                "action": "pending_write_not_implemented",
                "tool_id": request.tool_id,
                "arguments": request.arguments,
                "reply": WRITE_NOT_IMPLEMENTED_REPLY,
            }
        elif request.outcome == "needs_context":
            response = {
                "action": "needs_context",
                # plan.reason is Planner LLM output; Python only supplies a
                # meaning-neutral fallback when no reason is available.
                "reply": (
                    request.plan.reason
                    if request.plan is not None and request.plan.reason
                    else "対象を指定してください。"
                ),
            }
        elif request.outcome in {"runtime_error", "permission_denied"}:
            response = {
                "action": request.outcome,
                "tool_id": request.tool_id,
                "arguments": request.arguments,
                "reply": (
                    PERMISSION_DENIED_REPLY
                    if request.outcome == "permission_denied"
                    else RUNTIME_ERROR_REPLY
                ),
            }
        elif request.outcome == "max_steps":
            response = {
                "action": "needs_context",
                "reply": MAX_STEPS_REPLY,
            }
        else:
            raise ValueError(f"unsupported Travel compose outcome: {request.outcome}")

        return ComposeResult(
            response=response,
            response_v1=compose_travel_chat_response_v1(
                response,
                conversation_state=state,
            ),
            conversation_state=state,
        )

    def _compose_success(
        self,
        request: ComposeRequest,
        state: ConversationState | None,
    ) -> tuple[dict[str, Any], ConversationState | None]:
        tool_id = request.tool_id
        if tool_id not in SUCCESS_REPLIES:
            raise ValueError(f"unsupported Travel success tool: {tool_id}")

        response: dict[str, Any] = {
            "action": "tool_result",
            "tool_id": tool_id,
            "arguments": request.arguments,
            "reply": SUCCESS_REPLIES[tool_id],
            "result": request.runtime_result,
        }
        if (
            request.answer_result is not None
            and request.answer_result.answer_type != "not_applicable"
        ):
            response["reply"] = request.answer_result.answer
        if tool_id != "get_trip":
            return response, state

        trip = _extract_trip(request.runtime_result)
        if trip is None:
            response = {
                "action": "needs_context",
                "reply": TRIP_NOT_FOUND_REPLY,
            }
            if request.clear_context_on_not_found:
                state = ConversationState(active_skill="travel")
            return response, state

        state = conversation_state_from_runtime_trip(trip)
        title = trip.get("title")
        response["reply"] = (
            f"{redact_sensitive_text(title)}を開きます。"
            if isinstance(title, str) and title.strip()
            else "旅行を開きます。"
        )
        trip_id = request.arguments.get("trip_id")
        if not isinstance(trip_id, str):
            raise ValueError("get_trip response requires a string trip_id")
        safe_trip_id = redact_sensitive_text(trip_id)
        response["navigation"] = request.navigation_hint or {
            "type": "travel_trip",
            "target": f"#travel?trip_id={quote(safe_trip_id, safe='')}",
            "trip_id": safe_trip_id,
            "label": "Travelで開く",
        }
        if (
            request.answer_result is not None
            and request.answer_result.answer_type != "not_applicable"
            and request.answer_result.source == "llm"
        ):
            response["reply"] = request.answer_result.answer
        return response, state


def _extract_trip(runtime_result: Any) -> dict[str, Any] | None:
    if not isinstance(runtime_result, dict):
        return None
    trip = runtime_result.get("trip")
    if not isinstance(trip, dict):
        return None
    trip_id = trip.get("id")
    if not isinstance(trip_id, str) or not trip_id.strip():
        return None
    return trip


def _answer_or_default(request: ComposeRequest, default: str) -> str:
    answer = request.answer_result
    if answer is not None and answer.answer.strip():
        return answer.answer
    return default
