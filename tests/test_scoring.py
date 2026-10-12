"""Scoring + submission API: server-side points, idempotent awards, attempt
limits, and that no answer key leaks through meta/events."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.session import SessionStore


@pytest.fixture
def client():
    return TestClient(app)


def _submit(client, task_id, answer, sid="pytest-session"):
    return client.post(
        f"/api/tasks/{task_id}/submit",
        json={"answer": answer},
        headers={"X-Session-Id": sid},
    )


def test_max_score_is_derived_and_30():
    store = SessionStore()
    assert store._max_score == 30
    assert store._total_tasks == 15


@pytest.mark.requires_ground_truth
def test_correct_submission_awards_points(client):
    r = _submit(client, "S1-T1", "/var/log/auth.log", sid="s-award")
    body = r.json()
    assert r.status_code == 200
    assert body["correct"] is True
    assert body["points_awarded"] == 2
    assert body["score"] == 2
    assert body["progress"] == {"completed": 1, "total": 15}


@pytest.mark.requires_ground_truth
def test_points_awarded_once_per_task(client):
    _submit(client, "S1-T1", "/var/log/auth.log", sid="s-dup")
    r = _submit(client, "S1-T1", "/var/log/auth.log", sid="s-dup")
    body = r.json()
    assert body["already_solved"] is True
    assert body["score"] == 2  # not 4


@pytest.mark.requires_ground_truth
def test_wrong_answer_scores_zero(client):
    r = _submit(client, "S1-T1", "/var/log/wrong", sid="s-wrong")
    body = r.json()
    assert body["correct"] is False
    assert body["score"] == 0


@pytest.mark.requires_ground_truth
def test_completing_all_tasks_reaches_30(client):
    sid = "s-complete"
    answers = {
        "S1-T1": "/var/log/auth.log", "S1-T2": "Failed password", "S1-T3": "203.0.113.77",
        "S1-T4": "admin", "S1-T5": "4", "S1-T6": "10",
        "S1-T7": "2026-10-11T02:10:05Z", "S1-T8": "2026-10-11T02:18:30Z",
        "S2-T1": "203.0.113.77", "S2-T2": "single_account_guessing",
        "S2-T3": {"choice": "yes", "evidence": "EVT-0019"}, "S2-T4": "admin",
        "S2-T5": {"order": ["EVT-0009", "EVT-0018", "EVT-0019"]},
        "S2-T6": "high", "S2-T7": "escalate",
    }
    last = None
    for tid, ans in answers.items():
        last = _submit(client, tid, ans, sid=sid).json()
    assert last["score"] == 30
    assert last["status"] == "completed"
    assert last["progress"] == {"completed": 15, "total": 15}


@pytest.mark.requires_ground_truth
def test_attempt_limit_enforced(client):
    sid = "s-limit"
    for _ in range(10):
        _submit(client, "S1-T1", "/var/log/wrong", sid=sid)
    r = _submit(client, "S1-T1", "/var/log/wrong", sid=sid)
    assert r.status_code == 429


@pytest.mark.requires_ground_truth
def test_malformed_answer_is_422(client):
    r = _submit(client, "S1-T5", "four", sid="s-malformed")
    assert r.status_code == 422


def test_unknown_task_is_404(client):
    r = _submit(client, "S9-T9", "x", sid="s-unknown")
    assert r.status_code == 404


@pytest.mark.requires_ground_truth
def test_reset_clears_progress(client):
    sid = "s-reset"
    _submit(client, "S1-T1", "/var/log/auth.log", sid=sid)
    client.post("/api/session/reset", headers={"X-Session-Id": sid})
    s = client.get("/api/session", headers={"X-Session-Id": sid}).json()
    assert s["score"] == 0
    assert s["progress"]["completed"] == 0


def test_index_page_renders(client):
    # Guards the Starlette TemplateResponse(request, name, context) signature.
    r = client.get("/")
    assert r.status_code == 200
    assert "Linux SSH Brute Force Investigation" in r.text
    assert "/static/app.js" in r.text


def test_meta_and_events_do_not_leak_answers(client):
    for path in ("/api/meta", "/api/events"):
        text = client.get(path).text
        assert "/var/log/auth.log" not in text  # the S1-T1 answer
        assert "expected" not in text
