"""Natural-language predicate controls for the shared table selector.

These are the phrasings employees actually use. A sentence-final period must
not turn a numeric literal into a string, and "is greater than" must bind the
ordering operator instead of equality against the word "greater".
"""
from __future__ import annotations

import pandas as pd

from core.table_selection import resolve_selection


COLUMNS = ["Unit Price", "Description", "No."]


def _predicate(ask: str):
    df = pd.DataFrame({
        "Unit Price": [5, 10001, 20000, 50000],
        "Description": ["a", "b", "c", "d"],
        "No.": ["1", "2", "3", "4"],
    })
    return resolve_selection(COLUMNS, ask, df).get("predicate")


def test_is_greater_than_binds_ordering_not_equality():
    assert _predicate("Assess rows where Unit Price is greater than 10000.") == {
        "column": "Unit Price", "operator": ">", "value": 10000,
    }


def test_symbolic_comparison_ignores_sentence_period():
    assert _predicate("Assess rows where Unit Price > 10000.") == {
        "column": "Unit Price", "operator": ">", "value": 10000,
    }


def test_is_at_least_binds_inclusive_ordering():
    assert _predicate("Assess rows where Unit Price is at least 20000.") == {
        "column": "Unit Price", "operator": ">=", "value": 20000,
    }


def test_is_equality_still_binds_equality():
    assert _predicate("Assess rows where Unit Price is 20000.") == {
        "column": "Unit Price", "operator": "=", "value": 20000,
    }
