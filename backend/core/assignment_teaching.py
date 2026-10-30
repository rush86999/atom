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



def build_conversation_calculation(
    lesson_entry: Dict[str, Any],
    sources: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Compile a promoted conversation-learning method into a one-row calc.

    The method is already explicit (operation, inputs, units). Conditions and
    exceptions are NOT silently ignored: a method that needs row predicates
    cannot be compiled here and raises a clarification. A single unfamiliar
    row is enough to prove ordinary work consumes the accepted method.
    """
    from core.conversation_learning import method_from_lesson

    method = method_from_lesson(lesson_entry)
    if method is None:
        return None
    if method.decision_conditions or method.exceptions:
        raise TaughtCalculationError(
            "calculation_method_unresolved",
            "The taught method has row conditions or exceptions that this "
            "assignment calculation cannot evaluate; state the applicable "
            "subset explicitly.")
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
    columns = {str(column) for column in source.get("columns") or []}
    variables: List[str] = []
    bindings: Dict[str, Dict[str, str]] = {}
    for index, item in enumerate(method.inputs):
        column = str(item.column or "").strip()
        if not column or (columns and column not in columns):
            raise TaughtCalculationError(
                "calculation_method_unresolved",
                f"calculation column '{column or item.concept}' is not in the "
                "bound source",
                detail={"available_columns": sorted(columns)[:50]})
        variable = f"v{index + 1}"
        variables.append(variable)
        bindings[variable] = {
            "$ref": f"source-{source_index + 1}.rows.0.{column}",
        }
    operation = str(method.operation or "").strip()
    if operation == "sum":
        expression = variables[0]
    elif operation == "multiply_sum":
        expression = f"{variables[0]} * {variables[1]}"
    elif operation == "percentage":
        expression = f"{variables[0]} * {variables[1]} / 100"
    elif operation == "ratio":
        expression = f"{variables[0]} / {variables[1]}"
    elif operation == "count":
        expression = "1"
    else:
        raise TaughtCalculationError(
            "calculation_method_unsupported",
            f"The taught operation '{operation}' cannot be compiled for an "
            "assignment calculation.")
    return {
        "expression": expression,
        "bindings": bindings,
        "units": {},
        "output_unit": str(method.output_unit or ""),
        "origin": {
            "method": "conversation_learning",
            "lesson_id": str(lesson_entry.get("id") or ""),
            "teaching_revision": str(lesson_entry.get("revision") or 1),
        },
    }

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
