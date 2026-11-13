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

Only provider responses are authored (SIMULATED MODEL DECISIONS / CONTROLLED
TRANSPORT). Routing, source reads, the structured consumer, wait settlement,
the compiler/executor, reconciliation and durable persistence all run in
production code. No real credential, provider, account, send or spend is used.

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

LABELS = {
    "model_decisions": (
        "SIMULATED MODEL DECISIONS: authored JSON completions served by the "
        "existing loopback provider shim. Not served-model output."),
    "transport": (
        "CONTROLLED TRANSPORT: only the provider response is substituted; "
        "source upload/read, the structured consumer, wait settlement, "
        "invoice reconciliation, verification and persistence run in "
        "production code."),
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
    if not isinstance(responses, list) or len(responses) != 3:
        raise PreflightError("shim must author exactly three state responses")
    parsed: List[Dict[str, Any]] = []
    for index, entry in enumerate(responses):
        raw = entry.get("response")
        if not isinstance(raw, str):
            raise PreflightError(f"response[{index}] must be JSON text")
        payload = json.loads(raw)
        match = str(entry.get("match") or "")
        if "allowed_step_ids" in match:
            model = WorkAdaptationProposal.model_validate(payload)
            if model.decision != "replan" or not model.work_request:
                raise PreflightError("complete-evidence response is not a replan")
            if model.work_request.operation != "invoice_reconciliation":
                raise PreflightError("complete-evidence response wrong operation")
        elif "missing_prerequisites" in match:
            model = WorkAdaptationProposal.model_validate(payload)
            if model.decision != "retain":
                raise PreflightError("incomplete-evidence response must retain")
        elif "planning reasoner" in match:
            model = EmployeeWorkProposal.model_validate(payload)
            if model.proposal_kind != "evidence_read":
                raise PreflightError("discovery response must read evidence")
            handles = [read.source_id for read in model.evidence_reads]
            if handles != ["fixture:po.json", "fixture:receiving.json"]:
                raise PreflightError(f"unexpected discovery handles: {handles}")
        else:
            raise PreflightError(f"unrecognised match on response[{index}]")
        parsed.append({"match": match, "model": type(model).__name__,
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
            "reads; 'missing_prerequisites' -> retain while invoice incomplete; "
            "'allowed_step_ids' -> typed invoice reconciliation once complete"),
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
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = con.execute(
            "select parameters from goal_runs where id=?", (run_id,)).fetchone()
    finally:
        con.close()
    if row is None:
        return {}
    params = json.loads(row[0] or "{}")
    return (params.get("task_lifecycle") or {}).get("assignment") or {}


def _open_questions(assignment: Dict[str, Any]) -> List[Dict[str, Any]]:
    unresolved = (assignment.get("task_revision") or {}).get("unresolved") or []
    return [item for item in unresolved if item.get("status") == "open"]


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


def _upload_and_select(page: Any, path: Path, file_name: str) -> None:
    upload = page.get_by_test_id("assignment-source-upload")
    upload.wait_for(state="visible", timeout=60000)
    upload.set_input_files(str(path))
    page.wait_for_function(
        "name => (document.body.innerText || '').includes(`Uploaded ${name}`)",
        arg=file_name, timeout=120000)
    selector = page.get_by_test_id("assignment-answer-source-select")
    selector.wait_for(state="visible", timeout=120000)
    option = selector.locator("option").filter(has_text=file_name).first
    option.wait_for(state="attached", timeout=120000)
    selector.select_option(value=option.get_attribute("value") or "")
    page.get_by_test_id("assignment-use-source").click()
    page.wait_for_timeout(1500)


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
                login = BV.ui_login(page, fe_base, ADMIN_EMAIL, password)
                step("ordinary_signed_in_browser", {
                    "attempted": login.get("attempted") is True,
                    "landed_off_login": login.get("ok") is True,
                    "token_present_after_login": bool(
                        login.get("token_present_after_login")),
                }, details=login)
                D3._screenshot(page, out, "00_login.png")

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

                partial_path = fixture_root / PARTIAL_NAME
                _upload_and_select(page, partial_path, PARTIAL_NAME)
                def _partial_accepted():
                    current = _durable_assignment(db_path, run_id)
                    if any((step.get("inputs") or {}).get("path") == str(
                            partial_path)
                            for step in current.get("steps") or []):
                        return current
                    return None

                partial_assignment = _wait_for(
                    _partial_accepted, 180,
                    "partial invoice source acceptance")
                partial_questions = _open_questions(partial_assignment)
                partial_reconciliations = _reconciliations(partial_assignment)
                scenario["partial_evidence"] = {
                    "open_questions": partial_questions,
                    "reconciliations": len(partial_reconciliations),
                    "status": partial_assignment.get("status"),
                }
                step("partial_invoice_stays_unresolved", {
                    "question_still_open": bool(partial_questions),
                    "no_reconciliation": not partial_reconciliations,
                    "not_completed": (
                        partial_assignment.get("status") != "completed"),
                }, details=scenario["partial_evidence"])
                D3._screenshot(page, out, "02_partial_invoice_unresolved.png")

                complete_path = fixture_root / COMPLETE_NAME
                _upload_and_select(page, complete_path, COMPLETE_NAME)
                final = _wait_for(
                    lambda: (_durable_assignment(db_path, run_id)
                             if _reconciliations(
                                 _durable_assignment(db_path, run_id))
                             else None),
                    240, "complete invoice reconciliation")
                reconciliations = _reconciliations(final)
                value = (
                    (reconciliations[0].get("result") or {}).get("value")
                    if reconciliations else None)
                scenario["complete_evidence"] = {
                    "status": final.get("status"),
                    "reconciliations": len(reconciliations),
                    "value": value,
                    "open_questions": _open_questions(final),
                }
                step("complete_invoice_one_verified_result", {
                    "exactly_one_reconciliation": len(reconciliations) == 1,
                    "value_is_expected": value == EXPECTED_TOTAL,
                    "assignment_completed": final.get("status") == "completed",
                    "no_remaining_question": not _open_questions(final),
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
