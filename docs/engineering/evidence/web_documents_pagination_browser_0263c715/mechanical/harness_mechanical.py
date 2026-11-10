#!/usr/bin/env python3
"""No-browser mechanical tests for the prepared document pagination harness."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

HARNESS = Path("/private/tmp/root-web-document-pagination-browser-20261110.py")
RESULT = Path("/private/tmp/root-web-document-pagination-harness-mechanical-20261110-result.json")


def load():
    spec = importlib.util.spec_from_file_location("doc_pagination_harness", HARNESS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def page_obs(ids, count, has_more, next_offset, next_disabled, prev_disabled):
    return {
        "dom_ids": list(ids),
        "api_ids": list(ids),
        "api_status": 200,
        "total": 130,
        "count": count,
        "has_more": has_more,
        "next_offset": next_offset,
        "next_offset_present": next_offset is not None,
        "card_count": len(ids),
        "foreign_ids": [],
        "unknown_ids": [],
        "duplicate_ids": [],
        "next_disabled": next_disabled,
        "previous_disabled": prev_disabled,
    }


def valid_observations(module):
    p1 = list(module.EXPECTED_PAGE1)
    p2 = list(module.EXPECTED_PAGE2)
    return {
        "fresh": {"cookies_empty": True, "local_storage_empty": True,
                  "session_storage_empty": True},
        "environment": {"database_url_scratch": True,
                        "atom_data_dir_scratch": True,
                        "lancedb_base_scratch": True,
                        "testing_harness_process": "0"},
        "documents_page_status": 200,
        "signup": {"landed_dashboard": True, "register_calls": 1,
                   "user_rows": 1, "workspace_bound": True},
        "onboarding": {"present": True, "completed_via_ui": True},
        "seed": {"authorized": 130, "foreign": 7, "shared": 3,
                 "via_handler": True, "authorized_workspace": "ws1"},
        "page1": page_obs(p1, 100, True, 100, False, True),
        "page2": page_obs(p2, 30, False, None, True, False),
        "previous": page_obs(p1, 100, True, 100, False, True),
        "reload": page_obs(p1, 100, True, 100, False, True),
        "beyond": {"api_status": 200, "count": 0, "total": 130,
                   "has_more": False, "next_offset_present": False},
        "canonical": {
            "session_status": 200, "me_status": 200,
            "me_matches_session": True, "me_matches_db": True,
            "decoded_sdk_matches_me": True, "same_backend_generation": True,
            "sdk_cookie_encrypted_not_raw": True, "sdk_cookie_http_only": True,
            "one_user_row": True, "workspace_bound": True,
            "workspace_ids_match": True,
        },
        "store": {"unchanged": True, "path_scoped": True,
                  "foreign_rows": 7, "shared_rows": 3},
    }


def main():
    module = load()
    base = valid_observations(module)
    cases = []

    def check(name, mutate, expected_failure):
        obs = copy.deepcopy(base)
        mutate(obs)
        result = module.evaluate_checks(obs)
        ok = (result["passed"] is False and expected_failure in result["failures"])
        cases.append({
            "case": name, "failed_as_required": ok,
            "failures": result["failures"],
        })

    valid = module.evaluate_checks(copy.deepcopy(base))
    cases.append({
        "case": "valid_observations_pass",
        "failed_as_required": valid["passed"] is True and not valid["failures"],
        "failures": valid["failures"],
    })

    def foreign(obs):
        obs["page1"]["dom_ids"].append("w2-doc-000")
        obs["page1"]["foreign_ids"].append("w2-doc-000")
        obs["page1"]["card_count"] += 1

    check("injected_foreign_card_must_fail", foreign, "page1_dom_exact")

    def wrong_order(obs):
        obs["page1"]["dom_ids"][0], obs["page1"]["dom_ids"][1] = (
            obs["page1"]["dom_ids"][1], obs["page1"]["dom_ids"][0])
        obs["page1"]["api_ids"][0], obs["page1"]["api_ids"][1] = (
            obs["page1"]["api_ids"][1], obs["page1"]["api_ids"][0])

    check("wrong_order_must_fail", wrong_order, "page1_dom_exact")

    def missing_status(obs):
        obs["page1"]["api_status"] = None

    check("missing_api_status_must_fail", missing_status, "page1_api_status")

    def duplicate(obs):
        obs["page1"]["dom_ids"][1] = obs["page1"]["dom_ids"][0]
        obs["page1"]["duplicate_ids"] = [obs["page1"]["dom_ids"][0]]

    check("duplicate_ids_must_fail", duplicate, "page1_dom_exact")

    def none_total(obs):
        obs["page1"]["total"] = None

    check("none_observation_must_fail", none_total, "page1_total")

    def next_enabled(obs):
        obs["page2"]["next_disabled"] = False

    check("page2_next_enabled_must_fail", next_enabled, "page2_next_disabled")

    def api_mismatch(obs):
        obs["page1"]["api_ids"] = list(reversed(obs["page1"]["api_ids"]))

    check("dom_api_order_mismatch_must_fail", api_mismatch, "page1_api_exact")

    def foreign_page2(obs):
        obs["page2"]["dom_ids"].append("shared-doc-000")
        obs["page2"]["foreign_ids"].append("shared-doc-000")
        obs["page2"]["card_count"] += 1

    check("shared_card_on_page2_must_fail", foreign_page2, "page2_dom_exact")

    passed = all(c["failed_as_required"] for c in cases)
    output = {
        "ok": passed,
        "harness": str(HARNESS),
        "harness_sha256": __import__("hashlib").sha256(HARNESS.read_bytes()).hexdigest(),
        "cases": cases,
        "case_count": len(cases),
        "all_cases_failed_as_required": passed,
    }
    RESULT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
