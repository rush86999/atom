"""Deterministic two-domain adaptive employee campaign (G5 level 1).

This module exercises the same production assignment lifecycle, readiness,
plan-patch, observation, wait, recovery and outcome paths with two materially
different business vocabularies:

* an industrial quote employee reacting to eligibility, changed quantities,
  a governing price revision, an infeasible lead time and an approved
  equivalent; and
* a procurement/bookkeeping employee reconciling a supplier invoice against
  purchase/receiving records, waiting for a corrected invoice, and preparing
  one supported bill.

It is deliberately a *mechanism* campaign. The served-model adaptive-choice
campaign (G5 level 2) is not run here and is not claimed.
"""
from __future__ import annotations

import asyncio
import copy
from collections import defaultdict
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.assignment_executor import (
    AssignmentExecutor,
    WaitingForExternal,
    default_adapter_registry,
)
import core.assignment_quote  # noqa: F401,E402  (registers quote.calculate)
from core.assignment_plan import (
    new_assignment,
    new_deliverable,
    new_step,
    new_teaching_snapshot,
    step_by_id,
)
from core.employee_adaptation import (
    adopt_adaptation,
    deterministic_adaptation,
)
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.models import GoalObjective, GoalRun, TaskOperationRecord
from core.task_lifecycle import TaskLifecycle


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    engine = create_engine(f"sqlite:///{tmp_path}/campaign.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  TaskOperationRecord.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    runs = GoalRunService(
        workspace_id="ws_campaign", tenant_id="tenant_campaign",
        session_factory=factory)
    goals = GoalService(
        workspace_id="ws_campaign", tenant_id="tenant_campaign",
        session_factory=factory)
    lifecycle = TaskLifecycle(runs, goals)
    registry = default_adapter_registry.clone()
    return {
        "tmp": tmp_path,
        "lifecycle": lifecycle,
        "executor": AssignmentExecutor(lifecycle, adapters=registry),
        "registry": registry,
    }


def _run(coro):
    return asyncio.run(coro)


def _teaching(revision="campaign-teach-1"):
    return new_teaching_snapshot(
        revision=revision,
        matched_context={"business_category": "campaign"},
        output_requirements={
            "font_name": "Arial", "font_size": 11,
            "heading_order": ["Summary", "Sources"],
        },
    )


def _create(env, *, objective, steps, criteria, actions):
    plan = new_assignment(
        objective=objective, employee_id="employee-1",
        workspace_id="ws_campaign", tenant_id="tenant_campaign",
        teaching_snapshot=_teaching(),
        sources=[
            {"resource_id": "agreement-1", "kind": "document"},
            {"resource_id": "supplier-a", "kind": "dataset"},
            {"resource_id": "supplier-b", "kind": "dataset"},
            {"resource_id": "equivalence-1", "kind": "document"},
        ],
        steps=steps, authorized_actions=actions,
        completion_criteria=criteria,
        budget={"max_steps": 60, "max_attempts_per_step": 3,
                "max_wall_seconds": 900})
    record = env["executor"].create_assignment(
        f"conv-campaign-{objective[:12]}", objective, assignment=plan)
    return record["run_id"]


def _decimal_money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _quote_total(*, a_qty, a_price, b_qty, b_price, b_rate, freight):
    """Independent arithmetic; never imports the production calculator."""
    a = Decimal(str(a_qty)) * Decimal(str(a_price))
    b = Decimal(str(b_qty)) * Decimal(str(b_price))
    b_net = b * (Decimal("1") - Decimal(str(b_rate)))
    return (a + b_net + Decimal(str(freight))).quantize(Decimal("0.01"))


# --------------------------------------------------------------- domain A


def _quote_campaign(env, *, delivery_limit=10):
    state = {
        "a": {"qty": 2, "price": "100.00", "lead": 12, "version": "a-v1"},
        "b": {"qty": 3, "price": "50.00", "version": "b-v1"},
        "equivalence": {
            "approved": True, "unit_price": "106.00", "lead_days": 7,
            "currency": "USD", "resource_id": "equivalence-1",
            "version": "eq-v1",
        },
    }
    calls = defaultdict(int)

    def line_item(row, item_id, *, discount=False):
        item = {
            "item_id": item_id,
            "quantity": str(row["qty"]),
            "unit": "each",
            "pack_size": "1",
            "unit_price": row["price"],
            "price_basis": "contract",
            "currency": "USD",
            "category": item_id,
            "source_ref": {
                "resource_id": f"supplier-{item_id.lower()}",
                "source_version": row["version"],
            },
        }
        if discount:
            item["discount_rate"] = "0.05"
            item["discount_authority"] = "customer agreement v3"
        return item

    async def read_a(inputs, context):
        calls["read-a"] += 1
        row = state["a"]
        return {
            "status": "applied",
            "summary": "read primary A",
            "source_version": row["version"],
            "data": {
                "line_item": line_item(row, "A"),
                "lead_days": row["lead"],
                "source_version": row["version"],
            },
            "verification": {
                "status": "verified", "resource_id": "supplier-a",
                "version": row["version"],
            },
        }

    async def read_b(inputs, context):
        calls["read-b"] += 1
        row = state["b"]
        return {
            "status": "applied",
            "summary": "read B",
            "source_version": row["version"],
            "data": {"line_item": line_item(row, "B", discount=True)},
            "verification": {
                "status": "verified", "resource_id": "supplier-b",
                "version": row["version"],
            },
        }

    async def read_equivalence(inputs, context):
        calls["read-equivalence"] += 1
        record = dict(state["equivalence"])
        return {
            "status": "applied",
            "summary": "read approved equivalence",
            "data": {"record": record},
            "verification": {
                "status": "verified", "resource_id": record["resource_id"],
                "version": record["version"],
            },
        }

    async def select_a(inputs, context):
        calls["select-a"] += 1
        equivalence = inputs.get("equivalence")
        if (isinstance(equivalence, dict)
                and equivalence.get("approved") is True
                and int(equivalence.get("lead_days") or 99) <= 10):
            return {
                "status": "applied",
                "summary": "selected approved equivalent A-alt",
                "source_version": equivalence["version"],
                "data": {
                    "line_item": {
                        "item_id": "A-alt",
                        "quantity": str(state["a"]["qty"]),
                        "unit": "each",
                        "pack_size": "1",
                        "unit_price": equivalence["unit_price"],
                        "price_basis": "contract",
                        "currency": equivalence["currency"],
                        "category": "A",
                        "source_ref": {
                            "resource_id": equivalence["resource_id"],
                            "source_version": equivalence["version"],
                        },
                    },
                    "lead_days": equivalence["lead_days"],
                    "selected": "equivalent",
                },
            }
        return {
            "status": "applied",
            "summary": "selected primary A",
            "source_version": state["a"]["version"],
            "data": {
                "line_item": inputs.get("primary"),
                "lead_days": inputs.get("primary_lead"),
                "selected": "primary",
            },
        }

    async def verify_delivery(inputs, context):
        calls["verify-delivery"] += 1
        lead = int(inputs.get("lead_days") or 0)
        limit = int(inputs.get("limit") or 0)
        if lead > limit:
            return {
                "status": "failed",
                "message": (
                    f"selected delivery is {lead} days; the customer allows "
                    f"at most {limit}."),
            }
        return {
            "status": "applied",
            "summary": f"delivery {lead} days is within the {limit}-day limit",
        }

    for name, handler in (
            ("test.quote.read_a", read_a),
            ("test.quote.read_b", read_b),
            ("test.quote.read_equivalence", read_equivalence),
            ("test.quote.select_a", select_a),
            ("test.quote.verify_delivery", verify_delivery)):
        env["registry"].register(name, handler)
        default_adapter_registry.register(name, handler)

    document_path = env["tmp"] / "industrial-quote.docx"
    steps = [
        new_step(
            step_id="read-a", title="Read primary A price",
            operation_type="retrieve", adapter="test.quote.read_a",
            effect="read_only"),
        new_step(
            step_id="read-b", title="Read B price",
            operation_type="retrieve", adapter="test.quote.read_b",
            effect="read_only"),
        new_step(
            step_id="select-a", title="Select the A source",
            operation_type="calculate", adapter="test.quote.select_a",
            depends_on=["read-a"], effect="local",
            inputs={
                "primary": {"$ref": "read-a.data.line_item"},
                "primary_lead": {"$ref": "read-a.data.lead_days"},
                "equivalence": {"$ref": "read-equivalence.data.record"},
            }),
        new_step(
            step_id="verify-delivery", title="Verify the delivery promise",
            operation_type="calculate",
            adapter="test.quote.verify_delivery",
            depends_on=["select-a"], effect="local",
            inputs={"lead_days": {"$ref": "select-a.data.lead_days"},
                    "limit": delivery_limit}),
        new_step(
            step_id="calculate", title="Calculate the quote",
            operation_type="calculate", adapter="quote.calculate",
            depends_on=["select-a", "read-b"], effect="local",
            requires=[{"kind": "fact", "fact_id": "b_discount_eligible",
                       "equals": True}],
            inputs={
                "line_items": [
                    {"$ref": "select-a.data.line_item"},
                    {"$ref": "read-b.data.line_item"},
                ],
                "currency": "USD", "freight": "20.00",
                "tax": {"basis": "none"},
                "rounding": "half_up", "scale": 2,
                "rounding_authority": "customer agreement v3",
                "as_of": "2026-11-02",
            }),
        new_step(
            step_id="document", title="Render the quote",
            operation_type="present", adapter="artifact.document",
            depends_on=["calculate", "verify-delivery"], effect="local",
            inputs={
                "path": str(document_path),
                "title": "Industrial quote",
                "content": (
                    "# Quote\n\n"
                    "Total: ${calculate.value} ${calculate.unit}\n"
                    "Delivery: ${select-a.data.lead_days} days\n"
                    "A source: ${select-a.data.selected}\n"
                    "Sources: agreement-1, supplier-a, supplier-b, "
                    "equivalence-1\n"),
            }),
        new_step(
            step_id="draft", title="Prepare the customer reply draft",
            operation_type="present", adapter="email.draft",
            depends_on=["calculate", "document"], effect="local",
            inputs={
                "to": ["customer@example.invalid"],
                "subject": "Your industrial quote",
                "body": (
                    "The quoted total is ${calculate.value} "
                    "${calculate.unit} with delivery in "
                    "${select-a.data.lead_days} days."),
            }),
    ]
    criteria = [
        {"kind": "required_work_complete"},
        {"kind": "draft_saved"},
        {"kind": "artifact_verified"},
    ]
    run_id = _create(
        env, objective=(
            "Prepare an accurate, cited industrial quote within the "
            "customer's 10-day delivery requirement and 500 USD budget"),
        steps=steps, criteria=criteria,
        actions=["retrieve", "calculate", "present", "edit"])
    return run_id, state, calls, document_path


def test_industrial_quote_campaign_adapts_and_finishes_feasible_quote(env):
    run_id, state, calls, document_path = _quote_campaign(env)
    executor = env["executor"]

    started = _run(executor.execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    assert started["assignment"]["status"] in ("partial", "blocked"), started
    assert step_by_id(assignment, "read-a")["status"] == "applied"
    assert step_by_id(assignment, "read-b")["status"] == "applied"
    assert step_by_id(assignment, "select-a")["status"] == "applied"
    assert step_by_id(assignment, "verify-delivery")["status"] == "failed"
    calculate = step_by_id(assignment, "calculate")
    assert calculate["status"] == "pending"
    assert calculate["readiness"]["truth"] == "unknown"
    assert calculate["readiness"]["blockers"][0]["fact_id"] == (
        "b_discount_eligible")
    assert step_by_id(assignment, "document")["status"] == "pending"

    # Eligibility evidence arrives; only the dependent closure reopens.
    eligibility = deterministic_adaptation({
        "observation_id": "elig-1",
        "kind": "qualification",
        "fact_id": "b_discount_eligible",
        "value": True,
        "evidence_state": "established",
        "subject_id": "customer-1",
        "source_refs": [{"resource_id": "agreement-1", "version": "v3"}],
        "reason": "the customer agreement establishes B eligibility",
    }, assignment)
    assert eligibility["decision"] == "invalidate"
    adopted = adopt_adaptation(env["lifecycle"], run_id, eligibility)
    assert adopted["status"] == "applied"
    _run(executor.execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    assert step_by_id(assignment, "calculate")["status"] == "applied"
    assert _decimal_money(
        step_by_id(assignment, "calculate")["result"]["value"]) == (
            _quote_total(a_qty=2, a_price="100.00", b_qty=3,
                         b_price="50.00", b_rate="0.05",
                         freight="20.00"))
    assert _decimal_money(
        step_by_id(assignment, "calculate")["result"]["value"]) == Decimal(
            "362.50")
    assert step_by_id(assignment, "document")["status"] == "pending"

    # The governing B price changes; the independent delivery check and the
    # prior A chain are not part of the affected closure.
    state["b"]["price"] = "55.00"
    state["b"]["version"] = "b-v2"
    price_observation = deterministic_adaptation({
        "observation_id": "b-price-2",
        "kind": "source_version",
        "step_id": "read-b",
        "reason": "the governing B price list moved to v2",
    }, assignment)
    assert price_observation["decision"] == "invalidate"
    assert set(price_observation["step_ids"]) == {
        "read-b", "calculate", "document", "draft"}
    assert adopt_adaptation(
        env["lifecycle"], run_id, price_observation)["status"] == "applied"
    _run(executor.execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    assert _decimal_money(
        step_by_id(assignment, "calculate")["result"]["value"]) == (
            _quote_total(a_qty=2, a_price="100.00", b_qty=3,
                         b_price="55.00", b_rate="0.05",
                         freight="20.00"))
    assert _decimal_money(
        step_by_id(assignment, "calculate")["result"]["value"]) == Decimal(
            "376.75")
    assert step_by_id(assignment, "verify-delivery")["status"] == "failed"
    read_b_before = copy.deepcopy(step_by_id(assignment, "read-b"))

    # The customer changes the A quantity; only the A branch and its
    # descendants reopen, and the B receipt keeps its operation identity.
    state["a"]["qty"] = 3
    state["a"]["version"] = "a-v2"
    quantity_observation = deterministic_adaptation({
        "observation_id": "a-qty-3",
        "kind": "quantity",
        "step_id": "read-a",
        "reason": "the customer changed A quantity from 2 to 3",
    }, assignment)
    assert quantity_observation["decision"] == "invalidate"
    assert adopt_adaptation(
        env["lifecycle"], run_id, quantity_observation)["status"] == "applied"
    _run(executor.execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    assert _decimal_money(
        step_by_id(assignment, "calculate")["result"]["value"]) == (
            _quote_total(a_qty=3, a_price="100.00", b_qty=3,
                         b_price="55.00", b_rate="0.05",
                         freight="20.00"))
    assert _decimal_money(
        step_by_id(assignment, "calculate")["result"]["value"]) == Decimal(
            "476.75")
    read_b_after_a = step_by_id(assignment, "read-b")
    assert read_b_after_a["operation_id"] == read_b_before["operation_id"]
    assert read_b_after_a["result"] == read_b_before["result"]
    assert step_by_id(assignment, "verify-delivery")["status"] == "failed"

    # The primary lead time is infeasible. The employee adopts the approved
    # equivalence record, rewires selection to wait for it, and retries the
    # affected delivery/quote/document chain.
    replan = {
        "decision": "replan",
        "reason": (
            "primary A delivery is 12 days; the approved equivalence record "
            "provides A-alt at 106.00 with 7-day delivery"),
        "observation_ids": ["delivery-1"],
        "step_ids": ["select-a"],
        "new_steps": [{
            "step_id": "read-equivalence",
            "title": "Read the approved equivalence record",
            "operation_type": "retrieve",
            "adapter": "test.quote.read_equivalence",
            "effect": "read_only",
        }],
        "update_steps": [{
            "step_id": "select-a",
            "depends_on": ["read-a", "read-equivalence"],
        }],
    }
    adopted = adopt_adaptation(env["lifecycle"], run_id, replan)
    assert adopted["status"] == "applied"
    assert adopted["updated_steps"] == ["select-a"]
    assert step_by_id(
        adopted["assignment"], "read-equivalence") is not None
    completed = _run(executor.execute(run_id))
    assert completed["assignment"]["status"] == "completed", completed
    assignment = env["lifecycle"].get_assignment(run_id)
    assert step_by_id(assignment, "select-a")["result"]["data"][
        "selected"] == "equivalent"
    assert step_by_id(assignment, "verify-delivery")["status"] == "applied"
    total = step_by_id(assignment, "calculate")["result"]["value"]
    assert _decimal_money(total) == _quote_total(
        a_qty=3, a_price="106.00", b_qty=3, b_price="55.00",
        b_rate="0.05", freight="20.00")
    assert _decimal_money(total) == Decimal("494.75")
    assert Decimal(total) <= Decimal("500.00")
    assert document_path.exists()
    document_text = "\n".join(
        paragraph.text for paragraph in
        __import__("docx").Document(str(document_path)).paragraphs)
    assert "494.75" in document_text
    assert "7 days" in document_text
    draft = step_by_id(assignment, "draft")
    assert draft["status"] == "applied"
    assert "494.75" in str(draft["result"].get("draft") or "")
    assert draft["result"]["draft"]["send_performed"] is False
    assert assignment["outcome_summary"]["objective_met"] is True

    # A replayed delivery observation does not reopen the completed job.
    revision = assignment["plan_revision"]
    replay = adopt_adaptation(env["lifecycle"], run_id, replan)
    assert replay["status"] == "already_applied", replay
    final = env["lifecycle"].get_assignment(run_id)
    assert final["plan_revision"] == revision
    assert step_by_id(final, "calculate")["status"] == "applied"


# --------------------------------------------------------------- domain B


def _procurement_campaign(env):
    state = {"invoice_version": "v1", "bill_calls": 0,
             "period_open": True}
    calls = defaultdict(int)

    async def read_po(inputs, context):
        calls["read-po"] += 1
        return {
            "status": "applied",
            "summary": "read purchase order",
            "data": {"po": {
                "po_id": "PO-1", "vendor_id": "V-9",
                "vendor_name": "Acme Supply",
                "quantity": "3", "unit_price": "120.00",
                "freight": "30.00", "currency": "USD",
                "resource_id": "po-1", "version": "po-v1",
            }},
            "verification": {"status": "verified",
                             "resource_id": "po-1",
                             "version": "po-v1"},
        }

    async def read_invoice(inputs, context):
        calls["read-invoice"] += 1
        if state["invoice_version"] == "v2":
            payload = {
                "invoice_id": "INV-1", "version": "inv-v2",
                "quantity": "2", "unit_price": "120.00",
                "freight": "30.00", "currency": "USD",
                "resource_id": "invoice-1",
            }
        else:
            payload = {
                "invoice_id": "INV-1", "version": "inv-v1",
                "quantity": "3", "unit_price": "120.00",
                "freight": "30.00", "currency": "USD",
                "resource_id": "invoice-1",
            }
        return {
            "status": "applied", "summary": "read supplier invoice",
            "data": {"invoice": payload},
            "verification": {"status": "verified",
                             "resource_id": "invoice-1",
                             "version": payload["version"]},
        }

    async def read_receiving(inputs, context):
        calls["read-receiving"] += 1
        return {
            "status": "applied", "summary": "read receiving record",
            "data": {"receiving": {
                "po_id": "PO-1", "received_quantity": "2",
                "resource_id": "receiving-1", "version": "rec-v1",
            }},
            "verification": {"status": "verified",
                             "resource_id": "receiving-1",
                             "version": "rec-v1"},
        }

    async def lookup_vendor(inputs, context):
        calls["lookup-vendor"] += 1
        return {
            "status": "applied", "summary": "resolved vendor by stable id",
            "data": {"vendor": {
                "vendor_id": "V-9", "name": "Acme Supply",
                "same_name_candidates": ["V-8"]}},
            "verification": {"status": "verified",
                             "resource_id": "vendor-V-9",
                             "version": "vendor-v1"},
        }

    async def check_coa(inputs, context):
        calls["check-coa"] += 1
        return {"status": "applied", "summary": "CoA account current",
                "data": {"coa": {"account": "5100", "available": True}},
                "verification": {"status": "verified",
                                 "resource_id": "coa-1",
                                 "version": "coa-v1"}}

    async def check_period(inputs, context):
        calls["check-period"] += 1
        return {"status": "applied",
                "summary": (
                    "period open" if state["period_open"]
                    else "period closed"),
                "data": {"period": {
                    "period": "2026-11", "open": state["period_open"]}},
                "verification": {"status": "verified",
                                 "resource_id": "period-1",
                                 "version": "period-v1"}}

    async def reconcile(inputs, context):
        calls["reconcile"] += 1
        invoice = inputs.get("invoice") or {}
        receiving = inputs.get("receiving") or {}
        if str(invoice.get("quantity")) != str(
                receiving.get("received_quantity")):
            if state["invoice_version"] != "v2":
                raise WaitingForExternal({
                    "event": "email",
                    "state": "waiting_for_external",
                    "party": "supplier",
                    "correlation_id": "corr-invoice-v2",
                    "resume_on": "response",
                    "detail": (
                        "invoice quantity 3 differs from received quantity 2; "
                        "request the authoritative corrected invoice"),
                })
        quantity = Decimal(str(invoice.get("quantity")))
        unit_price = Decimal(str(invoice.get("unit_price")))
        freight = Decimal(str(invoice.get("freight")))
        total = (quantity * unit_price + freight).quantize(Decimal("0.01"))
        return {
            "status": "applied",
            "summary": "invoice matches received quantities",
            "data": {
                "total": str(total),
                "currency": invoice.get("currency"),
                "quantity": str(quantity),
                "invoice_version": invoice.get("version"),
                "receiving_version": receiving.get("version"),
            },
            "verification": {
                "status": "verified",
                "resource_id": invoice.get("resource_id"),
                "version": invoice.get("version"),
            },
        }

    async def create_bill(inputs, context):
        period = inputs.get("period") or {}
        if period.get("open") is not True:
            return {
                "status": "failed",
                "message": (
                    "the accounting period is closed; no bill was created"),
            }
        calls["create-bill"] += 1
        state["bill_calls"] += 1
        return {
            "status": "applied",
            "summary": "created one reviewed bill",
            "remote_id": "bill-1",
            "provider_ref": "bill-1",
            "provider_state": "accepted",
            "provider_receipt": {
                "operation_id": "provider-bill-1",
                "remote_id": "bill-1",
            },
            "data": {"bill_id": "bill-1",
                     "total": inputs.get("total")},
            "verification": {"status": "verified",
                             "resource_id": "bill-1",
                             "version": "bill-v1"},
        }

    for name, handler in (
            ("test.bookkeeping.read_po", read_po),
            ("test.bookkeeping.read_invoice", read_invoice),
            ("test.bookkeeping.read_receiving", read_receiving),
            ("test.bookkeeping.lookup_vendor", lookup_vendor),
            ("test.bookkeeping.check_coa", check_coa),
            ("test.bookkeeping.check_period", check_period),
            ("test.bookkeeping.reconcile", reconcile),
            ("test.bookkeeping.create_bill", create_bill)):
        env["registry"].register(name, handler)
        default_adapter_registry.register(name, handler)

    steps = [
        new_step(
            step_id="read-po", title="Read the purchase order",
            operation_type="retrieve", adapter="test.bookkeeping.read_po",
            effect="read_only"),
        new_step(
            step_id="read-invoice", title="Read the supplier invoice",
            operation_type="retrieve",
            adapter="test.bookkeeping.read_invoice", effect="read_only"),
        new_step(
            step_id="read-receiving", title="Read receiving records",
            operation_type="retrieve",
            adapter="test.bookkeeping.read_receiving", effect="read_only"),
        new_step(
            step_id="lookup-vendor", title="Resolve the PO vendor",
            operation_type="retrieve",
            adapter="test.bookkeeping.lookup_vendor", effect="read_only"),
        new_step(
            step_id="check-coa", title="Check the chart of accounts",
            operation_type="retrieve",
            adapter="test.bookkeeping.check_coa", effect="read_only"),
        new_step(
            step_id="check-period", title="Check the open period",
            operation_type="retrieve",
            adapter="test.bookkeeping.check_period", effect="read_only"),
        new_step(
            step_id="reconcile", title="Reconcile invoice to receiving",
            operation_type="calculate",
            adapter="test.bookkeeping.reconcile",
            depends_on=["read-po", "read-invoice", "read-receiving"],
            effect="local",
            inputs={
                "po": {"$ref": "read-po.data.po"},
                "invoice": {"$ref": "read-invoice.data.invoice"},
                "receiving": {"$ref": "read-receiving.data.receiving"},
            }),
        new_step(
            step_id="create-bill", title="Prepare the supported reviewed bill",
            operation_type="outbound",
            adapter="test.bookkeeping.create_bill",
            depends_on=["reconcile", "lookup-vendor", "check-coa",
                        "check-period"],
            effect="external", approval_required=True,
            approval_purpose="Create one bill for the corrected invoice",
            inputs={"total": {"$ref": "reconcile.data.total"},
                    "currency": {"$ref": "reconcile.data.currency"},
                    "period": {"$ref": "check-period.data.period"}}),
    ]
    criteria = [
        {"kind": "required_work_complete"},
        {"kind": "provider_accepted"},
    ]
    run_id = _create(
        env, objective=(
            "Reconcile the supplier invoice against the approved purchase "
            "order and receiving records and prepare only the supported bill"),
        steps=steps, criteria=criteria,
        actions=["retrieve", "calculate", "outbound"])
    return run_id, state, calls


def test_procurement_campaign_waits_corrects_and_posts_supported_bill(env):
    run_id, state, calls = _procurement_campaign(env)
    executor = env["executor"]

    first = _run(executor.execute(run_id))
    assert first["assignment"]["status"] == "waiting", first
    assignment = env["lifecycle"].get_assignment(run_id)
    assert step_by_id(assignment, "reconcile")["status"] == "waiting"
    for independent in ("lookup-vendor", "check-coa", "check-period"):
        assert step_by_id(assignment, independent)["status"] == "applied"
    assert step_by_id(assignment, "create-bill")["status"] == "pending"

    # Restart while the supplier obligation is open: same durable wait.
    restarted = AssignmentExecutor(env["lifecycle"], adapters=env["registry"])
    again = _run(restarted.execute(run_id))
    assert again["assignment"]["status"] == "waiting"
    assert step_by_id(
        env["lifecycle"].get_assignment(run_id), "reconcile")["status"] == (
            "waiting")

    # An old/out-of-order correlation cannot close the current obligation.
    old = restarted.record_external_response(
        run_id, "corr-old-invoice", response="old invoice reply")
    assert old["status"] == "unmatched"
    assert step_by_id(
        env["lifecycle"].get_assignment(run_id), "reconcile")["status"] == (
            "waiting")

    # The authoritative corrected invoice arrives.
    state["invoice_version"] = "v2"
    resumed = restarted.record_external_response(
        run_id, "corr-invoice-v2", response="corrected invoice v2")
    assert resumed["status"] == "resumed"
    assignment = env["lifecycle"].get_assignment(run_id)
    correction = deterministic_adaptation({
        "observation_id": "invoice-v2",
        "kind": "source_version",
        "step_id": "read-invoice",
        "reason": "the supplier issued a corrected invoice version",
    }, assignment)
    assert correction["decision"] == "invalidate"
    assert adopt_adaptation(
        env["lifecycle"], run_id, correction)["status"] == "applied"

    after_correction = _run(restarted.execute(run_id))
    assert after_correction["assignment"]["status"] == "waiting", (
        after_correction)
    assignment = env["lifecycle"].get_assignment(run_id)
    assert step_by_id(assignment, "read-invoice")["status"] == "applied"
    assert step_by_id(assignment, "read-invoice")["prior_results"]
    assert step_by_id(assignment, "reconcile")["status"] == "applied"
    assert _decimal_money(
        step_by_id(assignment, "reconcile")["result"]["data"]["total"]) == (
            Decimal("270.00"))
    create_bill = step_by_id(assignment, "create-bill")
    assert create_bill["status"] == "awaiting_approval"
    assert state["bill_calls"] == 0

    approved = restarted.approve_step(
        run_id, "create-bill", approved_by="bookkeeping owner")
    assert approved["status"] == "approved"
    completed = _run(restarted.execute(run_id))
    assert completed["assignment"]["status"] == "completed", completed
    assignment = env["lifecycle"].get_assignment(run_id)
    bill = step_by_id(assignment, "create-bill")
    assert bill["status"] == "applied"
    assert bill["result"]["remote_id"] == "bill-1"
    assert bill["result"]["data"]["total"] == "270.00"
    assert state["bill_calls"] == 1
    assert assignment["outcome_summary"]["objective_met"] is True
    assert Decimal("270.00") != Decimal("390.00")
    assert no_payment_step(assignment)

    # An exact replay of the accepted reply is idempotent, not a new
    # late reply: it reports the prior application without reviving the
    # completed assignment or creating a second effect.
    duplicate = restarted.record_external_response(
        run_id, "corr-invoice-v2", response="corrected invoice v2 again")
    assert duplicate["status"] == "already_applied"
    assert duplicate["assignment_status"] == "completed"
    operations = len(env["lifecycle"].get_task(run_id)["operations"])
    _run(restarted.execute(run_id))
    assert len(env["lifecycle"].get_task(run_id)["operations"]) == operations
    assert state["bill_calls"] == 1


def no_payment_step(assignment):
    return not any(
        "payment" in str(step.get("step_id") or "").lower()
        or "payment" in str(step.get("title") or "").lower()
        for step in assignment.get("steps") or [])


def test_procurement_campaign_period_close_blocks_bill(env):
    run_id, state, calls = _procurement_campaign(env)
    state["period_open"] = False
    executor = env["executor"]

    first = _run(executor.execute(run_id))
    assert first["assignment"]["status"] == "waiting", first
    assert step_by_id(
        env["lifecycle"].get_assignment(run_id), "check-period")[
            "result"]["data"]["period"]["open"] is False

    state["invoice_version"] = "v2"
    assert executor.record_external_response(
        run_id, "corr-invoice-v2", response="corrected invoice v2")[
            "status"] == "resumed"
    assignment = env["lifecycle"].get_assignment(run_id)
    correction = deterministic_adaptation({
        "observation_id": "invoice-v2-closed-period",
        "kind": "source_version",
        "step_id": "read-invoice",
        "reason": "corrected invoice arrived while the period was closed",
    }, assignment)
    adopt_adaptation(env["lifecycle"], run_id, correction)
    waiting = _run(executor.execute(run_id))
    assert waiting["assignment"]["status"] == "waiting", waiting
    assert step_by_id(
        env["lifecycle"].get_assignment(run_id), "create-bill")[
            "status"] == "awaiting_approval"

    executor.approve_step(run_id, "create-bill", approved_by="owner")
    refused = _run(executor.execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    create_bill = step_by_id(assignment, "create-bill")
    assert create_bill["status"] == "failed"
    assert "period is closed" in create_bill["failure"]["message"]
    assert state["bill_calls"] == 0
    assert calls["create-bill"] == 0
    assert refused["assignment"]["status"] != "completed"
    summary = assignment.get("outcome_summary")
    assert summary is None or summary["objective_met"] is not True


def test_industrial_quote_campaign_refuses_infeasible_delivery(env):
    run_id, state, calls, document_path = _quote_campaign(
        env, delivery_limit=5)
    executor = env["executor"]
    _run(executor.execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    eligibility = deterministic_adaptation({
        "observation_id": "elig-negative",
        "kind": "qualification",
        "fact_id": "b_discount_eligible",
        "value": True,
        "evidence_state": "established",
        "subject_id": "customer-1",
        "source_refs": [{"resource_id": "agreement-1", "version": "v3"}],
        "reason": "eligibility is established but delivery is not feasible",
    }, assignment)
    adopt_adaptation(env["lifecycle"], run_id, eligibility)

    state["a"]["qty"] = 3
    state["a"]["version"] = "a-v2"
    state["b"]["price"] = "55.00"
    state["b"]["version"] = "b-v2"
    for observation in (
        {"observation_id": "neg-b-price", "kind": "source_version",
         "step_id": "read-b"},
        {"observation_id": "neg-a-qty", "kind": "quantity",
         "step_id": "read-a"},
    ):
        assignment = env["lifecycle"].get_assignment(run_id)
        proposal = deterministic_adaptation(observation, assignment)
        adopt_adaptation(env["lifecycle"], run_id, proposal)
        _run(executor.execute(run_id))

    assignment = env["lifecycle"].get_assignment(run_id)
    replan = {
        "decision": "replan",
        "reason": "the approved equivalent is 7 days; the limit is 5",
        "observation_ids": ["neg-delivery"],
        "step_ids": ["select-a"],
        "new_steps": [{
            "step_id": "read-equivalence",
            "title": "Read the approved equivalence record",
            "operation_type": "retrieve",
            "adapter": "test.quote.read_equivalence",
            "effect": "read_only",
        }],
        "update_steps": [{
            "step_id": "select-a",
            "depends_on": ["read-a", "read-equivalence"],
        }],
    }
    adopt_adaptation(env["lifecycle"], run_id, replan)
    result = _run(executor.execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    assert step_by_id(assignment, "select-a")["result"]["data"][
        "selected"] == "equivalent"
    assert step_by_id(assignment, "calculate")["status"] == "applied"
    assert _decimal_money(
        step_by_id(assignment, "calculate")["result"]["value"]) == Decimal(
            "494.75")
    assert step_by_id(assignment, "verify-delivery")["status"] == "failed"
    assert "5" in step_by_id(
        assignment, "verify-delivery")["failure"]["message"]
    assert step_by_id(assignment, "document")["status"] == "pending"
    assert step_by_id(assignment, "draft")["status"] == "pending"
    assert not document_path.exists()
    assert result["assignment"]["status"] != "completed"
    summary = assignment.get("outcome_summary")
    assert summary is None or summary["objective_met"] is not True
