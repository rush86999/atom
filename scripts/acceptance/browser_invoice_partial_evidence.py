#!/usr/bin/env python3
"""Signed-in browser verification for incomplete invoice evidence.

The fixture is the same partial invoice used by
``backend/tests/test_task_wait_source_continuation_regressions.py``:

* purchase order ``PO-TRIGGER-63`` (3 x 42.50, freight 12.75)
* receiving record (3 received)
* invoice ``INV-TRIGGER-91`` with **no unit price** -> incomplete evidence
* the same invoice with unit price 42.50 -> complete evidence, total 140.25

``--execute`` runs one ordinary signed-in episode in a fresh isolated scratch
world, with the existing ``run_isolated`` launcher, the existing loopback
``provider_shim`` and the real ``next dev`` frontend copy:

  login -> create the objective from the two known procurement sources ->
  durable "which source contains the invoice?" question -> upload the partial
  invoice through the Assignments panel and select it -> the obligation stays
  open and no reconciliation exists -> upload the complete invoice through the
  same panel and select it -> exactly one verified ``invoice.reconcile`` result
  of 140.25 and a completed assignment.

Each upload is observed against the identity the mounted browser action
actually returned (document id, filename, extraction revision and the canonical
``office/uploads`` path), never against the fixture path handed to the file
input. Both uploads must match their own identity; a missing field or a fixture
path fails closed.

Only provider responses are authored (SIMULATED MODEL DECISIONS / CONTROLLED
TRANSPORT). Routing, source reads, the structured consumer, wait settlement,
the compiler/executor, reconciliation and durable persistence all run in
production code. No external provider credential, account, send or spend is
used.

The signed-in leg drives the real login form with the run-scoped admin
credential. The isolated frontend copy receives its own per-launch
``NEXTAUTH_SECRET`` so the installed NextAuth credentials provider can
establish the web session, and the driver proves both ``/api/auth/session``
and the backend ``/api/auth/me`` before continuing. No token or cookie is
seeded by the harness.

The default ``--preflight`` path validates the partial/complete fixture and the
authored loopback completions without creating a world or launching anything.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

FIXTURE = Path(__file__).with_name("fixtures") / (
    "browser_invoice_partial_evidence_shim.json")

PO = "PO-TRIGGER-63"
INVOICE = "INV-TRIGGER-91"
EXPECTED_TOTAL = "140.25"
OBJECTIVE = f"Reconcile invoice {INVOICE} for {PO}"
ADMIN_EMAIL = "admin@example.com"
PARTIAL_NAME = "invoice-partial.json"
COMPLETE_NAME = "invoice-complete.json"
SHIM_DEFAULT_LABEL = (
    "SIMULATED CONTROL TRANSPORT: no authored completion matched this request."
)
#: Complete-evidence continuations have two wire shapes: the compact
#: single-ready prompt carries ``allowed_step_ids``; the full follow-up prompt
#: carries the ready operation itself. The invoice_patch_MqoAP4 capture used
#: the full shape (2 follow-up requests, neither naming allowed_step_ids), so
#: a readiness discriminator is required in addition to the compact one.
COMPLETE_EVIDENCE_MATCHES = (
    "allowed_step_ids",
    '"ready_operations": ["invoice_reconciliation"]',
)


def _is_complete_evidence_match(match: str) -> bool:
    return any(token in match for token in COMPLETE_EVIDENCE_MATCHES)

LABELS = {
    "model_decisions": (
        "SIMULATED MODEL DECISIONS: authored JSON completions served by the "
        "existing loopback provider shim. Not served-model output."),
    "transport": (
        "CONTROLLED TRANSPORT: only the provider response is substituted; "
        "source upload/read, the structured consumer, wait settlement, "
        "invoice reconciliation, verification and persistence run in "
        "production code."),
    "web_auth": (
        "REAL CREDENTIAL SIGN-IN: the login form posts the run-scoped admin "
        "password to the backend; the isolated frontend copy mints its own "
        "per-run NEXTAUTH_SECRET so the installed NextAuth provider can "
        "establish the web session. The harness never seeds a token or "
        "cookie, and proves both /api/auth/session and the backend "
        "/api/auth/me after sign-in."),
    "not_claimed": [
        "served model or provider quality",
        "general model judgment or prompt quality",
        "a live provider, account, credential, send, spend or download",
        "a synthetic completed row or a hand-authored reconciliation result",
    ],
}


def _load_d3():
    path = REPO / "scripts" / "acceptance" / "browser_agent_job_wait.py"
    spec = importlib.util.spec_from_file_location(
        "browser_agent_job_wait_for_invoice", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D3 = _load_d3()


class PreflightError(RuntimeError):
    pass


class DriverError(RuntimeError):
    pass


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=False, default=str) + "\n",
        encoding="utf-8")


def _world_path(name: str) -> Path:
    """Resolve the world under the guard's configured (anchored) root."""
    try:
        from core.world_storage_guard import load_config

        root = load_config().root
    except Exception:  # noqa: BLE001 - canonical fallback is still guarded
        root = BACKEND / "data" / "acceptance_worlds"
    return Path(root) / name


def _facts(*, complete_invoice: bool = False) -> Dict[str, Dict[str, Any]]:
    invoice = {
        "po_id": PO, "invoice_id": INVOICE, "quantity": "3",
        "unit_price": "42.50" if complete_invoice else None,
        "freight": "12.75", "currency": "USD",
    }
    return {
        "po.json": {
            "po_id": PO, "vendor_id": "V-6", "quantity": "3",
            "unit_price": "42.50", "freight": "12.75", "currency": "USD",
        },
        "receiving.json": {"po_id": PO, "received_quantity": "3"},
        "invoice.json": invoice,
    }


def _write_fixture_files(root: Path) -> Dict[str, Any]:
    """Write the controlled facts, including the partial invoice variant."""
    root.mkdir(parents=True, exist_ok=True)
    complete = _facts(complete_invoice=True)
    partial = _facts(complete_invoice=False)
    for name in ("po.json", "receiving.json"):
        (root / name).write_text(json.dumps(complete[name]), encoding="utf-8")
    (root / PARTIAL_NAME).write_text(
        json.dumps(partial["invoice.json"]), encoding="utf-8")
    (root / COMPLETE_NAME).write_text(
        json.dumps(complete["invoice.json"]), encoding="utf-8")
    return {
        "root": str(root),
        "partial": {"name": PARTIAL_NAME, **partial["invoice.json"]},
        "complete": {"name": COMPLETE_NAME, **complete["invoice.json"]},
        "po": complete["po.json"],
        "receiving": complete["receiving.json"],
        "expected_total": EXPECTED_TOTAL,
    }


def _shim_doc() -> Dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _validate_shim() -> Dict[str, Any]:
    """Validate every authored completion against the real consumer schemas."""
    from core.employee_adaptation import WorkAdaptationProposal
    from core.employee_proposal import EmployeeWorkProposal
    from scripts.orchestration_acceptance import provider_shim

    doc = _shim_doc()
    if SHIM_DEFAULT_LABEL not in str(doc.get("default") or ""):
        raise PreflightError("shim default is not labelled as simulated")
    responses = doc.get("responses")
    if not isinstance(responses, list) or len(responses) != 5:
        raise PreflightError("shim must author exactly five state responses")
    parsed: List[Dict[str, Any]] = []
    for index, entry in enumerate(responses):
        raw = entry.get("response")
        if not isinstance(raw, str):
            raise PreflightError(f"response[{index}] must be JSON text")
        payload = json.loads(raw)
        match = str(entry.get("match") or "")
        if _is_complete_evidence_match(match):
            model = WorkAdaptationProposal.model_validate(payload)
            model_name = type(model).__name__
            if model.decision != "replan" or not model.work_request:
                raise PreflightError("complete-evidence response is not a replan")
            if model.work_request.operation != "invoice_reconciliation":
                raise PreflightError("complete-evidence response wrong operation")
        elif "You choose one bounded next response" in match:
            model = None
            model_name = "CompactWaitChoiceProposal"
            if payload.get("decision") != "clarify":
                raise PreflightError(
                    "compact incomplete-evidence response must clarify")
            if INVOICE not in str(payload.get("clarification_question") or ""):
                raise PreflightError(
                    "compact incomplete-evidence question does not name invoice")
            if payload.get("clarification_missing_roles") != ["invoice"]:
                raise PreflightError(
                    "compact incomplete-evidence question is not scoped")
        elif "missing_prerequisites" in match:
            model = WorkAdaptationProposal.model_validate(payload)
            model_name = type(model).__name__
            if model.decision != "clarify" or not model.clarification:
                raise PreflightError(
                    "incomplete-evidence response must ask for the invoice")
            if INVOICE not in model.clarification.question:
                raise PreflightError(
                    "incomplete-evidence question does not name the invoice")
            if list(model.clarification.missing_roles) != ["invoice"]:
                raise PreflightError(
                    "incomplete-evidence question is not scoped to invoice")
        elif "planning reasoner" in match:
            model = EmployeeWorkProposal.model_validate(payload)
            model_name = type(model).__name__
            if model.proposal_kind != "evidence_read":
                raise PreflightError("discovery response must read evidence")
            handles = [read.source_id for read in model.evidence_reads]
            if handles != ["fixture:po.json", "fixture:receiving.json"]:
                raise PreflightError(f"unexpected discovery handles: {handles}")
        else:
            raise PreflightError(f"unrecognised match on response[{index}]")
        parsed.append({"match": match, "model": model_name,
                       "payload": payload})
    with tempfile.TemporaryDirectory(prefix="invoice-shim-") as tmp:
        path = Path(tmp) / "shim.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        index = provider_shim.load_script(path)
    if len(index) != len(responses):
        raise PreflightError(
            f"provider_shim indexed {len(index)} keys for {len(responses)} responses")
    return {
        "fixture": str(FIXTURE),
        "responses": parsed,
        "provider_shim_keys": [str(key) for key in index],
        "state_selection": (
            "prompt discriminators: 'planning reasoner' -> initial evidence "
            "reads; compact wait-choice prompt + 'missing_prerequisites' -> one "
            "targeted invoice question; complete evidence -> typed invoice "
            "reconciliation, matched by 'allowed_step_ids' on the compact "
            "continuation or by a ready invoice_reconciliation operation on "
            "the full follow-up prompt"),
    }


def _run_preflight(args: argparse.Namespace) -> int:
    scratch = Path(tempfile.mkdtemp(prefix="atom-invoice-preflight-"))
    (scratch / "data").mkdir()
    (scratch / "office").mkdir()
    os.environ.update({
        "TESTING": "1",
        "DATABASE_URL": f"sqlite:///{scratch / 'preflight.db'}",
        "ATOM_DATA_DIR": str(scratch / "data"),
        "ATOM_OFFICE_DIR": str(scratch / "office"),
    })
    fixture = _write_fixture_files(scratch / "fixtures")
    partial = fixture["partial"]
    complete = fixture["complete"]
    problems: List[str] = []
    if partial.get("unit_price") is not None:
        problems.append("partial fixture unexpectedly has a unit price")
    if complete.get("unit_price") != "42.50":
        problems.append("complete fixture unit price is not 42.50")
    computed = (3 * 42.50) + 12.75
    if f"{computed:.2f}" != EXPECTED_TOTAL:
        problems.append(f"expected total mismatch: {computed:.2f}")
    if problems:
        raise PreflightError("; ".join(problems))
    schema = _validate_shim()
    report = {
        "kind": "browser_invoice_partial_evidence_preflight",
        "ok": True,
        "at": _now(),
        "labels": LABELS,
        "fixture": fixture,
        "partial_missing_unit_price": True,
        "expected_total": EXPECTED_TOTAL,
        "shim": schema,
        "world_created": False,
        "browser_launched": False,
        "provider_contacted": False,
        "storage_guard": (
            "not invoked by --preflight; --execute calls "
            "core.world_storage_guard.require_storage_ready before build"),
    }
    if args.out:
        _write_json(Path(args.out) / "preflight.json", report)
    print(json.dumps(report, indent=2, default=str))
    return 0


def _durable_assignment(db_path: Path, run_id: str) -> Dict[str, Any]:
    """The durable task record the driver observes, read-only.

    ``task_lifecycle`` persists ``assignment`` and ``task_revision`` as
    SIBLINGS; the revision (which owns ``unresolved``) is never nested in
    the assignment. Project the sibling onto the returned record so
    ``_open_questions`` reads the same authoritative revision the backend
    does (run3 SQLite: one open entry lived only under
    ``task_lifecycle.task_revision``, so an assignment-only read saw none).
    """
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = con.execute(
            "select parameters from goal_runs where id=?", (run_id,)).fetchone()
    finally:
        con.close()
    if row is None:
        return {}
    params = json.loads(row[0] or "{}")
    lifecycle = params.get("task_lifecycle") or {}
    assignment = lifecycle.get("assignment") or {}
    record = dict(assignment)
    if isinstance(lifecycle.get("task_revision"), dict):
        record["task_revision"] = lifecycle["task_revision"]
    return record


def _open_questions(assignment: Dict[str, Any]) -> List[Dict[str, Any]]:
    unresolved = (assignment.get("task_revision") or {}).get("unresolved") or []
    return [item for item in unresolved
            if isinstance(item, dict) and item.get("status") == "open"]


def _reconciliations(assignment: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        step for step in assignment.get("steps") or []
        if step.get("adapter") == "invoice.reconcile"
        and step.get("status") == "applied"
    ]


def _wait_for(predicate, timeout_s: float, label: str):
    end = time.time() + timeout_s
    last = None
    while time.time() < end:
        try:
            last = predicate()
            if last:
                return last
        except Exception as exc:  # noqa: BLE001 - recorded by caller timeout
            last = exc
        time.sleep(0.5)
    raise DriverError(f"timed out waiting for {label}; last={last!r}")


UPLOAD_ENDPOINT = "/api/documents/upload"


def _uploaded_source_identity(
        body: Any, *, expected_file_name: str = "") -> Dict[str, Any]:
    """The exact document identity the mounted upload action created.

    The fixture path only names the bytes handed to the file input; it is not
    the identity the product accepted. This reads the browser's real upload
    response and fails closed when any field the observer later compares is
    missing or internally inconsistent.
    """
    if not isinstance(body, dict):
        raise DriverError("upload response is not a JSON object")
    metadata = body.get("metadata")
    if not isinstance(metadata, dict):
        raise DriverError("upload response has no document metadata")
    doc_id = str(body.get("id") or "").strip()
    metadata_id = str(metadata.get("doc_id") or "").strip()
    file_name = str(metadata.get("filename") or "").strip()
    file_type = str(metadata.get("file_type") or "").strip().lower()
    integration = str(metadata.get("integration_id") or "").strip()
    version = str(metadata.get("source_content_hash") or "").strip()
    size = metadata.get("size")
    title = str(body.get("title") or "").strip()
    if (not doc_id or doc_id in (".", "..") or "/" in doc_id
            or "\\" in doc_id or metadata_id != doc_id):
        raise DriverError(
            "upload response document identity is incomplete: "
            f"id={doc_id!r} metadata.doc_id={metadata_id!r}")
    if not file_name or (
            expected_file_name and file_name != expected_file_name):
        raise DriverError(
            f"upload response names {file_name!r}, not "
            f"{expected_file_name!r}")
    if (not file_type or "/" in file_type or "\\" in file_type):
        raise DriverError(
            f"upload response file type is incomplete: {file_type!r}")
    if title and title != file_name:
        raise DriverError(
            f"upload response title {title!r} differs from {file_name!r}")
    if integration != "manual_upload":
        raise DriverError(
            "upload response is not a manual upload: "
            f"integration_id={integration!r}")
    if not version:
        raise DriverError("upload response has no source revision")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise DriverError(
            f"upload response size is incomplete: {size!r}")
    return {
        "document_id": doc_id,
        "file_name": file_name,
        "file_type": file_type,
        "source": integration,
        "external_id": f"upload_{doc_id}",
        "source_version": version,
        "file_size_bytes": size,
    }


def _source_identity_mismatches(
        step: Any, identity: Dict[str, Any], *,
        upload_root: Path, user_id: str) -> List[str]:
    """Every way a persisted source step differs from the upload.

    Empty means the step is the exact uploaded source AND the read applied;
    a parked/waiting step is not acceptance. Missing shape is a mismatch,
    never a pass.
    """
    doc_id = str(identity.get("document_id") or "")
    file_type = str(identity.get("file_type") or "")
    version = str(identity.get("source_version") or "")
    if (not doc_id or "/" in doc_id or "\\" in doc_id
            or not file_type or "/" in file_type or "\\" in file_type
            or not version):
        return ["identity"]
    if not isinstance(step, dict):
        return ["step"]
    if str(step.get("adapter") or "") != "document.text":
        return ["adapter"]
    if step.get("status") != "applied":
        return ["step_status"]
    inputs = step.get("inputs")
    if not isinstance(inputs, dict):
        return ["inputs"]
    binding = inputs.get("resource_binding")
    if not isinstance(binding, dict):
        return ["resource_binding"]
    coverage = binding.get("coverage")
    coverage = coverage if isinstance(coverage, dict) else {}
    scope = binding.get("access_scope")
    scope = scope if isinstance(scope, dict) else {}
    result = step.get("result")
    result = result if isinstance(result, dict) else {}
    verification = result.get("verification")
    verification = verification if isinstance(verification, dict) else {}
    expected_path = (
        Path(upload_root) / f"{doc_id}.{file_type}").resolve()
    raw_path = str(inputs.get("path") or "")
    actual_path = Path(raw_path).resolve() if raw_path else None
    binding_workspace = str(binding.get("workspace_id") or "")
    scope_workspace = str(scope.get("workspace_id") or "")
    checks = [
        ("binding.resource_id", binding.get("resource_id") == doc_id),
        ("binding.external_id",
         binding.get("external_id") == identity.get("external_id")),
        ("binding.original_file_name",
         binding.get("original_file_name") == identity.get("file_name")),
        ("binding.source", binding.get("source") == identity.get("source")),
        ("binding.representation",
         binding.get("representation") == "document_text"),
        ("binding.source_version",
         binding.get("source_version") == version),
        ("binding.internal_fixture",
         binding.get("internal_fixture") is False),
        ("binding.dataset_name", binding.get("dataset_name") is None),
        ("binding.file_size_bytes",
         coverage.get("file_size_bytes")
         == identity.get("file_size_bytes")),
        ("binding.access_scope_user",
         bool(user_id) and scope.get("user_id") == user_id),
        ("binding.workspace_scope",
         bool(binding_workspace) and binding_workspace == scope_workspace),
        ("inputs.path_canonical",
         bool(raw_path) and actual_path == expected_path),
        ("uploaded_file_present", expected_path.is_file()),
        ("result.resource_id", result.get("resource_id") == doc_id),
        ("result.source_version",
         result.get("source_version") == version),
        ("result.verification_status",
         verification.get("status") == "verified"),
        ("result.verification_resource_id",
         verification.get("resource_id") == doc_id),
        ("result.verification_version",
         verification.get("version") == version),
    ]
    return [name for name, ok in checks if not ok]


def _accepted_source_step(
        assignment: Dict[str, Any], identity: Dict[str, Any], *,
        upload_root: Path, user_id: str) -> Optional[Dict[str, Any]]:
    """The first persisted step carrying exactly this uploaded identity."""
    for step in assignment.get("steps") or []:
        if not _source_identity_mismatches(
                step, identity, upload_root=upload_root, user_id=user_id):
            return step
    return None


def _upload_and_select(
        page: Any, path: Path, file_name: str) -> Dict[str, Any]:
    """Upload through the mounted input, then attach that exact document.

    Returns the identity the product created and the identities the mounted
    source picker/attach action carried, so the durable observer can compare
    against those instead of the fixture path.
    """
    upload = page.get_by_test_id("assignment-source-upload")
    upload.wait_for(state="visible", timeout=60000)
    try:
        with page.expect_response(
                lambda response: (
                    response.request.method == "POST"
                    and UPLOAD_ENDPOINT in response.url),
                timeout=120000) as upload_info:
            upload.set_input_files(str(path))
    except Exception as exc:  # noqa: BLE001 - report the transport failure
        raise DriverError(
            f"upload of {file_name} produced no response: "
            f"{type(exc).__name__}: {exc}") from exc
    response = upload_info.value
    if response.status != 200:
        raise DriverError(
            f"upload of {file_name} returned {response.status}: "
            f"{response.text()[:500]}")
    try:
        body = response.json()
    except Exception as exc:  # noqa: BLE001 - non-JSON is a failed upload
        raise DriverError(
            f"upload of {file_name} returned non-JSON: "
            f"{type(exc).__name__}: {exc}") from exc
    identity = _uploaded_source_identity(
        body, expected_file_name=file_name)
    page.wait_for_function(
        "name => (document.body.innerText || '').includes(`Uploaded ${name}`)",
        arg=file_name, timeout=120000)
    selector = page.get_by_test_id("assignment-answer-source-select")
    selector.wait_for(state="visible", timeout=120000)
    option = selector.locator("option").filter(has_text=file_name).first
    option.wait_for(state="attached", timeout=120000)
    selected_key = option.get_attribute("value") or ""
    expected_key = f"document:{identity['document_id']}"
    if selected_key != expected_key:
        raise DriverError(
            f"source picker offered {selected_key!r} for {file_name}, "
            f"not the uploaded document {expected_key!r}")
    selector.select_option(value=selected_key)
    try:
        with page.expect_response(
                lambda response: (
                    response.request.method == "POST"
                    and "/api/assignments/" in response.url
                    and response.url.split("?")[0].endswith("/sources")),
                timeout=300000) as attach_info:
            page.get_by_test_id("assignment-use-source").click()
    except Exception as exc:  # noqa: BLE001 - report the transport failure
        raise DriverError(
            f"source attach for {file_name} produced no response: "
            f"{type(exc).__name__}: {exc}") from exc
    attach = attach_info.value
    if attach.status != 200:
        raise DriverError(
            f"source attach for {file_name} returned {attach.status}: "
            f"{attach.text()[:500]}")
    try:
        attach_body = json.loads(attach.request.post_data or "{}")
    except (TypeError, ValueError) as exc:
        raise DriverError(
            f"source attach for {file_name} sent no JSON source") from exc
    attached = (
        attach_body.get("source")
        if isinstance(attach_body, dict) else None)
    if not isinstance(attached, dict):
        raise DriverError(
            f"source attach for {file_name} carried no source object")
    if str(attached.get("document_id") or "") != identity["document_id"]:
        raise DriverError(
            "source attach did not carry the uploaded document id: "
            f"{attached.get('document_id')!r}")
    if str(attached.get("source_version") or "") != identity["source_version"]:
        raise DriverError(
            "source attach did not carry the uploaded source revision: "
            f"{attached.get('source_version')!r}")
    page.wait_for_timeout(1500)
    return {
        **identity,
        "selected_source_key": selected_key,
        "upload_status": response.status,
        "attach_status": attach.status,
        "attached_document_id": str(attached.get("document_id") or ""),
        "attached_source_version": str(
            attached.get("source_version") or ""),
    }


def _run_scenario(args: argparse.Namespace) -> int:
    if not args.out:
        print("[execute] --out is required", file=sys.stderr)
        return 2
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    world = _world_path(args.world)
    scenario: Dict[str, Any] = {
        "kind": "browser_invoice_partial_evidence_scenario",
        "status": "running",
        "started_at": _now(),
        "labels": LABELS,
        "steps": [],
    }
    cleanups: List[Any] = []

    def step(name: str, checks: Dict[str, Any],
             details: Optional[Dict[str, Any]] = None) -> None:
        ok = bool(checks) and all(value is True for value in checks.values())
        scenario["steps"].append({
            "name": name, "status": "PASS" if ok else "FAIL",
            "checks": checks, "details": details or {}, "at": _now()})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        for key, value in checks.items():
            print(f"    {'ok' if value is True else 'FAIL'} {key}: {value}")
        if not ok:
            raise DriverError(f"scenario check failed: {name}")

    try:
        stack = D3._prepare_execute_environment(args)
        scenario["driver_environment"] = stack
        scenario["preflight"] = D3._check_execute_ready(args)
        source = D3._source_probe(args.expect_source_sha)
        _write_json(out / "source.json", source)
        if args.expect_source_sha and source.get("matches_expected") is not True:
            raise DriverError(
                f"HEAD {source['head']} does not match --expect-source-sha")
        if source.get("backend_dirty_count"):
            raise DriverError("backend working tree is dirty")
        step("source_identity", {
            "head_present": bool(source.get("head")),
            "backend_tree_clean": source.get("backend_dirty_count") == 0,
        }, details={"head": source.get("head"),
                    "runtime_identity": source.get("runtime_identity")})

        build = D3._build_world(world, source.get("head") or "")
        scenario["world_build"] = {
            key: value for key, value in build.items()
            if key not in ("code_manifest", "export_tree")}
        step("world_built_once", {
            "manifest_present": Path(build["manifest_path"]).is_file(),
            "fixture_present": Path(build["fixture_path"]).is_file(),
            "disk_preflight_ok": bool(
                (build.get("disk_preflight") or {}).get("ok")),
            "preflight_source_matches_frozen": (
                (build.get("preflight") or {}).get("source_revision")
                == source.get("head")),
        }, details={"manifest_source_revision": build.get("source_revision")})

        fixture_root = world / "invoice_fixtures"
        fixtures = _write_fixture_files(fixture_root)
        scenario["fixtures"] = fixtures
        os.environ.update({
            "ADDITIONAL_ALLOWED_ORIGINS": (
                f"http://localhost:{args.frontend_port},"
                f"http://127.0.0.1:{args.frontend_port}"),
            "ALLOWED_HOSTS": (
                f"localhost,127.0.0.1,localhost:{args.backend_port},"
                f"localhost:{args.frontend_port}"),
            "ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS": "1",
            "ATOM_ASSIGNMENT_INTERNAL_FIXTURE_ROOT": str(fixture_root),
            "ATOM_EMPLOYEE_PROVIDER_MODEL": "openai:gpt-4o-mini",
        })

        shim_path = world / "invoice_partial_shim.json"
        _write_json(shim_path, _shim_doc())
        shim_capture = world / "invoice_partial_shim_capture.jsonl"
        os.environ["SHIM_CAPTURE_MESSAGES"] = "1"
        shim = D3.R.launch_shim(
            shim_path, args.shim_port, capture=shim_capture)
        cleanups.append(shim)

        backend = D3.R.launch_server(
            args.backend_port, world, provider_shim=True,
            shim_port=args.shim_port)
        cleanups.append(backend)
        run_dir = D3.R.launch_server.last_run_dir
        db_path = run_dir / "data" / "atom.db"
        descriptor = dict(D3.R.launch_server.descriptor)
        health = D3._health(args.backend_port)
        scenario["stack"] = {
            "world": str(world), "run_dir": str(run_dir),
            "db_path": str(db_path), "backend_port": args.backend_port,
            "frontend_port": args.frontend_port, "shim_port": args.shim_port,
            "descriptor": descriptor, "health": health,
            "shim_capture": str(shim_capture),
        }
        step("backend_isolated_scratch", {
            "health_ok": health.get("status") in (
                None, "healthy", "degraded", "ok"),
            "cwd_is_world_backend_root": (
                Path(str((health.get("identity") or {}).get("cwd") or ""))
                .resolve() == (world / "backend_root").resolve()),
            "db_is_run_db": Path(str(descriptor.get("db_path") or ""))
            .resolve() == db_path.resolve(),
            "db_not_live": db_path.resolve() != (
                BACKEND / "data" / "atom.db").resolve(),
        }, details={"descriptor": descriptor,
                    "health_identity": health.get("identity")})

        password, password_meta = D3._password_for_run(
            args, world, db_path, run_dir)
        scenario["admin_password_source"] = password_meta
        token, login_meta = D3._api_login(args.backend_port, password)
        scenario["api_login"] = login_meta

        from scripts.orchestration_acceptance import (
            case5_browser_recovery as C5,
            browser_verify as BV,
        )
        fe_proc = C5.start_frontend_copy(
            args.backend_port, args.frontend_port, world)
        if not fe_proc:
            raise DriverError("frontend copy failed to start")
        cleanups.append(fe_proc)
        fe_base = f"http://localhost:{args.frontend_port}"

        with D3._api_client(args.backend_port, token) as api:
            started = api.post("/api/assignments/from-objective", json={
                "objective": OBJECTIVE,
                "sources": [
                    {"path": str(fixture_root / "po.json")},
                    {"path": str(fixture_root / "receiving.json")},
                ],
                "authorized_actions": ["retrieve", "calculate"],
                "use_model": True,
            })
            if started.status_code != 200:
                raise DriverError(
                    f"objective start failed {started.status_code}: "
                    f"{started.text[:800]}")
            start_body = started.json()
            run_id = str(start_body.get("run_id") or "")
            if not run_id:
                raise DriverError("objective start returned no run_id")
            scenario["run_id"] = run_id
            waiting = _wait_for(
                lambda: (_open_questions(_durable_assignment(db_path, run_id))
                         or None), 180, "durable invoice question")
            scenario["initial_question"] = waiting[0]
            step("partial_fixture_before_invoice", {
                "question_open": bool(waiting),
                "question_names_invoice": INVOICE in json.dumps(waiting[0]),
                "no_reconciliation_yet": not _reconciliations(
                    _durable_assignment(db_path, run_id)),
            }, details={"question": waiting[0]})

            from playwright.sync_api import sync_playwright

            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=not args.headed, channel="chrome")
                context = browser.new_context(
                    viewport={"width": 1440, "height": 1100})
                page = context.new_page()
                page.add_init_script(
                    "sessionStorage.setItem('atom.onboarding.dismissed','1')")
                # Prove the browser starts with no app session: the only
                # credential in this context must be the one the real form
                # obtains below.
                page.goto(f"{fe_base}/login",
                          wait_until="domcontentloaded", timeout=300000)
                pre_auth = page.evaluate(
                    """() => ({
                        token: localStorage.getItem('auth_token'),
                        cookies: document.cookie
                            .split(';').map((c) => c.trim().split('=')[0])
                            .filter(Boolean),
                    })""")
                step("browser_starts_signed_out", {
                    "no_local_bearer": not pre_auth.get("token"),
                    "no_auth_cookie": "auth_token" not in pre_auth["cookies"],
                    "no_session_cookie": not any(
                        name.replace("__Secure-", "", 1).startswith(
                            "next-auth.session-token")
                        for name in pre_auth["cookies"]),
                }, details={"cookie_names": pre_auth["cookies"]})

                login = BV.ui_login(page, fe_base, ADMIN_EMAIL, password)
                step("ordinary_signed_in_browser", {
                    "attempted": login.get("attempted") is True,
                    "landed_off_login": login.get("ok") is True,
                    "token_present_after_login": bool(
                        login.get("token_present_after_login")),
                }, details=login)
                D3._screenshot(page, out, "00_login.png")

                # Prove both halves of the mounted auth: the SDK session the
                # middleware decodes and a backend endpoint that authorizes
                # only the login-issued bearer. Nothing here seeds a token or
                # cookie; the bearer is read from what the form persisted.
                auth_probe = page.evaluate(
                    """async (backendBase) => {
                        const token = localStorage.getItem('auth_token') || '';
                        const sessionResponse = await fetch(
                            '/api/auth/session',
                            {headers: {Accept: 'application/json'},
                             cache: 'no-store'});
                        let session = null;
                        try { session = await sessionResponse.json(); }
                        catch (e) {}
                        const meResponse = await fetch(
                            `${backendBase}/api/auth/me`,
                            {headers: {Accept: 'application/json',
                                       Authorization: `Bearer ${token}`},
                             cache: 'no-store'});
                        let me = null;
                        try { me = await meResponse.json(); }
                        catch (e) {}
                        return {
                            token_present: Boolean(token),
                            session_status: sessionResponse.status,
                            session_email: (session && session.user &&
                                            session.user.email) || null,
                            session_user_id: (session && session.user &&
                                              session.user.id) || null,
                            me_status: meResponse.status,
                            me_email: (me && me.email) || null,
                            me_id: (me && me.id) || null,
                            me_status_field: (me && me.status) || null,
                        };
                    }""",
                    arg=f"http://localhost:{args.backend_port}")
                scenario["authenticated_endpoint"] = auth_probe
                step("authenticated_endpoint", {
                    "bearer_came_from_login": (
                        auth_probe.get("token_present") is True),
                    "web_session_decoded": (
                        auth_probe.get("session_status") == 200
                        and auth_probe.get("session_email") == ADMIN_EMAIL),
                    "backend_me_authorized": (
                        auth_probe.get("me_status") == 200
                        and auth_probe.get("me_email") == ADMIN_EMAIL
                        and bool(auth_probe.get("me_id"))),
                    "backend_identity_active": (
                        auth_probe.get("me_status_field") == "active"),
                }, details={
                    "credential_source": (
                        "localStorage auth_token persisted by the real login "
                        "form; no token or cookie injected by the harness"),
                    "session_status": auth_probe.get("session_status"),
                    "me_status": auth_probe.get("me_status"),
                })

                page.goto(f"{fe_base}/assignments",
                          wait_until="domcontentloaded", timeout=300000)
                summary = page.get_by_test_id(
                    f"assignment-summary-{run_id}")
                summary.wait_for(timeout=180000)
                summary.click()
                detail = page.get_by_test_id("assignment-detail")
                detail.wait_for(timeout=120000)
                question = page.get_by_text(INVOICE, exact=False).first
                question.wait_for(timeout=120000)
                D3._screenshot(page, out, "01_missing_invoice_question.png")

                actor_id = str(auth_probe.get("me_id") or "")
                upload_root = db_path.parent / "office" / "uploads"
                partial_path = fixture_root / PARTIAL_NAME
                partial_upload = _upload_and_select(
                    page, partial_path, PARTIAL_NAME)
                scenario["partial_upload"] = partial_upload

                def _partial_accepted():
                    current = _durable_assignment(db_path, run_id)
                    if _accepted_source_step(
                            current, partial_upload,
                            upload_root=upload_root, user_id=actor_id):
                        return current
                    return None

                partial_assignment = _wait_for(
                    _partial_accepted, 180,
                    "partial invoice source acceptance")
                partial_step = _accepted_source_step(
                    partial_assignment, partial_upload,
                    upload_root=upload_root, user_id=actor_id)
                partial_mismatches = _source_identity_mismatches(
                    partial_step, partial_upload,
                    upload_root=upload_root, user_id=actor_id)
                partial_questions = _open_questions(partial_assignment)
                partial_reconciliations = _reconciliations(partial_assignment)
                scenario["partial_evidence"] = {
                    "open_questions": partial_questions,
                    "reconciliations": len(partial_reconciliations),
                    "status": partial_assignment.get("status"),
                    "upload": partial_upload,
                    "source_step_id": (partial_step or {}).get("step_id"),
                    "source_identity_mismatches": partial_mismatches,
                }
                step("partial_invoice_stays_unresolved", {
                    "question_still_open": bool(partial_questions),
                    "no_reconciliation": not partial_reconciliations,
                    "not_completed": (
                        partial_assignment.get("status") != "completed"),
                    "upload_identity_exact": not partial_mismatches,
                    "upload_response_200": (
                        partial_upload["upload_status"] == 200),
                    "attach_response_200": (
                        partial_upload["attach_status"] == 200),
                }, details=scenario["partial_evidence"])
                D3._screenshot(page, out, "02_partial_invoice_unresolved.png")

                complete_path = fixture_root / COMPLETE_NAME
                complete_upload = _upload_and_select(
                    page, complete_path, COMPLETE_NAME)
                scenario["complete_upload"] = complete_upload

                def _complete_accepted():
                    current = _durable_assignment(db_path, run_id)
                    if _accepted_source_step(
                            current, complete_upload,
                            upload_root=upload_root, user_id=actor_id):
                        return current
                    return None

                _wait_for(
                    _complete_accepted, 180,
                    "complete invoice source acceptance")
                final = _wait_for(
                    lambda: (_durable_assignment(db_path, run_id)
                             if _reconciliations(
                                 _durable_assignment(db_path, run_id))
                             else None),
                    240, "complete invoice reconciliation")
                complete_step = _accepted_source_step(
                    final, complete_upload,
                    upload_root=upload_root, user_id=actor_id)
                complete_mismatches = _source_identity_mismatches(
                    complete_step, complete_upload,
                    upload_root=upload_root, user_id=actor_id)
                reconciliations = _reconciliations(final)
                value = (
                    (reconciliations[0].get("result") or {}).get("value")
                    if reconciliations else None)
                scenario["complete_evidence"] = {
                    "status": final.get("status"),
                    "reconciliations": len(reconciliations),
                    "value": value,
                    "open_questions": _open_questions(final),
                    "upload": complete_upload,
                    "source_step_id": (complete_step or {}).get("step_id"),
                    "source_identity_mismatches": complete_mismatches,
                }
                step("complete_invoice_one_verified_result", {
                    "exactly_one_reconciliation": len(reconciliations) == 1,
                    "value_is_expected": value == EXPECTED_TOTAL,
                    "assignment_completed": final.get("status") == "completed",
                    "no_remaining_question": not _open_questions(final),
                    "upload_identity_exact": not complete_mismatches,
                    "both_upload_identities_exact": not (
                        partial_mismatches or complete_mismatches),
                    "distinct_source_identity": (
                        partial_upload["document_id"]
                        != complete_upload["document_id"]
                        and partial_upload["source_version"]
                        != complete_upload["source_version"]),
                    "both_upload_responses_200": (
                        partial_upload["upload_status"] == 200
                        and complete_upload["upload_status"] == 200),
                    "both_attach_responses_200": (
                        partial_upload["attach_status"] == 200
                        and complete_upload["attach_status"] == 200),
                }, details=scenario["complete_evidence"])
                D3._screenshot(page, out, "03_complete_invoice_result.png")

                page.reload(wait_until="domcontentloaded", timeout=120000)
                detail.wait_for(timeout=120000)
                result = page.get_by_test_id(
                    "assignment-result-invoice-reconcile")
                result.wait_for(timeout=120000)
                scenario["ui_result_text"] = result.inner_text()
                step("signed_in_ui_shows_result", {
                    "result_visible": result.is_visible(),
                    "result_has_expected_total": EXPECTED_TOTAL in (
                        scenario["ui_result_text"] or ""),
                }, details={"text": scenario["ui_result_text"]})
                D3._screenshot(page, out, "04_result_after_reload.png")
                browser.close()

            shim_state = D3._shim_snapshot(args.shim_port)
            scenario["shim"] = {
                "calls": shim_state.get("calls"),
                "available": shim_state.get("available"),
                "capture": str(shim_capture),
            }
            scenario["status"] = "passed"
            scenario["finished_at"] = _now()
            return 0
    except Exception as exc:  # noqa: BLE001 - failure is evidence
        scenario["status"] = "failed"
        scenario["error"] = f"{type(exc).__name__}: {exc}"
        scenario["finished_at"] = _now()
        print(f"[FAIL] {scenario['error']}", file=sys.stderr)
        return 1
    finally:
        for proc in reversed(cleanups):
            try:
                D3.R.stop_server(proc)
            except Exception:  # noqa: BLE001 - best-effort cleanup
                try:
                    os.killpg(os.getpgid(proc.pid), 15)
                except Exception:
                    pass
        _write_json(out / "scenario.json", scenario)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--world", default="browser_invoice_partial")
    ap.add_argument("--backend-port", type=int, default=8037)
    ap.add_argument("--frontend-port", type=int, default=3137)
    ap.add_argument("--shim-port", type=int, default=8107)
    ap.add_argument("--out", default="")
    ap.add_argument("--expect-source-sha", default="")
    ap.add_argument("--admin-password-file", default="")
    ap.add_argument("--provision-admin-password", action="store_true")
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args(argv)
    if args.preflight and args.execute:
        ap.error("choose --preflight or --execute")
    if not args.preflight and not args.execute:
        args.preflight = True
    if args.preflight:
        return _run_preflight(args)
    return _run_scenario(args)


if __name__ == "__main__":
    raise SystemExit(main())
