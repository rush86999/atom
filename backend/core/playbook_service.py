"""Playbooks — company processes as procedural memory (Installation
Adaptation Plan Phase 3). A playbook is a structured, versioned,
supervisor-approved object: when a draft applies (canvas type + keywords),
which steps to follow, which template questions to ask, worked examples.

Capture paths:
  * authored — wizard/API (supervisor types it once);
  * taught   — /teach upgraded: imperative lessons become structured drafts;
  * learned  — sleep-time drafts from recurring correction patterns
               (see exchange_memory_maintenance._draft_playbooks) and
               correction reflection (core/correction_reflection_service).

Rollout mirrors ATOM_EXCHANGE_MEMORY: runtime setting ATOM_PLAYBOOKS —
  off    → nothing enters prompts;
  shadow → approved playbooks render as a prompt leg (advisory);
  enforce→ (reserved) send/edit gates consult coverage.
Default is `shadow`: advisory presence only, never a hard gate.
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MODE_OFF, _MODE_SHADOW, _MODE_ENFORCE = "off", "shadow", "enforce"


def playbook_mode() -> str:
    """off | shadow | enforce — env > runtime_settings DB row > default."""
    try:
        from core.runtime_settings import get_setting
        mode = str(get_setting("ATOM_PLAYBOOKS", _MODE_SHADOW) or _MODE_SHADOW)
    except Exception:
        return _MODE_SHADOW
    return mode if mode in (_MODE_OFF, _MODE_SHADOW, _MODE_ENFORCE) else _MODE_SHADOW


def eval_gate_mode(db=None) -> str:
    """ATOM_PLAYBOOK_EVAL_GATE: off | shadow | enforce (default shadow).
    WikiSkill W5 — replay a draft's related incident evals at approval time;
    only `enforce` can block the promotion (the paper's strict gate, minus
    the failure mode where neutral proposals deadlock: skips never block)."""
    try:
        from core.runtime_settings import get_setting
        mode = str(get_setting("ATOM_PLAYBOOK_EVAL_GATE", "shadow", db=db) or "shadow").lower()
    except Exception:
        return "shadow"
    return mode if mode in (_MODE_OFF, _MODE_SHADOW, _MODE_ENFORCE) else "shadow"


class PlaybookService:
    def __init__(self, db, tenant_id: str = "default",
                 workspace_id: str = "default"):
        self.db = db
        self.tenant_id = tenant_id
        self.workspace_id = workspace_id or "default"

    # ── CRUD ──
    def create(self, name: str, *, description: str = "",
               trigger_canvas_type: Optional[str] = None,
               trigger_keywords: Optional[List[str]] = None,
               steps: Optional[List[str]] = None,
               template_questions: Optional[List[str]] = None,
               examples: Optional[List[Any]] = None,
               source: str = "authored",
               approval_state: str = "approved",
               created_by: Optional[str] = None,
               fingerprint: Optional[str] = None,
               origin_ids: Optional[List[str]] = None) -> Any:
        from core.models import Playbook

        row = Playbook(
            tenant_id=self.tenant_id,
            workspace_id=self.workspace_id,
            name=name,
            description=description,
            trigger_canvas_type=trigger_canvas_type,
            trigger_keywords=trigger_keywords or [],
            steps=steps or [],
            template_questions=template_questions or [],
            examples=examples or [],
            source=source,
            approval_state=approval_state,
            created_by=created_by,
            fingerprint=fingerprint,
            origin_ids=origin_ids or [],
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list(self, include_drafts: bool = False) -> List[Any]:
        from core.models import Playbook

        q = self.db.query(Playbook).filter(
            Playbook.tenant_id == self.tenant_id)
        if not include_drafts:
            q = q.filter(Playbook.approval_state == "approved")
        return q.order_by(Playbook.updated_at.desc()).all()

    def get(self, playbook_id: str) -> Optional[Any]:
        from core.models import Playbook

        return self.db.query(Playbook).filter(
            Playbook.id == playbook_id,
            Playbook.tenant_id == self.tenant_id,
        ).first()

    def set_state(self, playbook_id: str, state: str,
                  actor: Optional[str] = None) -> Optional[Any]:
        row = self.get(playbook_id)
        if row is None:
            return None
        if state == "approved":
            row.approval_state = "approved"
            row.approved_by = actor
        elif state == "retired":
            row.approval_state = "retired"
        elif state == "draft":
            row.approval_state = "draft"
        else:
            return None
        self.db.commit()
        return row

    # ── approval WITH the WikiSkill validation gate (W5) ──
    async def approve(self, playbook_id: str, actor: Optional[str] = None,
                      llm_service: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """The gated draft → approved promotion: replay the incident evals
        the draft originated from (``origin_ids``) before acceptance.

        WikiSkill accepts a skill change only on strict validation
        improvement; the analog here — related evals must not FAIL (skips
        never block — a case that cannot run is not evidence of regression).
        shadow records the replay and approves anyway; enforce blocks while
        any related eval fails (the draft stays `draft`, the wiki layer —
        its origin evals — stays intact either way).

        Returns None when the playbook does not exist, else
        {approved, playbook, eval_gate}.
        """
        row = self.get(playbook_id)
        if row is None:
            return None

        mode = eval_gate_mode()
        gate: Optional[Dict[str, Any]] = None
        if mode != _MODE_OFF:
            eval_ids = [oid for oid in (row.origin_ids or [])
                        if isinstance(oid, str)]
            if eval_ids:
                gate = await self._replay_origin_evals(eval_ids, llm_service)
                row.last_eval_result = gate

        if mode == _MODE_ENFORCE and gate and gate.get("failed", 0) > 0:
            self.db.commit()  # persist last_eval_result; row stays draft
            return {"approved": False, "playbook": row, "eval_gate": gate}

        row.approval_state = "approved"
        row.approved_by = actor
        self.db.commit()
        return {"approved": True, "playbook": row, "eval_gate": gate}

    async def _replay_origin_evals(self, eval_ids: List[str],
                                   llm_service: Optional[Any]) -> Dict[str, Any]:
        from core.incident_eval_runner import run_evals

        summary = await run_evals(self.db, tenant_id=self.tenant_id,
                                  limit=len(eval_ids),
                                  llm_service=llm_service,
                                  eval_ids=eval_ids)
        return {
            "ran": summary.get("ran", 0),
            "passed": summary.get("passed", 0),
            "failed": summary.get("failed", 0),
            "skipped": summary.get("skipped", 0),
            "results": summary.get("results", []),
        }

    # ── capture path: /teach upgrade ──
    def create_from_teach(self, lesson_text: str, *,
                          agent_id: Optional[str] = None,
                          trigger_canvas_type: Optional[str] = None) -> Any:
        """Turn an imperative lesson ("always ask material and dimensions
        before quoting voltage") into a structured draft playbook: the
        sentence becomes the first step; question-shaped sentences become
        template questions. Drafts need explicit approval."""
        sentences = [s.strip() for s in re.split(r"(?<=[.!?\n])\s+", lesson_text) if s.strip()]
        questions = [s for s in sentences if s.endswith("?")]
        steps = [s for s in sentences if not s.endswith("?")]
        name = (steps[0] if steps else lesson_text)[:80].rstrip()
        return self.create(
            name=name or "Taught process",
            description=f"Captured from /teach (agent={agent_id or 'n/a'})",
            trigger_canvas_type=trigger_canvas_type,
            steps=steps,
            template_questions=questions,
            source="taught",
            approval_state="draft",
            created_by=agent_id,
        )

    # ── capture path: sleep-time draft from a recurring pattern ──
    def find_by_pattern(self, pattern_text: str) -> Optional[Any]:
        """The draft a pattern fingerprint would map to, if any."""
        from core.models import Playbook

        fp = self._pattern_fingerprint(pattern_text)
        return self.db.query(Playbook).filter(
            Playbook.fingerprint == fp).first()

    def _pattern_fingerprint(self, pattern_text: str) -> str:
        return hashlib.sha1(
            f"pattern|{self.tenant_id}|{(pattern_text or '')[:200]}".encode()
        ).hexdigest()

    def draft_from_pattern(self, pattern_text: str,
                           trigger_canvas_type: Optional[str] = None,
                           origin_id: Optional[str] = None) -> Optional[Any]:
        """Idempotent: the pattern's fingerprint dedups — a recurring
        pattern bumps the existing draft's version instead of stacking
        duplicate rows."""
        from core.models import Playbook

        fp = self._pattern_fingerprint(pattern_text)
        existing = self.db.query(Playbook).filter(
            Playbook.fingerprint == fp).first()
        if existing is not None:
            existing.version = (existing.version or 1) + 1
            self.db.commit()
            return existing
        name = (pattern_text or "Recurring correction pattern")[:80].strip()
        return self.create(
            name=name,
            description="Auto-drafted from recurring supervisor corrections "
                        "(sleep-time). Review, edit, then approve.",
            trigger_canvas_type=trigger_canvas_type,
            steps=[pattern_text[:500]] if pattern_text else [],
            source="learned",
            approval_state="draft",
            fingerprint=fp,
            origin_ids=[origin_id] if origin_id else [],
        )

    # ── retrieval into prompts ──
    def get_relevant(self, message: str, canvas_type: Optional[str] = None,
                     limit: int = 2) -> List[Dict[str, Any]]:
        """Approved playbooks whose trigger matches the turn, keyword-scored.
        Keyword scoring (not embeddings) keeps this leg deterministic and
        cheap; the assembler reranker can reorder later if needed."""
        if playbook_mode() == _MODE_OFF:
            return []
        rows = self.list(include_drafts=False)
        scored: List[tuple] = []
        msg_norm = re.sub(r"[^a-z0-9\s]", " ", (message or "").lower())
        msg_l = f" {msg_norm} "
        for row in rows:
            keywords = [str(kw).lower().strip()
                        for kw in row.trigger_keywords or [] if str(kw).strip()]
            hits = sum(1 for kw in keywords if kw in msg_l)
            # A playbook with keywords needs at least one hit; a playbook
            # with NO keywords matches its canvas type alone. Canvas-type
            # match alone never justifies a keyworded playbook.
            if keywords and hits == 0:
                continue
            if not keywords and not (canvas_type and row.trigger_canvas_type
                                     and row.trigger_canvas_type.lower() == canvas_type.lower()):
                continue
            score = 1.0 * hits
            if canvas_type and row.trigger_canvas_type and \
                    row.trigger_canvas_type.lower() == canvas_type.lower():
                score += 2.0
            scored.append((score, row))
        scored.sort(key=lambda t: (-t[0], t[1].name))
        return [
            {
                "name": row.name,
                "description": row.description or "",
                "steps": row.steps or [],
                "template_questions": row.template_questions or [],
            }
            for _score, row in scored[:limit]
        ]
