"""Round 81f — P2 certification gate for the trust calibration gateway."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from core.trust_calibration.certify import (
    BRIER_BASELINE,
    ResolvedDecision,
    certify,
)


def _rows(spec: str, n=36):
    """spec: 'g'=well-scored approvals, 'b'=well-scored rejections,
    'X'=anti-correlated (high p on rejects). Rows spread over time."""
    rows = []
    now = datetime.now(timezone.utc)
    for i in range(n):
        kind = spec[i % len(spec)]
        age = timedelta(days=(n - i))  # temporal order: i=0 oldest
        decided = now - age
        if kind == "g":
            p, y = 0.9, 1
        elif kind == "b":
            p, y = 0.1, 0
        else:  # "X": anti-correlated — high p, human rejects
            p, y = 0.9, 0
        rows.append(ResolvedDecision(
            p_approve=p, y=y, decided_at=decided,
            features_json={"tool": [p, p, p], "ctx": [0.5]},
        ))
    return rows


class TestCertificationGate:
    def test_well_calibrated_history_certifies(self):
        # Alternating g/b keeps both classes in train AND holdout windows.
        result = certify(_rows("gb" * 18))
        assert result.certified is True
        assert result.brier_holdout <= BRIER_BASELINE
        assert result.n_eval >= 8
        assert result.reasons == []

    def test_anticorrelated_history_fails(self):
        # Train on clean separation; holdout rejections wear APPROVAL-like
        # features and carry confidently-wrong recorded p (0.95). The refit
        # must miss them -> Brier blows up AND coverage stays 0.
        now = datetime.now(timezone.utc)
        rows = []
        for i in range(24):
            good = i % 2 == 0
            p = 0.9 if good else 0.1
            rows.append(ResolvedDecision(
                p_approve=p, y=int(good),
                decided_at=now - timedelta(days=200 - i),
                features_json={"tool": [p] * 3, "ctx": [0.5]},
            ))
        for i in range(8):
            rows.append(ResolvedDecision(
                p_approve=0.95, y=0,
                decided_at=now - timedelta(days=20 - i),
                features_json={"tool": [0.9] * 3, "ctx": [0.5]},
            ))
        result = certify(rows)
        assert result.certified is False
        assert result.brier_holdout > BRIER_BASELINE
        assert result.denial_coverage == 0.0

    def test_insufficient_data(self):
        result = certify(_rows("gb", n=10))
        assert result.certified is False
        assert any("insufficient" in r for r in result.reasons)

    def test_no_rejections_in_holdout_flags_coverage(self):
        # Train+eval contain only approvals -> denial coverage None.
        result = certify(_rows("g" * 40))
        assert result.certified is False
        assert any("no rejected" in r or "coverage" in r for r in result.reasons)

    def test_denial_coverage_floor_enforced(self):
        now = datetime.now(timezone.utc)
        rows = []
        # Train window: clean separation so refit is sane.
        for i in range(24):
            good = i % 2 == 0
            p = 0.9 if good else 0.1
            rows.append(ResolvedDecision(
                p_approve=p, y=int(good),
                decided_at=now - timedelta(days=200 - i),
                features_json={"tool": [p] * 3, "ctx": [0.5]},
            ))
        # Holdout: 8 rejections, all over-scored at 0.6 -> coverage 0.
        for i in range(8):
            rows.append(ResolvedDecision(
                p_approve=0.6, y=0,
                decided_at=now - timedelta(days=20 - i),
                features_json={"tool": [0.6] * 3, "ctx": [0.5]},
            ))
        result = certify(rows)
        assert result.certified is False
        assert result.denial_coverage == 0.0
        assert any("coverage" in reason.lower() for reason in result.reasons)


class TestScriptWiring:
    def test_script_exists_and_uses_gate(self):
        import os

        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scripts", "calibrate_trust_gateway.py",
        )
        path = os.path.abspath(path)
        assert os.path.exists(path)
        src = open(path).read()
        assert "certify(" in src
        assert "sys.exit" in src
