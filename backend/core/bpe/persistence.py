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

Namespace identity: the persisted unit is the exact
``(workspace_id, agent_id, scope_key)`` triple. The workspace file name and
the inner scope key are injective encodings of those components, so two
different namespaces can never read or overwrite one another through a
lossy character substitution or a ``|`` separator collision. ``load`` also
verifies that the identity embedded in the stored snapshot is the identity
that was asked for; a mismatched (tampered/stale) snapshot is refused rather
than restored under the wrong namespace. Normal lowercase ids keep their
historic ``<workspace_id>.json`` / ``<agent_id>|<scope_key>`` spelling.
Unsafe or mixed-case ids are encoded, and a legacy lossy-named file is
read once for compatibility without being moved, deleted or overwritten.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Historic safe spelling: keeping this exact for lowercase ids preserves every
# existing file/key while the encodings below make all other ids unambiguous.
_SAFE_WORKSPACE_ID = re.compile(r"^[a-z0-9_-]{1,120}$")
_ENCODED_WORKSPACE_PREFIX = "~"
_ENCODED_SCOPE_PREFIX = "v2"
_SCOPE_SEPARATOR = "|"


def namespace_identity(
    workspace_id: Any, agent_id: Any, scope_key: Any
) -> Tuple[str, str, str]:
    """Canonical persisted namespace triple (same normalization as the API)."""
    return (
        str(workspace_id or "default"),
        str(agent_id or "agent"),
        str(scope_key or ""),
    )


def _workspace_file_name(workspace_id: Any) -> str:
    """Injective file name for a workspace id.

    Lowercase safe ids retain the established ``<id>.json`` name. Everything
    else (characters the old sanitizer rewrote, mixed case on case-insensitive
    filesystems, overlong ids, traversal-shaped values) becomes
    ``~<sha256>.json``. The ``~``/safe-alphabet split means an encoded name can
    never equal a pass-through name.
    """
    text = str(workspace_id or "default")
    if _SAFE_WORKSPACE_ID.fullmatch(text):
        return f"{text}.json"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"{_ENCODED_WORKSPACE_PREFIX}{digest}.json"


def _legacy_workspace_file_name(workspace_id: Any) -> str:
    """The pre-repair lossy name, retained only for read-through compatibility."""
    safe = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in str(workspace_id)
    )
    return f"{safe or 'default'}.json"


def _legacy_scope_key(agent_id: Any, scope_key: Any) -> str:
    return f"{str(agent_id or 'agent')}{_SCOPE_SEPARATOR}{str(scope_key or '')}"


def _scope_storage_key(agent_id: Any, scope_key: Any) -> str:
    """Injective inner key for ``(agent_id, scope_key)``.

    The legacy key is used when neither component contains the separator (so
    every existing safe snapshot keeps its exact key). Otherwise both
    components are urlsafe-base64 encoded inside a ``v2|...|...`` envelope;
    base64 cannot contain ``|``, so the envelope cannot collide with a legacy
    one-separator key.
    """
    agent = str(agent_id or "agent")
    scope = str(scope_key or "")
    if _SCOPE_SEPARATOR not in agent and _SCOPE_SEPARATOR not in scope:
        return _legacy_scope_key(agent, scope)

    def _encode(value: str) -> str:
        return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii")

    return f"{_ENCODED_SCOPE_PREFIX}{_SCOPE_SEPARATOR}{_encode(agent)}{_SCOPE_SEPARATOR}{_encode(scope)}"


def _snapshot_identity(snapshot: Any) -> Optional[Tuple[str, str, str]]:
    """Embedded namespace identity of one stored entry (None when not a dict)."""
    if not isinstance(snapshot, dict):
        return None
    return namespace_identity(
        snapshot.get("workspace_id"),
        snapshot.get("agent_id"),
        snapshot.get("scope_key"),
    )


def _snapshot_workspace_id(snapshot: Any) -> Optional[str]:
    identity = _snapshot_identity(snapshot)
    return identity[0] if identity is not None else None


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
        """Canonical (injective) path for one workspace's snapshot file."""
        return self.data_dir / _workspace_file_name(workspace_id)

    def _legacy_path_for(self, workspace_id: str) -> Path:
        """The pre-repair lossy path, used only for read-through compatibility."""
        return self.data_dir / _legacy_workspace_file_name(workspace_id)

    def _read_path(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.debug("bpe store read failed: %s", e)
            return {}

    def _read(self, workspace_id: str) -> Dict[str, Any]:
        """Read canonical state, falling back to a legacy lossy-named file.

        The fallback is read-only: ``save`` writes the canonical file and never
        moves, rewrites or deletes the old one.
        """
        canonical = self._path_for(workspace_id)
        if canonical.exists():
            return self._read_path(canonical)
        legacy = self._legacy_path_for(workspace_id)
        if legacy != canonical and legacy.exists():
            return self._read_path(legacy)
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
        """Persist one workspace snapshot (``BPEWorkspace.to_dict`` shape).

        The saved entry's identity is stamped from the canonical triple and
        written under its injective key, so the on-disk key, embedded identity
        and file name always agree.
        """
        try:
            identity = namespace_identity(
                snapshot.get("workspace_id"),
                snapshot.get("agent_id"),
                snapshot.get("scope_key"),
            )
            workspace_id, agent_id, scope_key = identity
            key = _scope_storage_key(agent_id, scope_key)

            canonical = self._path_for(workspace_id)
            if canonical.exists():
                scopes = self._read_path(canonical)
            else:
                legacy = self._legacy_path_for(workspace_id)
                if legacy != canonical and legacy.exists():
                    # Read-through only: keep every scope belonging to THIS
                    # workspace, never copy a colliding legacy file's foreign
                    # workspace entries into the new canonical file.
                    scopes = {
                        old_key: old_value
                        for old_key, old_value in self._read_path(legacy).items()
                        if _snapshot_workspace_id(old_value) == workspace_id
                    }
                else:
                    scopes = {}

            entry = dict(snapshot)
            entry["workspace_id"] = workspace_id
            entry["agent_id"] = agent_id
            entry["scope_key"] = scope_key
            entry["_saved_at"] = time.time()
            scopes[key] = entry
            # LRU bound: evict the oldest scopes beyond the cap.
            if len(scopes) > MAX_SCOPES_PER_WORKSPACE:
                ranked = sorted(
                    scopes.items(),
                    key=lambda kv: (
                        kv[1].get("_saved_at", 0)
                        if isinstance(kv[1], dict) else 0
                    ),
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
        """Return the snapshot for exactly this namespace, or None.

        A stored entry whose embedded workspace/agent/scope identity does not
        equal the requested triple is refused: it must never be restored under
        a namespace it was not written for.
        """
        try:
            identity = namespace_identity(workspace_id, agent_id, scope_key)
            workspace_id, agent_id, scope_key = identity
            scopes = self._read(workspace_id)
            key = _scope_storage_key(agent_id, scope_key)
            entry = scopes.get(key)
            legacy_key = _legacy_scope_key(agent_id, scope_key)
            if entry is None and legacy_key != key:
                # Pre-repair ambiguous key: still readable when its embedded
                # identity proves it is exactly this namespace.
                entry = scopes.get(legacy_key)
            if not isinstance(entry, dict):
                return None
            if _snapshot_identity(entry) != identity:
                logger.warning(
                    "bpe store namespace identity mismatch; refusing snapshot "
                    "for %r", identity,
                )
                return None
            return entry
        except Exception as e:
            logger.debug("bpe store load failed: %s", e)
            return None
