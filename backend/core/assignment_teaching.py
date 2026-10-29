"""Taught calculation methods on the existing artifact lesson journal.

The artifact-teaching module owns the lesson store and the applicability rules.
This module adds an opaque calculation contract to that same journal so a
teacher can declare a reusable method without a prompt-supplied formula:

* ``calculation_expression``: expression in the existing formula language;
* ``calculation_fields``: ``variable=Column`` entries read from the bound frame;
* ``calculation_wait_variable``: optional variable bound to the waiting fact;
* ``calculation_unit``: display/output unit.

The expression is evaluated by ``core.formula_engine``. Unsupported or
ambiguous methods fail closed instead of falling back to a guessed formula.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from core import artifact_teaching


class TaughtCalculationError(ValueError):
    def __init__(self, code: str, message: str, *, status: int = 409,
                 detail: Optional[Dict[str, Any]] = None):
        self.code = code
        self.status = status
        self.detail = dict(detail or {})
        super().__init__(message)


_CALCULATION_SCHEMA = {
    "calculation_expression": "str",
    "calculation_unit": "str",
    "calculation_fields": "list",
    "calculation_wait_variable": "str",
}


def install_schema() -> None:
    """Let lesson normalization keep the opaque calculation keys."""
    for schema in artifact_teaching._FORMAT_SCHEMA.values():  # noqa: SLF001
        schema.update(_CALCULATION_SCHEMA)


install_schema()


def _field_bindings(
    raw_fields: Any,
    source_step: str,
    columns: List[str],
) -> Dict[str, Dict[str, str]]:
    if raw_fields is None:
        raw_fields = []
    if not isinstance(raw_fields, (list, tuple)):
        raise TaughtCalculationError(
            "calculation_method_unresolved",
            "calculation_fields must be a list of variable=Column entries")
    bindings: Dict[str, Dict[str, str]] = {}
    known_columns = {str(column) for column in columns}
    for raw in raw_fields:
        text = str(raw or "").strip()
        variable, separator, column = text.partition("=")
        variable = variable.strip()
        column = column.strip()
        if (not separator or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$",
                                          variable)
                or not column):
            raise TaughtCalculationError(
                "calculation_method_unresolved",
                f"invalid calculation field mapping '{text}'")
        if variable in bindings:
            raise TaughtCalculationError(
                "calculation_method_ambiguous",
                f"calculation variable '{variable}' is declared twice")
        if known_columns and column not in known_columns:
            raise TaughtCalculationError(
                "calculation_method_unresolved",
                f"calculation column '{column}' is not in the bound source",
                detail={"available_columns": sorted(known_columns)[:50]})
        bindings[variable] = {
            "$ref": f"{source_step}.rows.0.{column}",
        }
    return bindings


def build_taught_calculation(
    teaching: Dict[str, Any],
    sources: List[Dict[str, Any]],
    wait: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Build a calculation descriptor from an applicable lesson, or None.

    It never invents a formula, a field binding or a missing-information
    source. A malformed/unsupported method raises a typed clarification.
    """
    requirements = dict((teaching or {}).get("output_requirements") or {})
    expression = str(
        requirements.get("calculation_expression") or "").strip()
    if not expression:
        return None
    source_index: Optional[int] = None
    for index, source in enumerate(sources or []):
        if str(source.get("representation") or "") in (
                "parquet_frame", "xlsx"):
            source_index = index
            break
    if source_index is None:
        raise TaughtCalculationError(
            "calculation_method_unresolved",
            "The taught method needs an authorized workbook/dataset source.")
    source = sources[source_index]
    source_step = f"source-{source_index + 1}"
    bindings = _field_bindings(
        requirements.get("calculation_fields"),
        source_step,
        list(source.get("columns") or []),
    )
    wait_variable = str(
        requirements.get("calculation_wait_variable") or "").strip()
    if wait_variable:
        if not wait:
            raise TaughtCalculationError(
                "calculation_method_unresolved",
                "The taught method requires a waiting fact but the "
                "assignment has no wait.")
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", wait_variable):
            raise TaughtCalculationError(
                "calculation_method_unresolved",
                f"invalid waiting variable '{wait_variable}'")
        if wait_variable in bindings:
            raise TaughtCalculationError(
                "calculation_method_ambiguous",
                f"calculation variable '{wait_variable}' is declared twice")
        bindings[wait_variable] = {"$ref": "wait.value"}
    from core.formula_engine import evaluate_expression

    probe = {variable: "1" for variable in bindings}
    probe_result = evaluate_expression(
        expression, probe,
        output_unit=str(requirements.get("calculation_unit") or ""),
    )
    if probe_result.status != "computed":
        detail = probe_result.missing or probe_result.unsupported or (
            probe_result.status)
        raise TaughtCalculationError(
            "calculation_method_unsupported",
            f"The taught method cannot be evaluated: {detail}",
            detail={"detail": str(detail)[:500]})
    return {
        "expression": expression,
        "bindings": bindings,
        "units": {},
        "output_unit": str(requirements.get("calculation_unit") or ""),
        "origin": {
            "method": "taught",
            "teaching_revision": str(
                (teaching or {}).get("revision") or ""),
        },
    }
