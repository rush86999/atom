"""Identity fingerprints must not hash a truncated diagnostic projection."""
from __future__ import annotations

import pytest

from core.assignment_plan import (
    FINGERPRINT_VERSION,
    canonical_sha256,
    new_teaching_snapshot,
)


def test_versioned_fingerprint_is_current():
    assert FINGERPRINT_VERSION == 2


def test_string_difference_after_legacy_1000_chars():
    prefix = "x" * 1200
    first = canonical_sha256({"text": prefix + "A"})
    second = canonical_sha256({"text": prefix + "B"})
    assert first != second
    # The old lossy projection could not distinguish these.
    assert canonical_sha256(
        {"text": prefix + "A"}, version=1) == canonical_sha256(
        {"text": prefix + "B"}, version=1)


def test_difference_after_legacy_list_and_dict_limits():
    list_a = list(range(50)) + ["A"]
    list_b = list(range(50)) + ["B"]
    assert canonical_sha256({"rows": list_a}) != canonical_sha256(
        {"rows": list_b})
    assert canonical_sha256(
        {"rows": list_a}, version=1) == canonical_sha256(
        {"rows": list_b}, version=1)

    dict_a = {f"k{i}": i for i in range(50)}
    dict_b = dict(dict_a)
    dict_a["tail"] = "A"
    dict_b["tail"] = "B"
    assert canonical_sha256({"m": dict_a}) != canonical_sha256(
        {"m": dict_b})


def test_difference_after_legacy_depth_limit():
    def nested(tail: str):
        value = tail
        for _ in range(7):
            value = {"next": value}
        return value

    assert canonical_sha256({"v": nested("A")}) != canonical_sha256(
        {"v": nested("B")})
    assert canonical_sha256(
        {"v": nested("A")}, version=1) == canonical_sha256(
        {"v": nested("B")}, version=1)


def test_oversized_and_unsupported_identity_values_fail_explicitly():
    with pytest.raises(ValueError):
        canonical_sha256({"text": "x" * 100001})
    with pytest.raises(ValueError):
        canonical_sha256({"object": object()})


def test_teaching_snapshot_fingerprint_is_strict_and_versioned():
    first = new_teaching_snapshot(
        revision="r1", output_requirements={"tail": "x" * 1200 + "A"})
    second = new_teaching_snapshot(
        revision="r1", output_requirements={"tail": "x" * 1200 + "B"})
    assert first["fingerprint_version"] == 2
    assert first["fingerprint"] != second["fingerprint"]
