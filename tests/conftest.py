"""
Pytest fixtures: test client, overridden settings, auth headers.
"""

import pytest
from fastapi.testclient import TestClient

from main import create_app


@pytest.fixture
def client() -> TestClient:
    """Test client with default app. Use override_dependency for settings/auth."""
    return TestClient(create_app())


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Example auth header for protected routes. Use real token in integration tests."""
    from core.security import create_access_token

    token = create_access_token("test-user-id")
    return {"Authorization": f"Bearer {token}"}
