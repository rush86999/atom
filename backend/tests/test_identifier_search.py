# -*- coding: utf-8 -*-
"""Identifier-tolerant search primitives (core.identifier_search).

The generalization of the 2026-09-04 WG-350DSAV fix: one implementation of
model-code normalization, ranked client-side filtering, and the bounded
provider-search ladder that every integration family reuses instead of
per-service copies. All mocked — zero network, zero DB.
"""
import pytest

from core.identifier_search import (
    filter_by_terms,
    identifier_rank,
    identifier_variants,
    normalize_code,
    query_terms,
    rank_records,
    record_score,
    run_search_ladder,
)


class TestIdentifierShapes:
    def test_normalize_strips_separators_and_case(self):
        assert normalize_code("WG-350DSAV") == "wg350dsav"
        assert normalize_code("wg 350 dsav") == "wg350dsav"
        assert normalize_code(None) == ""
        assert normalize_code(14145) == "14145"

    def test_variants_strip_alpha_prefix(self):
        # The price-book spelling 'WG350DSAV' never matches the hyphenated
        # Zoho name 'WG-350DSAV' as a token; '350DSAV' is a substring of it.
        assert identifier_variants("wg350dsav") == ["350dsav"]
        assert identifier_variants("WG350DSAV") == ["350DSAV"]

    def test_variants_skip_non_identifier_tokens(self):
        assert identifier_variants("Linmac") == []      # no digit boundary
        assert identifier_variants("350") == []          # variant < 4 chars
        assert identifier_variants("350DSAV") == []      # already starts with digit
        assert identifier_variants("") == []

    def test_rank_orders_identifier_tokens_before_prose(self):
        ranked = sorted(["Linmac", "350DSAV", "saw", "WG350"], key=identifier_rank)
        # letters+digits first, longest first; prose words last
        assert ranked[0] in ("350DSAV", "WG350")
        assert ranked[-1] in ("Linmac", "saw")

    def test_query_terms_identifier_first(self):
        terms = query_terms("Linmac WG-350DSAV is the bandsaw in stock")
        assert terms[0] == "350DSAV"
        assert "Linmac" in terms and "stock" in terms
        assert "is" not in terms and "WG" not in terms  # <3 chars dropped


class TestRecordScoring:
    def test_skeleton_exact_beats_contains(self):
        query_norm, terms = "wg350dsav", ["350dsav", "wg350dsav"]
        assert record_score("WG-350DSAV", query_norm, terms) == 3
        assert record_score("WG-350DSAV-5", query_norm, terms) == 2
        assert record_score("Bandsaw blade", query_norm, terms) == 0

    def test_short_terms_need_equality_not_substring(self):
        # '350' as a substring would match half a catalog; only equality.
        assert record_score("WG-350DSAV", "350", ["350"]) == 0
        assert record_score("350", "350", ["350"]) == 3


class TestFilterByTerms:
    def test_any_term_matches_and_weight_ranks_identifier_first(self):
        records = [
            {"name": "saw blade 10in"},                # matches neither term
            {"name": "WG-350DSAV bandsaw in stock"},   # matches bandsaw + wg-350dsav
            {"name": "bandsaw accessory kit"},         # matches bandsaw only
        ]
        out = filter_by_terms(
            records, "bandsaw WG-350DSAV", text_of=lambda r: r["name"])
        # the record carrying BOTH terms outranks the single-term match;
        # the no-match record is dropped
        assert out[0]["name"] == "WG-350DSAV bandsaw in stock"
        assert out[1]["name"] == "bandsaw accessory kit"
        assert len(out) == 2

    def test_recency_order_preserved_for_ties(self):
        records = [{"id": 1, "n": "alpha"}, {"id": 2, "n": "alpha too"}]
        out = filter_by_terms(records, "alpha", text_of=lambda r: r["n"])
        assert [r["id"] for r in out] == [1, 2]

    def test_limit_cut(self):
        records = [{"n": f"item {i} widget"} for i in range(20)]
        out = filter_by_terms(records, "widget", text_of=lambda r: r["n"], limit=3)
        assert len(out) == 3

    def test_short_query_falls_back_to_whole_query(self):
        records = [{"n": "wg saw"}]
        assert filter_by_terms(records, "wg saw", text_of=lambda r: r["n"]) == records
        assert filter_by_terms(records, "zz", text_of=lambda r: r["n"]) == []
        assert filter_by_terms(records, "", text_of=lambda r: r["n"]) == []

    def test_default_text_of_is_str(self):
        assert filter_by_terms(["BANDSAW pro", "drill"], "bandsaw") == ["BANDSAW pro"]


class TestRankRecords:
    def test_exact_name_first_regardless_of_input_order(self):
        records = ["WG-350DSAV-1", "WG-350DSAV", "drill"]
        out = rank_records(records, "wg-350dsav", name_of=lambda r: r)
        assert out[0] == "WG-350DSAV"


class TestSearchLadder:
    async def test_full_query_text_hit_stops_after_one_call(self):
        calls = []

        async def fetch(kind, value):
            calls.append((kind, value))
            return [{"name": "WG-350DSAV", "stock": 1}]

        out = await run_search_ladder(fetch, "wg-350dsav", name_of=lambda r: r["name"])
        assert calls == [("text", "wg-350dsav")]
        assert out[0]["name"] == "WG-350DSAV"

    async def test_multiword_query_recovered_via_token_attempts(self):
        async def fetch(kind, value):
            if value == "350DSAV" and kind == "name":
                return [{"name": "WG-350DSAV", "stock": 1}]
            return []

        out = await run_search_ladder(fetch, "Linmac WG-350DSAV", name_of=lambda r: r["name"])
        assert [r["name"] for r in out] == ["WG-350DSAV"]

    async def test_hyphenless_spelling_recovered_via_variant(self):
        calls = []

        async def fetch(kind, value):
            calls.append((kind, value))
            if (kind, value) == ("name", "350dsav"):
                return [{"name": "WG-350DSAV", "stock": 1}]
            return []

        out = await run_search_ladder(fetch, "wg350dsav", name_of=lambda r: r["name"])
        assert [r["name"] for r in out] == ["WG-350DSAV"]
        assert calls[0] == ("text", "wg350dsav")   # full-text first
        assert ("name", "350dsav") in calls

    async def test_ranks_exact_above_variants_when_ladder_widens(self):
        async def fetch(kind, value):
            return [
                {"name": "WG-350DSAV-1", "stock": 0},
                {"name": "WG-350DSAV", "stock": 1},
                {"name": "part saw"},
            ]

        out = await run_search_ladder(fetch, "wg350dsav", name_of=lambda r: r["name"])
        assert out[0]["name"] == "WG-350DSAV"
        assert out[0]["stock"] == 1

    async def test_first_attempt_failure_fails_fast(self):
        calls = []

        async def fetch(kind, value):
            calls.append((kind, value))
            raise ConnectionError("provider down")

        with pytest.raises(ConnectionError):
            await run_search_ladder(fetch, "wg-350dsav", name_of=lambda r: r["name"])
        assert calls == [("text", "wg-350dsav")]

    async def test_later_attempt_errors_skipped(self):
        # The FIRST attempt must succeed (fail-fast applies only to it);
        # the full-query name attempt errors, the variant attempt recovers.
        async def fetch(kind, value):
            if (kind, value) == ("name", "wg350dsav"):
                raise RuntimeError("name endpoint flaky")
            if (kind, value) == ("name", "350dsav"):
                return [{"name": "WG-350DSAV", "stock": 1}]
            return []

        out = await run_search_ladder(fetch, "wg350dsav", name_of=lambda r: r["name"])
        assert [r["name"] for r in out] == ["WG-350DSAV"]

    async def test_call_cap(self):
        calls = []

        async def fetch(kind, value):
            calls.append((kind, value))
            return [{"name": f"part {value}"}]

        await run_search_ladder(fetch, "Linmac WG-350DSAV bandsaw",
                                name_of=lambda r: r["name"], max_calls=3)
        assert len(calls) == 3

    async def test_empty_query_and_limit(self):
        async def fetch(kind, value):
            return [{"name": "x"}]

        assert await run_search_ladder(fetch, "", name_of=lambda r: r["name"]) == []
        out = await run_search_ladder(fetch, "wg-350dsav",
                                      name_of=lambda r: r["name"], limit=1)
        assert len(out) == 1
