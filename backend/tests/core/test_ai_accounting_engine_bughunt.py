"""
Bug-hunt tests for core/ai_accounting_engine.py (TDD).

Each test documents a genuine, net-new bug. Tests are written FIRST and must
fail for the right reason before the source is fixed.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from core.ai_accounting_engine import (
    AIAccountingEngine,
    Transaction,
    TransactionStatus,
    TransactionSource,
)


@pytest.fixture
def engine():
    return AIAccountingEngine()


class TestAIAccountingEngineBugs:
    """Net-new bugs in ai_accounting_engine."""

    def test_run_scenario_parses_comma_thousands(self, engine):
        """BUG: run_scenario number regex r'\\$?(\\d+)[k,]*' mis-parses
        comma-separated thousands. The greedy \\d+ stops at the first comma,
        so '$10,000' captures group(1)='10' and the trailing '[k,]*' swallows
        ',000'. The value is then computed as 10 instead of 10000 — a 1000x
        under-estimate of the financial impact.

        '$5k' correctly yields 5000, but '$5,000' (the same dollar value)
        yields 5. Scenario planning for hires/expenses is silently wrong
        whenever amounts use thousands separators.
        """
        result_k = engine.run_scenario("expense $5k", [])
        result_comma = engine.run_scenario("expense $5,000", [])

        assert result_k["impact_value"] == -5000
        # Same dollar amount, must produce the same impact.
        assert result_comma["impact_value"] == -5000

    def test_run_scenario_parses_large_comma_amount(self, engine):
        """BUG (same root cause): '$10,000' must parse as 10000, not 10.
        Verified across the hire / lose-client code paths.
        """
        result = engine.run_scenario("lose $10,000 client", [])
        assert result["impact_value"] == -10000
        assert result["risk_level"] == "high"
