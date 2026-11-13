"""An accepted upload stays consumable after the source answer.

The verified-source.6zZA4H run uploaded both invoices (HTTP 200) and attached
them (HTTP 200). Each persisted ``document.text`` step held the canonical
``office/uploads`` path, the uploaded document id in ``resource_id`` and
``source="manual_upload"`` -- but no ``document_id``. The executor's uploaded
branch only recognized ``source == "upload"``, so its pre-consumption recheck
asked the connected catalog for ``(manual_upload, upload_<id>)``, got
``resource_not_found``, and parked the already-applied read. The cached text
existed; ``invoice.reconcile`` never ran.

These tests pin the normal source answer to the uploaded document identity and
keep the exact run7 binding (which has no ``document_id``) consumable.
"""
from __future__ import annotations

import asyncio
import hashlib
import json

from core.assignment_executor import _document_text_read
from core.assignment_plan import new_assignment, new_step
from core.assignment_resources import (
    recheck_resource_access, resolve_assignment_source, resource_binding,
)
from core.models import IngestedDocument
from tests.test_assignment_routes import route_env  # noqa: F401

RUN7_DOC_ID = "doc_818f5b1a9eaf1d47e78e50e0"
RUN7_PARTIAL = {
    "currency": "USD",
    "freight": "12.75",
    "invoice_id": "INV-TRIGGER-91",
    "po_id": "PO-TRIGGER-63",
    "quantity": "3",
    "unit_price": None,
}


def _upload(route_env, tmp_path, *, doc_id=RUN7_DOC_ID,
            file_name="invoice-partial.json", payload=RUN7_PARTIAL):
    path = tmp_path / f"{doc_id}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    version = "ev4:" + hashlib.sha256(path.read_bytes()).hexdigest()
    route_env["db"].add(IngestedDocument(
        id=doc_id,
        workspace_id="ws-1",
        tenant_id="tenant-1",
        file_name=file_name,
        file_path=str(path),
        file_type="json",
        integration_id="manual_upload",
        external_id=f"upload_{doc_id}",
        source_content_hash=version,
        file_size_bytes=path.stat().st_size,
        freshness_status="fresh",
    ))
    route_env["db"].commit()
    return path, version


def _resolved_upload(route_env, path, version, *, doc_id=RUN7_DOC_ID):
    return resolve_assignment_source(
        route_env["db"], route_env["users"]["lead"],
        {"kind": "document", "document_id": doc_id,
         "source_version": version})


def _accepted_read(path, binding):
    result = asyncio.run(_document_text_read(
        {"resource_binding": binding, "path": str(path)},
        {"workspace_id": "ws-1", "tenant_id": "tenant-1"}))
    step = new_step(
        step_id="source-3", title=f"Read {path.name}",
        operation_type="retrieve", adapter="document.text",
        inputs={"resource_binding": binding, "path": str(path)},
        effect="read_only")
    step.update(
        status="applied", operation_id="op-source-3", result=result)
    return step


def test_uploaded_source_binding_preserves_document_identity(
        route_env, tmp_path):
    path, version = _upload(route_env, tmp_path)
    binding = resource_binding(_resolved_upload(route_env, path, version))

    assert binding["document_id"] == RUN7_DOC_ID
    assert binding["resource_id"] == RUN7_DOC_ID
    assert binding["source"] == "manual_upload"
    assert binding["representation"] == "document_text"
    assert binding["source_version"] == version


def test_run7_upload_binding_is_consumable_and_rechecks(
        route_env, tmp_path):
    path, version = _upload(route_env, tmp_path)
    resolved = _resolved_upload(route_env, path, version)
    # The exact shape persisted by the failing run: resource_id names the
    # uploaded document, but the binding predates the explicit document_id.
    binding = resource_binding(resolved)
    binding.pop("document_id", None)

    step = _accepted_read(path, binding)
    assignment = new_assignment(
        objective="Reconcile invoice INV-TRIGGER-91 for PO-TRIGGER-63",
        workspace_id="ws-1", tenant_id="tenant-1", steps=[step])

    assert route_env["executor"]._source_consumption_gap(
        assignment, {}) is None

    rechecked = recheck_resource_access(
        route_env["db"], route_env["users"]["lead"], binding)
    assert rechecked["resource_id"] == RUN7_DOC_ID
    assert rechecked["document_id"] == RUN7_DOC_ID
    assert rechecked["path"] == str(path)
    assert rechecked["source_version"] == version


def test_source_route_applies_uploaded_document_without_parking(
        route_env, tmp_path):
    _path, version = _upload(route_env, tmp_path)
    po_path = tmp_path / "purchase-order.json"
    po_path.write_text(json.dumps({
        "po_id": "PO-TRIGGER-63", "vendor_id": "V-6",
        "quantity": "3", "unit_price": "42.50", "currency": "USD"}))
    po_binding = resource_binding(resolve_assignment_source(
        route_env["db"], route_env["users"]["lead"],
        {"kind": "document", "path": str(po_path)}, allow_internal=True))
    po_step = _accepted_read(po_path, po_binding)
    po_step["step_id"] = "source-1"
    plan = new_assignment(
        objective="Reconcile invoice INV-TRIGGER-91 for PO-TRIGGER-63",
        employee_id="lead-1", workspace_id="ws-1", tenant_id="tenant-1",
        steps=[po_step], authorized_actions=["retrieve"],
        provenance={"use_model": False})
    record = route_env["executor"].create_assignment(
        "conv-upload-source-answer", plan["objective"], assignment=plan)

    response = route_env["client"].post(
        f"/api/assignments/{record['run_id']}/sources",
        json={
            "source": {
                "kind": "document",
                "document_id": RUN7_DOC_ID,
                "source_version": version,
            },
            "reason": "the user supplied the incomplete invoice",
        })
    assert response.status_code == 200, response.text

    assignment = route_env["lifecycle"].get_assignment(record["run_id"])
    step = next(
        item for item in assignment["steps"]
        if item["adapter"] == "document.text"
        and item["inputs"]["resource_binding"]["resource_id"]
        == RUN7_DOC_ID)
    assert step["status"] == "applied", step
    assert not step.get("gap_ids"), step
    assert step["inputs"]["resource_binding"]["document_id"] == RUN7_DOC_ID
    assert step["result"]["data"]["unit_price"] is None
    assert not any(
        item["adapter"] == "invoice.reconcile"
        for item in assignment["steps"]), (
            "the partial invoice must stay unresolved")
