"""Installation profile — per-install knowledge as DATA (Installation
Adaptation Plan Phase 1, docs/architecture/INSTALLATION_ADAPTATION_PLAN.md).

A new installation's identity, people/roles, reusable templates, and facts
registry live here, editable via the wizard/API. Consumers: the canvas
editor's SENDER IDENTITY section (chat_orchestrator._sender_identity), the
grounded-send gate (core/send_grounding.py), and the install report. Code
fixes failure classes once; THIS table holds the per-install values.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SECTION_KEYS = ("identity", "people", "templates", "facts")


class InstallationProfileService:
    """Tenant-scoped accessor over the single InstallationProfile row.
    Fault-tolerant reads (a missing table must not break a chat turn)."""

    def __init__(self, db):
        self.db = db

    def get_or_create(self, tenant_id: str = "default",
                      workspace_id: Optional[str] = None):
        from core.models import InstallationProfile

        row = self.db.query(InstallationProfile).filter(
            InstallationProfile.tenant_id == tenant_id
        ).first()
        if row is None:
            row = InstallationProfile(
                tenant_id=tenant_id,
                workspace_id=workspace_id or "default",
            )
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
        return row

    def get_payload(self, tenant_id: str = "default") -> Dict[str, Any]:
        """Dict payload for prompts/API — safe on any failure (empty)."""
        try:
            row = self.get_or_create(tenant_id)
            return {
                "identity": row.identity or {},
                "people": row.people or [],
                "templates": row.templates or [],
                "facts": row.facts or [],
            }
        except Exception as e:
            logger.debug(f"installation profile read skipped: {e}")
            return {"identity": {}, "people": [], "templates": [], "facts": []}

    def update_payload(self, tenant_id: str, payload: Dict[str, Any],
                       workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """Merge-write: sections present in the payload replace; absent
        sections keep their values. Unknown keys are ignored."""
        row = self.get_or_create(tenant_id, workspace_id)
        for key in _SECTION_KEYS:
            if key in payload:
                setattr(row, key, payload.get(key) or (list() if key != "identity" else dict()))
        if workspace_id and not row.workspace_id:
            row.workspace_id = workspace_id
        self.db.commit()
        return self.get_payload(tenant_id)

    # ── facts registry helpers (consumed by the grounded-send gate) ──

    @staticmethod
    def normalize_claim(text: str) -> str:
        """Lowercase, strip punctuation/whitespace — claim matching is
        semantic-ish normalization, not exact bytes ('480V 3-phase' ==
        '480v three phase' normalizes the voltage token)."""
        t = (text or "").lower().strip()
        t = re.sub(r"[^a-z0-9\s]", " ", t)
        t = re.sub(r"\bthree\b", "3", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    @staticmethod
    def claims_match(claim: str, fact_claim: str) -> bool:
        """A fact covers a claim when every distinctive fact token appears
        in the claim (substring containment alone misses word-order
        differences: '480V 3-phase configuration available' vs 'available
        in 480V 3-phase configuration')."""
        a = set(InstallationProfileService.normalize_claim(claim).split())
        b = set(InstallationProfileService.normalize_claim(fact_claim).split())
        b = {t for t in b if len(t) >= 2}
        if not b:
            return False
        return b.issubset(a)

    def fact_allows(self, tenant_id: str, claim: str) -> Optional[Dict[str, Any]]:
        """The registry entry that covers `claim`, or None. Only VERIFIED
        facts count."""
        for fact in self.get_payload(tenant_id).get("facts") or []:
            if not (fact or {}).get("verified", True):
                continue
            if self.claims_match(claim, str(fact.get("claim") or "")):
                return fact
        return None

    def identity_for_prompts(self, tenant_id: str) -> Dict[str, str]:
        """Flat identity fields for the editor's SENDER IDENTITY section."""
        ident = (self.get_payload(tenant_id).get("identity") or {})
        out: Dict[str, str] = {}
        for key in ("company_name", "sender_name", "sender_email", "reply_to"):
            value = str(ident.get(key) or "").strip()
            if value:
                out[key] = value
        return out
