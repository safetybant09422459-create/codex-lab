import unittest

from backend.domain_provider import OperationContext
from backend.jarvis_provider import JarvisProvider
from backend.models import RuntimeExecuteResponse
from backend.photo_executor import PhotoProvider
from backend.travel_executor import TravelProvider


class RuntimeExecutionModeContractTest(unittest.TestCase):
    def test_every_executor_mode_validates_as_runtime_response(self) -> None:
        read = OperationContext("get_trips", "travel", "read", "low")
        write = OperationContext("create_trip", "travel", "write", "medium")
        recent_photos = OperationContext("get_recent_photos", "photo", "read", "low")
        local_photo = OperationContext("other", "photo", "read", "low")
        jarvis_status = OperationContext("get_capabilities", "jarvis", "read", "low")
        modes = {
            "stub",
            "local_weather_stub",
            TravelProvider().get_execution_mode(read),
            TravelProvider().get_execution_mode(write),
            PhotoProvider().get_execution_mode(recent_photos),
            PhotoProvider().get_execution_mode(local_photo),
            JarvisProvider(lambda: {}, lambda: {}).get_execution_mode(jarvis_status),
        }

        self.assertEqual(
            modes,
            {
                "stub",
                "local_weather_stub",
                "local_travel_read",
                "local_travel_write",
                "local_photo_read",
                "immich_photo_metadata_read",
                "local_jarvis_status_read",
            },
        )
        for mode in modes:
            response = RuntimeExecuteResponse(
                success=True,
                tool_id="contract-test",
                execution_mode=mode,
                result={},
            )
            self.assertEqual(response.execution_mode, mode)


if __name__ == "__main__":
    unittest.main()
