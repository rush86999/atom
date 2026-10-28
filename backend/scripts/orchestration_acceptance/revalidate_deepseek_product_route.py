#!/usr/bin/env python3
"""Offline product-route reconciliation for the saved DeepSeek assessment.

No model call. Reads the saved response/history, fetches the persisted agent
journal (local API), and checks the route/policy/evidence/persistence claims.
The one-shot script's teach parser missed the response shape; the journal is
the authoritative read side of the same endpoint.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import httpx

EXPECTED = {"IN-7301": "DECLINE", "IN-7302": "HOLD", "IN-7303": "HOLD"}
POLICY_PREFIX = "Use exactly these decision labels: FUND, HOLD, DECLINE."
SOURCE_HASH = "0a84a5f50661bc8a7917d158bcd36cad5b3f0262"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8062")
    parser.add_argument("--password-file", required=True)
    parser.add_argument("--dir", required=True)
    parser.add_argument("--log", required=True)
    args = parser.parse_args()
    root = Path(args.dir).resolve()
    result = _json(root / "product_route_result.json")
    history = _json(root / "history.json")
    base = args.base_url.rstrip("/")
    password = Path(args.password_file).read_text(encoding="utf-8").strip()
    client = httpx.Client(trust_env=False, timeout=60.0)
    login = client.post(
        base + "/api/auth/login",
        json={"username": "admin@example.com", "password": password})
    token = str(login.json().get("access_token") or "")
    headers = {"Authorization": f"Bearer {token}"}
    detail = client.get(
        base + f"/api/agents/{result['agent_id']}", headers=headers).json()
    _write(root / "agent_detail.json", detail)
    learning = (((detail.get("data") or {}).get("configuration") or {})
                .get("learning") or {})
    points = [p for p in (learning.get("log") or []) if isinstance(p, dict)]
    point = next(
        (p for p in points
         if str(p.get("lesson") or "").startswith(POLICY_PREFIX)),
        {},
    )
    policy_id = str(point.get("id") or "")
    review = result.get("review") or {}
    decisions = result.get("decisions") or {}
    refs_ok = True
    policy_refs_ok = True
    evidence_details: list[dict] = []
    for assessment in review.get("assessments") or []:
        subject = str(assessment.get("subject_id") or "")
        for ref in assessment.get("evidence_refs") or []:
            identity = ref.get("source_identity") or {}
            values = {
                str(v.get("field")): v.get("value")
                for v in (ref.get("values") or []) if isinstance(v, dict)
            }
            evidence_details.append({
                "subject": subject,
                "row_ref": ref.get("row_ref"),
                "content_hash": identity.get("content_hash"),
                "values": values,
            })
            refs_ok = refs_ok and (
                identity.get("content_hash") == SOURCE_HASH
                and ref.get("row_ref") in {"vendor_loop!R2", "vendor_loop!R3",
                                           "vendor_loop!R4"}
                and values.get("State") == "Open")
        refs = assessment.get("policy_refs") or []
        policy_refs_ok = policy_refs_ok and bool(refs) and all(
            str(ref.get("policy_id")) == policy_id
            and str(ref.get("lesson") or "") == str(point.get("lesson") or "")
            for ref in refs
        )
    final_text = ""
    for message in reversed(history.get("messages") or []):
        response = message.get("response") or {}
        if response.get("message"):
            final_text = str(response["message"])
            break
    history_ok = all(
        subject in final_text and decision in final_text
        for subject, decision in EXPECTED.items()
    ) and "VALIDATED REVIEW" in final_text
    log_text = Path(args.log).read_text(encoding="utf-8", errors="replace")
    dispatch = {
        "provider_policy": sorted(set(re.findall(
            r"provider policy selected: allowed=\['deepseek'\] "
            r"preferred=\('deepseek', 'deepseek-v4-pro'\) revision=(\w+)",
            log_text))),
        "route_gate": sorted(set(re.findall(
            r"\[route-gate\] EXPLICIT OVERRIDE deepseek/deepseek-v4-pro[^\n]*",
            log_text))),
        "provider_http": sorted(set(re.findall(
            r"POST https://api\.deepseek\.com/v1/chat/completions[^\n]*",
            log_text))),
        "inflight": sorted(set(re.findall(
            r"\[inflight\] deepseek/deepseek-v4-pro released[^\n]*",
            log_text))),
        "byok_logic": sorted(set(re.findall(
            r"BYOK Logic: complexity=\w+, provider=deepseek, "
            r"model=deepseek-v4-pro",
            log_text))),
        "cost_lines": sorted(set(re.findall(
            r"LLM Cost Attributed \(BYOK\): deepseek-v4-pro[^\n]*",
            log_text))),
    }
    dispatch_ok = all(dispatch[key] for key in (
        "provider_policy", "route_gate", "provider_http", "inflight",
        "byok_logic"))
    checks = {
        "teaching_persisted": bool(policy_id),
        "review_certified": bool(review.get("ok")),
        "decisions_match": decisions == EXPECTED,
        "evidence_bound": refs_ok,
        "policy_refs_match": policy_refs_ok,
        "response_model_deepseek_v4_pro": (
            str(result.get("response", {}).get("model") or "")
            == "deepseek-v4-pro"
            and str(result.get("response", {}).get("provider") or "")
            == "deepseek"),
        "history_agrees": history_ok,
        "actual_dispatch_captured": dispatch_ok,
    }
    payload = {
        "schema": "deepseek-product-route-revalidation-1",
        "no_model_call": True,
        "policy_id": policy_id,
        "policy_lesson": point.get("lesson"),
        "checks": checks,
        "all_ok": all(checks.values()),
        "decisions": decisions,
        "expected": EXPECTED,
        "evidence": evidence_details,
        "history_final_text": final_text,
        "dispatch": dispatch,
        "note": (
            "The first product-route script treated the teach response as a "
            "teaching_point object and marked that step false. The persisted "
            "agent journal and the review's policy refs prove the same point "
            "was written; no model call or decision rewrite occurred here."),
    }
    _write(root / "product_route_revalidated.json", payload)
    _write(root / "dispatch_evidence.json", dispatch)
    print(json.dumps({"all_ok": payload["all_ok"], "checks": checks},
                     indent=1))
    return 0 if payload["all_ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
