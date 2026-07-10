import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend import codex_api
from backend.main import new_developer_session


class CodexSessionManagerTest(unittest.TestCase):
    def test_new_run_captures_session_then_resume_uses_explicit_id(self):
        manager = codex_api.CodexSessionManager()

        command, is_resume = manager.command("first prompt")
        self.assertFalse(is_resume)
        self.assertEqual(command[-1], "first prompt")
        self.assertNotIn("resume", command)

        session_id = "019c1234-1234-7000-8000-123456789abc"
        manager.capture(f"session id: {session_id}\n")
        command, is_resume = manager.command("follow-up")

        self.assertTrue(is_resume)
        self.assertEqual(command[-3:], ["resume", session_id, "follow-up"])
        self.assertNotIn("--last", command)

    def test_reset_discards_current_session(self):
        manager = codex_api.CodexSessionManager(session_id="019c1234-1234-7000-8000-123456789abc")
        manager.reset()

        command, is_resume = manager.command("new prompt")
        self.assertFalse(is_resume)
        self.assertNotIn("resume", command)


class DeveloperSessionApiTest(unittest.IsolatedAsyncioTestCase):
    async def test_new_session_endpoint_resets_process_local_session(self):
        with patch("backend.main.codex_api.reset_session") as reset_session:
            response = await new_developer_session()

        self.assertEqual(response.status, "new_session")
        reset_session.assert_called_once_with()

    async def test_new_session_endpoint_rejects_reset_while_running(self):
        with patch(
            "backend.main.codex_api.reset_session",
            side_effect=RuntimeError("Codex is already running."),
        ):
            with self.assertRaises(HTTPException) as raised:
                await new_developer_session()

        self.assertEqual(raised.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
