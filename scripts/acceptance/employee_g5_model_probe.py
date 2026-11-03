#!/usr/bin/env python3
"""G5 model probe: does the served local model discover material prerequisites?

This is a bounded evidence-selection probe, not G5 acceptance. It sends two
held-out business contexts through the production employee proposal consumer
and records the pinned model request/parsed response. A valid proposal that
selects the governing evidence is a candidate for the full journey; a
deterministic fallback is reported separately and never counted as adaptive
success.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

MODEL = os.getenv("G5_MODEL", "llama3.1:8b")
OLLAMA = os.getenv("G5_OLLAMA_URL", "http://127.0.0.1:11436/v1")
OUT = Path(os.getenv("G5_OUT", "/private/tmp/atom-local-ollama/g5-probe"))


def _scratch() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="atom-g5-probe-"))
    for name in (
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY",
        "OPENROUTER_API_KEY", "GOOGLE_API_KEY", "OPENCODE_API_KEY",
        "MOONSHOT_API_KEY", "DEEPINFRA_API_KEY",
    ):
        os.environ.pop(name, None)
    os.environ.update({
        "TESTING": "1",
        "DATABASE_URL": f"sqlite:///{tmp}/atom.db",
        "ATOM_DATA_DIR": str(tmp / "data"),
        "LANCEDB_URI": str(tmp / "data" / "atom_memory"),
        "ATOM_OFFICE_DIR": str(tmp / "data" / "office"),
        "BYOK_KEYS_FILE": str(tmp / "byok_keys.json"),
        "BYOK_CONFIG_FILE": str(tmp / "byok_config.json"),
        "BYOK_ENC_KEY_FILE": str(tmp / "byok_encryption_key"),
        "ATOM_LOCAL_ONLY": "true",
        "ATOM_PRODUCT_PROFILE": "core",
        "ENABLE_SCHEDULER": "false",
        "ENABLE_INGESTION_SYNC": "false",
        "OLLAMA_BASE_URL": OLLAMA,
        "OLLAMA_CONTEXT_WINDOW": "16384",
        "OLLAMA_MODEL": MODEL,
    })
    (tmp / "data").mkdir(parents=True, exist_ok=True)
    return tmp


class RecordingLLM:
    def __init__(self, inner: Any, calls: List[Dict[str, Any]]):
        self.inner = inner
        self.calls = calls

    async def generate_structured_response(self, **kwargs: Any) -> Any:
        kwargs.setdefault("provider_model", ("ollama", MODEL))
        record = {
            "kind": "employee_proposal",
            "prompt": kwargs.get("prompt"),
            "system_instruction": kwargs.get("system_instruction"),
            "response_model": getattr(
                kwargs.get("response_model"), "__name__",
                str(kwargs.get("response_model"))),
            "provider_model": list(kwargs.get("provider_model") or ()),
            "output_mode": kwargs.get("output_mode"),
            "task_type": kwargs.get("task_type"),
        }
        started = time.time()
        try:
            result = await self.inner.generate_structured_response(**kwargs)
            record["result_type"] = type(result).__name__
            record["parsed"] = (
                result.model_dump() if hasattr(result, "model_dump") else result)
            return result
        except Exception as exc:  # noqa: BLE001 - recorded boundary
            record["error_type"] = type(exc).__name__
            record["error"] = str(exc)[:8000]
            return None
        finally:
            record["seconds"] = round(time.time() - started, 2)
            self.calls.append(record)


def _quote_sources() -> List[Dict[str, Any]]:
    return [
        {
            "source_id": "price-workbook", "kind": "workbook",
            "representation": "xlsx", "file_name": "heldout-price-list.xlsx",
            "sheet": "Items", "row_count": 2,
            "columns": ["SKU", "Qty", "Unit Price", "Discount Percent",
                        "Category", "Unit", "Pack", "Lead Days"],
            "coverage": {"known": True, "complete": True, "truncated": False},
            "source_version": "prices-v7",
        },
        {
            "source_id": "terms-agreement", "kind": "document",
            "representation": "docx", "file_name": "customer-terms.docx",
            "coverage": {"known": True, "complete": True, "truncated": False},
            "source_version": "terms-v4",
        },
        {
            "source_id": "customer-record", "kind": "crm",
            "file_name": "customer-C-104.json",
            "coverage": {"known": True, "complete": True, "truncated": False},
            "source_version": "crm-v2",
        },
        {
            "source_id": "equivalence-record", "kind": "document",
            "representation": "pdf", "file_name": "approved-equivalence.pdf",
            "coverage": {"known": True, "complete": True, "truncated": False},
            "source_version": "equiv-v1",
        },
    ]


def _quote_context() -> Dict[str, Any]:
    from core.employee_proposal import build_employee_context
    return build_employee_context(
        objective=(
            "Prepare an accurate, cited industrial quote for customer C-104 "
            "using approved commercial sources. The customer requires delivery "
            "within 10 calendar days and a total no greater than 500 USD. "
            "Apply only established eligibility and approved equivalents."),
        employee_id="employee-quote-1",
        workspace_id="ws-g5", tenant_id="tenant-g5",
        teaching={
            "revision": "quote-teach-heldout-1",
            "rules": [
                "All prices are USD and exclude tax.",
                "Freight is explicit; do not infer tax or transit.",
                "A category discount applies only when eligibility is "
                "established by the governing customer agreement.",
                "The customer permits approved equivalents only when an "
                "authoritative equivalence record exists.",
                "A quote must cite its source rows and current versions.",
            ],
        },
        sources=_quote_sources(),
        authorized_actions=["retrieve", "calculate", "present", "edit"],
        action_views=[],
        budget={"max_steps": 40, "max_wall_seconds": 900},
    )


def _procurement_sources() -> List[Dict[str, Any]]:
    return [
        {
            "source_id": "purchase-order", "kind": "document",
            "representation": "pdf", "file_name": "PO-8841.pdf",
            "coverage": {"known": True, "complete": True, "truncated": False},
            "source_version": "po-v1",
        },
        {
            "source_id": "invoice-v1", "kind": "document",
            "representation": "pdf", "file_name": "INV-2210-v1.pdf",
            "coverage": {"known": True, "complete": True, "truncated": False},
            "source_version": "invoice-v1",
        },
        {
            "source_id": "receiving-records", "kind": "dataset",
            "file_name": "receiving-2026-11.csv",
            "columns": ["po_id", "received_quantity", "received_date"],
            "row_count": 1,
            "coverage": {"known": True, "complete": True, "truncated": False},
            "source_version": "receiving-v3",
        },
        {
            "source_id": "vendor-directory", "kind": "dataset",
            "file_name": "vendors.csv",
            "columns": ["vendor_id", "vendor_name", "tax_id"],
            "coverage": {"known": True, "complete": True, "truncated": False},
            "source_version": "vendors-v2",
        },
        {
            "source_id": "chart-of-accounts", "kind": "dataset",
            "file_name": "coa.csv",
            "columns": ["account", "name", "active"],
            "coverage": {"known": True, "complete": True, "truncated": False},
            "source_version": "coa-v5",
        },
        {
            "source_id": "open-period", "kind": "dataset",
            "file_name": "periods.csv",
            "columns": ["period", "open"],
            "coverage": {"known": True, "complete": True, "truncated": False},
            "source_version": "periods-v1",
        },
    ]


def _procurement_context() -> Dict[str, Any]:
    from core.employee_proposal import build_employee_context
    return build_employee_context(
        objective=(
            "Reconcile supplier invoice INV-2210 against approved purchase "
            "order PO-8841 and receiving records. Prepare or post only the "
            "supported reviewed bill; do not infer tax or rewrite quantities."),
        employee_id="employee-books-1",
        workspace_id="ws-g5", tenant_id="tenant-g5",
        teaching={
            "revision": "books-teach-heldout-1",
            "rules": [
                "Match received quantities to the invoice before posting.",
                "The purchase order stable vendor id resolves the vendor; do "
                "not ask the human for information already in an authorized "
                "record.",
                "The chart of accounts and current open period are required.",
                "A corrected invoice requires authoritative supplier evidence.",
                "A payment reference is evidence only; payment is separate.",
            ],
        },
        sources=_procurement_sources(),
        authorized_actions=["retrieve", "calculate", "outbound"],
        action_views=[{
            "action": "bookkeeping.create_bill",
            "effect": "external",
            "description": "Create one reviewed bill after reconciliation",
        }],
        budget={"max_steps": 40, "max_wall_seconds": 900},
    )


def _selected(result: Dict[str, Any]) -> List[str]:
    if not result:
        return []
    reads = (result.get("proposal") or {}).get("evidence_reads") or []
    return [str(item.get("source_id") or item.get("action") or "")
            for item in reads if isinstance(item, dict)]


async def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    _scratch()
    from core.llm_service import LLMService
    from core.employee_proposal import propose_employee_work

    service = LLMService(workspace_id="ws-g5", tenant_id="tenant-g5")
    calls: List[Dict[str, Any]] = []
    recorder = RecordingLLM(service, calls)
    report: Dict[str, Any] = {
        "schema": "atom-g5-model-probe-1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": {"base_url": OLLAMA, "declared": MODEL,
                  "pin": f"ollama:{MODEL}"},
        "boundaries": [
            "local Ollama only; no cloud/provider key",
            "proposal consumer only; no effect/send",
            "deterministic fallback is not adaptive success",
        ],
        "cases": [],
    }
    cases = [
        ("industrial_quote", _quote_context(),
         {"price-workbook", "terms-agreement"}),
        ("procurement_bookkeeping", _procurement_context(),
         {"purchase-order", "invoice-v1", "receiving-records"}),
    ]
    for name, context, required in cases:
        started = time.time()
        result = await propose_employee_work(
            context, llm_service=recorder,
            deadline_seconds=120.0,
            provider_model=("ollama", MODEL))
        selected = _selected(result)
        report["cases"].append({
            "name": name,
            "objective": context.get("objective"),
            "proposal_source": result.get("source"),
            "technical_fallback": result.get("technical_fallback"),
            "errors": result.get("errors") or [],
            "proposal": result.get("proposal"),
            "selected_handles": selected,
            "required_prerequisites": sorted(required),
            "discovered_required": sorted(
                required & set(selected)),
            "model_backed": result.get("source") == "model",
            "seconds": round(time.time() - started, 2),
        })
    report["calls"] = len(calls)
    (OUT / "report.json").write_text(
        json.dumps(report, indent=2, default=str) + "\n")
    with (OUT / "calls.jsonl").open("w", encoding="utf-8") as handle:
        for call in calls:
            handle.write(json.dumps(call, default=str) + "\n")
    print(json.dumps({
        "report": str(OUT / "report.json"),
        "calls": len(calls),
        "cases": [
            {
                "name": item["name"],
                "source": item["proposal_source"],
                "selected": item["selected_handles"],
                "discovered": item["discovered_required"],
            }
            for item in report["cases"]
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
