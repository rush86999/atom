#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Red-team the BYOK credential-resolution boundary (review item 1).

Reproduces, without touching the live store, the defect the in-flight
``_find_stored_key`` introduced and shows the containment the corrected
contract provides.

The store has TWO writers with different id shapes::

    store_api_key          → {provider}_{name}_{env}                 (global)
    store_tenant_api_key   → tenant_{tenant}_{provider}_{name}_{env} (scoped)

The in-flight resolver matched candidates on ``(provider, key_name,
environment)`` only and returned the FIRST hit, so the entry's owning tenant
was never consulted. Consequences, both reproduced below:

* **two-tenant collision** — tenant B receives tenant A's credential;
* **scoped → global promotion** — an unscoped operator lookup receives some
  tenant's credential, purely on dict insertion order.

Run::

    cd backend && ./venv/bin/python scripts/redteam_byok_scope_resolution.py

Exit code is non-zero if any attack SUCCEEDS against the current
implementation (i.e. the containment checks fail).
"""
from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography.fernet import Fernet  # noqa: E402


def _fresh_manager(tmpdir: str):
    """A BYOKManager whose store lives entirely in ``tmpdir``."""
    os.environ["BYOK_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    import core.byok_endpoints as be

    be.BYOK_KEYS_FILE = os.path.join(tmpdir, "byok_keys.json")
    be.BYOK_CONFIG_FILE = os.path.join(tmpdir, "byok_config.json")
    be._byok_manager = None
    return be, be.BYOKManager()


def _seed(be, manager, provider: str, secret: str, tenant: Optional[str]) -> str:
    from datetime import datetime as _dt

    if tenant is None:
        key_id = f"{provider}_default_production"
    else:
        key_id = f"tenant_{tenant}_{provider}_default_production"
    manager.api_keys[key_id] = be.APIKey(
        provider_id=provider,
        key_name="default",
        encrypted_key=manager.encrypt_api_key(secret),
        key_hash="h",
        created_at=_dt.now(),
        environment="production",
    )
    return key_id


@dataclass
class Attack:
    name: str
    #: what the in-flight (pre-correction) resolver returned
    legacy_result: Optional[str]
    #: what the corrected contract must return
    expected: Optional[str]
    actual: Optional[str]

    @property
    def contained(self) -> bool:
        return self.actual == self.expected


def _legacy_find_stored_key(manager, provider_id, key_name, environment, tenant_id=None):
    """The in-flight implementation: first field match wins, tenant ignored."""
    exact = manager.api_keys.get(f"{provider_id}_{key_name}_{environment}")
    if exact is not None:
        return exact
    for _key_id, obj in manager.api_keys.items():
        if (
            str(getattr(obj, "provider_id", "")) == provider_id
            and str(getattr(obj, "key_name", "")) == key_name
            and str(getattr(obj, "environment", "")) == environment
        ):
            return obj
    return None


def _legacy_value(manager, provider_id, **kw):
    obj = _legacy_find_stored_key(
        manager, provider_id, kw.get("key_name", "default"),
        kw.get("environment", "production"))
    if obj is None:
        return None
    try:
        return manager.decrypt_api_key(obj.encrypted_key)
    except Exception:
        return None


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        be, manager = _fresh_manager(tmp)
        # Insertion order: acme FIRST (this is what made the in-flight version
        # hand acme's key to globex).
        _seed(be, manager, "deepseek", "sk-acme", tenant="acme")
        _seed(be, manager, "deepseek", "sk-globex", tenant="globex")

        attacks = [
            Attack(
                name="tenant globex lookup must not receive acme's key",
                legacy_result=_legacy_value(manager, "deepseek", tenant_id="globex"),
                expected="sk-globex",
                actual=manager.get_api_key("deepseek", tenant_id="globex"),
            ),
            Attack(
                name="tenant acme lookup keeps its own key",
                legacy_result=_legacy_value(manager, "deepseek", tenant_id="acme"),
                expected="sk-acme",
                actual=manager.get_api_key("deepseek", tenant_id="acme"),
            ),
            Attack(
                name="unscoped lookup must not promote a scoped credential",
                legacy_result=_legacy_value(manager, "deepseek"),
                expected=None,
                actual=manager.get_api_key("deepseek"),
            ),
            Attack(
                name="unknown tenant must not receive anyone's key",
                legacy_result=_legacy_value(manager, "deepseek", tenant_id="initech"),
                expected=None,
                actual=manager.get_api_key("deepseek", tenant_id="initech"),
            ),
        ]

        # Reversed insertion order: the legacy defect must not be order-bound
        # either way, and the corrected contract must be order-independent.
        with tempfile.TemporaryDirectory() as tmp2:
            be2, m2 = _fresh_manager(tmp2)
            _seed(be2, m2, "deepseek", "sk-globex", tenant="globex")
            _seed(be2, m2, "deepseek", "sk-acme", tenant="acme")
            attacks.append(Attack(
                name="reversed insertion order: acme still gets acme",
                legacy_result=_legacy_value(m2, "deepseek", tenant_id="acme"),
                expected="sk-acme",
                actual=m2.get_api_key("deepseek", tenant_id="acme"),
            ))
            attacks.append(Attack(
                name="reversed insertion order: unscoped still refuses",
                legacy_result=_legacy_value(m2, "deepseek"),
                expected=None,
                actual=m2.get_api_key("deepseek"),
            ))

        # Global vs scoped: the operator's own entry is the intended fallback,
        # and only the operator's.
        with tempfile.TemporaryDirectory() as tmp3:
            be3, m3 = _fresh_manager(tmp3)
            _seed(be3, m3, "deepseek", "sk-acme", tenant="acme")
            _seed(be3, m3, "deepseek", "sk-operator", tenant=None)
            attacks.append(Attack(
                name="unscoped lookup prefers the operator's global entry",
                legacy_result=_legacy_value(m3, "deepseek"),
                expected="sk-operator",
                actual=m3.get_api_key("deepseek"),
            ))
            attacks.append(Attack(
                name="tenant acme still prefers its own over global",
                legacy_result=_legacy_value(m3, "deepseek", tenant_id="acme"),
                expected="sk-acme",
                actual=m3.get_api_key("deepseek", tenant_id="acme"),
            ))
            attacks.append(Attack(
                name="unowned tenant falls back to global, not to acme",
                legacy_result=_legacy_value(m3, "deepseek", tenant_id="globex"),
                expected="sk-operator",
                actual=m3.get_api_key("deepseek", tenant_id="globex"),
            ))

        failures = 0
        print("BYOK credential-resolution red team")
        print("=" * 72)
        for attack in attacks:
            status = "CONTAINED" if attack.contained else "*** ESCAPED ***"
            if not attack.contained:
                failures += 1
            print(f"[{status}] {attack.name}")
            print(f"    in-flight resolver returned: {attack.legacy_result!r}")
            print(f"    corrected contract  returns: {attack.actual!r} "
                  f"(expected {attack.expected!r})")
        print("=" * 72)
        escaped = [a.name for a in attacks if not a.contained]
        promoted = [a.name for a in attacks if a.legacy_result not in (None,)
                    and a.legacy_result != a.expected]
        print(f"{len(attacks) - failures}/{len(attacks)} contained")
        print(f"{len(promoted)} case(s) where the in-flight resolver returned a "
              f"credential the corrected contract refuses or reassigns")
        return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
