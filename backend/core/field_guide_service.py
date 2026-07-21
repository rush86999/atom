"""Stigmergic Field Guide Service — Swarm Coordination.

Implements the "Field Guide" pattern from Cursor's Agent Swarm research:
a shared, agent-curated Markdown file that captures runtime discoveries,
surprise execution encounters, and operational rules. The file is
automatically injected into every agent's system prompt, allowing
frozen-weight models to effectively "train" their successors.

Design decisions:
  * Strict 50-line budget enforced on every write.  Lines over the cap
    are pruned oldest-first so the guide stays fresh.
  * Topic-keyed sections let agents add structured discoveries under
    named headings, preventing duplicate entries.
  * Files are stored under ``data/field_guides/<workspace_id>/FIELD_GUIDE.md``
    so each workspace maintains its own independent operational memory.
  * All mutations are atomic: the file is read → mutated → written in
    a single call so concurrent agents cannot corrupt it.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FIELD_GUIDE_MAX_LINES: int = 50
"""Hard line-budget per workspace field guide."""

_FIELD_GUIDE_DIR = Path(__file__).parent / "data" / "field_guides"
"""Root directory for all workspace field guides."""

_INJECTION_HEADER = (
    "## 🗺 Workspace Field Guide\n"
    "_Curated by agents at runtime — read before acting._\n\n"
)
"""System-prompt injection wrapper header."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _guide_path(workspace_id: str) -> Path:
    """Return (and create if needed) the path for a workspace's FIELD_GUIDE.md."""
    safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", workspace_id)
    guide_dir = _FIELD_GUIDE_DIR / safe_id
    guide_dir.mkdir(parents=True, exist_ok=True)
    return guide_dir / "FIELD_GUIDE.md"


def _read_lines(path: Path) -> List[str]:
    """Read a file's lines, returning [] if it does not exist."""
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def _write_lines(path: Path, lines: List[str]) -> None:
    """Write lines to disk atomically via a temp-swap."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(lines), encoding="utf-8")
    tmp.replace(path)


def _prune_to_budget(lines: List[str], budget: int) -> List[str]:
    """Remove oldest non-header lines until the guide fits within *budget*."""
    if len(lines) <= budget:
        return lines
    # Identify the preamble (first blank line or first heading block)
    # and preserve it; prune body lines oldest-first.
    header_end = 0
    for i, line in enumerate(lines):
        if i > 0 and line.startswith("## ") and i > 0:
            header_end = i
            break
    header = lines[:header_end] if header_end else []
    body = lines[header_end:]
    excess = len(lines) - budget
    pruned_body = body[excess:]
    return header + pruned_body


def _find_or_create_section(lines: List[str], topic: str) -> int:
    """Return the line index immediately after the topic section header.

    If the section does not exist, append it and return the new index.
    """
    heading = f"### {topic}\n"
    for i, line in enumerate(lines):
        if line == heading:
            # Find next section or end of file
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("### "):
                    return j  # insert before next section
            return len(lines)
    # Section absent — append
    if lines and not lines[-1].endswith("\n"):
        lines.append("\n")
    lines.append("\n")
    lines.append(heading)
    return len(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class FieldGuideService:
    """Agent-curated workspace operations manual with stigmergic update semantics.

    Agents call :meth:`update_field_guide` whenever they discover a runtime
    rule, quirk, or operational constraint.  The guide auto-prunes to a
    50-line budget and is injected into successor agents' system prompts
    via :meth:`get_field_guide_context`.
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self._base_dir = base_dir or _FIELD_GUIDE_DIR

    def _guide_path(self, workspace_id: str) -> Path:
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", workspace_id)
        guide_dir = self._base_dir / safe_id
        guide_dir.mkdir(parents=True, exist_ok=True)
        return guide_dir / "FIELD_GUIDE.md"

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_field_guide_context(self, workspace_id: str) -> str:
        """Return the field guide formatted for injection into a system prompt.

        Returns an empty string if no guide has been written yet so callers
        need not special-case the first-run scenario.
        """
        path = self._guide_path(workspace_id)
        lines = _read_lines(path)
        if not lines:
            return ""
        content = "".join(lines)
        return f"{_INJECTION_HEADER}{content}\n---\n"

    def get_raw_guide(self, workspace_id: str) -> str:
        """Return the raw Markdown content of the field guide (for UI display)."""
        path = self._guide_path(workspace_id)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def update_field_guide(
        self,
        workspace_id: str,
        topic: str,
        insight_text: str,
        *,
        agent_id: Optional[str] = None,
        budget: int = FIELD_GUIDE_MAX_LINES,
    ) -> Dict[str, object]:
        """Append a new insight under *topic* and enforce the line budget.

        Args:
            workspace_id: Workspace to update (each workspace has its own guide).
            topic: Short section heading (e.g. "Tool Failures", "File Layout").
            insight_text: One-liner or short paragraph describing the discovery.
            agent_id: Optional author tag for audit trail.
            budget: Maximum allowed lines (default: ``FIELD_GUIDE_MAX_LINES``).

        Returns:
            Dict with ``{"path": ..., "lines_before": ..., "lines_after": ...,
            "pruned": bool}``.
        """
        path = self._guide_path(workspace_id)
        lines = _read_lines(path)
        lines_before = len(lines)

        # Ensure preamble exists
        if not lines:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            lines = [
                f"# Field Guide — {workspace_id}\n",
                f"_Auto-generated {ts}. Do not edit manually._\n",
                "\n",
            ]

        # Find or create the topic section
        insert_idx = _find_or_create_section(lines, topic)

        # Build the entry line
        ts_short = datetime.now(timezone.utc).strftime("%H:%MZ")
        author = f" [{agent_id}]" if agent_id else ""
        entry = f"- `{ts_short}`{author} {insight_text.strip()}\n"

        # Deduplicate: skip if identical insight already present in section
        insight_lower = insight_text.strip().lower()
        section_slice = lines[max(0, insert_idx - 20):insert_idx]
        if any(insight_lower in l.lower() for l in section_slice):
            logger.debug("FieldGuide: duplicate insight skipped for workspace=%s topic=%s", workspace_id, topic)
            return {
                "path": str(path),
                "lines_before": lines_before,
                "lines_after": lines_before,
                "pruned": False,
                "duplicate_skipped": True,
            }

        lines.insert(insert_idx, entry)

        # Enforce budget
        pruned = len(lines) > budget
        lines = _prune_to_budget(lines, budget)

        _write_lines(path, lines)
        logger.info(
            "FieldGuide updated: workspace=%s topic=%s lines=%d→%d pruned=%s",
            workspace_id, topic, lines_before, len(lines), pruned,
        )
        return {
            "path": str(path),
            "lines_before": lines_before,
            "lines_after": len(lines),
            "pruned": pruned,
        }

    def clear_guide(self, workspace_id: str) -> bool:
        """Delete the field guide for a workspace. Returns True if file existed."""
        path = self._guide_path(workspace_id)
        if path.exists():
            path.unlink()
            logger.info("FieldGuide cleared for workspace=%s", workspace_id)
            return True
        return False


# ---------------------------------------------------------------------------
# Module-level singleton for convenience
# ---------------------------------------------------------------------------
_default_service: Optional[FieldGuideService] = None


def get_field_guide_service() -> FieldGuideService:
    """Return the module-level default FieldGuideService instance."""
    global _default_service
    if _default_service is None:
        _default_service = FieldGuideService()
    return _default_service
