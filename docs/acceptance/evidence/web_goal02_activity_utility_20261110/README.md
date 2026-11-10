# Activity goal-utility visibility (GOAL-02, component scope)

- Source before: `310e72aec`
- Predecessor: `05ca1e72b`
- Successor repair: `a6e40729705d88f4f1ab41d760e235b60358d3ba`
- Scope: ordinary Activity list consumer surface only.
- No backend, API, router, store or engine change.

## Baseline and root negative

A failure-first component control on the existing Activity list with a goal
that already has `utility_target` failed: `activity-utility-summary` was
absent and `getGoalUtility` was never called (`1 failed, 14 passed`).

The root's independent consistency probe on `05ca1e72b` then failed 2/2:
an authoritative fresh `target=null` left the previous best winner visible,
and an older slow Activity load could resolve after a newer targetless load
and revive stale utility state. That exact negative review/controls is
preserved under `root-independent/`.

## Change

The Activity list reuses `Goal.utility_target`, `getGoalUtility` and the
existing detail-card semantics for each targeted goal, showing metric,
direction, eligible count, winner, ranked completed runs and withheld
reasons.

The successor also:

- assigns one request generation at load entry, before every await, and gates
  all run/goal/utility/loading/error writes on it;
- clears ranking/target/winner on an authoritative fresh `target=null`;
- preserves a failed utility read as explicitly stale, never a fresh winner;
- treats a `listGoals` failure as a distinct metadata error, preserving known
  titles/targets, while genuine empty goals still clear normally;
- preserves the existing poll, include-terminal filter, member read-only and
  detail write controls.

## Controls

- Failure-first baseline: red (`logs/baseline-red.log`)
- Predecessor controls: **45 passed** (`logs/predecessor-45-controls.log`)
- Successor index + detail: **48 passed**, exit 0
  (`logs/successor-48-controls.log`)
- Index consistency: **23 passed** (`logs/index-consistency-controls.log`)
- Unchanged root probe after repair: **2 passed** (`logs/root-probe-after.log`)
- `tsc --noEmit`: exit 0
- ESLint changed files: exit 0
- Twins: cleared target, older-load revival, metadata failure, first/read
  failure, no-target, two-result/withheld, member, poll, reload, detail

## Limits

This closes only the Activity consumer visibility boundary. It does not
declare GOAL-02 or the whole goal closed, does not change backend ranking,
and makes no model/general-judgment, browser, live DB/provider, whole-app or
PostgreSQL claim. Root owns CI/PR/final verification.
