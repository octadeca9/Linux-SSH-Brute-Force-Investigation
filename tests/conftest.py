"""Shared test fixtures/markers.

Tests that exercise scoring/validation need the answer key (ground truth).
In a platform-scored deployment (TASKS_ENABLED=false, scoring on
hack.redlimit.id) the key may be absent — CI then has no GROUND_TRUTH_B64 and no
config/ground_truth.yaml. Mark such tests with `@pytest.mark.requires_ground_truth`
and this hook skips them automatically when the key is not configured, so the
viewer/schema tests still run and CI stays green without any secret.
"""
import pytest

from app.services.loaders import GroundTruthNotConfigured, load_ground_truth


def _ground_truth_available() -> bool:
    try:
        load_ground_truth()
        return True
    except GroundTruthNotConfigured:
        return False


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "requires_ground_truth: test needs the answer key (GROUND_TRUTH_B64 or a mounted file)",
    )


def pytest_collection_modifyitems(config, items):
    if _ground_truth_available():
        return
    skip = pytest.mark.skip(
        reason="ground truth not configured (viewer-only / platform-scored); "
        "set GROUND_TRUTH_B64 to run"
    )
    for item in items:
        if "requires_ground_truth" in item.keywords:
            item.add_marker(skip)
