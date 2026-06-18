#!/usr/bin/env python3
"""Check Runtime API behavior through the FastAPI ASGI app.

This script uses the Runtime execution path only. Weather is executed through
the deterministic local WeatherExecutor, and high-risk developer tools remain
stubbed behind permission and confirmation checks.
"""

import asyncio
import json
from pathlib import Path
import sys
import tempfile
from typing import Any
from urllib.parse import urlsplit


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.audit import AuditLogger  # noqa: E402
from backend.main import app  # noqa: E402
import backend.main as main_module  # noqa: E402
from backend.runtime import RuntimeService  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def request_json(
    method: str, target: str, payload: dict[str, Any] | None = None
) -> tuple[int, dict[str, Any]]:
    body = b"" if payload is None else json.dumps(payload).encode("utf-8")
    split = urlsplit(target)
    headers = [
        (b"host", b"testserver"),
        (b"content-length", str(len(body)).encode("ascii")),
    ]
    if payload is not None:
        headers.append((b"content-type", b"application/json"))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": split.path,
        "raw_path": split.path.encode("ascii"),
        "query_string": split.query.encode("ascii"),
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }

    sent_request = False
    status_code: int | None = None
    response_body = bytearray()

    async def receive() -> dict[str, Any]:
        nonlocal sent_request
        if sent_request:
            return {"type": "http.disconnect"}
        sent_request = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        nonlocal status_code
        if message["type"] == "http.response.start":
            status_code = message["status"]
        elif message["type"] == "http.response.body":
            response_body.extend(message.get("body", b""))

    await app(scope, receive, send)
    assert_true(status_code is not None, "ASGI app did not return a response")
    data = json.loads(response_body.decode("utf-8"))
    return status_code, data


async def post_execute(payload: dict[str, Any]) -> dict[str, Any]:
    status_code, data = await request_json("POST", "/api/runtime/execute", payload)
    assert_true(status_code == 200, json.dumps(data, ensure_ascii=False))
    return data


async def run_checks() -> None:
    with tempfile.TemporaryDirectory(prefix="jarvis-runtime-audit-") as tmp_dir:
        audit_path = Path(tmp_dir) / "audit.log"
        main_module.runtime_service = RuntimeService(
            audit_logger=AuditLogger(audit_path)
        )

        status_code, tool_response = await request_json(
            "GET", "/api/runtime/tool/get_forecast"
        )
        assert_true(status_code == 200, json.dumps(tool_response, ensure_ascii=False))
        assert_true(tool_response["id"] == "get_forecast", "app import failed")

        forecast = await post_execute(
            {
                "tool_id": "get_forecast",
                "params": {"location": "Okayama", "days": 3},
                "role": "guest",
                "confirmed": False,
            },
        )
        assert_true(forecast["success"] is True, "get_forecast guest should succeed")
        assert_true(
            forecast["execution_mode"] == "local_weather_stub",
            "get_forecast must use WeatherExecutor",
        )
        assert_true(
            forecast["result"]["source"] == "local_weather_stub",
            "get_forecast result source must be local_weather_stub",
        )
        assert_true(
            len(forecast["result"]["forecast"]) == 3,
            "get_forecast should honor days in local stub",
        )

        guest_restart = await post_execute(
            {
                "tool_id": "restart_service",
                "params": {},
                "role": "guest",
                "confirmed": True,
            },
        )
        assert_true(
            guest_restart["permission_denied"] is True,
            "restart_service guest should be permission_denied",
        )
        assert_true(guest_restart["blocked"] is True, "guest restart should be blocked")

        admin_unconfirmed = await post_execute(
            {
                "tool_id": "restart_service",
                "params": {},
                "role": "admin",
                "confirmed": False,
            },
        )
        assert_true(
            admin_unconfirmed["confirmation_required"] is True,
            "admin restart without confirmation should require confirmation",
        )
        assert_true(
            admin_unconfirmed["blocked"] is True,
            "admin restart without confirmation should be blocked",
        )
        assert_true(
            admin_unconfirmed["permission_denied"] is False,
            "admin restart without confirmation should not be permission_denied",
        )

        admin_confirmed = await post_execute(
            {
                "tool_id": "restart_service",
                "params": {},
                "role": "admin",
                "confirmed": True,
            },
        )
        assert_true(admin_confirmed["success"] is True, "admin restart should succeed")
        assert_true(
            admin_confirmed["execution_mode"] == "stub",
            "admin restart must be stub execution",
        )
        assert_true(
            admin_confirmed["result"]["message"] == "stub execution",
            "admin restart should return stub success",
        )

        status_code, audit_response = await request_json("GET", "/api/audit?limit=10")
        assert_true(status_code == 200, json.dumps(audit_response, ensure_ascii=False))
        audit_items = audit_response["items"]
        assert_true(len(audit_items) >= 4, "audit log should contain runtime events")

        audit_event_types = {item["event_type"] for item in audit_items}
        assert_true(
            "runtime.permission_denied" in audit_event_types,
            "audit log should include permission_denied",
        )
        assert_true(
            "runtime.confirmation_blocked" in audit_event_types,
            "audit log should include confirmation_blocked",
        )
        assert_true(
            "runtime.execute_stub" in audit_event_types,
            "audit log should include execute_stub",
        )
        weather_audits = [
            item
            for item in audit_items
            if item.get("tool_id") == "get_forecast"
            and item.get("execution_mode") == "local_weather_stub"
        ]
        assert_true(
            bool(weather_audits),
            "audit log should include local_weather_stub execution",
        )

    print("Runtime API check passed")


if __name__ == "__main__":
    asyncio.run(run_checks())
