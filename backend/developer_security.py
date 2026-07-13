import hmac
import os

from fastapi import Header, HTTPException


ENABLE_ENV = "JARVIS_ENABLE_DEVELOPER_API"
TOKEN_ENV = "JARVIS_DEVELOPER_TOKEN"
_ENABLED_VALUES = {"1", "true", "yes", "on"}


def developer_api_enabled() -> bool:
    return os.environ.get(ENABLE_ENV, "").strip().lower() in _ENABLED_VALUES


def developer_token() -> str:
    return os.environ.get(TOKEN_ENV, "").strip()


async def require_developer_api(
    authorization: str | None = Header(default=None),
) -> None:
    """Fail closed before any Developer endpoint handler is entered."""
    if not developer_api_enabled():
        raise HTTPException(status_code=404, detail="Developer API is disabled")

    expected = developer_token()
    if not expected:
        raise HTTPException(status_code=503, detail="Developer API is unavailable")

    scheme, separator, supplied = (authorization or "").partition(" ")
    if (
        not separator
        or scheme.lower() != "bearer"
        or not supplied
        or not hmac.compare_digest(supplied, expected)
    ):
        raise HTTPException(
            status_code=401,
            detail="Developer authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


def redact_developer_token(value: str) -> str:
    secret = developer_token()
    if not secret:
        return value
    return value.replace(secret, "[REDACTED]")
