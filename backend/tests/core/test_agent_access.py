"""Direct regression for the shared AgentRegistry visibility rule.

``core.agent_access.agent_reader_condition`` is the one predicate the agent
reader (``GET /api/agents``) and the audit-linked correction writer share.
These cases pin every scope bucket explicitly: legacy shared rows stay
visible, the actor's exact workspace stays visible, and a foreign
workspace/tenant never is.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.agent_access import agent_reader_condition, scoped_agent_for_scope
from core.models import AgentRegistry


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    AgentRegistry.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([
        AgentRegistry(
            id="shared-null", name="Shared Null", category="Finance",
            module_path="a.null", class_name="Null",
            workspace_id=None, tenant_id=None,
        ),
        AgentRegistry(
            id="shared-empty", name="Shared Empty", category="Finance",
            module_path="a.empty", class_name="Empty",
            workspace_id="", tenant_id="",
        ),
        AgentRegistry(
            id="shared-default", name="Shared Default", category="Finance",
            module_path="a.default", class_name="Default",
            workspace_id="default", tenant_id="default",
        ),
        AgentRegistry(
            id="own-workspace", name="Own", category="Finance",
            module_path="a.own", class_name="Own",
            workspace_id="ws-1", tenant_id="t-1",
        ),
        AgentRegistry(
            id="foreign-workspace", name="Foreign WS", category="Finance",
            module_path="a.fws", class_name="ForeignWs",
            workspace_id="ws-2", tenant_id="t-1",
        ),
        AgentRegistry(
            id="foreign-tenant", name="Foreign Tenant", category="Finance",
            module_path="a.ft", class_name="ForeignT",
            workspace_id="ws-1", tenant_id="t-2",
        ),
        AgentRegistry(
            id="foreign-both", name="Foreign Both", category="Finance",
            module_path="a.fb", class_name="ForeignB",
            workspace_id="ws-2", tenant_id="t-2",
        ),
    ])
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


REAL_SCOPE = {"workspace_id": "ws-1", "tenant_id": "t-1", "personal": False}
PERSONAL_SCOPE = {
    "workspace_id": "default", "tenant_id": "default", "personal": True,
}


def _visible(db, scope):
    return {
        row.id
        for row in db.query(AgentRegistry)
        .filter(agent_reader_condition(scope))
        .all()
    }


def test_real_workspace_scope_sees_shared_and_own_only(db):
    assert _visible(db, REAL_SCOPE) == {
        "shared-null", "shared-empty", "shared-default", "own-workspace",
    }


def test_personal_scope_keeps_default_compatibility(db):
    assert _visible(db, PERSONAL_SCOPE) == {
        "shared-null", "shared-empty", "shared-default",
    }


def test_foreign_workspace_tenant_and_both_are_never_visible(db):
    assert "foreign-workspace" not in _visible(db, REAL_SCOPE)
    assert "foreign-tenant" not in _visible(db, REAL_SCOPE)
    assert "foreign-both" not in _visible(db, REAL_SCOPE)
    assert "foreign-workspace" not in _visible(db, PERSONAL_SCOPE)
    assert "foreign-tenant" not in _visible(db, PERSONAL_SCOPE)


def test_exact_lookup_matches_predicate(db):
    for agent_id in ("shared-null", "shared-empty", "shared-default",
                     "own-workspace"):
        assert scoped_agent_for_scope(db, REAL_SCOPE, agent_id) is not None
    for agent_id in ("foreign-workspace", "foreign-tenant", "foreign-both",
                     "does-not-exist"):
        assert scoped_agent_for_scope(db, REAL_SCOPE, agent_id) is None
