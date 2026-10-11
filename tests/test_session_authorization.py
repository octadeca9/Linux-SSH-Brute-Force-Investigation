"""Session isolation and viewer-only mode.

The dev baseline keys sessions off X-Session-Id (the gateway owns ownership in
prod). We assert that distinct session ids keep separate score state, and that
viewer-only mode exposes no task/scoring surface or ground truth.
"""
import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _submit(client, task_id, answer, sid):
    return client.post(
        f"/api/tasks/{task_id}/submit",
        json={"answer": answer},
        headers={"X-Session-Id": sid},
    )


@pytest.mark.requires_ground_truth
def test_sessions_do_not_share_score(client):
    _submit(client, "S1-T1", "/var/log/auth.log", sid="user-a")
    a = client.get("/api/session", headers={"X-Session-Id": "user-a"}).json()
    b = client.get("/api/session", headers={"X-Session-Id": "user-b"}).json()
    assert a["score"] == 2
    assert b["score"] == 0  # user-b sees none of user-a's progress


@pytest.mark.requires_ground_truth
def test_reset_only_affects_own_session(client):
    _submit(client, "S1-T1", "/var/log/auth.log", sid="owner-x")
    _submit(client, "S1-T1", "/var/log/auth.log", sid="owner-y")
    client.post("/api/session/reset", headers={"X-Session-Id": "owner-x"})
    y = client.get("/api/session", headers={"X-Session-Id": "owner-y"}).json()
    assert y["score"] == 2  # unaffected by owner-x reset


def test_viewer_only_mode_hides_tasks(monkeypatch):
    """With TASKS_ENABLED=false the app must not load ground truth or expose
    task/submission/session endpoints."""
    monkeypatch.setenv("TASKS_ENABLED", "false")
    # Force a clean re-import so config + app pick up the env change.
    import app.config as config_mod
    importlib.reload(config_mod)
    import app.main as main_mod
    importlib.reload(main_mod)
    try:
        c = TestClient(main_mod.app)

        meta = c.get("/api/meta").json()
        assert meta["tasks_enabled"] is False
        assert meta["tasks"] == []
        assert meta["max_score"] == 0

        # Viewer dataset still served.
        assert c.get("/api/events").json()["count"] > 0

        # Task/scoring surface is gone.
        assert c.get("/api/session").status_code == 404
        assert c.post("/api/session/reset").status_code == 404
        assert c.post("/api/tasks/S1-T1/submit", json={"answer": "x"}).status_code == 404

        # readyz reports viewer-only and does not require ground truth.
        rz = c.get("/readyz").json()
        assert rz["mode"] == "viewer-only"
    finally:
        monkeypatch.delenv("TASKS_ENABLED", raising=False)
        importlib.reload(config_mod)
        importlib.reload(main_mod)
