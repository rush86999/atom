#!/usr/bin/env python3
"""Substantive assessment campaign — prepared, blocked until a model exists.

Phases (run in order; restart the backend between ``correct`` and
``after-restart``):

    preflight     check the declared review model/provider/key, write blocker
    create        create the canvas, bind unfamiliar grant records, assess
    correct       change the taught policy and re-assess the same records
    after-restart re-assess after a real backend restart; verify fresh provenance

This harness is intentionally not a mock-model acceptance. A phase refuses
unless the assessment response carries a real served provider/model and the
review contract certifies every subject. It never sends email or changes a
connected source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

ROWS = [
    ["A-201", 120, "Open", "Low", "North"],
    ["A-202", 80, "Open", "High", "South"],
    ["A-203", 200, "Closed", "Low", "North"],
    ["A-204", 95, "Open", "Low", "North"],
    ["A-205", 150, "Open", "High", "North"],
    ["A-206", 60, "Open", "High", "North"],
]
COLUMNS = ["Ref", "Amount", "Status", "Risk", "Region"]
SUBJECTS = [row[0] for row in ROWS]

POLICY_V1 = (
    "Approve Open records with Amount >= 100 and Risk Low. "
    "Review Open records with Amount 50-99 or Risk High. "
    "Deny Closed records. Exception: North region with Risk High requires "
    "Review even when Amount >= 100."
)
POLICY_V2 = (
    "Approve Open records with Amount >= 100 regardless of Risk. "
    "Review Open records with Amount 50-99. Deny Closed records. "
    "Exception: North region with Risk High requires Review even when "
    "Amount >= 100."
)
EXPECTED_V1 = {
    "A-201": "APPROVE", "A-202": "REVIEW", "A-203": "DENY",
    "A-204": "REVIEW", "A-205": "REVIEW", "A-206": "REVIEW",
}
EXPECTED_V2 = {
    "A-201": "APPROVE", "A-202": "REVIEW", "A-203": "DENY",
    "A-204": "REVIEW", "A-205": "REVIEW", "A-206": "REVIEW",
}
# Removing the North/High exception is the correction under test.
POLICY_V3 = (
    "Approve Open records with Amount >= 100 regardless of Risk. "
    "Review Open records with Amount 50-99. Deny Closed records."
)
EXPECTED_V3 = {
    "A-201": "APPROVE", "A-202": "REVIEW", "A-203": "DENY",
    "A-204": "REVIEW", "A-205": "APPROVE", "A-206": "REVIEW",
}


def _request(base: str, path: str, payload: Any = None, *, token: str = "",
             method: str = "") -> Any:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        base + path, data=data,
        method=method or ("POST" if data is not None else "GET"),
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        })
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.loads(response.read().decode() or "{}")


def _login(frontend: str, password_file: str) -> str:
    password = Path(password_file).read_text().strip()
    result = _request(frontend, "/api/auth/login", {
        "username": "admin@example.com", "password": password})
    return str(result["access_token"])


def _manifest(policy: str) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "base_component": "table",
        "operations": ["read", "select", "calculate", "assess", "edit",
                       "export", "bind"],
        "data_binding": {
            "subject_field": "Ref",
            "measure_field": "Amount",
            "status_field": "Status",
        },
        "editable_fields": ["Amount", "Status"],
        "teaching_binding": {
            "agent_id": "assessment-campaign",
            "scope_id": "grant-eligibility-campaign",
        },
        "decision_options": ["APPROVE", "REVIEW", "DENY"],
        "task_policy": policy,
        "outputs": ["xlsx"],
        "required_approvals": [],
    }


def _assess(frontend: str, token: str, canvas_id: str) -> Dict[str, Any]:
    return _request(
        frontend, f"/api/canvas/{canvas_id}/capability/assess",
        {"ask": "Assess every record under the taught policy. Cite the "
                "row evidence and policy."}, token=token)


def _decision_map(result: Dict[str, Any]) -> Dict[str, str]:
    return {
        str(item.get("subject_id")): str(item.get("decision"))
        for item in (result.get("assessments") or [])
        if isinstance(item, dict)
    }


def _require_certified(result: Dict[str, Any], expected: Dict[str, str],
                       label: str) -> None:
    if result.get("success") is not True or result.get("certified") is not True:
        raise SystemExit(
            f"{label}: assessment not certified: "
            f"{json.dumps(result.get('errors') or result)[:1200]}")
    route = result.get("route") or {}
    if not route.get("served_provider") or not route.get("served_model"):
        raise SystemExit(
            f"{label}: no real model provenance in route: {route}")
    actual = _decision_map(result)
    if actual != expected:
        raise SystemExit(
            f"{label}: decision mismatch; expected {expected}, got {actual}")
    if sorted(result.get("subjects") or []) != sorted(SUBJECTS):
        raise SystemExit(f"{label}: subject coverage mismatch")


def _preflight(out: Path) -> int:
    model = (os.getenv("ATOM_REVIEW_MODEL") or "").strip()
    provider = (os.getenv("ATOM_REVIEW_PROVIDER") or "").strip()
    local = (os.getenv("OLLAMA_BASE_URL") or "").strip()
    blockers: List[str] = []
    if not model:
        blockers.append("ATOM_REVIEW_MODEL is not set")
    if not provider:
        blockers.append("ATOM_REVIEW_PROVIDER is not set")
    if provider and provider != "ollama":
        key_env = f"{provider.upper()}_API_KEY"
        if not (os.getenv(key_env) or "").strip():
            blockers.append(f"{key_env} is empty")
    if provider == "ollama" and not local:
        blockers.append("OLLAMA_BASE_URL is not set")
    payload = {
        "schema": "atom-substantive-assessment-preflight-1",
        "status": "blocked_external" if blockers else "ready",
        "review_model": model,
        "review_provider": provider,
        "blockers": blockers,
        "smallest_required_input": (
            "A funded provider key with the declared review model, or a "
            "readable local Ollama model store."),
        "records": SUBJECTS,
        "policy_v1": POLICY_V1,
        "expected_v1": EXPECTED_V1,
        "policy_v3": POLICY_V3,
        "expected_v3": EXPECTED_V3,
    }
    (out / "preflight.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    return 0 if not blockers else 3


def _create(frontend: str, token: str, out: Path) -> int:
    canvas = _request(frontend, "/api/canvas", {
        "title": "Grant eligibility substantive assessment",
        "description": "Unfamiliar grant records under a taught policy.",
        "canvas_type": "sheet",
    }, token=token)
    canvas_id = str(canvas.get("canvas_id") or canvas.get("id"))
    if not canvas_id:
        raise SystemExit(f"canvas create returned no id: {canvas}")
    _request(frontend, f"/api/canvas/{canvas_id}/capability/manifest",
             {"manifest": _manifest(POLICY_V1)}, token=token, method="PUT")
    _request(frontend, f"/api/canvas/{canvas_id}/capability/bind-json", {
        "columns": COLUMNS, "rows": ROWS,
        "source": {"file_name": "grant_eligibility_20261031.csv"},
        "title": "Grant eligibility 2026-10-31",
    }, token=token)
    result = _assess(frontend, token, canvas_id)
    _require_certified(result, EXPECTED_V1, "create")
    state = {
        "schema": "atom-substantive-assessment-state-1",
        "canvas_id": canvas_id,
        "subjects": SUBJECTS,
        "policy_v1": POLICY_V1,
        "expected_v1": EXPECTED_V1,
        "policy_v3": POLICY_V3,
        "expected_v3": EXPECTED_V3,
        "v1": result,
        "v1_route": result.get("route"),
        "v1_policy_revision": result.get("policy_revision"),
    }
    (out / "state.json").write_text(json.dumps(state, indent=2) + "\n")
    (out / "create.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": "passed", "phase": "create",
                      "canvas_id": canvas_id,
                      "route": result.get("route")}, indent=2))
    return 0


def _correct(frontend: str, token: str, out: Path, state_path: str) -> int:
    state = json.loads(Path(state_path).read_text())
    canvas_id = state["canvas_id"]
    _request(frontend, f"/api/canvas/{canvas_id}/capability/manifest",
             {"manifest": _manifest(POLICY_V3)}, token=token, method="PUT")
    result = _assess(frontend, token, canvas_id)
    _require_certified(result, EXPECTED_V3, "correct")
    if result.get("policy_revision") == state.get("v1_policy_revision"):
        raise SystemExit("correct: policy revision did not change")
    state["v3"] = result
    state["v3_route"] = result.get("route")
    state["v3_policy_revision"] = result.get("policy_revision")
    (out / "state.json").write_text(json.dumps(state, indent=2) + "\n")
    (out / "correct.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": "passed", "phase": "correct",
                      "route": result.get("route"),
                      "decisions": _decision_map(result)}, indent=2))
    return 0


def _after_restart(frontend: str, token: str, out: Path,
                   state_path: str) -> int:
    state = json.loads(Path(state_path).read_text())
    result = _assess(frontend, token, state["canvas_id"])
    _require_certified(result, EXPECTED_V3, "after-restart")
    route = result.get("route") or {}
    if route.get("served_provider") != state.get("v3_route", {}).get(
            "served_provider"):
        raise SystemExit("after-restart: served provider changed")
    (out / "after-restart.json").write_text(
        json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": "passed", "phase": "after-restart",
                      "route": route, "decisions": _decision_map(result)},
                     indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True,
                    choices=["preflight", "create", "correct", "after-restart"])
    ap.add_argument("--frontend", default="http://127.0.0.1:3130")
    ap.add_argument("--password-file", default="")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--state", default="")
    args = ap.parse_args()
    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.phase == "preflight":
        return _preflight(out)
    if not args.password_file:
        raise SystemExit("--password-file is required for assessment phases")
    token = _login(args.frontend, args.password_file)
    if args.phase == "create":
        return _create(args.frontend, token, out)
    if not args.state:
        raise SystemExit("--state is required for this phase")
    if args.phase == "correct":
        return _correct(args.frontend, token, out, args.state)
    return _after_restart(args.frontend, token, out, args.state)


if __name__ == "__main__":
    raise SystemExit(main())
