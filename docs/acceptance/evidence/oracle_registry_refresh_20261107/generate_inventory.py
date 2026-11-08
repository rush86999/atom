#!/usr/bin/env python3
"""Regenerate the authoritative enabled-registry-to-verifier map.

Unlike the historical coverage snapshots, this script imports BOTH lazy
registration modules (AgentRadio and BPE) before reading the registry, because
the real RPC router and MCP service do the same.  It records the source commit,
the trusted effect declaration, the verifier state, and an explicit
qualification/ownership bucket.  It is an inventory, not a qualification run.

Run from the repository root:

    TESTING=1 PYTHONPATH=backend python \
        docs/acceptance/evidence/oracle_registry_refresh_20261107/generate_inventory.py
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def _source() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _classification(name: str, effects) -> str:
    from core.action_effects import (
        declares_mutation,
        declares_plan_output,
        declares_read_only,
        effect_entries,
    )

    entries = effect_entries(effects or [])
    scopes = {
        str(item.get("scope") or "").strip().lower()
        for item in entries
        if isinstance(item, dict)
    }
    if declares_mutation(entries):
        return "mutation_local" if "local" in scopes else "mutation_external"
    if declares_plan_output(entries) or name == "goals.decompose":
        return "plan_output_validation"
    if declares_read_only(entries):
        return "read_only"
    return "undeclared"


def _bucket(name: str, kind: str, verified: bool) -> str:
    """Qualification/ownership bucket, deliberately not a runtime claim."""
    if kind == "read_only":
        return "enabled_read_only"
    if kind == "plan_output_validation":
        return "enabled_plan_output"
    if kind == "undeclared":
        return "unqualified_undeclared"
    if verified:
        return "enabled_covered"
    if name in {"radio.create_thread"}:
        return "enabled_uncovered_selected_trace"
    if name in {"radio.send_message"}:
        return "enabled_uncovered_pending_merge"
    if name in {"workspace.commit", "workspace.note"}:
        return "enabled_uncovered_deferred"
    if name == "mini_app_run":
        return "enabled_unqualified_guest_runtime"
    if name.startswith("shopify_"):
        return "enabled_uncovered_provider_pending_review"
    return "enabled_uncovered"


def main() -> int:
    os.environ.setdefault("TESTING", "1")
    # Import order mirrors app startup / the RPC router.
    import core.connected_actions  # noqa: F401
    import core.oracle.postcondition_verifiers  # noqa: F401
    import core.agent_radio.radio_actions  # noqa: F401
    import core.bpe.actions  # noqa: F401
    from core.action_registry import action_registry
    from core.oracle import get_postcondition

    rows = []
    for name in sorted(action_registry.list_actions()):
        action = action_registry.get_action(name)
        effects = list(getattr(action, "effects", None) or [])
        kind = _classification(name, effects)
        verified = get_postcondition(name) is not None
        rows.append({
            "action": name,
            "kind": kind,
            "effects": effects,
            "verifier_registered": verified,
            "bucket": _bucket(name, kind, verified),
            "description": (getattr(action, "description", "") or "")[:180],
        })

    mutations = [row for row in rows if row["kind"].startswith("mutation_")]
    payload = {
        "schema": "atom-oracle-registry-refresh-2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "executed_source": _source(),
        "lazy_registration_modules": [
            "core.agent_radio.radio_actions",
            "core.bpe.actions",
        ],
        "scope": (
            "Source-bound enabled-registry-to-verifier inventory with lazy "
            "AgentRadio/BPE modules loaded. Static counts are discovery "
            "evidence, never runtime coverage or acceptance."
        ),
        "counts": {
            "registered_actions": len(rows),
            "declared_mutations": len(mutations),
            "mutation_local": sum(
                1 for row in mutations if row["kind"] == "mutation_local"),
            "mutation_external": sum(
                1 for row in mutations if row["kind"] == "mutation_external"),
            "mutation_covered": sum(
                1 for row in mutations if row["verifier_registered"]),
            "mutation_uncovered": sum(
                1 for row in mutations if not row["verifier_registered"]),
            "read_only": sum(1 for row in rows if row["kind"] == "read_only"),
            "plan_output_validation": sum(
                1 for row in rows
                if row["kind"] == "plan_output_validation"),
            "undeclared": sum(1 for row in rows if row["kind"] == "undeclared"),
        },
        "uncovered_mutations": [
            row["action"] for row in mutations if not row["verifier_registered"]
        ],
        "covered_mutations": [
            row["action"] for row in mutations if row["verifier_registered"]
        ],
        "provider_reconciliation": {
            "origin_main": "36fa4ce39",
            "covered_on_main": [
                "shopify_create_article",
                "shopify_create_blog",
                "shopify_create_product",
            ],
            "pending_owner_review": {
                "owner": "root worker 56636 (PRs 745/748/749/750)",
                "rows": ["shopify_create_fulfillment"],
                "note": (
                    "Not edited here. Provider integration trees are outside "
                    "this worker's ownership."
                ),
            },
            "historical_snapshot_note": (
                "docs/acceptance/evidence/oracle_registry_coverage_20261107*/ "
                "records 90 actions / 26 mutations / 15 covered at an older "
                "source; it is preserved but not current."
            ),
        },
        "actions": rows,
    }

    out = Path(__file__).with_name("inventory.json")
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload["counts"], indent=2, sort_keys=True))
    print("uncovered:", payload["uncovered_mutations"])
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
