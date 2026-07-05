import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from backend.audit import AuditLogger
from backend.executors import ExecutorRegistry
from backend.provider_registry import (
    OperationNotExecutableError,
    ProviderRegistry,
)
from backend.runtime import RuntimeService
from backend.travel_executor import TravelExecutor, TravelProvider


class ProviderContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Mock()
        self.repository.get_trips.return_value = [{"id": "trip-1"}]
        self.provider = TravelProvider(repository=self.repository)
        self.registry = ProviderRegistry()
        self.registry.register(self.provider)

    def test_catalog_exposes_contract_v1_fields_and_planned_operations(self) -> None:
        catalog = self.registry.catalog()

        self.assertEqual(catalog["contract_version"], "1")
        self.assertEqual(catalog["providers"][0]["provider_id"], "travel")
        operations = {
            item["operation_id"]: item
            for item in catalog["providers"][0]["operations"]
        }
        get_trip = operations["get_trip"]
        for field in (
            "provider_id",
            "operation_id",
            "description",
            "what_it_can_do",
            "what_it_cannot_do",
            "input_schema",
            "output_schema",
            "mode",
            "risk_level",
            "confirmation_required",
            "audit_required",
            "examples",
            "limitations",
        ):
            self.assertIn(field, get_trip)
        self.assertEqual(get_trip["availability"], "implemented")
        self.assertEqual(operations["search_trip"]["availability"], "planned")
        self.assertIsNone(operations["search_trip"]["tool_id"])

    def test_planned_operation_cannot_be_resolved_for_execution(self) -> None:
        with self.assertRaises(OperationNotExecutableError):
            self.registry.get_operation("travel", "search_trip", executable=True)

    def test_runtime_provider_path_uses_existing_safety_pipeline(self) -> None:
        executor_registry = ExecutorRegistry()
        executor_registry.register_skill("travel", TravelExecutor(provider=self.provider))
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = RuntimeService(
                audit_logger=AuditLogger(Path(temp_dir) / "audit.log"),
                executor_registry=executor_registry,
                provider_registry=self.registry,
            )
            response = runtime.execute_provider_operation(
                "travel", "get_trips", {}, role="guest"
            )

        self.assertTrue(response["success"])
        self.assertEqual(response["result"]["trips"], [{"id": "trip-1"}])
        self.repository.get_trips.assert_called_once_with()

    def test_runtime_provider_write_still_requires_permission_and_confirmation(self) -> None:
        executor_registry = ExecutorRegistry()
        executor_registry.register_skill("travel", TravelExecutor(provider=self.provider))
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = RuntimeService(
                audit_logger=AuditLogger(Path(temp_dir) / "audit.log"),
                executor_registry=executor_registry,
                provider_registry=self.registry,
            )
            guest_response = runtime.execute_provider_operation(
                "travel", "create_trip", {"title": "test"}, role="guest"
            )
            admin_response = runtime.execute_provider_operation(
                "travel", "create_trip", {"title": "test"}, role="admin"
            )

        self.assertTrue(guest_response["permission_denied"])
        self.assertTrue(admin_response["blocked"])
        self.assertTrue(admin_response["confirmation_required"])
        self.repository.create_trip.assert_not_called()


if __name__ == "__main__":
    unittest.main()
