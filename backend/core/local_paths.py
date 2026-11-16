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


#: The PostgreSQL DBAPI declared by ``requirements.txt`` /
#: ``pyproject.toml`` (``psycopg2-binary``). SQLAlchemy 2.1 changed the
#: DEFAULT driver for a driver-less ``postgresql://`` URL to psycopg (psycopg3)
#: — https://docs.sqlalchemy.org/en/21/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2
#: — so an implicit URL would fail at engine construction on an installation
#: that only has the declared psycopg2 driver.
DECLARED_POSTGRES_DRIVER = "psycopg2"


def normalize_postgres_driver(value: str) -> str:
    """Pin a DRIVER-LESS PostgreSQL URL to the declared psycopg2 driver.

    Only the scheme token changes; the rest of the URL is preserved VERBATIM,
    so credentials escaping, IPv6 hosts, ports, database names and query
    strings (including SQLAlchemy's ``host``/``port`` query overrides) keep
    their existing semantics. Explicit driver choices are never rewritten:

    * ``postgresql://…`` / ``postgres://…`` → ``postgresql+psycopg2://…``
    * ``postgresql+psycopg2://``, ``postgresql+psycopg://``,
      ``postgresql+asyncpg://``, ``postgresql+pg8000://`` … unchanged
    * SQLite / redis / empty / ``None`` unchanged
    """
    if not value or not isinstance(value, str):
        return value
    for implicit in ("postgresql://", "postgres://"):
        if value.startswith(implicit):
            return (f"postgresql+{DECLARED_POSTGRES_DRIVER}://"
                    + value[len(implicit):])
    return value


def postgres_native_asyncpg_dsn(value: str) -> str:
    """Plain asyncpg DSN for a RAW ``asyncpg.connect`` client.

    asyncpg's DSN parser accepts only the ``postgres://`` / ``postgresql://``
    schemes (https://magicstack.github.io/asyncpg/current/api/index.html#asyncpg.connection.connect);
    a SQLAlchemy ``postgresql+asyncpg://`` (or any ``+driver``) suffix is NOT
    a valid native DSN. Strip the driver token only; endpoint, credential
    escaping and the query string remain verbatim so the native client
    reaches the same server with the same options.
    """
    if not value or not isinstance(value, str):
        return value
    lowered = value.lower()
    if lowered.startswith(("postgresql://", "postgres://")):
        return value
    if lowered.startswith("postgres+"):
        return "postgres://" + value.partition("://")[2]
    if lowered.startswith("postgresql+"):
        return "postgresql://" + value.partition("://")[2]
    return value


def postgres_asyncpg_url(value: str) -> str:
    """SQLAlchemy ASYNC ENGINE URL (``postgresql+asyncpg://``) for Postgres.

    This is an engine URL, not a native client DSN: raw ``asyncpg.connect``
    callers must use :func:`postgres_native_asyncpg_dsn`.

    Converts only driver-less URLs and the declared-default psycopg2 form
    produced by :func:`normalize_postgres_driver`; an explicit async or other
    driver is returned unchanged so callers keep their own choice.
    """
    if not value or not isinstance(value, str):
        return value
    for prefix in ("postgresql+psycopg2://", "postgresql://", "postgres://"):
        if value.startswith(prefix):
            return "postgresql+asyncpg://" + value[len(prefix):]
    return value


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
    fingerprint consumer (``core.db_safety``). It follows what the engine
    actually opens:

    * SQLAlchemy parses/unquotes the outer URL and produces the driver
      filename via ``SQLiteDialect_pysqlite.create_connect_args``;
    * when that driver filename uses ``uri=true``, the filename is parsed at
      the SQLite URI layer (``urlsplit``) and percent-decoded **once** for the
      filesystem path. Thus ``%23ignored``/``%3Fignored`` suffixes behave as
      the real engine does (fragment/query, still opening the protected file),
      while a double-encoded ``%2523`` becomes a literal ``#`` in the filename;
    * ``mode=memory`` is honored only from the actual driver URI query, so a
      plain non-URI URL with ``?mode=memory`` remains a disk file;
    * non-URI paths use the existing backend anchor; relative URI paths resolve
      against the current CWD exactly as SQLite does.

    Returns None for non-SQLite and actual in-memory databases. Raises
    ValueError for a malformed SQLite URL so live-data guards can fail closed.
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

    try:
        from sqlalchemy.dialects.sqlite.pysqlite import SQLiteDialect_pysqlite

        connect_args, connect_kwargs = (
            SQLiteDialect_pysqlite().create_connect_args(parsed))
    except Exception as exc:
        raise ValueError(f"cannot resolve SQLite connect args: {exc}") from exc
    filename = str(connect_args[0]) if connect_args else ""
    if not filename or filename == ":memory:":
        return None

    if filename.lower().startswith("file:") and connect_kwargs.get("uri"):
        from urllib.parse import parse_qs, unquote, urlsplit

        uri = urlsplit(filename)
        mode = (parse_qs(uri.query).get("mode") or [""])[0]
        if str(mode).lower() == "memory":
            return None
        candidate = unquote(uri.path)
    else:
        candidate = filename
    if not candidate or candidate == ":memory:":
        return None
    return str(Path(candidate).resolve(strict=False))
