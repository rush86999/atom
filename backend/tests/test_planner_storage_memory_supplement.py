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
import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import core.chat_tool_planner as ctp
from core.chat_tool_planner import ToolPlan, _StorageQuery, execute_tool_plan
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


class TestProductTokens:
    def test_identifier_shapes_across_industries(self):
        # The only requirement is mixed letters+digits — the shape catalog
        # codes share across industries and prose/years/amounts never do.
        cases = {
            "check consolidated price list for WG350DSAV price": ["WG350DSAV"],
            "find LM358 in the components catalog": ["LM358"],
            "row for chemical S318500 in the MSDS file": ["S318500"],
            "sku NK-AQ0818 stock check": ["NK-AQ0818"],
            "invoice INV-2024-118 status": ["INV-2024-118"],
            "ALU-400 saw and R6U-6SG2 kit": ["ALU-400", "R6U-6SG2"],
        }
        for text, expected in cases.items():
            assert ctp._product_tokens(text) == expected, text

    def test_non_identifiers_rejected(self):
        # Years, amounts, chunk refs, all-letter words: none qualify.
        assert ctp._product_tokens("price list 2019 total $14,145.00 row 17") == []
        assert ctp._product_tokens("see the attached document") == []

    def test_hexlike_dropped_only_where_marked(self):
        # Canvas HTML styles leak 6-hex tokens ('#1F3864', '#e8590c') —
        # layout noise, dropped for canvas text but kept for user text,
        # since a hex-shaped code can be a real code in someone's catalog.
        assert "1F3864" not in ctp._product_tokens(
            "background 1F3864 e8590c padding", skip_hexlike=True)
        assert "1F3864" in ctp._product_tokens("code 1F3864 lookup")

    def test_min_len_enforced(self):
        # DM10 (4 chars) is too short to be selective; DM-100 passes.
        assert ctp._product_tokens("hydmech DM10 vs DM-100", min_len=6) == ["DM-100"]

    def test_dedupe_by_document_diversity(self, monkeypatch):
        """A code in many files must surface each FILE, not three chunks of
        one — the answer should attribute by source."""
        rows = [
            {"id": "ext_aaa::c10", "text": "part ACME-100 row 1", "metadata": '{"file_name": "One.xlsx"}', "source": "s"},
            {"id": "ext_aaa::c11", "text": "part ACME-100 row 2", "metadata": '{"file_name": "One.xlsx"}', "source": "s"},
            {"id": "ext_bbb::c5", "text": "ACME-100 in stock", "metadata": '{"file_name": "Two.pdf"}', "source": "s"},
        ]

        class _FakeLance:
            def to_table(self, filter=None, columns=None):
                class _T:
                    def to_pylist(self):
                        return rows
                return _T()

        import lancedb

        class _FakeTable:
            def to_lance(self):
                return _FakeLance()

        monkeypatch.setattr(lancedb, "connect",
                            lambda *_a, **_k: type("DB", (), {
                                "open_table": lambda self, n: _FakeTable()})())
        lines = ctp._search_ingested_by_exact_token("u", "ACME-100")
        assert len(lines) == 2
        assert "One.xlsx" in lines[0] and "Two.pdf" in lines[1]

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


class TestStorageQueryRewrite:
    """Query authorship is LLM-owned: the planner's draft query inherits the
    current message's wording and drops identifiers that live in earlier
    turns. A bounded structured rewrite (fed history + canvas) replaces the
    old pattern-scan enrichment; on failure the draft passes through."""

    def _llm(self, rewritten):
        return SimpleNamespace(
            generate_structured_response=AsyncMock(
                return_value=_StorageQuery(query=rewritten)))

    async def test_storage_read_query_rewritten_by_llm(self, mem_block):
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
        ]}
        with patch.object(UniversalIntegrationService, "execute", _exec):
            await execute_tool_plan(
                _plan("zoho_workdrive", intent="read",
                      query="Consolidated Price List"),
                "user-1", context=ctx, llm_service=self._llm(
                    "Consolidated Price List WG350DSAV"))
        assert "WG350DSAV" in captured["query"]

    async def test_storage_query_passthrough_without_llm(self, mem_block):
        captured = {}

        async def _exec(self, service, action, params, context=None):
            captured["query"] = params.get("query")
            return {"status": "success",
                    "data": {"found": False, "message": "no file"}}

        with patch.object(UniversalIntegrationService, "execute", _exec):
            await execute_tool_plan(
                _plan("zoho_workdrive", intent="read",
                      query="Consolidated Price List"),
                "user-1")
        assert captured["query"] == "Consolidated Price List"

    async def test_rewrite_failure_keeps_draft_query(self, mem_block):
        captured = {}

        async def _exec(self, service, action, params, context=None):
            captured["query"] = params.get("query")
            return {"status": "success",
                    "data": {"found": False, "message": "no file"}}

        llm = SimpleNamespace(
            generate_structured_response=AsyncMock(side_effect=RuntimeError("down")))
        with patch.object(UniversalIntegrationService, "execute", _exec):
            await execute_tool_plan(
                _plan("zoho_workdrive", intent="read",
                      query="Consolidated Price List"),
                "user-1", llm_service=llm)
        assert captured["query"] == "Consolidated Price List"

    async def test_non_storage_query_not_rewritten(self, mem_block):
        captured = {}

        async def _search(self, service, query, context=None):
            captured["query"] = query
            return {"status": "success", "data": [{"name": "acme"}]}

        ctx = {"history": [
            {"role": "user", "content": "WG350DSAV bandsaw"},
        ]}
        with patch.object(UniversalIntegrationService, "search", _search):
            await execute_tool_plan(
                _plan("zoho_crm", query="acme leads"), "user-1", context=ctx,
                llm_service=self._llm("SHOULD NOT APPEAR"))
        assert captured["query"] == "acme leads"


class TestWorkdriveReadResolution:
    """_read_storage_file resolves a no-file_id read by running the
    service's own search. ZohoWorkDriveService.search_files returns a PLAIN
    LIST of records, but the resolver unwrapped a dict envelope — hits were
    always [], so every planner-initiated workdrive read returned
    found:False while the file sat on the drive (live 2026-09-04,
    'Consolidated Price List': the read leg ran 16s and answered "no file
    matched"). Both accepted shapes pinned here."""

    def _svc(self):
        return UniversalIntegrationService(workspace_id="default")

    def _storage_stub(self, search_result):
        return SimpleNamespace(
            search_files=AsyncMock(return_value=search_result),
            download_file=AsyncMock(return_value=b"xlsx-bytes"),
        )

    def _ingest_and_parse_patches(self, parsed_text):
        return [
            patch("core.auto_document_ingestion.DocumentParser.parse_document",
                  AsyncMock(return_value=parsed_text)),
            patch("core.auto_document_ingestion.AutoDocumentIngestionService",
                  SimpleNamespace(process_file_bytes=AsyncMock(
                      return_value={"status": "ingested"}))),
        ]

    async def _read(self, storage_stub, query="Consolidated Price List WG350DSAV"):
        svc = self._svc()
        with contextlib.ExitStack() as stack:
            for p in self._ingest_and_parse_patches(
                    "R17 | WG350DSAV | Bandsaw | 14145"):
                stack.enter_context(p)
            return await svc._read_storage_file(
                "zoho_workdrive", storage_stub, None,
                {"query": query}, {"user_id": "u1"})

    async def test_list_shaped_search_resolves_the_file(self):
        stub = self._storage_stub([
            {"id": "wb-1", "name": "Consolidated Price List 2019.xlsx"},
        ])
        result = await self._read(stub)
        stub.search_files.assert_awaited_once()
        assert result["data"]["found"] is True
        assert result["data"]["file_name"] == "Consolidated Price List 2019.xlsx"
        assert "WG350DSAV" in result["data"]["excerpt"]

    async def test_dict_envelope_still_accepted(self):
        # Tolerance for a future wrapped return shape.
        stub = self._storage_stub(
            {"data": {"files": [{"id": "wb-1", "name": "price.xlsx"}]}})
        result = await self._read(stub)
        assert result["data"]["found"] is True

    async def test_best_name_match_wins_over_other_hits(self):
        stub = self._storage_stub([
            {"id": "misc", "name": "Meeting Notes.xlsx"},
            {"id": "wb-1", "name": "Consolidated Price List 2019.xlsx"},
        ])
        result = await self._read(stub)
        assert result["data"]["file_id"] == "wb-1"


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
