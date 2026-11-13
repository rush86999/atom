"""Focused preparation tests for the incomplete-invoice browser driver.

These validate the partial/complete invoice fixture and every authored
loopback completion against the real planning/adaptation schemas and the
existing provider_shim index. They do not create a world, launch a browser or
contact a provider.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DRIVER_PATH = REPO / "scripts" / "acceptance" / (
    "browser_invoice_partial_evidence.py")


def _load_driver():
    spec = importlib.util.spec_from_file_location(
        "browser_invoice_partial_evidence", DRIVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def driver():
    return _load_driver()


def test_partial_and_complete_invoice_fixture(driver, tmp_path):
    files = driver._write_fixture_files(tmp_path)
    partial = json.loads((tmp_path / driver.PARTIAL_NAME).read_text())
    complete = json.loads((tmp_path / driver.COMPLETE_NAME).read_text())
    assert partial["unit_price"] is None
    assert complete["unit_price"] == "42.50"
    assert files["expected_total"] == "140.25"
    assert partial["invoice_id"] == driver.INVOICE
    assert partial["po_id"] == driver.PO


def test_authored_shim_is_real_schema_and_indexed(driver):
    result = driver._validate_shim()
    assert len(result["responses"]) == 3
    assert result["responses"][0]["model"] == "WorkAdaptationProposal"
    assert result["responses"][0]["payload"]["decision"] == "replan"
    assert result["responses"][1]["payload"]["decision"] == "retain"
    assert result["responses"][2]["model"] == "EmployeeWorkProposal"
    assert (
        result["responses"][2]["payload"]["evidence_reads"][0]["source_id"]
        == "fixture:po.json")
    assert len(result["provider_shim_keys"]) == 3


def test_unlabelled_default_is_rejected(driver, tmp_path):
    doc = json.loads(driver.FIXTURE.read_text(encoding="utf-8"))
    doc["default"] = "plain fallback"
    path = tmp_path / "bad_shim.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    original = driver.FIXTURE
    driver.FIXTURE = path
    try:
        with pytest.raises(driver.PreflightError, match="not labelled"):
            driver._validate_shim()
    finally:
        driver.FIXTURE = original


def test_complete_evidence_requires_invoice_reconciliation(driver, tmp_path):
    doc = json.loads(driver.FIXTURE.read_text(encoding="utf-8"))
    payload = json.loads(doc["responses"][0]["response"])
    payload["decision"] = "retain"
    payload["work_request"] = None
    doc["responses"][0]["response"] = json.dumps(payload)
    path = tmp_path / "wrong_decision.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    original = driver.FIXTURE
    driver.FIXTURE = path
    try:
        with pytest.raises(driver.PreflightError, match="not a replan"):
            driver._validate_shim()
    finally:
        driver.FIXTURE = original
