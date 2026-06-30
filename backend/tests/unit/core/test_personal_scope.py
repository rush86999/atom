"""
Regression tests for core/personal_scope.py — the single source of truth for
Personal Edition tenant_id / workspace_id resolution.

Covers:
- Constants are "default" (Personal Edition is single-tenant).
- Resolvers return the first non-empty source value.
- Resolvers fall back to PERSONAL_*_ID when sources are missing/None/empty
  (this is load-bearing for the admin user, whose tenant_id/workspace_id
  columns are nullable and never set by bootstrap).
- Resolvers skip None sources in the variadic list.
"""
from types import SimpleNamespace

from core.personal_scope import (
    PERSONAL_TENANT_ID,
    PERSONAL_WORKSPACE_ID,
    resolve_tenant_id,
    resolve_workspace_id,
)


def test_constants_are_default():
    """Personal Edition is single-tenant; both ids are 'default'."""
    assert PERSONAL_TENANT_ID == "default"
    assert PERSONAL_WORKSPACE_ID == "default"


def test_resolve_workspace_id_returns_user_value_when_set():
    user = SimpleNamespace(workspace_id="ws-42", tenant_id="t-1")
    assert resolve_workspace_id(user) == "ws-42"


def test_resolve_tenant_id_returns_user_value_when_set():
    user = SimpleNamespace(workspace_id="ws-42", tenant_id="t-1")
    assert resolve_tenant_id(user) == "t-1"


def test_resolve_falls_back_to_default_when_user_attr_is_none():
    """The admin user has tenant_id=None and workspace_id=None (nullable cols).
    The fallback to PERSONAL_*_ID must kick in so the admin's notifications
    and dashboard data resolve to the default scope."""
    admin = SimpleNamespace(workspace_id=None, tenant_id=None)
    assert resolve_workspace_id(admin) == PERSONAL_WORKSPACE_ID
    assert resolve_tenant_id(admin) == PERSONAL_TENANT_ID


def test_resolve_falls_back_when_no_sources_supplied():
    assert resolve_workspace_id() == PERSONAL_WORKSPACE_ID
    assert resolve_tenant_id() == PERSONAL_TENANT_ID


def test_resolve_skips_none_sources():
    """Variadic call with None placeholders must not raise."""
    assert resolve_workspace_id(None, None, None) == PERSONAL_WORKSPACE_ID
    assert resolve_tenant_id(None, None) == PERSONAL_TENANT_ID


def test_resolve_walks_multiple_sources_first_wins():
    """When user and agent are both supplied, the user (first) wins."""
    user = SimpleNamespace(workspace_id="ws-user", tenant_id="t-user")
    agent = SimpleNamespace(workspace_id="ws-agent", tenant_id="t-agent")
    assert resolve_workspace_id(user, agent) == "ws-user"
    assert resolve_tenant_id(user, agent) == "t-user"


def test_resolve_falls_through_to_next_source_when_first_is_empty():
    """If the first source has no value, the next source is consulted."""
    user = SimpleNamespace(workspace_id=None, tenant_id=None)
    agent = SimpleNamespace(workspace_id="ws-agent", tenant_id="t-agent")
    assert resolve_workspace_id(user, agent) == "ws-agent"
    assert resolve_tenant_id(user, agent) == "t-agent"


def test_resolve_handles_object_without_attr():
    """Objects without the attribute must not break resolution."""
    bare = SimpleNamespace(other=123)
    assert resolve_workspace_id(bare) == PERSONAL_WORKSPACE_ID
    assert resolve_tenant_id(bare) == PERSONAL_TENANT_ID
