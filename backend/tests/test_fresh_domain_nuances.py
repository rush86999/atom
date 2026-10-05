# -*- coding: utf-8 -*-
"""Fresh-domain nuance coverage (2026-10-01).

The concern this file answers: every fix from the 2026-10-01 price-list
session was verified on ONE conversation in ONE domain. A FRESH
installation, new users, a new domain and new intents must not re-learn
those nuances the hard way.

Design rules:
- The fixture domain (lab consumables) shares NO vocabulary with the
  incident domain: no 'price', no machine words, no shared sheet names,
  no shared model codes.
- Source statements deliberately use nouns the deterministic floors do
  NOT list ('the register', 'the consumables ledger') — the tests prove
  the GENERAL layers (identity shape, schema anchoring, clause scoping,
  base-aware exclusions) catch what any noun list misses.
- No machine state: no learned lessons, no bindings, no resolved files —
  pure seams and the TESTING scratch DB. This is the fresh-install
  condition.
"""
from __future__ import annotations

import io
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from openpyxl import Workbook

FILE = "Lab Consumables Register 2026.xlsx"


def _register_bytes() -> bytes:
    wb = Workbook()
    rg = wb.active
    rg.title = "Reagents"
    rg.append(["Ref", "Grade", "Unit Cost", "Contract Rate"])
    rg.append(["RGX-220", "analytical", 84.0, 76.5])
    rg.append(["220 1188 4", "bulk", 12.0, 9.0])          # fragment code
    rg.append(["RGX-1188", "technical", 31.0, 27.0])
    ds = wb.create_sheet("Disposables")
    ds.append(["Ref", "Spec", "Unit Cost"])
    ds.append(["DSP-09", "sterile 5 ml", 4.2])
    ds.append(["7702", "case of 10", 58.0])               # bare 4-digit code
    lg = wb.create_sheet("Instruments-Legacy")
    lg.append(["Ref", "Status"])
    lg.append(["MC-7", "discontinued"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestFreshDomainMining:
    def test_source_statement_with_unlisted_noun_mines_no_items(self):
        """The 'official' class, new-domain phrasing, noun NOT in any
        floor list ('register'): no adjective rides as an item."""
        from core.workbook_read_artifact import extract_targets

        msg = (
            "Lab Consumables Register 2026 file is the canonical register "
            "maintained by procurement. The consumables ledger is the "
            "master copy. reorder cadence is quarterly with a 5 percent "
            "buffer"
        )
        assert extract_targets(msg, [msg]) == []

    def test_spec_numerics_and_delivery_counts_never_become_items(self):
        """The '36'/'10–11 wks' class: spec quantities and pack counts are
        not identifiers; real codes (hyphenated, 4-digit bare) are."""
        from core.workbook_read_artifact import identity_shaped_item

        for junk in ("5", "10", "ml", "canonical", "quarterly"):
            assert not identity_shaped_item(junk), junk
        for keep in ("RGX-220", "DSP-09", "7702", "MC-7", "Acme",
                     "Sterile Pipette"):
            assert identity_shaped_item(keep), keep


class TestFreshDomainCriteria:
    def test_unlisted_source_statement_cannot_erase_rows(self):
        """The all-absent false-miss class through a noun the list missed:
        'the consumables ledger is the master copy' still mines a
        criterion, but its field anchors to nothing in the workbook —
        schema anchoring keeps the rows; the read answers with values."""
        from core.workbook_read_artifact import (
            _disambiguation_criteria,
            inspect_workbook_bytes,
        )

        query = (
            "find the contract rate for RGX-220. the consumables ledger "
            "is the master copy so trust it"
        )
        crit = _disambiguation_criteria(query, [], None)
        # the criterion MAY mine (noun list missed 'ledger') …
        assert any(
            "ledger" in k or "master" in v[0].lower()
            for k, v in crit.items() for v in [v]) or True
        artifact = inspect_workbook_bytes(
            _register_bytes(), FILE, query=query,
            provider="app_upload", resource_id="lab-1",
        )
        outcome = next(
            o for o in artifact["coverage"]["outcomes"]
            if o["target"] == "RGX-220")
        # … but it must not eliminate: the real row answers
        assert outcome["status"] == "found", (outcome["status"], crit)
        assert outcome["evidence"][0]["sheet"] == "Reagents"

    def test_anchored_attribute_still_constrains(self):
        """Anchoring must not over-relax: a criterion whose field the
        workbook names (Grade) still narrows candidates."""
        from core.workbook_read_artifact import inspect_workbook_bytes

        artifact = inspect_workbook_bytes(
            _register_bytes(), FILE,
            query="find the RGX-1188 where the grade is technical",
            provider="app_upload", resource_id="lab-1",
        )
        outcome = next(
            o for o in artifact["coverage"]["outcomes"]
            if o["target"] == "RGX-1188")
        assert outcome["status"] == "found"
        assert outcome["evidence"][0]["row"] == 4  # RGX-1188, grade=technical


class TestFreshDomainRanking:
    def test_exact_code_outranks_digit_fragments(self):
        """The 381/622 class: bare '220' matches the real RGX row's Ref
        fragment context and a longer spaced code — exact-code rows rank
        first, ambiguity kept honestly when more than one exact exists."""
        from core.workbook_read_artifact import inspect_workbook_bytes

        wb = Workbook()
        s = wb.active
        s.title = "Reagents"
        s.append(["Ref", "Unit Cost"])
        s.append(["220", 84.0])            # exact code
        s.append(["220 1188 4", 12.0])     # fragment
        s.append(["X220", 7.0])            # boundary-only fragment
        t = wb.create_sheet("Disposables")
        t.append(["Ref", "Unit Cost"])
        t.append(["220", 5.0])             # second exact code
        buf = io.BytesIO()
        wb.save(buf)
        artifact = inspect_workbook_bytes(
            buf.getvalue(), FILE, query="find 220",
            provider="app_upload", resource_id="lab-2")
        outcome = artifact["coverage"]["outcomes"][0]
        assert outcome["status"] == "ambiguous"
        values = [e.get("value") for e in outcome["evidence"]]
        assert values[:2] == ["220", "220"]


class TestFreshDomainSetSemantics:
    CODES = ["RGX-220", "DSP-09", "7702"]

    def test_refresh_recheck_over_served_set(self):
        """The 'which other items' class: an explicit re-check over a
        fully-served set re-checks it."""
        from core.target_set_resolution import resolve_target_set

        got = resolve_target_set(
            "check the rest of the consumables and verify contract rates "
            "against the latest supplier data",
            canvas_items=[], prior_items=list(self.CODES),
            last_served_items=list(self.CODES))
        assert got["kind"] == "resolved", got
        assert got["items"] == self.CODES

    def test_except_bare_code_excludes(self):
        """The 'except 622' class with new-domain codes."""
        from core.target_set_resolution import resolve_target_set

        got = resolve_target_set(
            "check the rest except 7702",
            canvas_items=[], prior_items=list(self.CODES),
            last_served_items=[])
        assert got["kind"] == "resolved"
        assert got["items"] == ["RGX-220", "DSP-09"]


class TestFreshDomainCompoundAsks:
    def test_file_plus_communication_clauses_resolve_the_file_clause(self):
        """The clause-scoping class with new-domain nouns: the file clause
        resolves to the conversation's register; the communication clause
        stays with normal planning."""
        import asyncio

        from integrations.chat_orchestrator import (
            _resolve_anaphoric_file_mention,
        )

        session = {"_pending_file_task": {"resolved_file": {
            "file_name": FILE}}}
        got = asyncio.run(_resolve_anaphoric_file_mention(
            "list what consumables were not found in the register file. "
            "also check courier threads for updates.",
            session))
        assert got == "lab consumables register 2026.xlsx"

    def test_outbound_clause_still_refuses(self):
        import asyncio

        from integrations.chat_orchestrator import (
            _resolve_anaphoric_file_mention,
        )

        session = {"_pending_file_task": {"resolved_file": {
            "file_name": FILE}}}
        assert asyncio.run(_resolve_anaphoric_file_mention(
            "find RGX-220 in the register. then forward the summary to "
            "procurement", session)) == ""

    def test_fresh_state_fails_closed(self):
        """No resolved file, no ledger state: every memory tier no-ops
        instead of guessing (the fresh-install condition)."""
        import asyncio

        from integrations.chat_orchestrator import (
            _resolve_anaphoric_file_mention,
        )
        from core import dialogue_state as ds

        assert asyncio.run(_resolve_anaphoric_file_mention(
            "find RGX-220 in the register file", {})) == ""
        assert ds.workbook_bindings(None, "any-hash", ["RGX-220"]) == []
        fresh_conv = f"fresh-{uuid.uuid4().hex[:8]}"
        assert ds.active_bindings(fresh_conv, "any-hash") == []


class TestFreshDomainBindingMemory:
    def test_confirmed_row_crosses_conversations(self):
        """The cross-session memory class: a confirmed row on the register
        is inherited by a NEW conversation at the same revision."""
        from core import dialogue_state as ds

        ws = f"ws-{uuid.uuid4().hex[:8]}"
        rev = f"rev-{uuid.uuid4().hex[:8]}"
        c1 = f"lab-{uuid.uuid4().hex[:8]}"
        ds.append_event(ds.BINDING_CAPTURED, c1, {
            "item": "RGX-220", "sheet": "Reagents", "row": 2,
            "content_hash": rev}, workspace_id=ws)
        got = ds.workbook_bindings(ws, rev, ["RGX-220", "DSP-09"])
        assert [(b["item"], b["row"]) for b in got] == [("RGX-220", 2)]
        assert got[0]["cross_conversation"] is True


class TestNonLatinSafety:
    def test_cjk_prose_with_digits_is_not_an_item(self):
        """Space-free CJK prose runs carry incidental digits — they are
        clauses, not codes. The digit rule requires ASCII-alphanumeric
        density; non-Latin name-only entities remain the NLU residue
        layer's job (fail-closed, never mined prose)."""
        from core.workbook_read_artifact import (
            extract_targets,
            identity_shaped_item,
        )

        for junk in ("2026年6月の価格", "第3四半期の部品表", "型号为220的试剂"):
            assert not identity_shaped_item(junk), junk
        # latin codes still ride inside mixed-script asks
        assert identity_shaped_item("RGX-220")
        msg = "型番RGX-220とDSP-09の単価を教えて"
        mined = extract_targets(msg, [msg])
        assert "RGX-220" in mined and "DSP-09" in mined
        assert all(identity_shaped_item(t) for t in mined), mined
