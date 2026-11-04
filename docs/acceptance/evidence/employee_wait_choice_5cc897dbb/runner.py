"""One bounded replay of the captured wait-choice no-result.

Reads the accepted captured context/assignment, runs the isolated worktree
consumer against the already-configured local route, and records the actual
decision, route and attempts. No HTTP server and no new provider.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:11436/v1")
os.environ.setdefault("OLLAMA_MODEL", "llama3.1:8b")
os.environ.setdefault("OLLAMA_CONTEXT_WINDOW", "16384")
os.environ.setdefault(
    "ATOM_LLM_PROVIDER_POLICY",
    '{"mode":"selected","allowed_providers":["ollama"],"preferred":'
    '{"provider":"ollama","model":"llama3.1:8b"}}')
os.environ.setdefault("ATOM_EMPLOYEE_PROVIDER_MODEL", "ollama:llama3.1:8b")

from core.employee_adaptation import propose_adaptation  # noqa: E402
from core.employee_attempt_journal import AttemptJournal  # noqa: E402
from core.llm_service import LLMService  # noqa: E402

EVIDENCE = Path(
    "/private/tmp/atom-full-app/docs/acceptance/evidence/"
    "employee_byok_auto_selection_0e04286b2")
prompt_text = Path("/private/tmp/wait-choice-captured-prompt.txt").read_text()
start = prompt_text.index("CONTEXT:\n") + len("CONTEXT:\n")
end = prompt_text.index("\n\nOBSERVATIONS:")
context = json.loads(prompt_text[start:end])
# The attempt journal truncates the captured prompt at 24k chars; the
# observation identity is retained in the prompt and the accepted state.
observations = [{
    "observation_id": "evidence-e5a109b85f4c6bc2bc52",
    "kind": "evidence_result",
    "step_id": "source-1",
    "shape": "text",
    "data_keys": [],
}]
state = json.loads((EVIDENCE / "state.json").read_text())
assignment = (
    (state.get("start_response") or {}).get("assignment") or {}
).get("assignment") or {}
assert assignment, "captured assignment missing"

journal = AttemptJournal()
service = LLMService(db=None, workspace_id="default", tenant_id="default")
started = time.monotonic()
result = __import__("asyncio").run(propose_adaptation(
    context,
    observations,
    assignment=assignment,
    llm_service=service,
    deadline=time.monotonic() + 180.0,
    attempt_journal=journal,
))
elapsed = time.monotonic() - started
output = {
    "captured_context": {
        "objective": context.get("objective"),
        "missing_prerequisites": context.get("missing_prerequisites"),
        "allowed_proposal_kinds": (context.get("rules") or {}).get(
            "allowed_proposal_kinds"),
        "allowed_work_requests": (context.get("rules") or {}).get(
            "allowed_work_requests"),
        "unread_source_count": context.get("unread_source_count"),
    },
    "result": result,
    "elapsed_seconds": elapsed,
    "journal_events": journal.events,
    "provider_identity": {
        "policy": os.environ.get("ATOM_LLM_PROVIDER_POLICY"),
        "ollama_base_url": os.environ.get("OLLAMA_BASE_URL"),
        "model": os.environ.get("OLLAMA_MODEL"),
    },
}
out = Path("/private/tmp/wait-choice-replay.json")
out.write_text(json.dumps(output, indent=1, default=str) + "\n")
print(json.dumps({
    "source": result.get("source"),
    "prompt_mode": result.get("prompt_mode"),
    "failure_stage": result.get("failure_stage"),
    "errors": result.get("errors"),
    "decision": (result.get("proposal") or {}).get("decision"),
    "work_request": (result.get("proposal") or {}).get("work_request"),
    "routing": result.get("routing"),
    "elapsed_seconds": elapsed,
    "attempt_events": [
        {k: event.get(k) for k in (
            "event", "call_stage", "attempt", "route", "seconds",
            "prompt_chars", "response_model") if event.get(k) is not None}
        for event in journal.events
    ],
}, indent=1, default=str)[:8000])
