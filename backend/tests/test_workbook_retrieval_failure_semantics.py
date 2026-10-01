# -*- coding: utf-8 -*-
"""A source that would not read must not be reported as an absence.

Acceptance case ``11_forced_retrieval_failure`` corrupts every parquet copy of
a workbook and found the answer saying "no matching row in the indexed content
searched" — an I/O error laundered into a confident negative. These tests
pin the three states apart on REAL corrupted bytes (not mocks):

    read_failed   the source would not open  -> report the failure
    absent        the source opened, no row  -> the honest absence sentence
    never_searched  nothing to scan          -> unverified, never "absent"

WHAT THESE TESTS DO NOT DO: none of them asserts merely "no exception was
raised". A broad ``except`` around the scan is exactly what hid this defect —
the scan never raised, it silently produced an empty result and the empty
result was rendered as an absence. Every assertion below is on the WORDS and
FLAGS the user and the model receive.

The failure wording is deliberately asserted against the acceptance case's own
vocabulary ("could not be read" / "unreadable" / "retrieval failed" /
"scan failed" / "source error") and its absence vocabulary ("no matching"),
so a regression here fails the same check the live acceptance run fails.
"""
from __future__ import annotations

import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest

pd = pytest.importorskip("pandas")

from core import answer_presentation as ap  # noqa: E402
from core.workbook_read_artifact import (  # noqa: E402
    inspect_dataset_entries,
    render_workbook_artifact,
)

FILE_NAME = "Synthetic Price List.xlsx"
PRESENT_TARGET = "M-1"
ABSENT_TARGET = "M-404"

# The acceptance case's own predicates (live_integration_acceptance.py).
UNREADABLE_MARKERS = (
    "could not be read", "unreadable", "source error", "retrieval failed",
    "scan failed",
)
ABSENCE_MARKERS = ("no matching",)

CORRUPT_BYTES = b"CORRUPTED-PARQUET-FOR-RETRIEVAL-FAILURE-INJECTION"


@pytest.fixture
def clean_copy(tmp_path):
    """A real, readable sheet parquet plus its catalog entry."""
    path = tmp_path / "SheetA.parquet"
    frame = pd.DataFrame({
        "Model": [PRESENT_TARGET, "M-2"],
        "PRICE": ["10", "20"],
        "__sheet_row": [1, 2],
    })
    frame.to_parquet(path, index=False)
    return {
        "parquet_path": str(path),
        "entity_name": "SheetA",
        "file_name": FILE_NAME,
        "row_count": 2,
        "coverage": {"known": True, "truncated": False},
        "columns": ["Model", "PRICE"],
    }


@pytest.fixture
def corrupted_copy(clean_copy, tmp_path):
    """The same catalog entry, pointed at bytes that are not a parquet.

    The ORIGINAL bytes are restored in the fixture teardown and the restore is
    hash-verified, mirroring the acceptance case's restore machinery: a test
    that leaves a corrupted fixture behind poisons every later run.
    """
    path = clean_copy["parquet_path"]
    with open(path, "rb") as handle:
        original = handle.read()
    digest = hashlib.sha256(original).hexdigest()
    entry = dict(clean_copy)
    corrupt_path = tmp_path / "SheetA.corrupt.parquet"
    corrupt_path.write_bytes(CORRUPT_BYTES)
    entry["parquet_path"] = str(corrupt_path)
    try:
        yield entry
    finally:
        with open(path, "wb") as handle:
            handle.write(original)
        with open(path, "rb") as handle:
            assert hashlib.sha256(handle.read()).hexdigest() == digest


def _scan(entries, targets):
    return inspect_dataset_entries(
        entries, FILE_NAME, targets=targets, requested_fields=["price"],
        provider="datasets", resource_id="res-1",
    )


def _outcomes(artifact, target):
    for outcome in (artifact.get("coverage") or {}).get("outcomes") or []:
        if outcome.get("target") == target:
            return outcome
    raise AssertionError(f"no outcome for {target}: {artifact}")


def _record(artifact, targets, evidence_action):
    """The producer's structured record, built exactly as the planner does."""
    outcomes = {
        outcome["target"]: outcome
        for outcome in (artifact.get("coverage") or {}).get("outcomes") or []
    }
    coverage = dict(artifact.get("coverage_limits") or {})
    coverage.update({
        "indexed_sheets": len(artifact.get("sheets") or []),
        "scanned_sheets": (artifact.get("coverage_limits") or {}).get(
            "sheets_scanned"),
    })
    return ap.build_structured_record(
        source_identity={"file_name": FILE_NAME,
                         "ingested_at": "2026-09-07",
                         "live_vs_saved": "saved copy"},
        evidence_revision=f"{FILE_NAME}:2026-09-07",
        attempt_id=ap.new_attempt_id(),
        evidence_action=evidence_action,
        requested_items=list(targets),
        requested_fields=["price"],
        targets=ap.build_targets_from_scan(list(targets), outcomes, {}),
        coverage=coverage,
    )


class TestCorruptedSourceIsAFailureNotAnAbsence:
    """(a) the failure is reported, (b) absence wording is NOT used."""

    def test_scan_reports_a_failed_read_leg_with_a_category(self, corrupted_copy):
        artifact = _scan([corrupted_copy], [PRESENT_TARGET, ABSENT_TARGET])
        coverage = artifact["coverage"]

        assert coverage["read_status"] == "failed", coverage
        assert coverage["absence_claimable"] is False
        leg = coverage["read_legs"]["SheetA"]
        assert leg["status"] == "failed"
        assert leg["error_category"], "a failed leg must name a category"
        assert leg["rows_read"] == 0
        # The raw reader message may carry the path and library internals; it
        # is classified, never forwarded.
        assert CORRUPT_BYTES.decode() not in repr(coverage)
        assert "ArrowInvalid" not in repr(coverage)

    def test_target_with_no_evidence_is_unavailable_not_absent(self, corrupted_copy):
        artifact = _scan([corrupted_copy], [PRESENT_TARGET, ABSENT_TARGET])
        outcome = _outcomes(artifact, PRESENT_TARGET)

        assert outcome["status"] == "unavailable", outcome
        assert outcome["evidence"] == []
        assert outcome["absence_claimable"] is False
        assert outcome["error_category"]
        assert artifact["coverage"]["complete"] is False

    def test_absence_wording_never_appears_in_the_answer(self, corrupted_copy):
        artifact = _scan([corrupted_copy], [PRESENT_TARGET, ABSENT_TARGET])
        record = _record(artifact, [PRESENT_TARGET, ABSENT_TARGET],
                         "read_failed")
        answer = ap.present_from_record(record)["answer"]
        lowered = answer.lower()

        assert "no matching" not in lowered, answer
        assert not any(marker in lowered for marker in ABSENCE_MARKERS), answer
        # No value may be invented for bytes nobody read.
        assert "10" not in answer and "20" not in answer, answer

    def test_every_item_line_names_the_failure(self, corrupted_copy):
        """One honest line per item: a mixed answer that still prints the
        absence sentence for a failed read is the defect, not a partial fix."""
        artifact = _scan([corrupted_copy], [PRESENT_TARGET, ABSENT_TARGET])
        record = _record(artifact, [PRESENT_TARGET, ABSENT_TARGET],
                         "read_failed")

        for style in ("default", "compact", "table"):
            answer = ap.present(
                requested_items=record["requested_items"],
                requested_fields=record["requested_fields"],
                source={"file_name": FILE_NAME,
                        "saved_copy_date": "2026-09-07",
                        "live_vs_saved": "saved copy",
                        "coverage": record["coverage"]},
                targets=record["targets"], style=style,
            )["answer"]
            lowered = answer.lower()
            assert "no matching" not in lowered, (style, answer)
            assert any(m in lowered for m in UNREADABLE_MARKERS), (style, answer)
            for item in record["requested_items"]:
                assert item.lower() in lowered, (style, item, answer)

    def test_model_visible_block_does_not_claim_an_absence(self, corrupted_copy):
        """The block the reply model reads is where a wrong negative is born."""
        artifact = _scan([corrupted_copy], [PRESENT_TARGET])
        block = render_workbook_artifact(artifact).lower()

        assert "no matching" not in block, block
        assert "unavailable" in block, block
        assert "source_corrupt" in block, block

    def test_read_failed_record_names_a_legible_reason(self):
        """Even a record stamped read_failed with NO coverage detail (an
        unobserved scan) must say the source could not be read, not merely
        'did not complete'."""
        record = ap.build_structured_record(
            source_identity={"file_name": FILE_NAME},
            evidence_revision="rev", attempt_id=ap.new_attempt_id(),
            evidence_action="read_failed", requested_items=[PRESENT_TARGET],
            requested_fields=["price"],
            targets=ap.build_targets_from_scan([PRESENT_TARGET], {}, {}),
            coverage={},
        )
        answer = ap.present_from_record(record)["answer"].lower()

        assert "did not complete" in answer
        assert "could not be read" in answer, answer
        assert "no matching" not in answer, answer


class TestLegitimateAbsenceIsNotRegressed:
    """(c) a clean source with a genuinely missing target still says so."""

    def test_absent_target_on_a_readable_source_keeps_the_absence_sentence(
            self, clean_copy):
        artifact = _scan([clean_copy], [PRESENT_TARGET, ABSENT_TARGET])

        assert artifact["coverage"]["read_status"] == "success"
        assert artifact["coverage"]["absence_claimable"] is True
        assert _outcomes(artifact, ABSENT_TARGET)["status"] == "absent"

        record = _record(artifact, [PRESENT_TARGET, ABSENT_TARGET],
                         "new_read")
        answer = ap.present_from_record(record)["answer"]

        assert "no match in this copy" in answer
        assert "could not be read" not in answer.lower(), answer
        # The present item still answers — the failure path must not swallow
        # readable evidence.
        assert "M-1" in answer and "10" in answer, answer

    def test_present_target_is_unaffected_by_the_new_verdict(self, clean_copy):
        artifact = _scan([clean_copy], [PRESENT_TARGET])
        outcome = _outcomes(artifact, PRESENT_TARGET)

        assert outcome["status"] == "found"
        assert "absence_claimable" not in outcome
        targets = ap.build_targets_from_scan(
            [PRESENT_TARGET],
            {PRESENT_TARGET: outcome}, {})
        assert targets[0]["retrieval"]["status"] == "searched"

    def test_partial_read_is_not_an_absence_either(self, clean_copy, tmp_path):
        """One damaged sheet beside a readable one: the readable row answers,
        and the missing item reports the failure instead of a negative."""
        broken = dict(clean_copy)
        broken["parquet_path"] = str(tmp_path / "SheetB.parquet")
        with open(broken["parquet_path"], "wb") as handle:
            handle.write(CORRUPT_BYTES)
        broken["entity_name"] = "SheetB"

        artifact = _scan([clean_copy, broken], [PRESENT_TARGET, ABSENT_TARGET])

        assert artifact["coverage"]["read_status"] == "partial"
        assert artifact["coverage"]["absence_claimable"] is False
        # The readable row still answers (a partial read keeps its evidence);
        # only the item nothing could be read for reports the failure.
        assert _outcomes(artifact, PRESENT_TARGET)["evidence"]
        assert _outcomes(artifact, ABSENT_TARGET)["status"] == "unavailable"

        record = _record(artifact, [PRESENT_TARGET, ABSENT_TARGET],
                         "new_read")
        answer = ap.present_from_record(record)["answer"]

        assert "no matching" not in answer.lower(), answer
        assert "10" in answer, answer
        # The source-level verdict is stated once, for the whole answer.
        assert "I couldn't read the source" in answer, answer


class TestErrorCategoryVocabulary:
    def test_corrupt_parquet_is_classified_as_source_corrupt(self):
        from core.hybrid_search.documents_hybrid import error_category

        assert error_category(
            RuntimeError("Parquet magic bytes not found in footer")) \
            == "source_corrupt"

    @pytest.mark.parametrize("payload", [
        CORRUPT_BYTES,
        b"",
        b"BAD",
        b"hello world, definitely not a columnar file",
    ])
    def test_real_reader_failures_classify_as_source_corrupt(self, tmp_path,
                                                             payload):
        """The CATEGORY comes from the exception the real reader raises, and a
        truncated-to-nothing parquet says none of the usual corruption words —
        it must still be recognised as damage, not as 'we do not know'."""
        from core.hybrid_search.documents_hybrid import error_category

        path = tmp_path / "damage.parquet"
        path.write_bytes(payload)
        with pytest.raises(Exception) as raised:
            pd.read_parquet(path)

        assert error_category(raised.value) == "source_corrupt", raised.value

    def test_the_classifier_still_keeps_the_older_categories(self):
        from core.hybrid_search.documents_hybrid import (
            ERROR_CORRUPT,
            ERROR_MISSING,
            ERROR_PERMISSION,
            ERROR_TIMEOUT,
            ERROR_UNAVAILABLE,
            error_category,
        )

        assert error_category(FileNotFoundError("nope")) == ERROR_MISSING
        assert error_category(PermissionError("denied")) == ERROR_PERMISSION
        assert error_category(ConnectionError("refused")) == ERROR_UNAVAILABLE
        assert error_category(TimeoutError()) == ERROR_TIMEOUT
        assert error_category(
            RuntimeError("postgres://user:hunter2@10.0.0.5 refused")) == "unknown"
        assert ERROR_CORRUPT == "source_corrupt"

    def test_a_broad_except_never_reaches_the_caller(self, corrupted_copy):
        """The scan must not raise, and must not swallow the failure into an
        empty result either. ``unavailable`` IS the observation; a test that
        only checked 'no exception' would pass on the original defect."""
        artifact = _scan([corrupted_copy], [ABSENT_TARGET])
        outcome = _outcomes(artifact, ABSENT_TARGET)

        assert outcome["status"] == "unavailable"
        assert outcome["evidence"] == []
        assert artifact["all_sheets_searched"] is False
        assert artifact["truncated"] is True
