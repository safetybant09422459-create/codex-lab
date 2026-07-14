import unittest
from unittest.mock import patch

from backend import main
from backend.models import GiftEntryCreateRequest


class GiftApiTest(unittest.IsolatedAsyncioTestCase):
    async def test_read_api_uses_guest_runtime_boundary(self) -> None:
        with patch.object(
            main.runtime_service,
            "execute_provider_operation",
            return_value={"success": True, "result": {"entries": [], "count": 0}},
        ) as execute:
            response = await main.gift_list_entries(entry_type=None, person=None, year=None)
        execute.assert_called_once_with("gift", "list_gifts", {}, confirmed=False, role="guest")
        self.assertEqual(response.count, 0)

    async def test_write_api_uses_confirmed_runtime_boundary(self) -> None:
        entry = {"id": "dummy-id", "entry_type": "candidate", "title": "本"}
        with patch.object(
            main.runtime_service,
            "execute_provider_operation",
            return_value={"success": True, "result": {"entry": entry}},
        ) as execute:
            response = await main.gift_create_entry(
                GiftEntryCreateRequest(entry_type="candidate", title="本")
            )
        self.assertEqual(response.entry, entry)
        self.assertTrue(execute.call_args.kwargs["confirmed"])
        self.assertEqual(execute.call_args.kwargs["role"], "admin")


if __name__ == "__main__":
    unittest.main()
