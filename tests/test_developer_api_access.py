import unittest
from unittest.mock import AsyncMock, patch

import httpx

from backend import main


class DeveloperApiAccessTest(unittest.IsolatedAsyncioTestCase):
    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
    ) -> httpx.Response:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.request(method, path, json=json)

    async def test_developer_api_is_available_without_authentication(self) -> None:
        with patch.object(main.codex_api, "start_codex", new=AsyncMock()) as start:
            response = await self.request("POST", "/api/run", json={"prompt": "test"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        start.assert_awaited_once()

    async def test_developer_operations_reach_existing_handlers(self) -> None:
        with (
            patch.object(main, "git_changes", new=AsyncMock(return_value={"status_text": "", "files": []})) as changes,
            patch.object(main, "schedule_restart", new=AsyncMock(return_value={"ok": True, "output": "scheduled"})) as restart,
        ):
            changes_response = await self.request("GET", "/api/changes")
            restart_response = await self.request("POST", "/api/service/restart")

        self.assertEqual(changes_response.status_code, 200)
        self.assertEqual(restart_response.status_code, 200)
        changes.assert_awaited_once()
        restart.assert_awaited_once()

    async def test_log_response_redacts_common_secrets(self) -> None:
        raw_lines = [
            "Authorization: Bearer dummy-authorization-value",  # test fixture
            "api_key=dummy-api-value",  # test fixture
        ]
        with (
            patch.object(main.codex_api, "logs", return_value=raw_lines),
            patch.object(main.codex_api, "returncode", return_value=0),
            patch.object(main.codex_api, "is_running", return_value=False),
            patch.object(main.codex_api, "current_status", return_value="succeeded"),
        ):
            response = await self.request("GET", "/api/logs")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("dummy-authorization-value", response.text)
        self.assertNotIn("dummy-api-value", response.text)
        self.assertIn("[REDACTED]", response.text)


if __name__ == "__main__":
    unittest.main()
