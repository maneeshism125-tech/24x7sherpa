from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_api_health() -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_root_serves_something() -> None:
    r = client.get("/")
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    if "application/json" in ct:
        assert "message" in r.json()
    else:
        assert "text/html" in ct or "html" in ct
