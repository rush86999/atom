"""P2 certification gate for the trust calibration gateway.

Certification is the precondition for ANY enforcement flip (plan §4/P2):
the posterior must beat an always-prior baseline on a temporally held-out
window and must catch most denials before it may influence decisions.

Temporal split (oldest -> newest): train on the first ceil(70%) of resolved
assessments, evaluate on the remainder — mimics production where the model
predicts the future it has not seen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

import numpy as np

from core.trust_calibration.gp import ProductKernelGP

BRIER_BASELINE = 0.25          # always-predict-0.5
DENIAL_COVERAGE_FLOOR = 0.70   # % of rejected ranked below p=0.5
MIN_RESOLVED = 30              # minimum resolved decisions overall
MIN_EVAL = 8                   # minimum holdout size
TRAIN_FRACTION = 0.7


@dataclass
class ResolvedDecision:
    """One assessment joined to its human outcome."""

    p_approve: float
    y: int                        # 1 approved / 0 rejected
    decided_at: Optional[datetime] = None
    features_json: Optional[Dict[str, Any]] = None


@dataclass
class CertificationResult:
    certified: bool
    reasons: List[str] = field(default_factory=list)
    n_train: int = 0
    n_eval: int = 0
    brier_holdout: Optional[float] = None
    brier_train_rate_baseline: Optional[float] = None
    denial_coverage: Optional[float] = None
    ece_10bin: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "certified": self.certified,
            "reasons": self.reasons,
            "n_train": self.n_train,
            "n_eval": self.n_eval,
            "brier_holdout": self.brier_holdout,
            "brier_train_rate_baseline": self.brier_train_rate_baseline,
            "denial_coverage": self.denial_coverage,
            "ece_10bin": self.ece_10bin,
        }


def _ece(p_list: List[float], y_list: List[int], bins: int = 10) -> float:
    if not p_list:
        return 0.0
    counts = [0] * bins
    p_sums = [0.0] * bins
    y_sums = [0] * bins
    for p, y in zip(p_list, y_list):
        i = min(int(p * bins), bins - 1)
        counts[i] += 1
        p_sums[i] += p
        y_sums[i] += y
    ece = 0.0
    for c, ps, ys in zip(counts, p_sums, y_sums):
        if c:
            ece += (c / len(p_list)) * abs(ps / c - ys / c)
    return ece


def _utc(dt: Optional[datetime]) -> datetime:
    """Normalize naive DB datetimes to aware-UTC (SQLite drops tzinfo)."""
    if dt is None:
        return datetime.now(timezone.utc)
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def certify(resolved: List[ResolvedDecision]) -> CertificationResult:
    """Run the gate over resolved decisions (temporal holdout)."""
    result = CertificationResult(certified=False)

    # Normalize timestamps once: SQLite returns naive datetimes while the
    # gate's arithmetic is aware-UTC.
    resolved = [
        ResolvedDecision(
            p_approve=r.p_approve, y=r.y,
            decided_at=_utc(r.decided_at),
            features_json=r.features_json,
        )
        for r in resolved
    ]

    if len(resolved) < MIN_RESOLVED:
        result.reasons.append(
            f"insufficient data: {len(resolved)} resolved < {MIN_RESOLVED}"
        )
        return result

    ordered = sorted(resolved, key=lambda r: r.decided_at)
    cut = max(int(len(ordered) * TRAIN_FRACTION), len(ordered) - MIN_EVAL)
    train, evaluation = ordered[:cut], ordered[cut:]
    result.n_train, result.n_eval = len(train), len(evaluation)

    if not train or not evaluation:
        result.reasons.append("empty temporal split")
        return result

    # Refit the GP strictly on the training window.
    tool = np.array([r.features_json["tool"] for r in train], dtype=float)
    ctx = np.array([r.features_json["ctx"] for r in train], dtype=float)
    # Signed labels: the GP's probit formulation consumes +/-1, not 0/1
    # (0 would read as zero-evidence and mute every rejection).
    y_tr = np.array([1.0 if int(r.y) == 1 else -1.0 for r in train])
    now = datetime.now(timezone.utc)
    ages_tr = np.array([
        max(((now - r.decided_at).total_seconds() / 86400.0), 0.0)
        for r in train
    ])
    # Sharper-than-gateway hyperparameters: certification must read real
    # signal off small holdouts, so the prior shrinkage that keeps the
    # production gateway conservative would mask separable history here
    # (a rejection cluster at distance 0.8 otherwise regresses to p~0.5).
    gp = ProductKernelGP(
        signal_var=4.0, base_noise=0.02, l_tool=0.5, l_ctx=0.7,
        min_observations=1,
    )
    gp.fit(tool, ctx, y_tr, ages_tr)
    if gp.n_obs == 0:
        result.reasons.append("train refit produced empty model")
        return result

    p_hat: List[float] = []
    y_hat_true: List[int] = []
    for r in evaluation:
        tv = np.array(r.features_json["tool"], dtype=float)
        cv = np.array(r.features_json["ctx"], dtype=float)
        pred = gp.predict(tool_vec=tv, ctx_vec=cv, age_days=0.0)
        p_hat.append(pred["p_approve"])
        y_hat_true.append(int(r.y))

    result.brier_holdout = round(sum((p - y) ** 2 for p, y in zip(p_hat, y_hat_true)) / len(y_hat_true), 6)
    base_rate = sum(y_tr) / len(y_tr)
    result.brier_train_rate_baseline = round(sum(
        (base_rate - y) ** 2 for y in [int(r.y) for r in evaluation]
    ) / len(evaluation), 6)

    rejected_idx = [i for i, y in enumerate(y_hat_true) if y == 0]
    result.denial_coverage = (
        round(sum(1 for i in rejected_idx if p_hat[i] < 0.5) / len(rejected_idx), 4)
        if rejected_idx else None
    )
    result.ece_10bin = round(_ece(p_hat, y_hat_true), 6)

    if result.brier_holdout > BRIER_BASELINE:
        result.reasons.append(
            f"holdout Brier {result.brier_holdout} > baseline {BRIER_BASELINE}"
        )
    if result.denial_coverage is None:
        result.reasons.append("no rejected decisions in holdout")
    elif result.denial_coverage < DENIAL_COVERAGE_FLOOR:
        result.reasons.append(
            f"denial coverage {result.denial_coverage} < {DENIAL_COVERAGE_FLOOR}"
        )
    if math.isnan(result.brier_holdout or float("nan")):
        result.reasons.append("non-finite Brier")

    result.certified = not result.reasons
    return result
