"""Canonical local storage paths anchored to backend, never the launch CWD."""
from pathlib import Path
import os

_BACKEND_ROOT = Path(__file__).resolve().parents[1]


def resolve_local_path(value: str | os.PathLike) -> Path:
    """Resolve local paths without granting access or creating/moving files.

    Absolute configured paths retain their location. Relative paths use the
    documented backend launch root; callers still enforce owned containment.
    """
    raw = os.fspath(value)
    if not raw.strip():
        raise ValueError("empty local path")
    path = Path(os.path.expanduser(raw))
    if not path.is_absolute():
        path = _BACKEND_ROOT / path
    return path.resolve()
