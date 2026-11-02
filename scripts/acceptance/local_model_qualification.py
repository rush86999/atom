#!/usr/bin/env python3
"""Local-model planning / goal / alignment qualification.

This is a qualification probe, not a product acceptance. It exercises the
real consumers (``plan_tool_use``, ``GoalRunRouter.decide`` and
``org_politics_automation.alignment_verdict``) against the declared local
Ollama model, records the exact prompt and parsed/raw outcome, and runs
bounded failure controls. It never uses a cloud provider and never writes
outside its scratch data root.

Usage::

    python scripts/acceptance/local_model_qualification.py --all \
        --ollama-url http://127.0.0.1:11436/v1 --model llama3.1:8b

Outputs ``report.json`` and ``calls.jsonl`` under ``--out``. A hard case that
fails stays failed: the report distinguishes a model-backed plan from a
deterministic floor/recovery, and never relabels an invalid structured
decision as a pass.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


def _scratch_environment(ollama_url: str, model: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="atom-local-qualification-"))
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
        "OLLAMA_BASE_URL": ollama_url,
        "OLLAMA_CONTEXT_WINDOW": "16384",
        "OLLAMA_MODEL": model,
        "ATOM_GOAL_RUN_ROUTER_PROVIDER_MODEL": f"ollama:{model}",
        # The alignment sweep is double-gated (never a PR gate). This probe
        # supplies its own local chat_fn and explicitly enables the gate.
        "ATOM_ALIGNMENT_SWEEP_ENABLED": "true",
    })
    (tmp / "data").mkdir(parents=True, exist_ok=True)
    return tmp


def _write_calls(out: Path, calls: List[Dict[str, Any]]) -> None:
    with (out / "calls.jsonl").open("w", encoding="utf-8") as handle:
        for call in calls:
            handle.write(json.dumps(call, default=str) + "\n")


class RecordingLLM:
    """Forward structured calls to the real service, recording the exchange.

    The probe pins the declared local model on every call because this is
    model qualification, not a routing benchmark. The production call sites
    are still the ones under test.
    """

    def __init__(self, inner: Any, model: str, calls: List[Dict[str, Any]]):
        self.inner = inner
        self.model = model
        self._sink = calls
        # Case-local list. The sink is the whole run's call log; using the
        # sink directly as ``self.calls`` made one case's prompt the "first"
        # prompt of the next case (a qualification-reporting bug).
        self.calls: List[Dict[str, Any]] = []

    async def generate_structured_response(self, **kwargs: Any) -> Any:
        kwargs.setdefault("provider_model", ("ollama", self.model))
        record = {
            "kind": "structured",
            "prompt": kwargs.get("prompt"),
            "system_instruction": kwargs.get("system_instruction"),
            "response_model": getattr(
                kwargs.get("response_model"), "__name__",
                str(kwargs.get("response_model"))),
            "temperature": kwargs.get("temperature"),
            "output_mode": kwargs.get("output_mode"),
            "provider_model": list(kwargs.get("provider_model") or ()),
            "task_type": kwargs.get("task_type"),
        }
        started = time.time()
        try:
            result = await self.inner.generate_structured_response(**kwargs)
            record["result_type"] = type(result).__name__
            record["parsed"] = (
                result.model_dump() if hasattr(result, "model_dump") else result)
            return result
        except Exception as exc:  # noqa: BLE001 - recorded failure boundary
            record["error_type"] = type(exc).__name__
            record["error"] = str(exc)[:12000]
            return None
        finally:
            record["seconds"] = round(time.time() - started, 2)
            self.calls.append(record)
            self._sink.append(record)


def _planner_cases() -> List[Dict[str, Any]]:
    return [
        {
            "id": "inventory_stock",
            "message": "Look up the current stock for item A-1 in inventory.",
            "connected": ["inventory", "outlook", "datasets"],
            "expect": {"use_tool": True, "service": "inventory"},
        },
        {
            "id": "outlook_rfq",
            "message": (
                "Find the customer email in Outlook about the RFQ and tell "
                "me who sent it."),
            "connected": ["outlook", "datasets"],
            "expect": {"use_tool": True, "service": "outlook"},
        },
        {
            "id": "dataset_price",
            "message": "What's the price of WG-350DSAV?",
            "connected": ["datasets"],
            "expect": {"use_tool": True, "service": "datasets"},
        },
        {
            "id": "no_tool_chat",
            "message": "Thanks, that's all for now.",
            "connected": ["outlook", "datasets"],
            "expect": {"use_tool": False},
        },
        {
            "id": "explicit_email_search",
            "message": "Search my email for the Acme quote thread.",
            "connected": ["outlook"],
            "expect": {"use_tool": True, "service": "outlook"},
        },
    ]


async def _run_planner(
    service: Any, model: str, calls: List[Dict[str, Any]],
    timeout: float,
) -> Dict[str, Any]:
    import core.chat_tool_planner as planner
    from core.chat_tool_planner import ToolPlan

    results = []
    for case in _planner_cases():
        planner.get_connected_services = (
            lambda user_id, connected=case["connected"]: list(connected))
        planner._available_platform_services = lambda: []
        recorder = RecordingLLM(service, model, calls)
        started = time.time()
        try:
            plan = await planner.plan_tool_use(
                case["message"], [], "qualification-user", recorder,
                planning_timeout=timeout)
            error = None
        except Exception as exc:  # noqa: BLE001 - consumer boundary
            plan = None
            error = f"{type(exc).__name__}: {exc}"
        actual = plan.model_dump() if hasattr(plan, "model_dump") else plan
        model_backed = bool(
            actual and "source-ask floor" not in (actual.get("reason") or "")
            and "repair" not in (actual.get("reason") or ""))
        expected = case["expect"]
        matched = bool(actual) and all(
            actual.get(key) == value for key, value in expected.items())
        entry = {
            "id": case["id"],
            "message": case["message"],
            "connected": case["connected"],
            "expected": expected,
            "actual": actual,
            "matched": matched,
            "model_backed": model_backed,
            "seconds": round(time.time() - started, 2),
            "error": error,
            "structured_calls": [
                {k: v for k, v in call.items()
                 if k not in ("prompt", "system_instruction")}
                for call in recorder.calls],
        }
        # A deterministic floor/recovery is evidence of safe degradation, not
        # a model-backed plan. Never count it as a planning pass.
        if not matched or not model_backed:
            # One schema-compatible retry on the exact consumer prompt. This
            # tests transport, not a different task: JSON mode is the same
            # schema with a flat response.
            first = next(
                (call for call in recorder.calls
                 if call.get("prompt")), None)
            if first:
                retry_started = time.time()
                retry_call = {
                    "kind": "planner_json_retry",
                    "case": case["id"],
                    "prompt": first["prompt"],
                    "system_instruction": first.get("system_instruction"),
                }
                try:
                    retry = await service.generate_structured_response(
                        prompt=first["prompt"],
                        system_instruction=first.get(
                            "system_instruction") or
                        "You return only the requested JSON object.",
                        response_model=ToolPlan,
                        temperature=0.0,
                        disable_reasoning=True,
                        task_type="planning",
                        provider_model=("ollama", model),
                        output_mode="json",
                        cascade=False,
                        allow_moa=False,
                        max_tokens=3000,
                        workspace_id="default",
                        tenant_id="default",
                    )
                    retry_call["parsed"] = (
                        retry.model_dump() if hasattr(retry, "model_dump")
                        else retry)
                except Exception as exc:  # noqa: BLE001
                    retry_call["error_type"] = type(exc).__name__
                    retry_call["error"] = str(exc)[:12000]
                retry_call["seconds"] = round(
                    time.time() - retry_started, 2)
                calls.append(retry_call)
                entry["json_retry"] = {
                    k: v for k, v in retry_call.items() if k != "prompt"}
        results.append(entry)

    passed = sum(1 for item in results
                 if item["matched"] and item["model_backed"])
    degraded = sum(1 for item in results
                   if item["matched"] and not item["model_backed"])
    return {
        "consumer": "core.chat_tool_planner.plan_tool_use",
        "cases": results,
        "model_backed_passes": passed,
        "degraded_floor_passes": degraded,
        "failures": len(results) - passed - degraded,
        "status": "passed" if passed == len(results) else "failed",
    }


def _goal_contexts() -> List[Dict[str, Any]]:
    return [
        {
            "id": "ambiguous_quote",
            "context": {
                "run": {
                    "id": "run-qual-1", "goal_id": "goal-qual-1",
                    "role": "operations", "status": "active",
                    "parameters": {"lead": "Acme",
                                   "request": "prepare a quote"},
                    "plan": [{
                        "id": "step-1", "kind": "canvas_work",
                        "title": "Research the lead",
                        "canvas_type": "document"}],
                    "cursor": "step-1", "decision_log": [],
                },
                "goal": {"status": "active", "satisfied": 0, "total": 0},
                "step_digest": {}, "event": {},
                "maturity_tier": "autonomous",
                "agent_name": "Model Employee",
            },
            "expect": "valid decision; REPLAN requires a non-empty new_plan",
        },
        {
            "id": "research_finished",
            "context": {
                "run": {
                    "id": "run-qual-2", "goal_id": "goal-qual-2",
                    "role": "sales", "status": "active",
                    "parameters": {"lead": "Acme", "currency": "USD"},
                    "plan": [
                        {"id": "step-1", "kind": "canvas_work",
                         "title": "Research the lead",
                         "canvas_type": "document"},
                        {"id": "step-2", "kind": "canvas_work",
                         "title": "Draft the quote",
                         "canvas_type": "spreadsheet"},
                    ],
                    "cursor": "step-1", "decision_log": [],
                },
                "goal": {"status": "active", "satisfied": 0, "total": 2},
                "step_digest": {
                    "summary": (
                        "Research complete: Acme needs 2 units of A-1. "
                        "No pricing constraint found yet."),
                    "canvas_id": "canvas-qual-1",
                },
                "event": {},
                "maturity_tier": "autonomous",
                "agent_name": "Model Employee",
            },
            "expect": "ADVANCE or a valid REPLAN with a concrete new_plan",
        },
    ]


def _decision_is_valid(decision: Dict[str, Any]) -> bool:
    from core.goals.goal_run_service import DECISION_TYPES
    kind = str(decision.get("decision") or "").upper()
    if kind not in DECISION_TYPES:
        return False
    if kind == "REPLAN":
        plan = decision.get("new_plan")
        return isinstance(plan, list) and bool(plan)
    if kind == "WAIT":
        return isinstance(decision.get("wait_spec"), dict)
    return True


async def _run_goal(
    service: Any, model: str, calls: List[Dict[str, Any]],
) -> Dict[str, Any]:
    from core.goals.goal_run_router import GoalRunRouter, RouterDecisionModel

    results = []
    for case in _goal_contexts():
        recorder = RecordingLLM(service, model, calls)
        router = GoalRunRouter(
            tenant_id="default", workspace_id="default",
            llm_service=recorder)
        started = time.time()
        try:
            decision = await router.decide(case["context"])
            error = None
        except Exception as exc:  # noqa: BLE001
            decision = None
            error = f"{type(exc).__name__}: {exc}"
        fallback = bool(decision) and str(
            decision.get("rationale") or "").startswith(
                ("router returned an unusable decision",
                 "router unavailable", "low-confidence"))
        valid = (
            bool(decision) and not fallback and _decision_is_valid(decision))
        parsed = [
            call.get("parsed") for call in recorder.calls
            if call.get("parsed") is not None]
        entry = {
            "id": case["id"],
            "expected": case["expect"],
            "decision": decision,
            "valid": valid,
            "fallback": fallback,
            "seconds": round(time.time() - started, 2),
            "error": error,
            "model_outputs": parsed,
            "structured_calls": [
                {k: v for k, v in call.items()
                 if k not in ("prompt", "system_instruction")}
                for call in recorder.calls],
        }
        # A malformed REPLAN gets one schema-compatible corrective retry with
        # the exact consumer prompt plus the defect named. The consumer's own
        # result stays as recorded; this only qualifies whether the model can
        # recover under a clearer schema instruction.
        invalid_replan = bool(
            parsed and any(
                str(p.get("decision") or "").upper() == "REPLAN"
                and not (isinstance(p.get("new_plan"), list)
                         and p.get("new_plan"))
                for p in parsed if isinstance(p, dict)))
        if invalid_replan:
            first = next(
                (call for call in recorder.calls if call.get("prompt")),
                None)
            if first:
                retry_call = {
                    "kind": "goal_replan_retry",
                    "case": case["id"],
                    "prompt": first["prompt"],
                    "system_instruction": first.get("system_instruction"),
                }
                retry_prompt = (
                    first["prompt"]
                    + "\n\nCORRECTION: the previous answer selected REPLAN but "
                      "omitted new_plan. REPLAN REQUIRES new_plan as a "
                      "non-empty JSON array of the full remaining plan steps, "
                      "each with a stable id, kind and title. Return the "
                      "corrected JSON object now.")
                retry_started = time.time()
                try:
                    retry = await service.generate_structured_response(
                        prompt=retry_prompt,
                        system_instruction=first.get(
                            "system_instruction") or
                        "You return only the requested JSON object.",
                        response_model=RouterDecisionModel,
                        temperature=0.0,
                        disable_reasoning=True,
                        provider_model=("ollama", model),
                        output_mode="json",
                        cascade=False,
                        allow_moa=False,
                        max_tokens=2000,
                        workspace_id="default",
                        tenant_id="default",
                    )
                    retry_call["parsed"] = (
                        retry.model_dump() if hasattr(retry, "model_dump")
                        else retry)
                    retry_valid = bool(retry_call["parsed"]) and \
                        _decision_is_valid(retry_call["parsed"]) and \
                        str(retry_call["parsed"].get("decision") or "").upper() \
                        == "REPLAN"
                    retry_call["valid"] = retry_valid
                except Exception as exc:  # noqa: BLE001
                    retry_call["error_type"] = type(exc).__name__
                    retry_call["error"] = str(exc)[:12000]
                retry_call["seconds"] = round(
                    time.time() - retry_started, 2)
                calls.append(retry_call)
                entry["replan_retry"] = {
                    k: v for k, v in retry_call.items() if k != "prompt"}
        results.append(entry)

    passed = sum(1 for item in results if item["valid"])
    return {
        "consumer": "core.goals.goal_run_router.GoalRunRouter.decide",
        "cases": results,
        "valid": passed,
        "failures": len(results) - passed,
        "status": "passed" if passed == len(results) else "failed",
    }


async def _run_alignment(
    service: Any, model: str, calls: List[Dict[str, Any]],
) -> Dict[str, Any]:
    from core.llm.byok_handler import _run_coroutine_sync
    from core.org_alignment import parse_rubric
    from core.org_politics_automation import alignment_verdict

    def chat(system: str, user: str) -> str:
        started = time.time()
        record = {
            "kind": "alignment_chat",
            "system_instruction": system,
            "prompt": user,
            "provider_model": ["ollama", model],
        }
        try:
            text = _run_coroutine_sync(
                service.generate(
                    prompt=user,
                    system_instruction=system,
                    temperature=0.0,
                    max_tokens=400,
                    prefer_cost=True,
                    sticky_hint=("ollama", model),
                    workspace_id="default",
                    tenant_id="default",
                ),
                timeout=120.0,
            )
            record["response"] = text
            return text
        except Exception as exc:  # noqa: BLE001
            record["error_type"] = type(exc).__name__
            record["error"] = str(exc)[:4000]
            return ""
        finally:
            record["seconds"] = round(time.time() - started, 2)
            calls.append(record)

    started = time.time()
    result = alignment_verdict(chat_fn=chat)
    # The judge calls' raw text is already in calls.jsonl; parse each judge
    # response here so a neutral fallback is visible rather than hidden.
    parsed_judges = []
    for call in calls:
        if call.get("kind") != "alignment_chat":
            continue
        if "score proposals for compliance" in (
                call.get("system_instruction") or "").lower():
            parsed_judges.append({
                "prompt": call.get("prompt", "")[-800:],
                "response": call.get("response"),
                "parsed": vars(parse_rubric(call.get("response") or "")),
            })
    return {
        "consumer": "core.org_politics_automation.alignment_verdict",
        "result": result,
        "seconds": round(time.time() - started, 2),
        "calls": len([c for c in calls
                      if c.get("kind") == "alignment_chat"]),
        "parsed_judges": parsed_judges,
        "status": (
            "passed" if result.get("ran") and result.get("green")
            else "failed"),
    }


async def _failure_controls() -> Dict[str, Any]:
    import core.chat_tool_planner as planner
    from core.goals.goal_run_router import (
        GoalRunRouter, RouterDecisionModel,
    )

    controls: Dict[str, Any] = {}

    class SleepLLM:
        async def generate_structured_response(self, **kwargs: Any) -> Any:
            await asyncio.sleep(5)
            return None

    planner.get_connected_services = lambda user_id: ["inventory"]
    planner._available_platform_services = lambda: []
    started = time.time()
    plan = await planner.plan_tool_use(
        "Look up the current stock for item A-1 in inventory.",
        [], "qualification-user", SleepLLM(), planning_timeout=0.25)
    controls["planner_timeout"] = {
        "plan": plan.model_dump() if plan else None,
        "seconds": round(time.time() - started, 2),
        "safe": plan is None,
    }

    class FailingLLM:
        async def generate_structured_response(self, **kwargs: Any) -> Any:
            raise ConnectionError("local model unavailable")

    started = time.time()
    decision = await GoalRunRouter(
        llm_service=FailingLLM()).decide(_goal_contexts()[0]["context"])
    controls["goal_unavailable"] = {
        "decision": decision,
        "seconds": round(time.time() - started, 2),
        "safe": (
            decision.get("decision") == "ASK_HUMAN"
            and not decision.get("new_plan")),
    }

    class InvalidReplanLLM:
        async def generate_structured_response(self, **kwargs: Any) -> Any:
            return RouterDecisionModel(
                decision="REPLAN",
                rationale="change direction",
                parameter_updates={},
                target_step=None,
                new_plan=None,
                wait_spec=None,
                confidence=0.9,
            )

    decision = await GoalRunRouter(
        llm_service=InvalidReplanLLM()).decide(
        _goal_contexts()[0]["context"])
    controls["goal_invalid_replan"] = {
        "decision": decision,
        "safe": decision.get("decision") == "ASK_HUMAN",
    }

    class NoneLLM:
        async def generate_structured_response(self, **kwargs: Any) -> Any:
            return None

    plan = await planner.plan_tool_use(
        "Look up the current stock for item A-1 in inventory.",
        [], "qualification-user", NoneLLM(), planning_timeout=5)
    controls["planner_empty_output"] = {
        "plan": plan.model_dump() if plan else None,
        "safe": plan is None,
    }
    return controls


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ollama-url", default=os.getenv(
        "QUALIFY_OLLAMA_URL", "http://127.0.0.1:11436/v1"))
    parser.add_argument("--model", default=os.getenv(
        "QUALIFY_MODEL", "llama3.1:8b"))
    parser.add_argument("--out", default=os.getenv(
        "QUALIFY_OUT", "/private/tmp/atom-local-ollama/qualification"))
    parser.add_argument("--planner", action="store_true")
    parser.add_argument("--goal", action="store_true")
    parser.add_argument("--alignment", action="store_true")
    parser.add_argument("--failure-controls", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--planner-timeout", type=float, default=120.0)
    args = parser.parse_args()
    run_all = args.all or not any(
        (args.planner, args.goal, args.alignment, args.failure_controls))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    _scratch_environment(args.ollama_url, args.model)
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s %(message)s")

    from core.llm_service import LLMService

    service = LLMService(workspace_id="default", tenant_id="default")
    calls: List[Dict[str, Any]] = []
    report: Dict[str, Any] = {
        "schema": "atom-local-model-qualification-1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "local_model": {
            "base_url": args.ollama_url,
            "declared_model": args.model,
            "provider_pin": f"ollama:{args.model}",
            "scratch_root": str(out),
        },
        "boundaries": [
            "local Ollama only; no cloud/provider key was used",
            "no live provider effect/write/send/credential/spend",
            "availability/pin is not planning-quality acceptance",
            "deterministic floor/recovery is reported as degraded, not a model pass",
            "failed discretionary-judgment verdict remains",
        ],
    }

    if run_all or args.planner:
        report["planner"] = await _run_planner(
            service, args.model, calls, args.planner_timeout)
    if run_all or args.goal:
        report["goal"] = await _run_goal(service, args.model, calls)
    if run_all or args.alignment:
        report["alignment"] = await _run_alignment(
            service, args.model, calls)
    if run_all or args.failure_controls:
        report["failure_controls"] = await _failure_controls()

    statuses = {
        name: report[name].get("status")
        for name in ("planner", "goal", "alignment")
        if name in report
    }
    report["capability_status"] = statuses
    report["status"] = (
        "passed" if statuses and all(v == "passed" for v in statuses.values())
        else "failed")
    (out / "report.json").write_text(
        json.dumps(report, indent=2, default=str) + "\n")
    _write_calls(out, calls)
    print(json.dumps({
        "status": report["status"],
        "capability_status": statuses,
        "report": str(out / "report.json"),
        "calls": len(calls),
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
