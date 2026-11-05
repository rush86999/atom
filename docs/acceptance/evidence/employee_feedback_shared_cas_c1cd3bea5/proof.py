#!/usr/bin/env python3
"""Fresh-session proof for the shared business/legacy annotation CAS.

Runs against a frozen backend extraction (set ATOM_BACKEND_ROOT). Scratch
SQLite and doubled transport only; no live model/provider call.

    ATOM_BACKEND_ROOT=/path/to/backend \
    PYTHONPATH=/path/to/backend TESTING=1 \
    python docs/acceptance/evidence/employee_feedback_shared_cas_c1cd3bea5/proof.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BACKEND_ROOT = Path(
    os.environ.get("ATOM_BACKEND_ROOT", Path.cwd() / "backend")).resolve()
sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("TESTING", "1")

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import core.database as database  # noqa: E402
from core.database import Base  # noqa: E402
from core.learning_llm_router import (  # noqa: E402
    LearningBasedRouter,
    RoutingFeedback,
)
from core.llm import learning_router_registry as registry  # noqa: E402
from core.llm.capability_profiles import (  # noqa: E402
    get_profile,
    load_feedback_evidence,
    reset_capability_evidence_cache,
)
from core.llm.fabrication_accounting import account_generations  # noqa: E402
from tests.test_employee_business_feedback import (  # noqa: E402
    _insert_outcome_row,
    _row_by_id,
    _synthetic_result,
)
from tests.test_employee_feedback_interleaving import (  # noqa: E402
    _pause_weak_read,
)


def _scratch(monkeypatch):
    db_path = Path("/private/tmp/atom-feedback-shared-cas-proof.db")
    if db_path.exists():
        db_path.unlink()
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", Session)
    router = object.__new__(LearningBasedRouter)
    LearningBasedRouter.__init__(router, Session())
    monkeypatch.setattr(
        registry, "get_learning_router_instance",
        lambda *args, **kwargs: router)
    return engine, {"Session": Session}


def _legacy_writer():
    return LearningBasedRouter.__new__(LearningBasedRouter)


def _pending_business_vs_legacy(
    monkeypatch, db, *, legacy_verdict, generation,
):
    from core.employee_routing_feedback import (
        record_pending_business_evaluation,
    )
    from core.models import LLMRoutingFeedback

    row_id = _insert_outcome_row(db, generation)
    if legacy_verdict == "unsupported_figures":
        with db["Session"]() as session:
            row = session.query(LLMRoutingFeedback).filter_by(
                id=row_id).one()
            row.quality_satisfied = False
            row.user_satisfaction = 0.1
            session.commit()
    read = threading.Event()
    release = threading.Event()
    _pause_weak_read(monkeypatch, generation, read, release)

    def _weak_pending():
        return asyncio.run(record_pending_business_evaluation(
            _synthetic_result(generation),
            stage="employee_evidence_selection",
            workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))

    with ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="weak") as pool:
        pending = pool.submit(_weak_pending)
        assert read.wait(20)
        try:
            strong = _legacy_writer()._persist_feedback(
                RoutingFeedback(
                    routing_result_id=generation,
                    tenant_id="tenant-ctrl",
                    model_id="llama3.1:8b",
                    task_type="general",
                    success=True,
                    quality_satisfied=(
                        legacy_verdict != "unsupported_figures"),
                    cost_within_budget=True,
                    user_satisfaction=(
                        0.1 if legacy_verdict == "unsupported_figures"
                        else 0.9),
                ),
                {"verdict": legacy_verdict})
        finally:
            release.set()
        weak = pending.result(timeout=20)
    row = _row_by_id(db, row_id)
    accounting = account_generations([row]).as_dict()
    return {
        "legacy_verdict": legacy_verdict,
        "weak_status": weak.get("status"),
        "weak_recorded": weak.get("recorded"),
        "strong_status": strong,
        "final_verdict": (
            (row.prompt_features or {}).get("verdict")),
        "final_evaluation_revision": (
            (row.prompt_features or {}).get("evaluation_revision")),
        "accounting": {
            "generations": accounting["generations"],
            "fabricated": accounting["fabricated"],
            "grounded_ok": accounting["grounded_ok"],
        },
    }


def _stale_legacy_vs_business_failure(monkeypatch, db, generation):
    from core.employee_routing_feedback import record_attempt_evaluation

    row_id = _insert_outcome_row(db, generation)
    read = threading.Event()
    release = threading.Event()
    _pause_weak_read(monkeypatch, generation, read, release)

    def _weak_legacy():
        return _legacy_writer()._persist_feedback(
            RoutingFeedback(
                routing_result_id=generation,
                tenant_id="tenant-ctrl",
                model_id="llama3.1:8b",
                task_type="general",
                success=True,
                quality_satisfied=True,
                cost_within_budget=True,
                user_satisfaction=0.9,
            ),
            {"verdict": "grounding_ok"})

    with ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="weak") as pool:
        pending = pool.submit(_weak_legacy)
        assert read.wait(20)
        try:
            strong = asyncio.run(record_attempt_evaluation(
                _synthetic_result(generation),
                stage="employee_evidence_selection",
                evaluation="failed",
                failure_kind="wrong_evidence_selection",
                workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
        finally:
            release.set()
        weak = pending.result(timeout=20)
    row = _row_by_id(db, row_id)
    reset_capability_evidence_cache()
    evidence = load_feedback_evidence(
        get_profile("employee_evidence_selection"),
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl")
    route = evidence.get("local_ctrl1234/llama3.1:8b") or {}
    return {
        "weak_status": weak,
        "strong_status": strong.get("status"),
        "final_verdict": (
            (row.prompt_features or {}).get("verdict")),
        "final_evaluation_revision": (
            (row.prompt_features or {}).get("evaluation_revision")),
        "selector": {
            "semantic_failures": route.get("semantic_failures"),
            "last_failure_kind": route.get("last_failure_kind"),
        },
    }


def main() -> int:
    mp = pytest.MonkeyPatch()
    engine, db = _scratch(mp)
    try:
        grounding = _pending_business_vs_legacy(
            mp, db, legacy_verdict="grounding_ok",
            generation="shared-cas-grounding")
        fabrication = _pending_business_vs_legacy(
            mp, db, legacy_verdict="unsupported_figures",
            generation="shared-cas-fabrication")
        stale_legacy = _stale_legacy_vs_business_failure(
            mp, db, generation="shared-cas-stale-legacy")
        proof = {
            "schema": "atom-feedback-shared-cas-proof-1",
            "executed_source": os.getenv("ATOM_PROOF_SOURCE", ""),
            "pending_business_vs_grounding_ok": grounding,
            "pending_business_vs_unsupported_figures": fabrication,
            "stale_legacy_grounding_vs_business_failure": stale_legacy,
            "boundaries": [
                "scratch SQLite feedback table; fresh sessions read the rows",
                "doubled transport; no live model inference",
                "one shared annotation CAS and evaluation revision",
                "legacy grounding/fabrication keeps its generation+model binding",
                "pending business skips when a legacy verdict committed",
                "stale legacy grounding skips when a business failure committed",
                "fabrication/grounding accounting still consumes the row",
                "business selector still sees the committed failure",
            ],
        }
        out = Path(__file__).with_name("feedback-shared-cas-proof.json")
        out.write_text(json.dumps(proof, indent=1, default=str) + "\n")
        print(json.dumps(proof, indent=1, default=str)[:5000])
        return 0
    finally:
        reset_capability_evidence_cache()
        mp.undo()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
