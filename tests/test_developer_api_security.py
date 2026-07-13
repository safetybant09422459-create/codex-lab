import os
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from backend import main


class DeveloperApiSecurityTest(unittest.IsolatedAsyncioTestCase):
    async def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json: dict | None = None,
    ) -> httpx.Response:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.request(method, path, headers=headers, json=json)

    async def test_developer_api_is_disabled_by_default(self) -> None:
        with patch.dict(
            os.environ,
            {"JARVIS_ENABLE_DEVELOPER_API": "", "JARVIS_DEVELOPER_TOKEN": ""},
        ):
            response = await self.request("POST", "/api/run", json={"prompt": "test"})

        self.assertEqual(response.status_code, 404)

    async def test_invalid_credentials_do_not_start_codex_git_or_service(self) -> None:
        environment = {
            "JARVIS_ENABLE_DEVELOPER_API": "true",
            "JARVIS_DEVELOPER_TOKEN": "dummy-developer-value",
        }
        with (
            patch.dict(os.environ, environment),
            patch.object(main.codex_api, "start_codex", new=AsyncMock()) as start,
            patch.object(main, "git_changes", new=AsyncMock()) as changes,
            patch.object(main, "schedule_restart", new=AsyncMock()) as restart,
        ):
            responses = [
                await self.request(
                    "POST", "/api/run", token="wrong-value", json={"prompt": "test"}
                ),
                await self.request("GET", "/api/changes", token="wrong-value"),
                await self.request("POST", "/api/service/restart", token="wrong-value"),
            ]

        self.assertTrue(all(response.status_code == 401 for response in responses))
        start.assert_not_awaited()
        changes.assert_not_awaited()
        restart.assert_not_awaited()

    async def test_query_parameter_is_not_accepted_as_authentication(self) -> None:
        with patch.dict(
            os.environ,
            {
                "JARVIS_ENABLE_DEVELOPER_API": "true",
                "JARVIS_DEVELOPER_TOKEN": "dummy-developer-value",
            },
        ):
            response = await self.request(
                "GET", "/api/project?token=dummy-developer-value"
            )

        self.assertEqual(response.status_code, 401)

    async def test_correct_configuration_and_token_reach_existing_handler(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "JARVIS_ENABLE_DEVELOPER_API": "true",
                    "JARVIS_DEVELOPER_TOKEN": "dummy-developer-value",
                },
            ),
            patch.object(main.codex_api, "start_codex", new=AsyncMock()) as start,
        ):
            response = await self.request(
                "POST",
                "/api/run",
                token="dummy-developer-value",
                json={"prompt": "test"},
            )

        self.assertEqual(response.status_code, 200)
        start.assert_awaited_once()

    async def test_log_response_redacts_common_secrets_and_developer_token(self) -> None:
        raw_lines = [
            "Authorization: Bearer dummy-authorization-value",  # test fixture
            "api_key=dummy-api-value",  # test fixture
            "developer value: dummy-developer-value",
        ]
        with (
            patch.dict(
                os.environ,
                {
                    "JARVIS_ENABLE_DEVELOPER_API": "true",
                    "JARVIS_DEVELOPER_TOKEN": "dummy-developer-value",
                },
            ),
            patch.object(main.codex_api, "logs", return_value=raw_lines),
            patch.object(main.codex_api, "returncode", return_value=0),
            patch.object(main.codex_api, "is_running", return_value=False),
            patch.object(main.codex_api, "current_status", return_value="succeeded"),
        ):
            response = await self.request(
                "GET", "/api/logs", token="dummy-developer-value"
            )

        body = response.text
        self.assertEqual(response.status_code, 200)
        for secret in (
            "dummy-authorization-value",
            "dummy-api-value",
            "dummy-developer-value",
        ):
            self.assertNotIn(secret, body)
        self.assertIn("[REDACTED]", body)

    async def test_consumer_read_apis_do_not_require_developer_auth(self) -> None:
        with patch.dict(
            os.environ,
            {"JARVIS_ENABLE_DEVELOPER_API": "", "JARVIS_DEVELOPER_TOKEN": ""},
        ):
            travel = await self.request("GET", "/api/travel/trips")
            catalog = await self.request("GET", "/api/providers/operations")
            with patch.object(
                main.photo_repository,
                "get_thumbnail",
                return_value=(b"image", "image/jpeg"),
            ):
                photo = await self.request("GET", "/api/photo/assets/asset-1/thumbnail")

        self.assertEqual(travel.status_code, 200)
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual(photo.status_code, 200)


if __name__ == "__main__":
    unittest.main()
