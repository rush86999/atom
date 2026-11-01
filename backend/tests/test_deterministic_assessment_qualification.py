"""Frozen-set qualification for the deterministic taught-rule method."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "acceptance"))


def test_rule_expressible_policies_qualify_without_a_model():
    from deterministic_assessment_qualification import run_qualification

    result = run_qualification()
    assert result["qualified"] is True
    assert result["configuration"]["provider"] == "none"
    assert result["configuration"]["model"] == "none"
    for phase in ("v1", "v3"):
        judgment = result["phases"][phase]["judgment"]
        assert judgment["ok"] is True
        assert judgment["judgment"] == "passed"
        assert judgment["accuracy"] == 1.0
        assert judgment["safe_abstention"]["passed"] is True
        assert judgment["safe_abstention"]["violations"] == []
        assert judgment["mismatches"] == {}
