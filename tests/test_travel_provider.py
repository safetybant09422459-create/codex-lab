import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from backend.domain_provider import OperationContext
from backend.travel_executor import TravelExecutor, TravelProvider


class TravelProviderTest(unittest.TestCase):
    def test_provider_executes_selected_operation_without_user_text(self) -> None:
        repository = Mock()
        repository.get_trip.return_value = {"id": "trip-1", "title": "旅行"}
        provider = TravelProvider(repository=repository)

        result = provider.execute(
            OperationContext("get_trip", "travel", "read", "low"),
            {"trip_id": "trip-1"},
        )

        self.assertEqual(result["trip"]["id"], "trip-1")
        repository.get_trip.assert_called_once_with("trip-1")

    def test_executor_only_adapts_runtime_tool_metadata(self) -> None:
        provider = Mock()
        provider.execute.return_value = {"tool_id": "get_trips", "trips": []}
        executor = TravelExecutor(provider=provider)
        tool = SimpleNamespace(
            id="get_trips", skill_id="travel", mode="read", risk_level="low"
        )

        result = executor.execute(tool, {})

        self.assertEqual(result["trips"], [])
        operation, arguments = provider.execute.call_args.args
        self.assertEqual(operation.operation_id, "get_trips")
        self.assertEqual(arguments, {})

    def test_provider_rejects_unknown_operation(self) -> None:
        provider = TravelProvider(repository=Mock())
        with self.assertRaisesRegex(ValueError, "Unsupported travel operation"):
            provider.execute(
                OperationContext("guess_user_intent", "travel", "read", "low"),
                {},
            )


if __name__ == "__main__":
    unittest.main()
