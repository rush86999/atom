"""Pluggable storage layer for mini-app assets (host-mediated).

The guest microVM has no host filesystem — ALL file/blob I/O from app logic
flows through host-mediated ``storage_ops`` envelopes executed by the host
against a ``MiniAppStorage`` backend. Two backends:

  * ``LocalFileSystemBackend`` — the Personal-edition default. Root
    ``MINIAPP_STORAGE_LOCAL_ROOT`` (default ``./data/mini_apps``); the facade's
    per-instance namespace maps a logical key to
    ``<root>/<tenant_id>/<canvas_id>/<key>``. Enforces path containment
    (rejects ``..``, absolute, and empty keys) — R53 office path-traversal
    precedent.
  * ``S3StorageBackend`` — wraps ``StorageService`` (S3/R2). Keys live under
    ``mini-apps/`` (the facade adds ``{tenant_id}/{canvas_id}/``); URIs are
    ``s3://bucket/mini-apps/{tenant_id}/{canvas_id}/<key>``.

``MiniAppStorage`` is the facade; ``get_mini_app_storage()`` selects the
backend via the ``MINIAPP_STORAGE_CLOUD_ENABLED`` gate (default: local). When
cloud is enabled but no bucket is configured, it falls back to local (the
LanceDB cloud→local downgrade precedent).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, List, Optional, Protocol

logger = logging.getLogger(__name__)

MINIAPP_STORAGE_CLOUD_ENABLED = "MINIAPP_STORAGE_CLOUD_ENABLED"
MINIAPP_STORAGE_LOCAL_ROOT = "MINIAPP_STORAGE_LOCAL_ROOT"
DEFAULT_LOCAL_ROOT = os.path.join("data", "mini_apps")
MINIAPP_STORAGE_MAX_OBJECT_BYTES = "MINIAPP_STORAGE_MAX_OBJECT_BYTES"
DEFAULT_MAX_OBJECT_BYTES = 50 * 1024 * 1024  # 50 MiB


class StorageBackend(Protocol):
    """Storage backend contract used by MiniAppStorage."""

    def store(self, key: str, data: bytes, content_type: Optional[str] = None) -> str: ...
    def retrieve(self, key: str) -> Optional[bytes]: ...
    def delete(self, key: str) -> bool: ...
    def exists(self, key: str) -> bool: ...
    def list_keys(self, prefix: str = "") -> List[str]: ...


# ---------------------------------------------------------------------------
# Key validation
# ---------------------------------------------------------------------------
def validate_key(key: str) -> str:
    """Validate a logical asset key (path-traversal guard).

    Rejects empty keys, absolute paths, backslashes, URL-encoded path
    separators (``%2f`` / ``%5c``), and any ``..`` traversal. Returns the
    sanitized relative key (normalized). Raises ``ValueError`` otherwise.
    """
    if not key or not isinstance(key, str):
        raise ValueError("asset key is required")
    if key.startswith("/") or "\\" in key:
        raise ValueError("asset key must be a relative path")
    # Reject URL-encoded separators that could bypass the segment checks below
    # after a downstream urldecode (e.g. "..%2fevil" → "../evil").
    lowered = key.lower()
    if "%2f" in lowered or "%5c" in lowered:
        raise ValueError("asset key must not contain encoded path separators")
    parts = key.split("/")
    if any(p in ("", "..", ".") for p in parts):
        raise ValueError("asset key must not contain empty, '.' or '..' segments")
    return key


class LocalFileSystemBackend:
    """Local-FS storage backend. Root is scoped per tenant/canvas."""

    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()

    def _resolve(self, key: str) -> Path:
        key = validate_key(key)
        resolved = (self.root / key).resolve()
        # Containment check: the resolved path must stay under root.
        if self.root not in resolved.parents and resolved != self.root:
            raise ValueError(
                f"Access denied: key '{key}' escapes the storage root"
            )
        return resolved

    def store(self, key: str, data: bytes, content_type: Optional[str] = None) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def retrieve(self, key: str) -> Optional[bytes]:
        path = self._resolve(key)
        if not path.exists():
            return None
        return path.read_bytes()

    def delete(self, key: str) -> bool:
        path = self._resolve(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    def list_keys(self, prefix: str = "") -> List[str]:
        base = self.root
        if prefix:
            base = self._resolve(prefix)
        out = []
        for p in sorted(base.rglob("*")):
            if p.is_file():
                out.append(str(p.relative_to(self.root)))
        return out


class S3StorageBackend:
    """S3/R2 storage backend wrapping ``StorageService``."""

    def __init__(self, storage_service: Any, prefix: str = "") -> None:
        self._svc = storage_service
        self._prefix = prefix.rstrip("/")

    def _key(self, key: str) -> str:
        validate_key(key)
        return f"{self._prefix}/{key}" if self._prefix else key

    def store(self, key: str, data: bytes, content_type: Optional[str] = None) -> str:
        from io import BytesIO

        k = self._key(key)
        uri = self._svc.upload_file(BytesIO(data), k, content_type=content_type)
        return uri

    def retrieve(self, key: str) -> Optional[bytes]:
        try:
            return self._svc.download_file(self._key(key))
        except Exception as e:  # noqa: BLE001
            logger.debug("S3 retrieve %s failed: %s", key, e)
            return None

    def delete(self, key: str) -> bool:
        return self._svc.delete_object(self._key(key))

    def exists(self, key: str) -> bool:
        return self._svc.check_exists(self._key(key))

    def list_keys(self, prefix: str = "") -> List[str]:
        pfx = self._key(prefix) if prefix else (self._prefix + "/")
        keys = self._svc.list_keys(prefix=pfx)
        strip = self._prefix + "/"
        return [k[len(strip):] for k in keys if k.startswith(strip)]


class MiniAppStorage:
    """Facade over a backend with a per-instance namespace."""

    def __init__(self, backend: StorageBackend, tenant_id: str, canvas_id: str) -> None:
        self.backend = backend
        self.tenant_id = tenant_id
        self.canvas_id = canvas_id

    @property
    def namespace(self) -> str:
        return f"{self.tenant_id}/{self.canvas_id}"

    def _ns_key(self, key: str) -> str:
        validate_key(key)
        return f"{self.namespace}/{key}"

    def store(self, key: str, data: bytes, content_type: Optional[str] = None) -> str:
        return self.backend.store(self._ns_key(key), data, content_type=content_type)

    def retrieve(self, key: str) -> Optional[bytes]:
        return self.backend.retrieve(self._ns_key(key))

    def delete(self, key: str) -> bool:
        return self.backend.delete(self._ns_key(key))

    def exists(self, key: str) -> bool:
        return self.backend.exists(self._ns_key(key))

    def list_keys(self, prefix: str = "") -> List[str]:
        keys = self.backend.list_keys(prefix=f"{self.namespace}/{prefix}".rstrip("/"))
        strip = f"{self.namespace}/"
        return [k[len(strip):] for k in keys if k.startswith(strip)]


def get_max_object_bytes() -> int:
    try:
        return max(1, int(os.getenv(MINIAPP_STORAGE_MAX_OBJECT_BYTES, str(DEFAULT_MAX_OBJECT_BYTES))))
    except (TypeError, ValueError):
        return DEFAULT_MAX_OBJECT_BYTES


def cloud_enabled() -> bool:
    return os.getenv(MINIAPP_STORAGE_CLOUD_ENABLED, "false").strip().lower() in {"1", "true", "yes", "on"}


def _has_bucket() -> bool:
    return bool(os.getenv("AWS_S3_BUCKET") or os.getenv("AWS_S3_BUCKET_NAME"))


def _make_local(tenant_id: str, canvas_id: str) -> MiniAppStorage:
    # The backend root is the base dir; the facade's per-instance namespace
    # adds <tenant_id>/<canvas_id>/ on top (no double-namespacing).
    root = os.getenv(MINIAPP_STORAGE_LOCAL_ROOT, DEFAULT_LOCAL_ROOT)
    return MiniAppStorage(LocalFileSystemBackend(root), tenant_id, canvas_id)


def get_mini_app_storage(tenant_id: str, canvas_id: str) -> MiniAppStorage:
    """Return a storage facade for an instance canvas.

    ``MINIAPP_STORAGE_CLOUD_ENABLED=true`` → S3/R2 backend (falls back to local
    when no bucket is configured — LanceDB cloud→local downgrade precedent).
    Default: local FS.
    """
    if cloud_enabled() and _has_bucket():
        try:
            from core.storage import get_storage_service

            svc = get_storage_service()
            if svc.s3 is not None:
                # The facade's namespace adds {tenant}/{canvas} under this
                # prefix (single-namespacing via the facade, not here).
                return MiniAppStorage(S3StorageBackend(svc, "mini-apps"), tenant_id, canvas_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("MiniAppStorage cloud backend unavailable, falling back to local: %s", e)
    return _make_local(tenant_id, canvas_id)
