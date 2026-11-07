# GOAL-02 ordinary-UI episode — prepared harness

**Status:** prepared only. Root owns review, the single browser episode,
ordinary UI acceptance, PR/CI and merge. No world, browser, backend, frontend,
app model or provider was launched in this slice.

**Branch:** `codex/goal-utility-ui-prep-20261107`

**Prep head:** `98bb2e181da25d48fdbebdcd1c0d3bfb6d419735`

**Frozen GOAL PR head:** `dc92728d6e1302e8718c9435c08c119972e6fca8`

**Runtime identity:** `git diff dc92728d6..98bb2e181 -- backend frontend-nextjs`
is empty. The prep branch adds only the driver/work order and this evidence
packet. Root must still pass the actual frozen source SHA to
`--execute --expect-source-sha`.

## Artifacts

- `scripts/acceptance/browser_goal_utility_ui.py` — prepared driver.
- `docs/acceptance/GOAL_UTILITY_UI_EPISODE_WORK_ORDER_20261107.md` — root-owned
  work order and exact episode assertions.
- `preflight.json` — passing read-only report (per-file Git source proof,
  fixture ranking, core profile, fresh world name, ports, storage guard).
- `preflight.log` / `preflight.exit.txt` — actual run and exit 0.
- `preflight-negative.log` / `preflight-negative.exit.txt` — wrong
  `--expect-source-sha` refused with exit 2.
- `pycompile.log` / `pycompile.exit.txt` — driver compile exit 0.
- `typescript.log` / `typescript.exit.txt` — `tsc --noEmit` exit 0 using the
  reused existing `node_modules`; no install.
- `source.json` — driver/work-order blobs and the empty runtime diff versus the
  frozen head.
- `verification.json` — checks and boundaries.
- `MANIFEST.json` — SHA-256 and byte counts for this packet plus source blobs.

## Preflight result

`preflight.ok = true`.

- frozen source SHA matched the passed `--expect-source-sha`;
- tracked tree clean;
- per-file Git source proof matched for 10 runtime/UI files, including
  `backend/api/goal_routes.py`, `GoalService`, `GoalRunService`,
  `goal_write_service`, `utility_target`, personal scope, product profile,
  `frontend-nextjs/lib/goal-run-api.ts` and
  `frontend-nextjs/pages/goal-runs/[id].tsx`;
- controlled analytics fixture ranked exactly two eligible rows, winner
  `eligible-low`, withheld `not_completed` and `metric_unknown`;
- core profile: Activity/Goal Runs enabled, Tasks/Boards not forced;
- fresh `goal_utility_ui_98bb2e181d` world absent;
- backend 8041 / frontend 3241 free;
- storage guard config loaded.

The only warning is expected: this **prep-only** worktree has no
`backend/venv314`. Root must run `--execute` from the prepared frozen capture
worktree with its venv and `frontend-nextjs/node_modules`; no install is
permitted.

## What is deliberately not done

- No `--execute`, world build, server/frontend launch, browser login, seeded
  GoalRun row, target set/clear, operation receipt, API/DB episode readback or
  model/provider call.
- No production/API/UI/runtime/test change and no change to the goal PR branch.
- No backup/export/ORCH implementation.
- No TASK-WAIT-01/source upload/download/Generic model call.
- No PostgreSQL, multi-worker, soak, live account/credential/send/spend or
  deployment claim.

The fixture history is explicitly a controlled analytics fixture, not completed
agent work or model output. The episode's target is created only through the
existing public supervisor UI/API; the fixture does not write a target or
winner. Member mutation refusal is checked through the public API after normal
form login.

## Relationship to the Generic source-answer packet

The eventual run may use the same frozen integrated source and the same
existing world-build/startup infrastructure after the source-answer episode is
accepted, to avoid duplicate build/startup work. Packets remain separate: this
driver requires its own fresh `goal_utility_ui_` marked world and does not reuse
or certify the source-answer world/job/source/model evidence.
