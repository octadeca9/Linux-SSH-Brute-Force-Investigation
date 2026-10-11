"""Dataset integrity: schema, UTC timestamps, unique refs, doc-range IPs, and
that the ground truth is recomputable from the dataset (no hard-coded drift)."""
import ipaddress
from collections import Counter
from datetime import datetime, timezone

import pytest

from app.services.loaders import load_dataset, load_ground_truth

REQUIRED = {"timestamp", "host", "program", "event_type", "username", "message", "event_ref"}
ALLOWED_TYPES = {
    "failed_password", "invalid_user", "accepted_password", "accepted_publickey",
    "connection_closed", "session_opened", "session_closed",
}
DOC_NETS = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]


@pytest.fixture(scope="module")
def events():
    return load_dataset()["events"]


def _parse(ts):
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    assert dt.tzinfo is not None
    return dt.astimezone(timezone.utc)


def test_required_fields_present(events):
    for e in events:
        assert REQUIRED <= set(e), f"{e.get('event_ref')} missing fields"


def test_event_types_allowed(events):
    for e in events:
        assert e["event_type"] in ALLOWED_TYPES, e["event_type"]


def test_timestamps_are_utc_iso8601(events):
    for e in events:
        assert e["timestamp"].endswith("Z"), e["event_ref"]
        _parse(e["timestamp"])


def test_event_refs_unique(events):
    refs = [e["event_ref"] for e in events]
    assert len(refs) == len(set(refs))


def test_source_ips_are_documentation_range(events):
    for e in events:
        ip = e.get("source_ip")
        if not ip:
            continue
        addr = ipaddress.ip_address(ip)
        assert any(addr in net for net in DOC_NETS), f"{ip} not in documentation range"


# --- ground truth must match what the dataset actually contains --------------

@pytest.mark.requires_ground_truth
def test_gt_invalid_user_count(events):
    gt = load_ground_truth()["tasks"]["S1-T5"]["expected"]
    actual = sum(1 for e in events if e["event_type"] == "invalid_user")
    assert actual == gt


@pytest.mark.requires_ground_truth
def test_gt_target_username_is_most_failed(events):
    counts = Counter(e["username"] for e in events if e["event_type"] == "failed_password")
    top_user = counts.most_common(1)[0][0]
    assert top_user == load_ground_truth()["tasks"]["S1-T4"]["expected"]


@pytest.mark.requires_ground_truth
def test_gt_failed_count_in_window(events):
    gt = load_ground_truth()["tasks"]["S1-T6"]["expected"]
    lo, hi = _parse("2026-10-11T02:10:00Z"), _parse("2026-10-11T02:20:00Z")
    actual = sum(
        1 for e in events
        if e["event_type"] == "failed_password"
        and e["username"] == "admin"
        and e.get("source_ip") == "203.0.113.77"
        and lo <= _parse(e["timestamp"]) <= hi
    )
    assert actual == gt


@pytest.mark.requires_ground_truth
def test_gt_first_last_timestamps(events):
    burst = sorted(
        (e for e in events
         if e["event_type"] == "failed_password"
         and e["username"] == "admin"
         and e.get("source_ip") == "203.0.113.77"),
        key=lambda e: e["timestamp"],
    )
    tasks = load_ground_truth()["tasks"]
    assert _parse(burst[0]["timestamp"]) == _parse(tasks["S1-T7"]["expected"])
    assert _parse(burst[-1]["timestamp"]) == _parse(tasks["S1-T8"]["expected"])


@pytest.mark.requires_ground_truth
def test_gt_top_attacking_ip(events):
    counts = Counter(
        e["source_ip"] for e in events
        if e["event_type"] in ("failed_password", "invalid_user") and e.get("source_ip")
    )
    assert counts.most_common(1)[0][0] == load_ground_truth()["tasks"]["S2-T1"]["expected"]


@pytest.mark.requires_ground_truth
def test_gt_successful_login_evidence_and_account(events):
    gt = load_ground_truth()["tasks"]
    ref = gt["S2-T3"]["evidence_accepted"][0]
    success = next(e for e in events if e["event_ref"] == ref)
    assert success["event_type"].startswith("accepted_")
    assert success["username"] == gt["S2-T4"]["expected"]
    assert success["source_ip"] == gt["S2-T1"]["expected"]


@pytest.mark.requires_ground_truth
def test_gt_timeline_order_is_chronological(events):
    order = load_ground_truth()["tasks"]["S2-T5"]["expected_order"]
    by_ref = {e["event_ref"]: e for e in events}
    times = [_parse(by_ref[r]["timestamp"]) for r in order]
    assert times == sorted(times)
