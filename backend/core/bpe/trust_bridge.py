"""Trust bridge between the adjudicated feedback pipeline and the BPE harness.

Atom has two reward channels with different trust properties:

- **Self-computed** — the consult-policy value EMA (consult_policy.py): dense,
  in-memory, success+efficiency scored. Trustworthy only for narrow "did the
  task complete efficiently" semantics; self-graded rewards inflate over time
  (the "memory reward inflation" failure mode, arXiv:2608.00017 — wrong
  episodes receive high self-assigned rewards and errors compound through
  memory).
- **Adjudicated** — the AgentFeedback pipeline (agent_governance_service.py):
  human corrections accepted only from trusted reviewers, plus verified
  tri-state outcomes. Per the Error-Independence requirement, this is the only
  channel that both tracks truth and is decorrelated from the agent's own
  grading bias — so it is the only one allowed to correct the self-channel.

Design (kept deliberately separate, joined hierarchically — never blended
into one score; PBRS practice: the extrinsic/trusted signal keeps precedence,
the self signal only shapes within what the trusted channel has not
contradicted):

1. **Corrections bypass the value gate** — an agent with accepted human
   corrections has its workspace rendered even when its own EMA would
   suppress it (corrections are *wrong*-ness signals, suppression is for
   *unhelpful*).
2. **Veto, not vote** — accepted corrections arriving since the last genome
   application hold ``evolution.apply_best`` (the fitness EMA is throttled by
   the human channel, never outvotes it). An explicit operator override
   (``ATOM_BPE_EVOLUTION_ENABLED=true``) still wins, matching the repo's
   kill-switch semantics.
3. **De-inflation** — only the adjudicated channel may demote Experience
   entries: on an accepted correction, entries that overlap the rejected
   original output are demoted (uses → 0) so LFU eviction removes them
   naturally. Self-judging is structurally disqualified from this path.
4. **Role-scaled trust** — the self-EMA earns gating autonomy as the agent's
   org status rises: STUDENT agents need 3× the episodes before their own EMA
   can suppress rendering, INTERN 2×, SUPERVISED/AUTONOMOUS 1× (today's
   behavior). Unknown/unreadable status behaves as today (fail-open, 1×).

In-memory, never raises (mirrors consult_policy/evolution patterns).
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from core.bpe.telemetry import record_bpe_span

logger = logging.getLogger(__name__)

# Role-scaled evidence multipliers: how much MORE episode evidence a junior
# agent needs before its self-EMA is trusted to suppress workspace rendering.
# Unknown status (DB unavailable, agent gone) → 1.0 = today's fail-open.
ROLE_EPISODE_MULTIPLIER = {
    "student": 3.0,
    "intern": 2.0,
    "supervised": 1.0,
    "autonomous": 1.0,
}
_UNKNOWN_ROLE_MULTIPLIER = 1.0
_ROLE_CACHE_TTL = 300.0  # seconds; org status changes are rare

# De-inflation: an Experience entry is "suspect" when it shares this many
# tokens (len>2) with the rejected original output AND at least this share of
# its own tokens — overlap, not verbatim matching (agents paraphrase).
DEINFLATE_MIN_SHARED_TOKENS = 2
DEINFLATE_MIN_SHARE = 0.5


class AgentTrustState:
    """Per-agent adjudication counters (in-process; resets with the registry)."""

    __slots__ = ("corrections_accepted", "approvals_accepted",
                 "deinflations", "role", "role_checked_at", "updated_at")

    def __init__(self) -> None:
        self.corrections_accepted = 0
        self.approvals_accepted = 0
        self.deinflations = 0
        self.role: Optional[str] = None
        self.role_checked_at = 0.0
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "corrections_accepted": self.corrections_accepted,
            "approvals_accepted": self.approvals_accepted,
            "deinflations": self.deinflations,
            "role": self.role,
            "updated_at": self.updated_at,
        }


class TrustBridge:
    """In-memory trust state + the three join points into BPE. Cheap."""

    def __init__(self) -> None:
        self._agents: Dict[str, AgentTrustState] = {}
        self._corrections_since_apply = 0

    # ------------------------------------------------------------------
    # Ingest (called from the adjudication seam)
    # ------------------------------------------------------------------

    def record_adjudication(self, agent_id: str, accepted: bool,
                            is_correction: bool,
                            original_output: str = "",
                            user_correction: str = "") -> Dict[str, Any]:
        """Fold one adjudicated feedback row into trust state.

        Accepted corrections (trusted reviewer, not a plain approval) are the
        strong signal: they raise the agent's protocol count, hold evolution
        application, and de-inflate the agent's workspaces. Rejected/pending
        rows are ignored — only adjudicated truth moves this module.
        """
        agent_id = str(agent_id)
        state = self._agents.setdefault(agent_id, AgentTrustState())
        result: Dict[str, Any] = {"agent_id": agent_id,
                                  "accepted": bool(accepted),
                                  "is_correction": bool(is_correction)}
        if not (accepted and is_correction):
            if accepted:
                state.approvals_accepted += 1
            state.updated_at = time.time()
            result["deinflated"] = 0
            return result

        state.corrections_accepted += 1
        self._corrections_since_apply += 1
        deinflated = self._deinflate_agent_workspaces(
            agent_id, original_output or "", user_correction or "")
        state.deinflations += deinflated
        state.updated_at = time.time()
        result["deinflated"] = deinflated
        result["corrections_since_apply"] = self._corrections_since_apply

        record_bpe_span(
            action="trust_adjudication",
            agent_id=agent_id,
            success=True,
            extra={
                "corrections_accepted": state.corrections_accepted,
                "deinflated": deinflated,
                "corrections_since_apply": self._corrections_since_apply,
            },
        )
        return result

    # ------------------------------------------------------------------
    # Join point 1: corrections bypass the consult-policy value gate
    # ------------------------------------------------------------------

    def has_protocol_signal(self, agent_id: str) -> bool:
        """True when a trusted human has corrected this agent.

        The agent's workspace carries correction-derived knowledge; the value
        gate must never suppress rendering it (suppression is for unhelpful,
        corrections mark wrong — they render regardless of the self-EMA).
        """
        state = self._agents.get(str(agent_id))
        return bool(state and state.corrections_accepted > 0)

    # ------------------------------------------------------------------
    # Join point 2: role-scaled evidence threshold for the self-EMA gate
    # ------------------------------------------------------------------

    def evidence_multiplier(self, agent_id: str, cache: bool = True) -> float:
        """How much episode evidence this agent's self-EMA needs (× base).

        Reads the agent's org status (``AgentRegistry.status`` — the ladder
        the adjudication pipeline itself maintains) on a short TTL cache.
        Any failure → 1.0 (today's behavior; the gate gets stricter, never
        looser, from this module).
        """
        agent_id = str(agent_id)
        state = self._agents.setdefault(agent_id, AgentTrustState())
        now = time.time()
        if (not cache) or state.role is None or \
                (now - state.role_checked_at) > _ROLE_CACHE_TTL:
            try:
                state.role = self._read_role(agent_id)
            except Exception as e:  # DB unavailable: fail open, retry next TTL
                logger.debug("bpe trust bridge: role read failed: %s", e)
                state.role = None
            state.role_checked_at = now
        return ROLE_EPISODE_MULTIPLIER.get(
            str(state.role or ""), _UNKNOWN_ROLE_MULTIPLIER)

    @staticmethod
    def _read_role(agent_id: str) -> Optional[str]:
        try:
            from core.database import SessionLocal
            from core.models import AgentRegistry

            with SessionLocal() as db:
                row = db.query(AgentRegistry.status).filter(
                    AgentRegistry.id == agent_id).first()
            status = str(row[0] or "").strip().lower() if row else ""
            return status or None
        except Exception as e:  # never let trust state break the hot path
            logger.debug("bpe trust bridge: role read skipped: %s", e)
            return None

    # ------------------------------------------------------------------
    # Join point 3: evolution veto
    # ------------------------------------------------------------------

    def evolution_veto(self) -> Tuple[bool, str]:
        """Hold ``apply_best`` while accepted corrections await incorporation.

        Corrections landed after the last genome application mean the fitness
        landscape the population searched is stale by the human channel's
        lights; the next application waits for fresh trials (automation
        retries on the next finished run). Returns (vetoed, reason).
        """
        if self._corrections_since_apply > 0:
            return (True,
                    f"{self._corrections_since_apply} adjudicated correction(s) "
                    "since last genome apply")
        return (False, "")

    def mark_applied(self) -> None:
        """Clear the veto window (called after a successful genome apply)."""
        self._corrections_since_apply = 0

    # ------------------------------------------------------------------
    # De-inflation (adjudicated channel ONLY — never self-judged)
    # ------------------------------------------------------------------

    def _deinflate_agent_workspaces(self, agent_id: str,
                                    original_output: str,
                                    user_correction: str) -> int:
        """Demote Experience entries that overlap the rejected output.

        Runs across every cached workspace for this agent. Entries are
        demoted (``uses → 0``), not deleted: LFU eviction then removes them
        naturally, and a later contrary adjudication can re-earn usage.
        """
        if not (original_output or user_correction):
            return 0
        try:
            from core.bpe.workspace import iter_agent_workspaces

            demoted = 0
            for ws in iter_agent_workspaces(agent_id):
                demoted += deinflate_experience(ws, original_output,
                                                user_correction)
            return demoted
        except Exception as e:  # de-inflation must never break adjudication
            logger.debug("bpe trust bridge: de-inflate skipped: %s", e)
            return 0

    # ------------------------------------------------------------------

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        return {aid: s.to_dict() for aid, s in self._agents.items()}

    def pending_corrections(self) -> int:
        return self._corrections_since_apply


def deinflate_experience(ws: Any, original_output: str,
                         user_correction: str) -> int:
    """Demote Experience entries overlapping the rejected original output.

    Deterministic, keyword-based (same token model as ``ExperienceStore
    .recall``): an entry is suspect when it shares ≥ 2 tokens (len>2) with
    the rejected output and those cover ≥ 50% of its own tokens. The
    correction text itself is never a demotion signal — it is what the agent
    should have done, not evidence about which stored knowledge misled it.
    """
    bad_tokens = _tokens(original_output) - _tokens(user_correction)
    if not bad_tokens:
        return 0
    demoted = 0
    for bucket in ws.experience._categories.values():
        for entry in bucket.values():
            e_tokens = _tokens(entry.content)
            if not e_tokens:
                continue
            shared = len(e_tokens & bad_tokens)
            if shared >= DEINFLATE_MIN_SHARED_TOKENS and \
                    shared / len(e_tokens) >= DEINFLATE_MIN_SHARE:
                entry.uses = 0  # LFU will evict naturally
                demoted += 1
    return demoted


def _tokens(text: str) -> set:
    return {t for t in str(text or "").lower().split() if len(t) > 2}


# Module-level singleton — same lifetime as consult_policy/population.
trust_bridge = TrustBridge()


def get_trust_bridge() -> TrustBridge:
    return trust_bridge


def record_adjudication(agent_id: str, accepted: bool, is_correction: bool,
                        original_output: str = "",
                        user_correction: str = "") -> Dict[str, Any]:
    """Singleton convenience wrapper (the adjudication seam's entry point)."""
    return get_trust_bridge().record_adjudication(
        agent_id, accepted, is_correction,
        original_output=original_output, user_correction=user_correction)


def evolution_veto() -> Tuple[bool, str]:
    """Singleton wrapper for :meth:`TrustBridge.evolution_veto`."""
    return get_trust_bridge().evolution_veto()


def mark_applied() -> None:
    """Singleton wrapper for :meth:`TrustBridge.mark_applied`."""
    get_trust_bridge().mark_applied()


def reset_trust() -> None:
    """Test helper: clear trust state."""
    global trust_bridge
    trust_bridge = TrustBridge()
