import unittest

from backend.native_tools import NativeToolSchemaError, compile_registry


class NativeToolRegistryTest(unittest.TestCase):
    def test_resolve_operation_uses_catalog_ids_and_fails_closed(self) -> None:
        registry = compile_registry({
            "providers": [{
                "provider_id": "travel",
                "operations": [{
                    "provider_id": "travel",
                    "operation_id": "get_trip",
                    "availability": "implemented",
                    "input_schema": {
                        "type": "object",
                        "properties": {"trip_id": {"type": "string"}},
                        "required": ["trip_id"],
                    },
                }],
            }],
        })

        entry = registry.resolve_operation("travel", "get_trip")
        self.assertEqual(entry.provider_id, "travel")
        self.assertEqual(entry.operation_id, "get_trip")
        for provider_id, operation_id in (
            ("unknown", "get_trip"), ("travel", "unknown")
        ):
            with self.subTest(provider_id=provider_id, operation_id=operation_id):
                with self.assertRaises(NativeToolSchemaError):
                    registry.resolve_operation(provider_id, operation_id)


if __name__ == "__main__":
    unittest.main()
