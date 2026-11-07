# TASK-WAIT-01 source-answer + GOAL-02 utility UI — integrated preparation

**STATUS: PREPARED — NOT EXECUTED. Root owns review, the two ordinary UI
episodes, PR/CI and normal merge. This packet is not browser or Goal
qualification.**

## Frozen source

- Branch: `codex/task-wait-source-ui-integration-20261107`
- Worktree: `/private/tmp/atom-goal-utility-surface-20261107`
- Prepared source: `3786e7098fa04dc26d8ba78c3847b5327ec215bd`
- Canonical per-file source SHA-256: `6ea0a052d331f64e4131987e97d6517424cc9d1568addebf8abb410dc1a27a08`
- Full per-file Git blob/SHA-256 identities: `source_identity.json`

The old `codex/goal-utility-ui-prep-20261107` branch is preserved at
`353c639d2`; the new branch was created from it and the four requested
sources were joined in this order:

| Source | SHA | Role |
|---|---|---|
| current main | `8ded00232c30961a990e675e06ec672ef6a43910` | Goal utility feature (already content-identical in the 353c base) |
| reviewed Generic | `2ef5c120cb33c71a27016326929f2aa004a7d271` | full wait/material CAS, current proxy reviewer, Personal NULL/default, extraction, permanent probes |
| source/executor 753 | `bd209add6716d056422752b411da7dc103790810` | post-209 authorized-source fixture successor, assignment/executor runtime and independent executor evidence |
| prepared source UI | `b493abb30143894a982d6285ad4f3a93ccca4cb0` | ordinary-UI source-answer driver, shim fixture, preflight test, wait panel and work order |

## Exact union

The four merges completed as ordinary 3-way merges. No force push, no blanket
`ours`/`theirs`, no conflict marker and no deleted evidence path was used
(147 `docs` files added versus main, zero deleted).

- **Goal / main:** `353c` already carries the same Goal utility content as main
  `8ded` plus its Personal NULL/default harness fix. The explicit main merge
  therefore records the parent without re-writing goal product files.
- **Reviewed Generic:** `backend/api/agent_routes.py`,
  `backend/core/information_wait.py`, `backend/core/generic_agent.py`, the
  Generic process worker and the source-answer/scope/reviewer probes are
  **byte-identical to `2ef5c120c`**. See the anchor check in
  `union-analysis.json`. This retains the reviewed full-record CAS, the current
  proxy reviewer authority, Personal NULL/default claims and the extraction
  checks.
- **Source/executor:** the 183-line post-209
  `backend/tests/source_authority_fixtures.py`, assignment executor runtime and
  the independent executor evidence join the tree. This branch does not touch
  the reviewed Generic runtime.
- **Prepared UI:** the ordinary-UI source-answer driver, controlled loopback
  shim fixture, preflight test, `AgentJobWaitPanel` and the AI WAIT-SOURCE-UI
  work order join the tree. Its older runtime hunks are already ancestors of
  `2ef5`, so the reviewed runtime bytes win without a conflict.
- **Evidence:** every packet from `353c`, `2ef5`, `bd209` and `b493` is
  retained. `union-analysis.json` lists the 16 evidence directories and the
  147 added docs files.

No export or radio branch was merged in this episode. PR756/757 and the Goal CI
synchronization worker remain separate and untouched.

## Preflight made real

Both prepared drivers now prove, with existing mechanisms only:

- HEAD equals `--expect-source-sha` and the tracked worktree is clean;
- every declared runtime/harness/UI file matches its committed Git blob
  (9 files for source-answer, 13 for Goal), not a health badge;
- the canonical worlds root resolves and
  `core.world_storage_guard.preflight()` is usable;
- the ACC output parent is writable and the 55-entry
  `fixtures/SHA256SUMS` verifies (`shasum -a 256 -c`);
- the reused D3/`run_isolated`/`provider_shim` launcher paths and the prepared
  `backend/venv314` + `frontend-nextjs/node_modules` are present;
- the report parent is writable and outside the worlds root;
- the fresh world path is under the configured root and is not created.

Preflight does not mkdir a world, launch a server/frontend/browser, create a
GoalRun, set a target or call a model/provider. The fresh-world refusal,
outside-worlds report and wrong-SHA negatives all exited 2 and created nothing.

| Run | Result | Artifact |
|---|---|---|
| source-answer preflight | `ok=true`, 9/9 source files, 55/55 fixtures, 3 ReActStep envelopes | `preflight-source.json`, `preflight-source.log` |
| Goal utility preflight | `ok=true`, 13/13 source files, 55/55 fixtures, winner `eligible-low`, 2 eligible | `preflight-goal.json`, `preflight-goal.log` |
| source preflight tests | 5 passed | `source-preflight-tests.log` |
| Goal utility/scope tests | 41 passed | `goal-component-tests.log` |
| five fail-closed negatives | exit 2 each, no world/output created | `negative-*.log` |

All pytest runs used `/private/tmp/atom-agent-cli/run_bounded_test_gate.py`
(`--profile bounded`), the existing `venv314`, a unique `TESTING=1`
DB/data/office/Lance/basetemp world and a synthetic `SECRET_KEY`. The largest
run was 41 tests; no broad campaign and no repeated stable backend-96 were run.

## What root still owns

Root runs **one** source-answer UI episode and **one** Goal utility UI episode,
each in its own fresh world, against the frozen source SHA it checks out. The
two packets stay separate: the Goal episode must not reuse or certify the
source-answer world/job/source/model evidence. See `WORK_ORDER.md`.

## Non-claims

No world, browser, backend, frontend, app model or provider was launched in
this preparation. No live DB, account, credential, send, spend, install,
download, deploy, export or radio merge occurred. This packet does not claim
browser qualification, Goal completion, served-model quality or full
TASK-WAIT-01/whole-app acceptance.
