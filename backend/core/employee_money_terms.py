"""Accepted monetary-term roles, dimensions and live validity.

A taught or accepted fact is not interchangeable authority for every money
field. ``freight`` is an amount, ``tax_rate`` is a dimensionless fraction,
``tax_amount`` is money and ``tax_basis``/exemption is a distinct decision.
The compiler and the calculation consumer share this module so role checking
is identical at both boundaries.

The alias table is trusted metadata for the existing teaching/fact contract.
A term record may also declare an explicit ``role``/``term_role`` (top-level
or inside ``validity``); an unknown explicit role is refused rather than
guessed from its value.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Mapping, Optional, Sequence

ROLE_CURRENCY = "currency"
ROLE_FREIGHT_AMOUNT = "freight_amount"
ROLE_TAX_RATE = "tax_rate"
ROLE_TAX_AMOUNT = "tax_amount"
ROLE_TAX_EXEMPTION = "tax_exemption"

ROLE_DIMENSIONS = {
    ROLE_CURRENCY: "currency",
    ROLE_FREIGHT_AMOUNT: "money",
    ROLE_TAX_RATE: "rate",
    ROLE_TAX_AMOUNT: "money",
    ROLE_TAX_EXEMPTION: "exemption",
}

#: Explicit aliases for the existing structured teaching/fact keys. These
#: name a semantic role; they are not a license for any numeric term to stand
#: in for another field.
TERM_ROLE_ALIASES = {
    "currency": ROLE_CURRENCY,
    "quote_currency": ROLE_CURRENCY,
    "currency_code": ROLE_CURRENCY,
    "currency_unit": ROLE_CURRENCY,
    "freight": ROLE_FREIGHT_AMOUNT,
    "freight_amount": ROLE_FREIGHT_AMOUNT,
    "shipping": ROLE_FREIGHT_AMOUNT,
    "shipping_amount": ROLE_FREIGHT_AMOUNT,
    "delivery_amount": ROLE_FREIGHT_AMOUNT,
    "tax_rate": ROLE_TAX_RATE,
    "vat_rate": ROLE_TAX_RATE,
    "sales_tax_rate": ROLE_TAX_RATE,
    "gst_rate": ROLE_TAX_RATE,
    "tax_amount": ROLE_TAX_AMOUNT,
    "vat_amount": ROLE_TAX_AMOUNT,
    "sales_tax_amount": ROLE_TAX_AMOUNT,
    "gst_amount": ROLE_TAX_AMOUNT,
    "tax_basis": ROLE_TAX_EXEMPTION,
    "tax_mode": ROLE_TAX_EXEMPTION,
    "tax_treatment": ROLE_TAX_EXEMPTION,
    "tax_none": ROLE_TAX_EXEMPTION,
    "tax_exemption": ROLE_TAX_EXEMPTION,
    "exemption": ROLE_TAX_EXEMPTION,
}
_EXEMPTION_VALUES = {"none", "zero", "exempt", "false", "0", "0.00"}
_EXPLICIT_ROLE_KEYS = ("role", "term_role", "semantic_role")
_STABLE_REF_KEYS = ("resource_id", "source_id", "id", "uri", "sha256")


class TermContractError(ValueError):
    """A term cannot serve as authoritative money authority."""


def _name(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def canonical_role(value: Any) -> Optional[str]:
    name = _name(value)
    if not name:
        return None
    role = TERM_ROLE_ALIASES.get(name)
    if role:
        return role
    return name if name in ROLE_DIMENSIONS else None


def role_dimension(role: str) -> str:
    return ROLE_DIMENSIONS.get(str(role), "unknown")


def role_for_record(
    record: Mapping[str, Any], *names: Any,
) -> Optional[str]:
    """Resolve a term's declared role, refusing unknown explicit metadata."""
    validity = record.get("validity")
    validity = validity if isinstance(validity, Mapping) else {}
    for key in _EXPLICIT_ROLE_KEYS:
        for source in (record, validity):
            if key in source and source.get(key) not in (None, ""):
                declared = source.get(key)
                role = canonical_role(declared)
                if role is None:
                    raise TermContractError(
                        f"term declares unknown semantic role {declared!r}")
                return role
    for name in names:
        role = TERM_ROLE_ALIASES.get(_name(name))
        if role:
            return role
    return None


def validate_role_value(role: str, value: Any) -> Any:
    """Validate a value against its role; returns the canonical value."""
    if role == ROLE_CURRENCY:
        text = str(value or "").strip()
        if not text or len(text) > 20:
            raise TermContractError("currency term has no currency unit")
        return text.upper()
    if role in (ROLE_FREIGHT_AMOUNT, ROLE_TAX_AMOUNT):
        number = _decimal(value, role)
        if number < 0:
            raise TermContractError(f"{role} must not be negative")
        return number
    if role == ROLE_TAX_RATE:
        number = _decimal(value, role)
        if number < 0 or number > 1:
            raise TermContractError(
                "tax_rate must be a dimensionless fraction between 0 and 1")
        return number
    if role == ROLE_TAX_EXEMPTION:
        text = str(value or "").strip().lower()
        if text not in _EXEMPTION_VALUES:
            raise TermContractError(
                "tax exemption term does not establish a no-tax decision")
        return text
    raise TermContractError(f"unsupported semantic role {role!r}")


def is_exemption_value(value: Any) -> bool:
    return str(value or "").strip().lower() in _EXEMPTION_VALUES


def _decimal(value: Any, role: str) -> Decimal:
    text = str(value if value is not None else "").strip()
    if not text:
        raise TermContractError(f"{role} term has no value")
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise TermContractError(f"{role} term is not a finite decimal") from exc
    if not number.is_finite():
        raise TermContractError(f"{role} term is not a finite decimal")
    return number


def same_role_value(role: str, left: Any, right: Any) -> bool:
    if role == ROLE_CURRENCY:
        return str(left or "").strip().upper() == str(
            right or "").strip().upper()
    if role == ROLE_TAX_EXEMPTION:
        return is_exemption_value(left) and is_exemption_value(right)
    try:
        return Decimal(str(left)) == Decimal(str(right))
    except (InvalidOperation, ValueError):
        return False


def source_identity(refs: Sequence[Mapping[str, Any]]) -> List[Dict[str, str]]:
    identity = []
    for ref in refs or []:
        if not isinstance(ref, Mapping):
            continue
        item = {
            key: str(ref.get(key))
            for key in _STABLE_REF_KEYS
            if ref.get(key) not in (None, "", [], {})
        }
        version = ref.get("version") or ref.get("source_version")
        if version not in (None, ""):
            item["version"] = str(version)
        if item:
            identity.append(item)
    return sorted(identity, key=lambda item: json.dumps(item, sort_keys=True))


def _parse_time(value: Any, ref: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise TermContractError(
            f"authority {ref!r} has invalid validity") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _check_validity(
    validity: Mapping[str, Any],
    assignment: Mapping[str, Any],
    ref: str,
    now: datetime,
) -> None:
    scope = validity.get("scope")
    if isinstance(scope, Mapping):
        for key in ("workspace_id", "tenant_id"):
            actual = scope.get(key)
            if actual not in (None, "") and str(actual) != str(
                    assignment.get(key) or ""):
                raise TermContractError(
                    f"authority {ref!r} is outside the assignment {key} scope")
        plan_revision = scope.get("plan_revision")
        if plan_revision not in (None, ""):
            try:
                scoped_revision = int(plan_revision)
                current_revision = int(
                    assignment.get("plan_revision") or 1)
            except (TypeError, ValueError) as exc:
                raise TermContractError(
                    f"authority {ref!r} has invalid plan-revision scope"
                ) from exc
            if scoped_revision != current_revision:
                raise TermContractError(
                    f"authority {ref!r} belongs to an earlier plan revision")
    snapshot_revision = str(
        (assignment.get("teaching_snapshot") or {}).get("revision") or "")
    actual_revision = validity.get("teaching_revision")
    if actual_revision not in (None, "") and snapshot_revision and str(
            actual_revision) != snapshot_revision:
        raise TermContractError(
            f"authority {ref!r} belongs to teaching revision "
            f"{actual_revision!r}, not {snapshot_revision!r}")
    for key in ("effective_from", "not_before", "starts_at"):
        value = validity.get(key)
        if value and now < _parse_time(value, ref):
            raise TermContractError(f"authority {ref!r} is not yet effective")
    for key in ("expires_at", "expires", "valid_until"):
        value = validity.get(key)
        if value and now >= _parse_time(value, ref):
            raise TermContractError(f"authority {ref!r} is expired")


def _term_key(term_id: Any) -> str:
    key = str(term_id or "").strip()
    for prefix in ("term:", "teaching:", "authored:", "fact:"):
        if key.startswith(prefix):
            return key[len(prefix):]
    return key


def resolve_accepted_term(
    term_id: Any,
    *,
    teaching: Optional[Mapping[str, Any]] = None,
    facts: Optional[Sequence[Mapping[str, Any]]] = None,
    assignment: Optional[Mapping[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Resolve one term id against the JOB's accepted snapshot/facts.

    This is lookup plus current validity, not a new authority store. Teaching
    terms win over facts with the same key; a receipt whose recorded source no
    longer matches is refused by the consumer.
    """
    ref = str(term_id or "").strip()
    if not ref:
        raise TermContractError("requires an authority term")
    key = _term_key(ref)
    assignment = dict(assignment or {})
    teaching = teaching or assignment.get("teaching_snapshot") or {}
    if isinstance(teaching, Mapping) and "terms" not in teaching:
        teaching = {"terms": dict(teaching or {})}
    terms = dict((teaching or {}).get("terms") or {})
    facts = list(facts if facts is not None else assignment.get("facts") or [])
    current = now or datetime.now(timezone.utc)

    if key in terms:
        raw = terms[key]
        record = dict(raw) if isinstance(raw, Mapping) else {}
        value = record.get("value") if record else raw
        role = role_for_record(record, key)
        if role is None:
            raise TermContractError(
                f"authority {ref!r} has no declared semantic role")
        validity = dict(record.get("validity") or {})
        _check_validity(validity, assignment, ref, current)
        return {
            "term_id": ref,
            "value": value,
            "currency": (
                record.get("currency") or validity.get("currency")
                or validity.get("unit")),
            "role": role,
            "dimension": role_dimension(role),
            "basis": key,
            "source": "teaching",
            "source_refs": list(record.get("source_refs") or []),
            "subject": dict(record.get("subject") or {}),
            "teaching_revision": str(
                (teaching or {}).get("revision") or ""),
            "teaching_fingerprint": str(
                (teaching or {}).get("fingerprint") or ""),
            "validity": validity,
        }

    for fact in facts:
        if not isinstance(fact, Mapping):
            continue
        if str(fact.get("fact_id") or "") != key and str(
                fact.get("authority_ref") or "") != ref:
            continue
        if str(fact.get("evidence_state") or "") != "established":
            continue
        validity = fact.get("validity") or {}
        if not isinstance(validity, Mapping):
            raise TermContractError(
                f"authority {ref!r} has an invalid validity object")
        role = role_for_record(
            fact, fact.get("field_id"), fact.get("fact_id"),
            fact.get("authority_ref"), key)
        if role is None:
            raise TermContractError(
                f"authority {ref!r} has no declared semantic role")
        _check_validity(validity, assignment, ref, current)
        subject = fact.get("subject") or {}
        if isinstance(subject, Mapping):
            for scope_key in ("workspace_id", "tenant_id"):
                actual = subject.get(scope_key)
                if actual not in (None, "") and str(actual) != str(
                        assignment.get(scope_key) or ""):
                    raise TermContractError(
                        f"authority {ref!r} belongs to another {scope_key}")
        refs = list(fact.get("source_refs") or [])
        stable = source_identity(refs)
        if not stable and not str(fact.get("authority_ref") or "").strip():
            raise TermContractError(
                f"authority {ref!r} has no accepted evidence identity")
        return {
            "term_id": ref,
            "value": fact.get("value"),
            "currency": (
                validity.get("currency") or validity.get("unit")
                or fact.get("currency") or fact.get("unit")),
            "role": role,
            "dimension": role_dimension(role),
            "basis": fact.get("field_id") or key,
            "source": "fact",
            "source_refs": refs,
            "subject": dict(subject),
            "teaching_revision": str(
                validity.get("teaching_revision") or ""),
            "teaching_fingerprint": "",
            "validity": dict(validity),
        }

    raise TermContractError(
        f"authority {ref!r} is not an accepted teaching/fact term")
