# TASK-WAIT-01 — ordinary UI authorized-source answer episode

**STATUS: PREPARED — NOT LAUNCHED. Root owns the single actual browser run and
its acceptance decision.**

Prepared source commit: `929979f4a4a279668020118b613d4f2eaafe0dd2`
Prepared driver: `scripts/acceptance/browser_agent_source_answer.py`
Prepared shim fixture: `scripts/acceptance/fixtures/browser_agent_source_answer_shim.json`
Preparation tests: `scripts/tests/test_browser_agent_source_answer_preflight.py`
Reused accepted driver: `scripts/acceptance/browser_agent_job_wait.py`
Reused isolated-world launcher: `backend/scripts/orchestration_acceptance/run_isolated.py`

## What this episode proves

One ordinary user, one fresh isolated world, one admitted GenericAgent job and
one execution:

1. normal login and visible onboarding;
2. one objective submitted through the Agents page Run dialog;
3. the agent asks a durable question for an authorized source;
4. the user uploads an authorized document through the ordinary Assignments
   page;
5. uploading alone does not settle the question, create a task or call the
   model;
6. the same job/execution/question survives returning to Agents and a real
   backend+frontend restart;
7. the wait panel's authorized-source picker lists the uploaded document from
   the normal catalog;
8. the user selects it and submits a source-only answer once;
9. the same execution continues, invokes the registered `tasks.create`, the
   default Oracle verifies it, and exactly one durable BoardTask exists;
10. the final UI, public job read and durable rows agree;
11. the controlled source content actually entered the served provider
    request, while server-owned correlation/HITL ids did not;
12. no second objective, manual advance, second job or synthetic row is used.

Only the loopback provider response is authored. Every authored completion is
labelled **SIMULATED MODEL DECISIONS / CONTROLLED TRANSPORT**. This is not
served-model quality or live-provider evidence.

## Blocking prerequisite found after the root gate

The root independent source/process/namespace gate completed at
`0509877ed20101b4e3e1e1123d1d54000e5fe7f2`:

- `actual_exit = 0`
- `22 passed, 115 warnings in 93.19s`
- outputs: `/private/tmp/root-generic-source-binding-recheck.{log,spec.json,exit.json}`

A new post-gate probe was then added at `1ac32d01530f2ac33f44cfd071d386873dcaab1b`:
`backend/tests/test_lead_generic_source_scope_cas.py`. It currently fails
**4/4** (`workspace_id`, `tenant_id`, `user_id`, `params`) because a peer change
to the durable wait scope/params after source read is not blocked by the pending
claim. The raw run is preserved in this packet
(`post-gate-scope-cas-fail.log` / `post-gate-scope-cas-finding.json`).

Per the current instruction, backend/API/test runtime was **not modified** for
this preparation checkpoint. Root must resolve or coordinate that API-gate
failure before running the ordinary UI episode. The prepared UI path itself is
not a workaround for the failing probe.

## Hard constraints for root

- Do not edit the frozen source branch `codex/task-wait-01-reconciliation-20261107`
  at `7d38d2ac9`.
- The CI worker separately owns `753` regressions; do not run a broad heavy
  campaign here.
- Main `cf5e98191` merged `752`; normal source-base reconciliation happens only
  after source `753` repair is ready and root coordinates it. Never pull/reset
  a dirty user repo.
- No `npm install`, `npx` fetch, dependency download, browser download, live
  model/provider/account/credential/send/spend/deploy.
- No direct DB row injection, source injection, cookie/token seeding, expected
  result/plan patch or fabricated manual answer.
- Never set `ATOM_WORLD_STORAGE_BYPASS`. Never `rm -rf` or hand-create the
  acceptance-worlds root.
- One fresh unique world, one episode. Do not duplicate the old text-only d3
  campaign.

## Exact preparation

Create a separate worktree at the prepared commit; do not move the shared
capture worktree:

```bash
REPO=/private/tmp/atom-task-wait-01-reconciliation-20261107
PREPARED=929979f4a4a279668020118b613d4f2eaafe0dd2
WT=/private/tmp/atom-source-ui-$PREPARED
git -C "$REPO" worktree add --detach "$WT" "$PREPARED"

# Existing dependencies only. No install/download.
ln -s /private/tmp/atom-browser-capture-frozen-20261107/backend/venv314 \
  "$WT/backend/venv314"
ln -s /private/tmp/atom-browser-capture-frozen-20261107/frontend-nextjs/node_modules \
  "$WT/frontend-nextjs/node_modules"
```

Safe preflight (no world, browser, model or provider):

```bash
SCRATCH=$(mktemp -d /private/tmp/atom-source-ui-preflight.XXXXXX)
mkdir -p "$SCRATCH/data" "$SCRATCH/office"
cd "$WT"
TESTING=1 \
DATABASE_URL=sqlite:///$SCRATCH/atom.db \
ATOM_DATA_DIR=$SCRATCH/data \
ATOM_OFFICE_DIR=$SCRATCH/office \
backend/venv314/bin/python scripts/acceptance/browser_agent_source_answer.py \
  --preflight --out "$SCRATCH/out" \
  --expect-source-sha "$(git rev-parse HEAD)"
```

The clean checkpoint run in this packet produced `ok=true`, 3 ReActStep
envelopes, source marker `UI-SOURCE-AUTH-7F3C`, and exit 0.

Before execution, the existing storage guard must pass:

```bash
cd "$WT/backend"
backend/venv314/bin/python -m core.world_storage_guard check
```

## Root-owned single execution

Choose a unique world name (must not exist), three free loopback ports and a
scratch evidence directory. Do not reuse a prior world.

```bash
cd "$WT"
EXPECTED=$(git rev-parse HEAD)
WORLD=browser_source_${EXPECTED:0:10}_$(date +%H%M%S)
OUT=/private/tmp/atom-source-ui-evidence-$WORLD
backend/venv314/bin/python scripts/acceptance/browser_agent_source_answer.py \
  --execute \
  --world "$WORLD" \
  --backend-port <free-backend> \
  --frontend-port <free-frontend> \
  --shim-port <free-shim> \
  --out "$OUT" \
  --expect-source-sha "$EXPECTED" \
  --provision-admin-password
```

`--admin-password-file` is the alternative if root already provisioned the
scratch world password. The password is never written to evidence.

## Required assertions

The driver fails loudly on any missing check. Root should independently confirm
at least:

- source HEAD equals `--expect-source-sha`, backend tree clean at launch;
- initial and restarted backend are bound per-file to the frozen Git blobs,
  exact isolated cwd/DB/descriptor; no health-badge-only pass;
- run response admits exactly one job; one execution id is retained throughout;
- first question is `Which authorized source should be used?`, no result;
- upload is through `[data-testid="assignment-source-upload"]` on
  `/assignments`; catalog returns the uploaded `document_id`/`source_version`;
- after upload: same job/execution/wait, wait still `pending`, zero tasks,
  provider call count unchanged;
- source picker option names the uploaded file and the panel says uploading a
  file elsewhere does not answer it;
- real backend+frontend restart: new pid, same source id/cwd/DB, same
  job/execution/wait/correlation, source still in picker, no new model call;
- source-only answer (empty textarea) returns 200 success on the same execution;
- `tasks.create` has `oracle_verified=true`; exactly one BoardTask;
- durable wait snapshot has approved status, server display label,
  `accepted_answer_sha256`, information_source resource id/source version/content
  sha/reader, receipt status `verified`;
- shim capture contains `AUTHORIZED SOURCE EVIDENCE`, the source marker and the
  untrusted-evidence label; it does not contain correlation/HITL id;
- exactly one run POST, one answer POST, no `/advance`;
- final UI completed/result, public GET readback and DB rows agree;
- duplicate exact source replay creates no second task/model call;
- browser origins are loopback only and no forbidden user ports appear;
- teardown frees ports and preserves the world/evidence for review.

## Evidence to retain

The driver writes `source.json`, `stack.json`, `scenario.json`,
`source_catalog.json`, `durable.json`, `prompt_evidence.json`,
`capture/requests.jsonl`, `shim_capture.jsonl`, screenshots and `MANIFEST.json`.
Root should review the actual raw run, not the preparation report alone.

## Abort conditions

Stop and preserve evidence if the storage guard refuses, source/per-file
identity differs, a live-origin request appears, the same wait cannot be
re-read after restart, upload alone settles the question, the final result lacks
`oracle_verified`, the durable source binding is absent/changed, the new
scope/params probe still fails, or any HTTP 200 is the only success evidence.

## Ownership

Root runs and reviews the single episode after the API gate passes. This
preparation is not acceptance and does not claim full TASK-WAIT-01 or full-app
completion.
