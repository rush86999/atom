# Browser info-wait driver — preparation preflight (2026-11-07)

Status: **PREPARATION ONLY.** No world was built or launched, no application
server was started, no browser was driven, no provider/model/account/credential
was used, and no dependency was installed. Root owns the actual browser
acceptance.

Source at this preflight: `378a893906bd2b5e1a0f721539d9780a35b19309`
(the combined candidate merged PR735/PR737, plus the driver commits).

Driver: `scripts/acceptance/browser_agent_job_wait.py`
Authored completions: `scripts/acceptance/fixtures/browser_agent_job_wait_shim.json`

## What was validated

`preflight.json` was produced by the driver's safe default mode against the
real `core.react_models.ReActStep` schema and the existing
`provider_shim.load_script` index. It records:

- `TESTING=1` and explicit fresh scratch `DATABASE_URL`/`ATOM_DATA_DIR`/
  `ATOM_OFFICE_DIR`, all outside the live `backend/data` tree;
- source HEAD, tracked/backend cleanliness, driver and fixture SHA-256;
- five authored envelopes parsed by the real `ReActStep` model
  (first wait, second wait, two wording variants of the `tasks.create` step,
  final answer), with no `correlation_id`/`hitl_action_id` in model input;
- the existing `provider_shim.load_script` indexes all five entries, including
  the bare `ReActStep` first-wait fallback, in the intended precedence order;
- the default response is labelled as simulated control transport;
- dependency, port, world and storage observations, with missing execute-only
  dependencies recorded as warnings rather than claimed.

Checks passed: `scratch_environment`, `source_head_recorded`,
`source_expected_sha_ok`, `backend_tree_clean`, `react_schema_envelopes`,
`provider_shim_index`, `default_labelled`.

Not exercised here: world build/storage-guard acceptance, backend/frontend
launch, Playwright/login, the provider-shim process or real structured
consumer transport, durable `AgentJob`/`AgentExecution`/`HITLAction`/
`BoardTask` effects, and any live provider/model/account.

## Exact commands used

```bash
python3 -m py_compile scripts/acceptance/browser_agent_job_wait.py
python3 scripts/acceptance/browser_agent_job_wait.py --help

SCRATCH=$(mktemp -d "$TMPDIR/atom-browser-preflight-XXXXXX")
mkdir -p "$SCRATCH/data" "$SCRATCH/office"
TESTING=1 \
DATABASE_URL="sqlite:///$SCRATCH/atom.db" \
ATOM_DATA_DIR="$SCRATCH/data" \
ATOM_OFFICE_DIR="$SCRATCH/office" \
python3 scripts/acceptance/browser_agent_job_wait.py \
  --preflight --out "$SCRATCH/report"
```

`pyflakes` also reported no issues for the driver.

## Remaining inputs for root's execution

1. Run from the frozen/combined capture worktree, not this preparation
   worktree. That worktree needs `backend/venv314/bin/python` and
   `frontend-nextjs/node_modules`; both are absent here and were **not**
   installed.
2. Choose a unique fresh `--world`; the driver refuses an existing world.
3. Choose free backend/frontend/shim ports.
4. Supply a scratch admin password source: `--admin-password-file` (0600) or
   `--provision-admin-password` (app's own bootstrap, scratch user only).
5. Run the root-owned execution:

```bash
python scripts/acceptance/browser_agent_job_wait.py --execute \
  --world browser_wait_<unique> \
  --backend-port 8031 --frontend-port 3131 --shim-port 8097 \
  --out <scratch-evidence>/browser_wait_<sha10> \
  --provision-admin-password
```

The execution path calls `core.world_storage_guard.require_storage_ready()`
before `build_world`, uses the existing measured `storage_policy` estimate,
never sets `ATOM_WORLD_STORAGE_BYPASS`, and refuses the live dev DB and an
existing world. It composes `run_isolated`, `provider_shim`,
`case5_browser_recovery` and `browser_verify.ui_login`; it does not replace the
real `LLMService`/structured consumer/GenericAgent loop with a ReAct-step
double and does not seed job/result/plan/receipt rows.

## Honest labels

The authored ReAct steps are **simulated model decisions / controlled
transport**. Only the provider response is substituted; routing, execution,
persistence, wait/resume, the registered `tasks.create` action and the default
oracle run in production code. No served-model quality or general judgment is
claimed. The positive path uses one job; duplicate- and stale-answer negatives
reuse that same job, so no second job is created.
