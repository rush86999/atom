"""Live session-factory binding for business AND legacy routing feedback.

Failure-first incident (joined main-230 gate, 2026-11-10): ``core.database``'s
session factory is deliberately swapped by harnesses/bootstrap code. A
module-level ``from core.database import get_db_session`` in
``core.learning_llm_router`` froze whichever factory existed at import time.
If that import happened while a temporary factory was installed, every later
business annotation read the OLD database: the model dispatch succeeded, the
consumer reported ``recorded=True``, but ``LLMRoutingFeedback`` had no exact
generation row because the write/read went to the stale (sometimes disposed)
store.

These controls are permanent and failure-first:

1. the router resolves the CURRENT authoritative factory on every call;
2. the established ``core.learning_llm_router.get_db_session`` override seam
   still wins;
3. a subprocess imports the router WHILE a temporary factory is installed,
   then restores the authoritative factory — business and legacy annotations
   must both land in the authoritative DB, never the old one — with the exact
   receipt/CAS status, binding and classification unchanged.

The subprocess isolate matters: it reproduces the real import-order defect
without leaking reloaded module state into the rest of the suite.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def test_router_resolves_current_authoritative_factory_each_call(monkeypatch):
    from core import database, learning_llm_router

    first, second = object(), object()
    monkeypatch.setattr(database, "get_db_session", lambda: first)
    assert learning_llm_router.get_db_session() is first
    monkeypatch.setattr(database, "get_db_session", lambda: second)
    assert learning_llm_router.get_db_session() is second


def test_existing_local_session_override_seam_is_preserved(monkeypatch):
    from core import learning_llm_router

    marker = object()
    monkeypatch.setattr(learning_llm_router, "get_db_session", lambda: marker)
    assert learning_llm_router.get_db_session() is marker


_SUBPROCESS_SCRIPT = r'''
import json
import sys
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

old_path, new_path = Path(sys.argv[1]), Path(sys.argv[2])

from core.models_registration import Base
from core.models import LLMRoutingFeedback

old_engine = create_engine(
    f"sqlite:///{old_path}", connect_args={"check_same_thread": False})
new_engine = create_engine(
    f"sqlite:///{new_path}", connect_args={"check_same_thread": False})
Base.metadata.create_all(old_engine)
Base.metadata.create_all(new_engine)
OldSession = sessionmaker(bind=old_engine)
NewSession = sessionmaker(bind=new_engine)
old_engine.dispose()   # stale store is DETACHED, like a disposed/rotated DB
new_engine.dispose()


def factory(Session):
    @contextmanager
    def _session():
        db = Session()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    return _session


def insert_row(Session, generation, marker, *, model="llama3.1:8b",
               provider="local_ctrl1234", workspace="ws-ctrl",
               tenant="tenant-ctrl", profile="employee_evidence_selection",
               version="2026-11-04.1"):
    db = Session()
    try:
        db.add(LLMRoutingFeedback(
            routing_result_id=generation,
            tenant_id=tenant,
            task_type="general",
            model_id=model,
            success=True,
            quality_satisfied=True,
            cost_within_budget=True,
            user_satisfaction=0.8,
            actual_cost=0.0123,
            actual_latency_ms=45.6,
            prompt_features={
                "route_provider": provider,
                "capability_profile": profile,
                "profile_version": version,
                "workspace_id": workspace,
                "db_marker": marker,
            },
        ))
        db.commit()
    finally:
        db.close()


def row(Session, generation):
    db = Session()
    try:
        return (db.query(LLMRoutingFeedback)
                .filter(LLMRoutingFeedback.routing_result_id == generation)
                .one())
    finally:
        db.close()


import core.database as database

# 1. The router is imported WHILE a temporary factory is installed.
database.get_db_session = factory(PrefixOldSession := OldSession)
import core.learning_llm_router as lr
from core.learning_llm_router import LearningBasedRouter, RoutingFeedback

# 2. The caller restores/rotates to the CURRENT authoritative factory.
database.get_db_session = factory(NewSession)

insert_row(OldSession, "gen-business", "old")
insert_row(NewSession, "gen-business", "new")
insert_row(OldSession, "gen-legacy", "old")
insert_row(NewSession, "gen-legacy", "new")

writer = LearningBasedRouter.__new__(LearningBasedRouter)
receipt = {
    "routing_result_id": "gen-business",
    "provider": "local_ctrl1234",
    "model": "llama3.1:8b",
    "profile": "employee_evidence_selection",
    "profile_version": "2026-11-04.1",
}

business_status = writer._persist_feedback(RoutingFeedback(
    routing_result_id="gen-business",
    tenant_id="tenant-ctrl",
    model_id="llama3.1:8b",
    task_type="general",
    success=False,
    quality_satisfied=False,
    cost_within_budget=True,
    user_satisfaction=0.15,
    provider_id="local_ctrl1234",
    capability_profile="employee_evidence_selection",
    capability_profile_version="2026-11-04.1",
    workspace_id="ws-ctrl",
    # The real consumer passes the classified failure as this generation's
    # verdict (record_attempt_evaluation: failure_kind or generic). Without
    # it the write is a pending marker and quality is intentionally untouched.
    verdict="wrong_evidence_selection",
    verdict_rule="business_outcome_v1",
    failure_kind="wrong_evidence_selection",
    evidence_features={
        "business_outcome": "failed",
        "business_stage": "employee_evidence_selection",
        "business_rule": "business_outcome_v1",
        "business_outcome_scope": "result",
    },
), None)

legacy_status = writer._persist_feedback(RoutingFeedback(
    routing_result_id="gen-legacy",
    tenant_id="tenant-ctrl",
    model_id="llama3.1:8b",
    task_type="general",
    # A fabrication correction rewrites the judged row's quality fields; keep
    # the correction on the authoritative row and the stale row untouched.
    success=False,
    quality_satisfied=False,
    cost_within_budget=True,
    user_satisfaction=0.15,
    provider_id="local_ctrl1234",
    workspace_id="ws-ctrl",
    verdict="unsupported_figures",
), {"verdict": "unsupported_figures"})

new_business = row(NewSession, "gen-business")
new_legacy = row(NewSession, "gen-legacy")
old_business = row(OldSession, "gen-business")
old_legacy = row(OldSession, "gen-legacy")
old_business_features = old_business.prompt_features or {}
old_legacy_features = old_legacy.prompt_features or {}

result = {
    "business_status": business_status,
    "legacy_status": legacy_status,
    "new_business_failure_kind": (
        new_business.prompt_features or {}).get("failure_kind"),
    "new_business_quality": new_business.quality_satisfied,
    "new_business_features": new_business.prompt_features,
    "new_legacy_verdict": (new_legacy.prompt_features or {}).get("verdict"),
    "new_legacy_quality": new_legacy.quality_satisfied,
    "new_legacy_success": new_legacy.success,
    "new_business_revision": (
        new_business.prompt_features or {}).get("evaluation_revision"),
    "new_legacy_revision": (
        new_legacy.prompt_features or {}).get("evaluation_revision"),
    "old_business_failure_kind": old_business_features.get("failure_kind"),
    "old_business_quality": old_business.quality_satisfied,
    "old_business_marker": old_business_features.get("db_marker"),
    "old_legacy_verdict": old_legacy_features.get("verdict"),
    "old_legacy_quality": old_legacy.quality_satisfied,
    "old_legacy_marker": old_legacy_features.get("db_marker"),
    "resolved_factory": lr.get_db_session,
}
print("RESULT:" + json.dumps(result, default=repr))
'''


def _run_rebinding_case(tmp_path):
    old_db = tmp_path / "old-stale.db"
    new_db = tmp_path / "new-authoritative.db"
    env = os.environ.copy()
    env["TESTING"] = "1"
    env["SECRET_KEY"] = "scratch-only-readable"
    env["DATABASE_URL"] = f"sqlite:///{tmp_path / 'unused.db'}"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(BACKEND)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    proc = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(_SUBPROCESS_SCRIPT),
         str(old_db), str(new_db)],
        cwd=str(BACKEND), env=env, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, (
        f"subprocess failed rc={proc.returncode}\nstdout:\n{proc.stdout}\n"
        f"stderr:\n{proc.stderr[-4000:]}")
    payload = None
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT:"):
            payload = line[len("RESULT:"):]
    assert payload is not None, proc.stdout[-4000:]
    import json

    return json.loads(payload)


def test_business_and_legacy_writes_follow_the_restored_factory(tmp_path):
    result = _run_rebinding_case(tmp_path)

    # Exact receipt/CAS status at the DB boundary.
    assert result["business_status"] == "annotated", result
    assert result["legacy_status"] == "annotated", result

    # Business annotation landed on the CURRENT authoritative row.
    assert result["new_business_failure_kind"] == "wrong_evidence_selection"
    assert result["new_business_quality"] is False
    features = result["new_business_features"]
    assert features["business_outcome"] == "failed"
    assert features["workspace_id"] == "ws-ctrl"
    assert features["route_provider"] == "local_ctrl1234"
    assert features["capability_profile"] == "employee_evidence_selection"

    # Legacy correction also landed on the CURRENT authoritative row.
    assert result["new_legacy_verdict"] == "unsupported_figures"
    assert result["new_legacy_quality"] is False
    assert result["new_legacy_success"] is False
    # The annotation receipt carries a bumped evaluation revision (the CAS
    # wrote exactly one revision, not an unrelated rewrite).
    assert result["new_business_revision"] == 1
    assert result["new_legacy_revision"] == 1

    # The stale/disposed factory's rows were never annotated.
    assert result["old_business_failure_kind"] is None
    assert result["old_business_quality"] is True
    assert result["old_business_marker"] == "old"
    assert result["old_legacy_verdict"] is None
    assert result["old_legacy_quality"] is True
    assert result["old_legacy_marker"] == "old"
