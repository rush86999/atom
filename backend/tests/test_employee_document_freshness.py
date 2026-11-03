"""document.text must bind the version that actually produced cached text."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from core.assignment_executor import (
    AssignmentExecutor, NeedsContext, _document_text_read,
)
from core.assignment_plan import new_assignment, new_step
from core.assignment_readiness import evaluate_step_readiness
from tests.test_assignment_executor import env  # noqa: F401


def _fixture(monkeypatch, *, indexed, sql, metadata=None, row_scope=None):
    import core.lancedb_handler as lance
    import core.database as database

    document = {
        "id": "doc-1",
        "text": '{"invoice_id":"INV-1","po_id":"PO-1","quantity":"2",'
                '"unit_price":"120"}',
        "source": "invoice.json",
        "metadata": {
            "source_content_hash": indexed,
            "pg_document_id": "doc-1",
            **(metadata or {}),
        },
    }
    handler = SimpleNamespace(
        get_document_by_id=lambda table, doc: document)
    monkeypatch.setattr(lance, "get_lancedb_handler", lambda workspace: handler)
    scope = {"workspace_id": "ws-1", "tenant_id": "t-1",
             **(row_scope or {})}
    row = SimpleNamespace(
        source_content_hash=sql, freshness_status="fresh", **scope)

    class Query:
        def filter(self, *args):
            return self

        def first(self):
            return row if sql is not None else None

    @contextmanager
    def session():
        yield SimpleNamespace(query=lambda model: Query())

    monkeypatch.setattr(database, "get_db_session", session)
    return {
        "resource_id": "doc-1", "source_version": sql or "",
        "workspace_id": "ws-1", "tenant_id": "t-1",
    }


def _run(binding, context=None, inputs=None):
    return asyncio.run(_document_text_read(
        {**(inputs or {}), "resource_binding": binding},
        context or {"workspace_id": "ws-1", "tenant_id": "t-1"}))


@pytest.mark.parametrize("indexed,sql,ok", [
    ("v-new", "v-new", True),
    ("v-old", "v-new", False),
    ("v-new", None, False),
    ("", "v-new", False),
])
def test_indexed_extraction_version_must_match_sql(
        monkeypatch, indexed, sql, ok):
    binding = _fixture(monkeypatch, indexed=indexed, sql=sql)
    if ok:
        result = _run(binding)
        assert result["source_version"] == "v-new"
        assert result["verification"]["version"] == "v-new"
        assert result["extraction"]["text_sha256"]
    else:
        with pytest.raises(NeedsContext):
            _run(binding)


@pytest.mark.parametrize("case", [
    "scope", "tenant", "identity", "binding_version", "stale",
])
def test_extraction_scope_identity_and_freshness_refuse(monkeypatch, case):
    indexed = "v-new"
    sql = "v-new"
    metadata = {}
    row_scope = {}
    expected = "v-new"
    if case == "scope":
        row_scope = {"workspace_id": "other"}
    elif case == "tenant":
        row_scope = {"tenant_id": "other"}
    elif case == "identity":
        metadata = {"pg_document_id": "other-doc"}
    elif case == "binding_version":
        expected = "v-old"
    elif case == "stale":
        pass
    binding = _fixture(
        monkeypatch, indexed=indexed, sql=sql,
        metadata=metadata, row_scope=row_scope)
    binding["source_version"] = expected
    if case == "stale":
        # A stale authoritative row is represented by replacing the row's
        # freshness in the same fixture.
        import core.database as database

        original = database.get_db_session

        @contextmanager
        def stale_session():
            with original() as db:
                row = db.query(None).first()
                row.freshness_status = "stale"
                yield db

        monkeypatch.setattr(database, "get_db_session", stale_session)
    with pytest.raises(NeedsContext):
        _run(binding)


def test_matching_extraction_releases_dependent_readiness(monkeypatch):
    binding = _fixture(monkeypatch, indexed="v-new", sql="v-new")
    result = _run(binding)
    source = new_step(
        step_id="read", title="Read authorized document",
        operation_type="retrieve", adapter="document.text", inputs={
            "resource_binding": binding}, effect="read_only")
    source.update(status="applied", operation_id="read-op", result=result)
    child = new_step(
        step_id="consume", title="Consume current evidence",
        operation_type="calculate", adapter="invoice.reconcile",
        inputs={}, requires=[{
            "kind": "receipt", "step_id": "read",
            "require": "verified"}])
    ready = evaluate_step_readiness(
        child, new_assignment(
            objective="Reconcile", steps=[source, child]),
        task_authorization="read_only")
    assert ready["eligible"] is True


def test_stale_extraction_does_not_run_dependent_work(
        env, monkeypatch):
    binding = _fixture(monkeypatch, indexed="v-old", sql="v-new")
    calls = []

    async def count(inputs, context):
        calls.append(1)
        return {"status": "applied", "summary": "should not run"}

    env["registry"].register("test.currency.count", count)
    source = new_step(
        step_id="read", title="Read authorized document",
        operation_type="retrieve", adapter="document.text", inputs={
            "resource_binding": binding}, effect="read_only")
    child = new_step(
        step_id="consume", title="Consume current evidence",
        operation_type="calculate", adapter="test.currency.count",
        inputs={}, effect="local", depends_on=["read"], requires=[{
            "kind": "receipt", "step_id": "read", "require": "verified"}])
    plan = new_assignment(
        objective="Use current document evidence",
        workspace_id="ws_assign", tenant_id="tenant_assign",
        steps=[source, child], authorized_actions=["retrieve", "calculate"])
    record = env["executor"].create_assignment(
        "conv-stale-extraction", plan["objective"], assignment=plan)
    run_id = record["run_id"]
    asyncio.run(env["executor"].execute(run_id))
    restarted = AssignmentExecutor(
        env["lifecycle"], adapters=env["registry"].clone())
    result = asyncio.run(restarted.execute(run_id))
    assert calls == []
    assert result["assignment"]["status"] != "completed"
    final = env["lifecycle"].get_assignment(run_id)
    source_step = next(
        item for item in final["steps"] if item["step_id"] == "read")
    assert source_step["status"] != "applied"
