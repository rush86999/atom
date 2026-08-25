#!/usr/bin/env python3
"""calibrate_trust_gateway.py — P2 certification gate runner.

Loads resolved trust-calibration assessments (joined to their HITL outcomes),
runs the temporal-holdout certification gate, and prints a JSON verdict.

Exit codes: 0 = certified, 1 = not certified, 2 = setup error.

Usage:
  PYTHONPATH=.:.. python scripts/calibrate_trust_gateway.py
"""

import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)


def main() -> int:
    # Isolated DB unless pointed otherwise; the gate reads production-shaped
    # rows from trust_calibration_assessments joined to hitl_actions.
    try:
        from core.database import SessionLocal
        from sqlalchemy import or_
        from core.models import HITLAction, TrustCalibrationAssessment
    except ImportError as e:
        print(f"setup error: {e}", file=sys.stderr)
        return 2

    try:
        from core.trust_calibration.certify import (
            ResolvedDecision,
            certify,
        )
    except ImportError as e:
        print(f"setup error: {e}", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        rows = (
            db.query(TrustCalibrationAssessment, HITLAction.status)
            .join(HITLAction, TrustCalibrationAssessment.decision_ref == HITLAction.id)
            .filter(
                HITLAction.status.in_(["approved", "rejected"]),
                TrustCalibrationAssessment.decision_ref.isnot(None),
            )
            .order_by(TrustCalibrationAssessment.created_at.asc())
            .limit(2000)
            .all()
        )
    except Exception as e:
        print(
            "setup error: could not read assessments (has the "
            "trust_calibration_assessments migration been applied?): "
            f"{type(e).__name__}",
            file=sys.stderr,
        )
        return 2
    finally:
        db.close()

    resolved = [
        ResolvedDecision(
            p_approve=float(a.p_approve),
            y=1 if status == "approved" else 0,
            decided_at=a.created_at,
            features_json=a.features_json
            or {"tool": [0.5, 0.5, 0.5], "ctx": [0.5]},
        )
        for a, status in rows
    ]

    print(f"Loaded {len(resolved)} resolved decisions")
    verdict = certify(resolved)
    out = verdict.to_dict()
    out["certified_thresholds"] = {
        "brier_baseline": 0.25,
        "denial_coverage_floor": 0.70,
        "min_resolved": 30,
        "min_eval": 8,
    }
    print(json.dumps(out, indent=2))

    if verdict.certified:
        print("CERTIFIED: gateway may proceed to consent-gated relaxation review.")
        return 0
    print("NOT CERTIFIED: enforcement stays off.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
