# C16 resume record

```json
{
  "schema": "lane3-c16-resume-record-v1",
  "generated_at": "2026-09-27T17:44:57-0400",
  "status": "case 1 (synchronous controlled mutation) PASS; C16 still FAILED overall",
  "harness": {
    "commands": {
      "contract_validation": "backend/venv314/bin/python docs/architecture/orchestration_migration/acceptance/lane3/validate_shim_contract.py --world c16_d0 --out docs/architecture/orchestration_migration/acceptance/lane3/c16_controlled",
      "synchronous_case": "backend/venv314/bin/python docs/architecture/orchestration_migration/acceptance/lane3/controlled_planner_c16.py --world c16_d0 --out docs/architecture/orchestration_migration/acceptance/lane3/c16_controlled --port 8074 --relaunch"
    },
    "files_sha256_16": {
      "controlled_planner_c16.py": "01652ea395e8ca63",
      "validate_shim_contract.py": "e9534825f755d25e",
      "provider_shim.py": "9fd9bf7f1312cd92",
      "planner_script.json": "49b870d7473137df",
      "shim_script.json": "49b870d7473137df"
    }
  },
  "candidate_identity": {
    "base_HEAD": "a8bc48dc13e56c93d54e3a2ba954138e7388e7d5",
    "base_HEAD_short": "a8bc48dc1",
    "branch": "main",
    "working_tree_dirty_paths": 94,
    "working_tree_fingerprint_sha256_16": "1ebdd1ae686fa149",
    "note": "harness fixes are NOT product proof; the uncommitted product diff (D0/D1/D3/D4) is what this run exercised"
  },
  "current_run": {
    "world": "c16_d0",
    "run_id": null,
    "run_dir": "/Users/rushiparikh/projects/atom/backend/data/acceptance_worlds/c16_d0/runs/run-3525cd473660",
    "db_path": "/Users/rushiparikh/projects/atom/backend/data/acceptance_worlds/c16_d0/runs/run-3525cd473660/data/atom.db",
    "backend_port": 8074,
    "api_only": true,
    "planner_pin": "local_935df51a/shim-1",
    "shim_provider_key": "local_935df51a",
    "shim_model": "shim-1",
    "requested_tool_name": "CanvasEditPlan",
    "tool_name_source": "captured from the structured request (tool_names), not assumed",
    "shim_script_shape": "{\"match\": \"CanvasEditPlan\", \"response\": {\"response\": {\"tool_call\": {\"name\": ..., \"arguments\": {...}}}}}"
  },
  "case_1_result": {
    "pass": true,
    "checks": {
      "injection_was_consumed": true,
      "injection_hits": 1,
      "exactly_one_audit_row": true,
      "durable_content_has_the_intended_change": true,
      "the_old_text_is_gone": true,
      "reported_updated_true": true,
      "reported_verified": true,
      "postcondition_verified": true,
      "reported_audit_id_present": true,
      "reported_canvas_is_the_edited_one": true,
      "execution_identity_present": true,
      "operation_identity_present": true,
      "no_stranded_operation": true,
      "accepted_plan_is_the_injected_plan": true,
      "no_fallback_provider_supplied_the_plan": true
    },
    "boundaries": {
      "b1_served": true,
      "b2_parser_accepted": true,
      "b3_no_fallback": true,
      "b4_mutation_audited": true,
      "b5_readback_verified": true
    },
    "reply": "Updated the quote validity to 30 days.",
    "audit_actions": [
      "create",
      "update"
    ],
    "durable_change_verified": true,
    "old_text_removed": true
  },
  "redacted_evidence": {
    "response_keys": [
      "confidence",
      "error_code",
      "execution_id",
      "intent",
      "memory_context",
      "message",
      "metadata",
      "model",
      "next_steps",
      "provider",
      "reasoning",
      "recovery_url",
      "requires_confirmation",
      "session_id",
      "success",
      "suggested_actions",
      "timestamp"
    ],
    "response_preview": {
      "success": true,
      "session_id": "c16-sync-C16SYNC-1790545462",
      "intent": "canvas_edit",
      "confidence": 0.9,
      "suggested_actions": [],
      "requires_confirmation": false,
      "next_steps": [],
      "timestamp": "2026-09-27T17:44:33.845837",
      "metadata": {
        "canvas_edit": {
          "canvas_id": "dd932724-ce58-44fa-81bf-16448531e691",
          "updated": true,
          "execution_id": "1b9913b8-304d-4032-a13f-86db7ec1f14a",
          "operation_id": "1b9913b8-304d-4032-a13f-86db7ec1f14a",
          "outcome": "completed",
          "postcondition_verified": true,
          "audit_id": "623a3069-564e-4f5f-981b-93ae6d62f908",
          "review_status": "accepted",
          "matched_playbooks": [
            {
              "id": "0fa14b32-af62-4002-92a2-42629b545092",
              "name": "[other] or"
            },
            {
              "id": "acc43818-a723-4ed0-ae77-98661ca73514",
              "name": "[tone] 10.5\""
            }
          ]
        },
        "persistence": {
          "status": "persisted"
        }
      },
      "memory_context": null,
      "model": null,
      "provider": null,
      "reasoning": null,
      "execution_id": "1b9913b8-304d-4032-a13f-86db7ec1f14a",
      "error_code": null,
      "recovery_url": null
    },
    "captured_structured_request": [
      {
        "tool_names": [
          "CanvasEditPlan"
        ],
        "tool_mode": true,
        "model": "shim-1",
        "stream": false,
        "matched": true
      },
      {
        "tool_names": [
          "CanvasEditPlan"
        ],
        "tool_mode": true,
        "model": "shim-1",
        "stream": false,
        "matched": true
      },
      {
        "tool_names": [
          "CanvasEditPlan"
        ],
        "tool_mode": true,
        "model": "shim-1",
        "stream": false,
        "matched": true
      }
    ],
    "redaction": "credential-shaped keys/values replaced with <REDACTED>"
  },
  "preserved_worlds_not_rebuilt": {
    "preview_v1": {
      "frontend_port": 3101,
      "backend_port": 8051,
      "touched": false
    },
    "candidate_fix1": {
      "frontend_port": 3102,
      "backend_port": 8071,
      "touched": false
    }
  },
  "remaining": [
    "case 2: background success (pending first, then verified live delivery + reload recovery)",
    "case 3: background failure (persisted terminal failure, no false success, no duplicate effect)",
    "D5 recovery: clearer rendering, live conversation/execution scoping, reconnect/reload, no re-execution",
    "separate real-planner trial matrix (accept / decline / contradiction / repair / provider failure)",
    "full candidate source freeze incl. base HEAD + complete manifest",
    "artifact editing remains EXCLUDED until controlled effect layer AND real-planner workflow pass"
  ]
}
```
