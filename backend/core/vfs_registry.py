"""
VFS provider registry (W1, P2a).

Maps a path prefix (``knowledge``, ``github``, …) to its ``VFSProvider``.
The ``documents.*`` actions resolve a path's provider via this registry.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

from core.vfs_base import VFSProvider

logger = logging.getLogger(__name__)

_REGISTRY: Dict[str, VFSProvider] = {}


def register_provider(provider: VFSProvider) -> None:
    """Register a VFS provider under its ``prefix``."""
    if not provider.prefix:
        raise ValueError("VFSProvider must define a non-empty prefix")
    _REGISTRY[provider.prefix] = provider
    logger.info(f"[VFS] registered provider for prefix '{provider.prefix}'")


def get_provider(prefix: str) -> Optional[VFSProvider]:
    return _REGISTRY.get(prefix)


def resolve_provider(path: str) -> Optional[VFSProvider]:
    """Resolve a VFS path (e.g. 'knowledge/documents/<id>') to its provider."""
    if not path:
        return None
    cleaned = path.lstrip("/")
    prefix = cleaned.split("/", 1)[0]
    return _REGISTRY.get(prefix)


def list_prefixes() -> list:
    return sorted(_REGISTRY.keys())
