# -*- coding: utf-8 -*-
"""Coverage wave 74 — core/cron_parser.py (pure Python, no deps).

TDD targets:
- ``get_next_run`` exhaustion branch (no match in a year → ValueError) via
  monkeypatched always-False matcher (avoids a 525600-iteration real scan).
- ``_matches_field`` step edge cases: non-digit step, zero step, range-step
  (inside/outside range).
- ``natural_language_to_cron`` callable-pattern branch (success + failure).
- ``_to_24h_static`` 12am conversion + "00" minute normalization.
- ``validate_cron_expression`` per-field rejections + non-string input
  (exception → False) + step/list validation rules.
"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from core.cron_parser import (
    CronParser,
    _to_24h_static,
    _weekday_to_num_static,
    natural_language_to_cron,
    validate_cron_expression,
)


class TestNextRunExhaustion:
    def test_no_match_in_year_raises(self):
        parser = CronParser()
        after = datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc)
        with patch.object(parser, "_matches_cron", return_value=False):
            with pytest.raises(ValueError, match="Invalid cron expression"):
                parser.get_next_run("0 0 30 2 *", after=after)

    def test_impossible_date_expression_raises(self):
        parser = CronParser()
        after = datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="Invalid cron expression"):
            parser.get_next_run("0 0 31 2 *", after=after)

    def test_invalid_parts_count_raises(self):
        parser = CronParser()
        with pytest.raises(ValueError, match="Invalid cron expression"):
            parser.get_next_run("* * *", datetime(2026, 5, 5, tzinfo=timezone.utc))

    def test_default_after_is_now(self):
        parser = CronParser()
        result = parser.get_next_run("* * * * *")
        assert result.minute is not None


class TestMatchesFieldSteps:
    @pytest.fixture()
    def parser(self):
        return CronParser()

    def test_step_non_digit_returns_false(self, parser):
        assert parser._matches_field(5, "*/x", 0, 59) is False

    def test_step_zero_returns_false(self, parser):
        assert parser._matches_field(5, "*/0", 0, 59) is False

    def test_range_step_inside(self, parser):
        # "1-10/2" → 1,3,5,7,9
        assert parser._matches_field(3, "1-10/2", 0, 59) is True
        assert parser._matches_field(4, "1-10/2", 0, 59) is False

    def test_range_step_outside_range(self, parser):
        assert parser._matches_field(11, "1-10/2", 0, 59) is False

    def test_malformed_step_base_falls_through(self, parser):
        assert parser._matches_field(5, "x/2", 0, 59) is False
        assert parser._matches_field(5, "/2", 0, 59) is False

    def test_wildcard_step_day_of_month_min_is_one(self, parser):
        # day-of-month min is 1 → */2 = 1,3,5...
        assert parser._matches_field(1, "*/2", 1, 31) is True
        assert parser._matches_field(2, "*/2", 1, 31) is False

    def test_list_with_range_entry(self, parser):
        assert parser._matches_field(4, "1-5,10", 0, 59) is True
        assert parser._matches_field(10, "1-5,10", 0, 59) is True
        assert parser._matches_field(7, "1-5,10", 0, 59) is False

    def test_list_with_step_entry(self, parser):
        assert parser._matches_field(45, "*/15,45", 0, 59) is True

    def test_weekday_convention_matching(self, parser):
        # dt weekday: Monday=0 → cron 1
        monday = datetime(2026, 5, 11, 9, 0, tzinfo=timezone.utc)  # Monday
        sunday = datetime(2026, 5, 10, 9, 0, tzinfo=timezone.utc)  # Sunday
        assert parser._matches_cron(monday, "0", "9", "*", "*", "1") is True
        assert parser._matches_cron(monday, "0", "9", "*", "*", "0") is False
        assert parser._matches_cron(sunday, "0", "9", "*", "*", "0") is True

    def test_mismatch_short_circuits(self, parser):
        dt = datetime(2026, 5, 11, 9, 0, tzinfo=timezone.utc)
        assert parser._matches_cron(dt, "5", "9", "*", "*", "*") is False
        assert parser._matches_cron(dt, "0", "8", "*", "*", "*") is False
        assert parser._matches_cron(dt, "0", "9", "12", "*", "*") is False
        assert parser._matches_cron(dt, "0", "9", "*", "12", "*") is False


class TestNaturalLanguageCallable:
    def test_callable_pattern_success(self):
        with patch.object(CronParser, "PATTERNS", {
            r"custom": lambda match: "5 5 * * *",
        }):
            assert natural_language_to_cron("custom") == "5 5 * * *"

    def test_callable_pattern_failure_continues_to_others(self):
        with patch.object(CronParser, "PATTERNS", {
            r"d.*": lambda match: (_ for _ in ()).throw(RuntimeError("boom")),
            r"daily": "0 9 * * *",
        }):
            assert natural_language_to_cron("daily") == "0 9 * * *"

    def test_unparseable_raises(self):
        with pytest.raises(ValueError, match="Could not parse"):
            natural_language_to_cron("whenever I feel like it")


class TestTo24hStatic:
    def test_midnight_am(self):
        assert _to_24h_static("12", "0", "am") == "0"

    def test_noon_pm(self):
        assert _to_24h_static("12", "0", "pm") == "12"

    def test_pm(self):
        assert _to_24h_static("2", "30", "pm") == "14"

    def test_minute_00_normalized(self):
        # minute not in return; internal normalization must not raise
        assert _to_24h_static("9", "00", "am") == "9"

    def test_no_meridiem(self):
        assert _to_24h_static("9", "30", None) == "9"


class TestWeekdayToNumStatic:
    def test_sunday(self):
        assert _weekday_to_num_static("sunday") == "0"

    def test_unknown_defaults_to_monday(self):
        assert _weekday_to_num_static("funday") == "1"


class TestValidate:
    def test_valid_full_expression(self):
        assert validate_cron_expression("*/15 9-17 1-15 1-12 0-6") is True
        assert validate_cron_expression("0 9 * * *") is True

    def test_invalid_field_ranges(self):
        assert validate_cron_expression("60 * * * *") is False   # minute
        assert validate_cron_expression("* 24 * * *") is False   # hour
        assert validate_cron_expression("* * 0 * *") is False    # day
        assert validate_cron_expression("* * * 13 *") is False   # month
        assert validate_cron_expression("* * * * 7") is False    # weekday

    def test_invalid_step_zero(self):
        assert validate_cron_expression("*/0 * * * *") is False

    def test_valid_step(self):
        assert validate_cron_expression("*/15 * * * *") is True

    def test_range_step_validation(self):
        assert validate_cron_expression("0 9 1-10/2 * *") is True

    def test_list_validation(self):
        assert validate_cron_expression("0 9,12,15 * * *") is True
        assert validate_cron_expression("0 9,12,15, * * *") is False  # trailing empty
        assert validate_cron_expression("0 9,12,x * * *") is False     # bad entry
        assert validate_cron_expression("0 9-17,20 * * *") is True     # range in list

    def test_bad_token(self):
        assert validate_cron_expression("abc def ghi jkl mno") is False

    def test_non_string_input_returns_false(self):
        assert validate_cron_expression(None) is False
        assert validate_cron_expression(12345) is False

    def test_too_few_parts(self):
        assert validate_cron_expression("0 9 * *") is False
