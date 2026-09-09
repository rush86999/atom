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
import math
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MODE_OFF, _MODE_SHADOW, _MODE_ENFORCE = "off", "shadow", "enforce"


# ── dense recall (hybrid retrieval) ────────────────────────────────────────
# Calibration (BAAI/bge-small-en-v1.5, measured 2026-09-08 over playbook-
# shaped docs vs message-shaped queries): related cosines 0.58–0.77,
# unrelated 0.40–0.63 — the ranges overlap, so the floor favors RECALL and
# ranking separates: a true paraphrase (≈0.7+) scores well above a stray
# near-miss (≈0.5–0.63), and the prompt leg is advisory + capped at 2
# either way. Weight 1.5 keeps a literal keyword hit (1.0) roughly equal to
# a strong dense match instead of letting weak-moderate similarity (0.55–
# 0.6 → 0.83–0.9) outrank the user having actually said the word.
_DENSE_FLOOR = 0.55
_DENSE_WEIGHT = 1.5


class _LocalEmbedder:
    """Sync local embeddings for playbook dense recall — fastembed ONLY.

    Deliberately no EmbeddingService instance: its __init__ also builds an
    LLMService, and a paid/cloud call would put latency and cost on the
    prompt-assembly hot path. When the configured provider isn't fastembed
    (or fastembed isn't installed) the backend reports unavailable and
    retrieval degrades to trigger keywords / canvas type — never fails the
    turn. Model load (seconds, ONNX) and embed are blocking, so async
    callers wrap them in to_thread; the ONNX client itself is process-cached
    per model inside EmbeddingService."""

    def __init__(self) -> None:
        self.model: Optional[str] = None
        self._client: Any = None
        try:
            provider = (os.getenv("EMBEDDING_PROVIDER", "fastembed")
                        or "fastembed").strip().lower()
            if provider == "local":  # same alias EmbeddingService honors
                provider = "fastembed"
            if provider != "fastembed":
                return
            try:
                import fastembed  # noqa: F401
            except Exception:
                return
            from core.embedding_service import EmbeddingService
            self.model = EmbeddingService.default_fastembed_model()
        except Exception as e:  # never raise from embedder construction
            logger.debug(f"playbook embedder unavailable: {e}")
            self.model = None

    @property
    def available(self) -> bool:
        return bool(self.model)

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not self.model:
            raise RuntimeError("playbook embedder unavailable")
        if self._client is None:
            from core.embedding_service import EmbeddingService
            self._client = EmbeddingService._load_fastembed_client(self.model)
        return [v.tolist() for v in self._client.embed(list(texts))]


_EMBEDDING_BACKEND: Optional[_LocalEmbedder] = None


def _shared_embedding_backend() -> _LocalEmbedder:
    """Process-wide embedder: PlaybookService is constructed per call site
    (every turn), but the embedder holds no per-tenant state — one is
    enough, and this keeps the INFO/LLMService-free construction to once."""
    global _EMBEDDING_BACKEND
    if _EMBEDDING_BACKEND is None:
        _EMBEDDING_BACKEND = _LocalEmbedder()
    return _EMBEDDING_BACKEND


def _playbook_document(row: Any) -> str:
    """The canonical text embedded for a playbook: everything a matching
    request could semantically resemble — name, description, steps,
    template questions, and the trigger keywords themselves."""
    parts = [getattr(row, "name", "") or "", getattr(row, "description", "") or ""]
    parts += [str(s) for s in (getattr(row, "steps", None) or [])]
    parts += [str(q) for q in (getattr(row, "template_questions", None) or [])]
    parts += [str(k) for k in (getattr(row, "trigger_keywords", None) or [])]
    return "\n".join(p for p in parts if p)


def _cosine(a: Optional[List[float]], b: Optional[List[float]]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / math.sqrt(na * nb)


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
                 workspace_id: str = "default",
                 embedding_backend: Optional[Any] = None):
        self.db = db
        self.tenant_id = tenant_id
        self.workspace_id = workspace_id or "default"
        # Tests inject a fake; production lazily builds the shared local
        # embedder on first use (see embedding_backend property).
        self._injected_backend = embedding_backend
        self._embedding_backend: Optional[Any] = embedding_backend

    @property
    def embedding_backend(self) -> Optional[Any]:
        if self._embedding_backend is None:
            self._embedding_backend = _shared_embedding_backend()
        return self._embedding_backend

    # ── embeddings ──
    def _refresh_embedding(self, row: Any) -> None:
        """Best-effort: embed the playbook document at write time so reads
        don't pay for it. Failure leaves the columns NULL — retrieval falls
        back to trigger keywords / canvas type, and the next read backfills.
        A backend that is merely unavailable (no fastembed, cloud provider)
        is a no-op, not an error."""
        backend = self.embedding_backend
        if backend is None or not getattr(backend, "available", False):
            return
        try:
            vec = backend.embed([_playbook_document(row)])[0]
            row.embedding = vec
            row.embedding_model = getattr(backend, "model", None)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.debug(f"playbook embedding refresh skipped: {e}")

    def _row_embedding(self, row: Any) -> Optional[List[float]]:
        """Stored embedding for a playbook, backfilling when missing or
        computed by a different model than the current backend (cross-model
        cosine is meaningless). Returns None when unavailable: the row
        still competes on keywords / canvas triggers alone."""
        backend = self.embedding_backend
        if backend is None or not getattr(backend, "available", False):
            return None
        model_name = getattr(backend, "model", None)
        if row.embedding and row.embedding_model == model_name:
            return row.embedding
        try:
            vec = backend.embed([_playbook_document(row)])[0]
        except Exception as e:
            logger.debug(f"playbook embedding backfill skipped: {e}")
            return None
        try:
            row.embedding = vec
            row.embedding_model = model_name
            self.db.commit()
        except Exception as e:
            self.db.rollback()  # usable this turn even if persistence failed
            logger.debug(f"playbook embedding backfill persist skipped: {e}")
        return vec

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
        self._refresh_embedding(row)
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
                           origin_id: Optional[str] = None,
                           steps: Optional[List[str]] = None,
                           description: Optional[str] = None) -> Optional[Any]:
        """Idempotent: the pattern's fingerprint dedups — a recurring
        pattern bumps the existing draft's version instead of stacking
        duplicate rows. ``steps``/``description`` let callers draft real
        review content (the rule the corrections imply); defaults keep the
        legacy pattern-text-is-the-draft behavior."""
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
            description=description or (
                "Auto-drafted from recurring supervisor corrections "
                "(sleep-time). Review, edit, then approve."),
            trigger_canvas_type=trigger_canvas_type,
            steps=steps if steps is not None else ([pattern_text[:500]] if pattern_text else []),
            source="learned",
            approval_state="draft",
            fingerprint=fp,
            origin_ids=[origin_id] if origin_id else [],
        )

    # ── retrieval into prompts ──
    def get_relevant(self, message: str, canvas_type: Optional[str] = None,
                     limit: int = 2) -> List[Dict[str, Any]]:
        """Approved playbooks whose trigger matches the turn — HYBRID
        retrieval: trigger keywords/canvas type PLUS dense (embedding)
        recall. Gating keyworded playbooks on a literal keyword hit silently
        skipped approved processes whenever the request paraphrased them
        ("chase the supplier about the unpaid one" vs keyword "invoice"), so
        keywords are now a BOOST, not a gate: a playbook is considered on a
        keyword hit, a canvas-type match, or strong semantic similarity
        (_DENSE_FLOOR). Embedding is local fastembed, computed/stored at
        write time and lazily backfilled on read; any embedding failure
        degrades to triggers-only scoring, never fails the turn. Keyword
        scoring stays deterministic and cheap."""
        if playbook_mode() == _MODE_OFF:
            return []
        rows = self.list(include_drafts=False)
        if not rows:
            return []
        backend = self.embedding_backend
        msg_vec: Optional[List[float]] = None
        if backend is not None and getattr(backend, "available", False) \
                and (message or "").strip():
            try:
                msg_vec = backend.embed([message])[0]
            except Exception as e:
                logger.debug(f"playbook query embedding skipped: {e}")
                msg_vec = None
        msg_norm = re.sub(r"[^a-z0-9\s]", " ", (message or "").lower())
        msg_l = f" {msg_norm} "
        scored: List[tuple] = []
        best_dense = 0.0
        for row in rows:
            dense = _cosine(msg_vec, self._row_embedding(row))
            best_dense = max(best_dense, dense)
            keywords = [str(kw).lower().strip()
                        for kw in row.trigger_keywords or [] if str(kw).strip()]
            hits = sum(1 for kw in keywords if kw in msg_l)
            canvas_match = bool(
                canvas_type and row.trigger_canvas_type
                and row.trigger_canvas_type.lower() == canvas_type.lower())
            # Recall: keyword hit OR canvas-type match OR strong dense
            # similarity. A keyworded playbook with zero hits AND weak
            # similarity still stays out — keywords keep excluding noise.
            if hits == 0 and not canvas_match and dense < _DENSE_FLOOR:
                continue
            score = 1.0 * hits + _DENSE_WEIGHT * dense
            if canvas_match:
                score += 2.0
            scored.append((score, row))
        scored.sort(key=lambda t: (-t[0], t[1].name))
        if logger.isEnabledFor(logging.DEBUG):
            top = [(round(s, 2), r.name) for s, r in scored[:limit]]
            logger.debug(
                "playbook retrieval: approved=%d matched=%d dense_best=%.2f "
                "canvas_type=%s top=%s",
                len(rows), len(scored), best_dense, canvas_type, top,
            )
        return [
            {
                # id rides along so the co-editor result can surface
                # matched_playbooks the UI can deep-link (Playbook Journey P3)
                "id": row.id,
                "name": row.name,
                "description": row.description or "",
                "steps": row.steps or [],
                "template_questions": row.template_questions or [],
            }
            for _score, row in scored[:limit]
        ]

    # ── draft editing (Playbook Journey P1: "Edit steps first") ──
    def update(self, playbook_id: str, *, name: Optional[str] = None,
               description: Optional[str] = None,
               trigger_canvas_type: Optional[str] = ...,
               trigger_keywords: Optional[List[str]] = None,
               steps: Optional[List[str]] = None,
               template_questions: Optional[List[str]] = None) -> Optional[Any]:
        """Supervisor edits a DRAFT before approving it. Approved playbooks
        are versioned objects — editing those goes through retire + re-draft,
        so this returns None for them (the route maps it to 409)."""
        row = self.get(playbook_id)
        if row is None or row.approval_state != "draft":
            return None
        if name is not None:
            row.name = name
        if description is not None:
            row.description = description
        if trigger_canvas_type is not ...:
            row.trigger_canvas_type = trigger_canvas_type
        if trigger_keywords is not None:
            row.trigger_keywords = trigger_keywords
        if steps is not None:
            row.steps = steps
        if template_questions is not None:
            row.template_questions = template_questions
        self.db.commit()
        self.db.refresh(row)
        self._refresh_embedding(row)  # content changed → refresh the vector
        return row
