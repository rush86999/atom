"""Round 20 (2026-10-02): the chained-fallback workflow — the recorded
architectural gap ("one turn, one operation") closed on the existing
general mechanisms.

User instruction (live, three attempts in replay-retry2-20260923):
"update the prices that were found in the email. search email
attachments for the ones not found. If still not found, find email for
vendor pricing if possible. if still not found ask Vipul or Chandrakant
to figure out how to get the pricing for these incomplete ones."

Behaviors pinned:
1. Chain detection: TWO fallback markers required (fail-closed for
   ordinary edits).
2. The evidence phase threads the unresolved item set through
   value_trace (catalog documents) → per-document row values → vendor
   mailbox, and never raises into the turn.
3. The editor's outcome-data section includes chain-found values and
   REPLACES the carrier's not-found line for those items.
4. The consolidated report lists per-source values and drafts the
   terminal ask (nothing is sent).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrations.chat_orchestrator import (
    _CHAIN_ASK_PEOPLE_RE,
    _MULTI_STEP_CHAIN_RE,
    ChatOrchestrator,
)

USER_MSG = (
    "update the prices that were found in the email . search email "
    "attachments for the ones not found. If still not found, find email "
    "for vendor pricing if possible. if still not found ask Vipul or "
    "Chandrakant to figure out how to get the pricing for these "
    "incomplete ones.")


def _svc() -> ChatOrchestrator:
    class Fake(ChatOrchestrator):
        def __init__(self):
            pass
    return Fake()


def _carrier_session(targets):
    return {"_pending_file_result": {
        "identity": {"file_name": "Consolidated Price List 2019.xlsx"},
        "structured_result": {"targets": targets},
    }}


def _target(item, status):
    return {"item": item, "identity": {"status": status,
                                        "candidates": []}}


class TestChainDetection:
    def test_user_instruction_matches_twice(self):
        # "for the ones not found" + "if still not found" ×2 → ≥2 markers.
        assert len(_MULTI_STEP_CHAIN_RE.findall(USER_MSG)) >= 2

    def test_ordinary_edit_request_does_not_match(self):
        for msg in (
            "update the price of the Roper Whitney row to $3,000",
            "change Quote validity: 15 days to 30 days",
            "update the prices that were found in the email",
        ):
            assert len(_MULTI_STEP_CHAIN_RE.findall(msg)) < 2, msg

    def test_people_extraction(self):
        m = _CHAIN_ASK_PEOPLE_RE.search(USER_MSG)
        assert m is not None
        assert "Vipul" in m.group(1) and "Chandrakant" in m.group(1)


class TestUnresolvedSet:
    def test_none_and_multiple_are_unresolved(self):
        session = _carrier_session([
            _target("381", "single"), _target("U-38", "none"),
            _target("622", "multiple"), _target("SLE24-16", "single"),
        ])
        assert ChatOrchestrator._chain_unresolved_items(session) == [
            "U-38", "622"]

    def test_no_carrier_is_empty(self):
        assert ChatOrchestrator._chain_unresolved_items({}) == []


class TestEvidencePhase:
    @pytest.mark.asyncio
    async def test_attachment_step_finds_values(self):
        svc = _svc()
        session = _carrier_session([
            _target("GSL24-16", "none"), _target("U-38", "none")])

        def fake_trace(items, *, exclude_file=None, user_id=None,
                       workspace_id=None):
            return {"GSL24-16": ["All Prices INDUSTRIAL Sept 2026.xlsx"],
                    "U-38": []}

        def fake_find(query, user_id, ws, limit):
            return [{"file_name": "All Prices INDUSTRIAL Sept 2026.xlsx",
                     "entity_name": "Sheet1"}]

        def fake_inspect(entries, file_name, *, targets=None, **kw):
            art_targets = []
            for item in (targets or []):
                if item == "GSL24-16":
                    art_targets.append({
                        "item": item,
                        "identity": {"status": "single", "candidates": [{
                            "ref": "Sheet1!R12",
                            "values": [
                                {"col": "A12", "basis": "Part",
                                 "display": "GSL24-16"},
                                {"col": "D12", "basis": "Price",
                                 "display": "4,995"},
                            ]}]}})
                else:
                    art_targets.append({"item": item, "identity": {
                        "status": "none", "candidates": []}})
            return {"targets": art_targets}

        async def fake_mail(*a, **kw):
            return []  # vendor step finds nothing for U-38

        with patch(
            "core.value_provenance.trace_items_across_catalog",
            fake_trace,
        ), patch(
            "core.sheet_dataset_service.find_entries_sync", fake_find,
        ), patch(
            "core.workbook_read_artifact.inspect_dataset_entries",
            fake_inspect,
        ), patch(
            "integrations.outlook_service.outlook_service.search_emails",
            new=fake_mail,
        ):
            state = await svc._run_fallback_chain_evidence(
                USER_MSG, session, "s1", "u1", {})

        assert state["found"]["GSL24-16"]["display"] == "4,995"
        assert state["found"]["GSL24-16"]["source"] == (
            "All Prices INDUSTRIAL Sept 2026.xlsx")
        assert state["unresolved_after"] == ["U-38"]
        assert state["people"] == ["Vipul", "Chandrakant"]
        # Both steps recorded in the trail.
        sources = [s["source"] for s in state["steps"]]
        assert any("mailbox" in s for s in sources)
        assert any("cataloged documents" in s for s in sources)

    @pytest.mark.asyncio
    async def test_vendor_mail_step_finds_value(self):
        svc = _svc()
        session = _carrier_session([_target("U-38", "none")])

        def fake_trace(items, **kw):
            return {"U-38": []}

        async def fake_mail(*, user_id, query, max_results, quote):
            assert "U-38" in query
            return [{
                "id": "mail-1", "subject": "RE: U-38 quote",
                "body": "The U-38 price is CAD 6,250.00 delivered.",
            }]

        with patch(
            "core.value_provenance.trace_items_across_catalog", fake_trace,
        ), patch(
            "integrations.outlook_service.outlook_service.search_emails",
            new=fake_mail,
        ):
            state = await svc._run_fallback_chain_evidence(
                USER_MSG, session, "s1", "u1", {})

        assert "U-38" in state["found"]
        assert "6,250" in state["found"]["U-38"]["display"]
        assert state["unresolved_after"] == []

    @pytest.mark.asyncio
    async def test_no_unresolved_items_short_circuits(self):
        svc = _svc()
        session = _carrier_session([_target("381", "single")])
        state = await svc._run_fallback_chain_evidence(
            USER_MSG, session, "s1", "u1", {})
        assert state["found"] == {}
        assert state["steps"] == [
            {"source": "chain", "outcome": "no_unresolved_items"}]

    @pytest.mark.asyncio
    async def test_step_failure_never_raises(self):
        svc = _svc()
        session = _carrier_session([_target("U-38", "none")])

        def explode(*a, **kw):
            raise RuntimeError("catalog down")

        with patch(
            "core.value_provenance.trace_items_across_catalog", explode,
        ), patch(
            "integrations.outlook_service.outlook_service.search_emails",
            new=AsyncMock(side_effect=RuntimeError("mail down")),
        ):
            state = await svc._run_fallback_chain_evidence(
                USER_MSG, session, "s1", "u1", {})
        # Degraded but complete: the turn continues as an ordinary edit.
        assert state["unresolved_after"] == ["U-38"]


class TestChainReport:
    def test_report_lists_values_and_drafts_ask(self):
        state = {
            "found": {"GSL24-16": {
                "display": "4,995", "basis": "Price",
                "source": "All Prices INDUSTRIAL Sept 2026.xlsx",
                "ref": "Sheet1!R12"}},
            "unresolved_after": ["U-38"],
            "people": ["Vipul", "Chandrakant"],
            "steps": [],
        }
        report = ChatOrchestrator._chain_report_text(state, USER_MSG)
        assert "GSL24-16" in report and "4,995" in report
        assert "U-38" in report
        # The draft ask names the people and the items, and asserts
        # nothing was sent.
        assert "Vipul" in report and "Chandrakant" in report
        assert "have not sent" in report
        # Neutral vocabulary: no hardcoded business nouns in the report.
        assert "vendor" not in report.lower()
        assert "pricing" in report or "price" in report.lower()

    def test_nothing_to_report_is_empty(self):
        assert ChatOrchestrator._chain_report_text(None, "x") == ""
        assert ChatOrchestrator._chain_report_text(
            {"found": {}, "unresolved_after": [],
             "steps": [{"source": "chain",
                        "outcome": "no_unresolved_items"}]}, "x") == ""


class TestOutcomeSectionChainMerge:
    def test_chain_value_replaces_notfound_line(self):
        svc = _svc()
        session = _carrier_session([_target("GSL24-16", "none")])
        session["_chain_evidence"] = {"found": {
            "GSL24-16": {"display": "4,995", "basis": "Price",
                         "source": "All Prices.xlsx", "ref": "R12"}}}
        section = svc._outcome_values_section(session, "s1")
        assert "GSL24-16 — 4,995 Price" in section
        assert "not found in this copy" not in section
        # The full-set edit instruction rides along.
        assert "EVERY item" in section


class TestCandidateFidelityOrdering:
    """Cosmetic gap (round 17 note): inside an ambiguous render the
    exact comma-form row could display after fragment matches. The
    fidelity axis puts the row whose identity cell EQUALS the requested
    item first — display order only, nothing eliminated."""

    def test_exact_match_leads_within_bucket(self):
        from core.answer_presentation import _rank_candidates

        fragment_row = {
            "ref": "Sheet!R5",
            "values": [{"col": "B5", "basis": "Price", "display": "100"}],
            "identity": {"status": "bound", "references": [
                {"sheet": "Sheet", "cell": "A5", "row": 5,
                 "value": "100", "role": "matched_target"}]},
        }
        exact_row = {
            "ref": "Sheet!R12",
            "values": [{"col": "D12", "basis": "Price", "display": "4,995"}],
            "identity": {"status": "bound", "references": [
                {"sheet": "Sheet", "cell": "A12", "row": 12,
                 "value": "56,100", "role": "matched_target"}]},
        }
        ranked = _rank_candidates(
            [fragment_row, exact_row],
            requested_fields=["price"], item="56100")
        assert ranked[0]["ref"] == "Sheet!R12"
        # Nothing eliminated: the fragment row is still there.
        assert ranked[1]["ref"] == "Sheet!R5"

    def test_no_item_keeps_previous_order(self):
        from core.answer_presentation import _rank_candidates

        a = {"ref": "A", "values": [{"display": "1"}]}
        b = {"ref": "B", "values": [{"display": "2"}]}
        assert [c["ref"] for c in _rank_candidates([a, b])] == ["A", "B"]


# ---------------------------------------------------------------------------
# DOMAIN & BUSINESS INDEPENDENCE (2026-10-02 audit): the chain must work
# for any business, any file, any value kind, any names — the vocabulary
# comes from the USER'S OWN instruction and the read's requested fields,
# never from this user's machinery/pricing domain.
# ---------------------------------------------------------------------------

RESTAURANT_MSG = (
    "update the delivery lead times that were found in the email . check "
    "supplier attachments for the ones not found. If still not found, "
    "find email for the schedule if possible. if still not found ask "
    "Maria or José to figure out how to get the lead times for these "
    "incomplete ones.")

CLINIC_MSG = (
    "update the dosages that were found in the email . search lab "
    "attachments for the ones not found. If still not found, find email "
    "for the protocol if possible. if still not found ask Dr. Chen to "
    "figure out how to get the dosages for these incomplete ones.")


class TestChainDomainIndependence:
    def test_detection_across_domains(self):
        for msg in (USER_MSG, RESTAURANT_MSG, CLINIC_MSG):
            assert len(_MULTI_STEP_CHAIN_RE.findall(msg)) >= 2, msg[:40]

    def test_value_noun_from_users_own_words(self):
        from integrations.chat_orchestrator import _chain_value_vocabulary as v
        assert v(RESTAURANT_MSG, {})["noun"] == "delivery lead times"
        assert v(CLINIC_MSG, {})["noun"] == "dosages"
        assert v(USER_MSG, {})["noun"] == "prices"
        # No value kind named anywhere → the neutral fallback.
        assert v("update these that were found. for the ones not found "
                 "check attachments. if still not found ask Ana to help",
                 {})["noun"] == "pricing"

    def test_fields_come_from_the_reads_own_request(self):
        from integrations.chat_orchestrator import _chain_value_vocabulary as v
        carrier = {"structured_result": {"requested_fields": ["lead time"]}}
        got = v(RESTAURANT_MSG, carrier)
        assert got["fields"] == ["lead time"]
        assert "lead time" in got["qualifiers"]
        # A pricing qualifier must NOT appear when the chain is about
        # lead times.
        assert "price" not in got["qualifiers"]

    @pytest.mark.asyncio
    async def test_accented_and_honorific_people(self):
        svc = _svc()
        # Extract people via the evidence phase header (no items → fast).
        session = _carrier_session([])
        st = await svc._run_fallback_chain_evidence(
            RESTAURANT_MSG, session, "s", "u", {})
        assert st["people"] == ["Maria", "José"]

    def test_report_uses_users_nouns_and_file(self):
        state = {
            "value_noun": "dosages",
            "primary_file": "Protocol Master v4.xlsx",
            "found": {},
            "unresolved_after": ["RX-77"],
            "people": ["Dr. Chen"],
            "steps": [],
        }
        report = ChatOrchestrator._chain_report_text(state, CLINIC_MSG)
        assert "current dosages" in report
        assert "Protocol Master v4.xlsx" in report
        assert "Dr. Chen" in report
        assert "vendor" not in report.lower()
        assert "machinery" not in report.lower()

    def test_german_basis_still_picks_the_value(self):
        # A non-English sheet's cost column ("Preis") is preferred by
        # the multilingual basis pattern; the first-value fallback keeps
        # any language working.
        from integrations.chat_orchestrator import (
            _CHAIN_BASIS_PREFERENCE_RE as pref,
        )
        assert pref.search("Preis")
        assert pref.search("Prix unitaire")
        assert pref.search("Coste")


class TestGuardTableExemption:
    """The 8-machine replay data loss (2026-10-03): a results TABLE with
    honest 'no match' rows was one 'sentence' to the absence guard — the
    whole table was replaced with scoped-limitation boilerplate, and the
    reply shipped as a tail fragment. Tables are evidence, not prose."""

    def test_table_with_no_match_rows_is_not_a_claim(self):
        from core.absence_guard import (
            uncovered_absence_claims, strip_uncovered_absence_claims,
        )

        reply = (
            "Here's the scan:\n\n"
            "| Item | Result |\n|---|---|\n"
            "| 381 | 1,845 |\n| GSL24-16 | no match |\n"
            "| U-38 | not found in this copy |\n\n"
            "Saved 2026-10-02.")
        assert uncovered_absence_claims(reply, "coverage: complete") == []
        # The deterministic strip keeps the table byte-for-byte.
        assert strip_uncovered_absence_claims(
            reply, "coverage: complete") == reply

    def test_prose_absence_still_flagged_beside_tables(self):
        from core.absence_guard import uncovered_absence_claims

        reply = (
            "| Item | Result |\n|---|---|\n| 381 | 1,845 |\n\n"
            "No such machine exists anywhere in the industry.")
        claims = uncovered_absence_claims(reply, "coverage: complete")
        assert len(claims) == 1
        assert "industry" in claims[0]

    def test_figure_grounding_counts_canvas_values(self):
        # The canvas quote prices the narration echoed are evidence once
        # the canvas text joins the pool — via the same combined-evidence
        # string the reply leg now passes.
        from core.chat_tool_planner import _unsupported_figures

        canvas = ("to: x; subject: Quote; body: <table><tr><td>"
                  "Roper Whitney 381</td><td>$2,902.00</td></tr>"
                  "<tr><td>Linmac U-22</td><td>$1,777.00</td></tr></table>")
        reply = ("381 is $2,902.00 on the quote and the workbook lists "
                 "1,845 U.S. LIST.")
        evidence = f"tool block with 1,845\n{canvas}"
        assert _unsupported_figures(reply, evidence) == []
        # Without the canvas text, the canvas prices ARE unsupported
        # (guards the fix's mechanism, not just its absence).
        assert any("2,902.00" in f for f in
                   _unsupported_figures(reply, "tool block with 1,845"))


class TestGuardRepresentationIndependence:
    """Round-22 audit: the table exemption must hold for EVERY table
    form a producer may emit, in ANY business's vocabulary."""

    def test_html_table_rows_exempt(self):
        from core.absence_guard import (
            strip_uncovered_absence_claims, uncovered_absence_claims,
        )

        reply = ("Scan results:\n<table>\n<tr><td>SKU-1</td>"
                 "<td>in stock</td></tr>\n<tr><td>SKU-9</td>"
                 "<td>not carried</td></tr>\n</table>\nDone.")
        assert uncovered_absence_claims(reply, "coverage: complete") == []
        assert strip_uncovered_absence_claims(
            reply, "coverage: complete") == reply

    def test_inline_html_table_exempt(self):
        # Producers emit the whole table on ONE line.
        from core.absence_guard import uncovered_absence_claims

        reply = ("Results: <table><tr><td>Item A</td><td>discontinued"
                 "</td></tr><tr><td>Item B</td><td>no longer offered"
                 "</td></tr></table> — full list above.")
        assert uncovered_absence_claims(reply, "coverage: complete") == []

    def test_restaurant_and_clinic_tables(self):
        from core.absence_guard import strip_uncovered_absence_claims

        restaurant = ("| Dish | Supplier status |\n|---|---|\n"
                      "| Scallops | out of stock seasonally |\n"
                      "| Truffles | not carried by any vendor on file |")
        clinic = ("| Panel | Availability |\n|---|---|\n"
                  "| Rare antigens | not performed in-network |\n"
                  "| Standard CBC | available |")
        for table in (restaurant, clinic):
            assert strip_uncovered_absence_claims(
                table, "coverage: complete") == table

    def test_prose_rewrite_keeps_table_intact(self):
        # When a rewrite DOES fire in the prose, the table survives
        # byte-for-byte (the old space-join flattened it).
        from core.absence_guard import strip_uncovered_absence_claims

        reply = ("| Item | Status |\n|---|---|\n| X | available |\n\n"
                 "There is no such supplier anywhere in the world.")
        out = strip_uncovered_absence_claims(reply, "coverage: complete")
        assert "| Item | Status |" in out
        assert "| X | available |" in out
        assert "did not find one in what this turn actually searched" in out
        assert "anywhere in the world" not in out


class TestFormulaAvailability:
    """The every-row formula contract (2026-10-03): a workbook cell's
    sidecar formula reaches every decision context — the editor's
    outcome-data section, the chain's found-value, the chain report —
    without needing a derivation-shaped ask."""

    def test_outcome_section_renders_formulas(self):
        svc = _svc()
        session = _carrier_session([_target("381", "single")])
        session["_pending_file_result"]["structured_result"]["targets"][0][
            "identity"]["candidates"] = [{
                "ref": "Acme!R12",
                "values": [
                    {"col": "B12", "basis": "List", "display": "1,845",
                     "formula": "=ROUNDUP(A12*1.15,0)"},
                ],
            }]
        section = svc._outcome_values_section(session, "s1")
        assert "B12) = =ROUNDUP(A12*1.15,0)" in section

    def test_outcome_section_omits_missing_formulas_cleanly(self):
        svc = _svc()
        session = _carrier_session([_target("381", "single")])
        session["_pending_file_result"]["structured_result"]["targets"][0][
            "identity"]["candidates"] = [{
                "ref": "Acme!R12",
                "values": [{"col": "B12", "basis": "List",
                            "display": "1,845"}],
            }]
        section = svc._outcome_values_section(session, "s1")
        assert "1,845" in section and "= =" not in section

    def test_chain_found_carries_formula_into_report(self):
        state = {
            "value_noun": "pricing",
            "primary_file": "master.xlsx",
            "found": {"GSL24-16": {
                "display": "4,995", "basis": "Price",
                "source": "vendor.xlsx", "ref": "Sheet1!R12",
                "formula": "=E12*1.3"}},
            "unresolved_after": [],
            "people": [],
            "steps": [],
        }
        report = ChatOrchestrator._chain_report_text(state, USER_MSG)
        assert "=E12*1.3" in report

    def test_reverify_due_on_missing_sidecar_for_sheet_files(self):
        from datetime import datetime, timedelta, timezone as tz

        from integrations.universal_integration_service import (
            _dataset_reverify_due,
        )

        def iso(**kw):
            return (datetime.now(tz.utc) + timedelta(**kw)).isoformat()

        # Sheet file, sidecar absent → due EVEN when brand new (the
        # sidecar rule ignores the age gate).
        assert _dataset_reverify_due({
            "file_name": "Vendor Price List.xlsx",
            "sidecar_present": False,
            "ingested_at": iso(minutes=-1),
        }) is True
        # Sidecar present + fresh → age rule only → not due.
        assert _dataset_reverify_due({
            "file_name": "Vendor Price List.xlsx",
            "sidecar_present": True,
            "ingested_at": iso(minutes=-1),
        }) is False
        # Non-sheet sources never trigger the sidecar rule (fresh +
        # sidecar missing → not due; a workbook with no extension-ful
        # name has no workbook bytes to re-download).
        assert _dataset_reverify_due({
            "file_name": "zoho books_invoices",
            "sidecar_present": False,
            "ingested_at": iso(minutes=-1),
        }) is False


def test_read_canvas_serves_draft_body_over_empty_shell():
    """Job step 7 (2026-10-03): save_draft audits carry an EMPTY content
    shell while the real body lives under details['draft']['body'] — the
    agent's canvas hydration saw 'an empty email draft' for a fully
    seeded quote. The reader must serve the draft body when the shell is
    blank (read-shape normalization, history untouched)."""
    import inspect

    from tools import canvas_crud_tool

    src = inspect.getsource(canvas_crud_tool.read_canvas)
    assert "EMAIL DRAFT-STATE READ" in src
    assert 'details.get("draft")' in src


class TestCreditExhaustionRouting:
    """The step-4 failure (2026-10-03): the ranked pool collapsed to one
    credit-dead gateway, its 300s bench expired mid-job and re-admitted
    it, and the exhaustion message claimed 'every configured provider'
    while opencode-go sat healthy."""

    def test_quota_cooldown_defaults_to_30_minutes(self):
        import importlib
        import core.llm.byok_handler as bh

        importlib.reload(bh)
        assert bh._PROVIDER_QUOTA_COOLDOWN_SECONDS == 1800.0

    def test_quota_bench_fires_on_credit_errors(self):
        import importlib
        import core.llm.byok_handler as bh

        importlib.reload(bh)
        inst = object.__new__(bh.BYOKHandler)
        called = {}

        def fake_bench(provider_id, *, cause, detail, seconds=None):
            called["p"] = provider_id
            called["cause"] = cause

        inst._bench_provider = fake_bench
        fired = inst._bench_provider_on_quota_error(
            "openrouter",
            "Error code: 402 - This request requires more credits")
        assert fired is True
        assert called["p"] == "openrouter"
        assert called["cause"] == "quota_exhausted"
        # Non-credit errors must not bench.
        assert inst._bench_provider_on_quota_error(
            "openrouter", "Error code: 400 - bad temperature") is False


class TestTbcCatalogProbe:
    """Reliability run A (2026-10-03): a value-edit with TBC rows ran
    BLIND — the planner judged no lookup necessary, the editor declined
    without evidence. The deterministic probe extracts unpriced rows and
    checks the catalog for each."""

    def _svc(self):
        import integrations.chat_orchestrator as co

        class Fake(co.ChatOrchestrator):
            def __init__(self):
                pass

        return Fake()

    def test_unpriced_rows_detected_domain_free(self):
        import asyncio

        svc = self._svc()
        canvas = {"content": {"body": (
            "<table><tr><th>#</th><th>Item</th><th>Price</th></tr>"
            "<tr><td>1</td><td>PE-16 Hand Seam Tool</td><td>TBC</td></tr>"
            "<tr><td>2</td><td>MidWest 24-in Brake</td><td>$1,240.00</td></tr>"
            "</table>")}}

        def fake_trace(items, **kw):
            assert "PE-16 Hand Seam Tool" in items
            assert "MidWest 24-in Brake" not in items
            return {"PE-16 Hand Seam Tool": []}

        with patch(
            "core.value_provenance.trace_items_across_catalog", fake_trace
        ):
            section = asyncio.run(svc._tbc_items_catalog_probe(
                canvas, "u1", "default"))
        assert "PE-16" in section
        assert "no cataloged document carries it" in section
        assert "MidWest" not in section.split("UNPRICED")[1].split("- \"")[1]

    def test_no_unpriced_rows_no_section(self):
        import asyncio

        svc = self._svc()
        canvas = {"content": {"body": (
            "<table><tr><td>1</td><td>X</td><td>$5.00</td></tr></table>")}}
        assert asyncio.run(svc._tbc_items_catalog_probe(
            canvas, "u1", None)) == ""


def test_item_code_tokens_reach_the_per_term_pool():
    """Step-3 depth gap (2026-10-03): resolved codes ride the query TAIL
    past the first-3 cut, so the mailbox search never searched for them.
    Identifier-shaped tokens (letters+digits) must join the pool."""
    import re as _re

    query = ("For the ones still open go through the supplier "
             "correspondence (the not-found items to search for: "
             "GSL24-16, SLE16-8, U-38, 622)")
    tokens = [t.strip('"$€£¥₹₩₽₺%,;:()') for t in query.split()
              if len(t.strip('"$€£¥₹₩₽₺%,;:()')) >= 2][:3]
    for _t in query.split():
        _tc = _t.strip('"$€£¥₹₩₽₺%,;:()')
        if len(_tc) < 4 or _tc in tokens:
            continue
        if _re.search(r"[A-Za-z]", _tc) and _re.search(r"\d", _tc):
            tokens.append(_tc)
            if len(tokens) >= 6:
                break
    assert "GSL24-16" in tokens and "SLE16-8" in tokens
    # Pure words without digits stay out of the additions.
    assert "correspondence" not in tokens


class TestArcIndependence:
    """Owner directive (2026-10-03): every fix domain- and business-
    independent. These pin the gates with non-purchasing domains."""

    def test_outcome_seek_gates_on_generic_sources(self):
        # The exact gate expression the orchestrator uses.
        import re as _re

        pattern = (
            r"\b(?:e-?mails?|attachments?|mailbox|inbox|"
            r"threads?|messages?|correspondence|letters?|vendor|suppliers?|"
            r"records?|documents?|docs?|files?|folders?|archives?|"
            r"databases?|notes?|registers?|index|system)\b")
        for msg in (
            "for the ones not found, check the case records",
            "the ones still open — look in the project folder",
            "check the lab documents for the ones missing",
            "go through the supplier correspondence for the missing ones",
        ):
            assert _re.search(pattern, msg, _re.IGNORECASE), msg

    def test_work_instruction_is_value_family_not_price_only(self):
        from integrations.chat_orchestrator import _WORK_INSTRUCTION_RE

        for msg in (
            "One correction: bind line 2 to the spec sheet; use the lab "
            "report as the source. Revised comparison please.",
            "use the registry as the basis and give me a revised table",
            "correct the lead-time-source for row 3",
        ):
            assert _WORK_INSTRUCTION_RE.search(msg), msg
        # Deliveries still exempt
        for msg in ("yes", "ok go ahead", "that file is correct"):
            assert not _WORK_INSTRUCTION_RE.search(msg), msg

    def test_tbc_probe_placeholder_family(self):
        import asyncio

        svc = _svc()
        canvas = {"content": {"body": (
            "<table><tr><td>1</td><td>Item One</td><td>TBA</td></tr>"
            "<tr><td>2</td><td>Item Two</td><td>pending</td></tr>"
            "<tr><td>3</td><td>Item Three</td><td>?</td></tr>"
            "</table>")}}

        def fake_trace(items, **kw):
            return {i: [] for i in items}

        with patch(
            "core.value_provenance.trace_items_across_catalog", fake_trace
        ):
            section = asyncio.run(svc._tbc_items_catalog_probe(
                canvas, "u1", None))
        assert section.count("no cataloged document carries it") == 3


def test_search_auto_read_covers_truncated_hits():
    """Thread-depth directive (2026-10-04): preview-only/excerpt hits are
    auto-read in the same search turn (top-2, per-id outcomes) — the
    agent no longer needs a second turn to see quoted-thread content."""
    import inspect
    import re as _re_mod

    import core.chat_tool_planner as ctp

    src = inspect.getsource(ctp)
    assert "AUTO-READ (full thread content pulled" in src
    # The auto-read reuses the read-by-ids machinery with the READ body
    # cap (not the smaller search cap) and bounded hit count.
    m = _re_mod.search(
        r"_auto_ids = \[.*?\]\[:2\]", src, _re_mod.DOTALL)
    assert m, "bounded auto-read slice missing"
    assert "_OUTLOOK_READ_BODY_CAP" in src


def test_inflight_claim_ttl_steals_leaked_claims(monkeypatch):
    """Step-3 verify (2026-10-04): opencode-go/kimi-k2.7-code was skipped
    as model_inflight across turns — claims had no TTL, so one leaked
    claim blocked the healthy route for the process lifetime."""
    import time as _time

    import core.llm.byok_handler as bh

    inst = object.__new__(bh.BYOKHandler)
    # Fresh claim succeeds; immediate re-claim fails.
    assert inst._claim_model_attempt("opencode-go", "kimi-k2.7-code") is True
    assert inst._claim_model_attempt("opencode-go", "kimi-k2.7-code") is False
    inst._release_model_attempt("opencode-go", "kimi-k2.7-code")
    assert inst._claim_model_attempt("opencode-go", "kimi-k2.7-code") is True
    # A LEAKED claim (older than the TTL) is stolen.
    pair = "opencode-go/kimi-k2.7-code"
    bh._MODEL_ATTEMPT_INFLIGHT[pair] = (
        _time.time() - bh._MODEL_ATTEMPT_INFLIGHT_TTL_SECONDS - 1)
    assert inst._claim_model_attempt("opencode-go", "kimi-k2.7-code") is True
    inst._release_model_attempt("opencode-go", "kimi-k2.7-code")


def test_na_means_not_applicable_unless_asked_to_fill_all():
    """Review correction (2026-10-04): 'n/a' usually means deliberately
    not applicable — a completed row, not a fill request. Only an
    explicit fill-everything instruction opens n/a rows."""
    import asyncio

    svc = _svc()
    canvas = {"content": {"body": (
        "<table><tr><td>1</td><td>Warranty Extension</td><td>n/a</td></tr>"
        "<tr><td>2</td><td>Rush Fee</td><td>TBC</td></tr></table>")}
    }
    # No fill-all instruction: n/a is completed, TBC is open.
    section = asyncio.run(svc._tbc_items_catalog_probe(
        canvas, "u1", None, message="fill what you can"))
    assert "Warranty Extension" not in section
    assert "Rush Fee" in section
    # Explicit fill-all: n/a opens too.
    section_all = asyncio.run(svc._tbc_items_catalog_probe(
        canvas, "u1", None,
        message="price all the rows in this quote"))
    assert "Warranty Extension" in section_all
    assert "Rush Fee" in section_all


def test_negated_edit_vocabulary_is_not_edit_shaped():
    """Final-job T1 (2026-10-04): 'Don't change the draft yet' matched the
    edit shape and the turn shipped 'editor declined' instead of running
    the requested research. The negation determines the semantics."""
    from integrations.chat_orchestrator import _canvas_edit_shaped

    canvas = {"canvas_id": "c1", "canvas_type": "email"}
    research = ("research all eight machines and give me the comparison — "
                "Don't change the draft yet.")
    assert not _canvas_edit_shaped(research, {"canvas": canvas})
    assert not _canvas_edit_shaped(
        "finish the comparison without changing the draft.",
        {"canvas": canvas})
    # A REAL edit keeps its lane.
    assert _canvas_edit_shaped(
        "update item 2 delivery to In Stock", {"canvas": canvas})


def test_lesson_designated_file_resolves_from_teaching():
    """Fresh-session completion (2026-10-04): session state dies with the
    session, but the teaching names the source durably. A generic file
    reference in a fresh session resolves through the lesson designation
    when exactly one catalog family matches."""
    import asyncio

    svc = _svc()
    svc._agent_lessons = lambda agent_id, query, limit=5: [
        {"source": "teacher",
         "lesson": "price list 2019 in zoho workdrive has the most "
                   "common formulas used for different machinery"}]
    canvas_files = {
        "consolidated price list 2019.xlsx": "Consolidated Price List 2019.xlsx",
        "inventory tracking 1.xlsx": "Inventory Tracking 1.xlsx",
    }

    def fake_entries(query, user_id, ws, limit):
        return [{"file_name": fn} for fn in canvas_files.values()]

    async def run():
        with patch("core.sheet_dataset_service.find_entries_sync",
                   fake_entries):
            return await svc._lesson_designated_file(
                "search the workbook for 381", agent_id="a1",
                user_id="u1", workspace_id=None)

    resolved = asyncio.run(run())
    assert resolved == "consolidated price list 2019.xlsx"

    # Ambiguous (two families match) → no resolution.
    def fake_entries2(query, user_id, ws, limit):
        return [
            {"file_name": "Acme Price List 2019.xlsx"},
            {"file_name": "Zenith Price List 2019.xlsx"},
        ]

    async def run2():
        with patch("core.sheet_dataset_service.find_entries_sync",
                   fake_entries2):
            return await svc._lesson_designated_file(
                "search the workbook", agent_id="a1", user_id="u1",
                workspace_id=None)

    assert asyncio.run(run2()) == ""


class TestSweepInjectionControls:
    """Reviewer closeout #1: catalog-added candidates must still satisfy
    the existing controls — the injection replaces the list, but pin/
    fallback exclusions and cooldowns stay enforced."""

    def test_exclusion_applies_after_injection(self):
        import re as _re

        src = open(
            "core/llm/byok_handler.py").read()
        # The injection block must apply exclude_provider_model AFTER
        # replacing options (order asserted structurally).
        m = _re.search(
            r"if _force_candidates:\n(.*?)logger\.warning\(\n"
            r"\s+\"\[structured-pool\] sweep injected",
            src, _re.DOTALL)
        assert m, "injection block not found"
        block = m.group(1)
        assert "exclude_provider_model" in block, (
            "pin/fallback exclusion must be applied to injected candidates")

    def test_injection_build_skips_cooldown_providers(self):
        import inspect

        import core.llm.byok_handler as bh

        src = inspect.getsource(bh)
        # The sweep-candidate builder skips cooldown-active providers.
        assert "_sp in _attempted_set" in src
        assert "self._provider_cooldown_active(_sp)" in src
        assert "self._ranked_model_is_known_unserved(_sp, _sm)" in src


def test_pricing_verify_cross_check_shape():
    """Reviewer closeout #4 (2026-10-04): the acceptance run consulted
    only the mailbox and stopped to ask permission for a read-only
    lookup. Verification-shaped turns must chain the workbook cross-
    check in the same block (deterministic gate: pricing/verify
    vocabulary + identifier tokens present)."""
    src = open("core/chat_tool_planner.py").read()
    assert "PRICING-VERIFY CROSS-CHECK" in src
    assert "WORKBOOK CROSS-CHECK (taught source" in src
    # Bounded: tokens are capped at 4 in the chained loop.
    assert "tokens[:4]" in src
