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

WORK_REQUEST_OPERATIONS = (
    "quote_calculation", "invoice_reconciliation", "await_evidence")
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
    authority_ref: str = Field(min_length=1, max_length=300)


class QuoteColumns(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1, max_length=120)
    quantity: str = Field(min_length=1, max_length=120)
    unit_price: str = Field(min_length=1, max_length=120)
    currency: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=120)
    unit: Optional[str] = Field(default=None, max_length=120)
    pack_size: Optional[str] = Field(default=None, max_length=120)
    price_basis: Optional[str] = Field(default=None, max_length=120)
    category: Optional[str] = Field(default=None, max_length=120)
    discount: Optional[str] = Field(default=None, max_length=120)


class QuoteCalculationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["quote_calculation"]
    source_step_id: str = Field(min_length=1, max_length=80)
    columns: QuoteColumns
    currency: str = Field(min_length=1, max_length=20)
    freight: MoneyTerm
    tax: TaxTerm = Field(default_factory=lambda: TaxTerm(basis="none"))
    #: Already-applied document reads whose discount terms govern this quote.
    #: Omit to let the compiler consider every accepted document read. The
    #: compiler extracts the rate/scope from the document text; the model never
    #: supplies a discount value.
    discount_evidence_steps: List[str] = Field(default_factory=list)
    evidence: List[EvidenceRef] = Field(default_factory=list)
    reason: str = Field(default="", max_length=800)


class AwaitEvidenceRequest(BaseModel):
    """A material external fact the employee must wait for.

    The model names the business fact, its subject and the authorized source/
    channel expected to answer it. It never supplies operation ids, step ids,
    correlation ids, callbacks, paths or executable mechanics; the compiler
    derives and binds those to the durable run.
    """

    model_config = ConfigDict(extra="forbid")

    operation: Literal["await_evidence"]
    fact: str = Field(min_length=1, max_length=120)
    subject: str = Field(min_length=1, max_length=200)
    expected_from: str = Field(min_length=1, max_length=200)
    expected_answer_type: Literal[
        "quantity", "amount", "price", "date", "text", "confirmation",
        "eligibility",
    ]
    blocks: str = Field(min_length=1, max_length=500)
    # The supported business result whose receipt depends on this fact. The
    # compiler binds the durable requirement; plain-language ``blocks`` is
    # explanatory only.
    blocks_operation: Optional[Literal[
        "quote_calculation", "invoice_reconciliation",
    ]] = None
    deadline: Optional[str] = Field(default=None, max_length=40)
    validity: Optional[str] = Field(default=None, max_length=40)
    reason: str = Field(default="", max_length=800)


class InvoiceReconciliationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["invoice_reconciliation"]
    # Role references are optional when the accepted evidence has exactly one
    # candidate for the role; the compiler infers it and still validates the
    # mapped fields and proof. Name a step only to disambiguate.
    invoice_step_id: Optional[str] = Field(default=None, max_length=80)
    purchase_order_step_id: Optional[str] = Field(default=None, max_length=80)
    receiving_step_id: Optional[str] = Field(default=None, max_length=80)
    vendor_step_id: Optional[str] = Field(default=None, max_length=80)
    coa_step_id: Optional[str] = Field(default=None, max_length=80)
    period_step_id: Optional[str] = Field(default=None, max_length=80)
    invoice_fields: Dict[str, str] = Field(default_factory=dict)
    purchase_order_fields: Dict[str, str] = Field(default_factory=dict)
    receiving_fields: Dict[str, str] = Field(default_factory=dict)
    currency: Optional[str] = Field(default=None, max_length=20)
    bill_action: Optional[str] = Field(default=None, max_length=200)
    evidence: List[EvidenceRef] = Field(default_factory=list)
    reason: str = Field(default="", max_length=800)


WorkRequest = Annotated[
    Union[
        QuoteCalculationRequest, InvoiceReconciliationRequest,
        AwaitEvidenceRequest,
    ],
    Field(discriminator="operation"),
]


def work_request_schemas() -> List[Dict[str, Any]]:
    return [
        {
            "operation": "quote_calculation",
            "description": (
                "Compute exact quote lines and total from one accepted source "
                "read plus taught/authorized currency, freight and tax terms. "
                "Explicit discount terms stated by accepted document evidence "
                "are extracted by the compiler; never supply a discount rate. "
                "Optionally name the accepted document step ids that govern "
                "the discount."),
            "schema": QuoteCalculationRequest.model_json_schema(),
        },
        {
            "operation": "invoice_reconciliation",
            "description": (
                "Reconcile invoice quantity and amount against accepted "
                "purchase-order and receiving evidence."),
            "schema": InvoiceReconciliationRequest.model_json_schema(),
        },
        {
            "operation": "await_evidence",
            "description": (
                "Wait for one material external fact that authorized evidence "
                "cannot supply yet. Name the supported operation whose "
                "verified result depends on it; the compiler binds that "
                "durable result requirement plus the wait, correlation and "
                "response requirement."),
            "schema": AwaitEvidenceRequest.model_json_schema(),
        },
    ]


def request_digest(request: Any) -> str:
    payload = (
        request.model_dump() if isinstance(request, BaseModel)
        else dict(request or {}))
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"),
                   default=str).encode("utf-8")).hexdigest()[:16]
