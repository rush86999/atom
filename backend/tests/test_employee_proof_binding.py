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


def _source_result(**overrides):
    result = {
        "resource_id": "file-1", "source_version": "v1",
        "coverage": {"complete": True, "truncated": False},
        "verification": {"status": "verified",
                         "coverage": {"complete": True}},
    }
    result.update(overrides)
    return result


def test_generated_source_profile_requires_every_material_category():
    invalid = []
    for field in ("resource_id", "source_version", "coverage"):
        omitted = _source_result()
        omitted.pop(field)
        invalid.append((f"{field}-omitted", omitted))
        for value in (None, "", 0, 123, ["x"], {"bad": "type"}):
            changed = _source_result()
            changed[field] = value
            invalid.append((f"{field}-{value!r}", changed))
    for status in (None, "", "not-a-status", 123):
        invalid.append((f"status-{status!r}",
                        _source_result(verification={
                            "status": status,
                            "coverage": {"complete": True}})))
    invalid.extend([
        ("missing-verification", {
            "resource_id": "file-1", "source_version": "v1",
            "coverage": {"complete": True}}),
        ("empty-verification", _source_result(verification={})),
        ("malformed-verification", _source_result(verification=[])),
    ])
    for label, result in invalid:
        decision = _eligible(_assignment(result))
        assert decision["eligible"] is False, (label, decision)

    assert _eligible(_assignment(_source_result()))["eligible"] is True


def test_generated_source_coverage_matrix_accepts_only_consistent_profiles():
    cases = []
    for complete in (True, False):
        for known in (True, False):
            for truncated in (True, False):
                cases.append((
                    {"complete": complete, "known": known,
                     "truncated": truncated},
                    complete is True and known is True and truncated is False))
    for value in ("true", "no", 1, 0, None, [], {}):
        for key in ("complete", "known", "truncated"):
            cases.append((
                {"complete": True, "known": True, "truncated": False,
                 key: value}, False))
    cases.extend([
        ({"complete": True}, True),
        ({"complete": True, "truncated": False}, True),
        ({"complete": True, "known": True}, True),
        ({"known": True, "truncated": False}, True),
        ({"known": True}, True),
        ({"truncated": False}, False),
        ({}, False),
        ({"complete": False}, False),
        ({"known": False}, False),
        ({"truncated": True}, False),
        ({"complete": True, "known": True, "truncated": False,
          "expected_count": 10, "matched_count": 9}, False),
        ({"complete": True, "known": True, "truncated": False,
          "expected_count": 10}, False),
        ({"complete": True, "known": True, "truncated": False,
          "expected_count": "inf", "matched_count": 1}, False),
    ])
    for coverage, supported in cases:
        result = _source_result(
            coverage=coverage,
            verification={"status": "verified", "coverage": coverage})
        decision = _eligible(_assignment(result))
        assert decision["eligible"] is supported, (coverage, decision)


def test_generated_sent_items_minimum_schema():
    cases = [
        (True, "op-1", "message-1", True),
        (True, "op-1", "message-foreign", False),
        (True, "op-foreign", "message-1", False),
        (True, "op-foreign", "message-foreign", False),
        (False, "op-1", "message-1", False),
        (None, "op-1", "message-1", None),
        ("yes", "op-1", "message-1", None),
        (True, None, "message-1", None),
        (True, "op-1", None, None),
        (True, None, None, None),
    ]
    for present, operation_id, provider_ref, expected in cases:
        sent_items = {"present": present}
        if operation_id is not None:
            sent_items["operation_id"] = operation_id
        if provider_ref is not None:
            sent_items["provider_ref"] = provider_ref
        result = {
            "provider_ref": "message-1",
            "readback": {"sent_items": sent_items},
        }
        assert sent_record_confirmed_evidence(
            {"operation_id": "op-1"}, result) is expected, (
                present, operation_id, provider_ref)

    assert sent_record_confirmed_evidence(
        {"operation_id": "op-1"},
        {"readback": {"sent_items": {
            "present": True, "operation_id": "op-1",
            "provider_ref": "message-1"}}}) is None
    assert sent_record_confirmed_evidence(
        {},
        {"provider_ref": "message-1",
         "readback": {"sent_items": {
             "present": True, "provider_ref": "message-1"}}}) is None
