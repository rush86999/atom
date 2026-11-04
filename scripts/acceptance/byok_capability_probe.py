#!/usr/bin/env python3
"""Controlled BYOK capability-routing probe (no provider calls).

Runs the production selector over a fixed candidate/evidence set so the
quality-before-cost policy and strict pin behavior are auditable without a
model campaign or spend.
"""
from __future__ import annotations

import json

from core.llm.capability_profiles import (
    escalation_candidate,
    get_profile,
    pin_decision,
    select_profile_candidates,
)


def candidate(provider, model, quality, cost, context=32768):
    return {
        "provider": provider, "model": model, "quality": quality,
        "cost": cost, "context_window": context,
        "supports_structured": True, "supports_tools": True,
    }


def main() -> int:
    profile = get_profile("employee_adaptive_planning")
    pool = [
        candidate("frontier", "expensive", 99, 20.0),
        candidate("fast", "flash", 90, 1.0),
        candidate("weak", "tiny", 60, 0.01),
    ]
    economy = select_profile_candidates(profile, pool)
    quality = select_profile_candidates(
        profile, pool, preference="quality")
    evidence = {
        "fast/flash": {
            "samples": 6, "successes": 1, "quality_successes": 1,
            "semantic_failures": 3, "unsafe_failures": 0, "retries": 3,
            "latency_ms": 1200, "last_failure_kind": "semantic_failure",
            "profile": profile.name, "profile_version": profile.version,
            "workspace_id": "ws-a", "tenant_id": "t-a",
        },
        "frontier/expensive": {
            "samples": 10, "successes": 10, "quality_successes": 10,
            "semantic_failures": 0, "unsafe_failures": 0, "retries": 0,
            "latency_ms": 4000, "last_failure_kind": "",
            "profile": profile.name, "profile_version": profile.version,
            "workspace_id": "ws-a", "tenant_id": "t-a",
        },
    }
    after_failure = select_profile_candidates(
        profile, pool, evidence=evidence)
    no_suitable = select_profile_candidates(
        profile, [candidate("weak", "tiny", 60, 0.01)])
    good_pin = pin_decision(
        profile, "fast", "flash", quality=90, context_window=32768)
    bad_pin = pin_decision(
        profile, "local", "llama3.1:8b", quality=75, context_window=8192)
    result = {
        "schema": "byok-capability-routing-probe-1",
        "profile": profile.metadata(),
        "pool": pool,
        "economy_order": [
            {"provider": c["provider"], "model": c["model"],
             "evidence_state": c["evidence_state"]}
            for c in economy["ranked"]],
        "quality_order": [
            {"provider": c["provider"], "model": c["model"]}
            for c in quality["ranked"]],
        "measured_failure": {
            "outcome": after_failure["outcome"],
            "ranked": [c["model"] for c in after_failure["ranked"]],
            "excluded": after_failure["excluded"],
            "escalation_from_failed": escalation_candidate(
                profile, after_failure["ranked"], ("fast", "flash")),
        },
        "no_suitable": {
            "outcome": no_suitable["outcome"],
            "excluded": no_suitable["excluded"],
        },
        "pins": {"good": good_pin, "bad": bad_pin},
        "limits": {
            "live_provider_calls": 0,
            "purpose": "controlled selection mechanics, not a model campaign",
        },
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
