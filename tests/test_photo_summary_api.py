import unittest
from unittest.mock import patch

from backend import main


class PhotoSummaryApiTest(unittest.IsolatedAsyncioTestCase):
    async def test_returns_family_safe_summary_through_photo_provider(self) -> None:
        provider_response = {
            "success": True,
            "tool_id": "get_recent_photos",
            "execution_mode": "immich_photo_metadata_read",
            "result": {
                "photo_count": 3,
                "date_range": {"from": "2026-07-01T00:00:00+00:00", "to": "2026-07-02T00:00:00+00:00"},
                "date_bucket_counts": {"2026-07-01": 2, "2026-07-02": 1},
                "day_count": 2,
                "has_location_count": 1,
                "has_faces_count": 2,
                "camera_make_counts": {"Example": 3},
                "camera_model_counts": {"Example Camera": 3},
                "timezone": "Asia/Tokyo",
                "newest_photo_at": "2026-07-02T00:00:00+00:00",
                "oldest_photo_at": "2026-07-01T00:00:00+00:00",
                "observed_at": "2026-07-03T00:00:00+00:00",
                "source": "immich",
                "connection_status": "available",
                "sample_photo_ids": ["dummy-private-asset"],
                "limitations": ["dummy internal detail"],
            },
        }
        with patch.object(
            main.runtime_service,
            "execute_provider_operation",
            return_value=provider_response,
        ) as execute:
            response = await main.photo_recent_summary(days=7, limit=10)

        execute.assert_called_once_with(
            "photo", "get_recent_photos", {"days": 7, "limit": 10}, confirmed=False, role="guest"
        )
        payload = response.model_dump()
        self.assertEqual(payload["photo_count"], 3)
        self.assertNotIn("sample_photo_ids", payload)
        self.assertNotIn("dummy internal detail", " ".join(payload["limitations"]))

    async def test_unavailable_response_does_not_expose_adapter_error(self) -> None:
        with patch.object(
            main.runtime_service,
            "execute_provider_operation",
            return_value={
                "success": True,
                "result": {
                    "photo_count": 0,
                    "date_range": {},
                    "observed_at": "2026-07-03T00:00:00+00:00",
                    "connection_status": "unavailable",
                    "limitations": ["Authorization: Bearer dummy-secret-value"],
                },
            },
        ):
            response = await main.photo_recent_summary(days=30, limit=20)

        serialized = response.model_dump_json()
        self.assertNotIn("dummy-secret-value", serialized)
        self.assertEqual(response.connection_status, "unavailable")


if __name__ == "__main__":
    unittest.main()
