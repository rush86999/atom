"""
Bug-hunt tests for core/negotiation_engine.py.

These tests don't require a real database: NegotiationStateMachine lets callers
inject `db_session`, so we hand it a MagicMock that returns a stand-in Deal.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from sales.models import NegotiationState


def _deal(state):
    """Stand-in Deal object with the negotiation_state we want to test."""
    d = SimpleNamespace(
        id="deal-1",
        negotiation_state=state,
        last_engagement_at=None,
    )
    return d


def _engine_with_deal(deal):
    """Build a NegotiationStateMachine whose injected db returns `deal`."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = deal
    from core.negotiation_engine import NegotiationStateMachine
    return NegotiationStateMachine(db_session=db), db


# =============================================================================
# BUG: terminal states (WON/LOST) can be resurrected by ordinary signals
# =============================================================================
def test_bug_lost_deal_is_not_resurrected_by_approval_signal():
    """BUG: _calculate_next_state has no terminal-state guard. A LOST deal
    that later receives an 'approval' signal (e.g. customer re-engages via a
    follow-up) is advanced back to CLOSING, silently resurrecting a dead deal
    and corrupting pipeline reporting.

    Fix: once a deal is WON or LOST, _calculate_next_state must return the
    current state unchanged regardless of incoming signals.
    """
    engine, db = _engine_with_deal(_deal(NegotiationState.LOST))

    result = engine.update_deal_state("deal-1", ["approval", "payment_commitment"])

    assert result == NegotiationState.LOST, (
        "a LOST deal must stay LOST; got " f"{result!r}"
    )
    # And the deal row must NOT have been mutated/committed.
    assert db.commit.call_count == 0


def test_bug_won_deal_is_not_resurrected_by_price_negotiation():
    """BUG: same root cause — a WON deal receiving a 'price_negotiation'
    signal (e.g. a late inbound email misclassified by the AI) is advanced
    back to BARGAINING. WON is a terminal state and must be immutable to
    signal-driven transitions.
    """
    engine, db = _engine_with_deal(_deal(NegotiationState.WON))

    result = engine.update_deal_state("deal-1", ["price_negotiation", "upsell_inquiry"])

    assert result == NegotiationState.WON, (
        "a WON deal must stay WON; got " f"{result!r}"
    )
    assert db.commit.call_count == 0
