"""Memory-store bootstrap — makes fresh installations and app restarts
land on ONE memory store, automatically.

Divergence incident (2026-09-02): older code resolved the LanceDB base
relative to the launch CWD, so an install that launched from the repo root
accumulated its whole memory (288 communications, documents, business
facts) under ``<repo>/data/atom_memory`` while the anchored code reads
``backend/data/atom_memory``. After upgrading + restarting, the agent went
memory-blind and could not find an email that sat in the store.

``reconcile_memory_store()`` runs at startup (before workers):

  - For each workspace dir in the LEGACY base (``<repo>/data/atom_memory``
    — the old CWD-relative location) whose anchored counterpart has NO
    LanceDB tables yet, the legacy ``*.lance`` tables and
    ``poll_fetch_state.json`` are adopted (copied) into the anchored base.
  - NEVER overwrites: an anchored workspace that already has tables wins
    (the durable store is authoritative on conflict).
  - Idempotent: a second run finds nothing to do. Fresh installations have
    no legacy dir and no-op too.

Also exposes ``memory_store_status()`` for the health surface so divergence
is observable instead of silent.
"""
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

STORE_DIR_NAME = "data/atom_memory"
POLL_STATE_FILE = "poll_fetch_state.json"


def _backend_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def _anchored_base() -> Path:
    return _backend_dir() / STORE_DIR_NAME


def _legacy_base() -> Path:
    # The old CWD-relative location when the app was launched from the repo
    # root: <repo>/data/atom_memory — i.e. the anchored base's grandparent.
    return _backend_dir().parent / STORE_DIR_NAME


def _lance_tables(dir_path: Path) -> List[str]:
    if not dir_path.is_dir():
        return []
    return sorted(p.name for p in dir_path.glob("*.lance"))


def reconcile_memory_store(
    anchored_base: Path = None,
    legacy_base: Path = None,
) -> Dict[str, Any]:
    """Adopt legacy-root memory stores into the anchored backend store.

    Returns a summary dict {"migrated": [...], "skipped": [...], ...}.
    Never raises — bootstrapping must not block startup."""
    anchored_base = Path(anchored_base) if anchored_base else _anchored_base()
    legacy_base = Path(legacy_base) if legacy_base else _legacy_base()
    summary: Dict[str, Any] = {
        "anchored_base": str(anchored_base),
        "legacy_base": str(legacy_base),
        "migrated": [],
        "skipped": [],
    }
    try:
        if not legacy_base.is_dir() or legacy_base.resolve() == anchored_base.resolve():
            return summary
        for legacy_ws in sorted(p for p in legacy_base.iterdir() if p.is_dir()):
            tables = _lance_tables(legacy_ws)
            if not tables:
                continue
            anchored_ws = anchored_base / legacy_ws.name
            existing = _lance_tables(anchored_ws)
            if existing:
                summary["skipped"].append(
                    f"{legacy_ws.name}: anchored store already has {len(existing)} table(s)"
                )
                continue
            anchored_ws.mkdir(parents=True, exist_ok=True)
            copied = []
            for table in tables:
                shutil.copytree(legacy_ws / table, anchored_ws / table)
                copied.append(table)
            state_src = legacy_ws / POLL_STATE_FILE
            if state_src.exists():
                shutil.copy2(state_src, anchored_ws / POLL_STATE_FILE)
                copied.append(POLL_STATE_FILE)
            summary["migrated"].append(
                {"workspace": legacy_ws.name, "copied": copied}
            )
            logger.warning(
                f"memory store: ADOPTED legacy store for workspace "
                f"'{legacy_ws.name}' ({len(copied)} item(s)) from {legacy_ws} "
                f"into {anchored_ws} — the old CWD-relative location is no "
                f"longer read; the original is preserved as backup")
        if summary["migrated"]:
            logger.warning(
                f"memory store: reconciliation migrated "
                f"{len(summary['migrated'])} workspace(s); restart-free "
                "adoption complete")
    except Exception as e:
        logger.warning(f"memory store reconciliation skipped: {e}")
    return summary


def memory_store_status() -> Dict[str, Any]:
    """Observable store state for /api/health — divergence becomes a
    visible fact instead of a silent agent-amnesia bug."""
    anchored_base = _anchored_base()
    legacy_base = _legacy_base()
    workspaces: Dict[str, int] = {}
    try:
        for ws in sorted(p for p in anchored_base.iterdir() if p.is_dir()):
            workspaces[ws.name] = len(_lance_tables(ws))
    except Exception:
        pass
    legacy_tables = 0
    try:
        for ws in (p for p in legacy_base.iterdir() if p.is_dir()):
            legacy_tables += len(_lance_tables(ws))
    except Exception:
        pass
    return {
        "anchored_base": str(anchored_base),
        "workspaces": workspaces,
        "legacy_base": str(legacy_base),
        "legacy_table_count": legacy_tables,
    }
