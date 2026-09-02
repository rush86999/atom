"""Correction reflection — every supervisor correction drafts the RULE it
implies (Installation Adaptation Plan Phase 4). Deterministic v1: the
failure taxonomy provides the rule template and the diff provides the
concrete token, so a lesson exists even with no LLM available. The draft
is a Playbook (source=learned, approval_state=draft) — the supervisor
confirms it in the training surface with one click; drafts never enter
prompts on their own.

Dedup: the fingerprint is (taxonomy + canvas_type + key token) — the same
lesson recurring BUMPS the existing draft instead of stacking rows.
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, Optional

from core.failure_taxonomy import _ASSERT_RE, _plain

logger = logging.getLogger(__name__)

_RULE_TEMPLATES = {
    "grounding": (
        "Grounding: do not state {token} as established fact. Prefer hedged "
        "wording ('we are confirming {token} and will follow up') unless the "
        "installation facts registry contains it."
    ),
    "identity": (
        "Identity: the sender's name/signature is {token}-free — never sign "
        "or address using names guessed from To/Cc fields."
    ),
    "persistence": (
        "Persistence: report honestly when an edit changes nothing; never "
        "claim an update for identical content."
    ),
    "process": (
        "Process: include the supervisor's required questions/steps "
        "({token}) in drafts of this kind before sending."
    ),
    "tone": (
        "Style: keep the supervisor's wording — {token} — in future drafts."
    ),
    "other": (
        "Follow the supervisor's corrected version for {token}."
    ),
}


def _key_token(original: Any, corrected: Any, taxonomy: str) -> str:
    before, after = _plain(original), _plain(corrected)
    if taxonomy == "grounding":
        claim = next((m.group(0) for m in _ASSERT_RE.finditer(before)), "")
        return claim or "unverified claim"
    if taxonomy == "identity":
        before_names = re.findall(r"\b[A-Z][a-z]{2,}\b", before[-400:])
        after_names = set(re.findall(r"\b[A-Z][a-z]{2,}\b", after[-400:]))
        removed = [n for n in before_names if n not in after_names]
        return removed[0] if removed else "sender name"
    if taxonomy == "process":
        before_lines = {ln.strip().lower() for ln in before.splitlines() if ln.strip()}
        added = [ln.strip() for ln in after.splitlines()
                 if ln.strip() and ln.strip().lower() not in before_lines]
        return (added[0][:60] if added else "template steps")
    bw = set(before.lower().split())
    aw = set(after.lower().split())
    changed = list((bw - aw) | (aw - bw))
    return (changed[0] if changed else "wording")[:60]


def reflect_on_correction(
    db,
    tenant_id: str,
    canvas_id: str,
    canvas_type: str,
    original: Any,
    corrected: Any,
    taxonomy: str,
    instruction: Optional[str] = None,
) -> Optional[Any]:
    """Create-or-bump the draft lesson playbook for one correction.
    Fault-isolated by the caller; returns the Playbook row or None."""
    from core.models import Playbook
    from core.playbook_service import PlaybookService

    token = _key_token(original, corrected, taxonomy)
    template = _RULE_TEMPLATES.get(taxonomy, _RULE_TEMPLATES["other"])
    rule = template.format(token=token)

    fingerprint = hashlib.sha1(
        f"reflection|{tenant_id}|{taxonomy}|{(canvas_type or '')}|{token.lower()}".encode()
    ).hexdigest()

    existing = db.query(Playbook).filter(
        Playbook.fingerprint == fingerprint).first()
    if existing is not None:
        existing.version = (existing.version or 1) + 1
        db.commit()
        return existing

    svc = PlaybookService(db, tenant_id=tenant_id)
    hint = (instruction or "no instruction recorded")[:160]
    return svc.create(
        name=f"[{taxonomy}] {token}"[:80],
        description=(
            f"Drafted by correction reflection on canvas {canvas_id[:8]}… "
            f"({hint}). Review and approve to make it a standing rule."
        ),
        trigger_canvas_type=canvas_type,
        steps=[rule],
        source="learned",
        approval_state="draft",
        fingerprint=fingerprint,
    )
