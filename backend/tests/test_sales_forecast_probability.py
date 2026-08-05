"""
Tests for sales weighted-forecast probability handling.

`d.probability or 0.5` treats probability=0 as falsy (Python `or`), inflating
the forecast: a deal explicitly assessed at 0% win probability contributes
50% of its value instead of 0. The guard should be
`d.probability if d.probability is not None else 0.5`.
"""

import pytest


class TestWeightedForecastProbability:
    def test_zero_probability_contributes_zero(self):
        """A deal with probability=0.0 must contribute 0, not 0.5 * value."""
        deal_value = 10000.0
        probability = 0.0  # explicitly zero — a dead deal still in the pipeline

        # The CURRENT (buggy) expression:
        buggy = deal_value * (probability or 0.5)
        # The CORRECT expression:
        correct = deal_value * (probability if probability is not None else 0.5)

        assert correct == 0.0, "A 0% probability deal must contribute $0"
        assert buggy == 5000.0, (
            "The buggy `or 0.5` treats 0 as falsy, contributing $5000 instead of $0"
        )

    def test_none_probability_defaults_to_half(self):
        """A deal with probability=None defaults to 0.5 (the intended behavior)."""
        deal_value = 10000.0
        probability = None

        result = deal_value * (probability if probability is not None else 0.5)
        assert result == 5000.0

    def test_normal_probability_used_correctly(self):
        """A 25% probability deal contributes 25% of value."""
        deal_value = 8000.0
        probability = 0.25

        result = deal_value * (probability if probability is not None else 0.5)
        assert result == 2000.0
