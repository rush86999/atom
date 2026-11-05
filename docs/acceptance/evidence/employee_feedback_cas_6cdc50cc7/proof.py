#!/usr/bin/env python3
"""Fresh-session proof for the feedback annotation CAS.

Runs against a frozen backend extraction (set ATOM_BACKEND_ROOT). Uses a
scratch SQLite table and doubled transport only. No live model, provider,
credential, spend or network call.

    ATOM_BACKEND_ROOT=/path/to/backend \
    PYTHONPATH=/path/to/backend TESTING=1 \
    python docs/acceptance/evidence/employee_feedback_cas_6cdc50cc7/proof.py
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
from core.learning_llm_router import LearningBasedRouter  # noqa: E402
from core.llm import learning_router_registry as registry  # noqa: E402
from core.llm.capability_profiles import (  # noqa: E402
    get_profile,
    load_feedback_evidence,
    reset_capability_evidence_cache,
)
from tests.test_employee_business_feedback import (  # noqa: E402
    _insert_outcome_row,
    _row_by_id,
)
from tests.test_employee_feedback_interleaving import (  # noqa: E402
    _evaluate,
    _pause_weak_read,
)


def _scratch(monkeypatch):
    db_path = Path("/private/tmp/atom-feedback-cas-proof.db")
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


def _selector(db):
    reset_capability_evidence_cache()
    evidence = load_feedback_evidence(
        get_profile("employee_evidence_selection"),
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl")
    route = evidence.get("local_ctrl1234/llama3.1:8b") or {}
    incidents = route.get("incidents") or []
    return {
        "samples": route.get("samples"),
        "successes": route.get("successes"),
        "semantic_failures": route.get("semantic_failures"),
        "last_failure_kind": route.get("last_failure_kind"),
        "incident_ids": [item.get("incident_id") for item in incidents],
    }


def _interleave(monkeypatch, db, *, weak_kind, generation):
    row_id = _insert_outcome_row(db, generation)
    read = threading.Event()
    release = threading.Event()
    _pause_weak_read(monkeypatch, generation, read, release)
    with ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="weak") as pool:
        pending = pool.submit(_evaluate, weak_kind, generation)
        assert read.wait(20)
        try:
            strong = _evaluate(False, generation)
        finally:
            release.set()
        weak = pending.result(timeout=20)
    row = _row_by_id(db, row_id)
    features = row.prompt_features or {}
    return {
        "weak_kind": weak_kind,
        "weak_status": weak.get("status"),
        "weak_recorded": weak.get("recorded"),
        "strong_status": strong.get("status"),
        "final_success": row.success,
        "final_quality_satisfied": row.quality_satisfied,
        "final_business_outcome": features.get("business_outcome"),
        "final_verdict": features.get("verdict"),
        "final_failure_kind": features.get("failure_kind"),
        "selector": _selector(db),
    }


def main() -> int:
    mp = pytest.MonkeyPatch()
    engine, db = _scratch(mp)
    try:
        stale_positive = _interleave(
            mp, db, weak_kind="positive",
            generation="cas-proof-stale-positive")
        stale_pending = _interleave(
            mp, db, weak_kind="pending",
            generation="cas-proof-stale-pending")

        stronger_generation = "cas-proof-stronger-failure"
        stronger_id = _insert_outcome_row(db, stronger_generation)
        positive = _evaluate(True, stronger_generation)
        failure = _evaluate(False, stronger_generation)
        stronger_row = _row_by_id(db, stronger_id)
        stronger = {
            "positive_status": positive.get("status"),
            "failure_status": failure.get("status"),
            "final_success": stronger_row.success,
            "final_verdict": (
                (stronger_row.prompt_features or {}).get("verdict")),
            "selector": _selector(db),
        }

        duplicate_generation = "cas-proof-duplicate"
        duplicate_id = _insert_outcome_row(db, duplicate_generation)
        first = _evaluate(False, duplicate_generation)
        before = _selector(db)
        second = _evaluate(False, duplicate_generation)
        after = _selector(db)
        duplicate_row = _row_by_id(db, duplicate_id)
        duplicate = {
            "first_status": first.get("status"),
            "second_status": second.get("status"),
            "second_recorded": second.get("recorded"),
            "incident_id_stable": (
                before["incident_ids"] == after["incident_ids"]),
            "final_success": duplicate_row.success,
        }

        changed_generation = "cas-proof-changed-binding"
        changed_id = _insert_outcome_row(db, changed_generation)
        read = threading.Event()
        release = threading.Event()
        _pause_weak_read(mp, changed_generation, read, release)
        with ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="weak") as pool:
            pending = pool.submit(_evaluate, "positive", changed_generation)
            assert read.wait(20)
            try:
                from core.models import LLMRoutingFeedback

                with db["Session"]() as session:
                    row = session.query(LLMRoutingFeedback).filter(
                        LLMRoutingFeedback.id == changed_id).one()
                    features = dict(row.prompt_features or {})
                    features["workspace_id"] = "ws-changed"
                    row.prompt_features = features
                    session.commit()
            finally:
                release.set()
            changed_weak = pending.result(timeout=20)
        changed_row = _row_by_id(db, changed_id)
        changed = {
            "weak_status": changed_weak.get("status"),
            "weak_recorded": changed_weak.get("recorded"),
            "final_workspace_id": (
                (changed_row.prompt_features or {}).get("workspace_id")),
            "final_business_outcome": (
                (changed_row.prompt_features or {}).get("business_outcome")),
            "final_success": changed_row.success,
        }

        proof = {
            "schema": "atom-feedback-cas-proof-1",
            "executed_source": os.getenv("ATOM_PROOF_SOURCE", ""),
            "stale_positive_vs_committed_failure": stale_positive,
            "stale_pending_vs_committed_failure": stale_pending,
            "stronger_failure_vs_positive": stronger,
            "duplicate_same_verdict": duplicate,
            "changed_binding_during_evaluation": changed,
            "boundaries": [
                "scratch SQLite feedback table; fresh sessions read the rows",
                "doubled transport; no live model inference",
                "database-enforced CAS, authoritative reload, bounded retry",
                "stale positive/pending writers cannot erase a committed failure",
                "stronger failure wins over a committed positive",
                "duplicate verdict is idempotent with stable incident identity",
                "changed binding during evaluation refuses",
                "selector evidence reflects the committed failure",
            ],
        }
        out = Path(__file__).with_name("feedback-cas-proof.json")
        out.write_text(json.dumps(proof, indent=1, default=str) + "\n")
        print(json.dumps(proof, indent=1, default=str)[:5000])
        return 0
    finally:
        reset_capability_evidence_cache()
        mp.undo()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
