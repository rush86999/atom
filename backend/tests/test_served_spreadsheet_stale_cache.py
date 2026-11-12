# -*- coding: utf-8 -*-
"""Served spreadsheet regression: a stale cached SUM must not win.

The user-facing sequence is the product's own:

1. ``POST /api/documents/upload`` (authenticated) uploads a synthetic XLSX
   whose ``Summary!B4`` formula is ``=SUM(B2,B3)``.  The workbook's cached
   result for B4 is deliberately stale (999) while the current inputs are
   B2=10 and B3=32.5.
2. The upload schedules the REAL sheet-dataset materialization, so the
   Parquet frame contains the stale cached 999 at B4 and the formula sidecar
   contains ``=SUM(B2,B3)``.
3. ``POST /api/chat/message`` (authenticated, the normal chat API) asks
   ``calculate formula for <file> Summary cell B4``.
4. The production workbook calculation lane evaluates the formula from the
   current inputs and the response reports 42.5, grounded in B2/B3/B4.  The
   task lifecycle operation keeps the dependency cells and values.

Isolation: a real uvicorn process on a loopback port, an explicit scratch
SQLite file, scratch ATOM_DATA_DIR/LanceDB/BYOK files, every provider key
pinned empty, ``ATOM_LOCAL_ONLY=true``, and a loopback-only socket guard in
the served fixture.  The LLM and embedding transports are doubled in
``tests/fixtures/served_spreadsheet_app.py``; ingestion, materialization,
the formula engine, the calculation lane, auth and chat are real.
"""
from __future__ import annotations

import io
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
import uuid
import zipfile
from decimal import Decimal
from pathlib import Path

import httpx
import pandas as pd
import pytest
from openpyxl import Workbook, load_workbook

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from scripts.orchestration_acceptance.acceptance_trial_lib import (  # noqa: E402
    job_for_session,
    sqlite_select,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.api,
    pytest.mark.slow,
]

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FILE_NAME = "stale_total.xlsx"
SHEET = "Summary"
OUTPUT_CELL = "B4"
STALE_CACHED_RESULT = Decimal("999")
CURRENT_TOTAL = Decimal("42.5")
INPUTS = {"B2": Decimal("10"), "B3": Decimal("32.5")}

# The names journey_runtime scrubs/pins for a world that must not reach a
# provider.  Kept explicit so this test does not depend on a larger harness.
_PROVIDER_KEY_ENV_NAMES = (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY",
    "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY", "GROQ_API_KEY",
    "TOGETHER_API_KEY", "GLM_API_KEY", "MOONSHOT_API_KEY",
    "OPENCODE_API_KEY", "TAVILY_API_KEY", "BRAVE_SEARCH_API_KEY",
)


def _build_stale_sum_xlsx() -> bytes:
    """A valid XLSX: current inputs + a deliberately stale cached SUM.

    openpyxl writes the formula cell with an empty cached ``<v>``.  Replace
    that one value with 999 while leaving the formula body intact, which is
    exactly the shape Excel leaves after an input edit outside Excel / after a
    recovered workbook.
    """
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = SHEET
    sheet.append(["Item", "Amount"])
    sheet.append(["Bolt", 10])
    sheet.append(["Nut", 32.5])
    sheet[OUTPUT_CELL] = "=SUM(B2,B3)"

    raw = io.BytesIO()
    workbook.save(raw)

    source = zipfile.ZipFile(io.BytesIO(raw.getvalue()))
    patched = io.BytesIO()
    replaced = 0
    with zipfile.ZipFile(patched, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                text = data.decode("utf-8")
                text, replaced = re.subn(
                    r'(<c r="B4"[^>]*>\s*<f>SUM\(B2,B3\)</f>)'
                    r'<v\s*/?>(?:</v>)?',
                    r"\1<v>999</v>",
                    text,
                )
                data = text.encode("utf-8")
            target.writestr(item, data)
    source.close()
    assert replaced == 1, "fixture must inject exactly one stale cached value"

    content = patched.getvalue()
    assert load_workbook(io.BytesIO(content), data_only=False)[
        SHEET][OUTPUT_CELL].value == "=SUM(B2,B3)"
    assert load_workbook(io.BytesIO(content), data_only=True)[
        SHEET][OUTPUT_CELL].value == float(STALE_CACHED_RESULT)
    return content


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _wait_for_health(base_url: str, process: subprocess.Popen,
                     log_path: Path, timeout_s: float = 120.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail(
                "served app exited during boot:\n"
                + _tail(log_path))
        try:
            response = httpx.get(
                base_url + "/api/health", timeout=2.0, trust_env=False)
            if response.status_code == 200:
                return
        except Exception:  # noqa: BLE001 — not up yet
            pass
        time.sleep(0.25)
    pytest.fail("served app did not become healthy:\n" + _tail(log_path))


def _tail(path: Path, limit: int = 8000) -> str:
    try:
        return path.read_text(errors="replace")[-limit:]
    except OSError:
        return "<no log>"


@pytest.fixture()
def served_app(tmp_path):
    scratch = tmp_path / "served"
    scratch.mkdir()
    db_path = scratch / "atom.db"
    log_path = scratch / "server.log"
    trace_path = scratch / "transport.jsonl"
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "TMPDIR": os.environ.get("TMPDIR", ""),
        # TESTING=1 makes core.database force backend/test_integration.db and
        # ignore DATABASE_URL.  This served world is explicit scratch SQLite.
        "TESTING": "0",
        "ENVIRONMENT": "development",
        "DATABASE_URL": f"sqlite:///{db_path}",
        "ATOM_DATA_DIR": str(scratch / "data"),
        "ATOM_OFFICE_DIR": str(scratch / "data" / "office"),
        "LANCEDB_URI": str(scratch / "data" / "atom_memory"),
        "LANCEDB_URI_BASE": str(scratch / "data" / "atom_memory"),
        "BYOK_CONFIG_FILE": str(scratch / "byok_config.json"),
        "BYOK_KEYS_FILE": str(scratch / "byok_keys.json"),
        "BYOK_ENC_KEY_FILE": str(scratch / "byok_encryption_key"),
        "ATOM_CHAT_STREAMING": "false",
        "ATOM_LOCAL_ONLY": "true",
        "ATOM_TASK_LIFECYCLE_ENABLED": "1",
        "CHAT_FINALIZATION_M1": "1",
        "CHAT_FINALIZATION_M2": "1",
        "ADMIN_PASSWORD": secrets.token_urlsafe(18),
        "SECRET_KEY": secrets.token_urlsafe(32),
        "PYTHONPATH": str(BACKEND),
        "PYTHONDONTWRITEBYTECODE": "1",
        "SERVED_SPREADSHEET_TRACE": str(trace_path),
    }
    for name in _PROVIDER_KEY_ENV_NAMES:
        env[name] = ""
    for name in ("OLLAMA_HOST", "OLLAMA_BASE_URL", "OLLAMA_MODEL"):
        env[name] = ""

    log_handle = log_path.open("w")
    process = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "served_spreadsheet_app:app",
            "--app-dir", str(FIXTURES),
            "--host", "127.0.0.1",
            "--port", str(port),
            "--log-level", "warning",
        ],
        cwd=str(BACKEND),
        env=env,
        stdout=log_handle,
        stderr=log_handle,
    )
    try:
        _wait_for_health(base_url, process, log_path)
        assert db_path.exists(), "the served app did not create the scratch DB"
        assert str(db_path).startswith(str(tmp_path))
        yield {
            "base_url": base_url,
            "db_path": db_path,
            "log_path": log_path,
            "trace_path": trace_path,
            "process": process,
        }
    finally:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        log_handle.close()


def _authenticated_user(base_url: str) -> dict:
    email = f"served_sheet_{uuid.uuid4().hex[:10]}@example.com"
    password = "TestPass123!"
    registered = httpx.post(
        base_url + "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "Served",
            "last_name": "Sheet",
        },
        timeout=30,
        trust_env=False,
    )
    assert registered.status_code in (200, 201), registered.text
    logged_in = httpx.post(
        base_url + "/api/auth/login",
        json={"username": email, "password": password},
        timeout=30,
        trust_env=False,
    )
    assert logged_in.status_code == 200, logged_in.text
    token = logged_in.json().get("access_token")
    assert token, logged_in.text
    me = httpx.get(
        base_url + "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        trust_env=False,
    )
    assert me.status_code == 200, me.text
    identity = me.json()
    assert identity.get("id") and identity.get("workspace_id"), identity
    return {
        "token": token,
        "user_id": identity["id"],
        "workspace_id": identity["workspace_id"],
    }


def _upload_workbook(base_url: str, token: str, content: bytes) -> dict:
    response = httpx.post(
        base_url + "/api/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": (
                FILE_NAME,
                content,
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet",
            )
        },
        timeout=180,
        trust_env=False,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _active_dataset_entry(db_path: Path, timeout_s: float = 60.0):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        rows = sqlite_select(
            db_path,
            "SELECT id, entity_name, parquet_path, content_hash "
            "FROM dataset_entries WHERE file_name=? AND status='active'",
            (FILE_NAME,),
        )
        if rows:
            return rows[0]
        time.sleep(0.25)
    return None


def _contains_number(text: str, value: Decimal) -> bool:
    # Word/letter boundaries keep a version hash containing "999" from being
    # read as the stale figure; a real figure is delimited by space/punctuation.
    pattern = rf"(?<![\w.]){re.escape(str(value))}(?:\.0+)?(?![\w.])"
    return re.search(pattern, text) is not None


def _calculation_operation(db_path: Path, session_id: str) -> dict:
    job = job_for_session(db_path, session_id)
    assert job, f"no durable task for chat session {session_id!r}"
    operations = [
        operation for operation in (job.get("ops") or [])
        if isinstance(operation, dict)
        and operation.get("operation_type") == "calculate"
    ]
    assert len(operations) == 1, (
        "expected exactly one durable calculate operation; got "
        f"{operations!r}")
    return operations[0]


def test_served_chat_uses_current_sum_not_stale_cached_result(served_app):
    """The public upload + chat boundary computes 42.5, never the cached 999."""
    base_url = served_app["base_url"]
    workbook_bytes = _build_stale_sum_xlsx()

    user = _authenticated_user(base_url)
    uploaded = _upload_workbook(base_url, user["token"], workbook_bytes)
    assert uploaded.get("title") == FILE_NAME or uploaded.get("file_name") == FILE_NAME

    entry = _active_dataset_entry(served_app["db_path"])
    assert entry, (
        "upload never materialized a sheet dataset; server log:\n"
        + _tail(served_app["log_path"]))
    _, sheet_name, parquet_path, content_hash = entry
    assert sheet_name == SHEET
    parquet = Path(parquet_path)
    assert parquet.exists()

    # The materialized frame really carries the STALE cached value...
    frame = pd.read_parquet(parquet)
    assert {"Item", "Amount", "__sheet_row"} <= set(frame.columns)
    stale_row = frame.loc[frame["__sheet_row"] == 4]
    assert len(stale_row) == 1, frame
    assert Decimal(str(stale_row.iloc[0]["Amount"])) == STALE_CACHED_RESULT
    # ...while the original formula body survived in the sidecar.
    sidecar = parquet.with_name(parquet.name + ".formulas.json")
    assert sidecar.exists(), f"missing formula sidecar beside {parquet}"
    formulas = json.loads(sidecar.read_text())["formulas"]
    assert formulas.get(OUTPUT_CELL) == "=SUM(B2,B3)", formulas

    ask = f"calculate formula for {FILE_NAME} {SHEET} cell {OUTPUT_CELL}"
    response = httpx.post(
        base_url + "/api/chat/message",
        headers={"Authorization": f"Bearer {user['token']}"},
        json={
            "message": ask,
            "user_id": user["user_id"],
            "request_id": str(uuid.uuid4()),
        },
        timeout=300,
        trust_env=False,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("success") is True, body
    message = str(body.get("message") or "")
    session_id = body.get("session_id")
    assert session_id, body

    # The delivered answer is the CURRENT total, attributed to the workbook.
    assert "42.5" in message, message
    assert FILE_NAME in message and SHEET in message and OUTPUT_CELL in message
    assert not _contains_number(message, STALE_CACHED_RESULT), (
        "the reply served the stale cached SUM result: " + message)

    # Durable agreement: the calculate operation's dependencies are the
    # workbook cells that ground the current total.
    operation = _calculation_operation(served_app["db_path"], session_id)
    assert operation.get("status") == "applied", operation
    record = operation.get("calculation") or {}
    assert record.get("status") == "succeeded", record
    assert record.get("workbook", {}).get("file") == FILE_NAME
    assert record.get("workbook", {}).get("sheet") == SHEET
    assert record.get("workbook", {}).get("output_cell") == OUTPUT_CELL

    dependencies = {
        (dependency.get("sheet"), dependency.get("cell")): dependency
        for dependency in (record.get("dependencies") or [])
        if isinstance(dependency, dict)
    }
    for cell, expected in INPUTS.items():
        dependency = dependencies.get((SHEET, cell))
        assert dependency is not None, dependencies
        assert Decimal(str(dependency.get("value"))) == expected, dependency
    output = dependencies.get((SHEET, OUTPUT_CELL))
    assert output is not None, dependencies
    assert output.get("formula") == "=SUM(B2,B3)", output
    assert Decimal(str(output.get("value"))) == CURRENT_TOTAL, output

    steps = [step for step in (record.get("steps") or [])
             if isinstance(step, dict)]
    assert any(
        step.get("op") == "add"
        and Decimal(str(step.get("output"))) == CURRENT_TOTAL
        for step in steps
    ), steps
    assert record.get("workbook", {}).get("version") == content_hash
