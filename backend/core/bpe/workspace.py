"""BPE workspace: bounded Belief / Progress / Experience state.

Implements the policy-facing harness state from EvoHarness-RL
(arXiv:2608.05446):

- **Belief (B)** — a persistent estimate of task-relevant environment facts.
  Maintained *off* the hot path by a :class:`~core.bpe.adapter.BPEAdapter`;
  the policy only reads it via ``track``.
- **Progress (P)** — a bounded committed-subgoal list (cap
  :data:`MAX_SUBGOALS`, mirroring the paper's cap of 8). Written ONLY when
  the policy explicitly commits.
- **Experience (E)** — cross-episode knowledge in categories, each
  capacity-bounded (:data:`MAX_ENTRIES_PER_CATEGORY`, paper: 80) with LFU
  eviction. Not append-only: consolidation removes/merges entries.

The four meta-actions (``track`` / ``commit`` / ``recall`` / ``note``) are
applied through :meth:`BPEWorkspace.apply`. Workspace instances are plain
state containers — persistence is the caller's concern via
:meth:`BPEWorkspace.to_dict` / :meth:`BPEWorkspace.from_dict` (rendered into
the execution record). The in-process registry :func:`get_workspace` keys
instances by ``(workspace_id, agent_id, scope_key)``.
"""
from __future__ import annotations

import inspect
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.bpe.telemetry import record_bpe_span

logger = logging.getLogger(__name__)

# Paper-grounded bounds. Progress cap mirrors the committed-plan list cap;
# Experience caps mirror the 80-entry LFU stores, top-3 recall per category.
MAX_SUBGOALS = 8
MAX_ENTRIES_PER_CATEGORY = 80
RECALL_TOP_K = 3
MAX_NOTE_CHARS = 400
MAX_BELIEF_SUMMARY_CHARS = 800
MAX_RENDER_CHARS = 2400

# Tunable workspace bounds — the AlphaEvolve-lite genome (core/bpe/evolution.py
# searches over these offline; set_active_bounds applies an approved genome).
GENE_BOUNDS = {
    "max_subgoals": (4, 12),
    "recall_top_k": (2, 5),
    "max_entries_per_category": (40, 120),
    "max_render_chars": (1600, 3200),
}

_ACTIVE_BOUNDS: Dict[str, Any] = {}


def set_active_bounds(genome: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply an evolved genome as the bounds for NEW workspaces.

    Values are clamped to GENE_BOUNDS; invalid entries are ignored. Returns
    the effective bounds. Callers gate application behind supervisor
    approval (``ATOM_BPE_EVOLUTION_ENABLED`` in evolution.py).
    """
    _ACTIVE_BOUNDS.clear()
    for gene, (lo, hi) in GENE_BOUNDS.items():
        raw = (genome or {}).get(gene)
        if raw is None:
            _ACTIVE_BOUNDS[gene] = {"max_subgoals": MAX_SUBGOALS,
                                    "recall_top_k": RECALL_TOP_K,
                                    "max_entries_per_category": MAX_ENTRIES_PER_CATEGORY,
                                    "max_render_chars": MAX_RENDER_CHARS}[gene]
            continue
        try:
            _ACTIVE_BOUNDS[gene] = max(lo, min(hi, type(lo)(raw)))
        except (TypeError, ValueError):
            _ACTIVE_BOUNDS[gene] = {"max_subgoals": MAX_SUBGOALS,
                                    "recall_top_k": RECALL_TOP_K,
                                    "max_entries_per_category": MAX_ENTRIES_PER_CATEGORY,
                                    "max_render_chars": MAX_RENDER_CHARS}[gene]
    return dict(_ACTIVE_BOUNDS)


def get_active_bounds() -> Dict[str, Any]:
    """Effective bounds for new workspaces (defaults until a genome applies)."""
    if not _ACTIVE_BOUNDS:
        set_active_bounds(None)
    return dict(_ACTIVE_BOUNDS)

# Experience categories from the paper: general skills, task-specific
# skills, common mistakes, search priors.
EXPERIENCE_CATEGORIES = ("skills", "task_skills", "mistakes", "priors")

SUBGOAL_STATUSES = ("pending", "in_progress", "done", "blocked")


@dataclass
class Subgoal:
    """One committed subgoal record (g_i, status)."""

    title: str
    status: str = "pending"
    committed_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "status": self.status,
            "committed_at": self.committed_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Subgoal":
        return cls(
            title=str(data.get("title") or ""),
            status=data.get("status") if data.get("status") in SUBGOAL_STATUSES else "pending",
            committed_at=float(data.get("committed_at") or time.time()),
            updated_at=float(data.get("updated_at") or time.time()),
        )


@dataclass
class ExperienceEntry:
    """One Experience-store entry with LFU usage tracking."""

    content: str
    uses: int = 0
    added_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {"content": self.content, "uses": self.uses, "added_at": self.added_at}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperienceEntry":
        return cls(
            content=str(data.get("content") or ""),
            uses=int(data.get("uses") or 0),
            added_at=float(data.get("added_at") or time.time()),
        )


class ExperienceStore:
    """Category-bounded knowledge store with LFU eviction.

    ``note`` writes land here only after consolidation (see
    ``core/bpe/consolidation.py`` roadmap); the store is deliberately NOT
    append-only — evict_lowest_usage keeps it a compact substrate.
    """

    def __init__(self, max_entries: int = MAX_ENTRIES_PER_CATEGORY,
                 recall_top_k: int = RECALL_TOP_K) -> None:
        self._categories: Dict[str, Dict[str, ExperienceEntry]] = {
            cat: {} for cat in EXPERIENCE_CATEGORIES
        }
        self.max_entries = max(int(max_entries), 1)
        self.recall_top_k = max(int(recall_top_k), 1)

    def add(self, category: str, content: str) -> bool:
        """Add an entry; returns False for unknown category or duplicates."""
        if category not in self._categories:
            return False
        content = str(content or "").strip()
        if not content:
            return False
        bucket = self._categories[category]
        if content in bucket:  # dedupe: consolidation updates uses instead
            bucket[content].uses += 1
            return False
        if len(bucket) >= self.max_entries:
            self._evict_one(category)
        bucket[content] = ExperienceEntry(content=content)
        return True

    def _evict_one(self, category: str) -> None:
        bucket = self._categories[category]
        if not bucket:
            return
        # LFU; ties broken by oldest added_at.
        key = min(bucket.values(), key=lambda e: (e.uses, e.added_at)).content
        del bucket[key]

    def recall(self, query: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Keyword-overlap top-K recall (paper: 3 per category, no vectors).

        Marks recalled entries as used (LFU signal). Never raises.
        """
        query = str(query or "").lower()
        q_tokens = {t for t in query.split() if len(t) > 2}
        categories = [category] if category in self._categories else list(self._categories)
        scored: List[tuple] = []
        for cat in categories:
            for entry in self._categories[cat].values():
                e_tokens = set(entry.content.lower().split())
                overlap = len(q_tokens & e_tokens)
                if overlap > 0:
                    scored.append((overlap, cat, entry))
        scored.sort(key=lambda s: (-s[0], s[2].uses, s[2].added_at))
        results = []
        for overlap, cat, entry in scored[:self.recall_top_k]:
            entry.uses += 1
            results.append({"category": cat, "content": entry.content, "score": overlap})
        return results

    def consolidate(self, category: str, remove_contents: Optional[List[str]] = None) -> int:
        """Offline consolidation hook: remove entries by content. Returns removed count."""
        bucket = self._categories.get(category)
        if not bucket or not remove_contents:
            return 0
        removed = 0
        for content in remove_contents:
            if content in bucket:
                del bucket[content]
                removed += 1
        return removed

    def to_dict(self) -> Dict[str, List[Dict[str, Any]]]:
        return {
            cat: [e.to_dict() for e in entries.values()]
            for cat, entries in self._categories.items()
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "ExperienceStore":
        store = cls()
        for cat, entries in (data or {}).items():
            if cat not in store._categories:
                continue
            for raw in entries or []:
                entry = ExperienceEntry.from_dict(raw)
                if entry.content:
                    store._categories[cat][entry.content] = entry
        return store


class BPEWorkspace:
    """The (Belief, Progress, Experience) state container for one scope.

    Belief is opaque here — the adapter maintains it externally and answers
    ``track`` queries (paper: rule-based parser updated in the background).
    """

    def __init__(self, workspace_id: str = "default", agent_id: str = "agent",
                 scope_key: str = "") -> None:
        self.workspace_id = workspace_id
        self.agent_id = agent_id
        self.scope_key = scope_key
        self.bounds: Dict[str, Any] = get_active_bounds()
        self.progress: List[Subgoal] = []
        self.notes: List[Dict[str, Any]] = []  # temp buffer, pre-consolidation
        self.experience = ExperienceStore(
            max_entries=self.bounds["max_entries_per_category"],
            recall_top_k=self.bounds["recall_top_k"],
        )
        self.adapter: Any = None  # BPEAdapter; late-bound to avoid cycles
        self._pending_notes: List[str] = []
        # Per-episode consult counters (consult_policy feedback signal).
        self.episode_consults = 0
        self.episode_commit_notes = 0

    # ------------------------------------------------------------------
    # Meta-actions (paper semantics: track=read B, commit=write P,
    # recall=read E, note=write temp buffer)
    # ------------------------------------------------------------------

    async def apply(self, action: str, payload: Any = None,
                    context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Apply one harness meta-action. Never raises; returns a result dict."""
        started = time.time()
        try:
            if action == "track":
                result = await self._track(payload, context or {})
            elif action == "commit":
                result = self._commit(payload)
            elif action == "recall":
                result = self._recall(payload)
            elif action == "note":
                result = self._note(payload)
            else:
                result = {"success": False, "error": f"unknown action '{action}'"}
            if action in ("track", "commit", "recall", "note") and result.get("success"):
                self.episode_consults += 1
                if action in ("commit", "note"):
                    self.episode_commit_notes += 1
        except Exception as e:  # harness actions must never break the loop
            logger.warning("bpe.apply(%s) failed: %s", action, e)
            result = {"success": False, "error": "workspace action failed"}
        record_bpe_span(
            action=action,
            workspace_id=self.workspace_id,
            agent_id=self.agent_id,
            scope_key=self.scope_key,
            success=bool(result.get("success")),
            latency_ms=(time.time() - started) * 1000.0,
            payload_chars=len(str(payload or "")),
        )
        return result

    async def _track(self, payload: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        topic = str(payload or "world").strip() or "world"
        if self.adapter is not None:
            summary = self.adapter.belief_summary(topic, context)
            if inspect.isawaitable(summary):
                summary = await summary
        else:
            summary = ""
        if summary:
            summary = str(summary)[:MAX_BELIEF_SUMMARY_CHARS]
        return {"success": True, "topic": topic, "belief": summary}

    def _commit(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            title = str(payload.get("title") or "").strip()
            status = payload.get("status")
        else:
            title, status = str(payload or "").strip(), None
        if not title:
            return {"success": False, "error": "commit requires a subgoal title"}
        now = time.time()
        if status is None:
            # New subgoal commit — bounded list, oldest done-subgoals drop first.
            cap = int(self.bounds.get("max_subgoals", MAX_SUBGOALS))
            if len(self.progress) >= cap:
                done = [s for s in self.progress if s.status == "done"]
                drop = done[0] if done else self.progress[0]
                self.progress.remove(drop)
            self.progress.append(Subgoal(title=title[:200]))
            return {"success": True, "op": "added", "title": title[:200],
                    "progress_size": len(self.progress)}
        # Status update on an existing subgoal (prefix match, first hit).
        if status not in SUBGOAL_STATUSES:
            return {"success": False, "error": f"status must be one of {SUBGOAL_STATUSES}"}
        for sub in self.progress:
            if sub.title == title or sub.title.startswith(title[:80]):
                sub.status = status
                sub.updated_at = now
                return {"success": True, "op": "status", "title": sub.title,
                        "status": status}
        return {"success": False, "error": "no matching subgoal to update"}

    def _recall(self, payload: Any) -> Dict[str, Any]:
        query = str(payload or "").strip()
        if not query:
            return {"success": False, "error": "recall requires a query", "results": []}
        results = self.experience.recall(query)
        return {"success": True, "query": query, "results": results}

    def _note(self, payload: Any) -> Dict[str, Any]:
        content = str(payload or "").strip()[:MAX_NOTE_CHARS]
        if not content:
            return {"success": False, "error": "note requires content"}
        self._pending_notes.append(content)
        return {"success": True, "buffered": len(self._pending_notes)}

    def drain_pending_notes(self) -> List[str]:
        """Hand buffered notes to consolidation (background writer)."""
        notes, self._pending_notes = self._pending_notes, []
        return notes

    def reset_episode_counters(self) -> None:
        """Start a fresh episode (called at run start by the agent loop)."""
        self.episode_consults = 0
        self.episode_commit_notes = 0

    # ------------------------------------------------------------------
    # Rendering + serialization
    # ------------------------------------------------------------------

    def render(self, mode: str = "full") -> str:
        """Bounded text block for the ReAct system prompt (empty when unused).

        ``mode='recall_only'`` is the annealing render: experience/progress
        state is shown but commit/note are flagged as internalized (the
        paper's decay ordering — recall persists longest).
        """
        sections: List[str] = []
        if self.progress:
            lines = [f"- [{s.status}] {s.title[:120]}" for s in self.progress]
            sections.append("PROGRESS (committed subgoals):\n" + "\n".join(lines))
        if self._pending_notes:
            lines = [f"- {n[:120]}" for n in self._pending_notes[-3:]]
            sections.append("RECENT NOTES (unconsolidated):\n" + "\n".join(lines))
        for cat in EXPERIENCE_CATEGORIES:
            entries = sorted(self.experience._categories[cat].values(),
                             key=lambda e: (-e.uses, e.added_at))[:self.experience.recall_top_k]
            if entries:
                lines = [f"- {e.content[:120]}" for e in entries]
                sections.append(f"EXPERIENCE/{cat} (top):\n" + "\n".join(lines))
        if not sections:
            return ""
        header = "WORKSPACE STATE (track/commit/recall/note meta-actions available):\n"
        if mode == "recall_only":
            header = ("WORKSPACE STATE (recall for reusable knowledge; "
                      "commit/note only if essential):\n")
        block = header + "\n".join(sections)
        render_cap = int(self.bounds.get("max_render_chars", MAX_RENDER_CHARS))
        if len(block) > render_cap:
            block = block[:render_cap] + "…"
        return block

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "agent_id": self.agent_id,
            "scope_key": self.scope_key,
            "progress": [s.to_dict() for s in self.progress],
            "pending_notes": list(self._pending_notes),
            "experience": self.experience.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "BPEWorkspace":
        data = data or {}
        ws = cls(
            workspace_id=str(data.get("workspace_id") or "default"),
            agent_id=str(data.get("agent_id") or "agent"),
            scope_key=str(data.get("scope_key") or ""),
        )
        ws.progress = [Subgoal.from_dict(s) for s in (data.get("progress") or [])]
        ws.progress = ws.progress[:int(ws.bounds.get("max_subgoals", MAX_SUBGOALS))]
        ws._pending_notes = [str(n)[:MAX_NOTE_CHARS] for n in (data.get("pending_notes") or [])]
        ws.experience = ExperienceStore.from_dict(data.get("experience"))
        return ws


# ---------------------------------------------------------------------------
# In-process registry — one workspace per (workspace_id, agent_id, scope).
# Process-local by design; durable state rides the execution record via
# to_dict/from_dict (same pattern as chat_session_manager's hybrid store).
# ---------------------------------------------------------------------------

_workspaces: Dict[tuple, BPEWorkspace] = {}
_MAX_CACHED_WORKSPACES = 512


def workspace_key(workspace_id: str, agent_id: str, scope_key: str) -> tuple:
    return (str(workspace_id or "default"), str(agent_id or "agent"), str(scope_key or ""))


def get_workspace(workspace_id: str, agent_id: str, scope_key: str) -> BPEWorkspace:
    """Return (creating if needed) the workspace for this scope.

    On a registry miss, tries a lazy restore from the durable store
    (``core.bpe.persistence``) so Progress/Experience survive a process
    restart. Restore failure falls through to a fresh workspace.
    """
    key = workspace_key(workspace_id, agent_id, scope_key)
    ws = _workspaces.get(key)
    if ws is None:
        if len(_workspaces) >= _MAX_CACHED_WORKSPACES:
            _workspaces.pop(next(iter(_workspaces)))  # FIFO; state is durable via to_dict
        restored: Optional[BPEWorkspace] = None
        try:
            from core.bpe.persistence import BPEWorkspaceStore

            snapshot = BPEWorkspaceStore().load(*key)
            if snapshot:
                restored = BPEWorkspace.from_dict(snapshot)
        except Exception as e:  # persistence is best-effort
            logger.debug("bpe workspace restore skipped: %s", e)
        ws = restored if restored is not None else BPEWorkspace(*key)
        _workspaces[key] = ws
    return ws


def reset_registry() -> None:
    """Test helper: clear cached workspaces."""
    _workspaces.clear()


def iter_agent_workspaces(agent_id: str) -> List["BPEWorkspace"]:
    """All cached workspaces belonging to one agent (snapshot list).

    Used by the trust bridge's de-inflation sweep (core/bpe/trust_bridge.py):
    adjudicated corrections demote experience entries across every scope the
    agent touched, without needing to know its workspace/scope keys.
    """
    return [ws for ws in list(_workspaces.values())
            if ws.agent_id == str(agent_id)]


def list_workspace_summaries() -> List[Dict[str, Any]]:
    """Bounded summaries of cached workspaces (admin observability surface).

    One row per cached scope: identity + state sizes, not full contents —
    use :func:`get_workspace_snapshot` for a full dump of one scope.
    """
    summaries: List[Dict[str, Any]] = []
    for ws in _workspaces.values():
        summaries.append({
            "workspace_id": ws.workspace_id,
            "agent_id": ws.agent_id,
            "scope_key": ws.scope_key,
            "progress_count": len(ws.progress),
            "progress_done": sum(1 for s in ws.progress if s.status == "done"),
            "pending_notes": len(ws._pending_notes),
            "experience_counts": {
                cat: len(bucket)
                for cat, bucket in ws.experience._categories.items()
            },
            "episode_consults": ws.episode_consults,
        })
    return summaries


def get_workspace_snapshot(workspace_id: str, agent_id: str,
                           scope_key: str) -> Optional[Dict[str, Any]]:
    """Full serialized state for one cached workspace, or None when absent
    (read-only: unlike :func:`get_workspace` this never creates one)."""
    ws = _workspaces.get(workspace_key(workspace_id, agent_id, scope_key))
    return ws.to_dict() if ws is not None else None
