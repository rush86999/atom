"""Focused preparation tests for the ordinary-UI source-answer driver.

These tests validate the authored source episode against the real ReActStep
schema and the existing provider_shim index. They do not launch a world,
browser, model or provider.
"""
from __future__ import annotations

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
