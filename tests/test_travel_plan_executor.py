import unittest

from backend.chat_core import ExecutionRequest, Plan, PlanToolCandidate
from backend.travel_chat_adapter import conversation_state_from_legacy_context
from backend.travel_plan_executor import TravelPlanExecutor


class FakeRuntimeService:
    def __init__(self, responses=None) -> None:
        self.responses = list(responses or [])
        self.calls = []

    def execute_stub(self, tool_id, params, confirmed=False, role=None):
        self.calls.append(
            {
                "tool_id": tool_id,
                "params": params,
                "confirmed": confirmed,
                "role": role,
            }
        )
        return self.responses[len(self.calls) - 1]


def plan_for(tool_id: str, arguments=None) -> Plan:
    return Plan(
        intent=tool_id,
        target_skill="travel",
        tool_candidates=[
            PlanToolCandidate(tool_id=tool_id, arguments=arguments or {})
        ],
        requires_confirmation=tool_id == "update_experience",
        reason="test plan",
        confidence="high",
    )


def request_for(
    plan: Plan,
    runtime: FakeRuntimeService,
    *,
    message: str,
    context=None,
    max_steps: int = 3,
) -> ExecutionRequest:
    return ExecutionRequest(
        plan=plan,
        user_message=message,
        conversation_state=conversation_state_from_legacy_context(context),
        role="family",
        runtime_service=runtime,
        max_steps=max_steps,
        debug=True,
    )


class TravelPlanExecutorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.executor = TravelPlanExecutor()

    def test_get_trips_executes_one_runtime_read(self) -> None:
        runtime_result = {"trips": [{"id": "trip-1"}]}
        runtime = FakeRuntimeService(
            [{"success": True, "result": runtime_result}]
        )

        result = self.executor.execute(
            request_for(
                plan_for("get_trips"),
                runtime,
                message="旅行一覧を見せて",
            )
        )

        self.assertEqual(result.execution_status, "success")
        self.assertEqual(result.runtime_result, runtime_result)
        self.assertEqual(result.tool_id, "get_trips")
        self.assertEqual([step.tool_id for step in result.steps], ["get_trips"])
        self.assertEqual(runtime.calls[0]["confirmed"], False)

    def test_named_trip_open_resolves_then_executes_get_trip(self) -> None:
        trip = {"id": "trip-fukuoka", "title": "福岡旅行"}
        runtime = FakeRuntimeService(
            [
                {"success": True, "result": {"trips": [trip]}},
                {"success": True, "result": {"trip": trip}},
            ]
        )

        result = self.executor.execute(
            request_for(
                plan_for("get_trips"),
                runtime,
                message="福岡旅行を開いて",
            )
        )

        self.assertEqual(result.execution_status, "success")
        self.assertEqual(result.tool_id, "get_trip")
        self.assertEqual(result.arguments, {"trip_id": "trip-fukuoka"})
        self.assertEqual(
            [call["tool_id"] for call in runtime.calls],
            ["get_trips", "get_trip"],
        )
        self.assertEqual(result.resolution_result.status, "resolved")

    def test_ambiguous_candidates_stop_before_get_trip(self) -> None:
        trips = [
            {"id": "trip-1", "title": "大阪旅行 2025"},
            {"id": "trip-2", "title": "大阪旅行 2026"},
        ]
        runtime = FakeRuntimeService(
            [{"success": True, "result": {"trips": trips}}]
        )

        result = self.executor.execute(
            request_for(
                plan_for("get_trips"),
                runtime,
                message="大阪旅行を開いて",
            )
        )

        self.assertEqual(result.execution_status, "candidates")
        self.assertEqual(result.candidates, trips)
        self.assertEqual(result.resolution_result.status, "ambiguous")
        self.assertEqual(len(runtime.calls), 1)

    def test_context_follow_up_validates_trip_before_timeline(self) -> None:
        trip = {"id": "trip-fukuoka", "title": "福岡旅行"}
        runtime = FakeRuntimeService(
            [
                {"success": True, "result": {"trip": trip}},
                {
                    "success": True,
                    "result": {"trip_id": "trip-fukuoka", "timeline": []},
                },
            ]
        )

        result = self.executor.execute(
            request_for(
                plan_for(
                    "get_trip_timeline",
                    {"trip_id": "trip-invented-by-model"},
                ),
                runtime,
                message="2日目は？",
                context={"selected_trip_id": "trip-fukuoka"},
            )
        )

        self.assertEqual(result.execution_status, "success")
        self.assertEqual(
            [call["tool_id"] for call in runtime.calls],
            ["get_trip", "get_trip_timeline"],
        )
        self.assertTrue(
            all(
                call["params"] == {"trip_id": "trip-fukuoka"}
                for call in runtime.calls
            )
        )
        self.assertEqual(
            result.conversation_state.selected_entities[0].label,
            "福岡旅行",
        )

    def test_write_plan_remains_pending_without_runtime_execution(self) -> None:
        runtime = FakeRuntimeService()

        result = self.executor.execute(
            request_for(
                plan_for(
                    "update_experience",
                    {"experience_id": "experience-1", "memo": "更新"},
                ),
                runtime,
                message="メモを更新して",
            )
        )

        self.assertEqual(result.execution_status, "pending_write")
        self.assertEqual(result.tool_id, "update_experience")
        self.assertEqual(runtime.calls, [])

    def test_max_steps_stops_before_follow_up_runtime_call(self) -> None:
        trip = {"id": "trip-fukuoka", "title": "福岡旅行"}
        runtime = FakeRuntimeService(
            [{"success": True, "result": {"trips": [trip]}}]
        )

        result = self.executor.execute(
            request_for(
                plan_for("get_trips"),
                runtime,
                message="福岡旅行を開いて",
                max_steps=1,
            )
        )

        self.assertEqual(result.execution_status, "max_steps")
        self.assertEqual(len(result.steps), 1)
        self.assertEqual(len(runtime.calls), 1)


if __name__ == "__main__":
    unittest.main()
