"""Self-healing, version-aware bootstrap for LanceDB full-text (FTS) indexes.

Why this exists
---------------
``table.create_fts_index(column, replace=True)`` is *not* sufficient to heal an
index written by a different LanceDB version. When the installed reader cannot
use the on-disk index format it logs::

    [WARN lance::index] Index content_idx has version 2, which is not
    supported (<=0), ignoring it

and silently falls back to a full scan on every query. Results stay correct but
the FTS performance win is lost *permanently*: ``replace=True`` re-uses the
incompatible index instead of rewriting it, so the warning recurs on every
boot. Only an explicit ``drop_index`` followed by a fresh ``create_fts_index``
actually rewrites it.

Calling that drop+recreate unconditionally on every boot would be wasteful, so
this module records — in a small on-disk marker next to the LanceDB data —
which library version last built the index for a given table. When the marker
matches the installed version and the index exists, the call is a no-op; when
anything is missing or stale, the index is rebuilt once.

The function never raises: a broken FTS bootstrap must not stop the app from
starting.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Set

logger = logging.getLogger(__name__)

#: Directory (relative to the LanceDB database dir) that holds marker files.
_MARKER_DIRNAME = ".lancedb_fts_index"

#: Bumped if the marker payload layout ever changes.
_MARKER_SCHEMA = 1


def _installed_lancedb_version() -> Optional[str]:
    """Return the installed ``lancedb`` version, or ``None`` if unavailable.

    Returns:
        The version string reported by ``lancedb.__version__``, or ``None``
        when the library cannot be imported or exposes no version.
    """
    try:
        import lancedb
    except Exception:
        return None
    try:
        version = getattr(lancedb, "__version__", None)
    except Exception:
        return None
    return str(version) if version else None


def _default_index_name(column: str) -> str:
    """Return the index name LanceDB derives for ``column``.

    Args:
        column: The indexed column name.

    Returns:
        The default index name (``<column>_idx``).
    """
    return f"{column}_idx"


def _table_name(table: Any) -> str:
    """Best-effort table name, used to keep marker files per-table.

    Args:
        table: A LanceDB table (or any object).

    Returns:
        The table name, or ``"table"`` when it cannot be determined.
    """
    try:
        name = getattr(table, "name", None)
    except Exception:
        name = None
    return name if isinstance(name, str) and name else "table"


def _connection_uri(table: Any) -> Optional[str]:
    """Best-effort LanceDB database URI for ``table``.

    Args:
        table: A LanceDB table (or any object).

    Returns:
        The connection/dataset URI string, or ``None`` if unavailable.
    """
    try:
        connection = getattr(table, "_conn", None)
        uri = getattr(connection, "uri", None) if connection is not None else None
        if isinstance(uri, str) and uri:
            return uri
    except Exception:
        pass
    try:
        dataset_uri = getattr(table, "_dataset_uri", None)
        if isinstance(dataset_uri, str) and dataset_uri:
            return dataset_uri
    except Exception:
        pass
    return None


def _local_db_dir(table: Any) -> Optional[Path]:
    """Return the local directory backing ``table``'s database, if any.

    Remote (S3/R2) and relative URIs return ``None`` — the marker then lands in
    a local fallback directory so it still survives restarts.

    Args:
        table: A LanceDB table (or any object).

    Returns:
        An absolute :class:`Path` for a local store, otherwise ``None``.
    """
    uri = _connection_uri(table)
    if not uri:
        return None
    if "://" in uri:
        if not uri.startswith("file://"):
            return None
        uri = uri[len("file://") :]
    if uri.endswith(".lance"):
        # Fell back to the dataset URI rather than the connection URI.
        uri = str(Path(uri).parent)
    try:
        path = Path(uri).expanduser()
    except Exception:
        return None
    return path if path.is_absolute() else None


def _fallback_marker_root() -> Path:
    """Return the local fallback directory for markers of non-local stores.

    Returns:
        An absolute :class:`Path` under the backend ``data/`` directory
        (overridable via ``ATOM_LANCEDB_FTS_MARKER_DIR``).
    """
    override = os.getenv("ATOM_LANCEDB_FTS_MARKER_DIR")
    if override:
        return Path(override).expanduser()
    backend_data = Path(__file__).resolve().parent.parent / "data"
    return backend_data / _MARKER_DIRNAME


def _safe_component(value: str) -> str:
    """Sanitize a value for use as a filename component.

    Args:
        value: Raw text (table name, URI, …).

    Returns:
        A filesystem-safe component; non-alphanumerics become ``_``.
    """
    cleaned = "".join(ch if (ch.isalnum() or ch in "-.") else "_" for ch in value)
    return cleaned.strip("._") or "unnamed"


def _ensure_parent(path: Path) -> None:
    """Create ``path``'s parent directories, best-effort.

    Args:
        path: The marker file path whose parent should exist.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Could not create FTS marker dir %s: %s", path.parent, exc)


def _resolve_marker_path(
    table: Any, column: str, marker_key: Optional[str]
) -> Optional[Path]:
    """Compute the on-disk marker path for a table's FTS index.

    Args:
        table: The LanceDB table the marker describes.
        column: The indexed column name.
        marker_key: Optional explicit marker path override. When provided it is
            used verbatim (this is what tests and exotic stores should pass).

    Returns:
        The marker :class:`Path`, or ``None`` if one cannot be determined.
    """
    if marker_key:
        path = Path(str(marker_key)).expanduser()
        _ensure_parent(path)
        return path
    db_dir = _local_db_dir(table)
    if db_dir is not None:
        root = db_dir / _MARKER_DIRNAME
    else:
        scope = _safe_component(_connection_uri(table) or "nonlocal")
        root = _fallback_marker_root() / scope
    path = root / f"{_safe_component(_table_name(table))}.{_safe_component(column)}.json"
    _ensure_parent(path)
    return path


def _read_marker_version(marker: Path) -> Optional[str]:
    """Read the LanceDB version recorded in a marker file.

    Args:
        marker: Path to the marker JSON file.

    Returns:
        The recorded version string, or ``None`` when absent/unreadable.
    """
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    version = payload.get("version")
    return str(version) if version else None


def _write_marker(
    marker: Path, version: str, table_name: str, column: str, index_name: str
) -> None:
    """Persist the version that just (re)built the index.

    Args:
        marker: Path to the marker JSON file.
        version: Installed ``lancedb`` version.
        table_name: LanceDB table name.
        column: Indexed column name.
        index_name: Name of the FTS index that was built.

    Raises:
        OSError: If the marker cannot be written.
    """
    _ensure_parent(marker)
    payload = {
        "schema": _MARKER_SCHEMA,
        "version": version,
        "table": table_name,
        "column": column,
        "index": index_name,
        "rebuilt_at": datetime.now(timezone.utc).isoformat(),
    }
    marker.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _list_index_configs(table: Any) -> List[Any]:
    """Return the table's index configs, or ``[]`` when unavailable.

    Args:
        table: The LanceDB table.

    Returns:
        A list of index configuration objects (possibly empty).
    """
    try:
        return list(table.list_indices())
    except Exception as exc:
        logger.debug("list_indices() unavailable: %s", exc)
        return []


def _config_name(config: Any) -> Optional[str]:
    """Return an index config's name, if any.

    Args:
        config: A LanceDB index configuration object.

    Returns:
        The index name, or ``None``.
    """
    try:
        name = getattr(config, "name", None)
    except Exception:
        return None
    return name if isinstance(name, str) and name else None


def _config_columns(config: Any) -> Set[str]:
    """Return the set of columns an index config covers.

    Args:
        config: A LanceDB index configuration object.

    Returns:
        A set of column names (empty when unavailable).
    """
    try:
        columns = getattr(config, "columns", None) or []
        return {str(col) for col in columns}
    except Exception:
        return set()


def _config_index_type(config: Any) -> str:
    """Return an index config's type (e.g. ``FTS``), upper-cased.

    Args:
        config: A LanceDB index configuration object.

    Returns:
        The upper-cased index type, or ``""``.
    """
    try:
        index_type = getattr(config, "index_type", None)
    except Exception:
        return ""
    return str(index_type).upper() if index_type else ""


def _is_fts_config(config: Any) -> bool:
    """Whether an index config describes a full-text index.

    Args:
        config: A LanceDB index configuration object.

    Returns:
        ``True`` for FTS-style indices, or for configs whose type is unknown
        (older LanceDB reported FTS indices without a type).
    """
    index_type = _config_index_type(config)
    if not index_type:
        return True
    return any(token in index_type for token in ("FTS", "FULL_TEXT", "TANTIVY"))


def _index_exists(table: Any, index_name: str, column: str) -> bool:
    """Whether a usable FTS index already exists for ``column``.

    Accepts either the exact expected name or any FTS index covering the
    column, since the derived name can differ between LanceDB versions.

    Args:
        table: The LanceDB table.
        index_name: The expected index name.
        column: The indexed column name.

    Returns:
        ``True`` when an FTS index for the column is listed.
    """
    for config in _list_index_configs(table):
        name = _config_name(config)
        if name == index_name:
            return True
        if column in _config_columns(config) and _is_fts_config(config):
            return True
    return False


def _drop_existing_indexes(table: Any, column: str, index_name: str) -> None:
    """Drop the existing FTS index(es) for ``column`` before a rebuild.

    "Not found"-style errors are swallowed: the goal is to remove a
    reader-rejected index when present, not to fail when it is already gone.

    Args:
        table: The LanceDB table.
        column: The indexed column name.
        index_name: The expected index name; the actual listed name is used
            when it differs.
    """
    configs = _list_index_configs(table)
    listed_names = {name for name in (_config_name(c) for c in configs) if name}
    to_drop: Set[str] = set()
    for config in configs:
        name = _config_name(config)
        if not name:
            continue
        if name == index_name:
            to_drop.add(name)
        elif column in _config_columns(config) and _is_fts_config(config):
            to_drop.add(name)
    if index_name not in listed_names:
        # Best-effort: some versions do not surface FTS indices via
        # list_indices() and only accept the derived name at drop time.
        to_drop.add(index_name)

    for name in sorted(to_drop):
        try:
            table.drop_index(name)
            logger.info("Dropped stale FTS index '%s'", name)
        except Exception as exc:
            logger.debug("drop_index(%s) skipped: %s", name, exc)


def ensure_fts_index(
    table: Any,
    column: str = "content",
    index_name: Optional[str] = None,
    marker_key: Optional[str] = None,
) -> bool:
    """Ensure ``table`` has a *readable* FTS index, rebuilding only when needed.

    Steady state (marker matches the installed ``lancedb`` version and the
    index is present) is a cheap no-op. Otherwise the index is dropped and
    recreated — the only way to rewrite an index whose on-disk format the
    installed reader rejects.

    Args:
        table: A LanceDB table object.
        column: The column to index (default ``"content"``).
        index_name: Expected FTS index name; ``None`` uses LanceDB's derived
            ``<column>_idx``. The listed name is used when it differs.
        marker_key: Optional explicit marker file path. When omitted the marker
            is stored beside the LanceDB data, keyed by table and column.

    Returns:
        ``True`` when an FTS index is available for ``column`` (whether it was
        rebuilt or already healthy), ``False`` on any failure. Never raises.
    """
    target_name = index_name or _default_index_name(column)
    try:
        version = _installed_lancedb_version() or "unknown"
        marker = _resolve_marker_path(table, column, marker_key)

        marker_fresh = False
        if marker is not None:
            try:
                marker_fresh = (
                    marker.exists() and _read_marker_version(marker) == version
                )
            except Exception:
                marker_fresh = False

        if marker_fresh and _index_exists(table, target_name, column):
            logger.debug(
                "FTS index '%s' already built by lancedb %s — skipping rebuild",
                target_name,
                version,
            )
            return True

        _drop_existing_indexes(table, column, target_name)
        table.create_fts_index(column, replace=True)

        if marker is not None:
            # A marker write failure only costs one extra rebuild next boot; the
            # index itself is already usable, so do not report it as down.
            try:
                _write_marker(
                    marker,
                    version,
                    _table_name(table),
                    column,
                    target_name,
                )
            except Exception as exc:
                logger.warning(
                    "FTS index '%s' built but version marker not written: %s",
                    target_name,
                    exc,
                )

        logger.info(
            "FTS index '%s' (re)built on '%s' for lancedb %s",
            target_name,
            column,
            version,
        )
        return True
    except Exception as exc:
        logger.warning(
            "FTS index self-heal failed for '%s' (non-fatal): %s", target_name, exc
        )
        return False
