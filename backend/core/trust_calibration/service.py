"""DB adapters: load binary human decisions as calibration observations.

Sources (plan §1):
- HITLAction rows with status approved/rejected (decided_at = reviewed_at
  or created_at)
- AgentProposal rows with status approved/rejected (decided_at =
  approved_at or reviewed_at or created_at)

Each observation carries RAW fields; the gateway turns them into kernel
vectors (features.py) so adapters stay cheap and testable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Observation:
    source: str                      # "hitl" | "proposal"
    action_type: str
    platform: str = "internal"
    agent_id: Optional[str] = None
    approved: bool = False
    decided_at: Optional[datetime] = None
    y: int = field(default=0)        # +1 / -1, filled by finalize()

    def finalize(self) -> "Observation":
        self.y = 1 if self.approved else -1
        return self

    @property
    def age_days(self) -> float:
        return _age_days(self.decided_at)


def _age_days(dt: Optional[datetime]) -> float:
    if dt is None:
        return 0.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt
    return max(delta.total_seconds() / 86400.0, 0.0)


def load_decisions(db, limit: int = 400) -> List[Observation]:
    """Union of the two decision streams, newest-first per stream.

    Never raises: missing tables / schema drift degrade to whatever loads.
    """
    out: List[Observation] = []
    half = max(limit // 2, 10)

    try:
        from core.models import HITLAction, HITLActionStatus

        rows = (
            db.query(HITLAction)
            .filter(
                HITLAction.status.in_([
                    HITLActionStatus.APPROVED.value,
                    HITLActionStatus.REJECTED.value,
                ])
            )
            .order_by(HITLAction.reviewed_at.desc(), HITLAction.created_at.desc())
            .limit(half)
            .all()
        )
        for r in rows:
            out.append(Observation(
                source="hitl",
                action_type=r.action_type or "unknown",
                platform=(r.platform or "internal"),
                agent_id=r.agent_id,
                approved=(r.status == HITLActionStatus.APPROVED.value),
                decided_at=r.reviewed_at or r.created_at,
            ).finalize())
    except Exception as e:  # noqa: BLE001
        logger.debug(f"trust calibration: hitl stream unavailable: {e}")

    try:
        from core.models import AgentProposal, ProposalStatus

        rows = (
            db.query(AgentProposal)
            .filter(
                AgentProposal.status.in_([
                    ProposalStatus.APPROVED.value,
                    ProposalStatus.REJECTED.value,
                ])
            )
            .order_by(
                AgentProposal.approved_at.desc(), AgentProposal.created_at.desc()
            )
            .limit(half)
            .all()
        )
        for r in rows:
            data = r.proposed_action if isinstance(r.proposed_action, dict) else {}
            action_type = (
                data.get("action_type")
                or data.get("tool")
                or (r.title or "proposal")[:60]
            )
            decided = r.approved_at or r.reviewed_at or r.created_at
            out.append(Observation(
                source="proposal",
                action_type=str(action_type),
                platform="internal",
                agent_id=r.agent_id,
                approved=(r.status == ProposalStatus.APPROVED.value),
                decided_at=decided,
            ).finalize())
    except Exception as e:  # noqa: BLE001
        logger.debug(f"trust calibration: proposal stream unavailable: {e}")

    return out


def age_days_of(obs: Observation) -> float:
    return _age_days(obs.decided_at)
