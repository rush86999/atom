"""Final scheduler boundaries: SQLite URI safety target + generic 503 body.

Two root-verified negatives on the final shared code:

1. Preserving ``sqlite:///file:...?...uri=true`` made the live-DB guard miss the
   protected ``backend/dev.db`` / ``backend/data/atom.db`` targets, because the
   guard still treated the URI as a filesystem string. These controls execute
   the exact source functions (AST extraction, like the root counter) with a
   synthetic backend anchor and SQLAlchemy's actual SQLite connect args; no
   database connection or live file is opened. A subprocess also proves the
   pytest guard forces a protected URI to the scratch DB and leaves a valid
   absolute scratch URI eligible.

2. The scheduler-unavailable handler returned ``str(exc)`` to the caller. These
   controls extract the exact handler body and serve it through an isolated
   ASGI app: 503 + stable code + a generic actionable detail, with the raw
   marker retained only in logging.

Fixture boundaries: synthetic backend roots only; handler test is an isolated
ASGI app with the exact extracted handler, not the full mounted app/browser.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects.sqlite.pysqlite import SQLiteDialect_pysqlite
from sqlalchemy.engine import make_url
from starlette.requests import Request
from starlette.responses import JSONResponse

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
DB_SOURCE = (BACKEND / "core" / "database.py").read_text()
LOCAL_PATHS_SOURCE = (BACKEND / "core" / "local_paths.py").read_text()
MAIN_SOURCE = (BACKEND / "main_api_app.py").read_text()


def _extract_functions(source: str, names: set[str], namespace: dict) -> dict:
    nodes = [
        node for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    assert {node.name for node in nodes} == names
    exec(compile(ast.Module(body=nodes, type_ignores=[]),
                 "<exact-source-pure-functions>", "exec"), namespace)
    return namespace


@pytest.fixture()
def guard_functions(tmp_path):
    """Exact source functions, synthetic backend anchor, no DB import."""
    backend = tmp_path / "synthetic-backend"
    backend.mkdir()
    local = _extract_functions(
        LOCAL_PATHS_SOURCE, {"anchor_sqlite_url"},
        {"os": os, "Path": Path, "re": __import__("re"),
         "_BACKEND_ROOT": backend})
    anchor = local["anchor_sqlite_url"]
    # The database guard calls its local anchor helper. Inject the exact
    # extracted local helper with the synthetic backend root instead of
    # replacing the real ``core`` package in sys.modules.
    namespace = {
        "os": os,
        "_DATABASE_BACKEND_DIR": str(backend),
        "_anchor_sqlite_url": lambda value: anchor(value, backend),
    }
    _extract_functions(DB_SOURCE, {"_targets_live_dev_db"}, namespace)
    return backend, namespace["_targets_live_dev_db"], anchor


def test_plain_and_uri_live_targets_are_guarded(guard_functions):
    backend, guarded, _ = guard_functions
    targets = [
        f"sqlite:///{backend}/data/atom.db",
        f"sqlite:///{backend}/dev.db",
        f"sqlite:///file:{backend}/data/atom.db?mode=rw&uri=true",
        f"sqlite:///file:{backend}/dev.db?mode=ro&uri=true",
        f"sqlite:///file:{backend}/data/atom%2Edb?uri=true",
        f"sqlite:///file:{backend}/data%2Fatom.db?uri=true",
        f"sqlite:///file://localhost{backend}/data/atom.db?uri=true",
        f"sqlite+pysqlite:///{backend}/data/atom.db",
        f"sqlite+aiosqlite:///{backend}/data/atom.db",
        "sqlite:///data/atom.db",             # relative, backend-anchored
        "sqlite:///./data/atom.db",
        "sqlite:///dev.db",
        f"SQLITE:///{backend}/data/atom.db",
        f"SQLITE:///file:{backend}/data/atom.db?uri=true",
        "Sqlite+PySQLite:///./data/atom.db",
    ]
    for url in targets:
        assert guarded(url) is True, url


def test_uri_connect_args_really_target_the_live_file(guard_functions):
    backend, guarded, _ = guard_functions
    uri = f"sqlite:///file:{backend}/data/atom.db?mode=rw&uri=true"
    args, kwargs = SQLiteDialect_pysqlite().create_connect_args(make_url(uri))
    assert args[0].startswith(f"file:{backend}/data/atom.db")
    assert kwargs.get("uri") is True
    assert guarded(uri) is True


def test_named_memory_scratch_and_non_sqlite_are_not_guarded(guard_functions):
    backend, guarded, _ = guard_functions
    targets = [
        "sqlite:///:memory:",
        "sqlite://",
        f"sqlite:///file:{backend}/scratch.db?mode=rw&uri=true",
        f"sqlite:///file:{backend}/data/scratch.db?uri=true",
        "sqlite:////tmp/scratch-atom.db",
        "sqlite:///file:memdb1?mode=memory&cache=shared&uri=true",
        "sqlite:///file::memory:?cache=shared&uri=true",
        "sqlite:///file:scratch-relative.db?uri=true",
        "postgresql://localhost/atom",
        "redis://localhost:6379/1",
        "",
    ]
    for url in targets:
        assert guarded(url) is False, url


GET_DATABASE_URL_CHILD = r"""
import json, os
import core.database as db

db._DATABASE_BACKEND_DIR = os.environ["SYNTH_BACKEND"]
probe_testing = os.environ.pop("PROBE_TESTING", "")
if probe_testing:
    os.environ["TESTING"] = probe_testing
else:
    os.environ.pop("TESTING", None)
os.environ["PYTEST_CURRENT_TEST"] = "synthetic-uri-guard-test"
os.environ["DATABASE_URL"] = os.environ["PROBE_DATABASE_URL"]
url = db.get_database_url()
print("RESULT:" + json.dumps({"url": url, "live_exists": os.path.exists(
    os.path.join(os.environ["SYNTH_BACKEND"], "data", "atom.db"))}))
"""


def _run_get_database_url(tmp_path, database_url: str, testing: str | None) -> dict:
    backend = tmp_path / "synthetic-backend"
    backend.mkdir(exist_ok=True)
    scratch = tmp_path / "scratch"
    scratch.mkdir(exist_ok=True)
    env = os.environ.copy()
    for key in (
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
        "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY", "GEMINI_API_KEY",
        "GROQ_API_KEY", "TOGETHER_API_KEY", "OPENCODE_API_KEY",
        "MISTRAL_API_KEY", "XAI_API_KEY", "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT", "TELEGRAM_BOT_TOKEN",
        "OUTLOOK_CLIENT_ID", "OUTLOOK_CLIENT_SECRET",
        "MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET",
        "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
        "SHOPIFY_WEBHOOK_SECRET",
    ):
        env[key] = ""
    env.update({
        "PYTHONPATH": str(BACKEND),
        "TESTING": "0",
        "ENVIRONMENT": "development",
        "DATABASE_URL": f"sqlite:///{scratch / 'bootstrap.db'}",
        "ATOM_DATA_DIR": str(scratch / "data"),
        "LANCEDB_URI": str(scratch / "lancedb"),
        "LANCEDB_URI_BASE": str(scratch / "lancedb"),
        "BYOK_CONFIG_FILE": str(scratch / "byok.json"),
        "BYOK_KEYS_FILE": str(scratch / "keys.json"),
        "BYOK_ENC_KEY_FILE": str(scratch / "enc.key"),
        "SECRET_KEY": "synthetic-uri-guard-secret",
        "SYNTH_BACKEND": str(backend),
        "PROBE_DATABASE_URL": database_url,
        "PROBE_TESTING": testing or "",
    })
    script = tmp_path / "get_database_url_child.py"
    script.write_text(GET_DATABASE_URL_CHILD)
    result = subprocess.run(
        [sys.executable, str(script)], cwd=str(tmp_path), env=env,
        capture_output=True, text=True, timeout=120, check=False)
    assert result.returncode == 0, (result.stdout, result.stderr)
    for line in result.stdout.splitlines():
        if line.startswith("RESULT:"):
            return json.loads(line.split("RESULT:", 1)[1])
    raise AssertionError((result.stdout, result.stderr))


def test_protected_uri_is_forced_to_scratch_by_pytest_guard(tmp_path):
    backend = tmp_path / "synthetic-backend"
    protected_uri = (
        f"sqlite:///file:{backend}/data/atom.db?mode=rw&uri=true")
    result = _run_get_database_url(tmp_path, protected_uri, testing=None)
    assert result["url"] == f"sqlite:///{backend}/test_integration.db"
    assert result["live_exists"] is False


def test_valid_absolute_scratch_uri_remains_eligible(tmp_path):
    backend = tmp_path / "synthetic-backend"
    scratch_uri = f"sqlite:///file:{backend}/scratch-jobs.db?mode=rw&uri=true"
    result = _run_get_database_url(tmp_path, scratch_uri, testing=None)
    assert result["url"] == scratch_uri
    assert result["live_exists"] is False


def test_testing_zero_opt_out_with_scratch_uri_is_preserved(tmp_path):
    backend = tmp_path / "synthetic-backend"
    scratch_uri = f"sqlite:///file:{backend}/scratch-jobs.db?uri=true"
    result = _run_get_database_url(tmp_path, scratch_uri, testing="0")
    assert result["url"] == scratch_uri


def test_testing_one_forces_scratch_even_for_protected_uri(tmp_path):
    backend = tmp_path / "synthetic-backend"
    protected_uri = (
        f"sqlite:///file:{backend}/data/atom.db?mode=rw&uri=true")
    result = _run_get_database_url(tmp_path, protected_uri, testing="1")
    assert result["url"] == f"sqlite:///{backend}/test_integration.db"


def _isolated_handler():
    node = next(
        node for node in ast.walk(ast.parse(MAIN_SOURCE))
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "scheduler_store_unavailable_handler")
    node.decorator_list = []
    logger = MagicMock()
    namespace = {
        "Request": Request,
        "SchedulerStoreUnavailable": RuntimeError,
        "JSONResponse": JSONResponse,
        "logger": logger,
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]),
                 "<exact-source-scheduler-handler>", "exec"), namespace)
    return namespace[node.name], logger


def test_scheduler_unavailable_response_is_generic_and_503():
    handler, logger = _isolated_handler()
    marker = "synthetic-private-startup-error-marker"
    app = FastAPI()
    app.add_exception_handler(RuntimeError, handler)

    @app.get("/api/v1/workflows/scheduler/jobs")
    def probe():
        raise RuntimeError(marker)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/workflows/scheduler/jobs")

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "SCHEDULER_STORE_UNAVAILABLE"
    assert "temporarily unavailable" in body["detail"]
    assert marker not in response.text
    assert "scheduler storage" in body["detail"]
    # Detailed diagnostics stay server-side.
    logger.error.assert_called_once()
    assert marker in str(logger.error.call_args)


def test_scheduler_unavailable_response_does_not_reflect_paths_or_reason():
    handler, logger = _isolated_handler()
    reason = "both canonical (/synthetic/private/jobs.sqlite) and legacy exist"
    app = FastAPI()
    app.add_exception_handler(RuntimeError, handler)

    @app.get("/probe")
    def probe():
        raise RuntimeError(reason)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/probe")

    assert response.status_code == 503
    assert "/synthetic/private" not in response.text
    assert "both canonical" not in response.text
    assert "SCHEDULER_STORE_UNAVAILABLE" in response.text
    logger.error.assert_called_once()
