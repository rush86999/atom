"""radio_adapter tests — breakpoint-gated fleet thread attachment.

Covers the thin adapter that _recruit_fleet calls:
  - radio disabled => no thread (fleet behavior unchanged),
  - bounded/local task => no thread (single-agent is the default),
  - breakpoint task => exactly one chain-scoped thread, members stamped,
  - execution_id, when given, is stamped with thread_id for run attribution.
"""

from __future__ import annotations

import pytest

from core.agent_radio import radio_adapter, radio_config
from core.agent_radio.radio_adapter import attach_thread_for_chain, execution_thread_id
from core.models import AgentExecution, AgentThread, ChainLink, DelegationChain


@pytest.fixture
def chain(db_session):
    """A minimal delegation chain to scope a thread to."""
    c = DelegationChain(
        id="chain-test-1",
        tenant_id="default",
        root_agent_id="atom_main",
        root_task="cross-service incident root-cause",
        status="active",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def execution(db_session, chain):
    ex = AgentExecution(agent_id="atom_main", chain_id=chain.id, status="running")
    db_session.add(ex)
    db_session.commit()
    db_session.refresh(ex)
    return ex


class TestAttachBreakpointGated:
    def test_bounded_task_no_thread(self, db_session, chain):
        thread = attach_thread_for_chain(
            db_session,
            chain_id=chain.id,
            task_description="fix a typo in one file",
            team_agent_ids=["agent_b", "agent_c"],
        )
        assert thread is None
        assert db_session.query(AgentThread).count() == 0

    def test_breakpoint_task_attaches_thread(self, db_session, chain):
        thread = attach_thread_for_chain(
            db_session,
            chain_id=chain.id,
            task_description="cross-service migration of the billing integration",
            team_agent_ids=["agent_b", "agent_c"],
            created_by_agent_id="atom_main",
            tenant_id=None,
        )
        assert thread is not None
        assert thread.chain_id == chain.id
        assert set(thread.member_agent_ids) >= {"atom_main", "agent_b", "agent_c"}
        assert thread.metadata_json.get("scope") == "fleet"

    def test_disabled_radio_no_thread(self, db_session, chain, monkeypatch):
        monkeypatch.setattr("core.agent_radio.radio_config.radio_enabled", lambda: False)
        thread = attach_thread_for_chain(
            db_session,
            chain_id=chain.id,
            task_description="cross-service incident root-cause refactor",
            team_agent_ids=["agent_b"],
        )
        assert thread is None

    def test_execution_thread_id_stamped(self, db_session, chain, execution):
        thread = attach_thread_for_chain(
            db_session,
            chain_id=chain.id,
            task_description="legacy refactor and security audit across modules",
            team_agent_ids=["agent_b"],
            execution_id=execution.id,
            tenant_id=None,
        )
        assert thread is not None
        db_session.refresh(execution)
        assert execution.thread_id == thread.id

    def test_execution_thread_id_lookup(self, db_session, chain, execution, monkeypatch):
        from contextlib import contextmanager

        # The lookup helper opens its own session; point it at the test session.
        @contextmanager
        def _cm():
            yield db_session

        monkeypatch.setattr("core.database.get_db_session", _cm)

        attach_thread_for_chain(
            db_session,
            chain_id=chain.id,
            task_description="legacy refactor and security audit across modules",
            team_agent_ids=["agent_b"],
            execution_id=execution.id,
            tenant_id=None,
        )
        assert execution_thread_id(execution.id) is not None
        assert execution_thread_id("nonexistent-exec") is None
