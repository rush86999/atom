# -*- coding: utf-8 -*-
"""
Bug-hunt tests for core.cron_parser.py (net-new bugs only).

Each test documents a genuine logic bug found in the module and was written
RED before the corresponding fix. Fixes already present in HEAD (the weekday
off-by-one conversion and the ``*/N`` min-offset step semantics) are NOT
re-tested here.
"""

from datetime import datetime, timezone

import pytest

from core.cron_parser import CronParser, validate_cron_expression


class TestCronListWithRangeOrStep:
    """BUG: list fields silently drop range/step sub-entries.

    A standard cron field like ``"1-5,10"`` (every value in 1-5 plus 10) or
    ``"*/15,45"`` is a single field containing comma-separated sub-fields, each
    of which may itself be a range or a step. The matcher's list branch only
    kept entries that were pure digits (``v.strip().isdigit()``), so ``"1-5"``
    and ``"*/15"`` were silently discarded. ``validate_cron_expression``
    suffered from the same flaw and wrongly rejected these expressions.
    """

    def setup_method(self):
        self.parser = CronParser()

    def test_matches_field_list_with_range_matches_value_in_range(self):
        """BUG: list-with-range drops the range entry (value within range)."""
        # value 3 is inside the range 1-5, so "1-5,10" must match.
        assert self.parser._matches_field(3, "1-5,10", 0, 59) is True

    def test_matches_field_list_with_range_matches_explicit_value(self):
        """BUG: list-with-range keeps the explicit value (10)."""
        assert self.parser._matches_field(10, "1-5,10", 0, 59) is True

    def test_matches_field_list_with_range_rejects_outside(self):
        """value outside both the range and the explicit entries must not match."""
        assert self.parser._matches_field(7, "1-5,10", 0, 59) is False

    def test_matches_field_list_with_step_matches_step_value(self):
        """BUG: list-with-step drops the step entry (e.g. */15)."""
        # 30 satisfies */15, so "*/15,45" must match 30.
        assert self.parser._matches_field(30, "*/15,45", 0, 59) is True

    def test_validate_accepts_list_with_range(self):
        """BUG: validation wrongly rejected a list containing a range."""
        assert validate_cron_expression("1-5,10 * * * *") is True

    def test_validate_accepts_list_with_step(self):
        """BUG: validation wrongly rejected a list containing a step."""
        assert validate_cron_expression("*/15,45 * * * *") is True


class TestCronStepZeroValidation:
    """BUG: ``*/0`` passes validation but crashes next-run calculation.

    A step value of zero is meaningless and produces a ``ZeroDivisionError``
    inside the matcher's modulo computation. ``validate_cron_expression``
    returned ``True`` for ``"*/0 * * * *"`` because the validator accepted any
    digit step without checking that it was non-zero, so callers were led to
    believe the expression was safe only to crash later.
    """

    def test_validate_rejects_step_zero_wildcard(self):
        """BUG: ``*/0`` must be rejected by validation."""
        assert validate_cron_expression("*/0 * * * *") is False

    def test_validate_rejects_step_zero_range(self):
        """BUG: ``0-59/0`` must be rejected by validation."""
        assert validate_cron_expression("0-59/0 * * * *") is False

    def test_matches_field_step_zero_does_not_crash(self):
        """BUG: ``*/0`` raised ZeroDivisionError instead of returning False."""
        # Should return False (no value satisfies an impossible step) rather
        # than raising ZeroDivisionError out of the matcher.
        assert self._new_parser()._matches_field(5, "*/0", 0, 59) is False

    def _new_parser(self):
        return CronParser()


class TestCronNextRunWithListField:
    """Integration: get_next_run must honour list-of-range fields after the fix."""

    def test_next_run_with_list_range_field(self):
        """BUG: a schedule using a list-with-range never fired correctly.

        ``"0 1-5,10 * * *"`` means "at minute 0 of hours 1-5 and 10". Starting
        from 00:30 the next fire should be 01:00 (covered by the range entry),
        which the pre-fix matcher would have skipped.
        """
        parser = CronParser()
        after = datetime(2026, 5, 5, 0, 30, tzinfo=timezone.utc)
        nxt = parser.get_next_run("0 1-5,10 * * *", after=after)
        assert (nxt.hour, nxt.minute) == (1, 0)
