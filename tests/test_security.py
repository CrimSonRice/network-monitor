"""
Security tests: auth, sanitization, rate limit behavior, headers.
"""

import pytest
from fastapi.testclient import TestClient

from core.security import sanitize_string, verify_token, create_access_token


def test_jwt_create_and_verify() -> None:
    token = create_access_token("user-123")
    assert token
    payload = verify_token(token)
    assert payload is not None
    assert payload.get("sub") == "user-123"
    assert "exp" in payload


def test_jwt_invalid_returns_none() -> None:
    assert verify_token("invalid") is None
    assert verify_token("") is None
    assert verify_token("eyJhbGciOiJIUzI1NiJ9.e30.wrong") is None


def test_sanitize_removes_unsafe() -> None:
    assert "<script>" not in sanitize_string("<script>alert(1)</script>")
    assert "SELECT" not in sanitize_string("x SELECT * FROM users")
    assert sanitize_string("  ok  ") == "ok"


def test_sanitize_max_length() -> None:
    long_str = "a" * 1000
    assert len(sanitize_string(long_str, max_length=10)) <= 10


def test_secure_headers(client: TestClient) -> None:
    r = client.get("/health")
    assert "X-XSS-Protection" in r.headers
    assert "Referrer-Policy" in r.headers


def test_openapi_available(client: TestClient) -> None:
    """OpenAPI schema should be available for docs and codegen."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    data = r.json()
    assert "paths" in data
    assert "/health" in data["paths"]
