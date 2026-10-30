"""Negative controls for the deployment assignment acceptance validator."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))

from smoke_assignment import validate_assignment  # noqa: E402


def _assignment():
    return {
        "status": "completed",
        "deliverables": [{
            "deliverable_id": "del-document",
            "kind": "document",
            "required": True,
            "status": "applied",
            "sha256": "abc123",
            "artifact_path": "/tmp/artifact.docx",
        }],
        "sources": [{"binding": {"source_version": "v1"}}],
    }


def test_complete_assignment_passes():
    result = validate_assignment(_assignment(), "sum of Price: 10.00", "abc123", "10.00")
    assert result["ok"] is True


def test_incomplete_assignment_is_rejected():
    assignment = _assignment()
    assignment["status"] = "waiting"
    result = validate_assignment(assignment, "sum: 10.00", "abc123", "10.00")
    assert result["ok"] is False
    assert any("status=" in error for error in result["errors"])


def test_failed_deliverable_is_rejected():
    assignment = _assignment()
    assignment["deliverables"][0]["status"] = "failed"
    result = validate_assignment(assignment, "sum: 10.00", "abc123", "10.00")
    assert result["ok"] is False


def test_altered_artifact_hash_is_rejected():
    result = validate_assignment(_assignment(), "sum: 10.00", "different", "10.00")
    assert result["ok"] is False
    assert any("hash mismatch" in error for error in result["errors"])


def test_missing_artifact_is_rejected():
    result = validate_assignment(
        _assignment(), "", "", "10.00", artifact_exists=False)
    assert result["ok"] is False
    assert "artifact missing" in result["errors"]


def test_absent_provenance_is_rejected():
    assignment = _assignment()
    assignment["sources"] = []
    result = validate_assignment(assignment, "sum: 10.00", "abc123", "10.00")
    assert result["ok"] is False
    assert any("provenance" in error for error in result["errors"])


def test_expected_result_must_be_in_artifact():
    result = validate_assignment(_assignment(), "sum: 99.00", "abc123", "10.00")
    assert result["ok"] is False
    assert any("expected result" in error for error in result["errors"])
