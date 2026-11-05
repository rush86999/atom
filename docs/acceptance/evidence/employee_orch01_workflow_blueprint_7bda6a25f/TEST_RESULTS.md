# ORCH-01 — test results

Executed 2026-11-05. Controlled store: isolated SQLite. Served qualification:
existing local Ollama route `ollama/llama3.1:8b` at `127.0.0.1:11436`; provider
transport was not doubled for the two served cases.

## ORCH-01 controls

```text
pytest tests/test_orch01_workflow_blueprint.py -q
```

Result: **15 passed**. The table covers:

- two domains (service intake/review; recurring inventory/operations review);
- exact persisted readback from a fresh session;
- forged body identity ignored; foreign workspace/tenant read 404;
- HITL approval insertion before `notify`/`write`/entity mutations;
- malformed, empty, unknown type/action, duplicate, dangling, cyclic,
  multiple-start, missing-capability and trigger negatives;
- timeout/unavailable typed responses with no persisted workflow;
- bounded model calls (one per request).

## Focused affected selection

```text
pytest \
  tests/test_orch01_workflow_blueprint.py \
  tests/test_round69_async_unguarded_surfaces.py::TestGenerateFromAgentAuth \
  tests/test_bughunt_agents_wave10c.py::TestGenerateFromAgentRealQueen \
  tests/test_covpush_w52_queen_agent.py \
  tests/core/agents/test_queen_agent.py \
  tests/test_covpush_w73b_agents.py \
  tests/test_workflow_realization.py \
  tests/test_advanced_workflow_system.py \
  tests/test_advanced_workflows_simple.py \
  tests/test_covpush_w28_advanced_workflow.py \
  tests/test_covpush_w29_workflow_engine_graph.py \
  tests/test_covpush_w63_workflow_ui_endpoints.py \
  tests/test_covpush_w103_workflow_composer.py \
  tests/test_covpush_w103_workflow_templates.py \
  tests/test_covpush_w109_workflow_templates.py \
  tests/test_covpush_w21_workflow_engine.py \
  tests/test_workload_capability_routing.py \
  tests/test_employee_byok_consumer_routing.py \
  tests/test_workload_incident_identity.py -q
```

Result: **634 passed** in 91.18 s (`focused-314.log`) and **634 passed** in
106.92 s (`focused-311.log`, `-p no:randomly`).

`workflow-neighborhood.log`: **443 passed** (the workflow files in the same
selection; included in the 634).

Known baseline-only timing tests excluded from the focused selection:

```text
tests/test_round69_async_unguarded_surfaces.py::TestWorkflowSchedulerCriticalNodes::test_execute_job_runs_critical_nodes_when_authorized
tests/test_round69_async_unguarded_surfaces.py::TestWorkflowSchedulerCriticalNodes::test_execute_job_runs_benign_nodes
```

They fail identically at base `81c5962bd` because the scheduler starts the
execution asynchronously and the assertion runs before the fake engine is
populated. No ORCH-01 code path is involved.

## Served qualification

```text
TESTING=1 PYTHONPATH=$PWD/backend \
  python /private/tmp/orch01_served_qualification.py
```

Two cases, one structured call each, no expected blueprint supplied:

| Case | Status | Latency | Prompt/completion tokens | Workflow | Readback |
|---|---|---:|---:|---|---|
| `service_intake_review` | accepted | 16.18 s | 1,608 / 371 | `ai_wf_e063d42320d5` | exact |
| `inventory_operations_review` | accepted | 12.78 s | 1,603 / 332 | `ai_wf_f24c8824d6f8` | exact |

Both served the configured `ollama/llama3.1:8b` route under profile
`workflow_blueprint` v2026-11-05.1. Actual structured prompts, raw completions,
usage, routing and persisted/readback definitions are in
`served-qualification.json`.

The two accepted cases had:
- service: two HITL gates (`notify_reviewer`, `record_review_decision`);
- inventory: one HITL gate (`update_stock_review_record`) and a schedule
  trigger retained in the blueprint but absent from live orchestrator triggers.

`served-protocol-negative.log` preserves the first TOOLS-mode protocol attempt:
the model returned a function-call envelope and the structured transport
reported no parsed blueprint. The existing JSON structured mode then produced
the accepted two-case result; no provider/route was added or substituted.

## Exact commands and source

- Base: `81c5962bd`
- Code: `7bda6a25f`
- `PYTHONPATH=backend`, `TESTING=1`; Python 3.14.7 and 3.11.16.
- Served route is the already-configured local Ollama on `127.0.0.1:11436`;
  the two calls were serialized (one at a time). No cloud provider, credential,
  spend, download or deployment was used.

## Scope

This qualifies workflow design, typed validation, durable scoped readback and
the HITL representation. It does not qualify workflow execution quality,
scheduling reliability, fleet recruitment, general adaptive judgment or served
multi-model comparison.
