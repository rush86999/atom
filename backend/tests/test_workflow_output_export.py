"""Workflow execution result export tests (scratch SQL/public routes)."""
from __future__ import annotations

import hashlib
import json

import pytest

from tests.test_generated_workflow_handoff import (
    AGENT_AUTO,
    _deploy,
    _draft_readonly,
    _generate,
    _run_fresh_child,
    harness,
)


def _completed_run(harness):
    harness.drafts["draft"] = _draft_readonly()
    generated = _generate(harness, agent_id=AGENT_AUTO)
    workflow_id = generated["workflow_id"]
    digest = generated["definition_digest"]
    deployed = _deploy(harness, workflow_id, digest, agent_id=AGENT_AUTO)
    assert deployed.status_code == 200, deployed.text
    run = harness.client.post(
        f"/api/v1/workflows/workflows/{workflow_id}/execute", json={})
    assert run.status_code == 200, run.text
    assert run.json()["status"] == "completed"
    return workflow_id, digest, run.json()["execution_id"]


def _export(harness, execution_id):
    return harness.client.get(
        f"/api/v1/workflows/workflows/executions/{execution_id}/export")


def test_export_completed_results_is_deterministic_and_scoped(harness):
    workflow_id, _digest, execution_id = _completed_run(harness)
    first = _export(harness, execution_id)
    assert first.status_code == 200, first.text
    assert first.headers["content-type"].startswith("application/json")
    disposition = first.headers["content-disposition"]
    assert disposition.startswith("attachment; filename=")
    assert disposition.endswith('.json"')
    assert "/" not in disposition and "\\" not in disposition
    expected_hash = hashlib.sha256(first.content).hexdigest()
    assert first.headers["etag"] == f'"sha256:{expected_hash}"'
    assert first.headers["cache-control"] == "no-store"

    document = json.loads(first.content.decode("utf-8"))
    assert document["schema"] == "atom.workflow.execution-result.v1"
    assert document["execution"]["execution_id"] == execution_id
    assert document["execution"]["workflow_id"] == workflow_id
    assert document["workflow"]["workflow_id"] == workflow_id
    assert document["execution"]["status"] == "completed"
    assert document["results"]["lookup"]["status"] == "completed"
    assert isinstance(document["results"]["lookup"]["matches"], list)
    assert all(step["status"] == "completed" for step in document["steps"])
    assert document["provenance"]["source"] == "durable_workflow_execution"
    assert document["provenance"]["execution_id"] == execution_id
    body_text = first.content.decode("utf-8")
    assert "/private/" not in body_text
    assert "context" not in document
    assert "authorization" not in body_text.lower()

    second = _export(harness, execution_id)
    assert second.status_code == 200
    assert second.content == first.content
    assert hashlib.sha256(second.content).hexdigest() == expected_hash

    harness.holder["user"] = harness.user_b
    assert _export(harness, execution_id).status_code == 404


@pytest.mark.parametrize("state", ["running", "failed", "cancelled"])
def test_export_refuses_non_completed_status(harness, state):
    _workflow_id, _digest, execution_id = _completed_run(harness)
    db = harness.Session()
    try:
        from core.models import WorkflowExecution

        row = db.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == execution_id).one()
        row.status = state
        db.commit()
    finally:
        db.close()
    response = _export(harness, execution_id)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"] == "execution_not_completed"


def test_export_refuses_error_missing_output_partial_and_failed_step(harness):
    _workflow_id, _digest, execution_id = _completed_run(harness)
    from core.models import WorkflowExecution

    db = harness.Session()
    try:
        row = db.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == execution_id).one()
        original_outputs = row.outputs
        original_context = row.context

        row.error = "boom"
        db.commit()
        refused = _export(harness, execution_id)
        assert refused.status_code == 409
        assert refused.json()["detail"]["error"] == "execution_has_error"

        row.error = None
        row.outputs = "{}"
        db.commit()
        refused = _export(harness, execution_id)
        assert refused.status_code == 409
        assert refused.json()["detail"]["error"] == "execution_has_no_output"

        row.outputs = original_outputs
        context = json.loads(original_context)
        for entry in context.get("execution_history") or []:
            if entry.get("step_id") == "lookup":
                entry["status"] = "waiting_approval"
        row.context = json.dumps(context)
        db.commit()
        refused = _export(harness, execution_id)
        assert refused.status_code == 409
        assert refused.json()["detail"]["error"] == "execution_not_completed"

        row.context = original_context
        outputs = json.loads(original_outputs)
        outputs["lookup"]["status"] = "failed"
        row.outputs = json.dumps(outputs)
        db.commit()
        refused = _export(harness, execution_id)
        assert refused.status_code == 409
        assert refused.json()["detail"]["error"] in {
            "execution_not_completed", "execution_output_contradictory"}
    finally:
        db.close()


def test_export_is_read_only_no_execution_or_scheduler_effect(harness):
    _workflow_id, _digest, execution_id = _completed_run(harness)
    from core.models import WorkflowExecution

    db = harness.Session()
    try:
        before = db.query(WorkflowExecution).count()
    finally:
        db.close()
    assert _export(harness, execution_id).status_code == 200
    assert _export(harness, execution_id).status_code == 200
    db = harness.Session()
    try:
        assert db.query(WorkflowExecution).count() == before
        row = db.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == execution_id).one()
        assert row.status == "completed"
    finally:
        db.close()
    assert harness.recorder.calls == []


def test_export_fresh_process_bytes_and_hash_match(harness):
    workflow_id, digest, execution_id = _completed_run(harness)
    parent = _export(harness, execution_id)
    assert parent.status_code == 200, parent.text
    parent_hash = hashlib.sha256(parent.content).hexdigest()

    row = next(item for item in _catalog_rows(harness)
               if item["id"] == workflow_id)
    operation_id = row["deployment"]["operation_id"]
    owner_id = row["deployment"]["owner_user_id"]

    first = _run_fresh_child(
        harness, "export", workflow_id=workflow_id, digest=digest,
        execution_id=execution_id, operation_id=operation_id,
        owner_id=owner_id)
    print("FRESH_EXPORT_FIRST:" + json.dumps(first, sort_keys=True))
    assert first["export_sha256"] == parent_hash
    assert first["export_bytes"] == len(parent.content)
    assert first["export_schema"] == "atom.workflow.execution-result.v1"
    assert first["export_execution_id"] == execution_id
    assert first["export_workflow_id"] == workflow_id
    assert "/" not in (first["export_filename"] or "")
    assert "\\" not in (first["export_filename"] or "")

    second = _run_fresh_child(
        harness, "export", workflow_id=workflow_id, digest=digest,
        execution_id=execution_id, operation_id=operation_id,
        owner_id=owner_id)
    print("FRESH_EXPORT_SECOND:" + json.dumps(second, sort_keys=True))
    assert second["export_sha256"] == parent_hash
    assert harness.recorder.calls == []


def _catalog_rows(harness):
    return json.loads(harness.catalog.read_text())


def test_export_refuses_revoked_actor_on_fresh_read(harness):
    _workflow_id, _digest, execution_id = _completed_run(harness)
    db = harness.Session()
    try:
        from core.models import User

        actor = db.query(User).filter(User.id == harness.user_a.id).one()
        actor.is_active = False
        actor.status = "disabled"
        db.commit()
    finally:
        db.close()
    response = _export(harness, execution_id)
    assert response.status_code == 404, response.text


def test_export_refuses_sensitive_fields_instead_of_rewriting(harness):
    _workflow_id, _digest, execution_id = _completed_run(harness)
    from core.models import WorkflowExecution

    db = harness.Session()
    try:
        row = db.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == execution_id).one()
        outputs = json.loads(row.outputs)
        outputs["lookup"]["api_key"] = "sk-this-should-never-export"
        row.outputs = json.dumps(outputs)
        db.commit()
    finally:
        db.close()
    response = _export(harness, execution_id)
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error"] == "execution_output_sensitive"
    assert any("api_key" in field for field in detail["fields"])


def test_export_rejects_malformed_identity_and_unknown_material(harness):
    _workflow_id, _digest, execution_id = _completed_run(harness)
    from core.models import WorkflowExecution

    db = harness.Session()
    try:
        row = db.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == execution_id).one()
        original_context = row.context
        original_outputs = row.outputs

        context = json.loads(original_context)
        context["execution_history"] = [None]
        row.context = json.dumps(context)
        db.commit()
        assert _export(harness, execution_id).status_code == 409

        context = json.loads(original_context)
        context["execution_history"] = [{"status": "completed"}]
        row.context = json.dumps(context)
        db.commit()
        assert _export(harness, execution_id).status_code == 409

        context = json.loads(original_context)
        context["execution_history"] = list(
            context.get("execution_history") or []) + [{
                "step_id": "unknown-step", "status": "completed"}]
        row.context = json.dumps(context)
        row.outputs = original_outputs
        db.commit()
        response = _export(harness, execution_id)
        assert response.status_code == 409
        assert response.json()["detail"]["error"] == (
            "execution_history_unknown_step")

        row.context = original_context
        outputs = json.loads(original_outputs)
        outputs["unknown-step"] = {"status": "completed"}
        row.outputs = json.dumps(outputs)
        db.commit()
        response = _export(harness, execution_id)
        assert response.status_code == 409
        assert response.json()["detail"]["error"] == (
            "execution_output_unknown_step")
    finally:
        db.close()


def _context_of(harness, execution_id):
    from core.models import WorkflowExecution

    db = harness.Session()
    try:
        row = db.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == execution_id).one()
        return json.loads(row.context), row
    finally:
        db.close()


def test_export_binds_executed_definition_digest_to_authoritative_revision(
        harness):
    workflow_id, original_digest, execution_id = _completed_run(harness)
    from core.models import Workflow, WorkflowExecution

    context, _row = _context_of(harness, execution_id)
    assert context["variables"]["_workflow_definition_digest"] == original_digest
    assert context["variables"]["_workflow_definition_id"] == workflow_id

    positive = _export(harness, execution_id)
    assert positive.status_code == 200, positive.text
    document = json.loads(positive.content.decode("utf-8"))
    assert document["provenance"]["definition_digest"] == original_digest
    assert document["provenance"]["executed_definition_digest"] == original_digest
    assert document["provenance"]["executed_definition_id"] == workflow_id
    assert document["provenance"]["definition_binding"] == (
        "executed-context-vs-authoritative-configuration")

    # Failure-first: a revised authoritative digest must not be relabelled as
    # the revision that actually executed.
    db = harness.Session()
    try:
        definition = db.query(Workflow).filter(Workflow.id == workflow_id).one()
        configuration = dict(definition.configuration)
        configuration["definition_digest"] = "different-authoritative-revision"
        definition.configuration = configuration
        db.commit()
    finally:
        db.close()
    mismatch = _export(harness, execution_id)
    assert mismatch.status_code == 409, mismatch.text
    assert mismatch.json()["detail"]["error"] == (
        "execution_definition_binding_mismatch")


def test_export_refuses_missing_or_contradictory_definition_binding(harness):
    workflow_id, _digest, execution_id = _completed_run(harness)
    from core.models import Workflow, WorkflowExecution

    db = harness.Session()
    try:
        row = db.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == execution_id).one()
        original_context = row.context
        definition = db.query(Workflow).filter(Workflow.id == workflow_id).one()
        original_config = dict(definition.configuration)

        context = json.loads(original_context)
        context["variables"].pop("_workflow_definition_digest", None)
        row.context = json.dumps(context)
        db.commit()
        missing = _export(harness, execution_id)
        assert missing.status_code == 409
        assert missing.json()["detail"]["error"] == (
            "execution_definition_binding_missing")

        context = json.loads(original_context)
        context["variables"]["_workflow_definition_digest"] = "contradictory"
        row.context = json.dumps(context)
        db.commit()
        contradictory = _export(harness, execution_id)
        assert contradictory.status_code == 409
        assert contradictory.json()["detail"]["error"] == (
            "execution_definition_binding_mismatch")

        context = json.loads(original_context)
        context["variables"]["_workflow_definition_id"] = "other-workflow"
        row.context = json.dumps(context)
        db.commit()
        identity = _export(harness, execution_id)
        assert identity.status_code == 409
        assert identity.json()["detail"]["error"] == (
            "execution_definition_binding_mismatch")

        row.context = original_context
        configuration = dict(original_config)
        configuration.pop("definition_digest", None)
        definition.configuration = configuration
        db.commit()
        no_authority = _export(harness, execution_id)
        assert no_authority.status_code == 409
        assert no_authority.json()["detail"]["error"] == (
            "execution_definition_binding_missing")

        configuration = dict(original_config)
        configuration["steps"] = [
            {**step, "description": "tampered"}
            for step in configuration.get("steps") or []
        ]
        definition.configuration = configuration
        db.commit()
        tampered = _export(harness, execution_id)
        assert tampered.status_code == 409
        assert tampered.json()["detail"]["error"] == (
            "execution_definition_binding_mismatch")
    finally:
        db.close()
