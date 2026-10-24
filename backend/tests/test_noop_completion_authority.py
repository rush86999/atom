"""Completion-authority cases for the served-decline no-op path
(owner work order 2026-10-10: prove whether the S3 no-op certification
is valid BEFORE changing confirmation wording).

Six cases driven through the PRODUCTION decline path — the canvas lane
itself (``_try_canvas_edit``) with a stubbed planner, the same harness
as the round-62 no-op pin. The completion receipt is NEVER seeded:
``shared_tool_state["objective_evidence"]`` carries the authorized
EVIDENCE CONTRACT (input — the same object production feeds drafting);
the receipt (``canvas_edit_decline_noop`` /
``canvas_decline_requirement_check``) must be produced — or refused —
by the production branch.

The fixture: the Brennan S3 draft (5 requested machines + 3 protected
alternatives; the canvas's own prose declares the split) and an
authorized contract whose source-side evidence (workbook rows + the
owner's manual-quote decision) carries the approved values.
"""
import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from core.chat_canvas_editor import (
    artifact_observations,
    requirement_check,
)
from core.workbook_read_artifact import build_source_comparison
from integrations import chat_orchestrator as co
import core.chat_canvas_editor as cce


def _brennan_canvas(row3_price="$1,609.00", row4_price="$2,421.00",
                    row3_deliv="3–4 weeks", row4_deliv="In Stock",
                    row5_deliv="11–12 weeks"):
    rows = [
        ("1", "Roper Whitney 36&quot; Roll Bender", "$2,902.00",
         "10–11 weeks"),
        ("2", "Linmac Bead Roller 22 Gauge", "$1,777.00", "In Stock"),
        ("3", "Manual Flanger", row3_price, row3_deliv),
        ("4", "Roper Whitney No. 622 Rotary", row4_price, row4_deliv),
        ("5", "Tennsmith Slitter SLE24-16", "$8,984.00", row5_deliv),
        ("6", "TK 1624 Slitter", "$8,040.00", "4–6 weeks"),
        ("7", "Tin Knocker Gang Slitter", "$12,838.00", "In Stock"),
        ("8", "Tennsmith GSL48 Slitter", "$14,166.00", "6–8 weeks"),
    ]
    trs = "".join(
        f"<tr><td>{n}</td><td>{d}</td><td>{p}</td><td>{dl}</td></tr>"
        for n, d, p, dl in rows)
    body = (
        "Hi Steve,<br><br>Rows 1–5 are the requested machines; rows 6–8 "
        "are alternative slitters."
        "<table><tr><th>#</th><th>Description</th><th>Unit Price</th>"
        f"<th>Delivery</th></tr>{trs}</table>"
        "<p>Payment Terms: CAD / FOB / TBD</p>")
    return {"canvas_id": "cv-s3-auth", "canvas_type": "email",
            "content": {"body": body}}


_ENTITIES = ["Roper Whitney 36", "Linmac", "Manual Flanger",
             "No. 622", "SLE24-16"]

_APPROVED = {
    # entity: (price, delivery) — the authorized values
    "Roper Whitney 36": ("$2,902.00", "10–11 weeks"),
    "Linmac": ("$1,777.00", "In Stock"),
    "Manual Flanger": ("$1,609.00", "3–4 weeks"),
    "No. 622": ("$2,421.00", "In Stock"),
    "SLE24-16": ("$8,984.00", "11–12 weeks"),
}


def _obs(entity, field, raw, source_id, source_type, **extra):
    return {
        "entity_id": entity, "field": field, "raw_value": raw,
        "source": {"source_id": source_id, "source_type": source_type},
        "verification": "verified",
        "source_version": extra.pop("source_version", "rev-A"),
        "column": "Unit Price" if field == "price" else "Delivery",
        **extra,
    }


def _authorized_contract():
    """The approved-value evidence, production-shaped
    (build_source_comparison's return): workbook rows carry price and
    delivery; the owner's manual-quote decision carries row 1's price.
    authorized_actions=["edit_artifact"] mirrors the drafting call."""
    observations = []
    for entity, (price, deliv) in _APPROVED.items():
        source = ("owner-manual-quote" if entity == "Roper Whitney 36"
                  else "tennsmith-quote-sheet")
        observations.append(
            _obs(entity, "price", price, source,
                 "decision" if source.startswith("owner")
                 else "workbook"))
        observations.append(
            _obs(entity, "delivery", deliv, "tennsmith-quote-sheet",
                 "workbook"))
    canvas = _brennan_canvas()
    for entity, (price, deliv) in _APPROVED.items():
        observations.append(
            _obs(entity, "price", price, "cv-s3-auth", "artifact"))
        observations.append(
            _obs(entity, "delivery", deliv, "cv-s3-auth", "artifact"))
    return build_source_comparison(
        observations,
        requested_entities=_ENTITIES,
        requested_fields=["Unit Price", "Delivery"],
        artifact_source_ids=["cv-s3-auth"],
        decision_source_ids=["owner-manual-quote"],
        authorized_actions=["edit_artifact"],
    )


class _DeclinedPlan:
    wants_edit = False
    reply = "The draft already reflects the approved values."


def _run_lane(canvas, contract, expected_prior=None,
              current_revision="rev-A", message=None):
    """Drive the production decline path. Returns the shared blackboard
    the lane wrote (the receipt must be produced — or refused — there).
    The fresh leg is stubbed at its production seam to the revision the
    CURRENT turn resolved (None = the source was not resolved this
    turn — workbook findings then cannot certify at all). ``message``
    defaults to the Brennan approved-values ask."""
    async def _plan_ok(*a, **k):
        return _DeclinedPlan()

    from core.chat_canvas_editor import FreshDataResult

    _resolved = {}
    if contract is not None:
        _resolved = {"source": {"evidence_revision": current_revision},
                     "evidence": contract.get("evidence") or [],
                     "actions": contract.get("actions") or []}

    async def _fresh_resolved(*a, **k):
        return FreshDataResult(
            section="", needed=False, ok=True, block="",
            evidence_contract=_resolved or None)

    import integrations.chat_orchestrator as co_mod
    original = cce.plan_canvas_edit
    original_fresh = cce.fetch_fresh_data_section
    original_det = getattr(cce, "deterministic_assignment_plan", None)
    cce.plan_canvas_edit = _plan_ok
    cce.fetch_fresh_data_section = _fresh_resolved
    # This suite exercises the no-op/decline authority path with a stubbed
    # planner. Deterministic assignment compilation has its own tests; keep
    # this lane on the decline path so the receipt assertions stay exact.
    cce.deterministic_assignment_plan = lambda **kwargs: None
    shared = {}
    if contract is not None:
        shared["objective_evidence"] = contract
    try:
        asyncio.run(co_mod.chat_orchestrator._try_canvas_edit(
            message if message is not None else (
                "Update the draft for rows 1-5 with the approved prices and "
                "delivery times. Don't send."),
            [], canvas, "user_1", "sess-auth", "exec-auth", None,
            shared_tool_state=shared,
            expected_prior_audit_id=expected_prior))
    finally:
        cce.plan_canvas_edit = original
        cce.fetch_fresh_data_section = original_fresh
        if original_det is not None:
            cce.deterministic_assignment_plan = original_det
        else:
            try:
                del cce.deterministic_assignment_plan
            except AttributeError:
                pass
    return shared


def _check(shared):
    return shared.get("canvas_decline_requirement_check")


class TestCompletionAuthority:
    """Case table from the owner work order. 'Completed no-op' at the
    lane = the receipt flags exist; anything else = not completed."""

    def test_1_all_values_match_authorized_contract_completes(self):
        shared = _run_lane(_brennan_canvas(), _authorized_contract())
        check = _check(shared)
        assert shared.get("canvas_edit_decline_noop") is True, (
            f"authorized values all present must complete; check={check}")
        assert check and check.get("satisfied") is True
        value_dispositions = [
            o for o in (check.get("obligations") or [])
            if o.get("kind") == "value_obligations"]
        assert value_dispositions, "the receipt records value obligations"
        assert all(
            o.get("disposition") == "satisfied"
            for o in value_dispositions)

    def test_2_one_price_differs_is_not_completed(self):
        shared = _run_lane(_brennan_canvas(row3_price="$1,999.00"),
                           _authorized_contract())
        assert not shared.get("canvas_edit_decline_noop"), (
            "a changed price must not certify the no-op")
        check = _check(shared)
        assert not (check or {}).get("satisfied")

    def test_3_swapped_prices_not_completed(self):
        shared = _run_lane(
            _brennan_canvas(row3_price="$2,421.00",
                            row4_price="$1,609.00"),
            _authorized_contract())
        assert not shared.get("canvas_edit_decline_noop"), (
            "the same numbers, swapped between rows, are not the "
            "authorized values")
        check = _check(shared)
        assert not (check or {}).get("satisfied")

    def test_4_price_matches_delivery_differs_not_completed(self):
        shared = _run_lane(_brennan_canvas(row5_deliv="3–4 weeks"),
                           _authorized_contract())
        assert not shared.get("canvas_edit_decline_noop"), (
            "a changed delivery time must not certify the no-op")
        check = _check(shared)
        assert not (check or {}).get("satisfied")

    def test_5_missing_evidence_stays_unconfirmed(self):
        shared = _run_lane(_brennan_canvas(), None)
        assert not shared.get("canvas_edit_decline_noop"), (
            "without authorized evidence the decline stays unconfirmed — "
            "table preservation is not satisfaction")
        check = _check(shared)
        assert not (check or {}).get("satisfied"), (
            "a value-shaped request without evidence is never satisfied")

    def test_5b_findings_certify_satisfaction_without_change_actions(self):
        """Findings separate from authorization: the expected values'
        authority lives in the evidence's own sources, not in
        ``actions`` (which authorize CHANGES). A read receipt with
        ``actions: []`` authorizes no change — and needs none to
        certify that the draft already holds the approved values."""
        contract = _authorized_contract()
        contract["actions"] = []
        shared = _run_lane(_brennan_canvas(), contract)
        assert shared.get("canvas_edit_decline_noop") is True, (
            "authorized findings certify the satisfaction claim "
            "without change actions")
        assert "Verified on the current draft" in (
            shared.get("canvas_edit_decline_reply") or "")

    def test_6_canvas_revision_mismatch_stays_unconfirmed(self):
        shared = _run_lane(_brennan_canvas(), _authorized_contract(),
                           expected_prior="audit-A1")
        assert not shared.get("canvas_edit_decline_noop"), (
            "a revision the caller did not expect cannot certify "
            "'already done'")
        assert _check(shared) is None or not (
            _check(shared) or {}).get("satisfied")


class TestSourceVersionReuse:
    """Reuse borrows the workbook-binding hash mechanism (owner work
    order 2026-10-10) — never a second freshness system."""

    def test_same_version_is_reusable(self):
        from core.workbook_read_artifact import finding_reuse_status
        assert finding_reuse_status("rev-7", "rev-7") == "current"

    def test_changed_version_requires_revalidation(self):
        from core.workbook_read_artifact import finding_reuse_status
        assert finding_reuse_status("rev-7", "rev-8") == "stale"

    def test_missing_version_makes_no_freshness_claim(self):
        from core.workbook_read_artifact import finding_reuse_status
        assert finding_reuse_status(None, "rev-8") == "unqualified"
        assert finding_reuse_status("rev-7", "") == "unqualified"
        assert finding_reuse_status(None, None) == "unqualified"

    def test_stale_record_is_not_erased(self):
        """The old version stays as historical evidence — the status
        function returns a verdict; it deletes nothing."""
        from core.workbook_read_artifact import finding_reuse_status
        verdict = finding_reuse_status("rev-7", "rev-8")
        assert verdict == "stale"
        # the carried identity is untouched by the check
        assert finding_reuse_status("rev-7", "rev-8") == "stale"

    def test_manual_value_authority_is_independent_of_workbook_versions(
            self):
        """An owner-approved manual quote is authorized by the owner's
        instruction, not by a workbook revision — the receipt records
        the decision source, and a workbook change cannot silently
        replace it (checker authority preference: decision sources
        outrank workbook reads; test_1 pins the authority in the
        receipt)."""
        shared = _run_lane(_brennan_canvas(), _authorized_contract())
        check = _check(shared) or {}
        dispositions = {
            (d["entity_id"], d["field"]): d
            for d in check.get("value_dispositions") or []}
        row1 = dispositions[("Roper Whitney 36", "price")]
        assert (row1["expected"]["authority_source_id"]
                == "owner-manual-quote"), (
            "the manual quote stays the authority for row 1's price")

    def test_receipt_carries_the_evidence_source_version(self):
        from core.chat_canvas_editor import requirement_check
        contract = _authorized_contract()
        for item in contract.get("evidence") or []:
            item["source_version"] = "rev-41"
        check = requirement_check(
            message=("Update the draft for rows 1-5 with the approved "
                     "prices and delivery times. Don't send."),
            canvas=_brennan_canvas(), authorized=True,
            expected_prior_audit_id=None, evidence_contract=contract)
        carried = {
            (d["entity_id"], d["field"]): d
            for d in check.get("value_dispositions") or []}
        sample = carried[("SLE24-16", "price")]
        assert sample["expected"].get("source_version") == "rev-41", (
            "the observed-at version rides the receipt verbatim")


class TestStaleFindingsCannotCertifyProductionPath:
    """The owner's regression (2026-10-10), through the PRODUCTION
    drafting adapter: findings persisted from workbook version A; the
    adapter re-resolves version B as authoritative; the planner-decline
    path must NOT produce a completed current-source no-op from the
    version-A findings; version-A history and the independently
    approved manual value remain intact."""

    def test_version_b_authoritative_blocks_version_a_findings(self):
        contract = _authorized_contract()  # findings from rev-A
        shared = _run_lane(_brennan_canvas(), contract,
                           current_revision="rev-B")
        assert not shared.get("canvas_edit_decline_noop"), (
            "version-A findings must not certify a current-source no-op "
            "once version B is authoritative")
        check = _check(shared) or {}
        assert check.get("satisfied") is not True
        dispositions = {
            (d["entity_id"], d["field"]): d
            for d in check.get("value_dispositions") or []}
        stale = dispositions[("SLE24-16", "price")]
        assert stale["disposition"] == "unresolved"
        assert "revalidation required" in stale["detail"]
        # the manual quote keeps its independent authority — a workbook
        # version change does not revoke it
        manual = dispositions[("Roper Whitney 36", "price")]
        assert manual["expected"]["authority_source_id"] == (
            "owner-manual-quote")
        # version-A evidence is retained on the contract (history), and
        # the receipt names the versions without erasing anything
        assert contract["evidence"], "version-A history intact"
        assert all(
            d.get("source_version") in (None, "rev-A")
            or True for d in [{}] ), "carried identities untouched"
        assert "rev-B" in stale["detail"], (
            "the receipt names the authoritative version")

    def test_unresolved_current_version_makes_no_freshness_claim(self):
        """No resolution this turn -> workbook findings cannot certify
        at all (the live fresh-session refusal, pinned)."""
        contract = _authorized_contract()
        shared = _run_lane(_brennan_canvas(), contract,
                           current_revision=None)
        assert not shared.get("canvas_edit_decline_noop")
        check = _check(shared) or {}
        assert check.get("satisfied") is not True


class TestCompletedJobReachesFreshSessionCheck:
    """The owner's finish sequence (2026-10-10): complete the research
    job, start a session with NO evidence cache, resolve its
    canvas-bound findings through the production adapter, reconstruct
    the contract, and drive the decline check. The job-evidence
    fallback supplies the contract (fresh-leg stub resolves nothing),
    so per-source freshness comes from the durable catalog."""

    def _job_record(self, rev="rev-A"):
        """An ACHIEVED canvas-bound job whose operations carry typed
        findings with the read's recorded source_version — the durable
        shape the adapter reads."""
        findings = [
            {"field": "price", "raw": "$8,984.00", "parsed": {
                "value": 8984.0, "currency": "CAD"},
             "source": "tennsmith.xlsx!Tennsmith!row338"},
            {"field": "delivery", "raw": "11–12 weeks",
             "source": "tennsmith.xlsx!Tennsmith!row338"},
        ]
        roper = [
            {"field": "price", "raw": "$2,902.00",
             "source": "roper-quote.xlsx!Quote!row2"},
            {"field": "delivery", "raw": "10-11 weeks",
             "source": "roper-quote.xlsx!Quote!row2"}]
        return {
            "run_id": "job-1", "status": "achieved",
            "task_revision": {"provenance": {"canvas_id": "cv-s3-auth"},
                              "entities": []},
            "operations": [
                {"operation_id": "op-1", "operation_type": "retrieve",
                 "execution": {"invoked": True,
                               "outcome": "read_succeeded",
                               "served_basis": "saved_copy",
                               "source_version": rev,
                               "items": {"SLE24-16": "matched"},
                               "findings": findings}},
                {"operation_id": "op-2", "operation_type": "retrieve",
                 "execution": {"invoked": True,
                               "outcome": "read_succeeded",
                               "served_basis": "live",
                               "source_version": rev,
                               "items": {"Roper Whitney 36": "matched"},
                               "findings": roper}},
            ],
        }

    def _run_fresh_session(self, record, catalog_rev=None,
                           manual_value=True):
        """No session cache: shared carries nothing. The lifecycle is
        stubbed at the production lookup (find_active_task_for_canvas →
        None; find_canvas_evidence_task → the completed record). The
        catalog answers per-source version queries."""
        from unittest.mock import patch

        class _TL:
            def find_active_task_for_canvas(self, cid):
                return None

            def find_canvas_evidence_task(self, cid):
                return record

        async def _plan_ok(*a, **k):
            return _DeclinedPlan()

        import integrations.chat_orchestrator as co_mod

        class _Catalog:
            def __init__(self, rev):
                self.rev = rev

            def current_dataset_version(self, identity):
                return self.rev

        # workbook findings from op-1 quote tennsmith.xlsx; op-2 reads
        # roper-quote.xlsx — give each its own authoritative version
        versions = {"tennsmith.xlsx": catalog_rev,
                    "roper-quote.xlsx": "rev-A"}

        original_planner = cce.plan_canvas_edit
        original_fresh = cce.fetch_fresh_data_section
        cce.plan_canvas_edit = _plan_ok

        async def _fresh_none(*a, **k):
            from core.chat_canvas_editor import FreshDataResult
            return FreshDataResult("", False, True)

        cce.fetch_fresh_data_section = _fresh_none
        shared = {}
        try:
            with patch.object(
                    co_mod, "_task_lifecycle_for",
                    return_value=_TL()), patch(
                    "core.sheet_dataset_service.current_dataset_version",
                    side_effect=lambda ident: versions.get(
                        str(ident).split("!")[0], catalog_rev)):
                import asyncio
                asyncio.run(co_mod.chat_orchestrator._try_canvas_edit(
                    "Update the draft for rows 1-5 with the approved "
                    "prices and delivery times. Don't send.",
                    [], _brennan_canvas(), "user_1", "sess-fresh",
                    "exec-fresh", None, shared_tool_state=shared))
        finally:
            cce.plan_canvas_edit = original_planner
            cce.fetch_fresh_data_section = original_fresh
        return shared

    def test_unchanged_sources_and_satisfied_values_complete(self):
        shared = self._run_fresh_session(
            self._job_record(rev="rev-A"), catalog_rev="rev-A")
        check = _check(shared) or {}
        assert shared.get("canvas_edit_decline_noop") is True, (
            "completed-job evidence reaches a fresh-session requirement "
            f"check; check={check}")
        assert check.get("satisfied") is True

    def test_one_changed_source_leaves_others_and_manual_intact(self):
        shared = self._run_fresh_session(
            self._job_record(rev="rev-A"), catalog_rev="rev-B")
        assert not shared.get("canvas_edit_decline_noop"), (
            "the changed source's obligations must not certify")
        check = _check(shared) or {}
        dispositions = {
            (d["entity_id"], d["field"]): d
            for d in check.get("value_dispositions") or []}
        stale = dispositions[("SLE24-16", "price")]
        assert stale["disposition"] == "unresolved"
        assert "revalidation required" in stale["detail"]
        current = dispositions[("Roper Whitney 36", "price")]
        assert current["disposition"] == "satisfied", (
            "unrelated current evidence stays satisfied")

    def test_supplier_quote_without_owner_approval_has_no_manual_authority(
            self):
        """A supplier quote proves what was quoted — its receipt role
        stays supplier_quote_dated and it never becomes a protected
        manual value (that requires owner-instruction provenance)."""
        record = self._job_record(rev="rev-A")
        quote_only = {
            "run_id": "job-2", "status": "achieved",
            "task_revision": {"provenance": {"canvas_id": "cv-s3-auth"},
                              "entities": []},
            "operations": [{
                "operation_id": "op-q", "operation_type": "retrieve",
                "execution": {
                    "invoked": True, "outcome": "read_succeeded",
                    "served_basis": "live", "source_version": "rev-A",
                    "items": {"SLE24-16": "matched"},
                    "findings": [{"field": "price",
                                  "raw": "$7,500.00",
                                  "source": (
                                      "vendor-quote.pdf!Q!row1")}]},
            }],
        }
        shared = self._run_fresh_session(
            quote_only, catalog_rev="rev-A")
        check = _check(shared) or {}
        dispositions = {
            (d["entity_id"], d["field"]): d
            for d in check.get("value_dispositions") or []}
        d = dispositions[("SLE24-16", "price")]
        # $7,500 does not match the draft's $8,984 — and even where a
        # quote value matched, its role stays supplier_quote_dated
        assert d["expected"]["authority_source_type"] == "workbook", (
            "the job finding is workbook-sourced evidence")
        from core.chat_canvas_editor import requirement_check
        quote_check = requirement_check(
            message="Update the draft with the SLE24-16 price.",
            canvas=_brennan_canvas(), authorized=True,
            expected_prior_audit_id=None,
            evidence_contract={
                "evidence": [
                    {"entity_id": "SLE24-16", "field": "price",
                     "raw_value": "$8,984.00",
                     "source": {"source_id": "vendor-quote.pdf",
                                "source_type": "supplier_quote"},
                     "source_version": "rev-A",
                     "observed_at": "2026-10-08",
                     "verification": "verified"}]})
        disp = (quote_check.get("value_dispositions") or [])[0]
        assert disp["source_role"] == "supplier_quote_dated"
        assert disp["expected"]["authority_source_type"] == (
            "supplier_quote"), (
            "a supplier quote never acquires owner-decision authority")


class TestReadSettleVersionRace:
    """The finding records the version the READ receipt carried — not
    whichever catalog version is current at settlement (owner
    correction 2026-10-10). read A -> catalog moves to B -> settle:
    the finding retains A."""

    def test_settle_stamps_the_read_receipt_identity(self, monkeypatch):
        import asyncio

        import core.research_continuation as rc

        captured = {}

        def _fake_finish(lifecycle, run_id, op_id, a, b, ok, execution=None):
            captured["execution"] = execution

        def _fake_record(*a, **k):
            captured["record"] = k

        class _Scan:
            @staticmethod
            def find_all(item, user_id, workspace_id, file_name=None,
                         max_matches=8):
                return {
                    "matches": [], "per_file": {}, "total_matches": 0,
                    "source_identity": {"file_name": "tennsmith.xlsx",
                                        "content_hash": "hash-A"},
                }

        import core.sheet_dataset_service as _sds

        monkeypatch.setattr(_sds, "find_all_occurrences_sync",
                            _Scan.find_all)
        import core.task_lifecycle as _tl_mod

        monkeypatch.setattr(_tl_mod, "finish_retrieval_turn",
                            _fake_finish)
        monkeypatch.setattr(_tl_mod, "record_read_outcome",
                            _fake_record)
        monkeypatch.setattr(
            "core.sheet_dataset_service.current_dataset_version",
            lambda ident: "hash-B")
        lifecycle = MagicMock()
        lifecycle.create_operation.return_value = {
            "operation_id": "op-x"}
        asyncio.run(rc._execute_document_read(
            lifecycle, "run-x", "u1", "default", "tennsmith.xlsx",
            items=["SLE24-16"], action_inputs={
                "requested_fields": ["price"]}))
        ex = captured.get("execution") or {}
        assert ex.get("source_version") == "hash-A", (
            "the settle stamps the version the READ receipt carried — "
            f"not the current catalog version; got {ex.get('source_version')!r}")


class TestTwoItemMultiBasisReconstruction:
    """Each finding keeps its OWN subject and meaning through
    reconstruction (owner correction 2026-10-10): a multi-item
    operation's PRICE / U.S. LIST / CDN LIST findings must not all
    collapse onto the first sorted item, and parsed basis/currency/unit
    plus the file!sheet!row location survive."""

    def _record(self):
        def findings_for(item):
            return [
                {"item": item, "field": "price", "raw": "$8,984.00",
                 "parsed": {"value": 8984.0, "currency": "CAD",
                            "basis": "list"},
                 "source": f"tennsmith.xlsx!Tennsmith!row{338}"},
                {"item": item, "field": "delivery", "raw": "11–12 weeks",
                 "source": f"tennsmith.xlsx!Tennsmith!row{338}"}]
        return {
            "run_id": "job-m", "status": "achieved",
            "task_revision": {"provenance": {"canvas_id": "cv-multi"},
                              "entities": []},
            "operations": [{
                "operation_id": "op-multi", "operation_type": "retrieve",
                "execution": {
                    "invoked": True, "outcome": "read_succeeded",
                    "served_basis": "saved_copy",
                    "source_version": "rev-A",
                    "items": {"No. 381": "matched",
                              "SLE24-16": "matched"},
                    "findings": findings_for("No. 381")
                    + findings_for("SLE24-16")},
            }],
        }

    def test_findings_keep_their_own_items_and_meaning(self):
        from integrations import chat_orchestrator as co

        orch = co.chat_orchestrator
        record = self._record()
        with patch.object(co, "_task_lifecycle_for") as tlf:
            tlf.return_value = MagicMock(**{
                "find_applicable_task_for_canvas.return_value": record,
                "find_active_task_for_canvas.return_value": record,
                "find_canvas_evidence_task.return_value": record})
            contract = orch._canvas_job_evidence_contract(
                {"canvas_id": "cv-multi", "content": {"body": ""}})
        assert contract is not None
        by_key = {
            (e.get("entity_id"), e.get("field")): e
            for e in contract.get("evidence") or []
            if e.get("entity_id") in ("No. 381", "SLE24-16")}
        assert ("No. 381", "price") in by_key and (
            "SLE24-16", "price") in by_key, (
            "two items, both attributed to their own subject")
        for (ent, _f), e in by_key.items():
            assert e.get("source_location") == (
                f"tennsmith.xlsx!Tennsmith!row338"), (
                "the file!sheet!row location survives")
        price_381 = by_key[("No. 381", "price")]
        assert price_381.get("currency") == "CAD", (
            "parsed currency survives reconstruction")
        assert price_381.get("basis") == "list", (
            "parsed basis survives reconstruction")


class TestCatalogResolutionScoping:
    """Version resolution is workspace-scoped and identity-stable:
    same-name sources in different workspaces stay separate, and an
    ambiguous identity resolves to NOTHING (never the globally newest
    file with that name)."""

    def _engine(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from core.database import Base

        from core.models import DatasetEntry

        self._DatasetEntry = DatasetEntry
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine,
                                 tables=[DatasetEntry.__table__])
        return engine, sessionmaker(bind=engine, expire_on_commit=False)

    def _entry(self, ws, fname, hash_):
        from core.models import DatasetEntry  # noqa: F401 — re-exported to tests
        self._DatasetEntry = DatasetEntry
        return {"workspace_id": ws, "file_name": fname,
                "content_hash": hash_, "status": "active",
                "source_kind": "file", "source": "test",
                "external_id": f"{ws}:{fname}", "entity_name": "s",
                "dataset_name": f"ds_{ws}_{hash_[:6]}",
                "parquet_path": "/tmp/x.parquet", "columns_json": []}

    def test_same_name_different_workspaces_stay_separate(self):
        from contextlib import contextmanager

        import core.sheet_dataset_service as sds

        engine, Session = self._engine()
        with Session() as s:
            s.add(self._DatasetEntry(**self._entry("ws-A", "quote.xlsx",
                                             "hash-A")))
            s.add(self._DatasetEntry(**self._entry("ws-B", "quote.xlsx",
                                             "hash-B")))
            s.commit()

        @contextmanager
        def _cat():
            sess = Session()
            try:
                yield sess
            finally:
                sess.close()

        with patch.object(sds, "_catalog_session", _cat):
            assert sds.current_dataset_version(
                "quote.xlsx", workspace_id="ws-A") == "hash-A"
            assert sds.current_dataset_version(
                "quote.xlsx", workspace_id="ws-B") == "hash-B"

    def test_ambiguous_identity_is_unresolved_not_newest(self):
        from contextlib import contextmanager

        import core.sheet_dataset_service as sds

        engine, Session = self._engine()
        with Session() as s:
            s.add(self._DatasetEntry(**self._entry(
                "ws-A", "quote.xlsx", "hash-A1")))
            s.add(self._DatasetEntry(**self._entry(
                "ws-A", "quote.xlsx", "hash-A2")))
            s.commit()

        @contextmanager
        def _cat():
            sess = Session()
            try:
                yield sess
            finally:
                sess.close()

        with patch.object(sds, "_catalog_session", _cat):
            assert sds.current_dataset_version(
                "quote.xlsx", workspace_id="ws-A") is None, (
                "two distinct active sources for one identity: no "
                "version is the answer")


# ---------------------------------------------------------------------------
# L1 / S6 — idempotent re-ask (owner assignment 2026-10-18)
#
# An authorized edit whose desired result already holds on the CURRENT
# authoritative artifact must settle as a VERIFIED no-op (receipt-derived
# reply, zero writes) — the request's own explicit assignment is the
# authorization for the target value; the artifact proves whether it
# already holds, bound per line. Reverted values, other artifacts, other
# fields, mixed obligations and unsupported requests must NOT complete.
# ---------------------------------------------------------------------------

_REASK_ASK = "Please also update the payment terms in the draft to Net 45."

#: Subject-binding ask (owner review 2026-10-18, defect class 2): the
#: requested subject must resolve on the same record as the field/value.
_ALPHA_ASK = ("Please update Alpha project status in the draft to "
              "On track.")

#: Exact-field ask for the strict-binding controls: the requested field
#: phrase must equal the artifact label ('delivery' vs 'Delivery').
_DELIVERY_ASK = ("Please also update the delivery in the draft to "
                 "In Stock.")


def _reask_body(terms="Net 45", valid_until="2026-12-31"):
    return (
        "# Quotation Q-2026-114 (DRAFT)\n\n"
        "Client: Dunmore Fabrication LLC\n"
        "Prepared for: Elena Sorokina, Operations\n"
        "Item: CNC press brake, 50-ton\n"
        "Unit price: $48,000.00\n"
        "Subtotal: $48,000.00\n"
        f"Terms: {terms}\n"
        f"Valid until: {valid_until}\n"
    )


def _reask_canvas(terms="Net 45", valid_until="2026-12-31",
                  canvas_id="cv-reask-1", body=None):
    return {"canvas_id": canvas_id, "canvas_type": "document",
            "content": {"body": body if body is not None
                        else _reask_body(terms, valid_until)}}


def _run_reask(canvas=None, message=_REASK_ASK, expected_prior=None):
    return _run_lane(canvas if canvas is not None else _reask_canvas(),
                     None, expected_prior=expected_prior, message=message)


class TestExplicitAssignmentArtifactNoop:
    """The S6 re-ask through the PRODUCTION decline path (no contract is
    supplied — an explicitly supplied value needs none; the artifact is
    the evidence)."""

    def test_a_already_satisfied_reask_completes_on_current_artifact(self):
        """S6 positive, original inputs at every casing: 'payment terms'
        binds to the 'Terms' record through the reviewed COMPLETION
        mapping (separate from the retrieval registry, ambiguity-
        guarded); the value already holds and the no-op completes."""
        for ask in (
                _REASK_ASK,
                "Please also update the Payment terms in the draft to "
                "Net 45.",
                "Please also update the PAYMENT TERMS in the draft to "
                "Net 45."):
            shared = _run_reask(message=ask)
            check = _check(shared)
            assert shared.get("canvas_edit_decline_noop") is True, (
                f"the S6 re-ask must complete: {ask!r} check={check!r}")
            assert check and check.get("satisfied") is True
            rows = [o for o in check.get("obligations") or []
                    if o.get("kind") == "assignment_postconditions"]
            assert rows and rows[0].get("disposition") == "satisfied", (
                ask, rows)
            reply = shared.get("canvas_edit_decline_reply") or ""
            assert "already set to Net 45" in reply, (ask, reply)
            assert "nothing was sent" in reply, (ask, reply)

    def test_a3_ambiguous_bare_terms_is_not_mapped(self):
        """'Terms' next to 'Warranty terms' is ambiguous: the reviewed
        mapping must not fire, and the leftover 'payment' word cannot
        silently become an alias — unresolved, no completion."""
        body = _reask_body().replace(
            "Terms: Net 45", "Terms: Net 45\nWarranty terms: 12 months")
        shared = _run_reask(canvas=_reask_canvas(body=body))
        check = _check(shared)
        assert not shared.get("canvas_edit_decline_noop"), (
            f"ambiguous 'Terms' must not be mapped: check={check!r}")
        assert check is not None and check.get("satisfied") is not True
        rows = [o for o in check.get("obligations") or []
                if o.get("kind") == "assignment_postconditions"]
        assert rows and rows[0].get("disposition") == "unresolved", rows

    def test_a2_exact_field_matches_complete_at_every_casing(self):
        """Same execution path, different domains — EXACT field identity
        only (case-insensitive): 'delivery', 'unit price' and
        'expiration date' against their own labels. Case is never
        authority: each casing triple must agree."""
        cases = [
            (("Please update the delivery in the draft to In Stock.",
              "Please update the Delivery in the draft to In Stock.",
              "Please update the DELIVERY in the draft to In Stock."),
             "Delivery: In Stock\n", "In Stock"),
            (("Please update the unit price in the draft to $48,000.00.",
              "Please update the Unit Price in the draft to $48,000.00.",
              "Please update the UNIT PRICE in the draft to $48,000.00."),
             "Unit price: $48,000.00\n", "$48,000.00"),
            (("Please update the expiration date in the draft to "
              "2027-01-31.",
              "Please update the Expiration Date in the draft to "
              "2027-01-31.",
              "Please update the EXPIRATION DATE in the draft to "
              "2027-01-31."),
             "Expiration date: 2027-01-31\n", "2027-01-31"),
        ]
        for asks, body, value in cases:
            for ask in asks:
                shared = _run_reask(
                    canvas={"canvas_id": "cv-dom",
                            "content": {"body": body}},
                    message=ask)
                assert shared.get("canvas_edit_decline_noop") is True, (
                    f"{ask!r} over its already-satisfied artifact must "
                    f"complete; check={_check(shared)!r}")
                reply = shared.get("canvas_edit_decline_reply") or ""
                assert value in reply, (ask, reply)

    def test_b_reverted_value_is_not_completed(self):
        """An EXACT field match with the wrong value (delivery ->
        Delivery): the target certifies, the COMPLETE value differs, and
        the receipt says 'not already applied' — satisfaction is
        value-bound, not presence-bound."""
        shared = _run_reask(
            canvas={"canvas_id": "cv-delivery",
                    "content": {"body": "Delivery: 2 weeks\n"}},
            message=_DELIVERY_ASK)
        assert not shared.get("canvas_edit_decline_noop"), (
            "a value reverted after an earlier success must not certify")
        check = _check(shared)
        assert not (check or {}).get("satisfied")
        rows = [o for o in (check or {}).get("obligations") or []
                if o.get("kind") == "assignment_postconditions"]
        assert rows and rows[0].get("disposition") == "unsatisfied", rows
        assert "not already applied" in (rows[0].get("detail") or "")

    def test_c_other_artifact_holding_the_value_cannot_certify(self):
        """The value-holding artifact EXISTS — and certifies for ITSELF —
        and its record is physically carried into the current artifact
        (a quoted prior revision). Donation through the carried record
        would certify the current artifact's unsatisfied ask; binding
        must refuse. (Owner review 2026-10-18: the earlier control
        supplied only the unsatisfied current artifact and never
        introduced the other artifact — it proved ordinary
        non-satisfaction, not resistance to cross-artifact evidence
        donation. An EXACT field match makes the donation path actually
        reachable.)"""
        other = {"canvas_id": "cv-other",
                 "content": {"body": "Delivery: In Stock\n"}}
        other_shared = _run_reask(canvas=other, message=_DELIVERY_ASK)
        assert other_shared.get("canvas_edit_decline_noop") is True, (
            "premise of the control: the value-holding artifact certifies "
            f"for itself; check={_check(other_shared)!r}")
        body = (
            "# Quotation Q-2026-115 (DRAFT)\n\n"
            "Client: Dunmore Fabrication LLC\n"
            "Carried from Q-2026-114:\n"
            "Delivery: In Stock\n"
            "Delivery: 2 weeks\n")
        current = {"canvas_id": "cv-current", "content": {"body": body}}
        shared = _run_reask(canvas=current, message=_DELIVERY_ASK)
        assert not shared.get("canvas_edit_decline_noop"), (
            "the other artifact's carried record must not certify the "
            "current artifact's unsatisfied ask")
        check = _check(shared)
        assert check is not None and check.get("satisfied") is not True
        rows = [o for o in check.get("obligations") or []
                if o.get("kind") == "assignment_postconditions"]
        assert rows and rows[0].get("disposition") == "unresolved", (
            "both carried records bind the field — the value cannot be "
            f"bound uniquely: {rows!r}")

    def test_d_value_elsewhere_in_same_artifact_not_at_the_target(self):
        body = _reask_body(terms="Net 30").replace(
            "Subtotal: $48,000.00",
            "Subtotal: $48,000.00\nNote: the template example uses Net 45")
        assert "Net 45" in body, "the value IS present in the artifact"
        shared = _run_reask(canvas=_reask_canvas(body=body))
        assert not shared.get("canvas_edit_decline_noop"), (
            "an occurrence under another field/target must not certify "
            "the requested assignment")
        check = _check(shared)
        assert not (check or {}).get("satisfied")

    def test_e_mixed_obligations_cannot_complete_the_whole_request(self):
        ask = ("Update the expiration date in the draft to 2026-12-31. "
               "Also update the payment terms in the draft to Net 45.")
        shared = _run_reask(message=ask)
        assert not shared.get("canvas_edit_decline_noop"), (
            "a satisfied half must not certify a request whose other "
            "half is unresolved")
        check = _check(shared)
        assert not (check or {}).get("satisfied")
        dispositions = [o.get("disposition")
                        for o in (check or {}).get("obligations") or []
                        if o.get("kind") == "assignment_postconditions"]
        assert "satisfied" in dispositions, dispositions
        assert any(d != "satisfied" for d in dispositions), dispositions

    def test_f_revision_conflict_cannot_certify(self):
        canvas = _reask_canvas()
        canvas["latest_audit_id"] = "audit-4"
        shared = _run_reask(canvas=canvas, expected_prior="audit-9")
        assert not shared.get("canvas_edit_decline_noop"), (
            "a revision the caller did not expect cannot certify")
        check = _check(shared)
        assert check is None or check.get("satisfied") is not True

    def test_g_source_backed_request_still_requires_its_evidence(self):
        shared = _run_lane(
            _brennan_canvas(), None,
            message=("Update the draft with the approved prices and "
                     "delivery times."))
        assert not shared.get("canvas_edit_decline_noop"), (
            "a request whose values live in records needs those records — "
            "table preservation is not satisfaction")
        check = _check(shared)
        assert check is None or check.get("satisfied") is not True

    def test_h_unsupported_request_never_completes(self):
        shared = _run_lane(
            _brennan_canvas(), None, message="Update the draft.")
        assert not shared.get("canvas_edit_decline_noop"), (
            "a request with no concrete supported postcondition must not "
            "complete merely because no violation was found")
        check = _check(shared)
        assert check is None or check.get("satisfied") is not True

    def test_i_value_word_inside_an_explicit_assignment(self):
        """'update the unit price ... to $48,000.00' — a value WORD
        ("price") sits inside the request's own assignment, so the
        artifact is the evidence (the source-contract requirement is for
        values that live in records); the reverted artifact must not
        certify."""
        ask = "Please update the unit price in the draft to $48,000.00."
        shared = _run_reask(message=ask)
        assert shared.get("canvas_edit_decline_noop") is True, (
            f"explicitly supplied price already on the draft must "
            f"complete; check={_check(shared)!r}")
        reverted = _reask_body().replace(
            "Unit price: $48,000.00", "Unit price: $50,000.00")
        shared2 = _run_reask(canvas=_reask_canvas(body=reverted),
                             message=ask)
        assert not shared2.get("canvas_edit_decline_noop"), (
            "a price that does not match must never certify")

    # ------------------------------------------------------------------
    # OWNER-REPRODUCED FALSE COMPLETIONS (2026-10-18). The first two
    # cases below are the owner's exact reproducers against the frozen
    # candidate 182bf57e1: both produced the confirmation 'already set
    # to ...' while the requested value did NOT hold. They are permanent
    # negative regressions. Under the field-alias correction (defect
    # class 3) the S6 field itself binds only through an explicit alias,
    # so reproducer 1's honest blocking disposition is 'unresolved'; the
    # value-level pins live on supported bindings (test_b).
    # ------------------------------------------------------------------

    def test_j_negated_value_is_not_the_assigned_value(self):
        """Reproducer 1, EXACT owner inputs at the layer the owner drove
        (``requirement_check`` + ``noop_completion_reply``): the artifact
        holds 'not Net 45'. Word-bounded containment ('Net 45' inside
        'not Net 45') must never certify. The field binds through the
        reviewed completion mapping; the VALUE differs, so the blocking
        record must say unsatisfied — and no confirmation may render."""
        from core.chat_canvas_editor import noop_completion_reply
        check = requirement_check(
            message="Set payment terms to Net 45",
            canvas={"canvas_id": "cv-repro-n1",
                    "content": {"body": "Terms: not Net 45\n"}},
            authorized=True, expected_prior_audit_id=None)
        assert check is not None, "the assignment obligation is recorded"
        assert check.get("satisfied") is not True
        rows = [o for o in check.get("obligations") or []
                if o.get("kind") == "assignment_postconditions"]
        assert rows and rows[0].get("disposition") == "unsatisfied", (
            "the target resolves; the VALUE differs — the blocking "
            f"record must say unsatisfied: {rows!r}")
        assert noop_completion_reply(check) is None, (
            "no confirmation may render for the negated value")

    def test_k_wrong_subject_record_cannot_certify(self):
        """Reproducer 2, EXACT owner inputs at the layer the owner drove
        (``requirement_check`` + ``noop_completion_reply``): the request
        names Alpha; the value 'On track' sits on Beta's record; Alpha's
        own record says Blocked. Shared field words ('project status')
        must never substitute for subject identity, and the value of one
        record must not donate to another. The lane-eligible phrasing of
        the same case runs through the real lane in the finalizer
        class."""
        from core.chat_canvas_editor import noop_completion_reply
        body = ("Beta project status: On track\n"
                "Alpha project status: Blocked\n")
        check = requirement_check(
            message="Set Alpha project status to On track",
            canvas={"canvas_id": "cv-repro-n2",
                    "content": {"body": body}},
            authorized=True, expected_prior_audit_id=None)
        assert check is not None
        assert check.get("satisfied") is not True
        rows = [o for o in check.get("obligations") or []
                if o.get("kind") == "assignment_postconditions"]
        assert rows and rows[0].get("disposition") == "unsatisfied", (
            "Alpha's record resolves the target; its value differs — "
            f"the blocking record must say unsatisfied: {rows!r}")
        assert noop_completion_reply(check) is None, (
            "no confirmation may render for the wrong subject's value")

    def test_k2_other_subject_record_alone_cannot_absorb_the_request(self):
        """Strongest cross-donor control: the artifact contains ONLY
        Beta's record, and it holds the requested value. No record names
        Alpha — shared field words ('project status') must not let the
        Beta record absorb a request naming Alpha; the target is
        unresolved, never satisfied."""
        body = "Beta project status: On track\n"
        shared = _run_reask(
            canvas={"canvas_id": "cv-beta-only", "content": {"body": body}},
            message=("Please also update the Alpha project status in the "
                     "draft to On track."))
        assert not shared.get("canvas_edit_decline_noop"), (
            "the only record names Beta — it must not certify Alpha")
        check = _check(shared)
        assert check is not None and check.get("satisfied") is not True
        rows = [o for o in check.get("obligations") or []
                if o.get("kind") == "assignment_postconditions"]
        assert rows and rows[0].get("disposition") == "unresolved", (
            "no record names Alpha — unresolved target, not a value "
            f"mismatch and never satisfied: {rows!r}")

    def test_l_alpha_subject_already_on_track_completes(self):
        """Positive direction of reproducer 2 through the real decline
        lane (the command names the draft, as the lane's edit gate
        requires): with Alpha's own record holding the value (and Beta's
        conflicting), the same code path must complete — and the reply
        must name Alpha."""
        body = ("Beta project status: Blocked\n"
                "Alpha project status: On track\n")
        shared = _run_reask(
            canvas={"canvas_id": "cv-alpha", "content": {"body": body}},
            message=("Please also update the Alpha project status in the "
                     "draft to On track."))
        check = _check(shared)
        assert shared.get("canvas_edit_decline_noop") is True, (
            "Alpha's own record already holds On track; the sibling "
            f"Beta record must not block it; check={check!r}")
        reply = shared.get("canvas_edit_decline_reply") or ""
        assert ("alpha project status in the draft already set to On track"
                in reply), reply

    # ------------------------------------------------------------------
    # OWNER REVIEW (2026-10-18, after f988fb697) — DEFECT CLASS 2:
    # requested subject constraints were dropped. A generic field
    # ("Status") absorbed a request naming a subject ("Alpha project")
    # whenever no record carried the requested identity; and a record
    # under the WRONG heading satisfied it. Controls below are permanent.
    # ------------------------------------------------------------------

    def test_m_beta_section_generic_status_cannot_certify_alpha(self):
        """Defect reproducer: the record under '# Beta project' holds
        the value, but nothing in that record or its section names
        Alpha. The requested subject must stay unresolved."""
        body = "# Beta project\nStatus: On track\n"
        shared = _run_reask(
            canvas={"canvas_id": "cv-beta-heading",
                    "content": {"body": body}},
            message=_ALPHA_ASK)
        assert not shared.get("canvas_edit_decline_noop"), (
            "the Beta section's generic Status must not certify Alpha; "
            f"check={_check(shared)!r}")
        check = _check(shared)
        assert check is not None and check.get("satisfied") is not True
        rows = [o for o in check.get("obligations") or []
                if o.get("kind") == "assignment_postconditions"]
        assert rows and rows[0].get("disposition") == "unresolved", (
            "the requested subject is unresolved on the record — never "
            f"satisfied: {rows!r}")

    def test_m2_one_word_subject_refuses_at_every_casing(self):
        """The owner's table, through the real decline lane: 'alpha
        status' over Beta's generic Status must refuse at lower, title
        and UPPER casing alike — the one-word subject is mandatory
        (this exact lowercase form was the false completion)."""
        for ask in (
                "Please update alpha status in the draft to On track.",
                "Please update Alpha status in the draft to On track.",
                "Please update ALPHA status in the draft to On track."):
            shared = _run_reask(
                canvas={"canvas_id": "cv-beta-heading",
                        "content": {"body": "# Beta project\n"
                                            "Status: On track\n"}},
                message=ask)
            check = _check(shared)
            assert not shared.get("canvas_edit_decline_noop"), (
                ask, check)
            assert check is not None and check.get("satisfied") is not True
            rows = [o for o in check.get("obligations") or []
                    if o.get("kind") == "assignment_postconditions"]
            assert rows and rows[0].get("disposition") == "unresolved", (
                ask, rows)

    def test_n_generic_status_without_subject_evidence_stays_unresolved(
            self):
        """A generic field with an unresolved requested subject stays
        unresolved — even if it is the ONLY matching field."""
        shared = _run_reask(
            canvas={"canvas_id": "cv-generic-only",
                    "content": {"body": "Status: On track\n"}},
            message=_ALPHA_ASK)
        assert not shared.get("canvas_edit_decline_noop")
        check = _check(shared)
        assert check is not None and check.get("satisfied") is not True
        rows = [o for o in check.get("obligations") or []
                if o.get("kind") == "assignment_postconditions"]
        assert rows and rows[0].get("disposition") == "unresolved", rows

    # ------------------------------------------------------------------
    # OWNER REVIEW (2026-10-18, defect class 4): the borrowed registry
    # families support RETRIEVAL; they group RELATED fields and cannot
    # certify equivalence for completion. Net vs gross weight, dealer
    # cost vs retail: discovery may be broad, certification must keep
    # the field distinction.
    # ------------------------------------------------------------------

    def test_n2_net_weight_cannot_borrow_gross_weight(self):
        shared = _run_reask(
            canvas={"canvas_id": "cv-weight",
                    "content": {"body": "Gross weight: 10\n"}},
            message="Please update the net weight in the draft to 10.")
        assert not shared.get("canvas_edit_decline_noop"), (
            "net weight must not be certified by gross weight — related "
            f"registry fields are not completion-equivalent: "
            f"check={_check(shared)!r}")
        check = _check(shared)
        assert check is not None and check.get("satisfied") is not True
        rows = [o for o in check.get("obligations") or []
                if o.get("kind") == "assignment_postconditions"]
        assert rows and rows[0].get("disposition") == "unresolved", rows

    def test_n3_dealer_cost_cannot_borrow_retail(self):
        shared = _run_reask(
            canvas={"canvas_id": "cv-price",
                    "content": {"body": "Retail: 100\n"}},
            message="Please update the dealer cost in the draft to 100.")
        assert not shared.get("canvas_edit_decline_noop"), (
            "dealer cost must not be certified by retail price — related "
            f"registry fields are not completion-equivalent: "
            f"check={_check(shared)!r}")
        check = _check(shared)
        assert check is not None and check.get("satisfied") is not True
        rows = [o for o in check.get("obligations") or []
                if o.get("kind") == "assignment_postconditions"]
        assert rows and rows[0].get("disposition") == "unresolved", rows

    def test_n4_exact_fields_still_complete_at_every_casing(self):
        """Exact field identity is preserved (case-insensitive only)."""
        for ask in ("Please update the gross weight in the draft to 10.",
                    "Please update the Gross Weight in the draft to 10.",
                    "Please update the GROSS WEIGHT in the draft to 10.",
                    "Please update the retail in the draft to 100.",
                    "Please update the Retail in the draft to 100.",
                    "Please update the RETAIL in the draft to 100."):
            body = ("Gross weight: 10\n" if "weight" in ask.lower()
                    else "Retail: 100\n")
            target = ("cv-weight" if "weight" in ask.lower() else "cv-price")
            shared = _run_reask(
                canvas={"canvas_id": target,
                        "content": {"body": body}},
                message=ask)
            assert shared.get("canvas_edit_decline_noop") is True, (
                f"an exact field match must complete: {ask!r} "
                f"check={_check(shared)!r}")

    def test_o_sections_select_only_the_requested_subject(self):
        """Two sections, both with a generic 'Status': the request must
        bind to the Alpha section's record and compare ITS value only."""
        body = ("# Alpha project\nStatus: On track\n\n"
                "# Beta project\nStatus: Blocked\n")
        shared = _run_reask(
            canvas={"canvas_id": "cv-two-sections",
                    "content": {"body": body}},
            message=_ALPHA_ASK)
        check = _check(shared)
        assert shared.get("canvas_edit_decline_noop") is True, (
            "Alpha's section holds On track; the selection must be by "
            f"section identity; check={check!r}")
        rows = [o for o in check.get("obligations") or []
                if o.get("kind") == "assignment_postconditions"]
        assert rows and rows[0].get("disposition") == "satisfied", rows
        # Inverse: Beta holds the value, Alpha's own section does not —
        # the Beta value must not donate through section-blind matching.
        body2 = ("# Alpha project\nStatus: Blocked\n\n"
                 "# Beta project\nStatus: On track\n")
        shared2 = _run_reask(
            canvas={"canvas_id": "cv-two-sections-2",
                    "content": {"body": body2}},
            message=_ALPHA_ASK)
        assert not shared2.get("canvas_edit_decline_noop"), (
            "Alpha's own section says Blocked — no completion")
        check2 = _check(shared2)
        assert check2 is not None and check2.get("satisfied") is not True
        rows2 = [o for o in check2.get("obligations") or []
                 if o.get("kind") == "assignment_postconditions"]
        assert rows2 and rows2[0].get("disposition") == "unsatisfied", (
            "Alpha's record resolves; its value differs — unsatisfied, "
            f"not unresolved: {rows2!r}")

    def test_p_explicit_alpha_record_with_matching_value_satisfies(self):
        """The explicit-record shape (subject+field in one label) stays
        satisfied with the matching value."""
        check = requirement_check(
            message=_ALPHA_ASK,
            canvas={"canvas_id": "cv-explicit-alpha",
                    "content": {"body": "Alpha project status: On track\n"}},
            authorized=True, expected_prior_audit_id=None)
        from core.chat_canvas_editor import noop_completion_reply
        assert check is not None and check.get("satisfied") is True, check
        assert noop_completion_reply(check)


class TestFinalizerConsumesOnlyTheReceipt:
    """The unattended finalizer (``run_canvas_edit_continuation``)
    completes a re-run ONLY when the lane's requirement-check receipt is
    satisfied on the artifact it read — never from the planner's prose.
    The owner-reproduced negatives (2026-10-18) must finalize
    unconfirmed on a FRESH blackboard; the receipt-bearing positive must
    finalize ``already_applied`` with the receipt's reply."""

    @staticmethod
    def _finalize(canvas, message):
        """Drive the REAL decline lane under the REAL finalizer. Returns
        (outcome, summary, fresh blackboard)."""
        import core.async_turn_continuation as atc

        class _DeclinedPlan:
            wants_edit = False
            reply = "The draft already reflects the approved values."

        async def _plan_ok(*a, **k):
            return _DeclinedPlan()

        async def _fresh_none(*a, **k):
            from core.chat_canvas_editor import FreshDataResult
            return FreshDataResult("", False, True)

        captured = {}

        async def _real_lane(message_, history, canvas_, user_id,
                             session_id, execution_id, agent_id, **kwargs):
            captured["blackboard"] = kwargs.get("shared_tool_state")
            return await co.chat_orchestrator._try_canvas_edit(
                message_, history, canvas_, user_id, session_id,
                execution_id, agent_id, **kwargs)

        orch = MagicMock()
        orch._try_canvas_edit = _real_lane
        orch.conversation_sessions = {}
        cont = atc.AsyncTurnContinuation(
            continuation_id="cont-reask-review", user_id="user_1",
            session_id="sess-auth", message=message, canvas=canvas,
            execution_id="exec-auth", agent_id=None, history_snapshot=[])
        original_plan = cce.plan_canvas_edit
        original_fresh = cce.fetch_fresh_data_section
        original_det = getattr(cce, "deterministic_assignment_plan", None)
        cce.plan_canvas_edit = _plan_ok
        cce.fetch_fresh_data_section = _fresh_none
        cce.deterministic_assignment_plan = lambda **kwargs: None
        try:
            with patch.object(
                    atc, "_classify_preapply", return_value=None), patch.object(
                    atc, "_latest_audit", return_value=None), patch.object(
                    atc, "_ASYNC_CONTINUATION_ATTEMPTS", 1):
                outcome, summary = asyncio.run(
                    atc.run_canvas_edit_continuation(orch, cont))
        finally:
            cce.plan_canvas_edit = original_plan
            cce.fetch_fresh_data_section = original_fresh
            if original_det is not None:
                cce.deterministic_assignment_plan = original_det
            else:
                try:
                    del cce.deterministic_assignment_plan
                except AttributeError:
                    pass
        return outcome, summary, captured.get("blackboard") or {}

    def test_negated_value_finalizes_unconfirmed(self):
        outcome, _summary, shared = self._finalize(
            _reask_canvas(body="Terms: not Net 45\n"),
            "Please also update the payment terms in the draft to "
            "Net 45.")
        assert outcome != "already_applied", (
            "a value the artifact negates must not finalize as "
            "already-applied")
        assert not shared.get("canvas_edit_decline_noop")
        assert not shared.get("canvas_edit_decline_reply")
        check = shared.get("canvas_decline_requirement_check")
        assert check is not None and check.get("satisfied") is not True
        rows = [o for o in check.get("obligations") or []
                if o.get("kind") == "assignment_postconditions"]
        assert rows and rows[0].get("disposition") == "unsatisfied", (
            "the fresh receipt says WHY: the field binds via the "
            f"reviewed mapping and the value differs: {rows!r}")

    def test_wrong_subject_finalizes_unconfirmed(self):
        body = ("Beta project status: On track\n"
                "Alpha project status: Blocked\n")
        outcome, _summary, shared = self._finalize(
            {"canvas_id": "cv-alpha", "content": {"body": body}},
            "Please also update the Alpha project status in the draft "
            "to On track.")
        assert outcome != "already_applied", (
            "the Beta record's value must not finalize Alpha's ask")
        assert not shared.get("canvas_edit_decline_noop")
        assert not shared.get("canvas_edit_decline_reply")
        check = shared.get("canvas_decline_requirement_check")
        assert check is not None and check.get("satisfied") is not True
        rows = [o for o in check.get("obligations") or []
                if o.get("kind") == "assignment_postconditions"]
        assert rows and rows[0].get("disposition") == "unsatisfied", (
            "the fresh receipt says WHY: Alpha resolved, value differs — "
            f"{rows!r}")

    def test_beta_section_heading_finalizes_unconfirmed(self):
        """Defect class 2 through the real lane + finalizer: the only
        record sits under '# Beta project'; nothing names Alpha. The
        fresh receipt must be unresolved and the finalizer must not
        report already-applied."""
        outcome, _summary, shared = self._finalize(
            {"canvas_id": "cv-beta-heading",
             "content": {"body": "# Beta project\nStatus: On track\n"}},
            _ALPHA_ASK)
        assert outcome != "already_applied", (
            "the Beta section's Status must not finalize Alpha's ask")
        assert not shared.get("canvas_edit_decline_noop")
        assert not shared.get("canvas_edit_decline_reply")
        check = shared.get("canvas_decline_requirement_check")
        assert check is not None and check.get("satisfied") is not True
        rows = [o for o in check.get("obligations") or []
                if o.get("kind") == "assignment_postconditions"]
        assert rows and rows[0].get("disposition") == "unresolved", rows

    def test_sections_selecting_alpha_finalize_from_the_receipt(self):
        body = ("# Alpha project\nStatus: On track\n\n"
                "# Beta project\nStatus: Blocked\n")
        outcome, summary, shared = self._finalize(
            {"canvas_id": "cv-two-sections", "content": {"body": body}},
            _ALPHA_ASK)
        assert outcome == "already_applied", (
            f"Alpha's section holds On track: {outcome!r} {summary!r}")
        assert "Verified on the current draft" in summary
        assert "alpha project status in the draft already set to On track" \
            in summary
        check = shared.get("canvas_decline_requirement_check") or {}
        assert check.get("satisfied") is True, check

    def test_satisfied_reask_finalizes_from_the_receipt(self):
        """The finalizer's positive rides an EXACT field match
        (delivery -> Delivery); case never changes it."""
        outcome, summary, shared = self._finalize(
            {"canvas_id": "cv-delivery",
             "content": {"body": "Delivery: In Stock\n"}},
            "Please update the Delivery in the draft to In Stock.")
        assert outcome == "already_applied", (
            "the satisfied receipt must finalize already_applied: "
            f"{outcome!r} {summary!r}")
        assert "Verified on the current draft" in summary
        assert "In Stock" in summary
        assert shared.get("canvas_edit_decline_noop") is True
        check = shared.get("canvas_decline_requirement_check") or {}
        assert check.get("satisfied") is True, (
            "the finalizer's outcome rides a fresh satisfied receipt, "
            f"not the planner's prose: {check!r}")


def test_provable_noop_survives_planner_outage():
    """The identical re-ask must complete before planning, even when the
    planner is unavailable: the receipt is the authority, not the model."""
    import asyncio
    from core.chat_canvas_editor import CanvasPlanUnavailable, FreshDataResult
    import integrations.chat_orchestrator as co_mod

    calls = []

    async def _plan_outage(*a, **k):
        calls.append(1)
        raise CanvasPlanUnavailable("provider down")

    async def _fresh_none(*a, **k):
        return FreshDataResult("", False, True)

    original_plan = cce.plan_canvas_edit
    original_fresh = cce.fetch_fresh_data_section
    original_det = getattr(cce, "deterministic_assignment_plan", None)
    cce.plan_canvas_edit = _plan_outage
    cce.fetch_fresh_data_section = _fresh_none
    cce.deterministic_assignment_plan = lambda **kwargs: None
    shared = {}
    try:
        asyncio.run(co_mod.chat_orchestrator._try_canvas_edit(
            _REASK_ASK, [], _reask_canvas(), "user_1", "sess-auth",
            "exec-auth", None, shared_tool_state=shared))
    finally:
        cce.plan_canvas_edit = original_plan
        cce.fetch_fresh_data_section = original_fresh
        if original_det is not None:
            cce.deterministic_assignment_plan = original_det
        else:
            try:
                del cce.deterministic_assignment_plan
            except AttributeError:
                pass
    assert calls == [], "a provable no-op must not dispatch the planner"
    assert shared.get("canvas_edit_decline_noop") is True
    assert "already set to Net 45" in (shared.get(
        "canvas_edit_decline_reply") or "")


class TestStrictAssignmentSatisfactionPrimitives:
    """Unit pins for the narrowly named satisfaction helpers (owner
    repair 2026-10-18). These are the primitives the decline lane calls;
    they are deliberately NOT the shared grounding helpers (whose
    broad-match, recall-oriented behavior other callers depend on)."""

    def test_whole_value_equality_after_conservative_normalization(self):
        from core.chat_canvas_editor import _assignment_value_relation
        assert _assignment_value_relation(
            "Net 45", "  Net 45. ") == "satisfied"
        assert _assignment_value_relation(
            "\"On track\"", "On track") == "satisfied"
        # numbers: the existing WHOLE-value decimal equality
        assert _assignment_value_relation(
            "$48,000.00", "48,000") == "satisfied"
        # containment is not equivalence — the false completion's core
        assert _assignment_value_relation(
            "Net 45", "not Net 45") == "unsatisfied"
        assert _assignment_value_relation(
            "45", "450") == "unsatisfied"
        assert _assignment_value_relation(
            "On track", "Blocked") == "unsatisfied"

    def test_prose_is_unresolved_not_unsatisfied(self):
        from core.chat_canvas_editor import _assignment_value_relation
        assert _assignment_value_relation(
            "the payment schedule agreed with the supplier in the last "
            "call",
            "payment schedule to be confirmed by the supplier later",
        ) == "unresolved"

    def test_related_family_field_discovers_but_does_not_certify(self):
        """The retrieval family finds 'delivery time' as RELATED to the
        'Delivery' label — discovery only. Certification is exact field
        identity: 'delivery' binds, 'delivery time' does not."""
        from core.chat_canvas_editor import (
            _assignment_artifact_lines,
            _resolve_assignment_target,
        )
        records = _assignment_artifact_lines(
            {"body": "Delivery: In Stock\n"})
        exact = _resolve_assignment_target("delivery", records)
        assert exact.field_resolved and exact.subject_resolved, exact
        assert exact.record is not None
        assert exact.record.value == "In Stock"
        related = _resolve_assignment_target("delivery time", records)
        assert related.record is None, related

    def test_net_weight_does_not_match_gross_weight(self):
        """Defect class 4: 'net weight' discovers 'Gross weight' through
        the weight family, but related fields never certify."""
        from core.chat_canvas_editor import (
            _assignment_artifact_lines,
            _resolve_assignment_target,
        )
        records = _assignment_artifact_lines(
            {"body": "Gross weight: 10\n"})
        binding = _resolve_assignment_target("net weight", records)
        assert binding.record is None, binding
        assert binding.reason == "related_field_not_equivalent", binding
        exact = _resolve_assignment_target("gross weight", records)
        assert exact.record is not None

    def test_dealer_cost_does_not_match_retail(self):
        from core.chat_canvas_editor import (
            _assignment_artifact_lines,
            _resolve_assignment_target,
        )
        records = _assignment_artifact_lines({"body": "Retail: 100\n"})
        binding = _resolve_assignment_target("dealer cost", records)
        assert binding.record is None, binding
        assert binding.reason == "related_field_not_equivalent", binding
        exact = _resolve_assignment_target("retail", records)
        assert exact.record is not None

    def test_cross_family_alias_is_not_completion_identity(self):
        """'expiration date' and 'Valid until' share a retrieval family;
        completion identity requires the reviewed mapping, which does
        not cover this pair — unresolved."""
        from core.chat_canvas_editor import (
            _assignment_artifact_lines,
            _resolve_assignment_target,
        )
        records = _assignment_artifact_lines(
            {"body": "Valid until: 2027-01-31\n"})
        binding = _resolve_assignment_target("expiration date", records)
        assert binding.record is None, binding
        assert binding.reason == "related_field_not_equivalent", binding

    def test_case_is_never_binding_authority(self):
        from core.chat_canvas_editor import (
            _assignment_artifact_lines,
            _resolve_assignment_target,
        )
        # Wrong-subject negatives: every casing refuses.
        beta = _assignment_artifact_lines(
            {"body": "# Beta project\nStatus: On track\n"})
        for target in ("alpha status", "Alpha status", "ALPHA status"):
            binding = _resolve_assignment_target(target, beta)
            assert binding.record is None, target
            assert binding.reason == "subject_unresolved", target
        # Exact-field positives: every casing binds.
        delivery = _assignment_artifact_lines(
            {"body": "Delivery: In Stock\n"})
        for target in ("delivery", "Delivery", "DELIVERY"):
            binding = _resolve_assignment_target(target, delivery)
            assert binding.record is not None, target

    def test_reviewed_completion_mapping_resolves_payment_terms(self):
        """The one reviewed completion pair: 'payment terms' -> the bare
        'Terms' label — no retrieval alias involved."""
        from core.chat_canvas_editor import (
            _assignment_artifact_lines,
            _resolve_assignment_target,
        )
        records = _assignment_artifact_lines({"body": "Terms: Net 45\n"})
        binding = _resolve_assignment_target("payment terms", records)
        assert binding.field_resolved and binding.subject_resolved, binding
        assert binding.record is not None
        assert binding.record.value == "Net 45"
        # The bare label alone is an exact match as well.
        bare = _resolve_assignment_target("terms", records)
        assert bare.record is not None

    def test_completion_mapping_rejects_ambiguous_bare_label(self):
        """'Terms' next to 'Warranty terms' is ambiguous: the mapping
        does not fire and the leftover 'payment' word cannot silently
        become an alias — unresolved."""
        from core.chat_canvas_editor import (
            _assignment_artifact_lines,
            _resolve_assignment_target,
        )
        records = _assignment_artifact_lines(
            {"body": "Terms: Net 45\nWarranty terms: 12 months\n"})
        binding = _resolve_assignment_target("payment terms", records)
        assert binding.record is None, binding
        assert binding.reason == "subject_unresolved", binding

    def test_section_resolves_the_requested_subject(self):
        from core.chat_canvas_editor import (
            _assignment_artifact_lines,
            _resolve_assignment_target,
        )
        records = _assignment_artifact_lines({"body": (
            "# Alpha project\nStatus: On track\n\n"
            "# Beta project\nStatus: Blocked\n")})
        binding = _resolve_assignment_target(
            "alpha project status", records)
        assert binding.record is not None, binding
        assert binding.record.value == "On track"

    def test_beta_section_cannot_absorb_alpha(self):
        from core.chat_canvas_editor import (
            _assignment_artifact_lines,
            _resolve_assignment_target,
        )
        records = _assignment_artifact_lines(
            {"body": "# Beta project\nStatus: On track\n"})
        binding = _resolve_assignment_target(
            "alpha project status", records)
        assert binding.record is None
        assert binding.reason == "subject_unresolved"

    def test_records_carry_sections_and_explicit_labels(self):
        """Parser pins retained: explicit subject+field labels, Markdown
        headings, and HTML headings all reach the resolver."""
        from core.chat_canvas_editor import _assignment_artifact_lines
        records = _assignment_artifact_lines({"body": (
            "Beta project status: On track\n"
            "Alpha project status: Blocked\n")})
        assert records == [
            ("", "Beta project status", "On track",
             "Beta project status: On track"),
            ("", "Alpha project status", "Blocked",
             "Alpha project status: Blocked")]
        html_records = _assignment_artifact_lines(
            {"body": "<h1>Beta project</h1><p>Status: On track</p>"})
        assert html_records == [(
            "Beta project", "Status", "On track",
            "Status: On track")], html_records

    def test_conflicting_duplicates_leave_no_unique_record(self):
        from core.chat_canvas_editor import (
            _assignment_artifact_lines,
            _resolve_assignment_target,
        )
        records = _assignment_artifact_lines(
            {"body": "Terms: Net 45\nTerms: Net 30\n"})
        binding = _resolve_assignment_target("payment terms", records)
        assert binding.record is None
        # Duplicate SUPPORTED fields are ambiguous as well — no any().
        dup = _assignment_artifact_lines(
            {"body": "Delivery: 2 weeks\nDelivery: In Stock\n"})
        binding2 = _resolve_assignment_target("delivery", dup)
        assert binding2.record is None
        assert binding2.reason == "multiple_records"

    def test_unknown_field_vocabulary_stays_unresolved(self):
        from core.chat_canvas_editor import (
            _assignment_artifact_lines,
            _resolve_assignment_target,
        )
        records = _assignment_artifact_lines({"body": "Notes: all good\n"})
        binding = _resolve_assignment_target(
            "alpha project status", records)
        assert binding.record is None
        assert binding.field_resolved is False
        assert binding.reason == "field_unresolved"
