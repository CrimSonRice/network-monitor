"""
Load testing placeholder. Use locust, k6, or artillery for real load tests.
This file documents the pattern and a minimal smoke check.
"""

import pytest
from fastapi.testclient import TestClient


def test_health_endpoint_low_latency(client: TestClient) -> None:
    """
    Smoke check: health should respond quickly.
    Real load: run locust/k6 against /health and /api/v1/monitor/status.
    """
    import time

    start = time.perf_counter()
    r = client.get("/health")
    elapsed = time.perf_counter() - start
    assert r.status_code == 200
    assert elapsed < 1.0, "Health check should complete under 1s locally"


# Example locust file location: tests/locustfile.py
# Example k6 script: tests/load/k6_health.js
# Run: locust -f tests/locustfile.py --host=http://localhost:8000
