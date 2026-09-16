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
"""
from __future__ import annotations

import hashlib
import logging
import os
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
    started_monotonic: float = 0.0
    pid: int = 0
    port: Optional[int] = None
    error: Optional[str] = None

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
            "pid": self.pid,
            "port": self.port,
            "error": self.error,
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


def capture_runtime_identity(cwd: Optional[str] = None) -> RuntimeIdentity:
    """Compute the identity ONCE for this process.

    Never raises: an install without git (or without a repository) still gets a
    usable identity, with ``error`` explaining what could not be determined.
    An unknown revision is reported as unknown — never silently as "clean".
    """
    backend_dir = cwd or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    repo_dir = os.path.dirname(backend_dir)
    started = time.monotonic()
    now = datetime.now(timezone.utc).isoformat()
    port: Optional[int] = None
    try:
        import sys

        if "--port" in sys.argv:
            port = int(sys.argv[sys.argv.index("--port") + 1])
    except Exception:  # noqa: BLE001
        port = None

    revision, dirty_paths, untracked_paths, error = "unknown", [], [], None
    try:
        rev = _git(["rev-parse", "HEAD"], repo_dir)
        if rev:
            revision = rev.strip()
        else:
            error = "git rev-parse failed (no repository or no git)"
        status = _git(["status", "--porcelain=v1", "--untracked-files=all"],
                      repo_dir) or ""
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
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"

    # Digest the CONTENT of every modified/untracked file, so two different
    # edits to the same path are distinguishable (a path list is not a state).
    entries: List[str] = []
    for path in dirty_paths + untracked_paths:
        full = os.path.join(repo_dir, path)
        entries.append(f"{path}:{_digest_file(full) if os.path.isfile(full) else 'absent'}")
    digest = hashlib.sha256("\n".join(sorted(entries)).encode()).hexdigest()[:12]
    dirty = bool(dirty_paths or untracked_paths)
    source_id = f"{revision[:12]}{'-dirty.' + digest if dirty else ''}"

    identity = RuntimeIdentity(
        source_id=source_id,
        instance_id=f"{source_id}.{os.getpid()}.{int(time.time())}",
        revision=revision,
        dirty=dirty,
        dirty_digest=digest,
        dirty_paths=sorted(dirty_paths),
        untracked_paths=sorted(untracked_paths),
        captured_at=now,
        started_monotonic=started,
        pid=os.getpid(),
        port=port,
        error=error,
    )
    logger.info(
        "runtime identity: source_id=%s revision=%s dirty=%s (%d modified, "
        "%d untracked)", identity.source_id, identity.revision[:12],
        identity.dirty, len(identity.dirty_paths), len(identity.untracked_paths))
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
