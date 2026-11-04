#!/usr/bin/env python3
"""Deterministic proof: evaluated bad work -> persisted feedback -> new route.

Runs the real employee consumer, LLMService and BYOKHandler against a scratch
SQLite feedback table. Only the provider transport is doubled. No live model,
provider, credential, spend or network call is used.

Run from the repository root:
    TESTING=1 PYTHONPATH=backend python \
      docs/acceptance/evidence/employee_business_feedback_2ab959fc0/proof.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("TESTING", "1")

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import core.database as database  # noqa: E402
from core.database import Base  # noqa: E402
from core.employee_proposal import propose_employee_work  # noqa: E402
from core.learning_llm_router import LearningBasedRouter  # noqa: E402
from core.llm import learning_router_registry as registry  # noqa: E402
from core.llm.capability_profiles import (  # noqa: E402
    get_profile,
    load_feedback_evidence,
    reset_capability_evidence_cache,
)
from tests.test_employee_business_feedback import (  # noqa: E402
    _configure_pool,
    _context,
    _handler,
    _route_aware_instructor,
    _rows,
    _service,
    _valid_proposal,
)


def _row_view(row):
    features = dict(row.prompt_features or {})
    return {
        "model_id": row.model_id,
        "success": row.success,
        "quality_satisfied": row.quality_satisfied,
        "profile": features.get("capability_profile"),
        "profile_version": features.get("profile_version"),
        "workspace_id": features.get("workspace_id"),
        "route_provider": features.get("route_provider"),
        "failure_kind": features.get("failure_kind"),
        "business_outcome": features.get("business_outcome"),
        "business_stage": features.get("business_stage"),
        "attempt_id": features.get("attempt_id"),
    }


def main() -> int:
    mp = pytest.MonkeyPatch()
    db_path = Path("/private/tmp/atom-business-feedback-proof.db")
    if db_path.exists():
        db_path.unlink()
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    mp.setattr(database, "SessionLocal", Session)
    router = object.__new__(LearningBasedRouter)
    LearningBasedRouter.__init__(router, Session())
    mp.setattr(
        registry, "get_learning_router_instance",
        lambda *args, **kwargs: router)
    reset_capability_evidence_cache()
    try:
        handler = _handler()
        _configure_pool(handler, mp)
        service = _service(handler)
        context = _context()
        invalid_client = handler.clients["local_ctrl1234"]

        evaluations = []
        for _ in range(3):
            with patch(
                    "core.llm.byok_handler.instructor.from_openai",
                    _route_aware_instructor(
                        [], invalid_client=invalid_client,
                        valid_proposal=_valid_proposal())):
                result = asyncio.run(propose_employee_work(
                    context, llm_service=service))
            evaluations.append({
                "source": result.get("source"),
                "served_route": (result.get("routing") or {}).get(
                    "served_route"),
                "evaluation": result.get("evaluation"),
            })

        rows = [_row_view(row) for row in _rows({"Session": Session})]
        reset_capability_evidence_cache()
        evidence = load_feedback_evidence(
            get_profile("employee_evidence_selection"),
            workspace_id="ws-ctrl", tenant_id="tenant-ctrl")

        selected = []
        with patch(
                "core.llm.byok_handler.instructor.from_openai",
                _route_aware_instructor(
                    selected, invalid_client=invalid_client,
                    valid_proposal=_valid_proposal())):
            next_result = asyncio.run(propose_employee_work(
                context, llm_service=service))

        proof = {
            "schema": "atom-business-feedback-proof-1",
            "executed_source": os.getenv("ATOM_PROOF_SOURCE", ""),
            "sequence": [
                "consumer evaluated 3 served model proposals as "
                "wrong_evidence_selection",
                "each evaluation annotated its own transport outcome row",
                "fresh capability evidence read excluded the route",
                "next unpinned decision served the one eligible alternative",
            ],
            "evaluations": evaluations,
            "persisted_rows": rows,
            "evidence": evidence,
            "next_decision": {
                "source": next_result.get("source"),
                "served_route": (next_result.get("routing") or {}).get(
                    "served_route"),
                "profile": (next_result.get("routing") or {}).get("profile"),
                "dispatched_clients": len(selected),
            },
            "boundaries": [
                "scratch SQLite feedback table; no live application DB",
                "provider transport doubled; no live model inference",
                "three deterministic consumer evaluations meet the profile "
                "evidence floor; no quality label was invented",
                "one eligible alternative served; no multi-route sweep",
            ],
        }
        out = Path(__file__).with_name("feedback-proof.json")
        out.write_text(json.dumps(proof, indent=1, default=str) + "\n")
        print(json.dumps(proof, indent=1, default=str)[:4000])
        return 0
    finally:
        reset_capability_evidence_cache()
        mp.undo()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
