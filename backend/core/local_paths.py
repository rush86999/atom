"""Canonical local storage paths anchored to backend, never the launch CWD."""
from pathlib import Path
import os
import re

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


def anchor_sqlite_url(value: str, backend_root: Path | str | None = None) -> str:
    """Anchor a relative SQLAlchemy SQLite file URL to the backend directory.

    SQLAlchemy resolves ``sqlite:///jobs.sqlite`` against the process CWD, so
    launching from the repo root vs ``backend/`` silently created two different
    stores. This reproduces the documented backend-launch location from any
    CWD. Only relative filesystem paths are rewritten:

    * ``sqlite:///jobs.sqlite`` / ``sqlite+pysqlite:///./jobs.sqlite`` →
      ``sqlite:////<backend>/jobs.sqlite``
    * absolute paths (``sqlite:////...``), ``:memory:``, ``sqlite://`` and
      ``file:`` URIs pass through unchanged;
    * non-SQLite URLs (postgresql, redis, …) pass through unchanged;
    * a query string (``?timeout=10``) is preserved verbatim.

    The normalization is deliberately the one already used by
    ``core.database.get_database_url``; no second URL parser is invented.
    """
    if (not value or not isinstance(value, str)
            or not value.lower().startswith("sqlite")):
        return value
    scheme, sep, rest = value.partition(":///")
    if not sep:
        return value
    path = rest
    query = ""
    if "?" in path:
        path, query = path.split("?", 1)
        query = "?" + query
    if (not path
            or path.startswith(("/", ":", "file:"))
            or re.match(r"^[A-Za-z]:[\\/]", path)):
        return value
    root = Path(backend_root) if backend_root is not None else _BACKEND_ROOT
    anchored = os.path.abspath(os.path.normpath(os.path.join(str(root), path)))
    return f"{scheme}:///{anchored}{query}"
