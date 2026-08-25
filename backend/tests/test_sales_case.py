"""
Sales Case service + tools tests — the AI sales agent's central object.

The service (core/sales_case.py) and the tools (tools/sales_tool.py, wired
through the action registry) are tested against the conftest worker DB via a
patched ``get_db_session``, so nothing leaks into the real dev DB.
"""

import os

os.environ.setdefault("TESTING", "1")

from contextlib import contextmanager
from unittest.mock import patch

import pytest

from core.action_registry import action_registry
from core.sales_case import (
    ask_human,
    create_case,
    find_case_by_email,
    get_case,
    list_cases,
    transition,
    valid_transition,
)


@pytest.fixture
def db(worker_database):
    """Point core.sales_case.get_db_session at the worker (in-memory) DB and
    wipe sales rows after each test (worker DB is session-scoped/shared)."""
    SessionLocal = worker_database

    @contextmanager
    def _session():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    with patch("core.sales_case.get_db_session", _session):
        yield

    s = SessionLocal()
    try:
        from core.models import HITLAction, SalesCase

        s.query(HITLAction).delete()
        s.query(SalesCase).delete()
        s.commit()
    except Exception:
        s.rollback()
    finally:
        s.close()


def _make_case(**over):
    kwargs = dict(
        customer_name="Jane Smith",
        customer_email="jane@acme.example",
        subject="Quote Request - Press Brake",
        intent="request_quote",
        conversation_id="thread-1",
    )
    kwargs.update(over)
    return create_case(**kwargs)


# --------------------------------------------------------------------------- #
# Service: create / get / find
# --------------------------------------------------------------------------- #

def test_create_case(db):
    case = _make_case()
    assert case["status"] == "new"
    assert case["customer_email"] == "jane@acme.example"
    assert any(d["action"] == "case_created" for d in case["decisions"])
    assert case["id"]


def test_get_case_missing(db):
    assert get_case("nope") is None


def test_find_case_by_email_keys(db):
    _make_case()
    assert find_case_by_email(customer_email="jane@acme.example") is not None
    assert find_case_by_email(conversation_id="thread-1") is not None
    assert find_case_by_email() is None


def test_find_case_excludes_completed_when_open_only(db):
    case = _make_case()
    transition(case["id"], "completed", reason="done")
    assert find_case_by_email(customer_email="jane@acme.example", open_only=True) is None
    assert find_case_by_email(customer_email="jane@acme.example", open_only=False) is not None


def test_list_cases_status_filter(db):
    c1 = _make_case()
    c2 = create_case(customer_email="bob@example.com", subject="Service")
    transition(c2["id"], "researching", reason="vendor price")  # valid from new
    listed = list_cases(status="researching")
    assert all(c["status"] == "researching" for c in listed)
    assert any(c["id"] == c2["id"] for c in listed)
    assert all(c["id"] != c1["id"] for c in listed)


# --------------------------------------------------------------------------- #
# Service: transitions
# --------------------------------------------------------------------------- #

def test_transition_valid(db):
    case = _make_case()
    out = transition(case["id"], "researching", reason="needs vendor check")
    assert out["success"] is True
    assert out["case"]["status"] == "researching"
    assert any("researching" in d["action"] for d in out["case"]["decisions"])


def test_transition_invalid(db):
    case = _make_case()
    out = transition(case["id"], "shipping")
    assert out["success"] is False
    assert "invalid_transition" in out["error"]
    assert out["case"]["status"] == "new"  # unchanged


def test_transition_unknown_case(db):
    out = transition("nope", "researching")
    assert out["success"] is False
    assert out["error"] == "case_not_found"


def test_valid_transition_map():
    assert valid_transition("new", "researching")
    assert valid_transition("waiting_for_vendor", "quoting")
    assert not valid_transition("completed", "new")
    assert not valid_transition("shipping", "quoting")


# --------------------------------------------------------------------------- #
# Service: ask human (HITL)
# --------------------------------------------------------------------------- #

def test_ask_human_pauses_case(db):
    case = _make_case()
    out = ask_human(case["id"], "Does this configuration meet the customer's application?")
    assert out["success"] is True
    assert out["hitl_id"]
    updated = get_case(case["id"])
    assert updated["status"] == "waiting_for_human"
    assert updated["human_interventions"][0]["hitl_id"] == out["hitl_id"]


def test_ask_human_unknown_case(db):
    out = ask_human("nope", "question?")
    assert out["success"] is False
    assert out["error"] == "case_not_found"


# --------------------------------------------------------------------------- #
# Tools (via the action registry — the agent's real dispatch surface)
# --------------------------------------------------------------------------- #

def test_registry_has_sales_tools():
    names = action_registry.list_actions()
    for n in (
        "sales.case.create",
        "sales.case.get",
        "sales.case.list",
        "sales.case.transition",
        "sales.case.ask_human",
        "sales.inventory.check",
        "sales.quote.calculate",
    ):
        assert n in names, f"missing registered action {n}"


@pytest.mark.asyncio
async def test_sales_case_create_tool(db):
    out = await action_registry.execute_action(
        "sales.case.create",
        {"customer_email": "tool@example.com", "subject": "Hi", "intent": "question"},
        {"workspace_id": "default", "tenant_id": "default"},
    )
    assert out["success"] is True
    assert out["case"]["status"] == "new"
    assert out["case"]["customer_email"] == "tool@example.com"


@pytest.mark.asyncio
async def test_sales_case_transition_tool(db):
    case = _make_case()
    out = await action_registry.execute_action(
        "sales.case.transition",
        {"case_id": case["id"], "status": "researching", "reason": "vendor price"},
        {},
    )
    assert out["success"] is True
    assert out["case"]["status"] == "researching"
    # The validated map must reject an illegal jump (shipping from new).
    bad = await action_registry.execute_action(
        "sales.case.transition",
        {"case_id": case["id"], "status": "shipping"},
        {},
    )
    assert bad["success"] is False
    assert "invalid_transition" in bad["error"]


@pytest.mark.asyncio
async def test_sales_inventory_check_requires_product():
    out = await action_registry.execute_action("sales.inventory.check", {}, {})
    assert out["success"] is False
    assert out["error"] == "product is required"


@pytest.mark.asyncio
async def test_sales_quote_calculate_missing_case():
    out = await action_registry.execute_action("sales.quote.calculate", {"case_id": "nope"}, {})
    assert out["success"] is False
    assert out["error"] == "case_not_found"
