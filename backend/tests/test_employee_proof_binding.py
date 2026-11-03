"""Typed proof profiles: omission, mismatch and complete positives."""
from __future__ import annotations

from core.assignment_plan import new_assignment, new_step
from core.assignment_readiness import evaluate_step_readiness
from core.task_outcome_contract import sent_record_confirmed_evidence


def _assignment(result, *, requested=None, adapter="workbook.read"):
    source = new_step(
        step_id="source", title="source", operation_type="retrieve",
        adapter=adapter,
        inputs={"resource_binding": requested or {
            "resource_id": "file-1", "source_version": "v1"}})
    source.update(status="applied", operation_id="op-1", result=result)
    child = new_step(
        step_id="use", title="use", operation_type="calculate",
        adapter="formula.calculate", inputs={},
        requires=[{"kind": "receipt", "step_id": "source",
                   "require": "verified"}])
    return new_assignment(
        objective="Use the verified evidence", steps=[source, child])


def _eligible(assignment):
    return evaluate_step_readiness(
        assignment["steps"][1], assignment,
        task_authorization="read_only")


def test_source_profile_requires_identity_and_coverage_not_only_status():
    status_only = _eligible(_assignment({
        "verification": {"status": "verified"}}))
    assert status_only["eligible"] is False
    assert status_only["blockers"][0]["reason"] == "verified_identity_missing"

    no_coverage = _eligible(_assignment({
        "resource_id": "file-1", "source_version": "v1",
        "verification": {"status": "verified"}}))
    assert no_coverage["eligible"] is False
    assert no_coverage["blockers"][0]["reason"] == "verified_coverage_missing"

    complete = _eligible(_assignment({
        "resource_id": "file-1", "source_version": "v1",
        "coverage": {"complete": True, "truncated": False},
        "verification": {"status": "verified",
                         "resource_id": "file-1", "version": "v1",
                         "coverage": {"complete": True}}}))
    assert complete["eligible"] is True


def test_source_profile_rejects_each_wrong_binding():
    base = {
        "resource_id": "file-1", "source_version": "v1",
        "coverage": {"complete": True, "truncated": False},
        "verification": {"status": "verified",
                         "resource_id": "file-1", "version": "v1",
                         "coverage": {"complete": True}},
    }
    for field, value, reason in (
        ("resource_id", "file-other", "verified_binding_resource_id_mismatch"),
        ("version", "v2", "verified_binding_version_mismatch"),
    ):
        result = dict(base)
        result["verification"] = {
            **base["verification"], field: value}
        decision = _eligible(_assignment(result))
        assert decision["eligible"] is False, (field, decision)
        assert decision["blockers"][0]["reason"] == reason

    missing_requested_identity = _eligible(_assignment({
        "source_version": "v1", "coverage": {"complete": True},
        "verification": {"status": "verified",
                         "coverage": {"complete": True}}}))
    assert missing_requested_identity["eligible"] is False
    assert missing_requested_identity["blockers"][0]["reason"] == (
        "verified_identity_missing")


def test_source_profile_rejects_incomplete_population_and_malformed_coverage():
    incomplete_population = _eligible(_assignment({
        "resource_id": "file-1", "source_version": "v1",
        "coverage": {"complete": True, "expected_count": 10,
                     "matched_count": 9},
        "verification": {"status": "verified",
                         "coverage": {"complete": True}}}))
    assert incomplete_population["eligible"] is False
    assert incomplete_population["blockers"][0]["reason"] == (
        "verified_coverage_incomplete")

    malformed = _eligible(_assignment({
        "resource_id": "file-1", "source_version": "v1",
        "coverage": {"complete": "yes"},
        "verification": {"status": "verified",
                         "coverage": {"complete": "yes"}}}))
    assert malformed["eligible"] is False
    assert malformed["blockers"][0]["reason"] == "verified_coverage_unknown"


def test_fact_qualification_requires_stable_evidence_or_authority():
    def assignment(fact):
        child = new_step(
            step_id="use", title="use", operation_type="calculate",
            adapter="formula.calculate", inputs={},
            requires=[{"kind": "fact", "fact_id": "eligible",
                       "equals": True}])
        return new_assignment(
            objective="Qualified work", steps=[child], facts=[fact])

    bare = evaluation = evaluate_step_readiness(
        assignment({"fact_id": "eligible", "value": True,
                    "evidence_state": "established"})["steps"][0],
        assignment({"fact_id": "eligible", "value": True,
                    "evidence_state": "established"}),
        task_authorization="read_only")
    assert bare["eligible"] is False

    note = evaluate_step_readiness(
        assignment({"fact_id": "eligible", "value": True,
                    "evidence_state": "established",
                    "source_refs": [{"note": "observed"}]})["steps"][0],
        assignment({"fact_id": "eligible", "value": True,
                    "evidence_state": "established",
                    "source_refs": [{"note": "observed"}]}),
        task_authorization="read_only")
    assert note["eligible"] is False

    authored = assignment({"fact_id": "eligible", "value": True,
                           "evidence_state": "established",
                           "authority_ref": "owner:eligible"})
    assert evaluate_step_readiness(
        authored["steps"][0], authored,
        task_authorization="read_only")["eligible"] is True


def test_sent_items_requires_each_correlated_identity():
    step = {"operation_id": "op-1"}
    presence = {"provider_ref": "message-1",
                "readback": {"sent_items": {"present": True}}}
    assert sent_record_confirmed_evidence(step, presence) is None

    wrong_message = {
        "provider_ref": "message-1",
        "readback": {"sent_items": {
            "present": True, "operation_id": "op-1",
            "provider_ref": "message-foreign"}},
    }
    assert sent_record_confirmed_evidence(step, wrong_message) is False

    missing_message = {
        "provider_ref": "message-1",
        "readback": {"sent_items": {
            "present": True, "operation_id": "op-1"}},
    }
    assert sent_record_confirmed_evidence(step, missing_message) is None

    complete = {
        "provider_ref": "message-1",
        "readback": {"sent_items": {
            "present": True, "operation_id": "op-1",
            "provider_ref": "message-1"}},
    }
    assert sent_record_confirmed_evidence(step, complete) is True

    account_mismatch = {
        "provider_ref": "message-1", "account": "owner@example.invalid",
        "readback": {"sent_items": {
            "present": True, "operation_id": "op-1",
            "provider_ref": "message-1",
            "account": "other@example.invalid"}},
    }
    assert sent_record_confirmed_evidence(step, account_mismatch) is False


def _profile_assignment(
    *, operation_type: str, adapter: str, effect: str, result: dict,
    requested=None, operation_id="op-1",
):
    source = new_step(
        step_id="source", title="source",
        operation_type=operation_type, adapter=adapter, effect=effect,
        inputs={"resource_binding": requested} if requested else {})
    source.update(status="applied", operation_id=operation_id,
                  result=result)
    child = new_step(
        step_id="use", title="use", operation_type="calculate",
        adapter="formula.calculate", inputs={},
        requires=[{"kind": "receipt", "step_id": "source",
                   "require": "verified"}])
    return new_assignment(
        objective="Use the verified proof", steps=[source, child])


def _profile_decision(assignment):
    return evaluate_step_readiness(
        assignment["steps"][1], assignment,
        task_authorization="read_only")


def test_source_profile_rejects_wrong_subject_and_operation_identity():
    base = {
        "resource_id": "file-1", "source_version": "v1",
        "operation_id": "op-1",
        "subject": {"kind": "invoice", "id": "INV-1"},
        "coverage": {"complete": True},
        "verification": {
            "status": "verified", "resource_id": "file-1",
            "version": "v1", "operation_id": "op-1",
            "subject": {"kind": "invoice", "id": "INV-1"},
            "coverage": {"complete": True}},
    }
    requested = {"resource_id": "file-1", "source_version": "v1"}
    valid = _profile_assignment(
        operation_type="retrieve", adapter="workbook.read",
        effect="local", result=base, requested=requested)
    assert _profile_decision(valid)["eligible"] is True

    for field, value, reason in (
        ("operation_id", "op-other",
         "verified_binding_operation_id_mismatch"),
        ("subject", {"kind": "invoice", "id": "INV-2"},
         "verified_binding_subject_mismatch"),
    ):
        result = dict(base)
        result["verification"] = {
            **base["verification"], field: value}
        decision = _profile_decision(_profile_assignment(
            operation_type="retrieve", adapter="workbook.read",
            effect="local", result=result, requested=requested))
        assert decision["eligible"] is False, (field, decision)
        assert decision["blockers"][0]["reason"] == reason


def test_source_profile_rejects_non_finite_and_incomplete_population():
    requested = {"resource_id": "file-1", "source_version": "v1"}
    for coverage, reason in (
        ({"complete": True, "expected_count": 10,
          "matched_count": 9}, "verified_coverage_incomplete"),
        ({"complete": True, "source_row_count": 10,
          "selected_count": 9}, "verified_coverage_incomplete"),
        ({"complete": True, "expected_count": "inf",
          "matched_count": 1}, "verified_coverage_unknown"),
        ({"complete": True, "expected_count": 10},
         "verified_coverage_unknown"),
        ({"complete": 1}, "verified_coverage_unknown"),
    ):
        result = {
            "resource_id": "file-1", "source_version": "v1",
            "coverage": coverage,
            "verification": {"status": "verified",
                             "coverage": coverage},
        }
        decision = _profile_decision(_profile_assignment(
            operation_type="retrieve", adapter="workbook.read",
            effect="local", result=result, requested=requested))
        assert decision["eligible"] is False, (coverage, decision)
        assert decision["blockers"][0]["reason"] == reason


def test_external_profile_requires_operation_and_remote_identity():
    requested = {"account": "owner@example.invalid"}
    valid = _profile_assignment(
        operation_type="outbound", adapter="email.send_outlook",
        effect="external", requested=requested,
        result={
            "operation_id": "op-1", "provider_ref": "message-1",
            "message_id": "mid-1", "account": "owner@example.invalid",
            "verification": {
                "status": "verified", "operation_id": "op-1",
                "provider_ref": "message-1", "message_id": "mid-1",
                "account": "owner@example.invalid"},
        })
    assert _profile_decision(valid)["eligible"] is True

    missing_remote = _profile_assignment(
        operation_type="outbound", adapter="email.send_outlook",
        effect="external",
        result={"operation_id": "op-1",
                "verification": {"status": "verified"}})
    decision = _profile_decision(missing_remote)
    assert decision["eligible"] is False
    assert decision["blockers"][0]["reason"] == (
        "verified_remote_identity_missing")

    missing_operation = _profile_assignment(
        operation_type="outbound", adapter="email.send_outlook",
        effect="external", operation_id=None,
        result={"provider_ref": "message-1",
                "verification": {"status": "verified"}})
    decision = _profile_decision(missing_operation)
    assert decision["eligible"] is False
    assert decision["blockers"][0]["reason"] == (
        "verified_operation_identity_missing")

    for field, value, reason in (
        ("provider_ref", "message-other",
         "verified_binding_provider_ref_mismatch"),
        ("message_id", "mid-other",
         "verified_binding_message_id_mismatch"),
        ("account", "other@example.invalid",
         "verified_binding_account_mismatch"),
    ):
        result = {
            "operation_id": "op-1", "provider_ref": "message-1",
            "message_id": "mid-1", "account": "owner@example.invalid",
            "verification": {
                "status": "verified", "operation_id": "op-1",
                "provider_ref": "message-1", "message_id": "mid-1",
                "account": "owner@example.invalid", field: value},
        }
        result["verification"][field] = value
        decision = _profile_decision(_profile_assignment(
            operation_type="outbound", adapter="email.send_outlook",
            effect="external", requested=requested, result=result))
        assert decision["eligible"] is False, (field, decision)
        assert decision["blockers"][0]["reason"] == reason


def test_artifact_and_local_profiles_require_their_material_result():
    artifact = _profile_assignment(
        operation_type="present", adapter="artifact.document",
        effect="local",
        result={"artifact": {"revision": "rev-1", "sha256": "sha-1"},
                "verification": {"status": "verified"}})
    assert _profile_decision(artifact)["eligible"] is True

    for incomplete in (
        {"verification": {"status": "verified"}},
        {"artifact": {"revision": "rev-1"},
         "verification": {"status": "verified"}},
        {"artifact": {"sha256": "sha-1"},
         "verification": {"status": "verified"}},
    ):
        missing_artifact = _profile_assignment(
            operation_type="present", adapter="artifact.document",
            effect="local", result=incomplete)
        decision = _profile_decision(missing_artifact)
        assert decision["eligible"] is False, incomplete
        assert decision["blockers"][0]["reason"] == (
            "verified_artifact_receipt_missing")

    local = _profile_assignment(
        operation_type="calculate", adapter="formula.calculate",
        effect="local",
        result={"value": "494.75", "unit": "USD",
                "verification": {"status": "verified"}})
    assert _profile_decision(local)["eligible"] is True

    missing_value = _profile_assignment(
        operation_type="calculate", adapter="formula.calculate",
        effect="local", result={"verification": {"status": "verified"}})
    decision = _profile_decision(missing_value)
    assert decision["eligible"] is False
    assert decision["blockers"][0]["reason"] == (
        "verified_material_result_missing")


def test_sent_items_rejects_swapped_namespaces_and_boolean_shortcuts():
    step = {"operation_id": "op-1"}
    swapped = {
        "provider_ref": "message-1",
        "readback": {"sent_items": {
            "present": True, "operation_id": "message-1",
            "provider_ref": "op-1"}},
    }
    assert sent_record_confirmed_evidence(step, swapped) is False

    bare = {"provider_ref": "message-1", "sent_record_confirmed": True}
    assert sent_record_confirmed_evidence(step, bare) is None
    readback_bool = {
        "provider_ref": "message-1",
        "readback": {"sent_items": True},
    }
    assert sent_record_confirmed_evidence(step, readback_bool) is None

    nested = {
        "provider_ref": "message-1",
        "receipt": {"readback": {"sent_items": {
            "present": True, "operation_id": "op-1",
            "provider_ref": "message-1"}}},
    }
    assert sent_record_confirmed_evidence(step, nested) is True

    message_ok = {
        "provider_ref": "message-1", "message_id": "mid-1",
        "readback": {"sent_items": {
            "present": True, "operation_id": "op-1",
            "provider_ref": "message-1", "message_id": "mid-1"}},
    }
    assert sent_record_confirmed_evidence(step, message_ok) is True
    message_wrong = {
        **message_ok,
        "readback": {"sent_items": {
            "present": True, "operation_id": "op-1",
            "provider_ref": "message-1", "message_id": "mid-2"}},
    }
    assert sent_record_confirmed_evidence(step, message_wrong) is False
    message_missing = {
        **message_ok,
        "readback": {"sent_items": {
            "present": True, "operation_id": "op-1",
            "provider_ref": "message-1"}},
    }
    assert sent_record_confirmed_evidence(step, message_missing) is None

    absent = {
        "provider_ref": "message-1",
        "readback": {"sent_items": {
            "present": False, "operation_id": "op-1",
            "provider_ref": "message-1"}},
    }
    assert sent_record_confirmed_evidence(step, absent) is False


def _receipt_for(step, result):
    step.update(status="applied", operation_id="op-1", result=result)
    child = new_step(
        step_id="use", title="use", operation_type="calculate",
        adapter="formula.calculate", inputs={},
        requires=[{"kind": "receipt", "step_id": "source",
                   "require": "verified"}])
    return new_assignment(
        objective="Use the receipt", steps=[step, child])


def test_artifact_and_local_receipts_use_their_durable_proof():
    artifact = new_step(
        step_id="source", title="Render artifact",
        operation_type="present", adapter="artifact.document",
        inputs={}, effect="local")
    assignment = _receipt_for(
        artifact, {"artifact": {"revision": "rev-1", "sha256": "sha-1"}})
    assert evaluate_step_readiness(
        assignment["steps"][1], assignment,
        task_authorization="read_only")["eligible"] is True

    missing_sha = new_step(
        step_id="source", title="Render artifact",
        operation_type="present", adapter="artifact.document",
        inputs={}, effect="local")
    assignment = _receipt_for(
        missing_sha, {"artifact": {"revision": "rev-1"}})
    assert evaluate_step_readiness(
        assignment["steps"][1], assignment,
        task_authorization="read_only")["eligible"] is False

    local = new_step(
        step_id="source", title="Calculate", operation_type="calculate",
        adapter="formula.calculate", inputs={}, effect="local")
    assignment = _receipt_for(local, {"value": 494.75, "unit": "USD"})
    assert evaluate_step_readiness(
        assignment["steps"][1], assignment,
        task_authorization="read_only")["eligible"] is True
