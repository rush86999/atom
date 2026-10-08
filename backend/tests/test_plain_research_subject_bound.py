"""Plain-research subject-bound lookup: the request's own subjects lead the
catalog probe.

Value-trial follow-up (2026-10-08): the demonstrated miss — the plain
research sweep mined the WHOLE query's tokens, missed the Tennsmith
SLE24-16 row a direct subject probe finds, and answered 'not found'.
Pins: the demonstrated miss, a nonpricing subject, subset scope
(history never contributes subjects), and an honest unmatched result.
"""
from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("TESTING", "1")

from core.chat_tool_planner import _datasets_search_block

UID = "b83eb105-d9e7-41a5-83e3-a632b15b9ee3"

TASK_A_MSG = ("What's the price basis and current lead time for the "
              "Tennsmith SLE24-16 single wheel slitter? Check the price "
              "list workbook and recent vendor correspondence.")


def _plan():
    return SimpleNamespace(_result_meta={})


def _capture():
    captured = {}

    def fake_sync(query, user_id, ws, limit, max_files, context_texts,
                  name_context_texts, deadline=None, request_subjects=None):
        captured["request_subjects"] = request_subjects
        captured["context_texts"] = list(context_texts or [])
        return {"files_searched": 1, "hits": [], "tokens_tried":
                request_subjects or []}

    return captured, fake_sync


def test_demonstrated_miss_now_subject_bound():
    """The exact value-trial-A query probes SLE24-16 (the Tennsmith row a
    direct probe finds), not generic query tokens."""
    captured, fake = _capture()
    with patch("core.sheet_dataset_service.search_all_datasets_sync",
               side_effect=fake), \
            patch("core.sheet_dataset_service.sheet_datasets_enabled",
                  return_value=True):
        asyncio.run(_datasets_search_block(
            UID, TASK_A_MSG,
            {"message": TASK_A_MSG, "history": [], "workspace_id": "default"},
            plan=_plan()))
    subs = captured["request_subjects"] or []
    assert any("sle24" in str(s).lower() for s in subs), (
        f"the request's own subject must lead the probe (got {subs})")


def test_name_claiming_cannot_shadow_subject_probe():
    """The junk-recency trap (live A2): with the FULL research message as
    name context, generic name tokens matched 'zz-formula-e2e-check.xlsx'
    and 'New Vendor Request Form_External.xlsx' and the name branch
    returned them — the subject's content probe never ran. Subject-bound
    probes bypass name-derived file claiming."""
    captured = {}

    def fake_named(files, tok, n):
        return {"file_name": "zz-formula-e2e-check.xlsx", "rows": []}

    import core.sheet_dataset_service as sds
    from unittest.mock import patch as _patch

    real_sync = sds.search_all_datasets_sync

    def spy(query, *a, **k):
        captured["request_subjects"] = k.get("request_subjects")
        return real_sync(query, *a, **k)

    msg = ("What's the price basis and current lead time for the Tennsmith "
           "SLE24-16 single wheel slitter? Check the price list workbook "
           "and recent vendor correspondence.")
    with _patch.object(sds, "search_all_datasets_sync", side_effect=spy), \
            _patch.object(sds, "sheet_datasets_enabled",
                          return_value=True):
        block = asyncio.run(_datasets_search_block(
            UID, msg, {"message": msg, "history": [],
                       "workspace_id": "default"},
            plan=SimpleNamespace(_result_meta={})))
    assert captured.get("request_subjects"), "subjects must reach the sweep"
    assert "zz-formula-e2e-check" not in (block or ""), (
        "junk name-claimed files must not shadow the subject probe")


def test_nonpricing_subject_leads():
    """A nonpricing subject (a machine name, no code) also leads."""
    captured, fake = _capture()
    msg = "check the Manual Flanger price in the workbook"
    with patch("core.sheet_dataset_service.search_all_datasets_sync",
               side_effect=fake), \
            patch("core.sheet_dataset_service.sheet_datasets_enabled",
                  return_value=True):
        asyncio.run(_datasets_search_block(
            UID, msg, {"message": msg, "history": [],
                       "workspace_id": "default"}, plan=_plan()))
    subs = captured["request_subjects"] or []
    assert any("flanger" in str(s).lower() for s in subs), subs


def test_history_never_contributes_subject_candidates():
    """Subset scope: earlier turns' items must not displace this turn's
    subjects (canvas/history may not replace explicit subjects)."""
    captured, fake = _capture()
    history = [{"message": "earlier we priced the TK 1624 Slitter and "
                           "Tin Knocker gang slitter"}]
    with patch("core.sheet_dataset_service.search_all_datasets_sync",
               side_effect=fake), \
            patch("core.sheet_dataset_service.sheet_datasets_enabled",
                  return_value=True):
        asyncio.run(_datasets_search_block(
            UID, TASK_A_MSG,
            {"message": TASK_A_MSG, "history": history,
             "workspace_id": "default"}, plan=_plan()))
    subs = " ".join(str(s).lower() for s in (captured["request_subjects"] or []))
    assert "sle24" in subs
    assert "tin knocker" not in subs and "1624" not in subs, (
        "history items must not ride in as subjects")


def test_honest_unmatched_result():
    """A subject found nowhere still returns the truthful not-found block
    — subject-binding must not fabricate hits."""
    def fake_sync(query, *a, **k):
        return {"files_searched": 5, "hits": [],
                "tokens_tried": k.get("request_subjects") or []}

    with patch("core.sheet_dataset_service.search_all_datasets_sync",
               side_effect=fake_sync), \
            patch("core.sheet_dataset_service.sheet_datasets_enabled",
                  return_value=True):
        block = asyncio.run(_datasets_search_block(
            UID, "price for the zz-notpresent-999 widget",
            {"message": "price for the zz-notpresent-999 widget",
             "history": [], "workspace_id": "default"}, plan=_plan()))
    assert block and "NONE of them" in block, (
        "an unmatched subject keeps the honest scoped-miss block")
