# -*- coding: utf-8 -*-
"""File-mention identity (2026-09-23 workbook incident).

The filename detector truncated "Consolidated Price List 2019.xlsx" to
"2019.xlsx" (its regex cannot span spaces) and the matcher then accepted
ANY shared token — a bare year — as proof of identity, so unrelated
ingested sources branded a workbook preview and the answer/preview pair
could contradict each other. These tests pin the fixed contract:

- spaced filenames are detected WHOLE (never truncated to the last
  segment), with leading conversational words stripped;
- identity is TIERED: exact/normalized/containment verify; token overlap
  only discovers; year-only or extension-only overlap is NOT a match;
- previews/blocks distinguish verified identity from candidates and label
  ingested rows as cached samples.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest

from core import agent_file_context as afc


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

class TestDetectFileMentions:
    def test_incident_name_detected_whole_not_truncated(self):
        mentions = afc.detect_file_mentions(
            "the workbook Consolidated Price List 2019.xlsx has the prices")
        assert mentions == ["consolidated price list 2019.xlsx"]

    def test_prose_prefix_pollution_still_contains_full_name(self):
        # Unquoted prose may pull a preceding word into the spaced match
        # ("8 machine prices in <name>"); the mention may gain a prefix
        # but must never LOSE the name to truncation.
        mentions = afc.detect_file_mentions(
            "find the 8 machine prices in Consolidated Price List 2019.xlsx please")
        assert len(mentions) == 1
        assert mentions[0].endswith("consolidated price list 2019.xlsx")
        assert mentions[0] != "2019.xlsx"

    def test_truncated_segment_not_reported_alongside_full_name(self):
        mentions = afc.detect_file_mentions(
            "look in Consolidated Price List 2019.xlsx")
        assert "2019.xlsx" not in mentions

    def test_leading_conversational_words_stripped(self):
        assert afc.detect_file_mentions(
            "hey check the price list.xlsx data") == ["price list.xlsx"]

    def test_no_space_names_unchanged(self):
        assert afc.detect_file_mentions(
            "check the acme_thread.xlsx data") == ["acme_thread.xlsx"]

    def test_dotted_no_space_name_unchanged(self):
        assert afc.detect_file_mentions(
            "open acme.q3.v2.xlsx") == ["acme.q3.v2.xlsx"]

    def test_bare_segment_name_standalone_still_detected(self):
        assert afc.detect_file_mentions("what about 2019.xlsx?") == ["2019.xlsx"]

    def test_short_real_name_keeps_its_first_word(self):
        # "Sheet" is a strip-word, but "1.xlsx" carries no identity without
        # it — the guard must keep it.
        assert afc.detect_file_mentions("use Sheet 1.xlsx") == ["sheet 1.xlsx"]

    def test_incident_confirmation_carries_no_false_mention(self):
        # "That filename is correct" names no file-with-extension.
        assert afc.detect_file_mentions("That filename is correct") == []

    def test_quoted_spaced_name(self):
        assert afc.detect_file_mentions(
            'yes, "Consolidated Price List 2019.xlsx" is the right one'
        ) == ["consolidated price list 2019.xlsx"]

    def test_multiple_mentions_most_specific_first(self):
        mentions = afc.detect_file_mentions(
            "compare price list.xlsx with stock.csv")
        assert "price list.xlsx" in mentions
        assert "stock.csv" in mentions

    def test_match_does_not_cross_sentence_punctuation(self):
        # A comma/period boundary must stop the spaced match.
        mentions = afc.detect_file_mentions(
            "Sure, check that. Prices.xlsx is the file")
        assert mentions == ["prices.xlsx"]


# ---------------------------------------------------------------------------
# Tiered identity
# ---------------------------------------------------------------------------

class TestScoreFileMatch:
    def test_exact(self):
        assert afc.score_file_match(
            "Consolidated Price List 2019.xlsx",
            "consolidated price list 2019.xlsx") == afc.MATCH_TIER_EXACT

    def test_normalized_separators_and_case(self):
        assert afc.score_file_match(
            "consolidated_price_list 2019.XLSX",
            "Consolidated Price-List 2019.xlsx",
        ) == afc.MATCH_TIER_NORMALIZED

    def test_containment_with_strong_token(self):
        assert afc.score_file_match(
            "price list.xlsx",
            "Consolidated Price List 2019.xlsx",
        ) == afc.MATCH_TIER_CONTAINMENT

    def test_incident_year_only_overlap_is_not_a_match(self):
        # THE regression: "2019.xlsx" used to match ANY 2019 source.
        assert afc.score_file_match("2019.xlsx", "Sales 2019 final.xlsx") is None
        assert afc.score_file_match("2019.xlsx", "Q3 Report 2019.xlsx") is None

    def test_prose_polluted_mention_still_verifies_by_containment(self):
        assert afc.score_file_match(
            "8 machine prices in consolidated price list 2019.xlsx",
            "Consolidated Price List 2019.xlsx",
        ) == afc.MATCH_TIER_CONTAINMENT

    def test_token_tier_is_discovery_only(self):
        assert afc.score_file_match(
            "acme xlsx", "acme_thread.xlsx") == afc.MATCH_TIER_TOKEN

    def test_extension_word_alone_is_not_a_match(self):
        assert afc.score_file_match("prices xlsx", "costs.xlsx") is None

    def test_empty_inputs(self):
        assert afc.score_file_match("", "a.xlsx") is None
        assert afc.score_file_match("a.xlsx", "") is None


# ---------------------------------------------------------------------------
# lookup_file_records with a fake workspace store
# ---------------------------------------------------------------------------

class _FakeTable:
    def __init__(self, rows):
        self._rows = rows

    def to_arrow(self):
        import pyarrow as pa

        columns = {}
        for key in ({k for r in self._rows for k in r} | {"source", "text"}):
            columns[key] = [
                r.get(key) for r in self._rows
            ]
        return pa.table(columns)


class _FakeDB:
    def __init__(self, tables):
        self._tables = tables

    def table_names(self):
        return list(self._tables)

    def open_table(self, name):
        return _FakeTable(self._tables[name])


@pytest.fixture
def fake_store(monkeypatch):
    def _install(rows):
        db = _FakeDB({"documents": rows})
        monkeypatch.setattr(afc, "_resolve_workspace_db", lambda ws: db)
        return db

    return _install


class TestLookupFileRecords:
    ROWS = [
        {"source": "Consolidated Price List 2019.xlsx",
         "text": "Sheet1 R12 | GSL48-16 | 44500 USD"},
        {"source": "Consolidated Price List 2019.xlsx",
         "text": "Sheet1 R13 | U-22 | 8100 USD"},
        {"source": "Q3 Report 2019.xlsx", "text": "quarterly numbers"},
        {"source": "stock.csv", "text": "widgets on hand"},
    ]

    def test_verified_identity_and_matched_source(self, fake_store):
        fake_store(self.ROWS)
        out = afc.lookup_file_records("ws", "Consolidated Price List 2019.xlsx")
        assert out["found"] is True
        assert out["verified"] is True
        assert out["matched_source"] == "Consolidated Price List 2019.xlsx"
        assert out["match_tier"] == afc.MATCH_TIER_EXACT
        assert out["total"] == 2
        assert out["candidates"] == []

    def test_truncated_mention_does_not_verify_or_candidate(self, fake_store):
        fake_store(self.ROWS)
        out = afc.lookup_file_records("ws", "2019.xlsx")
        # Year-only overlap: no identity, no candidates, no preview.
        assert out["found"] is False
        assert out["verified"] is False
        assert out["candidates"] == []

    def test_partial_mention_is_discovery_not_verification(self, fake_store):
        # Containment ("price list.xlsx" inside the full name) only
        # DISCOVERS a candidate — it must not verify identity on its own
        # (the same partial name can sit inside several workbooks).
        fake_store(self.ROWS)
        out = afc.lookup_file_records("ws", "price list.xlsx")
        assert out["found"] is True
        assert out["verified"] is False
        assert out["matched_source"] is None
        assert "Consolidated Price List 2019.xlsx" in out["candidates"]

    def test_duplicate_filenames_are_ambiguous_never_silent_pick(self, fake_store):
        # Two DIFFERENT files can carry the same name in different folders:
        # a name match alone is not identity — ask, don't pick by row count.
        fake_store([
            {"source": "Price List.xlsx", "text": "copy A row"},
            {"source": "price list.xlsx", "text": "copy B row"},
        ])
        out = afc.lookup_file_records("ws", "Price List.xlsx")
        assert out["found"] is True
        assert out["ambiguous"] is True
        assert out["verified"] is False
        assert out["matched_source"] is None

    def test_resource_id_present_marks_identity_verified(self, fake_store):
        fake_store([
            {"source": "Consolidated Price List 2019.xlsx",
             "text": "R12 | GSL48-16",
             "metadata": '{"provider": "zoho_workdrive", '
                         '"external_id": "wd-123"}'},
        ])
        out = afc.lookup_file_records(
            "ws", "Consolidated Price List 2019.xlsx")
        assert out["verified"] is True
        assert out["identity_verified"] is True
        assert out["resource_id"] == "wd-123"
        assert out["provider"] == "zoho_workdrive"

    def test_resource_id_absent_leaves_identity_unverified(self, fake_store):
        # Name-only match without a provider resource ID cannot ground a
        # stable identity (folder/version unknown).
        fake_store([
            {"source": "Consolidated Price List 2019.xlsx",
             "text": "R12 | GSL48-16"},
        ])
        out = afc.lookup_file_records(
            "ws", "Consolidated Price List 2019.xlsx")
        assert out["verified"] is True
        assert out["identity_verified"] is False

    def test_weak_token_match_is_candidate_not_identity(self, fake_store):
        fake_store([{"source": "acme_thread.xlsx", "text": "thread rows"}])
        out = afc.lookup_file_records("ws", "acme xlsx")
        assert out["found"] is True
        assert out["verified"] is False
        assert out["matched_source"] is None
        assert out["candidates"] == ["acme_thread.xlsx"]

    def test_no_store(self, monkeypatch):
        monkeypatch.setattr(afc, "_resolve_workspace_db", lambda ws: None)
        out = afc.lookup_file_records("ws", "anything.xlsx")
        assert out["found"] is False and out["verified"] is False


# ---------------------------------------------------------------------------
# Honest builders
# ---------------------------------------------------------------------------

class TestBuilders:
    def test_verified_block_names_source_and_labels_excerpts(self):
        block = afc.build_file_block("price list.xlsx", {
            "found": True, "verified": True,
            "match_tier": "containment",
            "matched_source": "Consolidated Price List 2019.xlsx",
            "tables": [{"table": "documents", "count": 2,
                        "samples": ["R12 | GSL48-16 | 44500"]}],
            "total": 2, "candidates": [],
        })
        assert "VERIFIED" in block
        assert "Consolidated Price List 2019.xlsx" in block
        assert "cached ingestion EXCERPTS" in block
        assert "verify specific values" in block

    def test_unverified_block_forbids_presenting_candidates(self):
        block = afc.build_file_block("acme xlsx", {
            "found": True, "verified": False, "match_tier": "token",
            "matched_source": None, "tables": [], "total": 1,
            "candidates": ["acme_thread.xlsx"],
        })
        assert "identity NOT confirmed" in block
        assert "acme_thread.xlsx" in block
        assert "do not present" in block.lower()

    def test_not_found_block_lists_similar_candidates(self):
        block = afc.build_file_block("prices 2018.xlsx", {
            "found": False, "verified": False, "tables": [], "total": 0,
            "candidates": ["prices 2019.xlsx"],
        })
        assert "NOT found" in block
        assert "prices 2019.xlsx" in block
        assert "do not present" in block.lower()

    def test_canvas_content_labels_cached_samples(self):
        content = afc.build_file_canvas_content(
            "Consolidated Price List 2019.xlsx",
            {"tables": [{"table": "documents", "count": 2,
                         "samples": ["R12 | GSL48-16"]}],
             "match_tier": "containment"},
            mention="price list.xlsx",
        )
        assert "Consolidated Price List 2019.xlsx" in content
        assert "NOT a fresh read" in content
        assert "price list.xlsx" in content


class TestSpreadsheetMentions:
    def test_spreadsheet_only(self):
        assert afc.spreadsheet_mentions("open price list.xlsx") == [
            "price list.xlsx"]
        assert afc.spreadsheet_mentions("read notes.docx") == []

    def test_incident_ask_counts(self):
        assert afc.spreadsheet_mentions(
            "prices in Consolidated Price List 2019.xlsx")
