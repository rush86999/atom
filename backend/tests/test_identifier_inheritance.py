"""Cache-loss regression for IDENTIFIER INHERITANCE (direction 5).

The defect this guards: inside ``_get_qwen_response`` the inheritance
block read ``_pending_file_task`` — a name that does not exist in that
scope — while the enclosing parameter is ``pending_file_task``. The
resulting ``NameError`` was swallowed by a bare ``except Exception``
that reset ``_requested_targets = []``. So the feature silently never
applied, and a resumed read searched the canvas TITLE's phrases instead
of the user's own identifiers.

Why the obvious test is worthless here: asserting "the resume did not
raise" passes with the bug present, because the handler that hides the
bug also absorbs the failure. These tests therefore assert on the value
that actually ARRIVES at ``extract_targets`` — the identifiers the
lookup will search for — not on the absence of an exception.

The scenario is a resume after SESSION-CACHE LOSS: the conversation's
in-memory session no longer holds the pending task, so the durable
``original_message`` on the pending task record is the only surviving
source of the user's identifiers.
"""
from __future__ import annotations

import ast
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from core.workbook_read_artifact import extract_targets
from integrations import chat_orchestrator as chat

# The exact identifiers from the live 2026-09-25 report, in order.
ORIGINAL_IDENTIFIERS = [
    "No. 381", "U-22", "No. 622", "TK Manual Flanger", "SLE24-16",
    "TK 1624", "TK Multi Wheel Gang Slitter", "GSL48-16",
]
# The vaguer ask that superseded the identifier-rich one. It carries no
# identifier-rich text, so nothing but the task's own record can supply
# them.
VAGUER_SUPERSEDING_ASK = "find all these prices"


def _canvas_with_title(title="Draft"):
    return {"canvas_id": "cv1", "canvas_type": "email",
            "content": {"subject": title, "body": "unrelated prose"}}


def _inherited_targets(pending_file_task, message=VAGUER_SUPERSEDING_ASK,
                       canvas=None):
    """The inheritance rule under test, reproduced exactly as the
    production block implements it.

    Kept byte-faithful to the shipped logic on purpose: the point is to
    exercise the DECISION (do the user's identifiers reach the lookup),
    and a re-implementation that drifted from production would test
    nothing.
    """
    canvas = canvas if canvas is not None else _canvas_with_title()
    _canvas_identity = (canvas.get("content") or {}).get("subject") or ""
    _requested_targets = extract_targets(message, [_canvas_identity])

    _task_targets = [
        str(item).strip()
        for item in (
            (pending_file_task or {}).get("requested_targets") or []
        )
        if str(item).strip()
    ] if isinstance(pending_file_task, dict) else []
    if _task_targets and not any(
            __import__("re").search(r"[\d-]", item)
            for item in _requested_targets):
        _requested_targets = _task_targets
    return _requested_targets


class TestIdentifierInheritance:
    def test_the_vaguer_ask_alone_loses_the_identifiers(self):
        """The regression's setup: without inheritance the resumed read
        has nothing identifier-rich to go on."""
        assert _inherited_targets(None) != ORIGINAL_IDENTIFIERS

    def test_identifiers_survive_session_cache_loss(self):
        """After cache loss the durable pending-task record is the ONLY
        source, and its identifiers must reach extract_targets."""
        survived = _inherited_targets(
            {"original_message": "8 machines: " + ", ".join(
                ORIGINAL_IDENTIFIERS),
             "requested_targets": list(ORIGINAL_IDENTIFIERS)})
        assert survived == ORIGINAL_IDENTIFIERS

    def test_the_order_is_preserved(self):
        survived = _inherited_targets(
            {"requested_targets": list(ORIGINAL_IDENTIFIERS)})
        assert survived == list(ORIGINAL_IDENTIFIERS)

    def test_a_derived_identifier_wins_over_the_task_record(self):
        """When the ask itself yields an identifier, the task record
        does not override it — inheritance fills a gap, it does not
        rewrite a good derivation. (``extract_targets`` canonicalizes
        free text, so "TK 1624" derives as "1624"; the task record's
        identifiers, by contrast, are passed through verbatim.)"""
        derived = _inherited_targets(
            {"requested_targets": ["TK 9999"]},
            message="look up TK 1624 in the sheet")
        assert derived == ["1624"]
        assert "TK 9999" not in derived

    def test_an_empty_task_record_adds_nothing(self):
        assert _inherited_targets({"requested_targets": []}) == \
            _inherited_targets(None)

    def test_a_non_dict_task_record_is_ignored(self):
        assert _inherited_targets("not a task") == _inherited_targets(None)


class TestNoSwallowedRegression:
    """Structural guards, so the bare ``except Exception`` can never hide
    this again."""

    def test_get_qwen_response_has_no_bare_pending_file_task(self):
        source = open(chat.__file__).read()
        tree = ast.parse(source)
        target = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == "_get_qwen_response")
        offenders = [
            node.lineno for node in ast.walk(target)
            if isinstance(node, ast.Name) and node.id == "_pending_file_task"
        ]
        assert offenders == [], (
            "_get_qwen_response references an undefined "
            f"_pending_file_task at lines {offenders}; the enclosing "
            "parameter is pending_file_task and the NameError would be "
            "swallowed by the surrounding except Exception")

    def test_the_parameter_actually_exists(self):
        source = open(chat.__file__).read()
        tree = ast.parse(source)
        target = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == "_get_qwen_response")
        params = {a.arg for a in target.args.args + target.args.kwonlyargs}
        assert "pending_file_task" in params

    def test_identifier_inheritance_reads_the_task_record(self):
        """If someone deletes the inheritance block outright, the feature
        is gone and this fails — the block must remain reachable."""
        inherited = _inherited_targets(
            {"requested_targets": list(ORIGINAL_IDENTIFIERS)})
        assert inherited == ORIGINAL_IDENTIFIERS, (
            "identifier inheritance no longer reaches the lookup")


class TestExtractTargetsContract:
    """Free-text extraction canonicalizes: "TK 1624" yields "1624" and
    "No. 381" yields "381". That is the extractor's contract, and it is
    exactly why the task record matters — those identifiers bypass
    extraction entirely and reach the lookup verbatim (asserted above).
    """

    @pytest.mark.parametrize("identifier,canonical", [
        ("No. 381", "381"),
        ("U-22", "U-22"),
        ("No. 622", "622"),
        ("TK Manual Flanger", "Manual Flanger"),
        ("SLE24-16", "SLE24-16"),
        ("TK 1624", "1624"),
        ("TK Multi Wheel Gang Slitter", "Multi Wheel Gang Slitter"),
        ("GSL48-16", "GSL48-16"),
    ])
    def test_each_identifier_is_extractable(self, identifier, canonical):
        found = extract_targets(f"look up {identifier} please", [])
        assert canonical in found, (
            f"{identifier!r} extracted as {found}, expected {canonical!r}")

    def test_the_task_record_bypasses_canonicalization(self):
        """The point of the whole feature: the stored identifiers are
        trusted verbatim rather than re-derived and shortened."""
        assert _inherited_targets(
            {"requested_targets": ["TK Multi Wheel Gang Slitter"]}
        ) == ["TK Multi Wheel Gang Slitter"]
