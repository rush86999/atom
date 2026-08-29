"""Per-table embedding identity registry.

Records which embedding provider/model/dimension each LanceDB table's
vectors were produced with. Without this, switching embedding models is
invisible:

- dimension change → hard "query dim(...) doesn't match" failures (or worse,
  a ``mode="overwrite"`` table create silently wiping the table);
- same-dimension model change (e.g. two different 384-dim models) → NO
  failure at all, but old and new vectors live in different vector spaces
  and similarity results quietly become garbage.

The registry is a small JSON file under backend/data (anchored, like the
BYOK store) with in-process caching. All functions fail open and never
raise — a broken registry must not take down vector search.
"""

import json
import logging
import os
import re
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Anchored to backend/ — independent of the launch CWD (same treatment as
# the BYOK key store). EMBEDDING_REGISTRY_FILE overrides for tests; resolved
# per call so tests can retarget it after this module is imported.
_DEFAULT_REGISTRY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "embedding_registry.json",
)


def _registry_file() -> str:
    return os.getenv("EMBEDDING_REGISTRY_FILE") or _DEFAULT_REGISTRY_FILE

_LOCK = threading.Lock()
_CACHE: Optional[Dict[str, Any]] = None

_DIM_RE = re.compile(r"fixed_size_list<[^>]*>\[(\d+)\]")


def _load() -> Dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        with open(_registry_file(), "r") as f:
            _CACHE = json.load(f)
    except Exception:
        _CACHE = {}
    return _CACHE


def _save(data: Dict[str, Any]) -> None:
    try:
        path = _registry_file()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except Exception as e:
        logger.error(f"Failed to save embedding registry: {e}")


def reload() -> None:
    """Drop the in-process cache (tests, external edits)."""
    global _CACHE
    with _LOCK:
        _CACHE = None


def get(table_name: str) -> Optional[Dict[str, Any]]:
    """Identity recorded for a table: {provider, model, dim} or None."""
    with _LOCK:
        entry = _load().get(table_name)
    return dict(entry) if isinstance(entry, dict) else None


def set_identity(table_name: str, provider: str, model: str, dim: int) -> None:
    """Record the embedding identity a table's vectors were produced with."""
    if not table_name:
        return
    with _LOCK:
        data = _load()
        data[table_name] = {
            "provider": str(provider),
            "model": str(model),
            "dim": int(dim),
        }
        _save(data)


def forget(table_name: str) -> None:
    with _LOCK:
        data = _load()
        if table_name in data:
            data.pop(table_name, None)
            _save(data)


def dim_from_schema(schema: Any, column: str = "vector") -> Optional[int]:
    """Extract the fixed vector dimension from a pyarrow/LanceDB schema."""
    try:
        for field in schema:
            if field.name == column:
                match = _DIM_RE.search(str(field.type))
                if match:
                    return int(match.group(1))
    except Exception:
        pass
    return None


def classify(
    identity: Optional[Dict[str, Any]],
    active_provider: str,
    active_model: str,
    active_dim: Optional[int],
) -> str:
    """Compare a table's recorded identity against the active embedder.

    Returns one of: "unregistered", "match", "model_changed_same_dim",
    "dim_changed".
    """
    if not identity:
        return "unregistered"
    same_model = (
        str(identity.get("model")) == str(active_model)
        and str(identity.get("provider")) == str(active_provider)
    )
    if same_model:
        return "match"
    if active_dim is not None and int(identity.get("dim", -1)) == int(active_dim):
        return "model_changed_same_dim"
    return "dim_changed"
