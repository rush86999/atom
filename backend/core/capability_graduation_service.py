"""
Capability Graduation Service - Upstream Edition

Manages the maturity progression of agent capabilities through 
Student, Intern, Supervised, and Autonomous levels.
"""
import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, Callable, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import Text, and_, cast, select, update

from core.models import AgentRegistry, HITLAction, HITLActionStatus

logger = logging.getLogger(__name__)

#: Marker used by callers that need a configuration mutation to CAS against
#: the exact raw blob they observed (rather than a freshly reread one).
_UNSET = object()

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
        maturities = config.get("capability_maturities")
        if not isinstance(maturities, dict):
            return CapabilityMaturityLevel.STUDENT
        # Per-capability level wins; "*" sets an agent-wide default tier
        # (e.g. register the meta agent at supervised) for capabilities
        # without an explicit entry.
        if capability_name in maturities:
            return maturities[capability_name]
        return maturities.get("*", CapabilityMaturityLevel.STUDENT)

    #: A peer writer may commit between our observed configuration read and
    #: the conditional UPDATE. Reload and retry a bounded number of times; if
    #: contention persists we fail closed instead of overwriting the winner.
    CAS_MAX_ATTEMPTS = 8

    @staticmethod
    def _json_dict(value: Any) -> dict:
        """Decode a JSON column (physical text or already-decoded dict)."""
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError):
                return {}
            return dict(parsed) if isinstance(parsed, dict) else {}
        return {}

    @staticmethod
    def _scope_predicates(expected_scope):
        if expected_scope is None:
            return []
        if not isinstance(expected_scope, dict) or set(expected_scope) != {"tenant_id", "workspace_id"}:
            raise ValueError("invalid_expected_scope")
        predicates = []
        for name in ("tenant_id", "workspace_id"):
            value = expected_scope[name]
            if value is not None and not isinstance(value, str):
                raise ValueError("invalid_expected_scope")
            column = getattr(AgentRegistry, name)
            predicates.append(column.is_(None) if value is None else column == value)
        return predicates

    def _observed_configuration(self, agent_id: str, expected_scope=None):
        """Read the PHYSICAL JSON value without trusting the ORM identity map.

        The returned scalar is exactly what a conditional UPDATE compares
        against. SQL NULL and JSON ``null`` therefore stay distinguishable on
        SQLite (NULL vs the text ``"null"``), avoiding the historical
        NULL/JSON-null mismatch.
        """
        row = self.db.execute(
            select(cast(AgentRegistry.configuration, Text)).where(
                AgentRegistry.id == str(agent_id),
                *self._scope_predicates(expected_scope))
        ).first()
        if row is None:
            return False, None
        return True, row[0]

    def observed_configuration(self, agent_id: str, expected_scope=None):
        """Public read of the exact raw configuration for eligibility binding.

        Consumers that made an eligibility decision from this blob can pass it
        back to :meth:`record_usage` as ``expected_configuration``; the counter
        UPDATE then applies only while the database still holds that identical
        physical value (SQL NULL and JSON ``null`` remain distinct).
        """
        return self._observed_configuration(agent_id, expected_scope)

    @staticmethod
    def _configuration_predicate(observed):
        return (
            AgentRegistry.configuration.is_(None)
            if observed is None
            else cast(AgentRegistry.configuration, Text) == observed
        )

    def _mutate_configuration(
        self,
        agent_id: str,
        mutate: Callable[[dict], dict],
        *,
        commit: bool,
        expected_scope=None,
        expected_configuration: Any = _UNSET,
    ) -> bool:
        """Apply one JSON configuration mutation via database CAS.

        ``with_for_update``/``populate_existing`` are not a compare-and-swap on
        SQLite (and they silently expire caller state elsewhere). Instead the
        exact observed physical configuration is bound into the UPDATE's WHERE
        clause. A peer that commits a revocation/regression between our read and
        write makes the UPDATE match zero rows; we reload from the database and
        retry, so a stale success cannot erase the peer's revocation. After the
        bounded attempts we fail closed (no write) rather than guess.

        When ``expected_configuration`` is supplied the caller has ALREADY
        observed that exact raw blob to make an eligibility decision. The
        mutation is then attempted once against that snapshot only: a changed
        blob refuses the write (the caller must re-read and decide again)
        instead of silently retrying on top of a peer's newer state.
        """
        if expected_configuration is not _UNSET:
            configuration = mutate(self._json_dict(expected_configuration))
            if not isinstance(configuration, dict):
                return False
            statement = (
                update(AgentRegistry)
                .where(
                    AgentRegistry.id == str(agent_id),
                    self._configuration_predicate(expected_configuration),
                    *self._scope_predicates(expected_scope),
                )
                .values(configuration=configuration)
                .execution_options(synchronize_session=False)
            )
            try:
                changed = self.db.execute(statement)
            except Exception as exc:  # noqa: BLE001 - no write is the safe result
                logger.warning(
                    "Capability config CAS unavailable for %s (%s)",
                    agent_id, type(exc).__name__)
                return False
            if int(changed.rowcount or 0) == 1:
                if commit:
                    self.db.commit()
                return True
            logger.debug(
                "Capability eligibility snapshot changed for %s; refusing "
                "counter credit until it is re-read", agent_id)
            return False

        for _attempt in range(self.CAS_MAX_ATTEMPTS):
            found, observed = self._observed_configuration(agent_id, expected_scope)
            if not found:
                return False
            configuration = mutate(self._json_dict(observed))
            if not isinstance(configuration, dict):
                return False
            predicate = self._configuration_predicate(observed)
            statement = (
                update(AgentRegistry)
                .where(AgentRegistry.id == str(agent_id), predicate,
                       *self._scope_predicates(expected_scope))
                .values(configuration=configuration)
                .execution_options(synchronize_session=False)
            )
            try:
                changed = self.db.execute(statement)
            except Exception as exc:  # noqa: BLE001 - no write is the safe result
                logger.warning(
                    "Capability config CAS unavailable for %s (%s)",
                    agent_id, type(exc).__name__)
                return False
            if int(changed.rowcount or 0) == 1:
                if commit:
                    self.db.commit()
                return True
            # The observed blob changed under us. Loop and reload; the next
            # mutation is based on the peer's current state, not our stale copy.
            logger.debug(
                "Capability config CAS contention for %s (attempt %s)",
                agent_id, _attempt + 1)
        logger.warning(
            "Capability config CAS exhausted for %s; no stale overwrite",
            agent_id)
        return False

    def record_usage(
        self,
        agent_id: str,
        capability_name: str,
        success: bool,
        verified: str = "unverified",
        *,
        commit: bool = True,
        lock: bool = True,
        expected_scope=None,
        expected_configuration: Any = _UNSET,
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
            commit: When False the caller owns the surrounding transaction
                (used by the fleet credit receipt consumer so the receipt and
                this counter update commit together).
            lock: Kept for API compatibility. Configuration writes are always
                a database-level conditional UPDATE (see
                :meth:`_mutate_configuration`); this argument no longer selects
                a weaker read/lock path.
            expected_configuration: Exact raw configuration blob (as returned
                by :meth:`observed_configuration`) that the caller used for its
                eligibility decision. When supplied, the counter update is
                attempted against that snapshot once and refused if the blob
                changed — the caller must re-read and re-decide. This keeps an
                eligibility decision and its counter write in one epoch.
        """
        def _apply(config: dict) -> dict:
            stats_map = config.get("capability_stats")
            if not isinstance(stats_map, dict):
                stats_map = {}
            config["capability_stats"] = stats_map

            stats = stats_map.get(
                capability_name,
                {"success": 0, "total": 0, "verified_success": 0},
            )
            if not isinstance(stats, dict):
                stats = {"success": 0, "total": 0, "verified_success": 0}
            stats["total"] = int(stats.get("total") or 0) + 1
            # Self-reported success — tracked but not sufficient for graduation.
            if success:
                stats["success"] = int(stats.get("success") or 0) + 1
            # Graduation-gating signal: only verified successes count.
            if success and verified == "verified":
                stats["verified_success"] = int(
                    stats.get("verified_success") or 0) + 1

            def _maturities(cfg: dict) -> dict:
                maturities = cfg.get("capability_maturities")
                if not isinstance(maturities, dict):
                    maturities = {}
                cfg["capability_maturities"] = maturities
                return maturities
            # P3 asymmetry (R9: slow to gain, fast to lose): externally-verified
            # failures increment a dedicated penalty counter consumed by
            # skill_scoped_trust.trust_score. Graduation thresholds unchanged.
            if verified == "failed_verification":
                stats["failures_verified"] = stats.get(
                    "failures_verified", 0) + 1
            stats["last_outcome_at"] = datetime.now(timezone.utc).isoformat()

            verified_count = int(stats.get("verified_success") or 0)
            # Keep a per-capability epoch baseline so old lifetime credit cannot
            # graduate the capability after the active revocation marker clears.
            revocations = config.get("autonomy_revocations")
            if not isinstance(revocations, dict):
                revocations = {}
            config["autonomy_revocations"] = revocations
            active = revocations.get(capability_name) or {}
            if not isinstance(active, dict):
                active = {}
            if active:
                active_baseline = active.get("baseline_verified_success")
                if active_baseline is None:
                    # Unknown legacy credit cannot certify post-regression work.
                    # Anchor at first observation, before this call's new success.
                    active_baseline = verified_count - int(
                        success and verified == "verified")
                    active["baseline_verified_success"] = active_baseline
                    active["baseline_origin"] = "legacy_first_observed"
                revocations[capability_name] = active
                config["autonomy_revocations"] = revocations
                stats["epoch_baseline_verified_success"] = max(
                    int(stats.get("epoch_baseline_verified_success") or 0),
                    int(active_baseline),
                )

            # Keep the epoch's clock after the active hold is removed. Legacy
            # baselines without a clock anchor at their first new observation;
            # the receipt consumer treats that observation as unverified.
            if ("epoch_baseline_verified_success" in stats
                    and not stats.get("epoch_started_at")):
                stats["epoch_started_at"] = (
                    active.get("at") or stats["last_outcome_at"])
                stats["epoch_time_origin"] = (
                    "regression_marker" if active.get("at")
                    else "legacy_first_observed")

            # VERIFIED REGRESSION revokes earned autonomy. A capability that had
            # verified successes and then fails external verification is not
            # "slow to gain, fast to lose" only on a score: the runtime gate
            # must stop trusting it. Persisted in the agent configuration so the
            # revocation survives a restart.
            if (verified == "failed_verification"
                    and verified_count > 0):
                revocations = config.setdefault("autonomy_revocations", {})
                previous = revocations.get(capability_name) or {}
                # Baseline the lifetime counter AT revocation: re-entry needs
                # new verified successes after this point. A repeated regression
                # starts a fresh epoch and baseline.
                stats["epoch_baseline_verified_success"] = verified_count
                revocations[capability_name] = {
                    "at": datetime.now(timezone.utc).isoformat(),
                    "reason": "verified_regression",
                    "failures_verified": int(
                        stats.get("failures_verified") or 0),
                    "verified_success": verified_count,
                    "baseline_verified_success": verified_count,
                    "epoch": int(previous.get("epoch") or 0) + 1,
                    "reentry_successes": 0,
                }
                stats["epoch_started_at"] = revocations[capability_name]["at"]
                stats["epoch_time_origin"] = "verified_regression"
                _maturities(config)[
                    capability_name] = CapabilityMaturityLevel.STUDENT

            config["capability_stats"][capability_name] = stats

            # Graduation now gates on verified_success — a silent no-op
            # returning {success: true} without evidence lands as unverified and
            # cannot promote the capability.
            verified_successes = int(stats.get("verified_success") or 0)
            baseline = int(stats.get("epoch_baseline_verified_success") or 0)
            new_successes = max(0, verified_successes - baseline)
            revocations = config.get("autonomy_revocations")
            if not isinstance(revocations, dict):
                revocations = {}
            entry = revocations.get(capability_name)
            if entry:
                entry["reentry_successes"] = new_successes
                revocations[capability_name] = entry
                config["autonomy_revocations"] = revocations
                reentered = False
                # Re-entry needs NEW verified successes after the revocation,
                # not the lifetime total.
                if (success and verified == "verified"
                        and new_successes
                        >= self.REVOCATION_REENTRY_SUCCESSES):
                    revocations.pop(capability_name, None)
                    config["autonomy_revocations"] = revocations
                    _maturities(config)[
                        capability_name] = CapabilityMaturityLevel.INTERN
                    reentered = True
                if not reentered:
                    _maturities(config)[
                        capability_name] = CapabilityMaturityLevel.STUDENT
            # While an active revocation marker remains, hold STUDENT. Only a
            # verified success may climb; post-regression successes alone count.
            if success and verified == "verified" and not entry:
                maturities = _maturities(config)
                current = maturities.get(
                    capability_name,
                    maturities.get("*", CapabilityMaturityLevel.STUDENT))
                if (new_successes >= 5
                        and current == CapabilityMaturityLevel.STUDENT):
                    maturities[capability_name] = CapabilityMaturityLevel.INTERN
                elif (new_successes >= 20
                        and current == CapabilityMaturityLevel.INTERN):
                    maturities[
                        capability_name] = CapabilityMaturityLevel.SUPERVISED
                elif (new_successes >= 50
                        and current == CapabilityMaturityLevel.SUPERVISED):
                    # Autonomous requires high confidence
                    maturities[
                        capability_name] = CapabilityMaturityLevel.AUTONOMOUS
            return config

        return self._mutate_configuration(
            agent_id, _apply, commit=commit, expected_scope=expected_scope,
            expected_configuration=expected_configuration)

    def reset_maturity(self, agent_id: str, capability_name: str,
                       reason: str) -> bool:
        """Reset capability maturity to STUDENT and open a fresh epoch.

        Uses the same conditional-UPDATE discipline as :meth:`record_usage`, so
        a reset racing a revocation/regression cannot resurrect an unrelated
        stale configuration blob.

        A human correction is NOT a verified regression: it starts a new
        verified-success baseline at the exact reset (the existing lifetime
        counters stay intact and auditable) without inventing failure counts or
        an ``autonomy_revocations`` regression marker. Only successes after the
        reset can re-graduate through the normal 5/20/50 ladder.
        """
        def _reset(config: dict) -> dict:
            maturities = config.get("capability_maturities")
            if not isinstance(maturities, dict):
                maturities = {}
            maturities[capability_name] = CapabilityMaturityLevel.STUDENT
            config["capability_maturities"] = maturities

            stats_map = config.get("capability_stats")
            if not isinstance(stats_map, dict):
                stats_map = {}
            config["capability_stats"] = stats_map
            stats = stats_map.get(capability_name)
            if not isinstance(stats, dict):
                stats = {"success": 0, "total": 0, "verified_success": 0}
            # Bind the epoch at the reset instant. Which success was lifetime
            # history vs fresh post-correction work stays auditable from the
            # counters; graduation compares against this baseline.
            stats["epoch_baseline_verified_success"] = int(
                stats.get("verified_success") or 0)
            stats["epoch_baseline_origin"] = "human_correction"
            stats["epoch_started_at"] = datetime.now(timezone.utc).isoformat()
            stats["epoch_time_origin"] = "human_correction"
            stats_map[capability_name] = stats
            return config

        changed = self._mutate_configuration(
            agent_id, _reset, commit=True)
        if changed:
            logger.info(
                f"Reset maturity for {agent_id}:{capability_name} to STUDENT. "
                f"Reason: {reason}")
        return changed

    def _update_maturity(self, agent: AgentRegistry, capability_name: str, level: str):
        config = self._config(agent)
        maturities = config.get("capability_maturities")
        if not isinstance(maturities, dict):
            maturities = {}
        maturities[capability_name] = level
        config["capability_maturities"] = maturities
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
