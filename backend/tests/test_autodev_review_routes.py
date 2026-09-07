"""Auto-Dev review routes — the supervisor API for the evolution harness.

Covers the journey contract: pending candidates (Memento skills +
AlphaEvolver tool mutations) list unified; approve/reject transition
statuses; tool-error signals aggregate per signature for the review UI.
"""

import importlib
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.autodev_review_routes as review_routes
from core.auth import get_current_tenant, get_current_user
from core.database import get_db


class _Chain:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    def all(self):
        return list(self._rows)

    def __iter__(self):
        return iter(list(self._rows))

    def first(self):
        return self._rows[0] if self._rows else None


class _StubDB:
    def __init__(self, rows_by_model):
        self._rows = rows_by_model
        self.committed = False

    def query(self, model):
        return _Chain(self._rows.get(model, []))

    def commit(self):
        self.committed = True


def _make_client(db):
    app = FastAPI()
    app.include_router(review_routes.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    app.dependency_overrides[get_current_tenant] = lambda: SimpleNamespace(id="t1")
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _skill_candidate(status="pending"):
    return SimpleNamespace(
        id="cand-1",
        tenant_id="t1",
        agent_id=AGENT,
        skill_name="outlook_search_fix",
        skill_description="Search the mailbox safely",
        generated_code="def run(): ...",
        failure_pattern={"failure_summary": "outlook search 400s on emails"},
        validation_status=status,
        created_at=None,
    )


def _tool_mutation(status="pending"):
    return SimpleNamespace(
        id="mut-1",
        tenant_id="t1",
        tool_name="outlook.search_emails",
        mutated_code="def mutated(): ...",
        sandbox_status=status,
        execution_error=None,
        created_at=None,
    )


AGENT = "agent-1"


def test_list_candidates_unifies_skills_and_mutations():
    db = _StubDB({
        review_routes.SkillCandidate: [_skill_candidate()],
        review_routes.ToolMutation: [_tool_mutation()],
    })
    client = _make_client(db)

    r = client.get("/api/autodev/candidates")
    assert r.status_code == 200
    body = r.json()["data"]
    kinds = {c["kind"] for c in body["candidates"]}
    assert kinds == {"skill", "mutation"}
    assert body["count"] == 2
    names = {c["name"] for c in body["candidates"]}
    assert names == {"outlook_search_fix", "outlook.search_emails"}


def test_approve_skill_marks_validated_and_commits():
    candidate = _skill_candidate()
    db = _StubDB({review_routes.SkillCandidate: [candidate]})
    client = _make_client(db)

    r = client.post("/api/autodev/skills/cand-1/approve")
    assert r.status_code == 200
    assert candidate.validation_status == "validated"
    assert candidate.validated_at is not None
    assert db.committed is True


def test_reject_mutation_marks_rejected():
    mutation = _tool_mutation()
    db = _StubDB({review_routes.ToolMutation: [mutation]})
    client = _make_client(db)

    r = client.post("/api/autodev/mutations/mut-1/reject")
    assert r.status_code == 200
    assert mutation.sandbox_status == "rejected"


def test_approve_missing_candidate_404():
    db = _StubDB({review_routes.SkillCandidate: []})
    client = _make_client(db)

    r = client.post("/api/autodev/skills/nope/approve")
    assert r.status_code == 404


def test_tool_errors_aggregate_by_signature():
    executions = []
    for i, err in enumerate([
        [{"signature": "outlook.search_emails", "error": "400 '@'", "at": "2026-09-02T18:00:00"}],
        [{"signature": "outlook.search_emails", "error": "400 '@' again", "at": "2026-09-02T19:00:00"}],
    ]):
        executions.append(SimpleNamespace(
            id=f"e{i}", agent_id=AGENT, status="completed",
            metadata_json={"tool_errors": err},
        ))
    db = _StubDB({review_routes.AgentExecution: executions})
    client = _make_client(db)

    r = client.get("/api/autodev/tool-errors", params={"agent_id": AGENT})
    assert r.status_code == 200
    body = r.json()["data"]["tool_errors"]
    assert len(body) == 1
    assert body[0]["signature"] == "outlook.search_emails"
    assert body[0]["count"] == 2
    assert "again" in body[0]["last_error"]
