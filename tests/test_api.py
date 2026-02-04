"""
API response and contract tests.
"""

import pytest
from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "network-monitor" in data.get("service", "")


def test_health_ready(client: TestClient) -> None:
    r = client.get("/health/ready")
    assert r.status_code == 200
    data = r.json()
    assert data["ready"] is True
    assert "checks" in data


def test_health_live(client: TestClient) -> None:
    r = client.get("/health/live")
    assert r.status_code == 200


def test_secure_headers_present(client: TestClient) -> None:
    r = client.get("/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"


def test_monitor_status(client: TestClient) -> None:
    r = client.get("/api/v1/monitor/status")
    assert r.status_code == 200
    data = r.json()
    assert "cpu_percent" in data
    assert "memory" in data
    assert "disk" in data


def test_monitor_check_validation(client: TestClient) -> None:
    # Missing body
    r = client.post("/api/v1/monitor/check", json={})
    assert r.status_code == 422
    # Valid body
    r = client.post("/api/v1/monitor/check", json={"host": "127.0.0.1", "timeout_seconds": 2})
    assert r.status_code == 200
    data = r.json()
    assert "host" in data
    assert "reachable" in data


def test_monitor_stats_query_validation(client: TestClient) -> None:
    r = client.get("/api/v1/monitor/stats?limit=50")
    assert r.status_code == 200
    assert r.json().get("limit") == 50
    # Out of range
    r = client.get("/api/v1/monitor/stats?limit=1000")
    assert r.status_code == 422
