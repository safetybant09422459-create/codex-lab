import unittest
from unittest.mock import patch

import httpx

from backend import basic_chat, main


class ChatApiTest(unittest.IsolatedAsyncioTestCase):
    async def post_chat(self, payload):
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.post("/api/chat", json=payload)

    async def test_chat_is_tool_free_until_agent_loop_exists(self) -> None:
        with patch.object(
            basic_chat,
            "generate_text_with_timings",
            return_value=("Travel操作は現在Chatから利用できません。", None),
        ):
            response = await self.post_chat({"message": "旅行一覧を見せて"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["action"], "direct_answer")
        self.assertNotIn("tool_id", response.json())
        self.assertNotIn("result", response.json())

    async def test_history_is_bounded(self) -> None:
        response = await self.post_chat(
            {
                "message": "続けて",
                "conversation_history": [
                    {"role": "user", "content": str(index)} for index in range(6)
                ],
            }
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
