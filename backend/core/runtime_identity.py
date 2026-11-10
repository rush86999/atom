# -*- coding: utf-8 -*-
"""Immutable runtime identity: WHICH SOURCE a serving process actually loaded.

Why this exists
===============

PID and start time identify an *instance*. They say nothing about which source
contents that instance is running, and resolving ``HEAD`` per health request is
worse than useless — it reports the repository's current state, not the state
that was loaded at boot. On a tree that is being edited (several agents, an
uncommitted fix, a worktree), those two answers diverge silently, and an
acceptance run gets attributed to code that never executed.

So the identity is captured ONCE, at process start, and never re-resolved:

``revision``
    the commit checked out at boot (``git rev-parse HEAD``).
``dirty`` / ``dirty_digest``
    whether the working tree differed from that commit, and a digest over the
    tracked-and-untracked modifications. This is what makes "uncommitted fix
    X was live" a checkable claim instead of an assumption.
``source_id``
    ``<revision>[-dirty.<digest>]`` — one stable string for one set of source
    contents. Two processes with the same ``source_id`` loaded the same code.
``instance_id``
    ``<source_id>.<pid>.<boot-epoch>`` — distinguishes two processes serving
    the same source (a rolling restart), which PID alone does in principle but
    not portably across pid reuse.

The identity is exposed on ``GET /api/health`` (``identity``) and stamped on
responses as ``X-Atom-Serving-Instance`` (plus ``X-Atom-Source``), so a caller
can attribute ITS OWN request to the instance that served it without a separate
health probe that may have hit a different process.

Git is trusted only when ``git rev-parse --show-toplevel`` IS the loaded source
root. An immutable export/install nested beneath another checkout must never
inherit that ancestor's HEAD or dirty state: it is identified from the existing
world/export ``MANIFEST.json`` + ``code_manifest.json`` contract, or reported as
``identity_kind="unknown"`` with the actual loaded path and an explicit error.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: Files larger than this are identified by size+mtime rather than content —
#: hashing a multi-GB artifact at boot would cost more than it proves.
_MAX_HASH_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class RuntimeIdentity:
    source_id: str
    instance_id: str
    revision: str
    dirty: bool
    dirty_digest: str
    dirty_paths: List[str] = field(default_factory=list)
    untracked_paths: List[str] = field(default_factory=list)
    captured_at: str = ""
    process_started_at: str = ""
    started_monotonic: float = 0.0
    pid: int = 0
    port: Optional[int] = None
    repo_path: str = ""
    backend_path: str = ""
    error: Optional[str] = None
    #: "git" for a checkout rooted at the loaded source, "export" for an
    #: immutable acceptance/export tree with MANIFEST+code_manifest metadata,
    #: "unknown" when neither can be established truthfully.
    identity_kind: str = "unknown"
    export_sha256: Optional[str] = None
    export_manifest_sha256: Optional[str] = None
    code_manifest_sha256: Optional[str] = None
    #: The verified Git top-level when this is a native checkout.
    git_toplevel: Optional[str] = None
    #: An enclosing repository that was deliberately NOT used to identify an
    #: export/install. Recorded for diagnosis only.
    ancestor_git_toplevel: Optional[str] = None
    #: False when dirty state could not be read; source_id then carries an
    #: explicit -unverified suffix rather than implying clean.
    dirty_known: bool = True

    def as_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "instance_id": self.instance_id,
            "revision": self.revision,
            "dirty": self.dirty,
            "dirty_digest": self.dirty_digest,
            "dirty_paths": self.dirty_paths[:40],
            "untracked_paths": self.untracked_paths[:40],
            "captured_at": self.captured_at,
            "process_started_at": self.process_started_at,
            "pid": self.pid,
            "port": self.port,
            "repo_path": self.repo_path,
            "backend_path": self.backend_path,
            "error": self.error,
            "identity_kind": self.identity_kind,
            "export_sha256": self.export_sha256,
            "export_manifest_sha256": self.export_manifest_sha256,
            "code_manifest_sha256": self.code_manifest_sha256,
            "git_toplevel": self.git_toplevel,
            "ancestor_git_toplevel": self.ancestor_git_toplevel,
            "dirty_known": self.dirty_known,
        }

    def headers(self) -> Dict[str, str]:
        """Headers a response carries so the CALLER can attribute its own request."""
        return {
            "X-Atom-Serving-Instance": self.instance_id,
            "X-Atom-Source": self.source_id,
        }


_IDENTITY: Optional[RuntimeIdentity] = None
_LOCK = threading.Lock()


def _git(args: List[str], cwd: str) -> Optional[str]:
    try:
        out = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10)
    except Exception:  # noqa: BLE001 — git may be absent
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def _digest_file(path: str) -> str:
    try:
        size = os.path.getsize(path)
        if size > _MAX_HASH_BYTES:
            return f"size:{size}:mtime:{int(os.path.getmtime(path))}"
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(65536), b""):
                h.update(block)
        return h.hexdigest()[:16]
    except Exception as exc:  # noqa: BLE001
        return f"unreadable:{type(exc).__name__}"


_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _read_export_metadata(repo_dir: str) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Read the existing world/export metadata contract, never invent one.

    run_isolated verifies the exported tree against ``code_manifest.json`` and
    pins the export tar in ``MANIFEST.json`` before launch. Runtime identity
    reuses those two files as metadata; it does not create a second provenance
    store and it does not inspect an ancestor Git checkout.
    """
    manifest_path = os.path.join(repo_dir, "MANIFEST.json")
    code_manifest_path = os.path.join(repo_dir, "code_manifest.json")
    if not os.path.isfile(manifest_path):
        return None, (
            "loaded source is not a Git checkout and has no export MANIFEST.json; "
            "an enclosing repository cannot certify it")
    if not os.path.isfile(code_manifest_path):
        return None, (
            "loaded source is not a Git checkout and export metadata is missing "
            "code_manifest.json")
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        return None, f"export MANIFEST.json is unreadable/malformed: {type(exc).__name__}"
    if not isinstance(manifest, dict):
        return None, "export MANIFEST.json is not an object"

    candidates = {
        str(value).strip().lower()
        for value in (
            manifest.get("code_snapshot_sha256"),
            manifest.get("code_archive_sha256"),
        )
        if value
    }
    if not candidates:
        return None, "export MANIFEST.json has no snapshot/archive code hash"
    if len(candidates) != 1:
        return None, "export MANIFEST.json has conflicting snapshot/archive code hashes"
    export_sha = next(iter(candidates))
    if not _HEX64.fullmatch(export_sha):
        return None, "export code hash is malformed (expected 64 hex characters)"

    try:
        with open(code_manifest_path, "r", encoding="utf-8") as fh:
            code_manifest = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        return None, f"export code_manifest.json is unreadable/malformed: {type(exc).__name__}"
    if not isinstance(code_manifest, (dict, list)) or not code_manifest:
        return None, "export code_manifest.json is empty or malformed"

    return {
        "export_sha256": export_sha,
        "export_manifest_sha256": _sha256_file(manifest_path),
        "code_manifest_sha256": _sha256_file(code_manifest_path),
    }, None


def capture_runtime_identity(cwd: Optional[str] = None) -> RuntimeIdentity:
    """Compute the identity ONCE for this process.

    Never raises: an install without git (or without a repository) still gets a
    usable identity, with ``error`` explaining what could not be determined.
    An unknown revision is reported as unknown — never silently as "clean", and
    never as an ancestor checkout's revision.
    """
    backend_dir = cwd or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    repo_dir = os.path.dirname(backend_dir)
    started = time.monotonic()
    now = datetime.now(timezone.utc).isoformat()
    process_started_at = datetime.fromtimestamp(
        time.time() - time.monotonic() + started,
        timezone.utc).isoformat()
    port: Optional[int] = None
    try:
        import sys

        if "--port" in sys.argv:
            port = int(sys.argv[sys.argv.index("--port") + 1])
    except Exception:  # noqa: BLE001
        port = None

    revision, dirty_paths, untracked_paths, error = "unknown", [], [], None
    dirty_digest = ""
    dirty = False
    dirty_known = False
    identity_kind = "unknown"
    export_sha = None
    export_manifest_sha = None
    code_manifest_sha = None
    git_toplevel = None
    ancestor_toplevel = None

    # Git may answer from an ancestor checkout when the loaded source is an
    # export nested beneath it. Trust Git only when its top-level IS the
    # source root we are identifying.
    observed_toplevel = _git(["rev-parse", "--show-toplevel"], repo_dir)
    is_worktree = _git(["rev-parse", "--is-inside-work-tree"], repo_dir)
    observed_toplevel = observed_toplevel.strip() if observed_toplevel else ""
    native_git = bool(
        observed_toplevel
        and is_worktree
        and is_worktree.strip().lower() == "true"
        and os.path.realpath(observed_toplevel) == os.path.realpath(repo_dir)
    )

    if native_git:
        git_toplevel = observed_toplevel
        try:
            rev = _git(["rev-parse", "HEAD"], repo_dir)
            if rev:
                revision = rev.strip()
                identity_kind = "git"
                status = _git(
                    ["status", "--porcelain=v1", "--untracked-files=all"],
                    repo_dir)
                if status is None:
                    error = "git status failed; dirty state is unknown"
                    dirty_known = False
                else:
                    dirty_known = True
                    for line in status.splitlines():
                        if len(line) < 4:
                            continue
                        path = line[3:].strip().strip('"')
                        if not path:
                            continue
                        if line.startswith("??"):
                            untracked_paths.append(path)
                        else:
                            dirty_paths.append(path)
            else:
                error = "git rev-parse HEAD failed (empty repository?)"
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
    else:
        # Do NOT use the ancestor checkout. An export/install is identifiable
        # only through its verified export metadata; otherwise report unknown.
        ancestor_toplevel = observed_toplevel or None
        export_meta, export_error = _read_export_metadata(repo_dir)
        if export_meta:
            identity_kind = "export"
            export_sha = export_meta["export_sha256"]
            export_manifest_sha = export_meta["export_manifest_sha256"]
            code_manifest_sha = export_meta["code_manifest_sha256"]
            revision = "unknown"
            dirty_known = True
            dirty = False
        else:
            identity_kind = "unknown"
            revision = "unknown"
            dirty_known = False
            error = export_error

    if identity_kind == "git":
        # Digest the CONTENT of every modified/untracked file, so two different
        # edits to the same path are distinguishable (a path list is not a state).
        entries: List[str] = []
        if dirty_known:
            for path in dirty_paths + untracked_paths:
                full = os.path.join(repo_dir, path)
                entries.append(
                    f"{path}:{_digest_file(full) if os.path.isfile(full) else 'absent'}")
            dirty_digest = hashlib.sha256(
                "\n".join(sorted(entries)).encode()).hexdigest()[:12]
            dirty = bool(dirty_paths or untracked_paths)
        if not dirty_known:
            source_id = f"{revision[:12]}-unverified"
        else:
            source_id = f"{revision[:12]}{'-dirty.' + dirty_digest if dirty else ''}"
    elif identity_kind == "export":
        source_id = f"export-sha256:{export_sha[:12]}"
    else:
        source_id = "unknown"

    identity = RuntimeIdentity(
        source_id=source_id,
        instance_id=f"{source_id}.{os.getpid()}.{int(time.time())}",
        revision=revision,
        dirty=dirty,
        dirty_digest=dirty_digest,
        dirty_paths=sorted(dirty_paths),
        untracked_paths=sorted(untracked_paths),
        captured_at=now,
        process_started_at=process_started_at,
        started_monotonic=started,
        pid=os.getpid(),
        port=port,
        repo_path=repo_dir,
        backend_path=backend_dir,
        error=error,
        identity_kind=identity_kind,
        export_sha256=export_sha,
        export_manifest_sha256=export_manifest_sha,
        code_manifest_sha256=code_manifest_sha,
        git_toplevel=git_toplevel,
        ancestor_git_toplevel=ancestor_toplevel,
        dirty_known=dirty_known,
    )
    logger.info(
        "runtime identity: kind=%s source_id=%s revision=%s dirty=%s "
        "(%d modified, %d untracked) export=%s",
        identity.identity_kind, identity.source_id, identity.revision[:12],
        identity.dirty, len(identity.dirty_paths),
        len(identity.untracked_paths), identity.export_sha256[:12]
        if identity.export_sha256 else "")
    return identity


def get_runtime_identity() -> RuntimeIdentity:
    """The identity captured for THIS process (computed on first use, frozen)."""
    global _IDENTITY
    if _IDENTITY is None:
        with _LOCK:
            if _IDENTITY is None:
                _IDENTITY = capture_runtime_identity()
    return _IDENTITY


def reset_runtime_identity_for_tests() -> None:
    global _IDENTITY
    with _LOCK:
        _IDENTITY = None
