"""Staged-delivery contract pins (guide steps 3-4, owner items 1-5)."""
from __future__ import annotations

import json
import pytest
from decimal import Decimal

from core.job_delivery import (
    job_event_id, render_acknowledgement, render_findings,
    render_job_result, render_remaining)


FINDINGS = [
    {"field": "completion_date", "column": "Completion Date",
     "raw": "2026-11-15",
     "parsed": {"value": "2026-11-15", "raw": "2026-11-15"},
     "source": "Plan.xlsx!Projects!row10",
     "content_hash": "abc123def456"},
    {"field": "floor_area", "column": "Floor Area (sq ft)",
     "raw": "12500",
     "parsed": {"value": 12500, "raw": "12500"},
     "source": "Plan.xlsx!Projects!row10"},
    {"field": "approved", "column": "Approved", "raw": "no",
     "parsed": {"value": False, "raw": "no"},
     "source": "Plan.xlsx!Projects!row10"},
    {"field": "contractor", "column": "Contractor",
     "raw": "Delta Builders Ltd.",
     "parsed": {"value": "Delta Builders Ltd.",
                "raw": "Delta Builders Ltd."},
     "source": "Plan.xlsx!Projects!row10"},
]


class TestEventIdentity:
    def test_distinct_events_distinct_ids(self):
        a = job_event_id("job1", 1, "terminal")
        b = job_event_id("job1", 2, "terminal")
        assert a != b

    def test_same_event_same_id(self):
        assert (job_event_id("job1", 1, "terminal")
                == job_event_id("job1", 1, "terminal"))

    def test_identical_text_different_jobs_not_deduped(self):
        """The ID is the dedup key, not the text — two jobs producing
        identical rendering text are distinct events."""
        a = job_event_id("job-A", 1, "terminal")
        b = job_event_id("job-B", 1, "terminal")
        assert a != b


class TestDeterministicRendering:
    def test_all_four_types_rendered(self):
        out = render_findings(FINDINGS, "Site A Expansion")
        assert "2026-11-15" in out
        assert "12500" in out
        assert "False" in out
        assert "Delta Builders Ltd." in out
        assert "Site A Expansion" in out

    def test_false_and_zero_visible(self):
        falsy = [
            {"field": "area", "column": "Area", "raw": "0",
             "parsed": {"value": 0, "raw": "0"}, "source": "F!S!r1"},
            {"field": "ok", "column": "OK", "raw": "no",
             "parsed": {"value": False, "raw": "no"}, "source": "F!S!r1"}]
        out = render_findings(falsy)
        assert "0" in out and "False" in out

    def test_source_and_version_attached(self):
        out = render_findings(FINDINGS[:1])
        assert "Plan.xlsx!Projects!row10" in out
        assert "content abc123def456" in out

    def test_remaining_rendered(self):
        out = render_remaining([
            {"next_action": "read Plan.xlsx for Site B"}])
        assert "Site B" in out and "Still needed" in out

    def test_empty_findings_honest(self):
        assert render_findings([]) == ""

    def test_job_result_partial_scope_visible(self):
        task = {
            "operations": [
                {"execution": {"findings": FINDINGS[:2],
                               "items": {"Site A": "matched"}}}],
            "status": "active",
            "task_revision": {"unresolved": []},
        }
        out = render_job_result(task, "job-x")
        assert "2026-11-15" in out
        assert "12500" in out
        assert "partial" in out.lower()


class TestAcknowledgement:
    def test_ack_describes_durable_job(self):
        out = render_acknowledgement("job-abc123", "Site A review", 2)
        assert "job-abc123"[:8] in out or "job" in out
        assert "Site A" in out
        assert "2 step" in out


class TestFullRecord:
    def test_render_from_task_record(self):
        """The render reads the AUTHORITATIVE record (operations +
        open work), never a prose field."""
        task = {
            "operations": [
                {"operation_type": "retrieve", "status": "applied",
                 "execution": {"findings": FINDINGS,
                               "items": {"Site A": "matched"}}}],
            "status": "completed",
            "task_revision": {"unresolved": []},
        }
        out = render_job_result(task, "job-done")
        for expected in ("2026-11-15", "12500", "False",
                         "Delta Builders Ltd.", "completed"):
            assert expected in out, f"{expected!r} missing from render"
