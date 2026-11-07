#!/usr/bin/env python3
"""Run the frozen-PR integration matrix and build the identity crosswalk.

Only observed production/test files are executed.  The family list is the
meaningful union of the frozen reviewed heads plus current-main originals:
positive maturity, neutral wait/browser identity, radio, image/SSRF, Shopify
fulfillment, and Article/product material/replay.  No broad unrelated suite is
included.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PACKET = Path(__file__).resolve().parent
REPO = PACKET.parents[3]
BACKEND = REPO / "backend"

FROZEN = {
    "745": "182dab986cce9fcd5afb587ddd3451c1532ca524",
    "747": "ee6b3efd8ee23f1387d4c0ff768d7652e657c5a6",
    "748": "e0ca9cca0d5627e39d6eaa7cdafac8d0d0905d41",
    "749": "3a188840dbf92a1f8f0ceb5eb1471051d44ed991",
    "750": "bf94fc1f81732375055130e1ccc8e4fed8586d0c",
}

FAMILIES = {
    "positive_745": {
        "head": FROZEN["745"],
        "production": ["backend/core/agent_governance_service.py"],
        "tests": ["backend/tests/test_positive_maturity_no_demotion.py"],
    },
    "wait_browser_main": {
        "head": "origin/main",
        "production": [],
        "tests": [
            "backend/tests/test_information_wait_maturity_neutral.py",
            "backend/tests/test_agent_generic_information_wait.py",
            "scripts/tests/test_browser_agent_job_wait_identity.py",
        ],
    },
    "radio_749": {
        "head": FROZEN["749"],
        "production": [
            "backend/core/agent_radio/radio_actions.py",
            "backend/core/agent_radio/radio_mutations.py",
            "backend/core/oracle/postcondition_verifiers.py",
            "backend/core/oracle/request_expectations.py",
        ],
        "tests": [
            "backend/tests/test_covpush_w80a_radio.py",
            "backend/tests/test_lead_radio_readback_identity.py",
            "backend/tests/test_oracle_radio_send.py",
        ],
    },
    "image_748": {
        "head": FROZEN["748"],
        "production": [
            "backend/core/asset_content_receipt.py",
            "backend/core/oracle/postcondition_verifiers.py",
            "backend/core/shopify_mutations.py",
            "backend/integrations/shopify_service.py",
        ],
        "tests": [
            "backend/tests/test_asset_content_receipt.py",
            "backend/tests/test_lead_asset_usable_image.py",
            "backend/tests/test_lead_shopify_image_content_receipt.py",
        ],
    },
    "fulfillment_750": {
        "head": FROZEN["750"],
        "production": [
            "backend/core/action_registry.py",
            "backend/core/connected_actions.py",
            "backend/core/oracle/postcondition_verifiers.py",
            "backend/core/oracle/request_expectations.py",
            "backend/core/shopify_mutations.py",
            "backend/integrations/shopify_service.py",
        ],
        "tests": [
            "backend/tests/test_lead_shopify_fulfillment_rest_shape.py",
            "backend/tests/test_oracle_shopify_fulfillment_create.py",
            "backend/tests/test_shopify_fulfillment_actions.py",
        ],
    },
    "article_product_main": {
        "head": "origin/main",
        "production": [
            "backend/core/shopify_mutations.py",
            "backend/integrations/shopify_service.py",
            "backend/core/oracle/postcondition_verifiers.py",
        ],
        "tests": [
            "backend/tests/test_oracle_shopify_article_create.py",
            "backend/tests/test_lead_shopify_article_rest_shape.py",
            "backend/tests/test_oracle_shopify_blog_create.py",
            "backend/tests/test_oracle_shopify_product_create.py",
            "backend/tests/test_oracle_shopify_product_replay.py",
            "backend/tests/test_oracle_shopify_product_authorized_material.py",
            "backend/tests/test_lead_shopify_authorized_material.py",
        ],
    },
}

MATRIX = [
    "tests/test_oracle_registry_verification_gap.py",
    "tests/test_oracle_effect_families.py",
    "tests/test_oracle_connected_mutations.py",
    "tests/test_assignment_executor.py",
    "tests/test_generic_oracle_mutation_contract.py",
    "tests/test_lead_shopify_authorized_material.py",
    "tests/test_oracle_shopify_product_authorized_material.py",
    "tests/test_oracle_shopify_product_create.py",
    "tests/test_oracle_shopify_product_replay.py",
    "tests/test_oracle_shopify_blog_create.py",
    "tests/test_oracle_shopify_article_create.py",
    "tests/test_lead_shopify_article_rest_shape.py",
    "tests/test_lead_shopify_error_privacy.py",
    "tests/test_generic_request_expectations.py",
    "tests/test_generic_reconcile_commit_contract.py",
    "tests/test_generic_normal_retry_identity.py",
    "tests/test_oracle_radio_send.py",
    "tests/test_lead_radio_readback_identity.py",
    "tests/test_agent_generic_information_wait.py",
    "tests/test_information_wait_maturity_neutral.py",
    "tests/test_positive_maturity_no_demotion.py",
    "../scripts/tests/test_browser_agent_job_wait_identity.py",
    "tests/test_oracle_shopify_fulfillment_create.py",
    "tests/test_lead_shopify_fulfillment_rest_shape.py",
    "tests/test_shopify_fulfillment_actions.py",
    "tests/test_asset_content_receipt.py",
    "tests/test_lead_asset_usable_image.py",
    "tests/test_lead_shopify_image_content_receipt.py",
    "tests/test_covpush_w95_shopify.py::TestFulfillments",
    "tests/test_covpush_saaspair.py::test_shopify_fulfillments",
    "tests/test_covpush_saaspair.py::test_shopify_create_fulfillment_minimal",
    "tests/test_covpush_intgr_b.py::TestShopifyService::test_write_operations",
    "tests/test_covpush_w87_freshdesk_trello_shopify.py::test_sh_write_endpoints",
    "tests/test_covpush_w80a_radio.py",
]


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_blob(ref: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=REPO)


def _counts(output: str) -> dict:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    summary = lines[-1] if lines else ""
    counts = {}
    for value, label in re.findall(
            r"(\d+) (failed|passed|error|errors|skipped|deselected)", summary):
        counts["errors" if label == "error" else label] = int(value)
    return counts


def _functions(source: str, *, test_file: bool) -> list[str]:
    tree = ast.parse(source)
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not test_file or child.name.startswith("test_"):
                            names.append(f"{node.name}.{child.name}")
            elif not test_file or node.name.startswith("test_"):
                names.append(node.name)
    return sorted(names)


def _duplicate_names(source: str) -> dict[str, list[int]]:
    tree = ast.parse(source)
    seen = defaultdict(list)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            seen[node.name].append(node.lineno)
    return {name: lines for name, lines in seen.items() if len(lines) > 1}


def _duplicate_names_at(ref: str, path: str) -> dict[str, list[int]]:
    """Duplicates at a ref; an absent file contributes no duplicates."""
    try:
        return _duplicate_names(_git_blob(ref, path).decode())
    except subprocess.CalledProcessError:
        return {}


def _crosswalk() -> dict:
    head = _git("rev-parse", "HEAD")
    families = {}
    duplicate_audit = {}
    for family, spec in FAMILIES.items():
        source_head = spec["head"]
        entry = {
            "frozen_source": source_head,
            "production": {},
            "tests": {},
            "missing_production": [],
            "missing_tests": [],
        }
        for path in spec["production"]:
            head_names = _functions(
                _git_blob(source_head, path).decode(), test_file=False)
            integration_names = _functions(
                (REPO / path).read_text(encoding="utf-8"), test_file=False)
            missing = sorted(set(head_names) - set(integration_names))
            entry["production"][path] = {
                "frozen_functions": head_names,
                "integration_functions": integration_names,
                "missing_in_integration": missing,
                "integration_additions": sorted(
                    set(integration_names) - set(head_names)),
                "frozen_sha256": _sha(_git_blob(source_head, path)),
                "integration_sha256": _sha((REPO / path).read_bytes()),
            }
            entry["missing_production"].extend(
                f"{path}:{name}" for name in missing)
            duplicate_audit[path] = {
                "integration": _duplicate_names(
                    (REPO / path).read_text(encoding="utf-8")),
                "origin_main": _duplicate_names_at("origin/main", path),
                "frozen": _duplicate_names_at(source_head, path),
            }
        for path in spec["tests"]:
            head_names = _functions(
                _git_blob(source_head, path).decode(), test_file=True)
            integration_names = _functions(
                (REPO / path).read_text(encoding="utf-8"), test_file=True)
            missing = sorted(set(head_names) - set(integration_names))
            entry["tests"][path] = {
                "frozen_tests": head_names,
                "integration_tests": integration_names,
                "missing_in_integration": missing,
                "integration_additions": sorted(
                    set(integration_names) - set(head_names)),
                "frozen_sha256": _sha(_git_blob(source_head, path)),
                "integration_sha256": _sha((REPO / path).read_bytes()),
            }
            entry["missing_tests"].extend(f"{path}:{name}" for name in missing)
            duplicate_audit[path] = {
                "integration": _duplicate_names(
                    (REPO / path).read_text(encoding="utf-8")),
                "origin_main": _duplicate_names_at("origin/main", path),
                "frozen": _duplicate_names_at(source_head, path),
            }
        families[family] = entry

    new_duplicates = {}
    for path, audit in duplicate_audit.items():
        introduced = {
            name: lines for name, lines in audit["integration"].items()
            if name not in audit["origin_main"] and name not in audit["frozen"]
        }
        if introduced:
            new_duplicates[path] = introduced

    registrations = {}
    verifier_text = (REPO / "backend/core/oracle/postcondition_verifiers.py").read_text()
    expectations_text = (
        REPO / "backend/core/oracle/request_expectations.py").read_text()
    for name in ("radio.send_message", "shopify_create_fulfillment"):
        registrations[name] = {
            "postcondition": verifier_text.count(
                f'@register_postcondition("{name}")'),
            "durable_projector": verifier_text.count(
                f'@register_durable_receipt_projector("{name}")'),
            "durable_matcher": verifier_text.count(
                f'@register_durable_receipt_matcher("{name}")'),
        }
    registrations["request_expectation_keys"] = {
        "radio": expectations_text.count('"_oracle_expected_radio_message"'),
        "fulfillment": expectations_text.count(
            '"_oracle_expected_shopify_fulfillment"'),
    }

    canonical = {}
    for path in (
        "backend/core/generic_agent.py",
        "backend/api/agent_routes.py",
        "backend/api/canvas_pdf_routes.py",
    ):
        main_sha = _sha(_git_blob("origin/main", path))
        integration_sha = _sha((REPO / path).read_bytes())
        canonical[path] = {
            "origin_main_sha256": main_sha,
            "integration_sha256": integration_sha,
            "equal": main_sha == integration_sha,
        }

    return {
        "executed_source": head,
        "frozen_heads": FROZEN,
        "families": families,
        "duplicate_ast_audit": {
            "new_duplicates_in_reviewed_files": new_duplicates,
            "pre_existing_action_registry": {
                "names": ["_mini_app_db_query", "_mini_app_db_write"],
                "present_in_origin_main": True,
                "function_source_byte_identical": True,
                "decorator_metadata_differs": True,
                "removed": False,
                "reason": (
                    "pre-existing current-main action registrations; removing "
                    "would change which decorated action identity wins and is "
                    "outside the frozen integration families"),
            },
        },
        "registration_completeness": registrations,
        "canonical_current_main_identity": canonical,
    }


def main() -> int:
    head = _git("rev-parse", "HEAD")
    crosswalk = _crosswalk()
    (PACKET / "IDENTITY_CROSSWALK.json").write_text(
        json.dumps(crosswalk, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")

    bad = [
        family for family, entry in crosswalk["families"].items()
        if entry["missing_production"] or entry["missing_tests"]
    ]
    if bad:
        print(json.dumps({"missing_family_identities": bad}, sort_keys=True))
        return 1
    if crosswalk["duplicate_ast_audit"][
            "new_duplicates_in_reviewed_files"]:
        print(json.dumps({"new_duplicate_ast_functions": crosswalk[
            "duplicate_ast_audit"]["new_duplicates_in_reviewed_files"]},
            sort_keys=True))
        return 1
    for name, counts in crosswalk["registration_completeness"].items():
        if not isinstance(counts, dict):
            continue
        if name == "request_expectation_keys":
            if set(counts.values()) != {1}:
                print(json.dumps({"incomplete_request_expectation": {
                    name: counts}}, sort_keys=True))
                return 1
        elif any(value != 1 for value in counts.values()):
            print(json.dumps({"incomplete_registration": {
                name: counts}}, sort_keys=True))
            return 1

    scratch = Path(tempfile.mkdtemp(
        prefix="integration-745-750-",
        dir=os.environ.get("ATOM_EVIDENCE_TMP") or None,
    ))
    log_path = PACKET / "decisive-matrix.log"
    xml_path = PACKET / "decisive-matrix.xml"
    exit_path = PACKET / "decisive-matrix-exit.json"
    env = os.environ.copy()
    env.update({
        "TESTING": "1",
        "SECRET_KEY": "synthetic-integration-secret",
        "DATABASE_URL": f"sqlite:///{scratch / 'scratch.db'}",
        "ENABLE_SCHEDULER": "false",
        "PYTHONPATH": str(BACKEND),
    })
    command = [
        sys.executable, "-m", "pytest", *MATRIX, "-q", "--tb=short",
        "--basetemp", str(scratch / "basetemp"),
        "-p", "no:cacheprovider",
        f"--junitxml={xml_path}",
    ]
    started = datetime.now(timezone.utc).isoformat()
    completed = subprocess.run(
        command, cwd=BACKEND, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    finished = datetime.now(timezone.utc).isoformat()
    log_path.write_text(completed.stdout, encoding="utf-8")
    exit_payload = {
        "phase": "decisive-matrix",
        "executed_source": head,
        "started_utc": started,
        "finished_utc": finished,
        "command": command,
        "cwd": str(BACKEND),
        "counts": _counts(completed.stdout),
        "exit_code": completed.returncode,
        "testing": env["TESTING"],
        "database_url": env["DATABASE_URL"],
    }
    exit_path.write_text(
        json.dumps(exit_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    shutil.rmtree(scratch, ignore_errors=True)

    source_files = {}
    for family in crosswalk["families"].values():
        for path in list(family["production"]) + list(family["tests"]):
            if (REPO / path).exists():
                source_files[path] = _sha((REPO / path).read_bytes())
    binding = {
        "executed_source": head,
        "executed_source_subject": _git("log", "-1", "--format=%s", head),
        "origin_main": _git("rev-parse", "origin/main"),
        "source_files": source_files,
        "python": sys.version,
        "python_executable": sys.executable,
        "live_calls": False,
        "credentials_used": False,
        "http_leaf_only_doubled": True,
        "testing": "1",
    }
    (PACKET / "source-binding.json").write_text(
        json.dumps(binding, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(json.dumps({
        "executed_source": head,
        "exit_code": completed.returncode,
        "counts": exit_payload["counts"],
        "missing_family_identities": bad,
        "new_duplicate_ast_functions": bool(
            crosswalk["duplicate_ast_audit"][
                "new_duplicates_in_reviewed_files"]),
    }, sort_keys=True))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
