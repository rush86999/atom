#!/usr/bin/env python3
"""Probe: can the app pin a local ollama model and get a structured response?

This is the cheapest check that the substantive assessment campaign is
runnable. It uses the real LLMService/BYOKHandler, a scratch data root and the
local ollama server; it never touches the live dev DB and never calls a cloud
provider. Prints the resolved clients, the pin outcome, the structured payload
and the recorded provenance.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

TMP = Path(tempfile.mkdtemp(prefix="atom-ollama-pin-probe-"))
for name in (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY",
    "OPENROUTER_API_KEY", "GOOGLE_API_KEY", "OPENCODE_API_KEY",
    "MOONSHOT_API_KEY", "DEEPINFRA_API_KEY",
):
    os.environ.pop(name, None)
os.environ.update({
    "TESTING": "1",
    "DATABASE_URL": f"sqlite:///{TMP}/atom.db",
    "ATOM_DATA_DIR": str(TMP / "data"),
    "LANCEDB_URI": str(TMP / "data" / "atom_memory"),
    "ATOM_OFFICE_DIR": str(TMP / "data" / "office"),
    "BYOK_KEYS_FILE": str(TMP / "byok_keys.json"),
    "BYOK_CONFIG_FILE": str(TMP / "byok_config.json"),
    "BYOK_ENC_KEY_FILE": str(TMP / "byok_encryption_key"),
    "ATOM_LOCAL_ONLY": "true",
    "ATOM_PRODUCT_PROFILE": "core",
    "ENABLE_SCHEDULER": "false",
    "ENABLE_INGESTION_SYNC": "false",
    "ATOM_REVIEW_MODEL": os.environ.get("PROBE_MODEL", "llama3.1:8b"),
    "ATOM_REVIEW_PROVIDER": "ollama",
    "OLLAMA_BASE_URL": os.environ.get(
        "PROBE_OLLAMA_URL", "http://127.0.0.1:11435/v1"),
})
(TMP / "data").mkdir(parents=True, exist_ok=True)


async def main() -> int:
    from pydantic import BaseModel

    from core.llm.pinned_planning import build_provider_model_pin
    from core.llm_service import LLMService

    class Decision(BaseModel):
        subject: str
        decision: str

    class Payload(BaseModel):
        assessments: list[Decision]

    model = os.environ["ATOM_REVIEW_MODEL"]
    service = LLMService(workspace_id="default", tenant_id="default")
    handler = service._get_handler()
    result = {
        "ollama_base_url": os.environ["OLLAMA_BASE_URL"],
        "model": model,
        "handler_clients": sorted(getattr(handler, "clients", {})),
        "pin": build_provider_model_pin(
            service, "ollama", model,
            workspace_id="default", tenant_id="default"),
        "policy_mode": getattr(
            getattr(handler, "provider_policy", None), "mode", None),
    }
    if not result["pin"]:
        result["status"] = "pin_unavailable"
        print(json.dumps(result, indent=2))
        return 3

    payload = await service.generate_structured_response(
        prompt=(
            "Assess this row under the policy.\n"
            "POLICY: Approve when Amount >= 100. Deny otherwise.\n"
            "ROW: Ref=A-1, Amount=120.\n"
            "Return the decision as APPROVE or DENY."
        ),
        response_model=Payload,
        system_instruction="You assess rows under the given policy.",
        model=model,
        task_type="review",
        output_mode="json",
        cascade=False,
        allow_moa=False,
        workspace_id="default",
        tenant_id="default",
        **result["pin"],
    )
    result["payload"] = (
        payload.model_dump() if hasattr(payload, "model_dump") else payload)
    result["served_provider"] = getattr(handler, "_last_used_provider", None)
    result["served_model"] = getattr(handler, "_last_used_model", None)
    result["status"] = "passed" if result["payload"] else "empty"
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["payload"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
