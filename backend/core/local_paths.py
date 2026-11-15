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
            or path.startswith(("/", ":"))
            or path.lower().startswith("file:")
            or re.match(r"^[A-Za-z]:[\\/]", path)):
        return value
    root = Path(backend_root) if backend_root is not None else _BACKEND_ROOT
    anchored = os.path.abspath(os.path.normpath(os.path.join(str(root), path)))
    return f"{scheme}:///{anchored}{query}"


def sqlite_readonly_uri(path: str | os.PathLike) -> str:
    """Build a SQLite read-only ``file:`` URI for an actual filesystem path.

    SQLite interprets ``?`` and ``#`` in a URI as query/fragment separators,
    and percent-decodes the path. Interpolating a filesystem path directly
    (``file:{path}?mode=ro``) therefore breaks for names containing ``#``,
    ``?`` or ``%`` — the ``mode=ro`` query can be dropped and a different
    writable sibling file opened. Percent-encode the absolute path with
    ``quote(..., safe="/")`` so SQLite decodes back to the exact file.
    """
    absolute = os.path.abspath(os.fspath(path))
    from urllib.parse import quote

    return f"file:{quote(absolute, safe='/')}?mode=ro"


def resolve_sqlite_file_path(
    value: str, backend_root: Path | str | None = None,
) -> str | None:
    """Actual filesystem path a SQLAlchemy SQLite URL opens, or None.

    Shared by the live-DB pytest guard (``core.database``) and the backup /
    fingerprint consumer (``core.db_safety``). It does not prefix-split the
    URL: SQLAlchemy parses the driver/query, URI-mode filenames are
    percent-decoded **after** URI parsing (so an encoded ``#``/``?``/``%``
    stays part of the filename), and relative non-URI paths use the same
    backend anchor as the rest of the DB layer. Returns None for non-SQLite
    and in-memory / named-memory URLs; raises ValueError for a malformed
    SQLite URL so live-data guards can fail closed.
    """
    if (not value or not isinstance(value, str)
            or not value.lower().startswith("sqlite")):
        return None
    anchored = anchor_sqlite_url(value, backend_root)
    try:
        from sqlalchemy.engine import make_url

        parsed = make_url(anchored)
    except Exception as exc:
        raise ValueError(f"unparseable SQLite URL: {exc}") from exc
    if str(parsed.get_backend_name()).lower() != "sqlite":
        return None

    # Use the raw URL database segment, not ``parsed.database``: SQLAlchemy
    # percent-decodes the latter before creating connect args, which turns an
    # encoded ``%23`` into a literal ``#`` and loses the rest of the filename
    # to URI-fragment parsing.
    scheme, sep, rest = anchored.partition(":///")
    if not sep:
        return None
    raw_database, _, raw_query = rest.partition("?")
    if not raw_database:
        return None
    from urllib.parse import parse_qs

    query = parse_qs(raw_query, keep_blank_values=True)

    def _first(name: str) -> str:
        values = query.get(name) or [""]
        return str(values[0]).strip().lower()

    if _first("mode") == "memory":
        return None
    uri_mode = _first("uri") in {"1", "true", "yes", "on"}
    if raw_database == ":memory:":
        return None
    if raw_database.lower().startswith("file:"):
        if uri_mode:
            from urllib.parse import unquote, urlsplit

            candidate = unquote(urlsplit(raw_database).path)
        else:
            candidate = raw_database
    else:
        candidate = raw_database
    if not candidate or candidate == ":memory:":
        return None
    return str(Path(candidate).resolve(strict=False))
