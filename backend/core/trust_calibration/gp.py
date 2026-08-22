"""Probit-link Gaussian process with the product kernel
k_tool x k_ctx x k_time (trust-calibration plan §3).

- k_tool / k_ctx: squared-exponential blocks over the tool and context
  sub-vectors (per-block lengthscales -> correlated generalization across
  unqueried action/context pairs).
- k_time: pointwise half-life decay w(t) = 0.5 ** (t / half_life_days),
  applied multiplicatively (K *= w w^T). Stale decisions are additionally
  noisier: label noise folds as sn_i^2 = base_noise / w_i, so old evidence
  is down-weighted AND lower-confidence — the bounded-false-allows property
  (predictive label variance floors at sn*^2) comes from this folding.

Labels are signed (+1 approved / -1 rejected); the probit likelihood is
marginalized in closed form via the noise-folded formulation:
    posterior latent ~ N(m*, v*_f),   p(approve) = Phi(m* / sqrt(1 + v*_f))
Numerically this is a single Cholesky per fit — no IRLS, no scipy.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

import numpy as np


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _se_block(A: np.ndarray, B: np.ndarray, lengthscale: float) -> np.ndarray:
    """Squared-exponential kernel between row sets A (n,d) and B (m,d)."""
    if A.size == 0 or B.size == 0:
        return np.zeros((A.shape[0], B.shape[0]))
    a2 = np.sum(A * A, axis=1)[:, None]
    b2 = np.sum(B * B, axis=1)[None, :]
    d2 = np.maximum(a2 + b2 - 2.0 * A @ B.T, 0.0)
    return np.exp(-d2 / (2.0 * lengthscale * lengthscale))


class ProductKernelGP:
    """GP binary classifier with k_tool x k_ctx x k_time and folded
    heteroscedastic probit likelihood."""

    def __init__(
        self,
        half_life_days: float = 30.0,
        l_tool: float = 0.8,
        l_ctx: float = 0.8,
        signal_var: float = 1.0,
        base_noise: float = 0.05,
        jitter: float = 1e-6,
        max_obs: int = 400,
        min_observations: int = 10,
    ) -> None:
        self.half_life_days = max(float(half_life_days), 0.5)
        self.l_tool = max(float(l_tool), 1e-3)
        self.l_ctx = max(float(l_ctx), 1e-3)
        self.signal_var = float(signal_var)
        self.base_noise = max(float(base_noise), 1e-4)
        self.jitter = float(jitter)
        self.max_obs = int(max_obs)
        self.min_observations = int(min_observations)

        self._tool: Optional[np.ndarray] = None
        self._ctx: Optional[np.ndarray] = None
        self._w: Optional[np.ndarray] = None
        self._alpha: Optional[np.ndarray] = None  # (K_sn)^-1 y
        self._n_obs = 0

    # ---------------------------------------------------------------- fit

    def fit(
        self,
        tool_vecs: np.ndarray,
        ctx_vecs: np.ndarray,
        y: np.ndarray,
        ages_days: np.ndarray,
    ) -> None:
        tool_vecs = np.atleast_2d(np.asarray(tool_vecs, dtype=float))
        ctx_vecs = np.atleast_2d(np.asarray(ctx_vecs, dtype=float))
        y = np.asarray(y, dtype=float).ravel()
        ages = np.clip(np.asarray(ages_days, dtype=float).ravel(), 0.0, None)

        if y.size < self.min_observations:
            return  # stay unfitted -> cold-start prior at predict()

        # Keep the most recent max_obs points.
        if y.size > self.max_obs:
            order = np.argsort(ages)  # ascending age = newest first
            keep = order[: self.max_obs]
            tool_vecs, ctx_vecs, y, ages = (
                tool_vecs[keep], ctx_vecs[keep], y[keep], ages[keep],
            )

        w = np.power(0.5, ages / self.half_life_days)
        w = np.clip(w, 1e-4, 1.0)

        K_tool = _se_block(tool_vecs, tool_vecs, self.l_tool)
        K_ctx = _se_block(ctx_vecs, ctx_vecs, self.l_ctx)
        K = self.signal_var * K_tool * K_ctx * np.outer(w, w)

        sn2 = self.base_noise / w  # stale -> noisier labels
        K_sn = K + np.diag(sn2 + self.jitter)

        try:
            L = np.linalg.cholesky(K_sn)
            alpha = np.linalg.solve(L.T, np.linalg.solve(L, y))
        except np.linalg.LinAlgError:
            # Degenerate geometry: fall back to heavy jitter once.
            K_sn = K + np.diag(sn2 + self.jitter + 1e-3 * np.trace(K_sn) / len(y))
            L = np.linalg.cholesky(K_sn)
            alpha = np.linalg.solve(L.T, np.linalg.solve(L, y))

        self._tool, self._ctx, self._w, self._alpha = tool_vecs, ctx_vecs, w, alpha
        self._K_sn_cache = K_sn
        self._n_obs = int(y.size)

    # ------------------------------------------------------------ predict

    def predict(
        self,
        tool_vec: np.ndarray,
        ctx_vec: np.ndarray,
        age_days: float = 0.0,
    ) -> dict:
        """Return {p_approve, uncertainty, mean, var_label}.

        uncertainty is the LABEL variance v_label = v_f + sn*^2 — its floor
        is sn*^2 (the bounded-false-allows property), not zero.
        """
        tv = np.atleast_2d(np.asarray(tool_vec, dtype=float))
        cv = np.atleast_2d(np.asarray(ctx_vec, dtype=float))

        if (
            self._alpha is None
            or self._tool is None
            or tv.shape[1] != self._tool.shape[1]
            or cv.shape[1] != self._ctx.shape[1]
        ):
            v_label = self.signal_var + self.base_noise
            return {
                "p_approve": 0.5,
                "uncertainty": v_label,
                "mean": 0.0,
                "var_label": v_label,
            }

        w_star = math.pow(
            0.5, max(float(age_days), 0.0) / self.half_life_days
        )
        sn2_star = self.base_noise / max(w_star, 1e-4)

        k_tool_star = _se_block(tv, self._tool, self.l_tool).ravel()
        k_ctx_star = _se_block(cv, self._ctx, self.l_ctx).ravel()
        k_star = (
            self.signal_var * k_tool_star * k_ctx_star * self._w * w_star
        )

        mean = float(k_star @ self._alpha)
        # v_f = 1 - k*^T K_sn^-1 k* ; solve instead of explicit inverse.
        try:
            solved = np.linalg.solve(self._K_sn_cache, k_star)
        except np.linalg.LinAlgError:
            solved = k_star  # conservative fallback
        v_f = max(1.0 - float(k_star @ solved), 0.0)
        v_label = v_f + sn2_star

        denom = math.sqrt(1.0 + max(v_f, 0.0))
        p = _norm_cdf(mean / denom) if denom > 0 else 0.5
        return {
            "p_approve": float(min(max(p, 0.0), 1.0)),
            "uncertainty": float(v_label),
            "mean": mean,
            "var_label": float(v_label),
        }

    # ------------------------------------------------------------- state

    @property
    def n_obs(self) -> int:
        return self._n_obs
