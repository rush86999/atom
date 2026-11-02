"""Typed, user-authored canvas fields: stable IDs, units and server totals.

These are the successor-batch controls for three differently shaped canvases
(industrial quote, service proposal, non-sales exception queue). They exercise
the existing canvas capability store and operation route; no per-canvas Python
and no second calculation engine are involved.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.auth import get_current_user
from core.canvas_capability_service import (
    CapabilityError,
    answer_derive_clarification,
    bind_dataset,
    current_revision,
    derive_operation,
    edit_operation,
    effective_operations,
    get_dataset,
    get_manifest,
    set_manifest,
)
from core.database import Base, get_db
from core.deployment_audience import require_pilot_user
from core.models import Canvas


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def user():
    return SimpleNamespace(
        id="typed-user", workspace_id="ws-typed", tenant_id="tenant-typed",
        role="workspace_admin", is_active=True,
    )


def _quote_fields():
    return [
        {"id": "item_id", "label": "Item", "type": "string",
         "column": "Item", "required": True},
        {"id": "quantity", "label": "Quantity", "type": "decimal",
         "column": "Qty", "unit": "each", "required": True, "editable": True},
        {"id": "unit_price", "label": "Unit price", "type": "currency",
         "column": "Price", "currency": "USD", "required": True,
         "editable": True},
        {"id": "line_total", "label": "Line total", "type": "currency",
         "column": "Line Total", "currency": "USD",
         "derived": "quantity * unit_price", "aggregate": "sum",
         "group_by": "item_id"},
    ]


def _quote_manifest():
    return {
        "schema_version": 2,
        "base_component": "table",
        "operations": ["read", "derive", "edit", "export", "bind"],
        "data_binding": {"subject_field": "Item"},
        "fields": _quote_fields(),
        "outputs": ["xlsx"],
    }


def _service_manifest():
    return {
        "schema_version": 2,
        "base_component": "form",
        "operations": ["read", "derive", "edit", "bind"],
        "data_binding": {"subject_field": "Service"},
        "fields": [
            {"id": "service", "label": "Service", "type": "string",
             "column": "Service", "required": True},
            {"id": "hours", "label": "Hours", "type": "decimal",
             "column": "Hours", "unit": "hour", "required": True,
             "editable": True},
            {"id": "rate", "label": "Rate", "type": "currency",
             "column": "Rate", "currency": "CAD", "required": True,
             "editable": True},
            {"id": "fee_total", "label": "Fee total", "type": "currency",
             "column": "Fee Total", "currency": "CAD",
             "derived": "hours * rate", "aggregate": "sum",
             "group_by": "service"},
        ],
        "outputs": ["xlsx"],
    }


def _queue_manifest():
    return {
        "schema_version": 2,
        "base_component": "queue",
        "operations": ["read", "derive", "edit", "select", "bind"],
        "data_binding": {"subject_field": "Exception", "status_field": "Status"},
        "fields": [
            {"id": "exception_id", "label": "Exception", "type": "string",
             "column": "Exception", "required": True,
             "aggregate": "count", "group_by": "status"},
            {"id": "amount", "label": "Amount", "type": "currency",
             "column": "Amount", "currency": "USD", "required": True,
             "editable": True, "aggregate": "sum", "group_by": "status"},
            {"id": "status", "label": "Status", "type": "string",
             "column": "Status", "required": True, "editable": True},
        ],
        "outputs": ["xlsx"],
    }


def _canvas(db, user, canvas_id, name, base="table"):
    row = Canvas(
        id=canvas_id, tenant_id=user.tenant_id,
        workspace_id=user.workspace_id, created_by=user.id,
        name=name, canvas_type=base, content={}, status="active",
    )
    db.add(row)
    db.commit()
    return row


def _bind_and_derive(db, user, canvas, manifest, columns, rows):
    set_manifest(db, canvas, user, manifest)
    bound = bind_dataset(
        db, canvas, user, columns, rows,
        source={"file_name": f"{canvas.id}.csv"},
    )
    result = derive_operation(
        db, canvas, user,
        expected_revision=bound["revision"],
        manifest_revision_value=bound["manifest"]["manifest_revision"],
        source_version=bound["source"]["source_version"],
    )
    return bound, result


def test_three_typed_canvases_derive_server_totals(db, user):
    quote = _canvas(db, user, "canvas_typed_quote", "Industrial quote")
    service = _canvas(
        db, user, "canvas_typed_service", "Service proposal", base="form")
    queue = _canvas(
        db, user, "canvas_typed_queue", "Exception queue", base="queue")

    quote_bound, quote_result = _bind_and_derive(
        db, user, quote, _quote_manifest(),
        ["Item", "Qty", "Price"],
        [["A", "2", "100.00"], ["B", "3", "50.00"]],
    )
    assert quote_result["aggregates"]["line_total"] == "350.00"
    assert quote_result["groups"] == [
        {"field_id": "line_total", "group_by": "item_id",
         "group": "A", "value": "200.00"},
        {"field_id": "line_total", "group_by": "item_id",
         "group": "B", "value": "150.00"},
    ]
    assert quote_result["rows"][0]["values"]["line_total"] == "200.00"
    assert quote_result["input_receipt"]["fields"][3]["unit"] == "USD"

    service_bound, service_result = _bind_and_derive(
        db, user, service, _service_manifest(),
        ["Service", "Hours", "Rate"],
        [["Consulting", "4", "120.00"], ["Site trip", "2", "75.00"]],
    )
    assert service_result["aggregates"]["fee_total"] == "630.00"
    assert service_result["input_receipt"]["fields"][2]["currency"] == "CAD"
    assert service_result["rows"][0]["values"]["fee_total"] == "480.00"

    queue_bound, queue_result = _bind_and_derive(
        db, user, queue, _queue_manifest(),
        ["Exception", "Amount", "Status"],
        [["EX-1", "100.00", "Open"],
         ["EX-2", "50.00", "Open"],
         ["EX-3", "20.00", "Closed"]],
    )
    assert queue_result["aggregates"] == {
        "exception_id": 3, "amount": "170.00"}
    assert queue_result["groups"] == [
        {"field_id": "exception_id", "group_by": "status",
         "group": "Closed", "value": 1},
        {"field_id": "exception_id", "group_by": "status",
         "group": "Open", "value": 2},
        {"field_id": "amount", "group_by": "status",
         "group": "Closed", "value": "20.00"},
        {"field_id": "amount", "group_by": "status",
         "group": "Open", "value": "150.00"},
    ]
    for canvas, bound in (
            (quote, quote_bound), (service, service_bound),
            (queue, queue_bound)):
        operations = effective_operations(canvas)
        assert "derive" in operations["effective"]
        assert operations["declared"] == sorted(
            get_manifest(canvas)["operations"])
        assert bound["manifest"]["manifest_revision"] == get_manifest(
            canvas)["manifest_revision"]


def test_unknown_widget_action_field_and_unit_are_refused(db, user):
    canvas = _canvas(db, user, "canvas_typed_refuse", "Refusals")
    with pytest.raises(CapabilityError) as exc:
        set_manifest(db, canvas, user, {
            **_quote_manifest(), "base_component": "mystery_grid"})
    assert exc.value.code == "unsupported_adapter"

    with pytest.raises(CapabilityError) as exc:
        set_manifest(db, canvas, user, {
            **_quote_manifest(),
            "actions": [{"id": "send", "operation": "totally.missing"}]})
    assert exc.value.code == "unsupported_action"

    with pytest.raises(CapabilityError) as exc:
        set_manifest(db, canvas, user, {
            **_quote_manifest(),
            "fields": [
                *(_quote_fields()[:-1]),
                {**_quote_fields()[-1], "derived": "quantity * mystery"},
            ]})
    assert exc.value.code == "unsupported_field_reference"

    with pytest.raises(CapabilityError) as exc:
        set_manifest(db, canvas, user, {
            **_quote_manifest(),
            "fields": [{"id": "quantity", "label": "Qty",
                        "type": "decimal", "column": "Qty"}]})
    assert exc.value.code == "missing_unit"

    with pytest.raises(CapabilityError) as exc:
        set_manifest(db, canvas, user, {
            **_quote_manifest(), "schema_version": 3})
    assert exc.value.code == "unsupported_manifest_version"


def test_missing_required_value_is_targeted_and_zero_is_not_missing(db, user):
    canvas = _canvas(db, user, "canvas_typed_missing", "Missing value")
    set_manifest(db, canvas, user, _quote_manifest())
    bound = bind_dataset(
        db, canvas, user, ["Item", "Qty", "Price"],
        [["A", "", "100.00"]], source={"file_name": "missing.csv"})
    with pytest.raises(CapabilityError) as exc:
        derive_operation(
            db, canvas, user,
            expected_revision=bound["revision"],
            manifest_revision_value=bound["manifest"]["manifest_revision"],
            source_version=bound["source"]["source_version"],
        )
    assert exc.value.code == "missing_required_value"
    assert exc.value.status_code == 409
    missing = exc.value.extra["missing"]
    assert missing[0]["row"] == 2
    assert missing[0]["field_id"] == "quantity"

    zero = _canvas(db, user, "canvas_typed_zero", "Zero value")
    _, result = _bind_and_derive(
        db, user, zero, _quote_manifest(), ["Item", "Qty", "Price"],
        [["A", "0", "100.00"]])
    assert result["aggregates"]["line_total"] == "0.00"
    assert result["rows"][0]["values"]["quantity"] == "0.00"
    assert result["rows"][0]["values"]["line_total"] == "0.00"


def test_forged_total_column_and_unknown_request_field_cannot_change_total(
        db, user):
    canvas = _canvas(db, user, "canvas_typed_forged", "Forged total")
    manifest = _quote_manifest()
    set_manifest(db, canvas, user, manifest)
    bound = bind_dataset(
        db, canvas, user, ["Item", "Qty", "Price", "Total"],
        [["A", "2", "100.00", "999.00"]],
        source={"file_name": "forged.csv"})
    result = derive_operation(
        db, canvas, user,
        expected_revision=bound["revision"],
        manifest_revision_value=bound["manifest"]["manifest_revision"],
        source_version=bound["source"]["source_version"],
    )
    # The untyped client Total column is not in the manifest and cannot be a
    # calculation input.
    assert result["aggregates"]["line_total"] == "200.00"
    assert "Total" not in [item["column"] for item in result["input_receipt"][
        "fields"]]


def test_stale_revision_manifest_source_and_edit_refuse(db, user):
    canvas = _canvas(db, user, "canvas_typed_stale", "Stale state")
    set_manifest(db, canvas, user, _quote_manifest())
    bound = bind_dataset(
        db, canvas, user, ["Item", "Qty", "Price"],
        [["A", "2", "100.00"]], source={"file_name": "stale.csv"})
    revisions = {
        "expected_revision": bound["revision"],
        "manifest_revision_value": bound["manifest"]["manifest_revision"],
        "source_version": bound["source"]["source_version"],
    }
    edit_operation(
        db, canvas, user, [{"row": 2, "column": "Qty", "value": "3"}],
        expected_revision=bound["revision"],
    )
    with pytest.raises(CapabilityError) as exc:
        derive_operation(db, canvas, user, **revisions)
    assert exc.value.code == "stale_revision"

    current = current_revision(canvas)
    changed = set_manifest(db, canvas, user, {
        **_quote_manifest(),
        "task_policy": "changed rule",
        "decision_options": ["REVIEW"],
    })
    with pytest.raises(CapabilityError) as exc:
        derive_operation(
            db, canvas, user, expected_revision=current,
            manifest_revision_value=bound["manifest"]["manifest_revision"],
            source_version=bound["manifest"]["data_binding"]["source_version"],
        )
    assert exc.value.code == "stale_manifest"

    set_manifest(db, canvas, user, _quote_manifest())
    current = current_revision(canvas)
    current_manifest = get_manifest(canvas)
    rebind = bind_dataset(
        db, canvas, user, ["Item", "Qty", "Price"],
        [["A", "2", "100.00"], ["B", "1", "10.00"]],
        source={"file_name": "stale-v2.csv"})
    with pytest.raises(CapabilityError) as exc:
        derive_operation(
            db, canvas, user, expected_revision=rebind["revision"],
            manifest_revision_value=rebind["manifest"]["manifest_revision"],
            source_version=bound["source"]["source_version"],
        )
    assert exc.value.code == "stale_source"


def test_duplicate_derive_is_stable_and_restart_preserves_receipt(db, user):
    canvas = _canvas(db, user, "canvas_typed_restart", "Restart")
    bound, first = _bind_and_derive(
        db, user, canvas, _quote_manifest(), ["Item", "Qty", "Price"],
        [["A", "2", "100.00"], ["B", "3", "50.00"]])
    second = derive_operation(
        db, canvas, user,
        expected_revision=bound["revision"],
        manifest_revision_value=bound["manifest"]["manifest_revision"],
        source_version=bound["source"]["source_version"],
    )
    assert second["input_receipt"]["digest"] == first["input_receipt"]["digest"]
    assert current_revision(canvas) == bound["revision"]

    # A fresh session is the restart-equivalent authoritative read.
    fresh = db.query(Canvas).filter(Canvas.id == canvas.id).first()
    restored = get_manifest(fresh)
    assert restored["schema_version"] == 2
    third = derive_operation(
        db, fresh, user,
        expected_revision=bound["revision"],
        manifest_revision_value=restored["manifest_revision"],
        source_version=bound["source"]["source_version"],
    )
    assert third["input_receipt"]["digest"] == first["input_receipt"]["digest"]


def test_cross_workspace_reader_is_refused(db, user):
    canvas = _canvas(db, user, "canvas_typed_scope", "Scoped")
    set_manifest(db, canvas, user, _quote_manifest())
    stranger = SimpleNamespace(
        id="other-user", workspace_id="ws-other", tenant_id="tenant-other",
        role="workspace_admin", is_active=True)
    bound = bind_dataset(
        db, canvas, user, ["Item", "Qty", "Price"],
        [["A", "2", "100.00"]], source={"file_name": "scope.csv"})
    with pytest.raises(CapabilityError) as exc:
        derive_operation(
            db, canvas, stranger,
            expected_revision=bound["revision"],
            manifest_revision_value=bound["manifest"]["manifest_revision"],
            source_version=bound["source"]["source_version"],
        )
    assert exc.value.status_code == 403


def test_registered_action_binding_is_declared_not_authority(db, user):
    canvas = _canvas(db, user, "canvas_typed_action", "Action binding")
    manifest = {
        **_quote_manifest(),
        "actions": [{
            "id": "create_estimate",
            "operation": "connected.books.create_estimate",
            "allowed_fields": ["item_id", "quantity", "unit_price"],
            "target": "org-1",
            "authority": "declared grant reference",
        }],
    }
    saved = set_manifest(db, canvas, user, manifest)
    assert saved["manifest"]["actions"][0]["operation"] == (
        "connected.books.create_estimate")
    # A declared binding is not an effective operation and does not widen the
    # operation intersection.
    assert "connected.books.create_estimate" not in saved["operations"][
        "effective"]
    assert "outbound" not in saved["operations"]["effective"]


def test_fork_keeps_typed_shape_but_drops_action_bindings(db, user):
    from core.canvas_capability_service import sanitize_capability_copy

    canvas = _canvas(db, user, "canvas_typed_fork", "Fork")
    manifest = {
        **_quote_manifest(),
        "actions": [{
            "id": "create_estimate",
            "operation": "connected.books.create_estimate",
            "allowed_fields": ["item_id", "quantity"],
        }],
    }
    set_manifest(db, canvas, user, manifest)
    copied = sanitize_capability_copy(canvas.content, "canvas_typed_copy")
    copied_manifest = copied["capability_manifest"]
    assert [item["id"] for item in copied_manifest["fields"]] == [
        "item_id", "quantity", "unit_price", "line_total"]
    assert copied_manifest["actions"] == []
    assert copied_manifest["data_binding"]["resource_id"] == (
        "canvas:canvas_typed_copy")


def test_unknown_action_field_is_refused(db, user):
    canvas = _canvas(db, user, "canvas_typed_action_bad", "Bad action")
    manifest = {
        **_quote_manifest(),
        "actions": [{
            "id": "create_estimate",
            "operation": "connected.books.create_estimate",
            "allowed_fields": ["not_a_field"],
        }],
    }
    with pytest.raises(CapabilityError) as exc:
        set_manifest(db, canvas, user, manifest)
    assert exc.value.code == "unsupported_field_reference"


def _client(db, user):
    from api.canvas_capability_routes import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_pilot_user] = lambda: user
    return TestClient(app)


def test_derive_route_rejects_forged_total_and_accepts_receipt(db, user):
    canvas = _canvas(db, user, "canvas_typed_route", "Route derive")
    set_manifest(db, canvas, user, _quote_manifest())
    bound = bind_dataset(
        db, canvas, user, ["Item", "Qty", "Price"],
        [["A", "2", "100.00"]], source={"file_name": "route.csv"})
    client = _client(db, user)
    body = {
        "expected_revision": bound["revision"],
        "manifest_revision": bound["manifest"]["manifest_revision"],
        "source_version": bound["source"]["source_version"],
    }
    forged = client.post(
        "/api/canvas/canvas_typed_route/capability/derive",
        json={**body, "total": "999.00"})
    assert forged.status_code == 422, forged.text
    accepted = client.post(
        "/api/canvas/canvas_typed_route/capability/derive", json=body)
    assert accepted.status_code == 200, accepted.text
    payload = accepted.json()
    assert payload["aggregates"]["line_total"] == "200.00"
    assert payload["input_receipt"]["digest"]
    stale = client.post(
        "/api/canvas/canvas_typed_route/capability/derive",
        json={**body, "expected_revision": bound["revision"] + 1})
    assert stale.status_code == 409, stale.text
    assert stale.json()["error"]["code"] == "stale_revision"


def test_missing_value_clarification_resumes_the_same_derive(db, user):
    canvas = _canvas(db, user, "canvas_typed_clarify", "Clarify")
    set_manifest(db, canvas, user, _quote_manifest())
    bound = bind_dataset(
        db, canvas, user, ["Item", "Qty", "Price"],
        [["A", "", "100.00"]], source={"file_name": "clarify.csv"})
    client = _client(db, user)
    body = {
        "expected_revision": bound["revision"],
        "manifest_revision": bound["manifest"]["manifest_revision"],
        "source_version": bound["source"]["source_version"],
    }
    opened = client.post(
        "/api/canvas/canvas_typed_clarify/capability/derive", json=body)
    assert opened.status_code == 200, opened.text
    payload = opened.json()
    assert payload["status"] == "clarification"
    clarification = payload["clarification"]
    assert clarification["missing"][0]["field_id"] == "quantity"
    assert clarification["missing"][0]["row"] == 2

    answer = {
        "expected_revision": bound["revision"],
        "answers": [{"row": 2, "field_id": "quantity", "value": "2"}],
    }
    stale = client.post(
        f"/api/canvas/canvas_typed_clarify/capability/derive/"
        f"{clarification['id']}/answer",
        json={**answer, "expected_revision": bound["revision"] + 1})
    assert stale.status_code == 409, stale.text
    assert stale.json()["error"]["code"] == "stale_revision"

    resumed = client.post(
        f"/api/canvas/canvas_typed_clarify/capability/derive/"
        f"{clarification['id']}/answer", json=answer)
    assert resumed.status_code == 200, resumed.text
    resumed_body = resumed.json()
    assert resumed_body["status"] == "resolved"
    assert resumed_body["result"]["aggregates"]["line_total"] == "200.00"

    duplicate = client.post(
        f"/api/canvas/canvas_typed_clarify/capability/derive/"
        f"{clarification['id']}/answer", json=answer)
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["status"] == "already_resolved"

    conflict = client.post(
        f"/api/canvas/canvas_typed_clarify/capability/derive/"
        f"{clarification['id']}/answer",
        json={"expected_revision": bound["revision"] + 1,
              "answers": [{"row": 2, "field_id": "quantity", "value": "3"}]})
    assert conflict.status_code == 409, conflict.text

    # A later edit invalidates the resolved clarification; an old duplicate
    # answer must not be reported as the current result.
    current = current_revision(canvas)
    edit_operation(
        db, canvas, user, [{"row": 2, "column": "Qty", "value": "4"}],
        expected_revision=current)
    stale_duplicate = client.post(
        f"/api/canvas/canvas_typed_clarify/capability/derive/"
        f"{clarification['id']}/answer", json=answer)
    assert stale_duplicate.status_code == 409, stale_duplicate.text
    assert stale_duplicate.json()["error"]["code"] == "stale_revision"


def test_typed_string_and_receipt_limits_refuse_without_partial_total(
        db, user, monkeypatch):
    canvas = _canvas(db, user, "canvas_typed_limits", "Limits")
    manifest = {
        "schema_version": 2,
        "base_component": "table",
        "operations": ["read", "derive", "bind"],
        "fields": [
            {"id": "item_id", "label": "Item", "type": "string",
             "column": "Item", "required": True},
            {"id": "note", "label": "Note", "type": "string",
             "column": "Note"},
        ],
        "outputs": ["xlsx"],
    }
    set_manifest(db, canvas, user, manifest)
    bound = bind_dataset(
        db, canvas, user, ["Item", "Note"],
        [["A", "x" * 20001]], source={"file_name": "limits.csv"})
    with pytest.raises(CapabilityError) as exc:
        derive_operation(
            db, canvas, user,
            expected_revision=bound["revision"],
            manifest_revision_value=bound["manifest"]["manifest_revision"],
            source_version=bound["source"]["source_version"],
        )
    assert exc.value.code == "invalid_field_value"

    monkeypatch.setenv("ATOM_CANVAS_DERIVE_MAX_BYTES", "1000")
    small = _canvas(db, user, "canvas_typed_small", "Small")
    set_manifest(db, small, user, _quote_manifest())
    bound = bind_dataset(
        db, small, user, ["Item", "Qty", "Price"],
        [["A", "2", "100.00"]], source={"file_name": "small.csv"})
    with pytest.raises(CapabilityError) as exc:
        derive_operation(
            db, small, user,
            expected_revision=bound["revision"],
            manifest_revision_value=bound["manifest"]["manifest_revision"],
            source_version=bound["source"]["source_version"],
        )
    assert exc.value.code == "receipt_too_large"


def test_declared_custom_code_runtime_is_refused_without_host_fallback(
        monkeypatch):
    from core.mini_app_runtime import get_miniapp_runtime

    monkeypatch.setenv("ATOM_MINIAAP_RUNTIME", "firecracker")
    monkeypatch.delenv("FIRECRACKER_KERNEL_IMAGE", raising=False)
    monkeypatch.delenv("FIRECRACKER_ROOTFS_TEMPLATE", raising=False)
    with pytest.raises(RuntimeError) as exc:
        get_miniapp_runtime()
    assert "Firecracker runtime unavailable" in str(exc.value)
    assert "host execution" not in str(exc.value).lower()


def _currency_fields():
    return [
        {"id": "item", "label": "Item", "type": "string",
         "column": "Item", "required": True},
        {"id": "usd", "label": "USD", "type": "currency",
         "column": "USD", "currency": "USD", "required": True},
        {"id": "cad", "label": "CAD", "type": "currency",
         "column": "CAD", "currency": "CAD", "required": True},
    ]


def _with_total(fields, expression, *, field_type="currency",
                currency="USD", unit=""):
    return fields + [{
        "id": "total", "label": "Total", "type": field_type,
        "column": "Total", "currency": currency, "unit": unit,
        "derived": expression, "aggregate": "sum",
    }]


def test_mixed_currency_and_hidden_currency_are_refused_at_manifest(db, user):
    canvas = _canvas(db, user, "canvas_currency_refuse", "Currency refuse")
    for fields in (
        _with_total(_currency_fields(), "usd + cad"),
        _with_total(_currency_fields()[2:], "cad", currency="USD"),
        _with_total(
            _currency_fields()[:2] + [
                {"id": "hours", "label": "Hours", "type": "decimal",
                 "column": "Hours", "unit": "hour", "required": True},
            ], "usd + hours"),
        _with_total(
            _currency_fields()[:2] + [
                {"id": "usd_copy", "label": "USD copy", "type": "decimal",
                 "column": "USD Copy", "unit": "USD",
                 "derived": "usd"},
            ], "usd_copy"),
        _with_total(
            _currency_fields()[:1] + [
                {"id": "note", "label": "Note", "type": "string",
                 "column": "Note", "required": True},
            ], "note + 1"),
    ):
        with pytest.raises(CapabilityError) as exc:
            set_manifest(db, canvas, user, {
                "schema_version": 2, "base_component": "table",
                "operations": ["read", "derive", "bind"],
                "data_binding": {"subject_field": "Item"},
                "fields": fields,
            })
        assert exc.value.code in {
            "incompatible_currency", "incompatible_units",
            "derived_type_mismatch", "unsupported_expression_type",
        }, exc.value.code


def test_same_currency_addition_and_rate_multiplication_are_accepted(db, user):
    canvas = _canvas(db, user, "canvas_currency_accept", "Currency accept")
    manifest = {
        "schema_version": 2, "base_component": "table",
        "operations": ["read", "derive", "bind"],
        "data_binding": {"subject_field": "Item"},
        "fields": _with_total(_currency_fields(), "usd + cad",
                              currency="USD"),
    }
    # Same-currency addition is compatible: use two USD fields.
    manifest["fields"] = _with_total(
        _currency_fields()[:2] + [
            {"id": "usd_2", "label": "USD 2", "type": "currency",
             "column": "USD 2", "currency": "USD", "required": True},
        ], "usd + usd_2")
    bound, result = _bind_and_derive(
        db, user, canvas, manifest, ["Item", "USD", "CAD", "USD 2"],
        [["A", "10.00", "20.00", "5.00"]])
    assert result["aggregates"]["total"] == "15.00"

    rate_canvas = _canvas(
        db, user, "canvas_currency_rate", "Currency rate")
    rate_manifest = {
        "schema_version": 2, "base_component": "table",
        "operations": ["read", "derive", "bind"],
        "data_binding": {"subject_field": "Item"},
        "fields": [
            {"id": "item", "label": "Item", "type": "string",
             "column": "Item", "required": True},
            {"id": "quantity", "label": "Quantity", "type": "decimal",
             "column": "Qty", "unit": "each", "required": True},
            {"id": "unit_price", "label": "Unit price", "type": "currency",
             "column": "Price", "currency": "USD", "required": True},
            {"id": "total", "label": "Total", "type": "currency",
             "column": "Total", "currency": "USD",
             "derived": "quantity * unit_price", "aggregate": "sum"},
        ],
    }
    _bind_and_derive(
        db, user, rate_canvas, rate_manifest, ["Item", "Qty", "Price"],
        [["A", "2", "10.00"]])
    # The quote/service positive cases are covered above; this explicitly
    # proves count x currency uses the bounded rate contract, not generic
    # unit algebra.
    assert result["aggregates"]["total"] == "15.00"


def test_old_open_clarification_refuses_replacement_source(db, user):
    canvas = _canvas(db, user, "canvas_old_question", "Old question")
    set_manifest(db, canvas, user, _quote_manifest())
    first = bind_dataset(
        db, canvas, user, ["Item", "Qty", "Price"],
        [["A", "", "100.00"]], source={"file_name": "a.csv"})
    client = _client(db, user)
    opened = client.post(
        "/api/canvas/canvas_old_question/capability/derive",
        json={
            "expected_revision": first["revision"],
            "manifest_revision": first["manifest"]["manifest_revision"],
            "source_version": first["source"]["source_version"],
        })
    assert opened.status_code == 200, opened.text
    question = opened.json()["clarification"]
    assert question["binding"]["missing"][0]["subject"] == "A"

    replacement = bind_dataset(
        db, canvas, user, ["Item", "Qty", "Price"],
        [["B", "", "1000.00"]], source={"file_name": "b.csv"})
    refused = client.post(
        f"/api/canvas/canvas_old_question/capability/derive/"
        f"{question['id']}/answer",
        json={
            "expected_revision": replacement["revision"],
            "answers": [{"row": 2, "field_id": "quantity", "value": "2"}],
        })
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "stale_clarification"
    assert "source.source_version" in refused.json()["error"]["reasons"]

    # No edit reached the replacement source, and the old question remains
    # open with its refused attempt; a fresh question binds the new subject.
    dataset = get_dataset(canvas)
    assert dataset["rows"][0][:3] == ["B", "", "1000.00"]
    durable = get_manifest(canvas)
    assert durable["manifest_revision"] == replacement[
        "manifest"]["manifest_revision"]
    question_after = json.loads(json.dumps(
        canvas.content["capability_derive_clarification"]))
    assert question_after["status"] == "open"
    assert question_after["refused_answers"][-1]["reasons"]

    fresh_client = _client(db, user)
    reasked = fresh_client.post(
        "/api/canvas/canvas_old_question/capability/derive",
        json={
            "expected_revision": current_revision(canvas),
            "manifest_revision": durable["manifest_revision"],
            "source_version": dataset["source"]["source_version"],
        })
    assert reasked.status_code == 200, reasked.text
    new_question = reasked.json()["clarification"]
    assert new_question["id"] != question["id"]
    assert new_question["binding"]["missing"][0]["subject"] == "B"
    assert new_question["binding"]["source"]["file_name"] == "b.csv"


def test_stale_session_old_answer_cannot_replace_newer_source(db, user):
    from sqlalchemy.orm import sessionmaker

    canvas = _canvas(db, user, "canvas_lost_update", "Lost update")
    set_manifest(db, canvas, user, _quote_manifest())
    first = bind_dataset(
        db, canvas, user, ["Item", "Qty", "Price"],
        [["A", "", "100.00"]], source={"file_name": "lost-a.csv"})
    client = _client(db, user)
    question = client.post(
        "/api/canvas/canvas_lost_update/capability/derive",
        json={
            "expected_revision": first["revision"],
            "manifest_revision": first["manifest"]["manifest_revision"],
            "source_version": first["source"]["source_version"],
        }).json()["clarification"]
    writer = sessionmaker(bind=db.get_bind(), expire_on_commit=False)()
    try:
        replacement = writer.query(Canvas).filter(
            Canvas.id == canvas.id).one()
        replacement_result = bind_dataset(
            writer, replacement, user, ["Item", "Qty", "Price"],
            [["B", "", "1000.00"]], source={"file_name": "lost-b.csv"})
        with pytest.raises(CapabilityError) as exc:
            answer_derive_clarification(
                db, canvas, user, question["id"],
                [{"row": 2, "field_id": "quantity", "value": "2"}],
                expected_revision=first["revision"])
        assert exc.value.code == "stale_clarification"
        writer.expire_all()
        durable = writer.query(Canvas).filter(
            Canvas.id == canvas.id).one()
        assert get_dataset(durable)["rows"][0][0] == "B"
        assert current_revision(durable) == replacement_result["revision"]
        clarification = durable.content["capability_derive_clarification"]
        assert clarification["status"] != "resolved"
    finally:
        writer.close()


def test_writer_after_validation_but_before_cas_wins(db, user, monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from core import canvas_capability_service as service

    canvas = _canvas(db, user, "canvas_cas_race", "CAS race")
    set_manifest(db, canvas, user, _quote_manifest())
    first = bind_dataset(
        db, canvas, user, ["Item", "Qty", "Price"],
        [["A", "", "100.00"]], source={"file_name": "race-a.csv"})
    client = _client(db, user)
    question = client.post(
        "/api/canvas/canvas_cas_race/capability/derive",
        json={
            "expected_revision": first["revision"],
            "manifest_revision": first["manifest"]["manifest_revision"],
            "source_version": first["source"]["source_version"],
        }).json()["clarification"]
    original_derive = service.derive_operation
    writer = sessionmaker(bind=db.get_bind(), expire_on_commit=False)()

    def racing_derive(*args, **kwargs):
        result = original_derive(*args, **kwargs)
        replacement = writer.query(Canvas).filter(
            Canvas.id == canvas.id).one()
        bind_dataset(
            writer, replacement, user, ["Item", "Qty", "Price"],
            [["B", "", "1000.00"]], source={"file_name": "race-b.csv"})
        return result

    monkeypatch.setattr(service, "derive_operation", racing_derive)
    try:
        with pytest.raises(CapabilityError) as exc:
            answer_derive_clarification(
                db, canvas, user, question["id"],
                [{"row": 2, "field_id": "quantity", "value": "2"}],
                expected_revision=first["revision"])
        assert exc.value.code == "concurrent_edit"
        writer.expire_all()
        durable = writer.query(Canvas).filter(
            Canvas.id == canvas.id).one()
        rows = get_dataset(durable)["rows"]
        assert rows[0][0] == "B"
        assert rows[0][1] == ""
        assert durable.content["capability_derive_clarification"][
            "status"] != "resolved"
    finally:
        writer.close()


def test_failed_derive_rolls_back_answer_and_keeps_question_open(db, user):
    canvas = _canvas(db, user, "canvas_answer_rollback", "Rollback")
    set_manifest(db, canvas, user, _quote_manifest())
    first = bind_dataset(
        db, canvas, user, ["Item", "Qty", "Price"],
        [["A", "", "100.00"]], source={"file_name": "rollback.csv"})
    client = _client(db, user)
    question = client.post(
        "/api/canvas/canvas_answer_rollback/capability/derive",
        json={
            "expected_revision": first["revision"],
            "manifest_revision": first["manifest"]["manifest_revision"],
            "source_version": first["source"]["source_version"],
        }).json()["clarification"]
    failed = client.post(
        f"/api/canvas/canvas_answer_rollback/capability/derive/"
        f"{question['id']}/answer",
        json={
            "expected_revision": first["revision"],
            "answers": [{"row": 2, "field_id": "quantity",
                         "value": "not-a-number"}],
        })
    assert failed.status_code == 400, failed.text
    assert failed.json()["error"]["code"] == "invalid_field_value"
    current = db.query(Canvas).filter(Canvas.id == canvas.id).first()
    assert get_dataset(current)["rows"][0][1] == ""
    assert current_revision(current) == first["revision"]
    clarification = current.content["capability_derive_clarification"]
    assert clarification["status"] == "open"
    assert clarification["refused_answers"][-1]["reasons"] == [
        "derive_invalid_field_value"]


def test_answer_refuses_after_an_edit_with_a_new_revision(db, user):
    canvas = _canvas(db, user, "canvas_answer_edit", "Answer edit")
    set_manifest(db, canvas, user, _quote_manifest())
    first = bind_dataset(
        db, canvas, user, ["Item", "Qty", "Price"],
        [["A", "", "100.00"]], source={"file_name": "answer-edit.csv"})
    client = _client(db, user)
    question = client.post(
        "/api/canvas/canvas_answer_edit/capability/derive",
        json={
            "expected_revision": first["revision"],
            "manifest_revision": first["manifest"]["manifest_revision"],
            "source_version": first["source"]["source_version"],
        }).json()["clarification"]
    edit_operation(
        db, canvas, user, [{"row": 2, "column": "Qty", "value": "5"}],
        expected_revision=first["revision"])
    refused = client.post(
        f"/api/canvas/canvas_answer_edit/capability/derive/"
        f"{question['id']}/answer",
        json={
            "expected_revision": current_revision(canvas),
            "answers": [{"row": 2, "field_id": "quantity", "value": "2"}],
        })
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "stale_clarification"
    assert "state_revision" in refused.json()["error"]["reasons"]
    assert get_dataset(canvas)["rows"][0][1] == "5"


def test_open_question_resolves_after_a_fresh_session(db, user):
    from sqlalchemy.orm import sessionmaker

    canvas = _canvas(db, user, "canvas_answer_restart", "Answer restart")
    set_manifest(db, canvas, user, _quote_manifest())
    first = bind_dataset(
        db, canvas, user, ["Item", "Qty", "Price"],
        [["A", "", "100.00"]], source={"file_name": "restart.csv"})
    client = _client(db, user)
    question = client.post(
        "/api/canvas/canvas_answer_restart/capability/derive",
        json={
            "expected_revision": first["revision"],
            "manifest_revision": first["manifest"]["manifest_revision"],
            "source_version": first["source"]["source_version"],
        }).json()["clarification"]
    second = sessionmaker(bind=db.get_bind(), expire_on_commit=False)()
    try:
        fresh = second.query(Canvas).filter(
            Canvas.id == canvas.id).first()
        fresh_client = _client(second, user)
        resumed = fresh_client.post(
            f"/api/canvas/canvas_answer_restart/capability/derive/"
            f"{question['id']}/answer",
            json={
                "expected_revision": current_revision(fresh),
                "answers": [{"row": 2, "field_id": "quantity",
                             "value": "2"}],
            })
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["status"] == "resolved"
        assert resumed.json()["result"]["aggregates"]["line_total"] == (
            "200.00")
    finally:
        second.close()


def test_answer_refuses_after_manifest_or_edit_change(db, user):
    canvas = _canvas(db, user, "canvas_old_manifest", "Old manifest")
    set_manifest(db, canvas, user, _quote_manifest())
    first = bind_dataset(
        db, canvas, user, ["Item", "Qty", "Price"],
        [["A", "", "100.00"]], source={"file_name": "manifest.csv"})
    client = _client(db, user)
    opened = client.post(
        "/api/canvas/canvas_old_manifest/capability/derive",
        json={
            "expected_revision": first["revision"],
            "manifest_revision": first["manifest"]["manifest_revision"],
            "source_version": first["source"]["source_version"],
        }).json()
    question = opened["clarification"]

    changed = set_manifest(db, canvas, user, {
        **_quote_manifest(),
        "task_policy": "changed after question",
    })
    refused = client.post(
        f"/api/canvas/canvas_old_manifest/capability/derive/"
        f"{question['id']}/answer",
        json={
            "expected_revision": current_revision(canvas),
            "answers": [{"row": 2, "field_id": "quantity", "value": "2"}],
        })
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "stale_clarification"
    assert "manifest_revision" in refused.json()["error"]["reasons"]
    assert changed["manifest"]["manifest_revision"] != (
        first["manifest"]["manifest_revision"])
    assert get_dataset(canvas)["rows"][0][1] == ""


def test_stale_session_answer_cannot_overwrite_replacement_source(db, user):
    """Two sessions: A's cached question must not write over B's dataset.

    The answer is submitted with the replacement's current revision, so a
    revision-only check is insufficient. The database CAS must reject the
    write and a fresh session must still see B.
    """
    from sqlalchemy.orm import Session

    canvas = _canvas(db, user, "canvas_stale_session", "Stale session")
    set_manifest(db, canvas, user, _quote_manifest())
    bound = bind_dataset(
        db, canvas, user, ["Item", "Qty", "Price"],
        [["A", "", "100.00"]], source={"file_name": "a.csv"})
    client = _client(db, user)
    opened = client.post(
        "/api/canvas/canvas_stale_session/capability/derive",
        json={
            "expected_revision": bound["revision"],
            "manifest_revision": bound["manifest"]["manifest_revision"],
            "source_version": bound["source"]["source_version"],
        })
    question = opened.json()["clarification"]

    writer = Session(bind=db.get_bind(), expire_on_commit=False)
    try:
        replacement = writer.query(Canvas).filter(
            Canvas.id == canvas.id).one()
        rebound = bind_dataset(
            writer, replacement, user, ["Item", "Qty", "Price"],
            [["B", "", "1000.00"]], source={"file_name": "b.csv"})
        with pytest.raises(CapabilityError) as exc:
            from core.canvas_capability_service import (
                answer_derive_clarification,
            )
            answer_derive_clarification(
                db, canvas, user, question["id"],
                [{"row": 2, "field_id": "quantity", "value": "2"}],
                expected_revision=rebound["revision"])
        assert exc.value.code in {
            "stale_clarification", "concurrent_edit"}
        # The writer session is authoritative; B is unchanged.
        writer.expire_all()
        durable = writer.query(Canvas).filter(Canvas.id == canvas.id).one()
        assert get_dataset(durable)["rows"][0][:3] == [
            "B", "", "1000.00"]
        assert current_revision(durable) == rebound["revision"]

        # A fresh session sees the same intact replacement, not A's answer.
        fresh = Session(bind=db.get_bind(), expire_on_commit=False)
        try:
            observed = fresh.query(Canvas).filter(
                Canvas.id == canvas.id).one()
            assert get_dataset(observed)["rows"][0][:3] == [
                "B", "", "1000.00"]
            assert get_dataset(observed)["rows"][0][1] == ""
        finally:
            fresh.close()
    finally:
        writer.close()
