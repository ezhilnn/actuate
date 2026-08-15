"""Console API token. Localhost health may reveal it once so the UI can store it."""

from __future__ import annotations

import os
import secrets
from typing import Any

TOKEN_KEY = "console_auth"


def auth_enabled() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return os.environ.get("ACTUATE_AUTH") == "1"
    return os.environ.get("ACTUATE_AUTH", "1") != "0"


def public_path(path: str) -> bool:
    if path in {"/api/health", "/api/auth/login", "/openapi.json", "/docs", "/redoc", "/favicon.ico"}:
        return True
    if path.startswith("/assets/") or path == "/" or path.endswith((".js", ".css", ".png", ".svg", ".ico", ".html")):
        return True
    return False


async def ensure_token(store: Any) -> str:
    env = os.environ.get("ACTUATE_API_TOKEN", "").strip()
    if env:
        return env
    keys = await store.get_keys()
    existing = (keys.get(TOKEN_KEY) or "").strip()
    if existing:
        return existing
    token = secrets.token_urlsafe(32)
    await store.put_key(TOKEN_KEY, token)
    return token


def token_ok(provided: str | None, expected: str) -> bool:
    if not expected:
        return True
    return bool(provided) and secrets.compare_digest(provided, expected)
