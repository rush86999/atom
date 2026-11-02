"""Joint document-byte -> quote -> verified estimate -> Outlook draft flow.

The test changes the returned file bytes and proves the resulting quote
changes, so a preceding read step cannot be satisfied by pre-seeded lines.
"""
from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.assignment_quote  # noqa: F401  (registers quote.calculate)
import core.connected_actions  # noqa: F401  (registers WorkDrive/read actions)
from core.assignment_executor import AssignmentExecutor, default_adapter_registry
from core.assignment_plan import new_assignment, new_step
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.models import GoalObjective, GoalRun, TaskOperationRecord
from core.task_lifecycle import TaskLifecycle


@pytest.fixture()
def env(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/assignment.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  TaskOperationRecord.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    runs = GoalRunService(
        workspace_id="ws_assign", tenant_id="tenant_assign",
        session_factory=factory)
    goals = GoalService(
        workspace_id="ws_assign", tenant_id="tenant_assign",
        session_factory=factory)
    lifecycle = TaskLifecycle(runs, goals)
    registry = default_adapter_registry.clone()
    return {
        "tmp": tmp_path,
        "factory": factory,
        "lifecycle": lifecycle,
        "executor": AssignmentExecutor(lifecycle, adapters=registry),
        "registry": registry,
    }


def _csv(price_b: str = "50.00", discount_b: str = "5") -> bytes:
    return (
        "sku,category,quantity,unit,pack,unit_price,currency,discount_percent\n"
        "A,A,2,each,1,100.00,USD,0\n"
        f"B,B,3,each,1,{price_b},USD,{discount_b}\n"
    ).encode("utf-8")


async def _read_rows(monkeypatch, content: bytes):
    from core import connected_actions as actions

    class FakeWorkDrive:
        async def get_file_metadata(self, user_id, file_id, workspace_id=None):
            return {"id": file_id, "name": "price-list.csv", "version": "v1"}

        async def download_file(self, user_id, file_id, workspace_id=None):
            return content

        async def get_access_token(self, user_id, workspace_id=None):
            return "token"

    async def fake_service(ids):
        return FakeWorkDrive()

    monkeypatch.setattr(actions, "_workdrive_service", fake_service)
    return await actions.workdrive_read_file(
        {"file_id": "file-1", "evidence_kind": "price_rows",
         "customer_id": "customer-1", "price_basis": "customer_contract",
         "effective_date": "2026-11-01"},
        {"user_id": "user-1", "tenant_id": "tenant-1",
         "workspace_id": "ws_assign"})


def _line_items(rows):
    items = []
    for row in rows:
        item = {
            "item_id": str(row["sku"]),
            "description": f"{row['sku']} line",
            "quantity": str(row["quantity"]),
            "unit": str(row["unit"]),
            "pack_size": str(row["pack"]),
            "unit_price": str(row["unit_price"]),
            "price_basis": "contract",
            "currency": str(row["currency"]),
        }
        discount = Decimal(str(row.get("discount_percent") or "0"))
        if discount != 0:
            item["discount_rate"] = str(discount / Decimal("100"))
            item["discount_authority"] = "price-list:v1"
        items.append(item)
    return items


def _run_calculation(env, line_items):
    step = new_step(
        step_id="calculate",
        title="Calculate the quote",
        operation_type="calculate",
        adapter="quote.calculate",
        inputs={
            "line_items": line_items,
            "currency": "USD",
            "freight": "20.00",
            "tax": {"basis": "none"},
            "rounding": "half_up",
            "scale": 2,
            "rounding_authority": "agreement:round-half-up-2dp",
        },
        effect="local",
    )
    plan = new_assignment(
        objective="Calculate a quote from returned document bytes",
        steps=[step], employee_id="user-1",
        workspace_id="ws_assign", tenant_id="tenant_assign",
        budget={"max_steps": 10, "max_attempts_per_step": 3,
                "max_wall_seconds": 300},
    )
    run_id = env["executor"].create_assignment(
        f"conv-{uuid.uuid4().hex[:8]}",
        "Calculate a quote from returned document bytes",
        assignment=plan,
    )["run_id"]
    result = asyncio.run(env["executor"].execute(run_id))["assignment"]
    step_result = next(item for item in result["steps"]
                       if item["step_id"] == "calculate")
    assert step_result["status"] == "applied", step_result
    return step_result["result_value"]


def test_changed_file_bytes_change_the_quote_total(env, monkeypatch):
    read = asyncio.run(_read_rows(monkeypatch, _csv("50.00")))
    assert read["status"] == "success"
    assert read["rows"][1]["unit_price"] == "50.00"

    first = _run_calculation(env, _line_items(read["rows"]))
    assert first == "362.50"

    changed = asyncio.run(_read_rows(monkeypatch, _csv("55.00")))
    assert changed["rows"][1]["unit_price"] == "55.00"
    second = _run_calculation(env, _line_items(changed["rows"]))
    # 2*100 + 3*55 less 5% + 20 freight = 376.75
    assert second == "376.75"


def test_unknown_customer_blocks_quote_evidence():
    from core.quote_evidence import (
        derive_quote_requirements,
        validate_quote_evidence,
    )

    requirements = derive_quote_requirements(
        "Prepare a customer quote", requested={"customer_id": "customer-1"})
    receipts = [{
        "kind": "customer", "provider": "zoho_crm",
        "customer_id": "customer-OTHER", "resource_id": "customer-OTHER",
        "version": "v1", "retrieved_at": "2026-11-01T00:00:00Z",
        "access": "granted", "fields": {"name": "Other Customer"},
    }]
    result = validate_quote_evidence(
        requirements, receipts, requested={"customer_id": "customer-1"})
    assert result["status"] != "ready"
    assert any(item["key"] == "customer_identity"
               for item in result["obligations"])


def test_runtime_quote_reaches_verified_estimate_and_draft(env, monkeypatch):
    from core import connected_actions as actions

    read = asyncio.run(_read_rows(monkeypatch, _csv("50.00")))
    lines = _line_items(read["rows"])
    total = _run_calculation(env, lines)
    assert total == "362.50"

    calls = {"create": 0, "readback": 0, "draft": 0}

    class FakeBooks:
        async def _get_active_token(self, *args, **kwargs):
            return "token"

        async def get_estimates_page(self, token, org, page=1, per_page=200):
            return [], {"has_more": False}

        async def create_estimate(self, token, org, data):
            calls["create"] += 1
            return {"estimate_id": "est-doc-1"}

        async def get_estimate(self, token, org, estimate_id):
            calls["readback"] += 1
            payload = estimate_arguments["estimate_data"]
            return {
                "estimate_id": estimate_id,
                "estimate_number": "EST-DOC-1",
                "customer_id": payload["customer_id"],
                "reference_number": payload["reference_number"],
                "date": payload["date"],
                "currency_code": payload["currency_code"],
                "total": payload["total"],
                "sub_total": payload["sub_total"],
                "tax_total": payload["tax_total"],
                "line_items": payload["line_items"],
            }

    class FakeOutlook:
        def __init__(self):
            self.sent = False

        async def _get_access_token(self, user_id):
            return "token"

        async def create_draft_email(self, **kwargs):
            calls["draft"] += 1
            return {"id": "draft-doc-1", "subject": kwargs["subject"]}

        async def send_email(self, *args, **kwargs):  # pragma: no cover
            self.sent = True
            raise AssertionError("draft must not send")

    service = FakeBooks()
    outlook = FakeOutlook()

    async def fake_books(ids):
        return service

    monkeypatch.setattr(actions, "_books_service", fake_books)
    monkeypatch.setattr(
        "integrations.outlook_service.OutlookService",
        lambda *a, **k: outlook)

    estimate_line_items = []
    for line in lines:
        row = {
            "item_id": line["item_id"], "quantity": line["quantity"],
            "rate": line["unit_price"], "account_id": "acct-1",
        }
        if line.get("discount_rate"):
            row["discount_percent"] = str(
                Decimal(line["discount_rate"]) * Decimal("100"))
        estimate_line_items.append(row)
    estimate_arguments = {
        "organization_id": "org-1",
        "estimate_data": {
            "customer_id": "customer-1",
            "reference_number": "RFQ-DOC-1",
            "date": "2026-11-01",
            "currency_code": "USD",
            "total": total,
            "sub_total": total,
            "tax_total": "0.00",
            "line_items": estimate_line_items,
        },
        "authority_reference": "grant-doc-1",
        "operation_id": "op-doc-1",
    }
    estimate = new_step(
        step_id="estimate", title="Create the verified estimate",
        operation_type="outbound", adapter="action.registry",
        inputs={"action": "connected.books.create_estimate",
                "arguments": estimate_arguments},
        effect="external", approval_required=True,
        approval_purpose="Create the estimate")
    draft = new_step(
        step_id="email-draft", title="Create the Outlook draft",
        operation_type="outbound", adapter="action.registry",
        depends_on=["estimate"],
        inputs={"action": "connected.outlook.create_draft",
                "arguments": {
                    "to": ["buyer@example.invalid"],
                    "subject": "Quote RFQ-DOC-1",
                    "body": f"Quoted total: {total} USD",
                    "operation_id": "op-doc-draft-1",
                }},
        effect="external", approval_required=True,
        approval_purpose="Create the Outlook draft")
    plan = new_assignment(
        objective="Quote from returned document bytes",
        steps=[estimate, draft], authorized_actions=["outbound"],
        employee_id="user-1", workspace_id="ws_assign",
        tenant_id="tenant_assign",
        budget={"max_steps": 20, "max_attempts_per_step": 3,
                "max_wall_seconds": 600},
    )
    run_id = env["executor"].create_assignment(
        f"conv-{uuid.uuid4().hex[:8]}",
        "Quote from returned document bytes", assignment=plan)["run_id"]

    asyncio.run(env["executor"].execute(run_id))
    env["executor"].approve_step(
        run_id, "estimate", approved_by="owner", note="verified quote")
    after_estimate = asyncio.run(env["executor"].execute(run_id))["assignment"]
    estimate_step = next(step for step in after_estimate["steps"]
                         if step["step_id"] == "estimate")
    assert estimate_step["status"] == "applied", estimate_step
    assert calls["create"] == 1
    assert calls["readback"] == 1

    env["executor"].approve_step(
        run_id, "email-draft", approved_by="owner", note="draft only")
    final = asyncio.run(env["executor"].execute(run_id))["assignment"]
    draft_step = next(step for step in final["steps"]
                      if step["step_id"] == "email-draft")
    assert draft_step["status"] == "applied", draft_step
    assert calls["create"] == 1
    assert calls["draft"] == 1
    assert outlook.sent is False


def test_unexpected_customer_prevents_quote_plan_even_with_line_items(tmp_path):
    from core.quote_evidence import (
        derive_quote_requirements,
        plan_quote_assignment,
        validate_quote_evidence,
    )

    requested = {"customer_id": "customer-1"}
    requirements = derive_quote_requirements(
        "Prepare a customer quote", requested=requested)
    receipts = [
        {"kind": "customer", "provider": "zoho_crm",
         "customer_id": "customer-OTHER", "resource_id": "customer-OTHER",
         "version": "v1", "retrieved_at": "2026-11-01T00:00:00Z",
         "access": "granted", "fields": {"name": "Other Customer"}},
        {"kind": "pricing_agreement", "provider": "zoho_workdrive",
         "customer_id": "customer-OTHER", "resource_id": "file-1",
         "version": "v1", "retrieved_at": "2026-11-01T00:00:00Z",
         "access": "granted", "price_basis": "customer_contract",
         "fields": {"currency": "USD", "effective_date": "2026-01-01",
                    "discount_policy": "5% B", "freight": "20.00",
                    "tax_treatment": "none", "delivery_terms": "FOB",
                    "validity": "30 days"}},
    ]
    validation = validate_quote_evidence(
        requirements, receipts, requested=requested)
    planned = plan_quote_assignment(
        objective="Prepare a customer quote",
        validation=validation,
        source={"kind": "text", "internal_fixture": True,
                "file_name": "preseeded.csv"},
        document_path=str(tmp_path / "should-not-exist.docx"),
        email_draft_path=None,
        email_to=["buyer@example.invalid"],
        subject="Customer quote",
        actions=[{
            "action": "connected.books.create_estimate",
            "arguments": {"organization_id": "org-1",
                          "estimate_data": {}, "authority_reference": "x",
                          "operation_id": "y"},
        }],
        employee_id="user-1", workspace_id="ws_assign",
        tenant_id="tenant_assign",
    )
    assert planned["status"] != "ready"
    assert planned["plan"] is None


def test_one_assignment_consumes_bytes_calculates_and_drafts(env, monkeypatch):
    from core import connected_actions as actions

    calls = {"create": 0, "readback": 0, "draft": 0}
    captured = {}

    class FakeWorkDrive:
        async def get_file_metadata(self, user_id, file_id, workspace_id=None):
            return {"id": file_id, "name": "price-list.csv", "version": "v1"}

        async def download_file(self, user_id, file_id, workspace_id=None):
            return _csv("50.00", discount_b="0")

        async def get_access_token(self, user_id, workspace_id=None):
            return "token"

    class FakeBooks:
        async def _get_active_token(self, *args, **kwargs):
            return "token"

        async def get_estimates_page(self, token, org, page=1, per_page=200):
            return [], {"has_more": False}

        async def create_estimate(self, token, org, data):
            calls["create"] += 1
            captured["estimate"] = data
            return {"estimate_id": "est-one-1"}

        async def get_estimate(self, token, org, estimate_id):
            calls["readback"] += 1
            data = captured["estimate"]
            return {
                "estimate_id": estimate_id,
                "estimate_number": "EST-ONE-1",
                "customer_id": data["customer_id"],
                "reference_number": data["reference_number"],
                "date": data["date"],
                "currency_code": data["currency_code"],
                "total": data["total"],
                "sub_total": data["sub_total"],
                "tax_total": data["tax_total"],
                "line_items": data["line_items"],
            }

    class FakeOutlook:
        def __init__(self):
            self.sent = False

        async def _get_access_token(self, user_id):
            return "token"

        async def create_draft_email(self, **kwargs):
            calls["draft"] += 1
            captured["draft"] = kwargs
            return {"id": "draft-one-1", "subject": kwargs["subject"]}

        async def send_email(self, *args, **kwargs):  # pragma: no cover
            self.sent = True
            raise AssertionError("draft must not send")

    async def fake_workdrive(ids):
        return FakeWorkDrive()

    async def fake_books(ids):
        return FakeBooks()

    outlook = FakeOutlook()
    monkeypatch.setattr(actions, "_workdrive_service", fake_workdrive)
    monkeypatch.setattr(actions, "_books_service", fake_books)
    monkeypatch.setattr(
        "integrations.outlook_service.OutlookService",
        lambda *a, **k: outlook)

    read = new_step(
        step_id="read",
        title="Read the returned price list bytes",
        operation_type="retrieve",
        adapter="action.registry",
        inputs={
            "action": "connected.workdrive.read_file",
            "arguments": {
                "file_id": "file-1", "evidence_kind": "price_rows",
                "customer_id": "customer-1",
                "price_basis": "customer_contract",
            },
        },
        effect="read_only",
    )
    map_rows = new_step(
        step_id="map",
        title="Map rows to quote lines",
        operation_type="calculate",
        adapter="quote.lines_from_rows",
        depends_on=["read"],
        inputs={
            "rows": {"$ref": "read.data.rows"},
            "columns": {
                "item_id": "sku", "quantity": "quantity",
                "unit": "unit", "pack_size": "pack",
                "unit_price": "unit_price", "currency": "currency",
                "description": "sku", "category": "category",
                "discount": "discount_percent",
            },
            "defaults": {"price_basis": "contract"},
            "discount_mode": "percent",
            "discount_authority": "price-list:v1",
            "source_identity": {
                "resource_id": {
                    "$ref": "read.data.read_receipt.resource_id"},
                "version": {
                    "$ref": "read.data.read_receipt.version"},
                "sha256": {
                    "$ref": "read.data.read_receipt.fields.sha256"},
            },
        },
        effect="local",
    )
    calculate = new_step(
        step_id="calculate",
        title="Calculate the quote",
        operation_type="calculate",
        adapter="quote.calculate",
        depends_on=["map"],
        inputs={
            "line_items": {"$ref": "map.line_items"},
            "currency": "USD",
            "freight": "20.00",
            "tax": {"basis": "none"},
            "discount_rules": [
                {"lesson_id": "general-b", "revision": 1,
                 "name": "general B discount",
                 "when": {"category": "B"}, "rate": "0.05"},
                {"lesson_id": "licensed-b", "revision": 1,
                 "name": "licensed B exception",
                 "when": {"category": "B",
                          "qualification": "licensed"},
                 "rate": "0.10"},
            ],
            "rounding": "half_up",
            "scale": 2,
            "rounding_authority": "agreement:round-half-up-2dp",
        },
        effect="local",
    )
    prepare_lines = new_step(
        step_id="prepare-lines",
        title="Prepare provider estimate lines",
        operation_type="calculate",
        adapter="quote.estimate_lines",
        depends_on=["calculate"],
        inputs={
            "rows": {"$ref": "calculate.rows"},
            "account_map": {"A": "acct-1", "B": "acct-1"},
        },
        effect="local",
    )
    estimate = new_step(
        step_id="estimate",
        title="Create the verified estimate",
        operation_type="outbound",
        adapter="action.registry",
        depends_on=["prepare-lines"],
        inputs={
            "action": "connected.books.create_estimate",
            "arguments": {
                "organization_id": "org-1",
                "estimate_data": {
                    "customer_id": "customer-1",
                    "reference_number": "RFQ-ONE-1",
                    "date": "2026-11-01",
                    "currency_code": "USD",
                    "total": "${calculate.value}",
                    "sub_total": "${calculate.value}",
                    "tax_total": "0.00",
                    "line_items": {"$ref": "prepare-lines.line_items"},
                },
                "authority_reference": "grant-one-1",
                "operation_id": "op-one-1",
            },
        },
        effect="external",
        approval_required=True,
        approval_purpose="Create the estimate",
    )
    draft = new_step(
        step_id="email-draft",
        title="Create the Outlook draft from the verified quote",
        operation_type="outbound",
        adapter="action.registry",
        depends_on=["estimate"],
        inputs={
            "action": "connected.outlook.create_draft",
            "arguments": {
                "to": ["buyer@example.invalid"],
                "subject": "Quote RFQ-ONE-1",
                "body": "Quoted total: ${calculate.value} USD",
                "operation_id": "op-one-draft-1",
            },
        },
        effect="external",
        approval_required=True,
        approval_purpose="Create the Outlook draft",
    )
    plan = new_assignment(
        objective="Quote from returned bytes",
        steps=[read, map_rows, calculate, prepare_lines, estimate, draft],
        authorized_actions=["retrieve", "calculate", "outbound"],
        employee_id="user-1", workspace_id="ws_assign",
        tenant_id="tenant_assign",
        budget={"max_steps": 30, "max_attempts_per_step": 3,
                "max_wall_seconds": 600},
    )
    run_id = env["executor"].create_assignment(
        f"conv-{uuid.uuid4().hex[:8]}",
        "Quote from returned bytes", assignment=plan)["run_id"]

    started = asyncio.run(env["executor"].execute(run_id))["assignment"]
    assert started["status"] == "waiting"
    calc_step = next(step for step in started["steps"]
                     if step["step_id"] == "calculate")
    assert calc_step["status"] == "waiting"
    gap = next(
        item for item in env["lifecycle"].get_task(
            run_id)["task_revision"]["unresolved"]
        if item["status"] == "open")
    assert gap["concept"] == "discount_scope"
    binding = gap["inputs"]["quote_discount"]
    assert binding["missing_fields"] == ["qualification"]
    assert [rule["lesson_id"] for rule in binding["candidate_rules"]] == [
        "general-b", "licensed-b"]

    env["executor"].resolve_gap(
        run_id, gap["question_id"], resolution="unlicensed",
        resolved_by="pricing owner",
        evidence="accepted customer qualification: unlicensed")
    started = asyncio.run(env["executor"].execute(run_id))["assignment"]
    calc_step = next(step for step in started["steps"]
                     if step["step_id"] == "calculate")
    assert calc_step["status"] == "applied"
    assert calc_step["result_value"] == "362.50"
    calc_internal = next(
        step for step in env["lifecycle"].get_assignment(run_id)["steps"]
        if step["step_id"] == "calculate")
    assert calc_internal["result"]["rows"][0]["source_ref"]["version"] == "v1"
    assert calc_internal["result"]["rows"][0]["source_ref"]["sha256"]
    estimate_step = next(step for step in started["steps"]
                         if step["step_id"] == "estimate")
    assert estimate_step["status"] == "awaiting_approval"
    assert calls["create"] == 0

    env["executor"].approve_step(
        run_id, "estimate", approved_by="owner", note="verified quote")
    after_estimate = asyncio.run(env["executor"].execute(run_id))["assignment"]
    estimate_step = next(step for step in after_estimate["steps"]
                         if step["step_id"] == "estimate")
    assert estimate_step["status"] == "applied", estimate_step
    assert calls["create"] == 1
    assert calls["readback"] == 1

    env["executor"].approve_step(
        run_id, "email-draft", approved_by="owner", note="draft only")
    final = asyncio.run(env["executor"].execute(run_id))["assignment"]
    draft_step = next(step for step in final["steps"]
                      if step["step_id"] == "email-draft")
    assert draft_step["status"] == "applied", draft_step
    assert calls["create"] == 1
    assert calls["draft"] == 1
    assert "362.50" in captured["draft"]["body"]
    assert outlook.sent is False


@pytest.mark.parametrize("row_count", [79, 80, 81])
def test_registered_workdrive_read_preserves_every_executable_row(
        env, monkeypatch, row_count):
    """Actual WorkDrive action -> executor -> quote calculation."""
    import base64
    import csv
    import io

    from core.assignment_plan import new_teaching_snapshot

    rows = [{
        "item_id": f"SKU-{index:03d}",
        "description": "café item" if index == 0 else "item",
        "quantity": "1", "unit": "each", "pack_size": "1",
        "unit_price": "1.00", "price_basis": "contract",
        "currency": "USD",
    } for index in range(row_count)]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    content = buffer.getvalue().encode("utf-8")
    assert len(content) > 2000

    from core import connected_actions as actions

    class FakeWorkDrive:
        async def get_file_metadata(self, user_id, file_id, workspace_id=None):
            return {"id": file_id, "name": "price-list.csv",
                    "version": "v1", "size": len(content)}

        async def download_file(self, user_id, file_id, workspace_id=None):
            return content

        async def get_access_token(self, user_id, workspace_id=None):
            return "token"

    async def fake_service(ids):
        return FakeWorkDrive()

    monkeypatch.setattr(actions, "_workdrive_service", fake_service)
    plan = new_assignment(
        objective="Quote from the complete returned price list",
        employee_id="user-1", workspace_id="ws_assign",
        tenant_id="tenant_assign",
        teaching_snapshot=new_teaching_snapshot(revision="quote-r1"),
        sources=[{"kind": "document",
                  "binding": {"resource_id": "price-list-v1"}}],
        authorized_actions=["retrieve", "calculate"],
        steps=[
            new_step(
                step_id="read", title="Read the full price list",
                operation_type="retrieve", adapter="action.registry",
                effect="read_only",
                inputs={"action": "connected.workdrive.read_file",
                        "arguments": {"file_id": "file-1",
                                      "evidence_kind": "price_rows"}}),
            new_step(
                step_id="calculate", title="Calculate every returned row",
                operation_type="calculate", adapter="quote.calculate",
                effect="local", depends_on=["read"],
                inputs={
                    "line_items": {"$ref": "read.data.rows"},
                    "currency": "USD", "freight": "0",
                    "tax": {"basis": "none"}, "discount_rules": [],
                }),
        ])
    run_id = env["executor"].create_assignment(
        "conv-data-transfer", plan["objective"], assignment=plan)["run_id"]
    result = asyncio.run(env["executor"].execute(run_id))
    assert result["assignment"]["status"] == "completed", result
    assignment = env["lifecycle"].get_assignment(run_id)
    read = next(step for step in assignment["steps"]
                if step["step_id"] == "read")
    returned = read["result"]["data"]
    assert len(returned["rows"]) == row_count
    assert returned["rows"][0]["description"] == "café item"
    assert returned["content_b64"] == base64.b64encode(content).decode("ascii")
    assert returned["read_receipt"]["coverage"] == "complete"
    assert returned["read_receipt"]["fields"]["truncated"] is False
    assert not returned["read_receipt"].get("truncated")
    calc = next(step for step in assignment["steps"]
                if step["step_id"] == "calculate")
    assert calc["result"]["value"] == f"{row_count}.00"
    assert len(calc["result"]["rows"]) == row_count

    restarted = AssignmentExecutor(
        env["lifecycle"], adapters=env["registry"])
    persisted = restarted.status(run_id)["assignment"]
    assert persisted["status"] == "completed"


def test_truncated_read_blocks_full_population_calculation(env, monkeypatch):
    """A bounded 500-row read of a 501-row file must not calculate silently."""
    import csv
    import io

    from core.assignment_plan import new_teaching_snapshot
    from core import connected_actions as actions

    rows = [{
        "item_id": f"SKU-{index:03d}", "quantity": "1", "unit": "each",
        "pack_size": "1", "unit_price": "1.00", "price_basis": "contract",
        "currency": "USD",
    } for index in range(501)]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    content = buffer.getvalue().encode()

    class FakeWorkDrive:
        async def get_file_metadata(self, user_id, file_id, workspace_id=None):
            return {"id": file_id, "name": "price-list.csv", "version": "v1"}

        async def download_file(self, user_id, file_id, workspace_id=None):
            return content

        async def get_access_token(self, user_id, workspace_id=None):
            return "token"

    async def fake_service(ids):
        return FakeWorkDrive()

    monkeypatch.setattr(actions, "_workdrive_service", fake_service)
    plan = new_assignment(
        objective="Quote from a bounded read",
        employee_id="user-1", workspace_id="ws_assign",
        tenant_id="tenant_assign",
        teaching_snapshot=new_teaching_snapshot(revision="quote-r1"),
        sources=[{"kind": "document",
                  "binding": {"resource_id": "price-list-v1"}}],
        authorized_actions=["retrieve", "calculate"],
        steps=[
            new_step(
                step_id="read", title="Read a bounded page",
                operation_type="retrieve", adapter="action.registry",
                effect="read_only",
                inputs={"action": "connected.workdrive.read_file",
                        "arguments": {"file_id": "file-1",
                                      "evidence_kind": "price_rows"}}),
            new_step(
                step_id="calculate", title="Calculate all rows",
                operation_type="calculate", adapter="quote.calculate",
                effect="local", depends_on=["read"],
                inputs={"line_items": {"$ref": "read.data.rows"},
                        "currency": "USD", "freight": "0",
                        "tax": {"basis": "none"}, "discount_rules": []}),
        ])
    run_id = env["executor"].create_assignment(
        "conv-truncated", plan["objective"], assignment=plan)["run_id"]
    result = asyncio.run(env["executor"].execute(run_id))
    assert result["assignment"]["status"] != "completed", result
    assignment = env["lifecycle"].get_assignment(run_id)
    read = next(step for step in assignment["steps"]
                if step["step_id"] == "read")
    assert read["status"] == "failed"
    assert "partial coverage" in str(read.get("failure") or "").lower()
    calc = next(step for step in assignment["steps"]
                if step["step_id"] == "calculate")
    assert calc["status"] == "pending"
    assert calc.get("result") is None


def test_oversized_inline_content_refuses_without_downstream_work(
        env, monkeypatch):
    from core.assignment_plan import new_teaching_snapshot
    from core import connected_actions as actions

    content = b"a" * 2_100_000

    class FakeWorkDrive:
        async def get_file_metadata(self, user_id, file_id, workspace_id=None):
            return {"id": file_id, "name": "large.txt", "version": "v1"}

        async def download_file(self, user_id, file_id, workspace_id=None):
            return content

        async def get_access_token(self, user_id, workspace_id=None):
            return "token"

    async def fake_service(ids):
        return FakeWorkDrive()

    monkeypatch.setattr(actions, "_workdrive_service", fake_service)
    plan = new_assignment(
        objective="Read an oversized source",
        employee_id="user-1", workspace_id="ws_assign",
        tenant_id="tenant_assign",
        teaching_snapshot=new_teaching_snapshot(revision="quote-r1"),
        sources=[{"kind": "document",
                  "binding": {"resource_id": "large-source"}}],
        authorized_actions=["retrieve"],
        steps=[new_step(
            step_id="read", title="Read the oversized source",
            operation_type="retrieve", adapter="action.registry",
            effect="read_only",
            inputs={"action": "connected.workdrive.read_file",
                    "arguments": {"file_id": "file-1"}})])
    run_id = env["executor"].create_assignment(
        "conv-oversized", plan["objective"], assignment=plan)["run_id"]
    result = asyncio.run(env["executor"].execute(run_id))
    assert result["assignment"]["status"] != "completed", result
    assignment = env["lifecycle"].get_assignment(run_id)
    read = next(step for step in assignment["steps"]
                if step["step_id"] == "read")
    assert read["status"] == "failed"
    message = str(read.get("failure") or "").lower()
    assert "limit" in message or "oversized" in message or "payload" in message
