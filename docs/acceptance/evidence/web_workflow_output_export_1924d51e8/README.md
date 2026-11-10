# Workflow execution result export — evidence packet

Packet: `docs/acceptance/evidence/web_workflow_output_export_1924d51e8/`

## Scope

Adds a supported **Download results** action to ordinary workflow Execution
Details. It projects one fresh durable `WorkflowExecution` row into a
deterministic JSON result document through the public route:

`GET /api/v1/workflows/workflows/executions/{execution_id}/export`

Reuses the existing durable execution outputs, generated read-scope helper,
owner/current-actor checks, existing blob-download UX, and `FileResponse`-style
safe delivery conventions. No new store, engine, schema, approval lifecycle,
filesystem artifact path, or core-profile enablement.

## Claim boundary

- Supported format is deterministic JSON only. This is **not** a DOCX/PPTX/
  email-generation claim and not a whole-app/served-model/browser claim.
- Scratch evidence only (`TESTING=1`, unique SQLite/data/catalog). No live
  provider/model credential, send, spend, install or deployment.
- Export is read-only. It never executes, forks, resumes, reruns, promotes or
  creates a scheduler job.
- Root independent export acceptance is still pending; the prior 7-negative
  root run failed at checkpoint `70cc3b7e7` and is preserved here. Local replay
  of those 7 negatives passes at the repaired checkpoint.

## Completion/refusal contract

- Completion is not trusted from the row's top-level `completed` status.
- The persisted canonical compiled step list is the authority for expected step
  ids. History must be a non-empty list of objects with exact, unique,
  non-empty step ids; all required canonical steps must be covered; unknown,
  duplicate or missing identities are refused.
- Allowed step success states are the canonical engine completion states
  (`completed`, `success`). `skipped` is accepted only when the authoritative
  step configuration marks the step optional. Unknown statuses
  (`blocked`, `unavailable`, `budget_exceeded`, `rejected`, arbitrary strings)
  are refused.
- Final outputs must match canonical step ids and history statuses. Missing,
  extra, non-object or contradictory outputs are refused.
- Missing definition/step contract, missing history, missing output, unreadable
  output, incomplete/partial, failed/cancelled/running/waiting executions and
  contradictory failed steps return typed 409 refusals; no success document is
  fabricated.
- Credential-shaped keys/values and absolute local paths in outputs are
  detected and refused with field paths only (no values) rather than silently
  rewriting business data. The document includes exact business results plus
  server-bound definition digest/status and requested executor provenance where
  the existing persisted data provides it.

## Determinism and authority

- Each click re-reads the fresh durable row, current active actor/scope/view
  permission, generated read scope and owner. Modal/cache/client-supplied
  identity is never authority.
- Bytes are deterministic: parent and two separate fresh OS processes produced
  the same 1,404-byte document and SHA-256 `91bc0193619f664b857ac1971d70d3bc3df35c41489ddddc06ab1f7d057b018a`
  for the recorded scratch execution.
- ETag is the actual SHA-256 of the response body. Filename is a safe ASCII
  attachment name; no local path is exposed. The stored context blob is not
  included.
- Toggling the same file generation is a read-only projection; repeated exports
  create no execution rows and no scheduler jobs.

## Gates at repaired checkpoint

| Gate | Result | Log |
|---|---|---|
| Export suite | 10 passed | `gates/export_suite_10.txt` |
| Combined handoff + export backend | 40 passed | `gates/combined_40.txt` |
| Affected workflow regression | 135 passed | `gates/affected_135.txt` |
| Frontend Execution Details/page/generator | 42 passed | `gates/frontend_42.txt` |
| Root export negatives replayed locally | 7 passed | `gates/root_export_negatives_local_7.txt` |

Boundary probe at base `7fd05261c`: export route returned **404** and Execution
Details returned raw results keys only (`boundary/base_export_404_and_raw_results.txt`).

Root negative run at `70cc3b7e7`: `actual_exit 1`, all 7 export probes failed
(`root_controls/root_export_negatives_70cc.*`). The repair derives coverage from
the canonical compiled definition and refuses malformed/incomplete/unknown
material. Root independent re-run remains required.

## UI

- Ordinary `ExecutionDetailView` and the execution modal in
  `WorkflowAutomation` both call the real export endpoint on click, consume the
  blob, use the server-safe filename, and show an inline error on refusal.
- Download is disabled unless the execution is completed/success. No
  console-only success, no blind cached export, no new UI flow.
- No browser/build claim; Jest component/page tests only.

## Commands

Export suite:

```
TESTING=1 DATABASE_URL=sqlite:///<scratch>/export.db \
ATOM_DATA_DIR=<scratch>/data PYTHONPATH=<backend>:<plugins> \
python -m pytest backend/tests/test_workflow_output_export.py \
  -q -p no:cacheprovider -p no:randomly
```

Combined backend:

```
python -m pytest backend/tests/test_workflow_output_export.py \
  backend/tests/test_generated_workflow_handoff.py \
  -q -p no:cacheprovider -p no:randomly
```

Fresh-process export bytes/hash:

```
python -m pytest \
  backend/tests/test_workflow_output_export.py::test_export_fresh_process_bytes_and_hash_match \
  -q -s -p no:cacheprovider -p no:randomly
```

Frontend:

```
cd frontend-nextjs
node_modules/.bin/jest \
  components/Automations/__tests__/ExecutionDetailView.test.tsx \
  tests/pages/automations-page.test.tsx \
  components/Automations/__tests__/test-agent-workflow-generator.test.tsx \
  --runInBand --ci --silent
```

Root export negatives:

```
python -m pytest /private/tmp/root-workflow-export-independent-20261110.py \
  -q -p no:cacheprovider -p no:randomly
```

## Sanitation

Only sanitized text logs and review JSON are included. No raw database, cookies,
credentials, tokens, secrets or absolute user paths; paths are redacted.
