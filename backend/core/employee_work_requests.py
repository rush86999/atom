"""Strict typed business-work requests for the employee reasoning layer.

The model chooses a supported business operation, evidence step references,
semantic field mappings and taught/authorized monetary terms. Execution
mechanics (step ids, adapters, references, dependencies, effect classes) are
compiled deterministically by ``employee_work_compiler``.
"""
from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

WORK_REQUEST_OPERATIONS = ("quote_calculation", "invoice_reconciliation")
QUOTE_COLUMN_FIELDS = (
    "item_id", "quantity", "unit_price", "currency", "description", "unit",
    "pack_size", "price_basis", "category", "discount",
)


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1, max_length=80)
    role: str = Field(default="evidence", max_length=80)


class MoneyTerm(BaseModel):
    """A taught/authorized monetary term bound to its authority."""

    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1, max_length=80)
    authority_ref: str = Field(min_length=1, max_length=300)
    currency: Optional[str] = Field(default=None, max_length=20)


class TaxTerm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    basis: Literal["none", "rate", "amount"]
    value: str = Field(default="", max_length=80)
    authority_ref: str = Field(default="", max_length=300)


class QuoteCalculationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["quote_calculation"]
    source_step_id: str = Field(min_length=1, max_length=80)
    require_verified_source: bool = True
    columns: Dict[str, str] = Field(default_factory=dict)
    currency: str = Field(min_length=1, max_length=20)
    freight: MoneyTerm
    tax: TaxTerm = Field(default_factory=lambda: TaxTerm(basis="none"))
    evidence: List[EvidenceRef] = Field(default_factory=list)
    reason: str = Field(default="", max_length=800)


class InvoiceReconciliationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["invoice_reconciliation"]
    invoice_step_id: str = Field(min_length=1, max_length=80)
    purchase_order_step_id: str = Field(min_length=1, max_length=80)
    receiving_step_id: str = Field(min_length=1, max_length=80)
    vendor_step_id: Optional[str] = Field(default=None, max_length=80)
    coa_step_id: Optional[str] = Field(default=None, max_length=80)
    period_step_id: Optional[str] = Field(default=None, max_length=80)
    invoice_fields: Dict[str, str] = Field(default_factory=dict)
    purchase_order_fields: Dict[str, str] = Field(default_factory=dict)
    receiving_fields: Dict[str, str] = Field(default_factory=dict)
    currency: Optional[str] = Field(default=None, max_length=20)
    require_verified_evidence: bool = True
    evidence: List[EvidenceRef] = Field(default_factory=list)
    reason: str = Field(default="", max_length=800)


WorkRequest = Annotated[
    Union[QuoteCalculationRequest, InvoiceReconciliationRequest],
    Field(discriminator="operation"),
]


def work_request_schemas() -> List[Dict[str, Any]]:
    return [
        {
            "operation": "quote_calculation",
            "description": (
                "Compute exact quote lines and total from one accepted source "
                "read plus taught/authorized currency, freight and tax terms."),
            "schema": QuoteCalculationRequest.model_json_schema(),
        },
        {
            "operation": "invoice_reconciliation",
            "description": (
                "Reconcile invoice quantity and amount against accepted "
                "purchase-order and receiving evidence."),
            "schema": InvoiceReconciliationRequest.model_json_schema(),
        },
    ]


def request_digest(request: Any) -> str:
    payload = (
        request.model_dump() if isinstance(request, BaseModel)
        else dict(request or {}))
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"),
                   default=str).encode("utf-8")).hexdigest()[:16]
