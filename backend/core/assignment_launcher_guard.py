"""Safety guard for disposable assignment-browser worlds.

The acceptance launcher must never delete a live/release/source directory
because an environment variable pointed at it. Only a verified disposable
directory under the OS temp root (or an explicitly configured scratch root)
is accepted, and deletion requires the launcher's marker plus an explicit
reset flag.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

MARKER_NAME = ".atom-assignment-browser-world"


class UnsafeScratchError(RuntimeError):
    """The requested scratch path is not provably disposable."""


def _allowed_roots() -> list[Path]:
    roots = [Path(tempfile.gettempdir()).resolve()]
    configured = os.getenv("ATOM_ASSIGNMENT_SCRATCH_ROOT")
    if configured:
        roots.append(Path(configured).expanduser().resolve())
    return roots


def _forbidden(path: Path) -> bool:
    text = str(path)
    forbidden = (
        "/backend/data",
        "/frontend-nextjs",
        "/docs/acceptance",
        "/node_modules",
        "/.git",
        "/Library",
        "/Applications",
        "/System",
        "/Volumes",
    )
    if any(part in text for part in forbidden):
        return True
    if path == Path("/") or path == Path.home().resolve():
        return True
    return False


def validate_scratch_dir(path: str | Path, *, must_exist: bool = False) -> Path:
    candidate = Path(path).expanduser().resolve()
    if _forbidden(candidate):
        raise UnsafeScratchError(
            f"refusing a live/release/source path: {candidate}")
    if not any(
        candidate == root or root in candidate.parents
        for root in _allowed_roots()
    ):
        raise UnsafeScratchError(
            f"scratch path is outside the approved temp/scratch roots: "
            f"{candidate}")
    if candidate.exists() and not candidate.is_dir():
        raise UnsafeScratchError(
            f"scratch path is not a directory: {candidate}")
    if must_exist and not candidate.exists():
        raise UnsafeScratchError(
            f"scratch path does not exist: {candidate}")
    return candidate


def prepare_scratch_dir(
    path: str | Path, *, reset: bool = False,
) -> Path:
    """Create or verify a disposable world; delete only with marker+reset."""
    candidate = validate_scratch_dir(path)
    marker = candidate / MARKER_NAME
    if candidate.exists() and any(candidate.iterdir()):
        if not marker.exists():
            raise UnsafeScratchError(
                f"refusing to reuse a non-empty directory without the "
                f"launcher marker: {candidate}")
        if reset:
            shutil.rmtree(candidate)
    candidate.mkdir(parents=True, exist_ok=True)
    marker.write_text("disposable assignment browser world\n")
    return candidate
