"""Focused regression for the invoice observer's uploaded-source identity.

On the verified-auth.8b2nWt/run7 scratch world the browser uploaded
``invoice-partial.json`` (HTTP 200) and the product persisted a
``document.text`` step whose ``inputs.resource_binding`` named the uploaded
document and whose ``inputs.path`` was the canonical ``office/uploads`` file.
The observer instead waited for ``inputs.path == <fixture path>``, so it
timed out against a fully accepted upload.

These tests pin the observer to the identity the mounted upload action
actually returned, require the canonical uploaded path, and fail closed on a
fixture path or an incomplete identity.
"""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DRIVER_PATH = REPO / "scripts" / "acceptance" / (
    "browser_invoice_partial_evidence.py")

# The real persisted identity from the run7 scratch SQLite.
PARTIAL_ID = "doc_818f5b1a9eaf1d47e78e50e0"
PARTIAL_VERSION = (
    "ev4:9643a7193276e99157204d6dc3f4d11c18edd04b08870658e3cb2e82e9e8d811")
ACTOR_ID = "d3b19cb2-ea39-4475-8b99-3fd2aa708191"
PARTIAL_SIZE = 134


def _load_driver():
    spec = importlib.util.spec_from_file_location(
        "browser_invoice_partial_evidence_observer", DRIVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def driver():
    return _load_driver()


def _upload_body(
        *,
        doc_id: str = PARTIAL_ID,
        file_name: str = "invoice-partial.json",
        version: str = PARTIAL_VERSION,
        size: int = PARTIAL_SIZE) -> dict:
    return {
        "id": doc_id,
        "title": file_name,
        "type": "application/json",
        "metadata": {
            "source": "upload",
            "size": size,
            "title": file_name,
            "filename": file_name,
            "file_type": "json",
            "doc_id": doc_id,
            "pg_document_id": doc_id,
            "integration_id": "manual_upload",
            "source_content_hash": version,
        },
        "ingested_at": "2026-11-13T04:02:30",
        "chunk_count": 1,
    }


def _identity(driver, **overrides):
    body = _upload_body(**overrides)
    return driver._uploaded_source_identity(
        body, expected_file_name=body["metadata"]["filename"])


def _binding(identity: dict) -> dict:
    return {
        "resource_id": identity["document_id"],
        "dataset_name": None,
        "source": identity["source"],
        "source_kind": None,
        "external_id": identity["external_id"],
        "original_file_name": identity["file_name"],
        "representation": "document_text",
        "source_version": identity["source_version"],
        "sheet": None,
        "columns": [],
        "numeric_columns": [],
        "row_count": None,
        "coverage": {
            "known": True,
            "freshness": "fresh",
            "file_size_bytes": identity["file_size_bytes"],
        },
        "access_scope": {
            "user_id": ACTOR_ID,
            "workspace_id": "default",
            "tenant_id": "default",
        },
        "workspace_id": "default",
        "tenant_id": None,
        "internal_fixture": False,
    }


def _uploaded_step(
        identity: dict, upload_root: Path, *,
        step_id: str = "source-3", path: str = "") -> dict:
    canonical = Path(upload_root) / (
        f"{identity['document_id']}.{identity['file_type']}")
    return {
        "step_id": step_id,
        "adapter": "document.text",
        "status": "applied",
        "inputs": {
            "resource_binding": _binding(identity),
            "path": path or str(canonical),
        },
        "result": {
            "resource_id": identity["document_id"],
            "source_version": identity["source_version"],
            "verification": {
                "status": "verified",
                "resource_id": identity["document_id"],
                "version": identity["source_version"],
            },
        },
    }


def _prepare_upload_file(identity: dict, upload_root: Path) -> None:
    upload_root.mkdir(parents=True, exist_ok=True)
    (upload_root / (
        f"{identity['document_id']}.{identity['file_type']}")).write_text(
            "{}", encoding="utf-8")


def test_uploaded_identity_matches_but_fixture_path_does_not(
        driver, tmp_path):
    identity = _identity(driver)
    upload_root = tmp_path / "data" / "office" / "uploads"
    _prepare_upload_file(identity, upload_root)

    step = _uploaded_step(identity, upload_root)
    assert driver._source_identity_mismatches(
        step, identity, upload_root=upload_root, user_id=ACTOR_ID) == []
    assert driver._accepted_source_step(
        {"steps": [step]}, identity,
        upload_root=upload_root, user_id=ACTOR_ID) is step

    fixture_path = tmp_path / "invoice_fixtures" / "invoice-partial.json"
    fixture_step = _uploaded_step(
        identity, upload_root, path=str(fixture_path))
    assert driver._source_identity_mismatches(
        fixture_step, identity,
        upload_root=upload_root, user_id=ACTOR_ID) == [
            "inputs.path_canonical"]
    assert driver._accepted_source_step(
        {"steps": [fixture_step]}, identity,
        upload_root=upload_root, user_id=ACTOR_ID) is None


def test_missing_or_wrong_identity_fails_closed(driver, tmp_path):
    identity = _identity(driver)
    upload_root = tmp_path / "data" / "office" / "uploads"
    _prepare_upload_file(identity, upload_root)

    def drop_binding(step):
        step["inputs"].pop("resource_binding")

    def wrong_resource(step):
        step["inputs"]["resource_binding"]["resource_id"] = "doc_other"

    def wrong_name(step):
        step["inputs"]["resource_binding"][
            "original_file_name"] = "other.json"

    def wrong_version(step):
        step["inputs"]["resource_binding"]["source_version"] = "ev4:other"

    def claims_fixture(step):
        step["inputs"]["resource_binding"]["internal_fixture"] = True

    def wrong_size(step):
        step["inputs"]["resource_binding"]["coverage"][
            "file_size_bytes"] += 1

    def wrong_user(step):
        step["inputs"]["resource_binding"]["access_scope"][
            "user_id"] = "someone-else"

    def missing_verification(step):
        step["result"].pop("verification")

    def empty_path(step):
        step["inputs"]["path"] = ""

    def parked_source(step):
        step["status"] = "waiting"

    cases = [
        (drop_binding, "resource_binding"),
        (wrong_resource, "binding.resource_id"),
        (wrong_name, "binding.original_file_name"),
        (wrong_version, "binding.source_version"),
        (claims_fixture, "binding.internal_fixture"),
        (wrong_size, "binding.file_size_bytes"),
        (wrong_user, "binding.access_scope_user"),
        (missing_verification, "result.verification_status"),
        (empty_path, "inputs.path_canonical"),
        (parked_source, "step_status"),
    ]
    for mutate, expected in cases:
        step = _uploaded_step(identity, upload_root)
        mutate(step)
        mismatches = driver._source_identity_mismatches(
            step, identity, upload_root=upload_root, user_id=ACTOR_ID)
        assert expected in mismatches, (expected, mismatches)
        assert driver._accepted_source_step(
            {"steps": [step]}, identity,
            upload_root=upload_root, user_id=ACTOR_ID) is None


def test_missing_canonical_upload_file_fails_closed(driver, tmp_path):
    identity = _identity(driver)
    upload_root = tmp_path / "data" / "office" / "uploads"
    upload_root.mkdir(parents=True)

    step = _uploaded_step(identity, upload_root)
    mismatches = driver._source_identity_mismatches(
        step, identity, upload_root=upload_root, user_id=ACTOR_ID)
    assert mismatches == ["uploaded_file_present"]
    assert driver._accepted_source_step(
        {"steps": [step]}, identity,
        upload_root=upload_root, user_id=ACTOR_ID) is None


def test_both_uploads_are_matched_by_their_own_identity(driver, tmp_path):
    partial = _identity(driver)
    complete = _identity(
        driver,
        doc_id="doc_complete_invoice",
        file_name="invoice-complete.json",
        version="ev4:" + "c" * 64,
        size=155)
    upload_root = tmp_path / "data" / "office" / "uploads"
    _prepare_upload_file(partial, upload_root)
    _prepare_upload_file(complete, upload_root)

    partial_step = _uploaded_step(
        partial, upload_root, step_id="source-3")
    complete_step = _uploaded_step(
        complete, upload_root, step_id="source-4")
    assignment = {"steps": [partial_step, complete_step]}

    assert driver._accepted_source_step(
        assignment, partial,
        upload_root=upload_root, user_id=ACTOR_ID) is partial_step
    assert driver._accepted_source_step(
        assignment, complete,
        upload_root=upload_root, user_id=ACTOR_ID) is complete_step
    assert driver._accepted_source_step(
        {"steps": [partial_step]}, complete,
        upload_root=upload_root, user_id=ACTOR_ID) is None
    assert partial["document_id"] != complete["document_id"]
    assert partial["source_version"] != complete["source_version"]


def _body_variant(mutate):
    body = copy.deepcopy(_upload_body())
    mutate(body)
    return body


@pytest.mark.parametrize("mutate", [
    lambda body: body.pop("metadata"),
    lambda body: body["metadata"].update({"doc_id": "doc_other"}),
    lambda body: body["metadata"].update({"filename": ""}),
    lambda body: body["metadata"].update({"file_type": ""}),
    lambda body: body["metadata"].update({"integration_id": "upload"}),
    lambda body: body["metadata"].update({"source_content_hash": ""}),
    lambda body: body["metadata"].pop("size"),
    lambda body: body.update({"title": "different.json"}),
])
def test_upload_response_identity_must_be_complete(driver, mutate):
    with pytest.raises(driver.DriverError):
        driver._uploaded_source_identity(_body_variant(mutate))
