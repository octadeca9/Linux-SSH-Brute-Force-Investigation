"""Server-side answer validation. Ground truth never leaves this module.

Each validator returns a ValidationResult. On an incorrect answer the message
must NOT reveal the expected value.
"""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from app.services.loaders import load_ground_truth


@dataclass
class ValidationResult:
    correct: bool
    message: str


class ValidationError(ValueError):
    """Raised when the submitted answer is malformed (bad type/shape)."""


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def _parse_ts(value: str) -> datetime:
    raw = _norm(value)
    if not raw:
        raise ValidationError("empty timestamp")
    # Accept trailing Z as UTC.
    candidate = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
    try:
        dt = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValidationError("timestamp is not valid ISO 8601") from exc
    if dt.tzinfo is None:
        raise ValidationError("timestamp must include a timezone (use ...Z)")
    return dt.astimezone(timezone.utc)


# --- per-type validators --------------------------------------------------

def _v_exact_match(spec: dict, answer) -> ValidationResult:
    submitted = _norm(answer)
    accepted = {_norm(a) for a in spec.get("accepted", [spec["expected"]])}
    ok = submitted in accepted
    return ValidationResult(ok, "Correct." if ok else "That value is not correct.")


def _v_normalized_string(spec: dict, answer) -> ValidationResult:
    submitted = _norm(answer).lower()
    accepted = {_norm(a).lower() for a in spec.get("accepted", [spec["expected"]])}
    ok = submitted in accepted
    return ValidationResult(ok, "Correct." if ok else "That value is not correct.")


def _v_ip_match(spec: dict, answer) -> ValidationResult:
    try:
        submitted = ipaddress.ip_address(_norm(answer))
    except ValueError as exc:
        raise ValidationError("not a valid IP address") from exc
    expected = ipaddress.ip_address(_norm(spec["expected"]))
    ok = submitted == expected
    return ValidationResult(ok, "Correct." if ok else "That source IP is not correct.")


def _v_integer_match(spec: dict, answer) -> ValidationResult:
    try:
        submitted = int(_norm(answer))
    except (ValueError, TypeError) as exc:
        raise ValidationError("answer must be an integer") from exc
    ok = submitted == int(spec["expected"])
    return ValidationResult(ok, "Correct." if ok else "That count is not correct.")


def _v_timestamp_match(spec: dict, answer) -> ValidationResult:
    ok = _parse_ts(answer) == _parse_ts(spec["expected"])
    return ValidationResult(ok, "Correct." if ok else "That timestamp does not match.")


def _v_structured_choice(spec: dict, answer) -> ValidationResult:
    # Accept either a bare choice string or a structured object with evidence.
    if isinstance(answer, dict):
        choice = _norm(answer.get("choice", "")).lower()
        evidence = _norm(answer.get("evidence", "")).lower()
    else:
        choice = _norm(answer).lower()
        evidence = ""

    valid_choices = {c.lower() for c in spec["choices"]}
    if choice not in valid_choices:
        raise ValidationError("choice not in allowed options")

    checks = [choice == _norm(spec["expected_choice"]).lower()]

    if spec.get("require_evidence"):
        if not evidence:
            raise ValidationError("evidence is required")
        accepted = {_norm(e).lower() for e in spec.get("evidence_accepted", [])}
        checks.append(evidence in accepted)

    ok = all(checks)
    return ValidationResult(ok, "Correct." if ok else "Choice or supporting evidence is not correct.")


def _v_ordered_events(spec: dict, answer) -> ValidationResult:
    if isinstance(answer, dict):
        answer = answer.get("order")
    if not isinstance(answer, (list, tuple)):
        raise ValidationError("answer must be an ordered list of event_ref values")
    submitted = [_norm(x).upper() for x in answer]
    expected = [_norm(x).upper() for x in spec["expected_order"]]
    if len(submitted) != len(expected):
        raise ValidationError(f"expected {len(expected)} event references")
    ok = submitted == expected
    return ValidationResult(ok, "Correct." if ok else "The event ordering is not correct.")


_DISPATCH = {
    "exact_match": _v_exact_match,
    "normalized_string": _v_normalized_string,
    "ip_match": _v_ip_match,
    "integer_match": _v_integer_match,
    "timestamp_match": _v_timestamp_match,
    "structured_choice": _v_structured_choice,
    "ordered_events": _v_ordered_events,
}


def validate(task_id: str, answer) -> ValidationResult:
    gt = load_ground_truth()
    spec = gt.get("tasks", {}).get(task_id)
    if spec is None:
        raise ValidationError(f"unknown task {task_id}")
    validator = _DISPATCH.get(spec["validator_type"])
    if validator is None:
        raise ValidationError(f"no validator for {spec['validator_type']}")
    return validator(spec, answer)


def max_attempts(task_id: str) -> int:
    gt = load_ground_truth()
    return int(gt.get("tasks", {}).get(task_id, {}).get("max_attempts", 10))
