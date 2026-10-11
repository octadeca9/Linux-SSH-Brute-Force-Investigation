"""Load dataset and challenge/task/ground-truth configuration."""
import base64
import binascii
import json
from functools import lru_cache
from pathlib import Path

import yaml

from app import config

# Static dataset metadata surfaced to participants. Kept out of the JSONL so the
# dataset file stays one-event-per-line. dataset_version comes from challenge.yaml.
_TIMEZONE = "UTC"
_NOTICE = (
    "Synthetic SSH authentication log for SOC training. No answer key is "
    "included; all values are documentation-range IPs and fictitious hosts."
)


def _read_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@lru_cache(maxsize=1)
def _load_events() -> list[dict]:
    """Read the participant-visible JSONL dataset (one event per line)."""
    events: list[dict] = []
    with open(config.DATASET_PATH, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on dataset line {lineno}: {exc}") from exc
    return events


def load_dataset() -> dict:
    """Participant-visible dataset envelope. Contains no answer key."""
    return {
        "dataset_version": load_challenge().get("dataset_version"),
        "notice": _NOTICE,
        "timezone": _TIMEZONE,
        "events": _load_events(),
    }


@lru_cache(maxsize=1)
def load_challenge() -> dict:
    return _read_yaml(config.CHALLENGE_CONFIG_PATH)


@lru_cache(maxsize=1)
def load_tasks() -> list[dict]:
    return _read_yaml(config.TASKS_CONFIG_PATH).get("tasks", [])


class GroundTruthNotConfigured(RuntimeError):
    """Raised when no ground-truth source is available."""


@lru_cache(maxsize=1)
def load_ground_truth() -> dict:
    """Server-side only. Never serialize this into any HTTP response.

    Resolved in order: GROUND_TRUTH_B64 -> GROUND_TRUTH_YAML -> file at
    GROUND_TRUTH_PATH. This lets env-only platforms inject the answer key at
    runtime without baking it into the image.
    """
    if config.GROUND_TRUTH_B64:
        try:
            raw = base64.b64decode(config.GROUND_TRUTH_B64, validate=True).decode("utf-8")
        except (binascii.Error, ValueError) as exc:
            raise GroundTruthNotConfigured(
                "GROUND_TRUTH_B64 is set but is not valid base64"
            ) from exc
        return yaml.safe_load(raw)

    if config.GROUND_TRUTH_YAML:
        return yaml.safe_load(config.GROUND_TRUTH_YAML)

    if config.GROUND_TRUTH_PATH.exists():
        return _read_yaml(config.GROUND_TRUTH_PATH)

    raise GroundTruthNotConfigured(
        "No ground truth configured. Set GROUND_TRUTH_B64 (recommended for "
        "env-only platforms) or GROUND_TRUTH_YAML, or mount a file at "
        f"{config.GROUND_TRUTH_PATH} and set GROUND_TRUTH_PATH."
    )


def public_tasks() -> list[dict]:
    """Task metadata safe to send to the browser (no answers)."""
    out = []
    for t in load_tasks():
        out.append(
            {
                "id": t["id"],
                "section_id": t["section_id"],
                "title": t["title"],
                "points": t["points"],
                "validator_type": t["validator_type"],
                "sort_order": t["sort_order"],
                "instructions": " ".join(t["instructions"].split()),
                "input": t.get("input", "text"),
                "answer_hint": t.get("answer_hint"),
                "evidence_hint": t.get("evidence_hint"),
                "choices": t.get("choices"),
                "event_choices": t.get("event_choices"),
                "require_evidence": t.get("require_evidence", False),
            }
        )
    return out
