"""Stigmergic Field Guide Service — Cloud-Native DB-backed Implementation.

Implements the "Field Guide" pattern from Cursor's Agent Swarm research:
a shared, agent-curated Markdown file that captures runtime discoveries,
surprise execution encounters, and operational rules.

## Storage Strategy

Content is stored in PostgreSQL (`field_guides` table) as a single ``Text``
column per workspace, making it:

  * **Pod-restart safe** — Postgres survives ephemeral container filesystems.
  * **Horizontally scalable** — every instance reads from the same row.
  * **Lock-free** — reads are non-blocking; writes use ``SELECT FOR UPDATE``
    at the row level so concurrent agents don't corrupt the guide.

## Local-dev / Test Fallback

When no ``db`` session is provided (local scripts, unit tests without a DB),
the service falls back to the original filesystem implementation under
``data/field_guides/<workspace_id>/FIELD_GUIDE.md``.  This keeps the
development experience zero-config.

## Line Budget

The guide is capped at 50 lines (configurable).  On every write, lines that
exceed the cap are pruned oldest-first so the guide stays fresh and lean
enough to fit in a system-prompt prefix.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FIELD_GUIDE_MAX_LINES: int = 50

_INJECTION_HEADER = (
    "## 🗺 Workspace Field Guide\n"
    "_Curated by agents at runtime — read before acting._\n\n"
)

# Filesystem fallback root (local dev / unit tests only)
_FS_FALLBACK_DIR = Path(__file__).parent / "data" / "field_guides"


# ---------------------------------------------------------------------------
# Internal line-manipulation helpers (shared by both backends)
# ---------------------------------------------------------------------------

def _prune_to_budget(lines: List[str], budget: int) -> List[str]:
    """Remove oldest non-header lines until the guide fits within *budget*."""
    if len(lines) <= budget:
        return lines
    # Find first section heading to preserve preamble
    header_end = 0
    for i, line in enumerate(lines):
        if i > 0 and line.startswith("## ") or (i > 0 and line.startswith("### ")):
            header_end = i
            break
    header = lines[:header_end] if header_end else []
    body = lines[header_end:]
    excess = len(lines) - budget
    return header + body[excess:]


def _find_or_create_section(lines: List[str], topic: str) -> int:
    """Return line index immediately after the topic heading.

    Appends the heading if absent and returns its insertion point.
    """
    heading = f"### {topic}\n"
    for i, line in enumerate(lines):
        if line == heading:
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("### "):
                    return j
            return len(lines)
    if lines and not lines[-1].endswith("\n"):
        lines.append("\n")
    lines.append("\n")
    lines.append(heading)
    return len(lines)


def _build_entry(insight_text: str, agent_id: Optional[str]) -> str:
    ts = datetime.now(timezone.utc).strftime("%H:%MZ")
    author = f" [{agent_id}]" if agent_id else ""
    return f"- `{ts}`{author} {insight_text.strip()}\n"


def _default_preamble(workspace_id: str) -> List[str]:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [
        f"# Field Guide — {workspace_id}\n",
        f"_Auto-generated {ts}. Do not edit manually._\n",
        "\n",
    ]


# ---------------------------------------------------------------------------
# DB backend
# ---------------------------------------------------------------------------

class _DbBackend:
    """Read/write field guide content via SQLAlchemy session."""

    def __init__(self, db) -> None:
        self._db = db

    def _get_or_create(self, workspace_id: str):
        """Return the FieldGuide ORM row, creating it if absent."""
        from core.models import FieldGuide
        row = (
            self._db.query(FieldGuide)
            .filter(FieldGuide.workspace_id == workspace_id)
            .with_for_update()
            .first()
        )
        if row is None:
            row = FieldGuide(
                id=str(uuid.uuid4()),
                workspace_id=workspace_id,
                content="",
                line_count=0,
            )
            self._db.add(row)
            self._db.flush()
        return row

    def read(self, workspace_id: str) -> str:
        from core.models import FieldGuide
        row = (
            self._db.query(FieldGuide)
            .filter(FieldGuide.workspace_id == workspace_id)
            .first()
        )
        return row.content if row else ""

    def write(self, workspace_id: str, content: str, line_count: int) -> None:
        from core.models import FieldGuide
        row = self._get_or_create(workspace_id)
        row.content = content
        row.line_count = line_count
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(row, "content")
        self._db.commit()

    def delete(self, workspace_id: str) -> bool:
        from core.models import FieldGuide
        row = (
            self._db.query(FieldGuide)
            .filter(FieldGuide.workspace_id == workspace_id)
            .first()
        )
        if row:
            self._db.delete(row)
            self._db.commit()
            return True
        return False

    def location(self, workspace_id: str) -> str:
        """Return a human-readable identifier for *workspace_id*'s storage."""
        return f"db:field_guides(workspace_id={workspace_id})"


# ---------------------------------------------------------------------------
# Filesystem fallback backend (local dev / unit tests)
# ---------------------------------------------------------------------------

class _FsBackend:
    """Read/write field guide content via local filesystem (dev fallback)."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self._base = base_dir or _FS_FALLBACK_DIR

    def _path(self, workspace_id: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", workspace_id)
        d = self._base / safe
        d.mkdir(parents=True, exist_ok=True)
        return d / "FIELD_GUIDE.md"

    def location(self, workspace_id: str) -> str:
        """Return the on-disk path for *workspace_id* (no side effects)."""
        safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", workspace_id)
        return str(self._base / safe / "FIELD_GUIDE.md")

    def read(self, workspace_id: str) -> str:
        p = self._path(workspace_id)
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def write(self, workspace_id: str, content: str, line_count: int) -> None:
        p = self._path(workspace_id)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(p)

    def delete(self, workspace_id: str) -> bool:
        p = self._path(workspace_id)
        if p.exists():
            p.unlink()
            return True
        return False

    def location(self, workspace_id: str) -> str:
        """Return the on-disk path for *workspace_id* (does not create the file)."""
        return str(self._path(workspace_id))


# ---------------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------------

class FieldGuideService:
    """Agent-curated workspace operations manual with cloud-native DB storage.

    Agents call :meth:`update_field_guide` whenever they discover a runtime
    rule, quirk, or operational constraint.  The guide auto-prunes to a
    50-line budget and is injected into successor agents' system prompts
    via :meth:`get_field_guide_context`.

    **Storage**:
      * With ``db`` → PostgreSQL ``field_guides`` table (production / cloud).
      * Without ``db`` → local filesystem under ``core/data/field_guides/``
        (local dev, unit tests).

    Example::

        # Production (FastAPI endpoint with DB session)
        svc = FieldGuideService(db=db_session)

        # Local dev / tests
        svc = FieldGuideService()
    """

    def __init__(
        self,
        db=None,
        *,
        base_dir: Optional[Path] = None,
    ) -> None:
        if db is not None:
            self._backend: _DbBackend | _FsBackend = _DbBackend(db)
            self._storage = "db"
        else:
            self._backend = _FsBackend(base_dir)
            self._storage = "fs"

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_field_guide_context(self, workspace_id: str) -> str:
        """Return the field guide formatted for injection into a system prompt."""
        content = self._backend.read(workspace_id)
        if not content:
            return ""
        return f"{_INJECTION_HEADER}{content}\n---\n"

    def get_raw_guide(self, workspace_id: str) -> str:
        """Return the raw Markdown content (for UI / API display)."""
        return self._backend.read(workspace_id)

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

        Returns a dict with ``path`` (or ``storage``), ``lines_before``,
        ``lines_after``, ``pruned``, and optionally ``duplicate_skipped``.
        """
        raw = self._backend.read(workspace_id)
        lines: List[str] = raw.splitlines(keepends=True) if raw else []
        lines_before = len(lines)

        # Ensure preamble
        if not lines:
            lines = _default_preamble(workspace_id)

        # Find / create topic section
        insert_idx = _find_or_create_section(lines, topic)

        # Deduplicate
        insight_lower = insight_text.strip().lower()
        section_slice = lines[max(0, insert_idx - 20):insert_idx]
        if any(insight_lower in l.lower() for l in section_slice):
            logger.debug(
                "FieldGuide: duplicate insight skipped workspace=%s topic=%s",
                workspace_id, topic,
            )
            return {
                "path": self._backend.location(workspace_id),
                "storage": self._storage,
                "lines_before": lines_before,
                "lines_after": lines_before,
                "pruned": False,
                "duplicate_skipped": True,
            }

        entry = _build_entry(insight_text, agent_id)
        lines.insert(insert_idx, entry)

        # Enforce budget
        pruned = len(lines) > budget
        lines = _prune_to_budget(lines, budget)

        content = "".join(lines)
        self._backend.write(workspace_id, content, len(lines))

        logger.info(
            "FieldGuide updated: workspace=%s topic=%s storage=%s lines=%d→%d pruned=%s",
            workspace_id, topic, self._storage, lines_before, len(lines), pruned,
        )
        return {
            "path": self._backend.location(workspace_id),
            "storage": self._storage,
            "lines_before": lines_before,
            "lines_after": len(lines),
            "pruned": pruned,
        }

    def clear_guide(self, workspace_id: str) -> bool:
        """Delete the field guide for a workspace. Returns True if it existed."""
        deleted = self._backend.delete(workspace_id)
        if deleted:
            logger.info("FieldGuide cleared: workspace=%s storage=%s", workspace_id, self._storage)
        return deleted


# ---------------------------------------------------------------------------
# Module-level singleton (filesystem backend, for scripts / non-DI callers)
# ---------------------------------------------------------------------------
_default_service: Optional[FieldGuideService] = None


def get_field_guide_service(db=None) -> FieldGuideService:
    """Return a FieldGuideService.

    Passes ``db`` through when provided (returns a fresh DB-backed instance).
    When called without arguments, returns the module-level filesystem-backed
    singleton (suitable for local scripts and tests without a DB).
    """
    global _default_service
    if db is not None:
        return FieldGuideService(db=db)
    if _default_service is None:
        _default_service = FieldGuideService()
    return _default_service
