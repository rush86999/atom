"""Durable persistence for BPE workspace state (plan gap: restore-on-restart).

The in-process workspace registry loses state on process restart; this store
gives Progress + Experience a durable home using the same JSON-file pattern
as ``core.automation_settings``: one file per workspace under
``backend/data/bpe_workspaces/``, bounded to the most recent
:data:`MAX_SCOPES_PER_WORKSPACE` scopes (LRU by ``updated_at``).

Write path: the agent-loop episode close-out saves the pre-reset snapshot.
Read path: :func:`core.bpe.workspace.get_workspace` lazily restores on a
registry miss. Never raises — persistence failure degrades to in-memory
only.
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

DATA_DIR = Path(os.getenv("ATOM_BPE_DATA_DIR", "backend/data/bpe_workspaces"))
MAX_SCOPES_PER_WORKSPACE = 32
MAX_STATE_CHARS = 64_000  # guard against a runaway Experience store on disk


class BPEWorkspaceStore:
    """JSON-file store for workspace snapshots. Cheap, best-effort."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
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

    def _write(self, workspace_id: str, scopes: Dict[str, Any]) -> None:
        path = self._path_for(workspace_id)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Atomic-ish write: temp file in the same dir, then replace.
            fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(scopes, f)
            os.replace(tmp, path)
        except Exception as e:
            logger.debug("bpe store write failed: %s", e)

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
            self._write(workspace_id, scopes)
            return True
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
