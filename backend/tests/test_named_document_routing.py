# -*- coding: utf-8 -*-
"""Named-document routing regressions (2026-10-25).

The live pilot's exact named-request smoke failed because a ``.txt``
mention entered the spreadsheet/dataset reader and its dataset-catalog miss
was rendered as "document absent". These tests pin the corrected capability
precedence:

- explicit document extension outranks workbook wording (``price list.txt``);
- non-spreadsheet mentions never enter the dataset lane;
- extensionless names are resolved against both workspace-scoped catalogs;
- duplicates are ambiguous, no-match is unresolved (not absent), and every
  requested source is preserved in mixed asks.
"""
import os
import sys
import types
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest

from core.agent_file_context import (
    explicit_file_kind,
    is_spreadsheet_task_mention,
)
import core.named_file_resolution as nfr

SMOKE = "release_smoke_record_55b13cd2f.txt"
APPROVED = "approved_records_q2026_114.txt"
WORKBOOK = "Consolidated Price List 2019.xlsx"


def test_explicit_document_extension_outranks_price_list_words():
    assert explicit_file_kind("price list.txt") == "document"
    assert is_spreadsheet_task_mention("price list.txt") is False
    assert is_spreadsheet_task_mention("price list") is True
    assert explicit_file_kind(WORKBOOK) == "spreadsheet"
    assert is_spreadsheet_task_mention(WORKBOOK) is True


def test_smoke_filename_is_a_document_not_a_dataset():
    assert explicit_file_kind(SMOKE) == "document"
    assert is_spreadsheet_task_mention(SMOKE) is False


@pytest.mark.asyncio
async def test_dataset_lane_returns_none_for_document_mention():
    from core.chat_tool_planner import _datasets_named_file_block

    plan = types.SimpleNamespace(_result_meta={})
    with (
        patch("core.sheet_dataset_service.sheet_datasets_enabled",
              return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync") as find_entries,
    ):
        block = await _datasets_named_file_block(
            "u1",
            f"search my uploaded documents for the code in {SMOKE}",
            {"workspace_id": "ws", "message": f"read {SMOKE}"},
            plan=plan,
        )
    assert block is None
    find_entries.assert_not_called()
    scope = plan._result_meta["named_file_scope"]
    assert scope["reader"] == "documents"
    assert SMOKE in " ".join(scope["mentions"])


@pytest.mark.asyncio
async def test_dataset_lane_preserves_mixed_sources_and_selects_none():
    from core.chat_tool_planner import _datasets_named_file_block

    plan = types.SimpleNamespace(_result_meta={})
    msg = f"compare {SMOKE} with {WORKBOOK}"
    with (
        patch("core.sheet_dataset_service.sheet_datasets_enabled",
              return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync") as find_entries,
    ):
        block = await _datasets_named_file_block(
            "u1", msg, {"workspace_id": "ws", "message": msg}, plan=plan
        )
    assert block is None, "a mixed ask must not be answered from one source"
    find_entries.assert_not_called()
    scope = plan._result_meta["named_file_scope"]
    assert scope["reader"] == "mixed"
    joined = " ".join(scope["mentions"])
    assert SMOKE in joined and "consolidated price list 2019.xlsx" in joined


def _doc(file_id, name, workspace="ws"):
    return {
        "file_id": file_id,
        "file_name": name,
        "title": None,
        "workspace_id": workspace,
        "file_type": name.rsplit(".", 1)[-1],
    }


def _dataset(external_id, name):
    return {
        "source": "catalog",
        "external_id": external_id,
        "file_name": name,
        "parquet_path": "/tmp/x.parquet",
    }


def test_exact_smoke_name_resolves_through_document_catalog(monkeypatch):
    monkeypatch.setattr(nfr, "_document_rows", lambda ws: [_doc("doc-1", SMOKE)])
    monkeypatch.setattr(nfr, "_dataset_rows", lambda u, ws: [])
    intent = nfr.resolve_named_file_intent(
        f"search my uploaded documents for the code in {SMOKE}",
        "u1", "ws",
    )
    assert intent["reader"] == "documents"
    assert intent["state"] == "resolved"
    assert intent["sources"][0]["document"]["file_id"] == "doc-1"
    assert intent["sources"][0]["document"]["file_name"] == SMOKE


def test_duplicate_titles_are_ambiguous_never_first_pick(monkeypatch):
    monkeypatch.setattr(nfr, "_document_rows", lambda ws: [
        _doc("doc-1", SMOKE), _doc("doc-2", SMOKE),
    ])
    monkeypatch.setattr(nfr, "_dataset_rows", lambda u, ws: [])
    intent = nfr.resolve_named_file_intent(f"read {SMOKE}", "u1", "ws")
    assert intent["reader"] == "documents"
    assert intent["state"] == "ambiguous"
    names = [c["file_id"] for c in intent["sources"][0]["candidates"]]
    assert names == ["doc-1", "doc-2"]


def test_no_match_is_unresolved_not_absent(monkeypatch):
    monkeypatch.setattr(nfr, "_document_rows", lambda ws: [])
    monkeypatch.setattr(nfr, "_dataset_rows", lambda u, ws: [])
    intent = nfr.resolve_named_file_intent(f"read {SMOKE}", "u1", "ws")
    assert intent["state"] == "unresolved"
    # An explicit document stays a document request; the catalog has no
    # identity for it, but that is not a claim that no document exists.
    assert intent["reader"] == "documents"
    assert intent["sources"][0]["state"] == "unresolved"
    assert intent["sources"][0]["document"]["candidates"] == []


def test_document_catalog_is_workspace_scoped(monkeypatch):
    seen = []

    def rows(ws):
        seen.append(ws)
        return [_doc("doc-1", SMOKE, workspace="ws")] if ws == "ws" else []

    monkeypatch.setattr(nfr, "_document_rows", rows)
    monkeypatch.setattr(nfr, "_dataset_rows", lambda u, ws: [])
    other = nfr.resolve_named_file_intent(f"read {SMOKE}", "u1", "ws-other")
    assert seen == ["ws-other"]
    assert other["sources"][0]["state"] == "unresolved"
    # The row from ws is not visible in ws-other.
    assert other["sources"][0]["document"]["candidates"] == []


def test_extensionless_document_resolves_before_reader_choice(monkeypatch):
    monkeypatch.setattr(nfr, "_document_rows", lambda ws: [
        _doc("doc-1", SMOKE),
    ])
    monkeypatch.setattr(nfr, "_dataset_rows", lambda u, ws: [])
    intent = nfr.resolve_named_file_intent(
        "read the release smoke record",
        "u1", "ws",
        pinned_mention="release smoke record",
    )
    # The phrase is a containment match for the catalog name (the name
    # carries an additional release id), so identity is clarified rather
    # than silently verified. The reader is still the document catalog.
    assert intent["reader"] == "documents"
    assert intent["state"] == "ambiguous"


def test_mixed_ask_preserves_both_sources(monkeypatch):
    monkeypatch.setattr(nfr, "_document_rows", lambda ws: [
        _doc("doc-1", SMOKE),
    ])
    monkeypatch.setattr(nfr, "_dataset_rows", lambda u, ws: [
        _dataset("wb-1", WORKBOOK),
    ])
    intent = nfr.resolve_named_file_intent(
        f"compare {SMOKE} with {WORKBOOK}",
        "u1", "ws",
    )
    assert intent["reader"] == "mixed"
    names = []
    for source in intent["sources"]:
        if source.get("document"):
            names.append(source["document"].get("file_name"))
        if source.get("dataset"):
            names.append(source["dataset"].get("file_name"))
    assert SMOKE in names and WORKBOOK in names


def test_ordinary_workbook_still_routes_to_datasets(monkeypatch):
    monkeypatch.setattr(nfr, "_document_rows", lambda ws: [])
    monkeypatch.setattr(nfr, "_dataset_rows", lambda u, ws: [
        _dataset("wb-1", WORKBOOK),
    ])
    intent = nfr.resolve_named_file_intent(
        f"find the price in {WORKBOOK}", "u1", "ws"
    )
    assert intent["reader"] == "datasets"
    assert intent["state"] == "resolved"
    assert intent["sources"][0]["dataset"]["file_id"] == "catalog|wb-1"


def test_containment_only_is_ambiguous_not_verified(monkeypatch):
    monkeypatch.setattr(nfr, "_document_rows", lambda ws: [
        _doc("doc-1", "Old Price List Backup.txt"),
    ])
    monkeypatch.setattr(nfr, "_dataset_rows", lambda u, ws: [])
    intent = nfr.resolve_named_file_intent(
        "read the price list", "u1", "ws", pinned_mention="price list"
    )
    assert intent["reader"] == "documents"
    assert intent["state"] == "ambiguous"
    assert intent["sources"][0]["document"]["match_tier"] == "containment"


def test_pinned_source_is_added_to_detected_sources(monkeypatch):
    monkeypatch.setattr(nfr, "_document_rows", lambda ws: [
        _doc("doc-1", SMOKE),
    ])
    monkeypatch.setattr(nfr, "_dataset_rows", lambda u, ws: [
        _dataset("wb-1", WORKBOOK),
    ])
    intent = nfr.resolve_named_file_intent(
        f"compare {SMOKE} with the consolidated price list 2019 workbook",
        "u1", "ws",
        pinned_mention="consolidated price list 2019.xlsx",
    )
    assert intent["reader"] == "mixed"
    names = []
    for source in intent["sources"]:
        if source.get("document"):
            names.append(source["document"].get("file_name"))
        if source.get("dataset"):
            names.append(source["dataset"].get("file_name"))
    assert SMOKE in names and WORKBOOK in names


def test_single_workbook_in_both_catalogs_is_one_dataset_source(monkeypatch):
    name = "Q3 financials.xlsx"
    monkeypatch.setattr(nfr, "_document_rows", lambda ws: [
        _doc("doc-1", name),
    ])
    monkeypatch.setattr(nfr, "_dataset_rows", lambda u, ws: [
        _dataset("wb-1", name),
    ])
    intent = nfr.resolve_named_file_intent(
        "read Q3 financials", "u1", "ws",
        pinned_mention="Q3 financials",
    )
    assert intent["reader"] == "datasets"
    assert intent["state"] == "resolved"
    assert intent["sources"][0]["dataset"]["file_name"] == name


def test_catalog_failure_is_not_a_no_match(monkeypatch):
    def boom(ws):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(nfr, "_document_rows", boom)
    monkeypatch.setattr(nfr, "_dataset_rows", lambda u, ws: [])
    intent = nfr.resolve_named_file_intent(f"read {SMOKE}", "u1", "ws")
    assert intent["state"] == "catalog_unavailable"
    assert intent["sources"][0]["document"]["state"] == "catalog_unavailable"


@pytest.mark.asyncio
async def test_extensionless_workbook_reaches_dataset_catalog(monkeypatch):
    from core.chat_tool_planner import _datasets_named_file_block

    intent = {
        "reader": "datasets",
        "state": "resolved",
        "mentions": ["q3 financials"],
        "document_mentions": [],
        "dataset_mentions": ["q3 financials"],
        "sources": [{
            "mention": "q3 financials",
            "reader": "datasets",
            "state": "resolved",
            "dataset": {
                "file_id": "catalog|wb-1",
                "file_name": "Q3 financials.xlsx",
            },
        }],
    }
    plan = types.SimpleNamespace(_result_meta={})
    with (
        patch(
            "core.named_file_resolution.resolve_named_file_intent",
            return_value=intent,
        ),
        patch(
            "core.sheet_dataset_service.sheet_datasets_enabled",
            return_value=True,
        ),
        patch(
            "core.sheet_dataset_service.find_entries_sync",
            return_value=[],
        ) as find_entries,
    ):
        await _datasets_named_file_block(
            "u1",
            "read Q3 financials",
            {"workspace_id": "ws",
             "named_file_mention": "q3 financials"},
            plan=plan,
        )
    find_entries.assert_called()


@pytest.mark.asyncio
async def test_named_document_read_rejects_unverified_top_hit(monkeypatch):
    from core.action_registry import action_registry
    import integrations.chat_orchestrator as chat

    async def fake_execute(name, args, context):
        return {
            "success": True,
            "results": [{
                "id": "other-doc",
                "title": "Unrelated File.txt",
                "content": "CONTENT FROM ANOTHER FILE",
            }],
        }

    monkeypatch.setattr(action_registry, "execute_action", fake_execute)
    orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
    intent = {
        "reader": "documents",
        "state": "resolved",
        "sources": [{
            "mention": SMOKE,
            "reader": "documents",
            "state": "resolved",
            "document": {"file_id": "doc-1", "file_name": SMOKE},
        }],
    }
    res = await orch._direct_named_document_read(intent, "u1", "ws")
    assert "no VERIFIED hit" in res["rendered_answer"]
    assert "CONTENT FROM ANOTHER FILE" not in res["rendered_answer"]
    assert res["identity"] == {}


@pytest.mark.asyncio
async def test_named_document_read_marks_long_content_as_excerpt(monkeypatch):
    from core.action_registry import action_registry
    import integrations.chat_orchestrator as chat

    async def fake_execute(name, args, context):
        return {
            "success": True,
            "results": [{
                "id": "doc-1",
                "title": SMOKE,
                "content": "C" * 5000,
            }],
        }

    monkeypatch.setattr(action_registry, "execute_action", fake_execute)
    orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
    intent = {
        "reader": "documents",
        "state": "resolved",
        "sources": [{
            "mention": SMOKE,
            "reader": "documents",
            "state": "resolved",
            "document": {"file_id": "doc-1", "file_name": SMOKE},
        }],
    }
    res = await orch._direct_named_document_read(intent, "u1", "ws")
    assert "matching excerpt" in res["rendered_answer"]
    assert res["coverage_complete"] is False
    assert res["retrieval_complete"] is False
    assert res["meta"]["coverage_limits"]["excerpt"] is True
    assert res["identity"]["file_id"] == "doc-1"


@pytest.mark.asyncio
async def test_named_document_read_ambiguity_publishes_no_identity():
    import integrations.chat_orchestrator as chat

    orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
    intent = {
        "reader": "documents",
        "state": "ambiguous",
        "sources": [{
            "mention": "duplicate_record.txt",
            "reader": "documents",
            "state": "ambiguous",
            "candidates": [
                {"file_id": "doc-1", "file_name": "duplicate_record.txt"},
                {"file_id": "doc-2", "file_name": "duplicate_record.txt"},
            ],
        }],
    }
    res = await orch._direct_named_document_read(intent, "u1", "ws")
    assert "More than one uploaded document" in res["rendered_answer"]
    assert "doc-1" not in res["rendered_answer"]
    assert res["identity"] == {}


@pytest.mark.asyncio
async def test_named_document_read_rejects_same_title_different_id(monkeypatch):
    from core.action_registry import action_registry
    import integrations.chat_orchestrator as chat

    async def fake_execute(name, args, context):
        return {
            "success": True,
            "results": [{
                "id": "other-doc",
                "title": SMOKE,
                "content": "CONTENT FROM A DIFFERENT DOC WITH SAME TITLE",
            }],
        }

    monkeypatch.setattr(action_registry, "execute_action", fake_execute)
    orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
    intent = {
        "reader": "documents",
        "state": "resolved",
        "sources": [{
            "mention": SMOKE,
            "reader": "documents",
            "state": "resolved",
            "document": {"file_id": "doc-1", "file_name": SMOKE},
        }],
    }
    res = await orch._direct_named_document_read(intent, "u1", "ws")
    assert "no VERIFIED hit" in res["rendered_answer"]
    assert "DIFFERENT DOC" not in res["rendered_answer"]
    assert res["identity"] == {}


def test_same_stem_different_kind_is_not_collapsed(monkeypatch):
    monkeypatch.setattr(nfr, "_document_rows", lambda ws: [
        _doc("doc-1", "price list.txt"),
    ])
    monkeypatch.setattr(nfr, "_dataset_rows", lambda u, ws: [
        _dataset("wb-1", "price list.xlsx"),
    ])
    intent = nfr.resolve_named_file_intent(
        "read the price list", "u1", "ws",
        pinned_mention="price list",
    )
    assert intent["reader"] == "mixed"
    assert len(intent["sources"]) == 1
    assert intent["sources"][0]["reader"] == "mixed"


def test_pinned_workbook_survives_detected_document_substring(monkeypatch):
    monkeypatch.setattr(nfr, "_document_rows", lambda ws: [
        _doc("doc-1", "Q3 financials.txt"),
    ])
    monkeypatch.setattr(nfr, "_dataset_rows", lambda u, ws: [
        _dataset("wb-1", "Q3 financials.xlsx"),
    ])
    intent = nfr.resolve_named_file_intent(
        "compare Q3 financials.txt with the summary",
        "u1", "ws",
        pinned_mention="Q3 financials",
    )
    readers = [s["reader"] for s in intent["sources"]]
    assert "documents" in readers
    assert "mixed" in readers
    assert intent["reader"] == "mixed"
    # The pinned source carries both catalog identities; it was not dropped.
    mixed = next(s for s in intent["sources"] if s["reader"] == "mixed")
    assert mixed["document"] and mixed["dataset"]


def test_missing_workspace_is_explicit_not_no_match():
    intent = nfr.resolve_named_file_intent(f"read {SMOKE}", "u1", None)
    assert intent["state"] == "workspace_required"
    assert intent["reader"] == "documents"
    assert intent["sources"][0]["state"] == "workspace_required"
