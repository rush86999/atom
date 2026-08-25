"""Runtime settings resolver — env vars as UI-administrable settings.

Resolution precedence (kill-switch semantics preserved):

    1. explicit env var   → source="env"      (operator hard-override)
    2. runtime_settings DB row → source="db"  (UI admin edit)
    3. catalog default    → source="default"

The DB leg is cached module-globally with a TTL (default 60s) so hot
flag checks never hit the database; writes call
``invalidate_settings_cache()``. Env vars are read fresh on every
resolve — they are NEVER cached — so test patches and process-env
changes take effect immediately.

Never raises: unknown keys, missing tables, bad JSON, coercion
failures all degrade to the next leg (log + default).
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

from core.settings_catalog import SETTING_CATALOG, find_spec

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedSetting:
    """A single resolved value + where it came from."""

    value: Any
    source: str  # "env" | "db" | "default" | "unknown"


_CACHE_TTL_SECONDS = float(os.getenv("ATOM_SETTINGS_CACHE_TTL", "60"))
_cache_rows: Optional[dict[str, Any]] = None
_cache_loaded_at: float = 0.0


def invalidate_settings_cache() -> None:
    """Drop the cached DB snapshot (called after every UI write)."""
    global _cache_rows, _cache_loaded_at
    _cache_rows = None
    _cache_loaded_at = 0.0


# ---------------------------------------------------------------------------
# Coercion
# ---------------------------------------------------------------------------


def _coerce(raw: Any, spec_type: str) -> Any:
    """Coerce ``raw`` to ``spec_type``; raises ValueError on garbage."""
    if raw is None:
        raise ValueError("None value")
    if spec_type == "bool":
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}
    if spec_type == "int":
        if isinstance(raw, bool):
            raise ValueError("bool is not int")
        if isinstance(raw, int):
            return raw
        return int(str(raw).strip())
    if spec_type == "float":
        if isinstance(raw, bool):
            raise ValueError("bool is not float")
        if isinstance(raw, (int, float)):
            return float(raw)
        return float(str(raw).strip())
    if spec_type == "json":
        if isinstance(raw, str):
            import json

            return json.loads(raw)
        return raw
    # str
    if isinstance(raw, str):
        return raw
    return str(raw)


def _coerce_or_none(key_name: str, raw: Any, spec_type: str) -> Any:
    try:
        return _coerce(raw, spec_type)
    except Exception as exc:
        logger.warning(f"Runtime setting {key_name}: coercion failed ({exc})")
        return None


# ---------------------------------------------------------------------------
# DB snapshot (TTL-cached)
# ---------------------------------------------------------------------------


def _db_snapshot(db: Any = None) -> dict[str, Any]:
    """Whole-table snapshot of runtime_settings rows, TTL-cached."""
    global _cache_rows, _cache_loaded_at

    now = time.monotonic()
    if _cache_rows is not None and (now - _cache_loaded_at) < _CACHE_TTL_SECONDS:
        return _cache_rows

    rows: dict[str, Any] = {}
    try:
        from core.models import RuntimeSetting

        if db is not None:
            for row in db.query(RuntimeSetting).all():
                rows[row.key] = row.value_json
        else:
            from core.database import get_db_session

            with get_db_session() as session:
                for row in session.query(RuntimeSetting).all():
                    rows[row.key] = row.value_json
        _cache_rows = rows
        _cache_loaded_at = now
    except Exception as exc:
        # Missing table / fresh dev DB / transient failure → defaults.
        logger.debug(f"Runtime settings DB read unavailable ({exc}); using env/defaults")
        _cache_rows = rows or {}
        _cache_loaded_at = now
    return _cache_rows


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_setting(key_name: str, db: Any = None) -> ResolvedSetting:
    """Resolve one setting through env > db > default."""
    spec = find_spec(key_name)
    if spec is None:
        return ResolvedSetting(value=None, source="unknown")

    # 1. Explicit environment override always wins. Read fresh — never cached.
    env_raw = os.environ.get(key_name)
    if env_raw is not None:
        coerced = _coerce_or_none(key_name, env_raw, spec.type)
        if coerced is not None:
            return ResolvedSetting(value=coerced, source="env")
        # Garbage env value: fall through to db/default (never raise).

    # 2. UI-persisted row.
    rows = _db_snapshot(db)
    if key_name in rows and rows[key_name] is not None:
        coerced = _coerce_or_none(key_name, rows[key_name], spec.type)
        if coerced is not None:
            return ResolvedSetting(value=coerced, source="db")

    # 3. Catalog default.
    return ResolvedSetting(value=spec.default, source="default")


def get_setting(key_name: str, default: Any = None, db: Any = None) -> Any:
    """Bare-value convenience wrapper."""
    res = resolve_setting(key_name, db=db)
    if res.source == "unknown":
        return default
    return res.value


def get_bool_setting(key_name: str, default: bool = False, db: Any = None) -> bool:
    res = resolve_setting(key_name, db=db)
    if isinstance(res.value, bool):
        return res.value
    return default


def get_int_setting(key_name: str, default: int = 0, db: Any = None) -> int:
    res = resolve_setting(key_name, db=db)
    if isinstance(res.value, int) and not isinstance(res.value, bool):
        return res.value
    return default


def get_float_setting(key_name: str, default: float = 0.0, db: Any = None) -> float:
    res = resolve_setting(key_name, db=db)
    if isinstance(res.value, (int, float)) and not isinstance(res.value, bool):
        return float(res.value)
    return default


def catalog_size() -> int:
    """Number of cataloged settings (introspection/testing helper)."""
    return len(SETTING_CATALOG)
