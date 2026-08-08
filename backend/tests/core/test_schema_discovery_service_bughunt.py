# -*- coding: utf-8 -*-
"""Bug-hunt tests (TDD RED->GREEN) for core/schema_discovery_service.py.

Each test targets a genuinely-new bug (fix absent from HEAD).
"""
import pytest

from core.schema_discovery_service import SchemaDiscoveryService


@pytest.fixture()
def svc():
    """SchemaDiscoveryService needs a db arg but the inference helpers don't use it."""
    class _FakeDb:
        pass

    return SchemaDiscoveryService(_FakeDb())


# ============================================================================
# BUG 1 (MEDIUM): _infer_string_format falsely flags hyphenated / colon-bearing
# strings as date-time because the "date_indicators" list contains bare
# substrings "-", "T", ":", "Z" that match almost any identifier.
#
# Real-world impact: a product-code / slug column such as
# ["PRD-100", "PRD-101", ...] is detected as {"format": "date-time"}, producing
# a wrong JSON Schema. The fix must only flag a value as date-time when it
# actually parses as an ISO-8601 timestamp, not merely because it contains a
# hyphen.
# ============================================================================


class TestInferStringFormatDateTimeFalsePositive:
    """BUG: hyphenated identifiers must NOT be detected as date-time."""

    def test_product_codes_not_datetime(self, svc):
        """BUG: kebab-case product codes are misdetected as date-time."""
        examples = ["PRD-100", "PRD-101", "PRD-102", "PRD-103", "PRD-104"]

        fmt = svc._infer_string_format(examples)

        assert "format" not in fmt or fmt.get("format") != "date-time", (
            f"product codes wrongly flagged as date-time: {fmt!r}"
        )

    def test_slugs_not_datetime(self, svc):
        """BUG: kebab-case slugs are misdetected as date-time via the '-' indicator."""
        examples = ["us-east-1", "us-west-2", "eu-central-1"]

        fmt = svc._infer_string_format(examples)

        assert fmt.get("format") != "date-time", (
            f"region slugs wrongly flagged as date-time: {fmt!r}"
        )

    def test_real_iso_timestamps_still_datetime(self, svc):
        """Regression guard: genuine ISO-8601 timestamps must still be date-time."""
        examples = [
            "2026-01-15T10:30:00Z",
            "2026-02-20T14:45:30Z",
            "2026-03-10T09:15:00Z",
            "2026-04-05T18:00:00Z",
        ]

        fmt = svc._infer_string_format(examples)

        assert fmt.get("format") == "date-time", (
            f"genuine ISO timestamps not flagged as date-time: {fmt!r}"
        )

    def test_iso_timestamp_with_offset_still_datetime(self, svc):
        """Regression guard: ISO timestamps with numeric offset must be date-time."""
        examples = [
            "2026-01-15T10:30:00+00:00",
            "2026-02-20T14:45:30-05:00",
            "2026-03-10T09:15:00+09:30",
        ]

        fmt = svc._infer_string_format(examples)

        assert fmt.get("format") == "date-time", f"{fmt!r}"

    def test_plain_time_strings_not_datetime(self, svc):
        """BUG: bare clock times '10:30:00' match ':' indicator -> false date-time."""
        examples = ["10:30:00", "14:45:30", "09:15:00"]

        fmt = svc._infer_string_format(examples)

        # Bare times are not ISO-8601 datetimes (no date component).
        assert fmt.get("format") != "date-time", f"{fmt!r}"
