"""TDD bug-hunt: ContactGovernance session handling (R80 follow-up).

The whole class used ``db = self.db or get_db_session()`` — when no session is
injected (the global ``contact_governance = ContactGovernance()`` default),
``get_db_session()`` returns a ``_GeneratorContextManager``, so ``db.query``
crashed on every call and ``db.close()`` in the finally block crashed too.
Every external-contact governance check was dead code at runtime.
"""
from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.governance_engine import ContactGovernance


@pytest.fixture
def governance() -> ContactGovernance:
    return ContactGovernance()


def _patch_session(monkeypatch, session: MagicMock):
    @contextlib.contextmanager
    def _cm():
        yield session
        session.close()

    monkeypatch.setattr("core.governance_engine.get_db_session", _cm)
    return session


def _workspace_query(session: MagicMock, workspace) -> None:
    def _query(model):
        if model.__name__ == "Workspace":
            q = MagicMock()
            q.filter.return_value.first.return_value = workspace
            return q
        q = MagicMock()
        q.filter.return_value.first.return_value = None
        q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        return q

    session.query.side_effect = _query


def test_is_external_contact_no_injected_session_uses_context_manager(monkeypatch, governance):
    session = _patch_session(monkeypatch, MagicMock())
    _workspace_query(session, None)

    result = governance.is_external_contact("email", {"recipient_id": "x@evil.com"})

    assert result is True
    session.close.assert_called_once()


def test_is_external_contact_internal_domain_via_workspace(monkeypatch, governance):
    session = _patch_session(monkeypatch, MagicMock())
    workspace = MagicMock()
    workspace.metadata_json = {"internal_domains": ["atom.ai"]}
    _workspace_query(session, workspace)

    assert governance.is_external_contact("email", {"recipient_id": "x@atom.ai"}) is False


def test_injected_session_is_not_closed(governance):
    session = MagicMock()
    gov = ContactGovernance(db_session=session)

    gov.is_external_contact("email", {"recipient_id": "x@evil.com"})

    session.close.assert_not_called()


def test_should_require_approval_no_injected_session(monkeypatch, governance):
    session = _patch_session(monkeypatch, MagicMock())
    workspace = MagicMock()
    workspace.learning_phase_completed = True
    _workspace_query(session, workspace)

    assert asyncio.run(governance.should_require_approval("ws-1", "send_message", "slack", {})) is False
    session.close.assert_called()


def test_get_confidence_score_no_injected_session(monkeypatch, governance):
    session = _patch_session(monkeypatch, MagicMock())
    actions = []
    for _ in range(9):
        a = MagicMock()
        a.status = "approved"
        actions.append(a)
    a = MagicMock()
    a.status = "rejected"
    actions.append(a)

    def _query(model):
        q = MagicMock()
        q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = actions
        return q

    session.query.side_effect = _query

    assert governance.get_confidence_score("ws-1", "send_message", "slack") == pytest.approx(0.9)
    session.close.assert_called_once()


def test_request_approval_no_injected_session(monkeypatch, governance):
    session = _patch_session(monkeypatch, MagicMock())
    session.refresh.side_effect = lambda obj: setattr(obj, "id", "hitl-1")
    _workspace_query(session, None)

    result = governance.request_approval(
        "ws-1", "send_message", "slack", {"tenant_id": "t1"}, "Testing"
    )

    assert asyncio.run(result) == "hitl-1"
    session.add.assert_called_once()
    session.commit.assert_called_once()
    session.close.assert_called()


def test_request_approval_urgent_notifies(monkeypatch, governance):
    session = _patch_session(monkeypatch, MagicMock())
    session.refresh.side_effect = lambda obj: setattr(obj, "id", "hitl-2")
    _workspace_query(session, None)
    notify = AsyncMock()
    monkeypatch.setattr(governance, "_notify_governance_channel", notify)

    result = governance.request_approval(
        "ws-1", "delete_customer", "slack", {"tenant_id": "t1"}, "Destructive"
    )

    assert asyncio.run(result) == "hitl-2"
    notify.assert_awaited_once()
