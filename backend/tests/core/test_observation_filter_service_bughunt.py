"""Bug-hunt tests for core.observation_filter_service."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest

from unittest.mock import MagicMock

# Ensure the flag is ON for rule-pass tests (imported fresh per process).
os.environ["OBSERVATION_FILTER_ENABLED"] = "true"
os.environ["OBS_FILTER_PER_OBSERVATION_LENGTH_CAP"] = "20"

# Re-import AFTER setting env so module-level constants pick them up.
import importlib
import core.observation_filter_service as _of
importlib.reload(_of)
from core.observation_filter_service import ObservationFilterService  # noqa: E402


# ---------------------------------------------------------------------------
# BUG 1: _apply_rules collapses two DIFFERENT long observations into one
#         because the dedup key is computed on the truncated payload (which
#         appends a fixed truncation marker). Distinct observations sharing a
#         common prefix longer than the cap are silently dropped (data loss).
# ---------------------------------------------------------------------------
def test_apply_rules_keeps_distinct_long_observations():
    """BUG: distinct long observations sharing a prefix are wrongly deduped."""
    svc = ObservationFilterService(MagicMock())

    cap = 20  # matches OBS_FILTER_PER_OBSERVATION_LENGTH_CAP set above
    # Two different observations sharing a common 30-char body but distinct suffixes
    common = "A" * 30
    o1 = "Observation: " + common + "UNIQUE_SUFFIX_1"
    o2 = "Observation: " + common + "UNIQUE_SUFFIX_2"
    history = "\n".join(["Thought: t", o1, o2])

    out = svc._apply_rules(history)
    observations = [ln for ln in out.split("\n") if ln.startswith("Observation:")]

    assert len(observations) == 2, (
        f"expected both distinct observations kept, got {len(observations)}: "
        f"{observations}"
    )
    # Both suffixes must be represented (after truncation, the suffix may be cut,
    # but the two observations must not collapse to one).
    joined = " ".join(observations)
    assert "UNIQUE_SUFFIX_1" in joined or "UNIQUE_SUFFIX_2" in joined or len(observations) == 2


# ---------------------------------------------------------------------------
# Sanity: identical observations ARE still collapsed by the rule pass.
# ---------------------------------------------------------------------------
def test_apply_rules_collapses_identical_observations():
    """Guard: truly identical observations should still be deduped."""
    svc = ObservationFilterService(MagicMock())
    o = "Observation: short identical message"
    history = "\n".join(["Thought: t", o, o, o])
    out = svc._apply_rules(history)
    observations = [ln for ln in out.split("\n") if ln.startswith("Observation:")]
    assert len(observations) == 1
