# -*- coding: utf-8 -*-
"""Storage/mail evidence dead-ends supplemented with the ingested copy.

Bug class this closes (live 2026-09-04, Consolidated Price List 2019.xlsx):
a tool search that SUCCEEDS with file RECORDS is not a content answer — the
model reads metadata-only evidence and replies "I found the file but can't
read its contents" while the row sat fully extracted in the ingested copy.
Two second-source supplements (the pattern the outlook branch already used
for mailbox copies):

- storage search success / read fall-through → evidence carries the
  ingested-workspace block alongside the metadata;
- outlook empty search → full ingested-workspace block instead of a dead
  end (the Sep 3 misroute had the verify panel strip true claims because
  the evidence set never contained the row).
"""
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

import core.chat_tool_planner as ctp
from core.chat_tool_planner import ToolPlan, execute_tool_plan
from integrations.universal_integration_service import UniversalIntegrationService


def _storage_search_result(names):
    return {"status": "success",
            "data": {"data": {"files": [{"name": n} for n in names]}}}


def _plan(service, intent="search", query="Consolidated Price List WG350DSAV"):
    return ToolPlan(use_tool=True, service=service, intent=intent, query=query)


@pytest.fixture
def mem_block(monkeypatch):
    """Stands in for the ingested-copy search; set .return_value to None to
    simulate 'nothing ingested matches'."""
    mock = AsyncMock(return_value=(
        "LIVE TOOL RESULTS (memory.search, query='q') — ingested workspace\n"
        "- [document: Consolidated Price List 2019.xlsx — ingested 2026-09-01] "
        "R17 | WG350DSAV | Bandsaw | 14145"
    ))
    monkeypatch.setattr(ctp, "_memory_search_block", mock)
    return mock


class TestStorageMetadataSupplement:
    async def test_storage_search_gain_ingested_copy(self, mem_block):
        with patch.object(UniversalIntegrationService, "search",
                          AsyncMock(return_value=_storage_search_result(
                              ["Consolidated Price List 2019.xlsx"]))) as s:
            block = await execute_tool_plan(_plan("zoho_workdrive"), "user-1")
        s.assert_awaited_once()
        mem_block.assert_awaited_once()
        assert "METADATA only" in block
        assert "INGESTED COPY" in block
        assert "WG350DSAV" in block

    async def test_storage_search_without_ingested_copy_stays_metadata(self, mem_block):
        mem_block.return_value = None
        with patch.object(UniversalIntegrationService, "search",
                          AsyncMock(return_value=_storage_search_result(
                              ["Unrelated.docx"]))):
            block = await execute_tool_plan(_plan("zoho_workdrive"), "user-1")
        mem_block.assert_awaited_once()
        assert "Unrelated.docx" in block
        assert "INGESTED COPY" not in block

    async def test_failed_read_falls_back_to_ingested_copy(self, mem_block):
        # Explicit open (intent=read) whose download/extraction failed used
        # to dead-end on the failure envelope — same metadata-only class.
        with patch.object(UniversalIntegrationService, "execute",
                          AsyncMock(return_value={"status": "success",
                                                  "data": {"found": False,
                                                           "message": "download failed"}})):
            block = await execute_tool_plan(_plan("zoho_workdrive", intent="read"), "user-1")
        mem_block.assert_awaited_once()
        assert "INGESTED COPY" in block
        assert "WG350DSAV" in block

    async def test_successful_read_skips_supplement(self, mem_block):
        # A real open returns content inside the read_file branch and must
        # NOT double-query memory.
        with patch.object(UniversalIntegrationService, "execute",
                          AsyncMock(return_value={"status": "success",
                                                  "data": {"found": True,
                                                           "file_name": "p.xlsx",
                                                           "chars_extracted": 10,
                                                           "excerpt": "R17 | WG350DSAV | 14145",
                                                           "ingested_into_workspace": True,
                                                           "note": ""}})):
            block = await execute_tool_plan(_plan("zoho_workdrive", intent="read"), "user-1")
        mem_block.assert_not_awaited()
        assert "FILE OPENED" in block


class TestExactTokenLookup:
    def test_product_token_pattern(self):
        # Model numbers / SKUs are mixed letters+digits; years and chunk ids
        # are not — a containment scan on those would be pure noise.
        assert ctp._PRODUCT_TOKEN_RE.findall(
            "check consolidated price list for WG350DSAV price"
        ) == ["WG350DSAV"]
        assert "ALU-400" in ctp._PRODUCT_TOKEN_RE.findall("ALU-400 saw")
        assert ctp._PRODUCT_TOKEN_RE.findall("price list 2019") == []
        assert ctp._PRODUCT_TOKEN_RE.findall("row 17 of the file") == []

    def test_exact_token_match_against_real_store(self):
        """Integration leg (skips without the local store): the live
        2026-09-04 incident — the row lives in chunk c2213 of 3,797 and
        vector search never surfaces it."""
        try:
            import lancedb

            base = Path(__file__).resolve().parent.parent / "data" / "atom_memory"
            lance = (lancedb.connect(str(base / "default"))
                     .open_table("documents").to_lance())
            probe = lance.to_table(
                filter="text LIKE '%WG350DSAV%'", columns=["id"]
            )
            if probe.num_rows == 0:
                pytest.skip("workbook not ingested on this machine")
            hit_ids = {str(r) for r in probe.column("id").to_pylist()}
        except Exception:
            pytest.skip("local lancedb store unavailable")
        lines = ctp._search_ingested_by_exact_token(
            "user-1", "Consolidated Price List WG350DSAV")
        assert lines and "WG350DSAV" in lines[0]
        assert "14145" in lines[0]
        assert "Consolidated Price List 2019.xlsx" in lines[0]
        # skip_ids mirrors the hybrid-hit dedupe: chunks the hybrid already
        # surfaced must not produce duplicate lines.
        deduped = ctp._search_ingested_by_exact_token(
            "user-1", "Consolidated Price List WG350DSAV",
            skip_ids=hit_ids)
        assert all("14145" not in ln or "EXACT MATCH" not in ln
                   for ln in deduped)


class TestContextTokenEnrichment:
    async def test_storage_read_query_gains_model_token_from_history(self, mem_block):
        """Live 2026-09-04: the user message ('check the price list file …
        find the row') carries no model number — only the history does. The
        read excerpt anchored on boilerplate for three consecutive turns."""
        captured = {}

        async def _exec(self, service, action, params, context=None):
            captured["query"] = params.get("query")
            return {"status": "success",
                    "data": {"found": True, "file_name": "p.xlsx",
                             "chars_extracted": 5, "excerpt": "x",
                             "ingested_into_workspace": True, "note": ""}}

        ctx = {"history": [
            {"role": "user",
             "content": "my file shows WG350DSAV Bandsaw 230V $14,145.00"},
            {"role": "assistant", "content": "checked"},
        ]}
        with patch.object(UniversalIntegrationService, "execute", _exec):
            await execute_tool_plan(
                _plan("zoho_workdrive", intent="read",
                      query="Consolidated Price List"),
                "user-1", context=ctx)
        assert "WG350DSAV" in captured["query"]

    async def test_non_storage_query_not_enriched(self, mem_block):
        captured = {}

        async def _search(self, service, query, context=None):
            captured["query"] = query
            return {"status": "success", "data": [{"name": "acme"}]}

        ctx = {"history": [
            {"role": "user", "content": "WG350DSAV bandsaw"},
        ]}
        with patch.object(UniversalIntegrationService, "search", _search):
            await execute_tool_plan(
                _plan("zoho_crm", query="acme leads"), "user-1", context=ctx)
        assert captured["query"] == "acme leads"


class TestQueryAnchoredExcerpt:
    def test_rare_token_beats_boilerplate_coverage(self):
        """Live 2026-09-04 shape: the identifying model number sits deep in
        a numeric row region; 'consolidated price list' boilerplate occurs
        throughout the head. Coverage scoring picked the head; the rarest-
        token anchor must land on the model row."""
        from integrations.universal_integration_service import (
            _query_anchored_excerpt,
        )

        boiler = "consolidated price list sheet header boilerplate "
        text = (
            boiler * 200                      # head: boilerplate-heavy
            + "R14 | ALU-400 | saw | 8157 | 0.37 | 2.46\n"
            + "R16 | WV-310DSV-5 | saw | 11805 | 0.37 | 2.55\n"
            + "R17 | WG350DSAV | Bandsaw 230V/3PH Linmac 10.5 | 14145\n"
            + "R18 | Lathes | 0\n"
            + boiler * 200                    # tail: more boilerplate
        )
        excerpt = _query_anchored_excerpt(
            text, "Consolidated Price List WG350DSAV")
        assert "WG350DSAV" in excerpt
        assert "14145" in excerpt

    def test_frequent_token_falls_back_to_coverage(self):
        from integrations.universal_integration_service import (
            _query_anchored_excerpt,
        )

        # No rare anchor (every token >50 hits) — coverage scoring decides;
        # the all-token window must win.
        text = ("alpha beta " * 100
                + "alpha beta gamma " * 100
                + "alpha beta " * 100)
        excerpt = _query_anchored_excerpt(text, "alpha beta gamma")
        assert "gamma" in excerpt


class TestOutlookEmptyFallback:
    async def test_outlook_empty_returns_ingested_matches(self, mem_block):
        with patch("integrations.outlook_service.outlook_service.search_emails",
                   AsyncMock(return_value=[])), \
             patch("core.hybrid_search.documents_hybrid.DocumentsHybridSearch.search",
                   AsyncMock(return_value={"results": []})):
            block = await execute_tool_plan(_plan("outlook"), "user-1")
        mem_block.assert_awaited_once()
        assert "no matching messages in the mailbox" in block
        assert "Ingested-workspace matches" in block
        assert "WG350DSAV" in block

    async def test_outlook_empty_without_memory_keeps_dead_end(self, mem_block):
        mem_block.return_value = None
        with patch("integrations.outlook_service.outlook_service.search_emails",
                   AsyncMock(return_value=[])), \
             patch("core.hybrid_search.documents_hybrid.DocumentsHybridSearch.search",
                   AsyncMock(return_value={"results": []})):
            block = await execute_tool_plan(_plan("outlook"), "user-1")
        assert "no matching messages in the mailbox or ingested memory" in block
