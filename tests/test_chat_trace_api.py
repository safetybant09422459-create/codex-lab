import unittest

from httpx import ASGITransport, AsyncClient

from backend import main


class ChatTraceApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        main.chat_trace_store.clear()
        main.chat_trace_store.put({
            "trace_version": "1", "turn_id": "turn-api", "session_id": "session",
            "created_at": "2026-07-19T00:00:00+00:00", "completed_at": "2026-07-19T00:00:01+00:00",
            "overall_status": "error", "user_input": {"text": "hello"}, "final_answer": None,
            "environment": {"configured_model": "test-model", "api_key": "dummy-secret"},
            "token_usage": {"total_tokens": 12}, "total_duration_ms": 1000,
            "anomaly_flags": [{"severity": "error", "code": "LLM_REQUEST_FAILED", "stage": "llm_call_1", "message": "failed", "evidence": {}}],
            "stages": {}, "llm_calls": [], "error_category": "provider_request_error", "error_message": "Bearer dummy-token",
        })

    async def request(self, method: str, path: str):
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            return await client.request(method, path)

    async def test_list_detail_bundles_clear_and_no_store(self) -> None:
        listing = await self.request("GET", "/api/developer/chat-traces?limit=1")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.headers["cache-control"], "no-store")
        self.assertEqual(listing.json()[0]["turn_id"], "turn-api")
        detail = await self.request("GET", "/api/developer/chat-traces/turn-api")
        self.assertNotIn("dummy-secret", detail.text)
        self.assertNotIn("dummy-token", detail.text)
        for mode in ("consultation", "full"):
            bundle = await self.request("GET", f"/api/developer/chat-traces/turn-api/bundle?mode={mode}")
            self.assertEqual(bundle.status_code, 200)
            self.assertTrue(bundle.headers["content-type"].startswith("text/plain"))
        cleared = await self.request("DELETE", "/api/developer/chat-traces")
        self.assertEqual(cleared.json()["deleted_count"], 1)

    async def test_404_and_limit_validation(self) -> None:
        self.assertEqual((await self.request("GET", "/api/developer/chat-traces/missing")).status_code, 404)
        self.assertEqual((await self.request("GET", "/api/developer/chat-traces?limit=0")).status_code, 422)


if __name__ == "__main__":
    unittest.main()
