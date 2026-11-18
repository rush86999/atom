"""Personal Edition scope resolution — single source of truth for tenant/workspace ids.

Personal Edition is **single-tenant**. Its bootstrap uses Tenant and Workspace
rows both named "default", while existing ordinary-registration records can
carry distinct opaque ids. We keep ``tenant_id`` and ``workspace_id`` as
**distinct concepts** (rather than collapsing to a single id) because the schema
syncs upstream with the multitenant SaaS repo where they ARE distinct. Models
inherit the dual-column shape from SaaS; collapsing here would create sync
divergence and silently break any SaaS tooling that assumes the dual shape.

Single-tenant deployment does not make those two keys interchangeable.
Callers must still pick the RIGHT one per model:

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

#: The server-owned bootstrap account created by ``admin_bootstrap``.
#: Only this identity may use the Personal-workspace fallback below when it
#: has no explicit binding; the server itself created it with NULL scope.
BOOTSTRAP_ADMIN_EMAIL = "admin@example.com"


class DocumentScopeUnavailable(Exception):
    """An authenticated principal has no eligible document workspace."""


class DocumentScopeResolutionError(Exception):
    """Workspace binding lookup failed; the caller must fail closed."""


def is_bootstrap_identity(user: Any) -> bool:
    """True only for the server-owned bootstrap account.

    Identity is proven from the persisted ``User`` row behind the
    authenticated principal — never from a request-supplied value. An email
    match alone is not proof (a profile/registration path can set it), so all
    of the following must hold:

      1. a non-empty principal id — anonymous, transient or unpersisted
         objects are refused;
      2. the exact bootstrap email;
      3. a ``workspace_admin``-or-higher role, checked through the same RBAC
         hierarchy ``admin_bootstrap`` uses, so a downgraded account stops
         being the bootstrap identity;
      4. raw NULL ``tenant_id`` and ``workspace_id``, matching what
         ``admin_bootstrap`` creates for this account. An account with an
         explicit binding is not the bootstrap identity — its own binding
         governs, and a non-NULL tenant is never a fallback grant.

    Any other account with NULL workspace scope has not been provisioned and
    must not be given a personal namespace.
    """
    if user is None:
        return False
    principal_id = str(getattr(user, "id", "") or "").strip()
    if not principal_id:
        return False
    email = str(getattr(user, "email", "") or "").strip().lower()
    if not email or email != BOOTSTRAP_ADMIN_EMAIL:
        return False
    # Raw NULL scope, exactly as ``admin_bootstrap`` leaves it. Empty strings
    # are not NULL: a value was written, so this is not the initialized row.
    if getattr(user, "tenant_id", None) is not None:
        return False
    if getattr(user, "workspace_id", None) is not None:
        return False
    # Local imports keep this low-level module free of auth-layer imports at
    # module load time (mirrors ``admin_bootstrap``'s own deferred RBAC use).
    from core.models import UserRole
    from core.security.rbac import user_meets_role

    return user_meets_role(user, UserRole.WORKSPACE_ADMIN)


def resolve_document_workspace_id(user: Any) -> Any:
    """Authoritative document scope for an authenticated principal.

    Order preserves the existing J3 contract: non-empty ``workspace_id`` FK
    first, legacy ``workspaces`` relationship second. Only the server-owned
    bootstrap identity — documented as intentionally created with NULL scope —
    may fall back to ``PERSONAL_WORKSPACE_ID``. Every other unbound account
    and every lookup failure raises, so callers fail closed instead of
    landing in the legacy shared ``default_shared`` store.
    """
    if user is None:
        return None
    fk = getattr(user, "workspace_id", None)
    if fk:
        return str(fk)
    try:
        rel = getattr(user, "workspaces", None)
        if rel:
            return str(rel[0].id)
    except Exception as exc:  # noqa: BLE001 — unreadable binding is not proof
        raise DocumentScopeResolutionError(
            "workspace binding lookup failed") from exc
    if is_bootstrap_identity(user):
        return PERSONAL_WORKSPACE_ID
    raise DocumentScopeUnavailable(
        "this account has no document workspace binding")


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
