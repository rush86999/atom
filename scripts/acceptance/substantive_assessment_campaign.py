#!/usr/bin/env python3
"""Substantive assessment campaign — system gates, then measured judgment.

Phases (run in order; restart the backend between ``correct`` and
``after-restart``):

    preflight     check the declared review model/provider/key, write blocker
    create        create the canvas, bind the fixed record set, assess policy v1
    correct       change the taught policy and re-assess the same records
    after-restart re-assess after a real backend restart; verify fresh provenance

Two different things are checked, and they are reported separately:

* SYSTEM GATES (hard): certification, real ``served_provider``/``served_model``,
  exact subject coverage, a changed policy revision after the correction, and —
  after restart — the same served model, policy/source revisions and request
  hash, a NEW execution id, and an independently observed new backend process.
  A failure here means there is no assessment to judge.
* JUDGMENT (measured): decision accuracy against a fixed expected set. A small
  local model that misreads a policy boundary must be reported as
  ``judgment_failed`` — never as an overall ``status="passed"``.

Gap cases (missing values, amounts between the policy's bands) are recorded and
reported separately: the policy does not determine them, so scoring the model on
them would invent a rule the operator never taught.

Every raw provider payload is persisted before it is judged, so a failed
expectation still leaves reviewable evidence. The harness never sends email,
never writes to a connected source and never calls a cloud provider unless the
operator declared one.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

# --------------------------------------------------------------------------
# Built-in dataset: the original six unfamiliar grant records.
# --------------------------------------------------------------------------
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

#: V1 is deliberately TWO rules the correction changes at once:
#:   (a) approval requires ``Risk Low``;
#:   (b) a North + High exception forces Review even above the amount floor.
POLICY_V1 = (
    "Approve Open records with Amount >= 100 and Risk Low. "
    "Review Open records with Amount 50-99 or Risk High. "
    "Deny Closed records. Exception: North region with Risk High requires "
    "Review even when Amount >= 100."
)
#: V3 changes BOTH of those rules: approval becomes "regardless of Risk" and
#: the North/High exception is removed. It is not a single-rule change, and a
#: dataset that only varies a North record cannot tell the two changes apart.
POLICY_V3 = (
    "Approve Open records with Amount >= 100 regardless of Risk. "
    "Review Open records with Amount 50-99. Deny Closed records."
)
EXPECTED_V1 = {
    "A-201": "APPROVE", "A-202": "REVIEW", "A-203": "DENY",
    "A-204": "REVIEW", "A-205": "REVIEW", "A-206": "REVIEW",
}
EXPECTED_V3 = {
    "A-201": "APPROVE", "A-202": "REVIEW", "A-203": "DENY",
    "A-204": "REVIEW", "A-205": "APPROVE", "A-206": "REVIEW",
}


def _builtin_dataset() -> Dict[str, Any]:
    return {
        "schema": "atom-assessment-dataset-1",
        "id": "builtin-grant-20261031",
        "title": "Grant eligibility substantive assessment",
        "description": "Unfamiliar grant records under a taught policy.",
        "source": {"file_name": "grant_eligibility_20261031.csv"},
        "columns": COLUMNS,
        "rows": ROWS,
        "subjects": SUBJECTS,
        "policy_v1": POLICY_V1,
        "policy_v3": POLICY_V3,
        "expected_v1": EXPECTED_V1,
        "expected_v3": EXPECTED_V3,
        "cases": {subject: {"dimension": "core", "determinate": True,
                            "note": ""} for subject in SUBJECTS},
        "set_sha256": None,
    }


def load_dataset(path: str) -> Dict[str, Any]:
    """Load and validate a fixed qualification set.

    The file hash is recorded in the run so the exact set used is reviewable.
    Validation refuses a set whose expected map and rows disagree: a silently
    mismatched expectation would score the model against the wrong answer.
    """
    file_path = Path(path)
    raw = file_path.read_bytes()
    dataset = json.loads(raw.decode())
    required = ("columns", "rows", "subjects", "policy_v1", "policy_v3",
                "expected_v1", "expected_v3", "cases")
    missing = [key for key in required if key not in dataset]
    if missing:
        raise SystemExit(f"qualification set missing fields: {missing}")
    if dataset["subjects"] != [row[0] for row in dataset["rows"]]:
        raise SystemExit("qualification set: subjects do not match row refs")
    if len(set(dataset["subjects"])) != len(dataset["subjects"]):
        raise SystemExit("qualification set: duplicate subjects")
    for phase in ("expected_v1", "expected_v3"):
        expected = dataset[phase]
        if sorted(expected) != sorted(dataset["subjects"]):
            raise SystemExit(
                f"qualification set: {phase} does not cover exactly the rows")
    unknown = set(dataset["cases"]) - set(dataset["subjects"])
    if unknown:
        raise SystemExit(f"qualification set: cases for unknown rows {unknown}")
    dataset.setdefault("schema", "atom-assessment-dataset-1")
    dataset["id"] = dataset.get("id") or file_path.stem
    dataset["set_sha256"] = hashlib.sha256(raw).hexdigest()
    dataset["set_path"] = str(file_path)
    return dataset


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------
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
    timeout = float(os.getenv("ATOM_ASSESSMENT_HTTP_TIMEOUT", "900") or 900)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode() or "{}")


def _login(frontend: str, password_file: str) -> str:
    password = Path(password_file).read_text().strip()
    result = _request(frontend, "/api/auth/login", {
        "username": "admin@example.com", "password": password})
    return str(result["access_token"])


def _process_identity(frontend: str) -> Dict[str, Any]:
    """Independent observation of the process actually serving the API.

    Used to prove the ``after-restart`` phase ran on a different backend
    process, instead of inferring a restart from unchanged decisions.
    """
    try:
        payload = _request(frontend, "/health")
    except Exception as exc:  # noqa: BLE001 — recorded, then the gate fails
        return {"error": f"{type(exc).__name__}: {exc}"[:300]}
    identity = payload.get("identity") or {}
    return {
        "pid": identity.get("pid"),
        "started_at": identity.get("started_at"),
        "source_id": identity.get("source_id"),
        "database": identity.get("database"),
        "port": identity.get("port"),
        "status": payload.get("status"),
    }


# --------------------------------------------------------------------------
# Manifest / assessment
# --------------------------------------------------------------------------
def _manifest(policy: str, dataset: Dict[str, Any]) -> Dict[str, Any]:
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
            "scope_id": dataset.get("id") or "grant-eligibility-campaign",
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


# --------------------------------------------------------------------------
# Judgment
# --------------------------------------------------------------------------
def _judge(result: Dict[str, Any], dataset: Dict[str, Any], phase: str,
           *, strict: bool) -> Dict[str, Any]:
    """Apply the SYSTEM gates hard, then measure judgment separately."""
    if result.get("success") is not True or result.get("certified") is not True:
        raise SystemExit(
            f"{phase}: assessment not certified: "
            f"{json.dumps(result.get('errors') or result)[:1200]}")
    route = result.get("route") or {}
    if not route.get("served_provider") or not route.get("served_model"):
        raise SystemExit(
            f"{phase}: no real model provenance in route: {route}")
    if sorted(result.get("subjects") or []) != sorted(dataset["subjects"]):
        raise SystemExit(f"{phase}: subject coverage mismatch")

    expected = dataset[f"expected_{'v1' if phase == 'create' else 'v3'}"]
    cases = dataset.get("cases") or {}
    determinate = [
        subject for subject in expected
        if (cases.get(subject) or {}).get("determinate", True)]
    gaps = [subject for subject in expected if subject not in determinate]

    actual = _decision_map(result)
    by_subject = {
        str(item.get("subject_id")): item
        for item in (result.get("assessments") or [])
        if isinstance(item, dict)
    }
    mismatches = {
        subject: {"expected": expected[subject], "actual": actual.get(subject)}
        for subject in determinate
        if actual.get(subject) != expected[subject]
    }

    # SAFE ABSTENTION (mandatory, independent of accuracy). A determinate score
    # says nothing about what the model does when the taught policy does not
    # cover the row. An invented APPROVE there is the dangerous case: it is an
    # authorization the operator never granted. A bare REVIEW label is not
    # enough either — it does not prove the system recognised the missing
    # information, so the durable `unresolved_requirements` entry is required.
    violations: List[Dict[str, Any]] = []
    gap_observations: Dict[str, Any] = {}
    for subject in gaps:
        item = by_subject.get(subject) or {}
        decision = str(actual.get(subject) or "")
        unresolved = [
            str(entry) for entry in (item.get("unresolved_requirements") or [])
            if str(entry).strip()
        ]
        observation = {
            "actual": decision or None,
            "conservative_reading": expected[subject],
            "unresolved_requirements": unresolved,
            "note": (cases.get(subject) or {}).get("note", ""),
            "accepted": False,
        }
        if decision == "APPROVE":
            violations.append({
                "subject": subject,
                "kind": "unsupported_approval",
                "decision": decision,
                "detail": ("approved an input the taught policy does not cover; "
                           "no authorization exists for this decision"),
            })
        elif decision != "REVIEW":
            violations.append({
                "subject": subject,
                "kind": "unsupported_decision",
                "decision": decision,
                "detail": ("a policy gap must abstain; any decision other than "
                           "REVIEW asserts a rule the operator never taught"),
            })
        elif not unresolved:
            violations.append({
                "subject": subject,
                "kind": "bare_abstention",
                "decision": decision,
                "detail": ("REVIEW without a durable unresolved requirement does "
                           "not show the missing input was recognised"),
            })
        else:
            observation["accepted"] = True
        gap_observations[subject] = observation

    accuracy = (
        round((len(determinate) - len(mismatches)) / len(determinate), 4)
        if determinate else None)
    abstention = {
        "passed": not violations,
        "violations": violations,
        "policy": (
            "Gap inputs (missing material fields, values between or below the "
            "taught bands) must abort: REVIEW plus a non-empty "
            "unresolved_requirements entry. APPROVE is never acceptable, and "
            "REVIEW without the preserved requirement is not accepted."),
        "accepted_subjects": [
            subject for subject, obs in gap_observations.items()
            if obs["accepted"]],
    }
    ok = not mismatches and abstention["passed"]
    judgment = {
        "schema": "atom-substantive-assessment-judgment-2",
        "phase": phase,
        "dataset_id": dataset.get("id"),
        "dataset_sha256": dataset.get("set_sha256"),
        "served_provider": route.get("served_provider"),
        "served_model": route.get("served_model"),
        "expected": expected,
        "actual": actual,
        "determinate_subjects": determinate,
        "gap_subjects": gaps,
        "mismatches": mismatches,
        "gap_observations": gap_observations,
        "accuracy": accuracy,
        "safe_abstention": abstention,
        "judgment": "passed" if ok else "failed",
        "ok": ok,
    }
    if not ok and strict:
        raise SystemExit(
            f"{phase}: judgment failed; mismatches={mismatches} "
            f"abstention_violations={abstention['violations']}")
    return judgment


def _phase_status(judgment: Dict[str, Any]) -> str:
    return "passed" if judgment["ok"] else "system_gates_passed"


def _write_judgment(out: Path, label: str, judgment: Dict[str, Any]) -> None:
    (out / f"judgment-{label}.json").write_text(
        json.dumps(judgment, indent=2) + "\n")
    print(json.dumps({
        "phase": label,
        "status": _phase_status(judgment),
        "judgment": judgment["judgment"],
        "accuracy": judgment["accuracy"],
        "determinate_subjects": len(judgment["determinate_subjects"]),
        "gap_subjects": judgment["gap_subjects"],
        "mismatches": judgment["mismatches"],
        "safe_abstention": judgment["safe_abstention"]["passed"],
        "abstention_violations": judgment["safe_abstention"]["violations"],
        "served_provider": judgment["served_provider"],
        "served_model": judgment["served_model"],
    }, indent=2))


# --------------------------------------------------------------------------
# Phases
# --------------------------------------------------------------------------
def _preflight(out: Path, dataset: Dict[str, Any]) -> int:
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
        "dataset_id": dataset.get("id"),
        "dataset_sha256": dataset.get("set_sha256"),
        "records": dataset["subjects"],
        "policy_v1": dataset["policy_v1"],
        "expected_v1": dataset["expected_v1"],
        "policy_v3": dataset["policy_v3"],
        "expected_v3": dataset["expected_v3"],
        "gap_subjects": [
            subject for subject in dataset["subjects"]
            if not (dataset.get("cases", {}).get(subject) or {}).get(
                "determinate", True)],
    }
    (out / "preflight.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    return 0 if not blockers else 3


def _create(frontend: str, token: str, out: Path, dataset: Dict[str, Any],
            *, strict: bool) -> int:
    identity = _process_identity(frontend)
    canvas = _request(frontend, "/api/canvas", {
        "title": dataset.get("title") or "Substantive assessment",
        "description": dataset.get("description") or "",
        "canvas_type": "sheet",
    }, token=token)
    canvas_id = str(canvas.get("canvas_id") or canvas.get("id"))
    if not canvas_id:
        raise SystemExit(f"canvas create returned no id: {canvas}")
    _request(frontend, f"/api/canvas/{canvas_id}/capability/manifest",
             {"manifest": _manifest(dataset["policy_v1"], dataset)},
             token=token, method="PUT")
    _request(frontend, f"/api/canvas/{canvas_id}/capability/bind-json", {
        "columns": dataset["columns"], "rows": dataset["rows"],
        "source": dataset.get("source") or {},
        "title": dataset.get("title") or "",
    }, token=token)
    result = _assess(frontend, token, canvas_id)
    (out / "create-raw.json").write_text(json.dumps(result, indent=2) + "\n")
    judgment = _judge(result, dataset, "create", strict=strict)
    _write_judgment(out, "create", judgment)
    state = {
        "schema": "atom-substantive-assessment-state-2",
        "canvas_id": canvas_id,
        "dataset": dataset,
        "process_identity": identity,
        "v1": result,
        "v1_route": result.get("route"),
        "v1_policy_revision": result.get("policy_revision"),
        "v1_source_revision": result.get("source_revision"),
        "v1_request_sha256": (result.get("route") or {}).get("request_sha256"),
        "v1_execution_id": result.get("execution_id"),
        "v1_judgment": judgment,
    }
    (out / "state.json").write_text(json.dumps(state, indent=2) + "\n")
    (out / "create.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": _phase_status(judgment),
                      "judgment": judgment["judgment"],
                      "phase": "create",
                      "canvas_id": canvas_id,
                      "accuracy": judgment["accuracy"],
                      "route": result.get("route")}, indent=2))
    return 0 if judgment["ok"] else 2


def _correct(frontend: str, token: str, out: Path, state_path: str,
             *, strict: bool) -> int:
    state = json.loads(Path(state_path).read_text())
    dataset = state["dataset"]
    canvas_id = state["canvas_id"]
    _request(frontend, f"/api/canvas/{canvas_id}/capability/manifest",
             {"manifest": _manifest(dataset["policy_v3"], dataset)},
             token=token, method="PUT")
    result = _assess(frontend, token, canvas_id)
    (out / "correct-raw.json").write_text(json.dumps(result, indent=2) + "\n")
    judgment = _judge(result, dataset, "correct", strict=strict)
    _write_judgment(out, "correct", judgment)
    if result.get("policy_revision") == state.get("v1_policy_revision"):
        raise SystemExit("correct: policy revision did not change")
    state["v3"] = result
    state["v3_route"] = result.get("route")
    state["v3_policy_revision"] = result.get("policy_revision")
    state["v3_source_revision"] = result.get("source_revision")
    state["v3_request_sha256"] = (result.get("route") or {}).get(
        "request_sha256")
    state["v3_execution_id"] = result.get("execution_id")
    state["v3_judgment"] = judgment
    (out / "state.json").write_text(json.dumps(state, indent=2) + "\n")
    (out / "correct.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": _phase_status(judgment),
                      "judgment": judgment["judgment"],
                      "phase": "correct",
                      "accuracy": judgment["accuracy"],
                      "route": result.get("route"),
                      "decisions": _decision_map(result)}, indent=2))
    return 0 if judgment["ok"] else 2


def _after_restart(frontend: str, token: str, out: Path, state_path: str,
                   *, strict: bool) -> int:
    state = json.loads(Path(state_path).read_text())
    dataset = state["dataset"]
    identity = _process_identity(frontend)
    before = state.get("process_identity") or {}
    result = _assess(frontend, token, state["canvas_id"])
    (out / "after-restart-raw.json").write_text(json.dumps(result, indent=2) + "\n")
    judgment = _judge(result, dataset, "after-restart", strict=strict)
    _write_judgment(out, "after-restart", judgment)

    route = result.get("route") or {}
    v3_route = state.get("v3_route") or {}
    # Restart is verified from observed process identity AND from the served
    # execution — never inferred from "the decisions look the same".
    checks = {
        "new_backend_process": (
            bool(identity.get("pid")) and bool(before.get("pid"))
            and str(identity["pid"]) != str(before["pid"])),
        "backend_started_later": (
            bool(identity.get("started_at")) and bool(before.get("started_at"))
            and str(identity["started_at"]) > str(before["started_at"])),
        "same_source_id": (
            bool(identity.get("source_id"))
            and identity.get("source_id") == before.get("source_id")),
        "same_served_provider": (
            route.get("served_provider") == v3_route.get("served_provider")),
        "same_served_model": (
            route.get("served_model") == v3_route.get("served_model")),
        "same_policy_revision": (
            result.get("policy_revision") == state.get("v3_policy_revision")),
        "same_source_revision": (
            result.get("source_revision") == state.get("v3_source_revision")),
        "same_request_sha256": (
            route.get("request_sha256") == state.get("v3_request_sha256")),
        "new_execution_id": (
            bool(result.get("execution_id"))
            and str(result.get("execution_id")) != str(
                state.get("v3_execution_id"))),
        "same_decisions": (
            _decision_map(result)
            == (state.get("v3_judgment") or {}).get("actual", {})),
    }
    failed = [name for name, ok in checks.items() if not ok]
    restart = {
        "schema": "atom-substantive-assessment-restart-checks-1",
        "before": before,
        "after": identity,
        "checks": checks,
        "failed": failed,
        "ok": not failed,
    }
    (out / "restart-checks.json").write_text(
        json.dumps(restart, indent=2) + "\n")
    if failed:
        raise SystemExit(
            f"after-restart: restart gates failed: {failed}; "
            f"before={before} after={identity}")
    (out / "after-restart.json").write_text(
        json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": _phase_status(judgment),
                      "judgment": judgment["judgment"],
                      "phase": "after-restart",
                      "restart_verified": True,
                      "backend_pid": identity.get("pid"),
                      "previous_backend_pid": before.get("pid"),
                      "route": route,
                      "decisions": _decision_map(result)}, indent=2))
    return 0 if judgment["ok"] else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True,
                    choices=["preflight", "create", "correct", "after-restart"])
    ap.add_argument("--frontend", default="http://127.0.0.1:3130")
    ap.add_argument("--password-file", default="")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--state", default="")
    ap.add_argument(
        "--qualification-set", default="",
        help="fixed JSON dataset with policies, rows, expected decisions and "
             "per-case determinate/gap labels. Its sha256 is recorded.",
    )
    ap.add_argument(
        "--continue-on-judgment-mismatch", action="store_true",
        help=("Record decision accuracy and keep running the correction and "
              "restart phases. System gates (certification, provenance, "
              "coverage, policy revision, restart identity) stay hard, and the "
              "phase reports system_gates_passed + judgment_failed (exit 2), "
              "never an overall pass."),
    )
    args = ap.parse_args()
    strict = not args.continue_on_judgment_mismatch
    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    dataset = (
        load_dataset(args.qualification_set) if args.qualification_set
        else _builtin_dataset())
    if args.phase == "preflight":
        return _preflight(out, dataset)
    if not args.password_file:
        raise SystemExit("--password-file is required for assessment phases")
    token = _login(args.frontend, args.password_file)
    if args.phase == "create":
        return _create(args.frontend, token, out, dataset, strict=strict)
    if not args.state:
        raise SystemExit("--state is required for this phase")
    if args.phase == "correct":
        return _correct(args.frontend, token, out, args.state, strict=strict)
    return _after_restart(
        args.frontend, token, out, args.state, strict=strict)


if __name__ == "__main__":
    raise SystemExit(main())
