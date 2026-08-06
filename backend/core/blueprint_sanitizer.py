"""
Blueprint Sanitizer — P5 Blueprint Security.

Sharing/forking never leaks credentials. This module provides a recursive
denylist-based credential stripper used by every "share" surface:

* Workflow template EXPORT  (``core/workflow_template_system.py``)
* Agent marketplace PUBLISH (``core/agent_marketplace_service.py``)
* Canvas FORK component configs (``api/canvas_routes.py``)

The denylist regex mirrors the key shapes redacted by the credential vault so
behaviour stays consistent across all sharing paths. ``strip_credentials``
always returns a deep copy and never mutates the input.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

# Denylist of credential-bearing dict keys, case-insensitive. Matches the key
# shapes the credential vault redacts (api_key, access/refresh token, secret,
# password) plus the common token/key variants (auth_token, apikey,
# x-api-key, private_key, bearer_token, Authorization) so export/publish/fork
# behaves consistently and does not leak credentials under renamed keys.
_CREDENTIAL_KEY_RE = re.compile(
    r"(api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|"
    r"bot[_-]?token|bearer[_-]?token|token|private[_-]?key|secret|password|authorization)",
    re.IGNORECASE,
)


def _is_credential_key(key: str) -> bool:
    """Return True if ``key`` matches the credential denylist."""
    return bool(_CREDENTIAL_KEY_RE.search(key))


def strip_credentials(obj: Any) -> Any:
    """Recursively remove credential-shaped keys from ``obj``.

    Dict keys whose name matches the denylist regex ``(api_key|access_token|
    refresh_token|secret|password)`` (case-insensitive) are dropped anywhere in
    the nested dict/list structure. Returns a deep copy; the input is never
    mutated. Scalars and lists pass through (their members are still recursed).

    Args:
        obj: Arbitrary JSON-ish structure (dict, list, scalar, None).

    Returns:
        A deep copy of ``obj`` with credential keys removed.
    """
    if isinstance(obj, dict):
        cleaned: dict[str, Any] = {}
        for key, value in obj.items():
            if _is_credential_key(str(key)):
                continue
            cleaned[key] = strip_credentials(value)
        return cleaned
    if isinstance(obj, list):
        return [strip_credentials(item) for item in obj]
    return deepcopy(obj)


def has_credentials(obj: Any) -> bool:
    """Return True if ``obj`` (recursively) contains a credential-shaped key.

    Useful for pre-share checks / audit decisions.

    Args:
        obj: Arbitrary JSON-ish structure.

    Returns:
        True if any nested dict key matches the credential denylist.
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            if _is_credential_key(str(key)):
                return True
            if has_credentials(value):
                return True
        return False
    if isinstance(obj, list):
        return any(has_credentials(item) for item in obj)
    return False
