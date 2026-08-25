"""TrustCalibrationGateway — three-tier allow/ask/block assessments.

Shadow-only in P0: assess() is pure inference over already-recorded human
decisions. Nothing here writes to any decision path (plan §4/P0).
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from core.trust_calibration.features import context_vector, tool_vector
from core.trust_calibration.gp import ProductKernelGP

logger = logging.getLogger(__name__)

MIN_OBSERVATIONS = 10


def _env_float(name: str, default: float) -> float:
    # Env wins > runtime_settings DB row (UI admin) > default.
    from core.runtime_settings import get_float_setting

    return get_float_setting(name, default)


def enabled() -> bool:
    return get_bool_setting("ATOM_TRUST_CALIBRATION_ENABLED", False)


class TrustCalibrationGateway:
    """Fit-on-demand posterior with a TTL cache; never raises on assess."""

    def __init__(self, db=None) -> None:
        self.db = db
        self.half_life_days = _env_float(
            "ATOM_TRUST_CALIBRATION_HALF_LIFE_DAYS", 30.0
        )
        self.max_obs = int(_env_float("ATOM_TRUST_CALIBRATION_MAX_OBS", 400))
        self.refit_ttl = _env_float("ATOM_TRUST_CALIBRATION_REFIT_TTL", 300.0)
        self.tau_low = _env_float("ATOM_TRUST_CALIBRATION_TAU_LOW", 0.35)
        self.tau_uncertain = _env_float("ATOM_TRUST_CALIBRATION_TAU_UNCERTAIN", 0.15)
        self.min_observations = int(
            _env_float("ATOM_TRUST_CALIBRATION_MIN_OBS", MIN_OBSERVATIONS)
        )

        self._gp = ProductKernelGP(
            half_life_days=self.half_life_days, max_obs=self.max_obs,
            min_observations=self.min_observations,
        )
        self._synthetic: List[Any] = []   # test-only injected observations
        self._fitted_at: float = 0.0
        self._stats: Dict[str, int] = {"hitl": 0, "proposal": 0}
        self._last_error: Optional[str] = None

    # ------------------------------------------------------------- refit

    def refresh(self, force: bool = False) -> None:
        now = time.monotonic()
        if (
            not force
            and self._gp.n_obs > 0
            and (now - self._fitted_at) < self.refit_ttl
        ):
            return

        obs = list(self._synthetic)
        if self.db is not None:
            try:
                from core.trust_calibration.service import (
                    age_days_of, load_decisions,
                )

                obs = obs + load_decisions(self.db, limit=self.max_obs)
            except Exception as e:  # noqa: BLE001
                self._last_error = f"load failed: {e}"
                logger.debug(f"trust calibration load failed: {e}")

        if not obs:
            self._fitted_at = now
            self._stats = {"hitl": 0, "proposal": 0}
            return

        # Batch agent-tier lookup.
        agent_ids = {o.agent_id for o in obs if o.agent_id}
        tier_by_agent: Dict[str, str] = {}
        if agent_ids and self.db is not None:
            try:
                from core.models import AgentRegistry

                rows = (
                    self.db.query(AgentRegistry)
                    .filter(AgentRegistry.id.in_(list(agent_ids)))
                    .all()
                )
                tier_by_agent = {r.id: r.status for r in rows}
            except Exception as e:  # noqa: BLE001
                logger.debug(f"tier lookup skipped: {e}")

        tool_rows, ctx_rows, ys, ages = [], [], [], []
        stats = {"hitl": 0, "proposal": 0}
        for o in obs:
            tool_rows.append(tool_vector(o.action_type))
            ctx_rows.append(context_vector(tier_by_agent.get(o.agent_id), o.platform))
            ys.append(float(o.y))
            from core.trust_calibration.service import age_days_of

            ages.append(age_days_of(o))
            stats[o.source] = stats.get(o.source, 0) + 1

        try:
            self._gp.fit(
                np.vstack(tool_rows), np.vstack(ctx_rows),
                np.asarray(ys), np.asarray(ages),
            )
            self._last_error = None
        except Exception as e:  # noqa: BLE001
            self._last_error = f"fit failed: {e}"
            logger.warning(f"trust calibration fit failed: {e}")

        self._stats = stats
        self._fitted_at = now

    # ------------------------------------------------------------ assess

    def assess(
        self,
        action_type: str,
        platform: str = "internal",
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Three-tier recommendation. Never raises; fail-safe = ask."""
        try:
            self.refresh()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"trust calibration refresh failed: {e}")

        n_obs = self._gp.n_obs
        base = {
            "action_type": action_type,
            "platform": platform,
            "n_obs": n_obs,
            "sources": dict(self._stats),
            "thresholds": {
                "tau_low": self.tau_low,
                "tau_uncertain": self.tau_uncertain,
            },
            "min_observations": self.min_observations,
        }

        agent_status: Optional[str] = None
        if agent_id and self.db is not None:
            try:
                from core.models import AgentRegistry

                row = (
                    self.db.query(AgentRegistry)
                    .filter(AgentRegistry.id == str(agent_id))
                    .first()
                )
                agent_status = row.status if row else None
            except Exception:  # noqa: BLE001
                agent_status = None

        pred = self._gp.predict(
            tool_vec=tool_vector(action_type),
            ctx_vec=context_vector(agent_status, platform),
            age_days=0.0,
        )
        p = float(pred["p_approve"])
        unc = float(pred["uncertainty"])

        if n_obs < self.min_observations or unc > self.tau_uncertain:
            rec = "ask"
        elif p < self.tau_low:
            rec = "block"
        else:
            rec = "allow"

        base.update({
            "p_approve": p,
            "uncertainty": unc,
            "recommendation": rec,
        })
        return base

    def assess_and_record(
        self,
        db,
        action_type: str,
        platform: str = "internal",
        agent_id: Optional[str] = None,
        source_path: str = "hitl_step_act",
        decision_ref: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Assess AND persist one shadow row (P1 live-shadow).

        Call at every ask-the-human moment; decision_ref is the HITLAction.id
        so /stats can join the human's actual outcome later. Flag-gated and
        never raises — recording must never break the ask path.
        """
        if not enabled():
            return None
        try:
            _ensure_table(db)
            from core.models import TrustCalibrationAssessment

            assessment = self.assess(
                action_type=action_type, platform=platform, agent_id=agent_id
            )
            row = TrustCalibrationAssessment(
                agent_id=agent_id,
                action_type=action_type,
                platform=platform,
                features_json={
                    "tool": tool_vector(action_type).tolist(),
                    "ctx": context_vector(agent_status=None, platform=platform).tolist(),
                },
                p_approve=assessment["p_approve"],
                uncertainty=assessment["uncertainty"],
                recommendation=assessment["recommendation"],
                source_path=source_path,
                decision_ref=decision_ref,
                half_life_days=self.half_life_days,
                n_obs=assessment["n_obs"],
            )
            db.add(row)
            db.commit()
            logger.debug(
                "trust calibration recorded: %s %s p=%.3f rec=%s ref=%s",
                source_path, action_type, assessment["p_approve"],
                assessment["recommendation"], decision_ref,
            )
            return {"id": row.id, **assessment}
        except Exception as e:  # noqa: BLE001
            logger.warning(f"trust calibration record skipped: {e}")
            return None

    # -------------------------------------------------------- test hook

    def seed_synthetic_history(self) -> None:
        """Inject the two-cluster geometry used by tests/docs examples.

        Approvals at the low-complexity/non-destructive corner (fresh);
        denials at the high-complexity/destructive corner (stale, so the
        time-decay path is exercised too).
        """
        import numpy as np
        from core.trust_calibration.service import Observation

        rng = np.random.default_rng(11)
        obs: List[Observation] = []
        for i in range(8):
            obs.append(Observation(
                source="hitl", action_type="search_contacts",
                platform="internal", agent_id=None, approved=True,
                decided_at=datetime.now(timezone.utc) - timedelta(hours=i + 1),
            ).finalize())
        for i in range(6):
            jitter_t = float(np.clip(rng.normal(0.03, 0.01), 0.0, 0.2))
            obs.append(Observation(
                source="hitl",
                action_type=f"bulk_delete_leads_{i}",
                platform="payment", agent_id=None, approved=False,
                decided_at=(
                    datetime.now(timezone.utc) - timedelta(days=120 + i)
                ),
            ).finalize())
        self._synthetic.extend(obs)


# Engines already provisioned this process. Keyed by engine identity (not a
# single bool) so multiple isolated databases each get their own create;
# checkfirst=True keeps re-runs harmless regardless.
_ensured_engines: set = set()


def _ensure_table(db) -> None:
    """Idempotent self-provisioning so the shadow never silently no-ops on
    an un-migrated database (dev/hybrid convention; alembic remains
    canonical for prod)."""
    try:
        bind = db.get_bind()
        key = id(bind)
        if key in _ensured_engines:
            return
        from core.models import TrustCalibrationAssessment

        TrustCalibrationAssessment.__table__.create(
            bind=bind, checkfirst=True
        )
        _ensured_engines.add(key)
        logger.info("trust_calibration_assessments table ensured")
    except Exception as e:  # noqa: BLE001
        logger.debug(f"ensure_table skipped: {e}")
