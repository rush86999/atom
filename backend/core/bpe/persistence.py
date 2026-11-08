"""Durable persistence for BPE workspace state (plan gap: restore-on-restart).

The in-process workspace registry loses state on process restart; this store
gives Progress + Experience a durable home using the same JSON-file pattern
as ``core.automation_settings``: one file per workspace under
``backend/data/bpe_workspaces/`` (``data/bpe_workspaces`` relative to the
backend directory), bounded to the most recent
:data:`MAX_SCOPES_PER_WORKSPACE` scopes (LRU by ``updated_at``).

Write path: the agent-loop episode close-out saves the pre-reset snapshot.
Read path: :func:`core.bpe.workspace.get_workspace` lazily restores on a
registry miss. Never raises — persistence failure degrades to in-memory
only.

Path anchoring: relative ``ATOM_BPE_DATA_DIR`` values are resolved against
the ``backend/`` directory (the documented launch dir), matching the LanceDB
and SQLite anchoring convention. Absolute paths pass through, and the
historically documented repo-relative spelling ``backend/data/...`` is
accepted as a compatibility alias for ``data/...``. An explicit ``data_dir``
passed to :class:`BPEWorkspaceStore` is used as supplied.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Relative default is backend-relative (not launch-CWD-relative). The effective
# location remains the documented <repo>/backend/data/bpe_workspaces.
DEFAULT_DATA_DIR = "data/bpe_workspaces"
_BACKEND_DIR = Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))


def _resolve_data_dir(raw: str) -> Path:
    """Resolve one configured BPE data directory.

    Relative paths are anchored to the ``backend/`` directory so a repo-root
    and a backend launch point at the same store. Absolute paths are returned
    untouched. For compatibility with the previously documented
    ``backend/data/bpe_workspaces`` spelling, a leading ``backend`` path
    component is treated as the repository-root marker and dropped before
    backend anchoring.
    """
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    parts = candidate.parts
    if parts and parts[0] == "backend":
        candidate = Path(*parts[1:]) if len(parts) > 1 else Path(".")
    return Path(os.path.normpath(os.path.join(str(_BACKEND_DIR), str(candidate))))


def _default_data_dir() -> Path:
    """Resolve the current default data directory from the environment."""
    return _resolve_data_dir(os.getenv("ATOM_BPE_DATA_DIR") or DEFAULT_DATA_DIR)


DATA_DIR = _default_data_dir()
MAX_SCOPES_PER_WORKSPACE = 32
MAX_STATE_CHARS = 64_000  # guard against a runaway Experience store on disk


class BPEWorkspaceStore:
    """JSON-file store for workspace snapshots. Cheap, best-effort."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        # Explicit directories (including tests' tmp_path) are used as given;
        # only the omitted default goes through backend anchoring above.
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR

    def _path_for(self, workspace_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(workspace_id))
        return self.data_dir / f"{safe or 'default'}.json"

    def _read(self, workspace_id: str) -> Dict[str, Any]:
        path = self._path_for(workspace_id)
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.debug("bpe store read failed: %s", e)
            return {}

    def _write(self, workspace_id: str, scopes: Dict[str, Any]) -> bool:
        """Write one workspace atomically. Returns True only on success.

        The replacement is best-effort but its outcome must be truthful:
        a failed ``os.replace`` leaves the previous file intact and the
        caller must not report a successful persist. Any temporary file
        created for this attempt is removed on every path, including
        replacement failures.
        """
        path = self._path_for(workspace_id)
        tmp: Optional[str] = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Atomic-ish write: temp file in the same dir, then replace.
            fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
            try:
                handle = os.fdopen(fd, "w", encoding="utf-8")
            except Exception:
                os.close(fd)  # fdopen failed before taking ownership of fd
                raise
            with handle:
                json.dump(scopes, handle)
            os.replace(tmp, path)
            tmp = None  # replaced successfully; nothing left to clean up
            return True
        except Exception as e:
            logger.debug("bpe store write failed: %s", e)
            return False
        finally:
            if tmp is not None:
                try:
                    os.unlink(tmp)
                except FileNotFoundError:
                    pass
                except OSError as e:
                    logger.debug("bpe store temp cleanup failed: %s", e)

    def save(self, snapshot: Dict[str, Any]) -> bool:
        """Persist one workspace snapshot (``BPEWorkspace.to_dict`` shape)."""
        try:
            workspace_id = str(snapshot.get("workspace_id") or "default")
            key = "|".join([
                str(snapshot.get("agent_id") or "agent"),
                str(snapshot.get("scope_key") or ""),
            ])
            scopes = self._read(workspace_id)
            scopes[key] = dict(snapshot)
            scopes[key]["_saved_at"] = time.time()
            # LRU bound: evict the oldest scopes beyond the cap.
            if len(scopes) > MAX_SCOPES_PER_WORKSPACE:
                ranked = sorted(
                    scopes.items(),
                    key=lambda kv: kv[1].get("_saved_at", 0),
                    reverse=True,
                )
                scopes = dict(ranked[:MAX_SCOPES_PER_WORKSPACE])
            payload = json.dumps(scopes)
            if len(payload) > MAX_STATE_CHARS:
                logger.debug("bpe store snapshot too large; skipping persist")
                return False
            return bool(self._write(workspace_id, scopes))
        except Exception as e:
            logger.debug("bpe store save failed: %s", e)
            return False

    def load(self, workspace_id: str, agent_id: str, scope_key: str) -> Optional[Dict[str, Any]]:
        """Return the persisted snapshot for this scope, or None."""
        try:
            scopes = self._read(str(workspace_id or "default"))
            key = "|".join([str(agent_id or "agent"), str(scope_key or "")])
            return scopes.get(key)
        except Exception as e:
            logger.debug("bpe store load failed: %s", e)
            return None
