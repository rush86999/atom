# Web generated-workflow handoff — evidence packet

Packet directory reference: `docs/acceptance/evidence/web_generated_workflow_handoff_2ce38f305/`

## What this proves

- The Automations → AI Agents **Deploy** action now has a server-owned, scoped
  handoff into the existing JSON workflow catalog; the SQL blueprint remains
  execution authority.
- Generated execution reloads the scoped canonical SQL definition, recomputes
  the compiler digest, re-registers through the existing blueprint consumer,
  and runs the existing canonical orchestrator. The positive execution uses a
  real supported read-only entity lookup handler, not an invented no-op.
- Actual fresh-OS-process roundtrip: parent generates/deploys through public
  routes; a separate Python process with only the same scratch SQLite DB,
  catalog and `ATOM_DATA_DIR` reads My Workflows, executes the real handler,
  and returns a durable execution/step result. A third fresh process verifies
  persisted results, exact business outputs/matches/status/errors, the same
  execution/operation/owner, idempotent `already_deployed` replay, exactly one
  execution row, and no scheduler job.
- Generated execution history/details are scope-strict. Foreign users get 404.
  Missing/unavailable authority is `unknown`, not an implicit global/legacy
  grant; a durable execution row's server-bound scope is the fallback.
  Positively identified legacy rows keep their previous compatibility.
- Shared catalog writers use strict mutation reads and atomic replacement;
  corrupt/unreadable/wrong-shape catalogs are preserved with zero writes.
  Failed lock acquisition refuses rather than writing unguarded. Legacy
  natural-language edit commits one row with stale refusal instead of replacing
  a whole old snapshot.

## Claim boundary (explicit non-claims)

- This is **not** a served-model or model-quality claim. Generation used real
  `compile_blueprint` and the real SQL/catalog/orchestrator path with only the
  model transport doubled. The fresh child is explicitly guarded against model
  calls.
- This is **not** a browser/UI-runtime, whole-app ORACLE, PostgreSQL,
  multi-worker, soak, or production deployment claim. All evidence is scratch
  (`TESTING=1`, unique DB/data/catalog).
- Legacy workflow rows are preserved; their global isolation is not newly
  certified. The new strict scope applies only to new generated deployment
  metadata and to positively identified authority.
- No raw database, credentials, tokens, or secrets are included. Logs are
  sanitized; paths are redacted to `<scratch-path>`.

## Gates

| Gate | Result | Log |
|---|---|---|
| Backend handoff suite at frozen base `2ce38f305` | 25 passed | `gates/backend_handoff_25_frozen_2ce.txt` |
| Affected workflow regression at frozen base | 135 passed | `gates/affected_135_frozen_2ce.txt` |
| Frontend parent/child/scheduler at frozen base | 48 passed | `gates/frontend_48_frozen_2ce.txt` |
| Backend handoff suite at successor `23a9a4496` | 30 passed | `gates/backend_handoff_30_successor_23a9a44.txt` |
| Affected workflow regression at successor | 135 passed | `gates/affected_135_successor_23a9a44.txt` |
| Frontend parent/child/scheduler at successor | 48 passed | `gates/frontend_48_successor_23a9a44.txt` |
| Local root-control replay at successor | 10 passed | `gates/local_root_probes_10_successor.txt` |

Root independent controls history:

- `root_controls/root_7_accept_2ce.*` — 7/7 at frozen `2ce` (critical race
  proof accepted; not overall handoff acceptance).
- `root_controls/root_zzy_9_with_2_scope_fails.*` — original 9 controls; 2
  foreign history/details reads leaked and failed, revealing the scope-readback
  gap.
- `root_controls/root_uzsv_10th_metadata_outage_fail.*` — added metadata-outage
  control; execution row was readable while projection/SQL authority was
  unavailable, and the old fallback wrongly granted legacy access.
- `root_controls/root_g6f_10_pass_successor.*` — all 10 unchanged controls
  pass at the successor source, `same_source: true`, `actual_exit: 0`.

## Fresh-process evidence

- `fresh_process/fresh_process_roundtrip.py` — the test-only child helper.
- `fresh_process/fresh_process_child_results.txt` — captured `FRESH_CHILD_RUN`
  and `FRESH_CHILD_VERIFY` JSON, including the real lookup step (`matches: []`
  at scratch; handler completed), same execution id, same operation id, same
  owner, one execution row, no scheduler jobs, `model_calls: false`.
- The parent test also asserts exact normalized business results between the
  child run and the third fresh read. The run route returns a list and the
  persisted read returns a dict; normalization is by exact `step_id` and only
  excludes documented volatile `execution_time_ms` timing. Status, errors,
  matches and all other business values are compared exactly.

## Commands

Backend handoff suite (scratch):

```
TESTING=1 DATABASE_URL=sqlite:///<scratch>/handoff.db \
ATOM_DATA_DIR=<scratch>/data \
PYTHONPATH=<backend>:<plugins> \
python -m pytest backend/tests/test_generated_workflow_handoff.py \
  -q -p no:cacheprovider -p no:randomly
```

Affected workflow regression:

```
TESTING=1 DATABASE_URL=sqlite:///<scratch>/affected.db \
ATOM_DATA_DIR=<scratch>/data \
PYTHONPATH=<backend>:<plugins> \
python -m pytest \
  backend/tests/test_bughunt_api_wave.py \
  backend/tests/test_r79_workflow_dynamic_rows.py \
  backend/tests/test_covpush_api_wave.py \
  backend/tests/api/test_atom_agent_endpoints.py \
  backend/tests/test_orch01_real_checkpoint_contract.py \
  backend/tests/test_workflow_scheduler_recovery.py \
  backend/tests/test_covpush_w105_workflow_approval_routes.py \
  -k 'workflow or Workflow' -q -p no:cacheprovider -p no:randomly
```

Frontend:

```
cd frontend-nextjs
node_modules/.bin/jest \
  tests/pages/automations-page.test.tsx \
  components/Automations/__tests__/test-agent-workflow-generator.test.tsx \
  tests/automations/test-workflow-scheduler.test.tsx \
  --runInBand --ci --silent
```

Fresh-process test (spawns real child OS processes):

```
python -m pytest \
  backend/tests/test_generated_workflow_handoff.py::test_actual_fresh_process_roundtrip \
  -q -s -p no:cacheprovider -p no:randomly
```

Root controls (independent):

```
python -m pytest /private/tmp/root-workflow-handoff-independent-20261110.py \
  -q -p no:cacheprovider -p no:randomly
```

## Original public-route reproduction

`first_gate/public_route_reconciliation.txt` and
`first_gate/public_route_reconciliation.py` preserve the original read-only
reconciliation: real compile output, generated blueprint absent from My
Workflows, no deploy route, no scheduler job, and in-memory-only execution
before the repair. This is historical reproduction, not the final positive.

## Research and tradeoff

See `research/PRIMARY_LINKS.md`. In short: Camunda distinguishes deployed
process definitions from process instances and verifies deployment separately
from starting an instance. Atom reuses its existing SQL blueprint, HITL rows,
JSON catalog projection and orchestrator; no Camunda or new workflow framework
was installed, and no new store/engine/schema was added.
