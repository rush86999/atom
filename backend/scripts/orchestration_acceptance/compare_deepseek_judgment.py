#!/usr/bin/env python3
"""Frozen, one-shot DeepSeek judgment comparison (diagnostic only).

This harness is intentionally gated. It refuses to read a credential or make
any network call unless BOTH of these are present:

* ``--authorize-deepseek-exception``; and
* ``ATOM_AUTHORIZE_DEEPSEEK_COMPARISON_20261028=1``.

That is the owner's specific, one-run exception to local-only operation. The
application's local-only default, provider policy, stored credentials and the
pilot are not changed. The output is diagnostic comparison evidence, not
application acceptance evidence.

One attempt per fixed case. No semantic retries. Transport retries are zero
and recorded. Prompts and settings are loaded once from the frozen SPEC and
never changed mid-run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(HERE))

from core.review_result import build_review_result  # noqa: E402
from diagnose_minimal_judgment import (  # noqa: E402
    _decision_for,
    _diagnostic,
    _minimal_request,
    _money,
    _write_json,
    expected_from_policy,
    sha256,
)

SPEC_DEFAULT = (
    "docs/acceptance/evidence/whole_app_20261028/"
    "deepseek_judgment_comparison_20261028/SPEC.json"
)
AUTH_ENV = "ATOM_AUTHORIZE_DEEPSEEK_COMPARISON_20261028"


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _read_env_file(path: Path, name: str) -> str:
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        if key.strip() == name:
            return value.strip().strip("'\"")
    return ""


def _byok_entry(args: argparse.Namespace) -> tuple[dict, dict]:
    store_path = Path(args.byok_store).resolve()
    payload = json.loads(store_path.read_text(encoding="utf-8"))
    keys = payload.get("keys", payload)
    key_id = str(args.key_id or "")
    entry = keys.get(key_id) if key_id else None
    if entry is None:
        entry = next(
            (
                value for value in keys.values()
                if isinstance(value, dict)
                and str(value.get("provider_id") or "") == "deepseek"
                and value.get("is_active")
            ),
            {},
        )
        key_id = next(
            (
                name for name, value in keys.items()
                if value is entry
            ),
            key_id,
        )
    return dict(entry or {}), {
        "key_id": key_id,
        "key_hash": (entry or {}).get("key_hash"),
        "is_active": bool((entry or {}).get("is_active")),
        "store_sha256": sha256(store_path),
        "store_path": str(store_path),
    }


def _credential(
    args: argparse.Namespace, name: str, *, decrypt: bool = True,
) -> tuple[str, str, dict]:
    if args.byok_store:
        entry, meta = _byok_entry(args)
        if not entry or not entry.get("is_active"):
            return "", "byok_store", meta
        if not decrypt:
            return "", "byok_store", meta
        if not args.byok_key_file:
            raise SystemExit(
                "--byok-key-file is required with --byok-store")
        key_file = Path(args.byok_key_file).resolve()
        from cryptography.fernet import Fernet

        fernet = Fernet(key_file.read_bytes().strip())
        value = fernet.decrypt(
            str(entry["encrypted_key"]).encode()).decode()
        meta["key_file_sha256"] = sha256(key_file)
        return value, "byok_store", meta
    if args.env_file:
        path = Path(args.env_file).resolve()
        value = _read_env_file(path, name)
        return value, f"env_file:{path}", {"env_file_sha256": sha256(path)}
    return str(os.environ.get(name) or ""), "process_environment", {}


def _synthetic_evidence(case: dict) -> dict:
    row_number = str(case.get("row_ref") or "minimal_judgment!R2").rsplit(
        "R", 1)[-1]
    return {
        "evidence_id": (
            f"ev:{case['subject']}:minimal_judgment!R{row_number}"),
        "subject_id": case["subject"],
        "source_identity": {
            "file_name": "minimal_judgment_eval.csv",
            "resource_id": "eval:minimal_judgment",
            "content_hash": "eval:minimal_judgment",
        },
        "retrieval_operation": f"eval:{case['case_id']}",
        "retrieval_execution_id": f"eval-{case['case_id']}",
        "row_ref": case.get("row_ref") or f"minimal_judgment!R{row_number}",
        "target_status": "matched",
        "values": [
            {"field": "Invoice Amount", "value": float(case["amount"])},
            {"field": "State", "value": "Open"},
        ],
    }


def _build_requests(spec: dict, source: dict) -> list[dict]:
    full_messages = list(source["messages"])
    full_evidence = list(source["evidence_index"])
    full_policy = list(source["policy_index"])
    allowed = list(source["allowed_decisions"])
    preserved = next(
        entry for entry in full_evidence
        if entry.get("subject_id") == "IN-7301")
    prepared = []
    for case in spec["cases"]:
        expected = expected_from_policy(
            _money(case["amount"]), str(spec["source"]["policy_lesson"]))
        if expected != case["expected"]:
            raise SystemExit(
                f"SPEC DRIFT: {case['case_id']} expected {case['expected']} "
                f"but policy yields {expected}")
        if case["kind"] == "full_context":
            messages = full_messages
            evidence = full_evidence
            policy = full_policy
            execution_id = str(source.get("execution_id") or "deepseek-full")
            requested_records = list(source["subjects"])
            request_meta = {
                "kind": "preserved_full_context",
                "message_count": len(messages),
            }
        else:
            evidence_entry = (
                dict(preserved) if case.get("preserved_row")
                else _synthetic_evidence(case))
            messages, _contract, evidence, policy = _minimal_request(
                case["subject"], float(case["amount"]), evidence_entry,
                full_policy[0], allowed)
            execution_id = f"deepseek-{case['case_id']}"
            requested_records = [case["subject"]]
            request_meta = {
                "kind": "minimal_complete",
                "message_count": len(messages),
                "row_values": evidence_entry.get("values"),
            }
        prepared.append({
            **case,
            "execution_id": execution_id,
            "requested_records": requested_records,
            "messages": messages,
            "evidence_index": evidence,
            "policy_index": policy,
            "allowed_decisions": allowed,
            "request_sha256": _canonical_sha256(messages),
            "request_meta": request_meta,
        })
    return prepared


def _post(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    generation: dict,
) -> tuple[dict, dict, float]:
    started = time.monotonic()
    response = client.post(
        base_url.rstrip("/") + "/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": generation["temperature"],
            "max_tokens": generation["max_tokens"],
            "stream": generation["stream"],
        },
        timeout=float(generation["request_timeout_seconds"]),
    )
    latency_ms = int((time.monotonic() - started) * 1000)
    try:
        payload = response.json()
    except Exception:  # noqa: BLE001
        payload = {"raw_text": response.text[:8000]}
    headers = {
        key: value for key, value in response.headers.items()
        if key.lower() in {
            "x-request-id", "request-id", "x-ratelimit-limit",
            "x-ratelimit-remaining", "retry-after",
        }
    }
    return payload, {
        "http_status": response.status_code,
        "headers": headers,
        "transport_retries": 0,
    }, latency_ms


def _content(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return ""
    return str((choices[0].get("message") or {}).get("content") or "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", default=SPEC_DEFAULT)
    parser.add_argument("--out-dir")
    parser.add_argument(
        "--env-file",
        help=(
            "Read only DEEPSEEK_API_KEY from this local env file. The key is "
            "never written to output."
        ),
    )
    parser.add_argument(
        "--byok-store",
        help=(
            "Read the existing authorized DeepSeek key from this encrypted "
            "BYOK store. Read-only; the key is never written to output."
        ),
    )
    parser.add_argument(
        "--byok-key-file",
        help="Fernet key file for --byok-store.",
    )
    parser.add_argument(
        "--key-id",
        default="tenant_default_deepseek_default_production",
        help="BYOK key id to use (default: the active DeepSeek default key).",
    )
    parser.add_argument("--check-credential", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--authorize-deepseek-exception", action="store_true")
    args = parser.parse_args()

    spec_path = Path(args.spec).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec_sha = sha256(spec_path)
    source_path = (Path(__file__).resolve().parents[3]
                   / spec["source"]["preserved_request"]).resolve()
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if sha256(source_path) != spec["source"]["preserved_request_sha256"]:
        raise SystemExit("SOURCE DRIFT: preserved request hash changed")
    if spec.get("status") != "prepared_not_authorized":
        raise SystemExit(
            "SPEC STATUS CHANGED: this harness is frozen at "
            "'prepared_not_authorized'")

    prepared = _build_requests(spec, source)
    if len(prepared) != 7:
        raise SystemExit(f"EXPECTED 7 CASES, got {len(prepared)}")
    request_hashes = {
        case["case_id"]: case["request_sha256"] for case in prepared
    }

    if args.check_credential:
        value, origin, meta = _credential(
            args, spec["provider"]["credential_env_var"], decrypt=False)
        present = bool(value) if origin != "byok_store" else bool(
            meta.get("is_active") and meta.get("key_hash"))
        print(json.dumps({
            "credential_env_var": spec["provider"]["credential_env_var"],
            "credential_present": present,
            "credential_origin": origin,
            "credential_metadata": meta,
            "decrypted": False,
            "external_call_made": False,
        }, indent=1))
        return 0 if present else 4

    if not args.out_dir:
        raise SystemExit("--out-dir is required for a dry run or comparison")
    out_dir = Path(args.out_dir).resolve()
    if args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_json(out_dir / "PREPARED_REQUESTS.json", {
            "schema": "deepseek-judgment-prepared-requests-1",
            "spec": str(spec_path),
            "spec_sha256": spec_sha,
            "source_request": str(source_path),
            "source_request_sha256": sha256(source_path),
            "provider": spec["provider"],
            "generation": spec["generation"],
            "request_hashes": request_hashes,
            "external_call_made": False,
        })
        print(json.dumps({
            "status": "prepared_not_authorized",
            "cases": len(prepared),
            "request_hashes": request_hashes,
            "external_call_made": False,
        }, indent=1))
        return 0

    if not args.authorize_deepseek_exception or (
            os.environ.get(AUTH_ENV) != "1"):
        raise SystemExit(
            "AUTHORIZATION REQUIRED: one isolated DeepSeek comparison has "
            "not been authorized. Provide --authorize-deepseek-exception and "
            f"{AUTH_ENV}=1 for this run only. No credential was read and no "
            "external call was made.")
    if results_path := (out_dir / "results.json"):
        if results_path.exists():
            raise SystemExit(
                f"REFUSING TO OVERWRITE preserved results: {results_path}")

    api_key, credential_origin, credential_meta = _credential(
        args, spec["provider"]["credential_env_var"], decrypt=True)
    if not api_key:
        raise SystemExit("CREDENTIAL ABSENT: no external call was made.")

    out_dir.mkdir(parents=True, exist_ok=True)
    generation = spec["generation"]
    provider = spec["provider"]
    started_at = datetime.now(timezone.utc).isoformat()
    cases = []
    aborted = None
    client = httpx.Client(
        trust_env=False,
        transport=httpx.HTTPTransport(retries=0),
    )
    try:
        for case in prepared:
            messages = case["messages"]
            try:
                payload, transport, latency_ms = _post(
                    client, provider["base_url"], api_key,
                    provider["model"], messages, generation)
            except Exception as exc:  # noqa: BLE001 — one attempt, no retry
                cases.append({
                    "case_id": case["case_id"],
                    "kind": case["kind"],
                    "subject": case["subject"],
                    "amount": case["amount"],
                    "expected": case["expected"],
                    "request_sha256": case["request_sha256"],
                    "request_file": None,
                    "response_file": None,
                    "review_file": None,
                    "raw_decision": None,
                    "substantive_match": False,
                    "certified": False,
                    "errors": [{
                        "code": "transport_error",
                        "type": type(exc).__name__,
                        "detail": str(exc)[:500],
                    }],
                    "provider_id": provider["id"],
                    "model_requested": provider["model"],
                    "response_model": None,
                    "latency_ms": None,
                    "usage": None,
                    "http_status": None,
                    "transport_retries": 0,
                })
                break
            content = _content(payload)
            review = build_review_result(
                execution_id=case["execution_id"],
                requested_records=case["requested_records"],
                answer=content,
                allowed_decisions=case["allowed_decisions"],
                evidence_index=case["evidence_index"],
                policy_index=case["policy_index"],
            )
            decision = _decision_for(review, case["subject"])
            request_file = f"cases/{case['case_id']}_request.json"
            response_file = f"cases/{case['case_id']}_response.json"
            review_file = f"cases/{case['case_id']}_review.json"
            _write_json(out_dir / request_file, {
                "messages": messages,
                "request_sha256": case["request_sha256"],
                "request_meta": case["request_meta"],
            })
            _write_json(out_dir / response_file, payload)
            _write_json(out_dir / review_file, review)
            usage = payload.get("usage") or {}
            cases.append({
                "case_id": case["case_id"],
                "kind": case["kind"],
                "subject": case["subject"],
                "amount": case["amount"],
                "expected": case["expected"],
                "requested_records": case["requested_records"],
                "raw_decision": decision,
                "substantive_match": decision == case["expected"],
                "certified": bool(review.get("ok")),
                "errors": review.get("errors") or [],
                "request_sha256": case["request_sha256"],
                "request_file": request_file,
                "response_file": response_file,
                "review_file": review_file,
                "provider_id": provider["id"],
                "model_requested": provider["model"],
                "response_model": payload.get("model"),
                "response_id": payload.get("id"),
                "latency_ms": latency_ms,
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                },
                "http_status": transport["http_status"],
                "response_headers": transport["headers"],
                "transport_retries": transport["transport_retries"],
            })
            if transport["http_status"] in (401, 403, 429):
                aborted = (
                    f"http_{transport['http_status']} stopped the run before "
                    "remaining cases")
                break
    finally:
        client.close()

    results = {
        "schema": "deepseek-judgment-comparison-1",
        "status": "completed" if len(cases) == 7 and not aborted else "aborted",
        "not_acceptance_evidence": True,
        "spec": str(spec_path),
        "spec_sha256": spec_sha,
        "source_request": str(source_path),
        "source_request_sha256": sha256(source_path),
        "authorization": {
            "scope": spec["authorization"]["scope"],
            "local_only_default_unchanged": True,
            "provider_policy_unchanged": True,
            "stored_credentials_unchanged": True,
            "pilot_unchanged": True,
        },
        "provider": {
            "id": provider["id"],
            "name": provider["name"],
            "base_url": provider["base_url"],
            "model": provider["model"],
            "credential_env_var": provider["credential_env_var"],
            "credential_origin": credential_origin,
            "credential_metadata": credential_meta,
            "credential_value_recorded": False,
        },
        "generation": generation,
        "started_at_utc": started_at,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "request_hashes": request_hashes,
        "transport_retries": 0,
        "semantic_retries": 0,
        "aborted": aborted,
        "cases": cases,
        "summary": {
            "raw_judgment_matches": sum(
                1 for case in cases if case["substantive_match"]),
            "certified": sum(1 for case in cases if case["certified"]),
            "total_cases": len(cases),
            "expected_total_cases": 7,
            "raw_and_certified": sum(
                1 for case in cases
                if case["substantive_match"] and case["certified"]),
        },
        "interpretation_rule": (
            "A label is correct only when the applicable teaching's own "
            "threshold text yields it. No decision label has an inherent "
            "safety rank. Format/reference validity is reported separately "
            "and never substitutes for judgment."
        ),
    }
    _write_json(out_dir / "results.json", results)
    print(json.dumps(results["summary"], indent=1))
    return 0 if results["status"] == "completed" else 5


if __name__ == "__main__":
    raise SystemExit(main())
