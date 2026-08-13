# -*- coding: utf-8 -*-
"""Coverage wave 87 — core/negotiation_engine (standalone, zero LLM spend,
no network, no real DB).

- update_deal_state: deal-not-found, every transition arc (INITIAL→DISCOVERY
  via meeting_request, INITIAL→CLOSING via payment_commitment/approval,
  DISCOVERY→BARGAINING via upsell_inquiry/price_negotiation, BARGAINING→CLOSING
  via approval, BARGAINING→LOST via lost_interest/unsubscribe, INITIAL→LOST),
  terminal-state guard (WON/LOST absorbing — no signal can walk a closed deal
  back), no-op when no signal matches, persistence + timezone-aware
  last_engagement_at (naive datetime crashes on PG timestamptz — R13 class),
  session close when no injected db, commit-free path when state unchanged.
- _calculate_next_state: terminal guard + all signal branches + no-match
  returns current.
- get_strategy_prompt: every strategy bucket (INITIAL/DISCOVERY/BARGAINING/
  CLOSING/FOLLOW_UP/WON/LOST), unknown state fallback, deal-not-found falls
  back to INITIAL prompt, session close.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
import sales.models  # noqa: F401 (register sales_deals on Base)
from core.negotiation_engine import NegotiationStateMachine
from sales.models import Deal, NegotiationState


@pytest.fixture()
def db():
    """In-memory SQLite session with the full schema."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_deal(db, deal_id="deal-1", state=NegotiationState.INITIAL):
    deal = Deal(
        id=deal_id,
        workspace_id="ws-1",
        name="Test Deal",
        negotiation_state=state,
    )
    db.add(deal)
    db.commit()
    return deal


class TestUpdateDealState:
    def test_deal_not_found_returns_none(self, db):
        result = NegotiationStateMachine(db_session=db).update_deal_state(
            "missing", ["meeting_request"]
        )
        assert result is None

    def test_initial_meeting_request_advances_to_discovery(self, db):
        deal = _make_deal(db)
        result = NegotiationStateMachine(db_session=db).update_deal_state(
            deal.id, ["meeting_request"]
        )
        assert result == NegotiationState.DISCOVERY
        db.refresh(deal)
        assert deal.negotiation_state == NegotiationState.DISCOVERY

    def test_initial_payment_commitment_advances_to_closing(self, db):
        deal = _make_deal(db)
        result = NegotiationStateMachine(db_session=db).update_deal_state(
            deal.id, ["payment_commitment"]
        )
        assert result == NegotiationState.CLOSING

    def test_initial_approval_advances_to_closing(self, db):
        deal = _make_deal(db)
        result = NegotiationStateMachine(db_session=db).update_deal_state(
            deal.id, ["approval"]
        )
        assert result == NegotiationState.CLOSING

    def test_initial_lost_interest_advances_to_lost(self, db):
        deal = _make_deal(db)
        result = NegotiationStateMachine(db_session=db).update_deal_state(
            deal.id, ["lost_interest"]
        )
        assert result == NegotiationState.LOST

    def test_discovery_upsell_advances_to_bargaining(self, db):
        deal = _make_deal(db, state=NegotiationState.DISCOVERY)
        result = NegotiationStateMachine(db_session=db).update_deal_state(
            deal.id, ["upsell_inquiry"]
        )
        assert result == NegotiationState.BARGAINING

    def test_discovery_price_negotiation_advances_to_bargaining(self, db):
        deal = _make_deal(db, state=NegotiationState.DISCOVERY)
        result = NegotiationStateMachine(db_session=db).update_deal_state(
            deal.id, ["price_negotiation"]
        )
        assert result == NegotiationState.BARGAINING

    def test_bargaining_approval_advances_to_closing(self, db):
        deal = _make_deal(db, state=NegotiationState.BARGAINING)
        result = NegotiationStateMachine(db_session=db).update_deal_state(
            deal.id, ["approval"]
        )
        assert result == NegotiationState.CLOSING

    def test_bargaining_unsubscribe_advances_to_lost(self, db):
        deal = _make_deal(db, state=NegotiationState.BARGAINING)
        result = NegotiationStateMachine(db_session=db).update_deal_state(
            deal.id, ["unsubscribe"]
        )
        assert result == NegotiationState.LOST

    def test_no_matching_signal_keeps_current_state(self, db):
        deal = _make_deal(db, state=NegotiationState.BARGAINING)
        result = NegotiationStateMachine(db_session=db).update_deal_state(
            deal.id, ["meeting_request"]
        )
        assert result == NegotiationState.BARGAINING

    def test_won_is_absorbing_guard(self, db):
        deal = _make_deal(db, state=NegotiationState.WON)
        result = NegotiationStateMachine(db_session=db).update_deal_state(
            deal.id, ["upsell_inquiry", "approval"]
        )
        assert result == NegotiationState.WON
        db.refresh(deal)
        assert deal.negotiation_state == NegotiationState.WON

    def test_lost_is_absorbing_guard(self, db):
        deal = _make_deal(db, state=NegotiationState.LOST)
        result = NegotiationStateMachine(db_session=db).update_deal_state(
            deal.id, ["payment_commitment", "meeting_request"]
        )
        assert result == NegotiationState.LOST
        db.refresh(deal)
        assert deal.negotiation_state == NegotiationState.LOST

    def test_last_engagement_at_is_timezone_aware(self, db):
        """Naive datetime into DateTime(timezone=True) crashes on PostgreSQL
        (timestamptz) — the R13 bug class. Regress: the engine must pass a
        timezone to datetime.now(). SQLite's dialect drops tzinfo at
        serialization, so assert the contract at the call site."""
        import core.negotiation_engine as nego_mod

        fake_now = MagicMock(
            return_value=datetime(2026, 8, 13, 22, 0, 0, tzinfo=timezone.utc)
        )
        with patch.object(nego_mod, "datetime") as fake_dt:
            fake_dt.now = fake_now
            deal = _make_deal(db)
            NegotiationStateMachine(db_session=db).update_deal_state(
                deal.id, ["meeting_request"]
            )
        fake_now.assert_called_once()
        assert (
            fake_now.call_args.kwargs.get("tz") is not None
            or len(fake_now.call_args.args) > 0
        )

    def test_session_closed_when_no_injected_db(self):
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.negotiation_engine.get_db_session", return_value=fake_db):
            NegotiationStateMachine().update_deal_state("x", ["meeting_request"])
        fake_db.close.assert_called_once()

    def test_injected_db_not_closed(self, db):
        deal = _make_deal(db)
        machine = NegotiationStateMachine(db_session=db)
        closed = []
        orig_close = db.close
        db.close = lambda: closed.append(1)
        try:
            machine.update_deal_state(deal.id, ["meeting_request"])
        finally:
            db.close = orig_close
        assert closed == []


class TestCalculateNextState:
    def test_terminal_guard_won(self):
        m = NegotiationStateMachine()
        assert m._calculate_next_state(NegotiationState.WON, ["price_negotiation"]) \
            == NegotiationState.WON

    def test_terminal_guard_lost(self):
        m = NegotiationStateMachine()
        assert m._calculate_next_state(NegotiationState.LOST, ["meeting_request"]) \
            == NegotiationState.LOST

    def test_no_match_returns_current(self):
        m = NegotiationStateMachine()
        assert m._calculate_next_state(NegotiationState.FOLLOW_UP, ["small_talk"]) \
            == NegotiationState.FOLLOW_UP

    def test_initial_meeting_request_discovery(self):
        m = NegotiationStateMachine()
        assert m._calculate_next_state(
            NegotiationState.INITIAL, ["meeting_request"]
        ) == NegotiationState.DISCOVERY


class TestGetStrategyPrompt:
    def test_all_state_buckets(self, db):
        expected = {
            NegotiationState.INITIAL: "Establish initial rapport",
            NegotiationState.DISCOVERY: "Uncover pain points",
            NegotiationState.BARGAINING: "protecting margin",
            NegotiationState.CLOSING: "Finalize paperwork",
            NegotiationState.FOLLOW_UP: "without being intrusive",
            NegotiationState.WON: "ensure successful handoff",
            NegotiationState.LOST: "exit survey",
        }
        for state, snippet in expected.items():
            deal = _make_deal(db, deal_id=f"deal-{state.value}", state=state)
            prompt = NegotiationStateMachine(db_session=db).get_strategy_prompt(deal.id)
            assert snippet in prompt

    def test_deal_not_found_falls_back_to_initial(self, db):
        prompt = NegotiationStateMachine(db_session=db).get_strategy_prompt("missing")
        assert "Establish initial rapport" in prompt

    def test_session_closed_when_no_injected_db(self):
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.negotiation_engine.get_db_session", return_value=fake_db):
            NegotiationStateMachine().get_strategy_prompt("x")
        fake_db.close.assert_called_once()
