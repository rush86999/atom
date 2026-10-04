"""Round 19 (2026-10-02): the empty re-delivery incident, pinned.

User's live sequence (session replay-retry2-20260923): a read executed
under a mid-rebuild catalog returned 0 targets; that empty structured
result REPLACED the healthy 6-target carrier; "give me the list with a
table show what is confirmed and what is not" and "clarify what you mean
for the other machinery you didn't mention in the previous message" both
rated non-substantive and were re-delivered from the poisoned record —
attribution header + freshness footer, NO body, twice.

Four behaviors pinned here:
1. _adopt_pending_file_result refuses a 0-target downgrade of a healthy
   carrier (the visible reply is unaffected — only the durable carrier).
2. Status/clarification/result-reference asks are NOT delivery retries.
3. A delivery of a degenerate record carries the empty-record honesty
   note instead of silent header+footer.
4. The canvas editor receives the confirmed item→value table
   (_outcome_values_section) so a multi-row price edit is data-driven.
"""

import re
from unittest.mock import MagicMock

import pytest

from integrations.chat_orchestrator import (
    _STATUS_TABLE_ASK_RE,
    _CLARIFY_PREVIOUS_RE,
    _RESULT_REFERENCE_ASK_RE,
    _adopt_pending_file_result,
)


def _carrier(targets: int) -> dict:
    return {
        "status": "delivered",
        "rendered": "full answer body" if targets else "",
        "structured_result": {
            "targets": [
                {"item": f"item-{i}", "identity": {"status": "single",
                                                   "candidates": []}}
                for i in range(targets)
            ],
        },
    }


class TestAdoptDowngradeGuard:
    def test_zero_target_candidate_cannot_replace_healthy_carrier(self):
        session = {"_pending_file_result": _carrier(6)}
        out = _adopt_pending_file_result(
            session, _carrier(0), source="ask_lane")
        assert out is session["_pending_file_result"]
        assert len(
            session["_pending_file_result"]["structured_result"]["targets"]
        ) == 6

    def test_empty_carrier_adopts_any_candidate(self):
        session = {}
        out = _adopt_pending_file_result(
            session, _carrier(0), source="ask_lane")
        assert out is session["_pending_file_result"]

    def test_zero_target_replaces_zero_target_carrier(self):
        session = {"_pending_file_result": _carrier(0)}
        candidate = _carrier(0)
        candidate["rendered"] = "newer empty verdict"
        _adopt_pending_file_result(session, candidate, source="direct_read")
        assert session["_pending_file_result"]["rendered"] == (
            "newer empty verdict")

    def test_healthy_candidate_always_adopts(self):
        session = {"_pending_file_result": _carrier(2)}
        _adopt_pending_file_result(session, _carrier(8), source="ask_lane")
        assert len(
            session["_pending_file_result"]["structured_result"]["targets"]
        ) == 8

    def test_legacy_shape_without_artifact_never_blocks(self):
        session = {"_pending_file_result": _carrier(6)}
        legacy = {"status": "retrieved", "rendered": "text-only row"}
        _adopt_pending_file_result(session, legacy, source="tool_block")
        assert session["_pending_file_result"] is legacy

    def test_non_dict_candidate_passes_through(self):
        session = {"_pending_file_result": _carrier(6)}
        assert _adopt_pending_file_result(session, None, source="x") is None


class TestResultReferenceRouting:
    """The exact user phrasings from the incident must route to planning."""

    def test_status_table_ask_matches(self):
        assert _STATUS_TABLE_ASK_RE.search(
            "give me the list with a table show what is confirmed and "
            "what is not")
        assert _STATUS_TABLE_ASK_RE.search(
            "show me what's confirmed vs not")
        assert _STATUS_TABLE_ASK_RE.search(
            "which items are still missing?")

    def test_clarify_ask_matches(self):
        assert _CLARIFY_PREVIOUS_RE.search(
            "clarify what you mean for the other machinery you didn't "
            "mention in the previous message")
        assert _CLARIFY_PREVIOUS_RE.search(
            "what do you mean by the other ones?")

    def test_result_reference_still_matches_notfound_shape(self):
        assert _RESULT_REFERENCE_ASK_RE.search(
            "give me a list first what machinery was not found")

    def test_approval_and_filename_confirmation_do_not_match(self):
        # The delivery lane's legitimate traffic must keep flowing.
        for msg in ("yes go ahead", "Consolidated Price List 2019.xlsx is "
                    "correct", "that filename is correct"):
            assert not _STATUS_TABLE_ASK_RE.search(msg)
            assert not _CLARIFY_PREVIOUS_RE.search(msg)
            assert not _RESULT_REFERENCE_ASK_RE.search(msg)


class TestDeliveryHonesty:
    @pytest.mark.asyncio
    async def test_degenerate_record_delivery_says_so(self):
        """A re-delivery from a 0-target record must not ship bare
        header+footer — the honesty note tells the user the record can't
        answer and how to get a real read."""
        import integrations.chat_orchestrator as co

        src = open(co.__file__).read()
        # The guard sits at the delivery lane's single exit, after the
        # formula-section append, before the lane's return.
        assert "EMPTY-RECORD HONESTY" in src
        assert "carries no item rows" in src
        m = re.search(
            r"EMPTY-RECORD HONESTY.*?return _deliver_response",
            src, re.DOTALL)
        assert m, "honesty guard must precede the delivery return"


class TestOutcomeValuesSection:
    def _svc(self):
        import integrations.chat_orchestrator as co

        class FakeOrch(co.ChatOrchestrator):
            def __init__(self):  # skip the real init entirely
                pass

        return FakeOrch()

    def test_section_lists_items_values_and_statuses(self):
        svc = self._svc()
        session = {"_pending_file_result": {
            "identity": {"file_name": "Consolidated Price List 2019.xlsx"},
            "structured_result": {"targets": [
                {"item": "381", "identity": {"status": "single",
                                             "candidates": [{
                                                 "ref": "Tennsmith!R338",
                                                 "values": [
                                                     {"col": "M338",
                                                      "basis": "U.S. LIST",
                                                      "display": "1,845"}],
                                             }]}},
                {"item": "622", "identity": {"status": "multiple",
                                             "candidates": [{}, {}]}},
                {"item": "U-38", "identity": {"status": "none",
                                              "candidates": []}},
            ]},
        }}
        section = svc._outcome_values_section(session, "s1")
        assert "Consolidated Price List 2019.xlsx" in section
        assert "381 — found at Tennsmith!R338" in section
        assert "U.S. LIST 1,845 (M338)" in section
        assert "622 — ambiguous" in section
        assert "U-38 — not found in this copy" in section
        assert "EVERY item" in section  # the full-set instruction

    def test_no_carrier_no_section(self):
        svc = self._svc()
        assert svc._outcome_values_section({}, "s1") == ""
        assert svc._outcome_values_section(
            {"_pending_file_result": {"structured_result": {"targets": []}}},
            "s1") == ""


class TestWorkInstructionOverride:
    """Job step 5 (2026-10-03): a correction/binding/revision turn rated
    non-substantive and the delivery lane re-rendered the stored read.
    A positive work shape must override both delivery entrances."""

    def test_step5_correction_is_work(self):
        from integrations.chat_orchestrator import _WORK_INSTRUCTION_RE

        msg = ("One correction: for item 4, bind 622 to the populated "
               "RoperWhitney row 268 (the machine row, PRICE 2,455) — that "
               "is the one the draft quotes; ignore the fragment rows. Also "
               "use the June 17 Chandrakant-to-Steve thread as the "
               "proposed-price source where it carries a figure. Revised "
               "comparison, please.")
        assert _WORK_INSTRUCTION_RE.search(msg)

    def test_deliveries_still_classify_as_deliveries(self):
        from integrations.chat_orchestrator import _WORK_INSTRUCTION_RE

        for msg in ("yes go ahead",
                    "that filename is correct",
                    "ok",
                    "show me that list again"):
            assert not _WORK_INSTRUCTION_RE.search(msg), msg
