"""Schema verifier — the cheapest strong signal for structured output.

For extraction / structured-output tasks, "correct" largely means
"matches the agreed shape". This verifier validates each candidate
against either:

  * a full JSON Schema (``step.parameters["output_schema"]``), using
    ``jsonschema`` if importable; or
  * a simpler required-field list
    (``step.parameters["required_fields"]``) with type checks.

The first candidate that validates wins. If none validate, or no
schema is configured, ``winner=None`` is returned and the orchestrator
falls back to voting.

This is the highest value-per-cost verifier: zero external
dependencies, zero latency, and extraction errors are overwhelmingly
shape errors (missing keys, wrong types) rather than subtle semantic
ones.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.orchestration.verification.base import (
    VerificationResult,
    VerificationStrategy,
    Verifier,
)

logger = logging.getLogger(__name__)

try:  # Optional dependency — degrade gracefully if absent.
    import jsonschema  # type: ignore
    _HAS_JSONSCHEMA = True
except ImportError:  # pragma: no cover — exercised only when jsonschema missing
    _HAS_JSONSCHEMA = False


class SchemaVerifier(Verifier):
    """JSON-schema / required-field validation."""

    strategy = VerificationStrategy.SCHEMA

    async def verify(
        self,
        candidates: List[Any],
        step: Any,
        context: Any,
    ) -> VerificationResult:
        domain = getattr(context, "_resolved_domain", None) or "unknown"
        params = getattr(step, "parameters", None) or {}
        schema = params.get("output_schema")
        required_fields = params.get("required_fields")

        if not candidates:
            return VerificationResult.empty(domain, self.strategy, reason="no candidates")

        if schema is None and not required_fields:
            return VerificationResult.empty(
                domain, self.strategy,
                reason="no output_schema or required_fields configured on the step",
            )

        errors: List[Dict[str, Any]] = []
        for idx, candidate in enumerate(candidates):
            ok, why = self._validate(candidate, schema, required_fields)
            if ok:
                return VerificationResult(
                    winner=candidate,
                    strategy=self.strategy,
                    domain=domain,
                    confidence=1.0,
                    details={
                        "winning_index": idx,
                        "candidate_count": len(candidates),
                        "mode": "jsonschema" if schema is not None else "required_fields",
                    },
                    reason="first candidate matching the configured schema",
                )
            errors.append({"index": idx, "error": why})

        return VerificationResult.empty(
            domain, self.strategy,
            reason="no candidate matched the configured schema",
        ).__class__(
            winner=None,
            strategy=self.strategy,
            domain=domain,
            confidence=0.0,
            details={"validation_errors": errors[:10], "candidate_count": len(candidates)},
            reason="no candidate matched the configured schema",
        )

    @staticmethod
    def _validate(
        candidate: Any,
        schema: Optional[Dict[str, Any]],
        required_fields: Optional[List[str]],
    ) -> tuple:
        """Return ``(ok, reason)``. ``reason`` is None on success."""
        if not isinstance(candidate, dict):
            return False, f"expected a dict/object, got {type(candidate).__name__}"

        if schema is not None:
            if _HAS_JSONSCHEMA:
                try:
                    jsonschema.validate(candidate, schema)
                except jsonschema.ValidationError as exc:
                    return False, f"jsonschema: {exc.message}"
                except Exception as exc:  # noqa: BLE001 — schema bugs shouldn't crash the swarm
                    return False, f"jsonschema (unexpected): {exc}"
            else:
                # Fall back to manual required-field + type checks if
                # jsonschema isn't installed. We honour the schema's
                # ``required`` and ``properties.type`` if present.
                ok, why = SchemaVerifier._manual_schema_check(candidate, schema)
                if not ok:
                    return False, why

        if required_fields:
            missing = [f for f in required_fields if f not in candidate]
            if missing:
                return False, f"missing required fields: {missing}"

        return True, None

    @staticmethod
    def _manual_schema_check(
        candidate: Dict[str, Any],
        schema: Dict[str, Any],
    ) -> tuple:
        required = schema.get("required") or []
        missing = [f for f in required if f not in candidate]
        if missing:
            return False, f"missing required fields: {missing}"

        # Lightweight type mapping for the common JSON-Schema types.
        type_map = {
            "string": str, "integer": int, "number": (int, float),
            "boolean": bool, "array": list, "object": dict, "null": type(None),
        }
        properties = schema.get("properties") or {}
        for field, spec in properties.items():
            if field not in candidate:
                continue
            expected = spec.get("type") if isinstance(spec, dict) else None
            if expected and expected in type_map:
                # bool is a subclass of int — exclude it for integer/number.
                value = candidate[field]
                py_type = type_map[expected]
                if expected in ("integer", "number") and isinstance(value, bool):
                    return False, f"field {field!r}: expected {expected}, got bool"
                if not isinstance(value, py_type):
                    return False, f"field {field!r}: expected {expected}, got {type(value).__name__}"
        return True, None


__all__ = ["SchemaVerifier"]
