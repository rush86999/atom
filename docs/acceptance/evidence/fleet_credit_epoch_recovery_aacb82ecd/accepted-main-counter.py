"""
Capability Graduation Service - Upstream Edition

Manages the maturity progression of agent capabilities through 
Student, Intern, Supervised, and Autonomous levels.
"""
import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.models import AgentRegistry, HITLAction, HITLActionStatus

logger = logging.getLogger(__name__)

class CapabilityMaturityLevel:
    STUDENT = "student"
    INTERN = "intern"
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"

    ORDER = [STUDENT, INTERN, SUPERVISED, AUTONOMOUS]

    @classmethod
    def is_at_least(cls, current: str, required: str) -> bool:
        if current not in cls.ORDER or required not in cls.ORDER:
            return False
        return cls.ORDER.index(current) >= cls.ORDER.index(required)

class CapabilityGraduationService:
    #: New verified successes required after a revocation before the
    #: capability may act autonomously again (the 20-success supervised rung).
    REVOCATION_REENTRY_SUCCESSES = 20
    """Service to track and manage capability maturity for agents."""

    def __init__(self, db: Session):
        self.db = db

    def get_maturity(self, agent_id: str, capability_name: str) -> str:
        """Get current maturity level for a capability."""
        # Stored under the agent's `configuration` JSON column (the model has
        # no `properties` field; earlier code referenced a nonexistent attr).
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            return CapabilityMaturityLevel.STUDENT

        config = self._config(agent)
        maturities = config.get("capability_maturities", {})
        # Per-capability level wins; "*" sets an agent-wide default tier
        # (e.g. register the meta agent at supervised) for capabilities
        # without an explicit entry.
        if capability_name in maturities:
            return maturities[capability_name]
        return maturities.get("*", CapabilityMaturityLevel.STUDENT)

    def record_usage(
        self,
        agent_id: str,
        capability_name: str,
        success: bool,
        verified: str = "unverified",
    ):
        """
        Record usage of a capability to progress maturity.

        Args:
            success: Tool's self-reported success (kept for audit, NOT trusted
                for graduation alone).
            verified: Tri-state from tool_outcome_verifier —
                'verified' | 'unverified' | 'failed_verification'.
                Only 'verified' successes increment the graduation counter.
                Unverified successes still count in the denominator (they
                *lower* the success ratio), so silent no-ops cannot inflate
                capability stats (general critique, fixed).
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            return

        config = self._config(agent)
        if "capability_stats" not in config:
            config["capability_stats"] = {}

        stats = config["capability_stats"].get(
            capability_name,
            {"success": 0, "total": 0, "verified_success": 0},
        )
        stats["total"] += 1
        # Self-reported success — tracked but not sufficient for graduation.
        if success:
            stats["success"] += 1
        # Graduation-gating signal: only verified successes count.
        if success and verified == "verified":
            stats["verified_success"] = stats.get("verified_success", 0) + 1
        # P3 asymmetry (R9: slow to gain, fast to lose): externally-verified
        # failures increment a dedicated penalty counter consumed by
        # skill_scoped_trust.trust_score. Graduation thresholds unchanged.
        if verified == "failed_verification":
            stats["failures_verified"] = stats.get("failures_verified", 0) + 1
        stats["last_outcome_at"] = datetime.now(timezone.utc).isoformat()

        verified_count = int(stats.get("verified_success") or 0)
        # Keep a per-capability epoch baseline so old lifetime credit cannot
        # graduate the capability after the active revocation marker clears.
        revocations = config.get("autonomy_revocations") or {}
        active = revocations.get(capability_name) or {}
        if active:
            active_baseline = active.get("baseline_verified_success")
            if active_baseline is None:
                # Unknown legacy credit cannot certify post-regression work.
                # Anchor at first observation, before this call's new success.
                active_baseline = verified_count - int(success and verified == "verified")
                active["baseline_verified_success"] = active_baseline
                active["baseline_origin"] = "legacy_first_observed"
            stats["epoch_baseline_verified_success"] = max(
                int(stats.get("epoch_baseline_verified_success") or 0),
                int(active_baseline),
            )

        # VERIFIED REGRESSION revokes earned autonomy. A capability that had
        # verified successes and then fails external verification is not
        # "slow to gain, fast to lose" only on a score: the runtime gate must
        # stop trusting it. Persisted in the agent configuration so the
        # revocation survives a restart.
        if (verified == "failed_verification"
                and verified_count > 0):
            revocations = config.setdefault("autonomy_revocations", {})
            previous = revocations.get(capability_name) or {}
            # Baseline the lifetime counter AT revocation: re-entry needs new
            # verified successes after this point. A repeated regression starts
            # a fresh epoch and baseline.
            stats["epoch_baseline_verified_success"] = verified_count
            revocations[capability_name] = {
                "at": datetime.now(timezone.utc).isoformat(),
                "reason": "verified_regression",
                "failures_verified": int(stats.get("failures_verified") or 0),
                "verified_success": verified_count,
                "baseline_verified_success": verified_count,
                "epoch": int(previous.get("epoch") or 0) + 1,
                "reentry_successes": 0,
            }
            config.setdefault("capability_maturities", {})[
                capability_name] = CapabilityMaturityLevel.STUDENT

        config["capability_stats"][capability_name] = stats
        # Persist back through the model's JSON column (mutation isn't auto-detected).
        agent.configuration = dict(config)
        self.flag_modified(agent, "configuration")

        # Graduation now gates on verified_success — a silent no-op returning
        # {success: true} without evidence lands as unverified and cannot
        # promote the capability.
        verified_successes = int(stats.get("verified_success") or 0)
        baseline = int(stats.get("epoch_baseline_verified_success") or 0)
        new_successes = max(0, verified_successes - baseline)
        revocations = config.get("autonomy_revocations") or {}
        entry = revocations.get(capability_name)
        if entry:
            entry["reentry_successes"] = new_successes
            revocations[capability_name] = entry
            config["autonomy_revocations"] = revocations
            reentered = False
            # Re-entry needs NEW verified successes after the revocation, not
            # the lifetime total.
            if (success and verified == "verified"
                    and new_successes >= self.REVOCATION_REENTRY_SUCCESSES):
                revocations.pop(capability_name, None)
                config["autonomy_revocations"] = revocations
                config.setdefault("capability_maturities", {})[
                    capability_name] = CapabilityMaturityLevel.INTERN
                reentered = True
            if not reentered:
                config.setdefault("capability_maturities", {})[
                    capability_name] = CapabilityMaturityLevel.STUDENT
            agent.configuration = dict(config)
            self.flag_modified(agent, "configuration")
        # While an active revocation marker remains, hold STUDENT. Only a
        # verified success may climb; post-regression successes alone count.
        if success and verified == "verified" and not entry:
            current = self.get_maturity(agent_id, capability_name)
            if new_successes >= 5 and current == CapabilityMaturityLevel.STUDENT:
                self._update_maturity(agent, capability_name, CapabilityMaturityLevel.INTERN)
            elif new_successes >= 20 and current == CapabilityMaturityLevel.INTERN:
                self._update_maturity(agent, capability_name, CapabilityMaturityLevel.SUPERVISED)
            elif new_successes >= 50 and current == CapabilityMaturityLevel.SUPERVISED:
                # Autonomous requires high confidence
                self._update_maturity(agent, capability_name, CapabilityMaturityLevel.AUTONOMOUS)

        self.db.commit()

    def reset_maturity(self, agent_id: str, capability_name: str, reason: str):
        """Reset capability maturity to STUDENT level."""
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if agent:
            self._update_maturity(agent, capability_name, CapabilityMaturityLevel.STUDENT)
            logger.info(f"Reset maturity for {agent_id}:{capability_name} to STUDENT. Reason: {reason}")
            self.db.commit()

    def _update_maturity(self, agent: AgentRegistry, capability_name: str, level: str):
        config = self._config(agent)
        if "capability_maturities" not in config:
            config["capability_maturities"] = {}
        config["capability_maturities"][capability_name] = level
        agent.configuration = dict(config)
        self.flag_modified(agent, "configuration")
        logger.info(f"Capability '{capability_name}' for agent {agent.id} graduated to {level}")

    def _config(self, agent: AgentRegistry) -> dict:
        """Read the agent's configuration JSON column as a plain dict.

        Earlier code referenced a nonexistent ``agent.properties`` attribute;
        the model stores flexible metadata under ``configuration``. Returns a
        mutable copy so callers can edit and reassign.
        """
        cfg = getattr(agent, "configuration", None) or {}
        if not isinstance(cfg, dict):
            # JSON columns may return other shapes; coerce defensively.
            try:
                cfg = dict(cfg)
            except Exception:
                cfg = {}
        return dict(cfg)

    @staticmethod
    def flag_modified(agent: AgentRegistry, column: str) -> None:
        """Mark a JSON column as mutated so SQLAlchemy flushes the change."""
        try:
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(agent, column)
        except Exception:
            pass
