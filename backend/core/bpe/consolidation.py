"""Experience consolidation for BPE workspaces (plan Phase 3, v1).

The paper's harness-evolution dynamic: the Experience store is actively
reshaped — ``note`` writes land in a temp buffer, then a consolidator moves
them into the store *outside the rollout loop*, merging/evicting so the
substrate stays compact. Without an LLM consolidator (that's the
flag-gated upgrade, mirroring ``ATOM_MEMORY_CONSOLIDATION_LLM``), this v1
uses deterministic keyword routing:

- notes mentioning avoid/never/don't/fail → ``mistakes``
- notes mentioning where/lives in/location → ``priors``
- everything else → ``skills``

Promotion happens only after a **successful** episode (failed-run lessons
are dropped rather than trusted — same posture as the evidence gate).
``sweep_pending_notes`` is wired into the nightly
``memory_consolidator.consolidate_workspace`` run. Never raises.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_MISTAKE_MARKERS = ("avoid", "never", "don't", "do not", "fails", "failed", "wrong")
_PRIOR_MARKERS = ("live in", "lives in", "located", "location", "stored in",
                  "found in", "channel", "path")


def classify_note(content: str) -> str:
    """Deterministic note → category routing."""
    text = str(content or "").lower()
    if any(m in text for m in _MISTAKE_MARKERS):
        return "mistakes"
    if any(m in text for m in _PRIOR_MARKERS):
        return "priors"
    return "skills"


def consolidate_workspace_notes(ws) -> Dict[str, int]:
    """Promote one workspace's buffered notes into its Experience store.

    Called at episode end (success path) and by the nightly sweep. Returns
    per-category promotion counts.
    """
    report = {"skills": 0, "task_skills": 0, "mistakes": 0, "priors": 0}
    try:
        notes: List[str] = ws.drain_pending_notes()
        for note in notes:
            category = classify_note(note)
            if ws.experience.add(category, note):
                report[category] += 1
    except Exception as e:  # consolidation must never break the caller
        logger.debug("bpe note consolidation failed: %s", e)
    return report


def sweep_pending_notes(workspaces: Any) -> Dict[str, int]:
    """Nightly sweep: consolidate stale buffers across cached workspaces.

    ``workspaces`` is the workspace registry dict (key → BPEWorkspace) or
    any iterable of workspaces.
    """
    total = {"skills": 0, "task_skills": 0, "mistakes": 0, "priors": 0}
    if hasattr(workspaces, "values"):
        workspace_iter = workspaces.values()
    else:
        workspace_iter = workspaces or []
    for ws in workspace_iter:
        try:
            report = consolidate_workspace_notes(ws)
            for cat, n in report.items():
                total[cat] = total.get(cat, 0) + n
        except Exception as e:
            logger.debug("bpe sweep skipped a workspace: %s", e)
    return total
