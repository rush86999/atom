"""
P0 — temporal normalization layer (Temporal Evolution phase, A2/A7/A8).

RED: `core.memory.temporal_normalizer` does not exist yet — the import below
fails, proving the test targets are new behavior (TDD red → green).

Contracts pinned here (deterministic — no network, no DB, no LLM):
  - extract_temporal(text) -> List[TemporalEntity]: regex-based date anchors
    (ISO dates, "as of/on <Month> <d>, <yyyy>", "<Month> <yyyy>", "Q<n> <yyyy>",
    "by end of <yyyy>"), sorted by as_of desc, capped at 10, never raises,
    empty when ATOM_TEMPORALITY_ENABLED=false.
  - normalize_record(record) -> dict: additive — returns the record content
    plus `temporal_entities` / `as_of` / `temporal_axis`; never raises; flag-off
    is a no-op.
  - temporal_entities receiver: handle_temporal_entities(...) stores
    workspace-scoped; encode_temporal_context(...) re-reads with bi-temporal
    edges_as_of semantics (visible when as_of <= t < valid_until).
  - Ingestion hook: IngestionPipelineService._apply_temporal_normalization is
    wired through a _record_to_text override so EVERY ingestion path (sync,
    webhook, binary, tiered) passes through it; never raises.
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from core.memory.temporal_normalizer import (
    TemporalEntity,
    encode_temporal_context,
    extract_temporal,
    handle_temporal_entities,
    normalize_record,
)

UTC = timezone.utc


def _utc(y: int, m: int, d: int) -> datetime:
    return datetime(y, m, d, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _clean_normalizer_store():
    # In-memory store must not leak across tests.
    from core.memory.temporal_normalizer import _reset_store

    _reset_store()
    yield
    _reset_store()


class TestExtractTemporal:
    def test_iso_date_anchor(self):
        entities = extract_temporal("Deal closed on 2026-03-03 for $50k ARR")
        assert len(entities) == 1
        e = entities[0]
        assert e.as_of == _utc(2026, 3, 3)
        assert e.entity_type == "date"
        assert e.confidence == 1.0
        assert "2026-03-03" in e.source_text

    def test_as_of_month_day_year_phrase(self):
        entities = extract_temporal(
            "Company status as of March 3, 2026: healthy, 12 hires."
        )
        assert len(entities) == 1
        assert entities[0].as_of == _utc(2026, 3, 3)
        assert entities[0].entity_type == "date"

    def test_on_phrase_without_comma(self):
        entities = extract_temporal("On Jan 15 2026 revenue crossed $1M.")
        assert len(entities) == 1
        assert entities[0].as_of == _utc(2026, 1, 15)

    def test_month_year_anchor(self):
        entities = extract_temporal("Board deck updated in March 2026.")
        assert len(entities) == 1
        assert entities[0].as_of == _utc(2026, 3, 1)
        assert entities[0].entity_type == "month"

    def test_quarter_window(self):
        entities = extract_temporal("Launch planned for Q3 2026.")
        assert len(entities) == 1
        e = entities[0]
        assert e.as_of == _utc(2026, 7, 1)
        assert e.valid_until == _utc(2026, 10, 1)
        assert e.entity_type == "window"

    def test_by_end_of_year_window(self):
        entities = extract_temporal("Ship the dashboard by end of 2026.")
        assert len(entities) == 1
        e = entities[0]
        assert e.valid_until == _utc(2027, 1, 1)
        assert e.entity_type == "window"

    def test_no_dates_returns_empty(self):
        assert extract_temporal("Just a casual chat about the weather.") == []

    def test_never_raises_on_garbage(self):
        assert extract_temporal(None) == []
        assert extract_temporal(b"\x00\x01 binary") == []
        assert extract_temporal(12345) == []
        assert extract_temporal("") == []

    def test_capped_at_ten(self):
        text = " ".join(f"milestone {i} on 2026-0{i % 2 + 1}-0{i % 9 + 1}" for i in range(20))
        entities = extract_temporal(text)
        assert len(entities) <= 10

    def test_sorted_by_as_of_desc(self):
        text = "A on 2026-01-01. B on 2026-05-05. C on 2026-03-03."
        entities = extract_temporal(text)
        as_ofs = [e.as_of for e in entities]
        assert as_ofs == sorted(as_ofs, reverse=True)

    def test_flag_off_returns_empty(self, monkeypatch):
        monkeypatch.setenv("ATOM_TEMPORALITY_ENABLED", "false")
        assert extract_temporal("Launch planned for Q3 2026.") == []


class TestNormalizeRecord:
    def test_stamps_temporal_keys(self):
        record = {
            "id": "rec-1",
            "name": "Acme Q3 report",
            "text": "Launch planned for Q3 2026.",
        }
        out = normalize_record(record)
        assert "temporal_entities" in out
        assert "as_of" in out
        assert "temporal_axis" in out
        assert len(out["temporal_entities"]) == 1
        assert out["as_of"] == _utc(2026, 7, 1).isoformat()
        assert out["temporal_axis"] == "Q3 2026"
        assert out["name"] == record["name"]

    def test_original_record_untouched(self):
        record = {"id": "rec-2", "name": "Acme"}
        out = normalize_record(record)
        assert out is not record  # copy, never the input object
        assert record.get("as_of") is None
        assert out["name"] == "Acme"

    def test_never_raises_on_weird_records(self):
        assert normalize_record(None) == {}
        assert normalize_record(42) == {}
        assert normalize_record(["a", "b"]) == {}  # unshaped → empty, no raise
        assert normalize_record({"text": None}) == {"text": None}

    def test_flag_off_noop(self, monkeypatch):
        monkeypatch.setenv("ATOM_TEMPORALITY_ENABLED", "false")
        record = {"id": "rec-3", "text": "Launch planned for Q3 2026."}
        out = normalize_record(record)
        assert out == record
        assert "temporal_entities" not in out


class TestTemporalEntitiesReceiver:
    def test_store_and_encode(self):
        handle_temporal_entities(
            [
                {"name": "Launch", "entity_type": "window", "as_of": "2026-07-01T00:00:00+00:00",
                 "valid_until": "2026-10-01T00:00:00+00:00", "confidence": 0.9},
                {"name": "Funding", "entity_type": "date", "as_of": "2026-03-03T00:00:00+00:00",
                 "confidence": 1.0},
            ],
            "ws-a",
            source="rec-1",
        )
        ctx = encode_temporal_context("ws-a")
        assert len(ctx) == 2
        assert ctx[0]["name"] == "Launch"  # newest as_of first
        assert ctx[1]["name"] == "Funding"
        assert ctx[1]["entity_type"] == "date"
        assert ctx[1]["provenance"] == "rec-1"

    def test_workspace_isolation(self):
        handle_temporal_entities([{"name": "Acme", "entity_type": "date",
                                   "as_of": "2026-01-01T00:00:00+00:00"}], "ws-a")
        handle_temporal_entities([{"name": "Globex", "entity_type": "date",
                                   "as_of": "2026-02-01T00:00:00+00:00"}], "ws-b")
        ctx_a = {e["name"] for e in encode_temporal_context("ws-a")}
        assert ctx_a == {"Acme"}
        assert encode_temporal_context("ws-unknown") == []

    def test_as_of_filter_bi_temporal(self):
        # edges_as_of semantics: visible at time t when as_of <= t and
        # (valid_until is None or valid_until > t).
        handle_temporal_entities(
            [
                {"name": "Past", "entity_type": "date", "as_of": "2026-01-01T00:00:00+00:00",
                 "valid_until": "2026-03-01T00:00:00+00:00"},
                {"name": "Current", "entity_type": "date", "as_of": "2026-03-10T00:00:00+00:00"},
            ],
            "ws-a",
        )
        visible = {e["name"] for e in encode_temporal_context("ws-a", as_of=_utc(2026, 3, 20))}
        assert visible == {"Current"}
        all_ctx = {e["name"] for e in encode_temporal_context("ws-a")}
        assert all_ctx == {"Past", "Current"}

    def test_limit(self):
        handle_temporal_entities(
            [{"name": f"E{i}", "entity_type": "date",
              "as_of": f"2026-01-{i:02d}T00:00:00+00:00"} for i in range(1, 31)],
            "ws-a",
        )
        assert len(encode_temporal_context("ws-a", limit=5)) == 5

    def test_malformed_payload_never_raises(self):
        handle_temporal_entities([{"bogus": 1}, None, "nope"], "ws-a")
        assert encode_temporal_context("ws-a") == []

    def test_flag_off_noop(self, monkeypatch):
        monkeypatch.setenv("ATOM_TEMPORALITY_ENABLED", "false")
        handle_temporal_entities([{"name": "E", "entity_type": "date",
                                   "as_of": "2026-01-01T00:00:00+00:00"}], "ws-a")
        assert encode_temporal_context("ws-a") == []


class TestIngestionHook:
    """A2: IngestionPipelineService temporal hook + _record_to_text override."""

    @staticmethod
    def _make_service() -> Mock:
        with patch.multiple(
            "core.ingestion_pipeline",
            LanceDBHandler=Mock(return_value=Mock()),
            GraphRAGEngine=Mock(return_value=Mock()),
            MultiEntityLLMExtractor=Mock(return_value=Mock()),
            SchemaDiscoveryService=Mock(return_value=Mock()),
            EntityLinkingService=Mock(return_value=Mock()),
            UsageTrackingService=Mock(return_value=Mock()),
        ), patch(
            "core.meta_agent_orchestrator.MetaAgentOrchestrator",
            Mock(return_value=Mock()),
        ):
            from core.ingestion_pipeline import IngestionPipelineService

            return IngestionPipelineService(tenant_id="t-1", workspace_id="ws-1", db=Mock())

    def test_hook_stamps_record_and_stores(self):
        svc = self._make_service()
        record = {"id": "rec-x", "name": "Acme", "text": "Launch planned for Q3 2026."}

        anchor = TemporalEntity(
            name="Q3 2026",
            entity_type="window",
            as_of=_utc(2026, 7, 1),
            valid_until=_utc(2026, 10, 1),
            source_text="Q3 2026",
            confidence=0.9,
        )
        with patch("core.ingestion_pipeline.extract_temporal", return_value=[anchor]), patch(
            "core.ingestion_pipeline.handle_temporal_entities"
        ) as store:
            # Guard: if the hook is not wired, this returns raw text (no stamps)
            # and the asserts below fail = RED.
            text = svc._record_to_text(record, "stripe")
            store.assert_called_once()
            args, kwargs = store.call_args
            assert args[1] == "ws-1"  # handle_temporal_entities(payload, workspace_id, ...)

        assert "Q3 2026" in text  # base behavior preserved
        assert "temporal_entities" in record
        assert "as_of" in record
        assert record["as_of"] == "2026-07-01T00:00:00+00:00"

    def test_hook_never_raises(self):
        svc = self._make_service()
        record = {"id": "rec-y", "name": "Acme"}
        with patch.object(svc, "_apply_temporal_normalization", side_effect=RuntimeError("boom")):
            # The override must swallow and fall back, never raising.
            text = svc._record_to_text(record, "stripe")
        assert isinstance(text, str)
        assert "Acme" in text

    def test_normalizer_failure_never_breaks_ingestion(self):
        svc = self._make_service()
        record = {"id": "rec-z", "name": "Acme"}
        with patch("core.ingestion_pipeline.extract_temporal",
                   side_effect=RuntimeError("boom")):
            out = svc._apply_temporal_normalization(record)
        assert out == record