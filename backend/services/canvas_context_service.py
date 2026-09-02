"""
Canvas Context Service - Persists canvas state for agent learning and memory.

Canvas context captures the state of user interactions within a canvas session,
providing rich contextual data for agent learning and continuity across sessions.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import json
import logging
import uuid
from collections import OrderedDict
from sqlalchemy.orm import Session

from core.models import CanvasContext, AgentFeedback, FeedbackStatus

logger = logging.getLogger(__name__)

_EMBEDDING_SERVICE = None

# Profile tokens below this length and these common words carry no
# "same kind of task" signal for cross-canvas similarity. Shape words
# (subject/body/content/title) appear in EVERY serialized canvas and would
# otherwise inflate the union and dilute genuine task overlap.
_PROFILE_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "please", "can", "you",
    "your", "here", "draft", "email", "from", "was", "are", "have", "has",
    "not", "out", "how", "what", "when", "will", "would", "them", "they",
    "subject", "body", "content", "title", "type", "canvas_edit", "state",
    "com", "best", "regards", "hello",
}


def _tokenize_profile(text: str) -> set:
    """Significant lowercase tokens of a canvas profile text.

    Escaped-whitespace artifacts from JSON dumps (``\\n`` run together with
    the next word) are split first so ``nchandrakant``-style hybrids never
    poison the token sets."""
    import re as _re

    cleaned = (text or "").replace("\\n", " ").replace("\\t", " ").replace("\\r", " ")
    return {
        t for t in _re.findall(r"[a-z0-9]{3,}", cleaned.lower())
        if t not in _PROFILE_STOPWORDS
    }


def profile_similarity(a: str, b: str) -> float:
    """How much two canvas profiles talk about the same kind of task.

    Overlap coefficient ``|A∩B| / min(|A|,|B|)`` over significant tokens —
    the asymmetric-containment measure: a canvas veteran with 21 corrections
    legitimately holds a large vocabulary, and Jaccard's big union would
    bury a genuinely similar current canvas under it (observed live: a
    same-kind dealer draft scored 0.06 by Jaccard against the corrected
    WFS Ltd canvas). One profile being a subset of the other is a STRONG
    same-task signal, not dilution.

    Deterministic and deliberately NOT embedding-based: the LanceDB
    embedding path is not initialized in every deployment (sync embed
    returns None inside the event loop), and co-editor recall must work
    synchronously everywhere. This function is the seam: a vector-based
    scorer can replace it without touching the callers.
    """
    ta, tb = _tokenize_profile(a), _tokenize_profile(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def finalize_ranked_candidates(
    candidates: List[Dict[str, Any]],
    score_fn,
    now: datetime,
    min_score: float,
    limit: int,
) -> List[Dict[str, Any]]:
    """Shared scoring tail for episodic recall: relevance (via ``score_fn``)
    × a 14-day recency half-life (Generative Agents-style relevance×recency;
    corrections are high-importance by definition, so no separate importance
    term), min_score filter, best-first. Mutates nothing — returns new
    dicts with the corrections attached."""
    scored: List[Dict[str, Any]] = []
    for cand in candidates:
        relevance = score_fn(cand)
        if relevance < min_score:
            continue
        latest_ts = cand.get("latest_ts") or now
        age_days = max(0.0, (now - latest_ts).total_seconds()) / 86400.0
        recency = 0.5 ** (age_days / 14.0)
        scored.append({
            "canvas_id": cand["canvas_id"],
            "canvas_type": cand.get("canvas_type"),
            "similarity": round(relevance * recency, 4),
            "relevance": round(relevance, 4),
            "corrections": cand.get("corrections") or [],
        })
    scored.sort(key=lambda e: e["similarity"], reverse=True)
    return scored[:limit]


def _cosine(a, b) -> float:
    """Cosine similarity between two equal-length vectors (lists/arrays)."""
    try:
        import numpy as np

        va, vb = np.asarray(a, dtype="float32"), np.asarray(b, dtype="float32")
        na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return float(np.dot(va, vb) / (na * nb))
    except Exception:
        return 0.0


# Profile embeddings, keyed by content hash. Canvas profiles change rarely,
# and the recall fires on every co-editor turn — re-embedding 20 candidates
# of FastEmbed every turn is pure waste, while a bounded cache keeps memory
# flat. Far from an LRU-cache-of-one service: profiles are stable text.
_EMBED_CACHE: "OrderedDict[str, Any]" = OrderedDict()
_EMBED_CACHE_MAX = 256


async def _embed_text_cached(text: str) -> Optional[Any]:
    """FastEmbed vector for ``text`` via the shared EmbeddingService, with a
    content-hash LRU in front. None when embeddings are unavailable."""
    import hashlib

    try:
        key = hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()
        if key in _EMBED_CACHE:
            _EMBED_CACHE.move_to_end(key)
            return _EMBED_CACHE[key]
        svc = await _get_embedding_service()
        if svc is None:
            return None
        vec = await svc.create_fastembed_embedding(text)
        if vec is None:
            return None
        _EMBED_CACHE[key] = vec
        while len(_EMBED_CACHE) > _EMBED_CACHE_MAX:
            _EMBED_CACHE.popitem(last=False)
        return vec
    except Exception as e:
        logger.debug(f"profile embedding skipped: {e}")
        return None


async def _get_embedding_service():
    """The shared EmbeddingService (FastEmbed default: local, 384-dim,
    10-20ms/doc — part of the LanceDB vector ecosystem). None when the
    service or its model is unavailable on this deployment."""
    global _EMBEDDING_SERVICE
    if _EMBEDDING_SERVICE is not None:
        return _EMBEDDING_SERVICE
    try:
        from core.embedding_service import EmbeddingService

        _EMBEDDING_SERVICE = EmbeddingService(provider="fastembed")
        return _EMBEDDING_SERVICE
    except Exception as e:
        logger.debug(f"EmbeddingService unavailable for canvas recall: {e}")
        return None


async def rank_similar_canvas_candidates(
    current_profile: str,
    candidates: List[Dict[str, Any]],
    now: datetime,
    min_score: float = 0.25,
    limit: int = 2,
) -> List[Dict[str, Any]]:
    """Rank episodic-recall candidates SEMANTICALLY when embeddings are
    available (FastEmbed cosine — "enable LanceDB for semantic similarity"),
    falling back to the lexical overlap scorer otherwise. Same relevance ×
    recency tail as the lexical path."""
    score_fn = None
    if candidates:
        try:
            cur_vec = await _embed_text_cached(current_profile)
            if cur_vec is not None:
                cand_vecs = [await _embed_text_cached(c["profile_text"]) for c in candidates]
                if all(v is not None for v in cand_vecs):
                    vec_by_id = {
                        c["canvas_id"]: v for c, v in zip(candidates, cand_vecs)
                    }
                    score_fn = lambda cand: _cosine(
                        cur_vec, vec_by_id[cand["canvas_id"]])
                    logger.debug(
                        "canvas recall: semantic (FastEmbed) scoring over "
                        f"{len(candidates)} candidate(s)")
        except Exception as e:
            logger.debug(f"semantic scoring failed — falling back to lexical: {e}")
    if score_fn is None:
        score_fn = lambda cand: profile_similarity(current_profile, cand["profile_text"])
    return finalize_ranked_candidates(
        candidates, score_fn, now=now, min_score=min_score, limit=limit
    )


class CanvasContextService:
    """Manages canvas context for agent learning and memory."""

    def __init__(self, db: Session, tenant_id: Optional[str] = None):
        """
        Initialize the CanvasContextService.

        Args:
            db: Database session
            tenant_id: Optional tenant ID for multi-tenant filtering
        """
        self.db = db
        self.tenant_id = tenant_id or "default"
    
    def create_context(
        self,
        canvas_id: str,
        canvas_type: str,
        user_id: str,
        agent_id: Optional[str] = None,
        initial_state: Optional[dict] = None
    ) -> CanvasContext:
        """Create a new canvas context."""
        context = CanvasContext(
            canvas_id=canvas_id,
            tenant_id=self.tenant_id,
            canvas_type=canvas_type,
            user_id=user_id,
            agent_id=agent_id,
            current_state=initial_state or {}
        )

        self.db.add(context)
        self.db.commit()
        self.db.refresh(context)

        return context
    
    def get_context(
        self,
        canvas_id: str,
        user_id: str
    ) -> Optional[CanvasContext]:
        """Get existing context for a canvas."""
        query = self.db.query(CanvasContext).filter(
            CanvasContext.canvas_id == canvas_id,
            CanvasContext.user_id == user_id
        )
        if self.tenant_id:
            query = query.filter(CanvasContext.tenant_id == self.tenant_id)
        
        return query.first()
    
    def get_or_create_context(
        self,
        canvas_id: str,
        canvas_type: str,
        user_id: str,
        agent_id: Optional[str] = None
    ) -> CanvasContext:
        """Get existing context or create new one."""
        context = self.get_context(canvas_id, user_id)
        
        if not context:
            context = self.create_context(
                canvas_id=canvas_id,
                canvas_type=canvas_type,
                user_id=user_id,
                agent_id=agent_id
            )
        
        return context
    
    def update_state(
        self,
        canvas_id: str,
        user_id: str,
        state_update: dict
    ) -> bool:
        """Update current canvas state."""
        context = self.get_context(canvas_id, user_id)
        
        if not context:
            return False
        
        # Merge state update
        context.current_state = {**(context.current_state or {}), **state_update}
        context.last_activity_at = datetime.now(timezone.utc)
        
        self.db.commit()
        return True
    
    def add_action_to_history(
        self,
        canvas_id: str,
        user_id: str,
        action: dict
    ) -> bool:
        """Add an action to session history."""
        context = self.get_context(canvas_id, user_id)
        
        if not context:
            return False
        
        history = list(context.session_history or [])
        history.append({
            **action,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        context.session_history = history
        context.last_activity_at = datetime.now(timezone.utc)
        
        self.db.commit()
        return True
    
    def record_user_correction(
        self,
        canvas_id: str,
        user_id: str,
        original_action: dict,
        corrected_action: dict,
        context_info: Optional[str] = None
    ) -> bool:
        """
        Record a user correction for agent learning.
        """
        context = self.get_context(canvas_id, user_id)

        if not context:
            return False

        correction_data = {
            "original": original_action,
            "corrected": corrected_action,
            "context": context_info,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        corrections = list(context.user_corrections or [])
        corrections.append(correction_data)

        context.user_corrections = corrections
        context.last_activity_at = datetime.now(timezone.utc)

        self.db.commit()

        # Send to learning service for RLHF
        try:
            from core.agent_learning_enhanced import AgentLearningEnhanced

            # Extract agent_id from context if available
            agent_id = context.agent_id

            if agent_id:
                learning = AgentLearningEnhanced(self.db)

                # Create feedback record for the correction
                feedback = AgentFeedback(
                    agent_id=agent_id,
                    user_id=user_id,
                    tenant_id=self.tenant_id,
                    original_output=str(original_action),
                    user_correction=str(corrected_action),
                    input_context=f"canvas_id={canvas_id}; {context_info or ''}",
                    feedback_type='correction',
                    status=FeedbackStatus.PENDING.value if hasattr(FeedbackStatus, 'PENDING') else "pending",
                    created_at=datetime.now(timezone.utc)
                )

                self.db.add(feedback)
                self.db.commit()

                logger.info(f"[LEARNING] Recorded user correction for agent {agent_id}")

                # Training circuit: the correction is also a PERMANENT
                # work-time lesson ("human_correction" observations are
                # injected into every chat turn / canvas edit plan / task
                # run — and survive graduation), not just an RLHF row.
                # Student-only by the learning design; best-effort — the
                # feedback record above is the contract.
                try:
                    from core.student_learning_service import StudentLearningService

                    gist = corrected_action if isinstance(corrected_action, str) else json.dumps(corrected_action, default=str)
                    StudentLearningService(self.db).learn_from_observation(
                        agent_id,
                        "human_correction",
                        f"Supervisor corrected my work — follow the corrected "
                        f"version's content and style: {gist[:400]}",
                        details={
                            "canvas_id": canvas_id,
                            "context": (context_info or "")[:200],
                        },
                    )
                    logger.info(f"[LEARNING] Correction journaled as work-time lesson for {agent_id}")
                except Exception as journal_err:
                    logger.debug(f"correction journal skipped: {journal_err}")

                # Real-time circuit: the correction moved the agent's learning
                # state — drop the GovernanceCache maturity/confidence snapshot
                # so gated automation sees the updated agent immediately.
                try:
                    from core.governance_cache import get_governance_cache

                    get_governance_cache().invalidate_agent(agent_id)
                except Exception as cache_err:
                    logger.debug(f"governance cache invalidate skipped: {cache_err}")

        except Exception as e:
            logger.warning(f"[LEARNING] Failed to record user correction: {e}")

        # Installation Adaptation Plan (Phase 2 + 4): classify WHY the
        # supervisor corrected, file a replayable regression case, and
        # draft the rule it implies — the per-install learning loop that
        # replaces per-install engineering. Runs regardless of agent
        # binding (evals are per-tenant) and is fault-isolated: a learning
        # failure never blocks the correction itself.
        try:
            from core.failure_taxonomy import classify_correction
            from core.correction_reflection_service import reflect_on_correction
            from core.incident_eval_service import generate_from_correction

            original_content = (original_action.get("content")
                                if isinstance(original_action, dict) else original_action)
            corrected_content = (corrected_action.get("content")
                                 if isinstance(corrected_action, dict) else corrected_action)
            label, _signals = classify_correction(original_content, corrected_content)
            snapshot = {
                "canvas_type": context.canvas_type,
                "title": None,
                "content": original_content,
            } if isinstance(original_action, dict) else {}
            generate_from_correction(
                self.db, self.tenant_id, canvas_id, context.canvas_type,
                snapshot=snapshot,
                original=original_content,
                corrected=corrected_content,
                instruction=context_info,
            )
            reflect_on_correction(
                self.db, self.tenant_id, canvas_id, context.canvas_type,
                original=original_content,
                corrected=corrected_content,
                taxonomy=label,
                instruction=context_info,
            )
        except Exception as adapt_err:
            logger.debug(f"installation adaptation capture skipped: {adapt_err}")

        return True
    
    def get_similar_canvas_corrections(
        self,
        current_canvas_id: str,
        user_id: str,
        current_profile_text: str,
        current_canvas_type: str = "",
        limit: int = 2,
        scan: int = 25,
        min_score: float = 0.25,
        now: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """EPISODIC recall: corrections the supervisor made on OTHER canvases
        of the same kind, ranked by how similar each canvas is to the current
        one. A human painter reuses what they learned on similar canvases,
        not just the one on the easel; this gives the co-editor that channel
        (the per-agent lesson log is the PROCEDURAL channel; the patterns
        method below is the DISTILLED channel).

        Scoring mirrors Generative Agents' retrieval — relevance × recency:
        relevance is ``profile_similarity`` (deterministic lexical overlap;
        the embedding seam lives there), recency is a 14-day half-life so
        last month's correction outweighs last year's. Corrections are
        high-importance by definition (a supervisor intervened), so no
        separate importance term. Same ``canvas_type`` is required — a sheet
        correction must not steer an email draft.

        Returns [{canvas_id, canvas_type, similarity, corrections:[…]}],
        best first; [] when nothing clears ``min_score``. Fault-isolated.
        """
        try:
            now = now or datetime.now(timezone.utc)
            candidates = self.get_similar_canvas_candidates(
                current_canvas_id, user_id, current_canvas_type, scan=scan, now=now
            )
            scored = finalize_ranked_candidates(
                candidates,
                lambda cand: profile_similarity(current_profile_text, cand["profile_text"]),
                now=now, min_score=min_score, limit=limit,
            )
            return scored
        except Exception as e:
            logger.debug(f"similar-canvas correction recall skipped: {e}")
            return []

    def get_similar_canvas_candidates(
        self,
        current_canvas_id: str,
        user_id: str,
        current_canvas_type: str = "",
        scan: int = 25,
        now: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """UNRANKED episodic-recall candidates: other canvases of the same
        kind that carry supervisor corrections, newest-activity first, each
        with its bounded profile text. Scoring (lexical or embedding) is the
        caller's choice — ``get_similar_canvas_corrections`` scores lexically
        in-process; the async recall path scores with LanceDB-ecosystem
        FastEmbed vectors and falls back to lexical."""
        try:
            now = now or datetime.now(timezone.utc)
            query = (
                self.db.query(CanvasContext)
                .filter(
                    CanvasContext.user_id == user_id,
                    CanvasContext.canvas_id != current_canvas_id,
                )
                .order_by(CanvasContext.last_activity_at.desc().nullslast(),
                          CanvasContext.created_at.desc())
            )
            if self.tenant_id:
                query = query.filter(CanvasContext.tenant_id == self.tenant_id)
            rows = query.limit(scan).all()

            candidates: List[Dict[str, Any]] = []
            for ctx in rows:
                corrections = [c for c in (ctx.user_corrections or []) if c]
                if not corrections:
                    continue
                if (current_canvas_type
                        and (ctx.canvas_type or "") != current_canvas_type):
                    continue
                latest_ts = self._correction_timestamp(corrections[-1], now)
                candidates.append({
                    "canvas_id": ctx.canvas_id,
                    "canvas_type": ctx.canvas_type,
                    "profile_text": self._canvas_profile_text(ctx),
                    "corrections": corrections[-2:],
                    "latest_ts": latest_ts,
                })
            return candidates
        except Exception as e:
            logger.debug(f"similar-canvas candidate lookup skipped: {e}")
            return []

    @staticmethod
    def _canvas_profile_text(
        ctx: CanvasContext,
        state_bound: int = 300,
        correction_bound: int = 450,
    ) -> str:
        """Bounded text describing what a canvas was about — the comparison
        surface for cross-canvas similarity. Priority order matters: the
        supervisor's corrections carry the strongest task signal (a long
        chat_feedback narrative once crowded them out entirely and the
        recall scored a same-kind dealer draft at 0.06), so corrections get
        their own budget after a small state head. Dict-shaped content
        contributes its VALUES (the actual email text), not its JSON keys —
        shape words carry no task signal."""
        parts: List[str] = [str(ctx.canvas_type or "")]
        state = ctx.current_state if isinstance(ctx.current_state, dict) else {}
        if state:
            parts.append(json.dumps(state, default=str)[:state_bound])
        corrections = [
            c for c in (ctx.user_corrections or [])
            if isinstance(c, dict)
        ]
        for c in corrections[-3:]:
            for key in ("original", "corrected", "context"):
                v = c.get(key)
                if isinstance(v, dict):
                    content = v.get("content")
                    if isinstance(content, dict):
                        parts.append(" ".join(
                            str(x) for x in content.values()
                            if isinstance(x, str)
                        )[:correction_bound])
                    elif content is not None:
                        parts.append(str(content)[:correction_bound])
                elif isinstance(v, str):
                    parts.append(v[:correction_bound])
        return " ".join(p for p in parts if p)

    @staticmethod
    def _correction_timestamp(correction: Dict[str, Any], now: datetime) -> datetime:
        ts = correction.get("timestamp")
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                pass
        return now

    def get_correction_patterns(
        self,
        user_id: str,
        agent_id: Optional[str] = None,
        current_canvas_id: Optional[str] = None,
        scan: int = 40,
    ) -> List[Dict[str, Any]]:
        """DISTILLED recall: recurring patterns across the supervisor's
        corrections on ALL of this user's canvases (optionally one agent's) —
        ExpeL-style insights that transfer across tasks, not tied to one
        canvas. Deterministic field-diff extraction over dict-shaped
        corrections (e.g. an email {to, cc, subject, body}): WHICH fields
        the supervisor changed and in which direction.

        Returns pattern dicts {pattern, count, total} sorted by frequency,
        e.g. ``{"pattern": "filled the empty 'to' field", "count": 3,
        "total": 4}``. Empty list when corrections are unstructured or
        scarce — never guess a pattern from one example.
        """
        try:
            query = self.db.query(CanvasContext).filter(
                CanvasContext.user_id == user_id
            )
            if agent_id:
                query = query.filter(CanvasContext.agent_id == agent_id)
            if self.tenant_id:
                query = query.filter(CanvasContext.tenant_id == self.tenant_id)
            contexts = query.order_by(
                CanvasContext.last_activity_at.desc().nullslast()
            ).limit(scan).all()

            counts: Dict[str, int] = {}
            total = 0
            for ctx in contexts:
                for c in (ctx.user_corrections or []):
                    c = c if isinstance(c, dict) else {}
                    original = c.get("original")
                    corrected = c.get("corrected")
                    if not (isinstance(original, dict) and isinstance(corrected, dict)):
                        continue
                    oc = original.get("content")
                    cc = corrected.get("content")
                    if not (isinstance(oc, dict) and isinstance(cc, dict)):
                        continue
                    total += 1
                    for field in set(oc) | set(cc):
                        before, after = oc.get(field), cc.get(field)
                        before_s = before.strip() if isinstance(before, str) else ""
                        after_s = after.strip() if isinstance(after, str) else ""
                        if not before_s and after_s:
                            counts[f"filled the empty '{field}' field"] = (
                                counts.get(f"filled the empty '{field}' field", 0) + 1
                            )
                        elif before_s and not after_s:
                            counts[f"cleared the '{field}' field"] = (
                                counts.get(f"cleared the '{field}' field", 0) + 1
                            )
                        elif before_s != after_s:
                            counts[f"rewrote the '{field}' field"] = (
                                counts.get(f"rewrote the '{field}' field", 0) + 1
                            )
            if not total:
                return []
            patterns = [
                {"pattern": p, "count": n, "total": total}
                for p, n in counts.items()
                if n >= 2  # a pattern needs repetition; one example is noise
            ]
            patterns.sort(key=lambda e: e["count"], reverse=True)
            return patterns[:4]
        except Exception as e:
            logger.debug(f"correction pattern extraction skipped: {e}")
            return []

    def get_context_snapshot(
        self,
        canvas_id: str,
        user_id: str
    ) -> dict:
        """
        Get complete context snapshot for agent memory.
        """
        context = self.get_context(canvas_id, user_id)

        if not context:
            return {}

        return {
            "canvas_id": context.canvas_id,
            "canvas_type": context.canvas_type,
            "current_state": context.current_state,
            "recent_actions": (context.session_history or [])[-10:],  # Last 10 actions
            "user_preferences": context.user_preferences,
            "corrections_summary": self._summarize_corrections(context.user_corrections),
            "last_activity": context.last_activity_at.isoformat() if context.last_activity_at else None
        }
    
    def _summarize_corrections(self, corrections: Optional[List[dict]]) -> dict:
        """
        Summarize user corrections into actionable patterns.
        """
        if not corrections:
            return {}

        summary = {
            "total_corrections": len(corrections),
            "common_patterns": []
        }

        pattern_counts = {}
        for correction in corrections:
            orig = correction.get('original', {})
            action = orig.get('action_type', 'unknown') if isinstance(orig, dict) else 'unknown'
            pattern_counts[action] = pattern_counts.get(action, 0) + 1

        summary['common_patterns'] = [
            {'action_type': action, 'count': count}
            for action, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        return summary
    
    def reset_context(
        self,
        canvas_id: str,
        user_id: str
    ) -> bool:
        """
        Reset canvas context - user-initiated fresh start.
        """
        context = self.get_context(canvas_id, user_id)
        
        if not context:
            return False
        
        # Clear all session data
        context.session_history = []
        context.user_corrections = []
        context.current_state = {}
        context.user_preferences = {}
        context.last_activity_at = datetime.now(timezone.utc)
        
        self.db.commit()
        return True
