# Activity goal-utility visibility (GOAL-02, component scope)

- Source before: `310e72aec`
- Repair commit: `05ca1e72bb87848d07c702cc4c99201217c92b7b`
- Scope: ordinary Activity list consumer surface only.
- No backend, API, router, store or engine change.

## Baseline

A failure-first component control on the existing Activity list with a goal
that already has `utility_target` failed: `activity-utility-summary` was
absent and `getGoalUtility` was never called (`1 failed, 14 passed`).
The Activity list discarded `Goal.utility_target` returned by `/api/goals`
and only loaded detail ranking after opening a run.

## Change

The Activity list now reuses the existing `getGoalUtility` API and detail-card
semantics for each goal with a target:

- target metric and direction
- eligible count and winner
- ranked completed runs with metric values
- explicit withheld reason for ineligible runs

Existing 15s polling, include-terminal reload/filter, member read-only and
detail supervisor write controls are preserved. A utility read failure shows
a typed error, keeps the legitimate last known ranking marked stale, and does
not present the old winner as fresh. A first-read failure never fabricates a
winner.

## Controls

- Failure-first baseline: red (`logs/baseline-red.log`)
- Activity index + detail: **45 passed**, exit 0 (`logs/index-detail-controls.log`)
- `tsc --noEmit`: exit 0
- ESLint changed files: exit 0
- Twins: target/two-result/withheld, no-target/no-call, first failure, stale
  after later failure, member read-only, poll refresh, reload, detail controls

## Limits

This closes only the Activity consumer visibility boundary. It does not
declare GOAL-02 or the whole goal closed, does not change backend ranking,
and makes no model/general-judgment, browser, live DB/provider, whole-app or
PostgreSQL claim. Root owns CI/PR/final verification.
