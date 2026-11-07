"""Focused preparation tests for the ordinary-UI source-answer driver.

These tests validate the authored source episode against the real ReActStep
schema and the existing provider_shim index. They do not launch a world,
browser, model or provider.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DRIVER_PATH = REPO / "scripts" / "acceptance" / (
    "browser_agent_source_answer.py")


def _load_driver():
    spec = importlib.util.spec_from_file_location(
        "browser_agent_source_answer", DRIVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def driver():
    return _load_driver()


def _variant(driver, tmp_path: Path, mutate) -> Path:
    doc = json.loads(driver.FIXTURE.read_text(encoding="utf-8"))
    mutate(doc)
    path = tmp_path / "source_fixture_variant.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_authored_source_fixture_is_valid_and_content_gated(driver, tmp_path):
    result = driver._validate_source_fixture(tmp_path)
    assert result["response_count"] == 3
    assert result["source_marker"] == "UI-SOURCE-AUTH-7F3C"
    assert result["source_action_gated_on_marker"] is True
    assert result["final_gated_on_oracle"] is True
    assert result["provider_shim_bare_fallback"] is True
    assert result["default_labelled"] is True
    steps = result["parsed_steps"]
    assert steps[0]["kind"] == "final_answer"
    assert steps[1]["kind"] == "action"
    assert steps[2]["kind"] == "information_wait"


def test_action_without_source_marker_is_rejected(driver, tmp_path):
    def mutate(doc):
        doc["responses"][1]["match"] = "AUTHORIZED SOURCE EVIDENCE"
    path = _variant(driver, tmp_path, mutate)
    original = driver.FIXTURE
    driver.FIXTURE = path
    try:
        with pytest.raises(driver.PreflightError, match="source content marker"):
            driver._validate_source_fixture(tmp_path)
    finally:
        driver.FIXTURE = original


def test_wait_before_action_is_rejected(driver, tmp_path):
    def mutate(doc):
        responses = doc["responses"]
        doc["responses"] = [responses[2], responses[0], responses[1]]
    path = _variant(driver, tmp_path, mutate)
    original = driver.FIXTURE
    driver.FIXTURE = path
    try:
        with pytest.raises(driver.PreflightError, match="script order"):
            driver._validate_source_fixture(tmp_path)
    finally:
        driver.FIXTURE = original


def test_unlabelled_shim_default_is_rejected(driver, tmp_path):
    def mutate(doc):
        doc["default"] = "no match"
    path = _variant(driver, tmp_path, mutate)
    original = driver.FIXTURE
    driver.FIXTURE = path
    try:
        with pytest.raises(driver.PreflightError, match="not labelled"):
            driver._validate_source_fixture(tmp_path)
    finally:
        driver.FIXTURE = original


def test_source_ref_binds_only_typed_identity(driver):
    assert driver._source_ref({
        "document_id": "doc-1",
        "source_version": "ev4:abc",
        "path": "/tmp/not-authority",
        "file_name": "ignored.txt",
    }) == {"document_id": "doc-1", "source_version": "ev4:abc"}


def _body_sha(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _post(path, key, *, from_key=None, to_key=None, body="controlled objective",
          op=None, origin="http://localhost:3000", method="POST"):
    return {
        "path": path,
        "method": method,
        "origin": origin,
        "operation_id": op,
        "body_sha256": _body_sha(body),
        "request_key": key,
        "redirected_from_key": from_key,
        "redirected_to_key": to_key,
    }


def _resp(path, key, status, *, location="", origin="http://localhost:3000",
          method="POST"):
    return {
        "path": path,
        "status": status,
        "method": method,
        "origin": origin,
        "location": location,
        "request_key": key,
    }


def _success(key, path, status=202):
    return {
        "status": status,
        "path": path,
        "origin": "http://localhost:3000",
        "method": "POST",
        "request_key": key,
        "job_id": "job-1",
        "execution_id": "exec-1",
    }


def test_run_classifier_accepts_one_canonical_admission(driver):
    result = driver._classify_run_admissions(
        [_post("/api/agents/a/run", "A")],
        [_resp("/api/agents/a/run", "A", 202)],
        _success("A", "/api/agents/a/run"),
    )
    assert result["ok"] is True
    assert result["logical_admissions"] == 1
    assert result["redirect_hops"] == 0
    assert result["raw_run_post_count"] == 1


def test_run_classifier_collapses_one_307_hop(driver):
    posts = [
        _post("/api/agents/a/run/", "A", to_key="B"),
        _post("/api/agents/a/run", "B", from_key="A"),
    ]
    responses = [
        _resp("/api/agents/a/run/", "A", 307,
              location="/api/agents/a/run"),
        _resp("/api/agents/a/run", "B", 202),
    ]
    result = driver._classify_run_admissions(
        posts, responses, _success("B", "/api/agents/a/run"))
    assert result["ok"] is True
    assert result["logical_admissions"] == 1
    assert result["redirect_hops"] == 1
    assert result["raw_run_post_count"] == 2
    assert result["redirect_edges"][0]["status"] == 307


def test_run_classifier_refutes_two_independent_admissions(driver):
    posts = [
        _post("/api/agents/a/run", "A"),
        _post("/api/agents/a/run", "B"),
    ]
    responses = [
        _resp("/api/agents/a/run", "A", 202),
        _resp("/api/agents/a/run", "B", 202),
    ]
    result = driver._classify_run_admissions(
        posts, responses, _success("A", "/api/agents/a/run"))
    assert result["ok"] is False
    assert result["logical_admissions"] == 2
    assert result["reason"] == "not_one_logical_admission"


def test_run_classifier_refutes_foreign_redirect(driver):
    posts = [
        _post("/api/agents/a/run/", "A", to_key="B"),
        _post("/api/agents/a/run", "B", from_key="A",
              origin="https://evil.example"),
    ]
    responses = [
        _resp("/api/agents/a/run/", "A", 307,
              location="https://evil.example/api/agents/a/run"),
        _resp("/api/agents/a/run", "B", 202,
              origin="https://evil.example"),
    ]
    result = driver._classify_run_admissions(
        posts, responses, _success("B", "/api/agents/a/run"))
    assert result["ok"] is False
    assert result["invalid_edges"][0]["reason"] == "redirect_origin_changed"


def test_run_classifier_refutes_changed_body_agent_or_operation(driver):
    for label, child in {
        "body": _post("/api/agents/a/run", "B", from_key="A",
                      body="different objective"),
        "agent": _post("/api/agents/b/run", "B", from_key="A"),
        "operation": _post("/api/agents/a/run", "B", from_key="A",
                           op="different-operation"),
    }.items():
        posts = [_post("/api/agents/a/run/", "A", to_key="B"), child]
        responses = [
            _resp("/api/agents/a/run/", "A", 307,
                  location="/api/agents/a/run"),
            _resp(child["path"], "B", 202),
        ]
        result = driver._classify_run_admissions(
            posts, responses, _success("B", child["path"]))
        assert result["ok"] is False, label
        assert result["invalid_edges"], label


def test_run_classifier_refutes_non_307_redirect(driver):
    posts = [
        _post("/api/agents/a/run/", "A", to_key="B"),
        _post("/api/agents/a/run", "B", from_key="A"),
    ]
    responses = [
        _resp("/api/agents/a/run/", "A", 301,
              location="/api/agents/a/run"),
        _resp("/api/agents/a/run", "B", 202),
    ]
    result = driver._classify_run_admissions(
        posts, responses, _success("B", "/api/agents/a/run"))
    assert result["ok"] is False
    assert result["invalid_edges"][0]["reason"] == \
        "redirect_status_not_307_308"

