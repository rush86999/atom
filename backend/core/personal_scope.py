"""Personal Edition scope resolution — single source of truth for tenant/workspace ids.

Personal Edition is **single-tenant**: there is exactly one Tenant (id="default")
and one Workspace (id="default"). We keep ``tenant_id`` and ``workspace_id`` as
**distinct concepts** (rather than collapsing to a single id) because the schema
syncs upstream with the multitenant SaaS repo where they ARE distinct. Models
inherit the dual-column shape from SaaS; collapsing here would create sync
divergence and silently break any SaaS tooling that assumes the dual shape.

The trade-off is: in Personal Edition the two ids are always equal. Callers must
still pick the RIGHT one per model:

  - ``AgentExecution``, ``AgentRegistry``, ``ChatSession`` → key on ``workspace_id``
  - ``CanvasAudit``, ``Notification``                         → carry BOTH (FK constraints)

Use ``resolve_workspace_id(*sources)`` / ``resolve_tenant_id(*sources)`` instead
of hardcoding ``"default"``. Each resolver walks the supplied source objects
(user, agent, session, …) in order and returns the first non-empty value,
falling back to the Personal-Edition default.

Why the fallback is load-bearing: the admin user created by ``admin_bootstrap``
has ``tenant_id=None`` and ``workspace_id=None`` (both columns are nullable and
bootstrap doesn't set them). So ``current_user.tenant_id`` cannot be trusted
alone — the resolver's fallback to ``PERSONAL_TENANT_ID`` is what makes the
admin user's notifications and dashboard data resolve correctly.
"""
from typing import Any

# Single source of truth. If Personal Edition ever moves off "default"
# (e.g. a "personal" tenant id), change it here and every caller updates.
PERSONAL_TENANT_ID = "default"
PERSONAL_WORKSPACE_ID = "default"


def resolve_workspace_id(*sources: Any) -> str:
    """Return the first non-empty ``workspace_id`` from the given sources.

    Sources are inspected in order; typical call sites pass (user, agent) or
    just (user,). Falls back to ``PERSONAL_WORKSPACE_ID`` when none supply one.
    """
    for src in sources:
        if src is None:
            continue
        ws = getattr(src, "workspace_id", None)
        if ws:
            return str(ws)
    return PERSONAL_WORKSPACE_ID


def resolve_tenant_id(*sources: Any) -> str:
    """Return the first non-empty ``tenant_id`` from the given sources.

    Same pattern as ``resolve_workspace_id``. Note that the admin user has
    ``tenant_id=None`` — the fallback to ``PERSONAL_TENANT_ID`` is intentional.
    """
    for src in sources:
        if src is None:
            continue
        tid = getattr(src, "tenant_id", None)
        if tid:
            return str(tid)
    return PERSONAL_TENANT_ID
