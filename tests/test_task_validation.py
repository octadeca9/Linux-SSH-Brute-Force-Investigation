"""Per-validator behaviour: correct answers pass, wrong answers fail without
leaking, and malformed answers raise ValidationError."""
import pytest

from app.services import validator
from app.services.loaders import load_ground_truth, load_tasks

# Every test here calls validator.validate(), which loads the answer key.
pytestmark = pytest.mark.requires_ground_truth


def test_all_public_tasks_have_ground_truth():
    gt = load_ground_truth()["tasks"]
    for t in load_tasks():
        assert t["id"] in gt, f"{t['id']} has no ground truth"
        assert gt[t["id"]]["validator_type"] == t["validator_type"]


# --- correct answers ---------------------------------------------------------

@pytest.mark.parametrize("task_id,answer", [
    ("S1-T1", "/var/log/auth.log"),
    ("S1-T2", "Failed password"),
    ("S1-T3", "203.0.113.77"),
    ("S1-T4", "admin"),
    ("S1-T5", "4"),
    ("S1-T6", "10"),
    ("S1-T7", "2026-10-11T02:10:05Z"),
    ("S1-T8", "2026-10-11T02:18:30Z"),
    ("S2-T1", "203.0.113.77"),
    ("S2-T2", "single_account_guessing"),
    ("S2-T3", {"choice": "yes", "evidence": "EVT-0019"}),
    ("S2-T4", "admin"),
    ("S2-T5", {"order": ["EVT-0009", "EVT-0018", "EVT-0019"]}),
    ("S2-T6", "high"),
    ("S2-T7", "escalate"),
])
def test_correct_answers_pass(task_id, answer):
    assert validator.validate(task_id, answer).correct is True


# --- normalization tolerance -------------------------------------------------

def test_normalized_string_case_insensitive():
    assert validator.validate("S1-T4", "  ADMIN ").correct is True


def test_ip_match_canonical_not_substring():
    assert validator.validate("S1-T3", " 203.0.113.77 ").correct is True
    assert validator.validate("S1-T3", "203.0.113.7").correct is False


def test_timestamp_offset_equivalent_to_z():
    assert validator.validate("S1-T7", "2026-10-11T02:10:05+00:00").correct is True


def test_ordered_events_accepts_list_and_is_order_sensitive():
    assert validator.validate("S2-T5", ["EVT-0009", "EVT-0018", "EVT-0019"]).correct is True
    assert validator.validate("S2-T5", ["EVT-0018", "EVT-0009", "EVT-0019"]).correct is False


def test_structured_choice_bare_string_accepted():
    assert validator.validate("S2-T7", "escalate").correct is True


# --- wrong answers fail (and never reveal the expected value) ----------------

@pytest.mark.parametrize("task_id,answer", [
    ("S1-T1", "/var/log/syslog"),
    ("S1-T5", "3"),
    ("S1-T6", "9"),
    ("S1-T7", "2026-10-11T02:10:06Z"),
    ("S2-T2", "multi_account_probing"),
    ("S2-T6", "low"),
    ("S2-T7", "monitor"),
])
def test_wrong_answers_fail_without_leak(task_id, answer):
    res = validator.validate(task_id, answer)
    assert res.correct is False
    gt = load_ground_truth()["tasks"][task_id]
    expected = str(gt.get("expected") or gt.get("expected_choice") or gt.get("expected_order"))
    assert expected not in res.message


def test_structured_choice_requires_valid_evidence():
    # correct choice, wrong evidence -> incorrect, not an error
    assert validator.validate("S2-T3", {"choice": "yes", "evidence": "EVT-0001"}).correct is False


# --- malformed answers raise ValidationError ---------------------------------

def test_integer_match_rejects_non_integer():
    with pytest.raises(validator.ValidationError):
        validator.validate("S1-T5", "four")


def test_ip_match_rejects_bad_ip():
    with pytest.raises(validator.ValidationError):
        validator.validate("S1-T3", "not-an-ip")


def test_timestamp_rejects_naive():
    with pytest.raises(validator.ValidationError):
        validator.validate("S1-T7", "2026-10-11 02:10:05")


def test_structured_choice_rejects_out_of_enum():
    with pytest.raises(validator.ValidationError):
        validator.validate("S2-T7", "ignore")


def test_structured_choice_requires_evidence_when_configured():
    with pytest.raises(validator.ValidationError):
        validator.validate("S2-T3", {"choice": "yes"})


def test_ordered_events_wrong_length_raises():
    with pytest.raises(validator.ValidationError):
        validator.validate("S2-T5", ["EVT-0009", "EVT-0018"])
