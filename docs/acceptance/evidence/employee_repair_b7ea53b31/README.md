# Employee repair successor — fact identity and authority staleness

Status: **submitted for independent verification; deterministic only. Served
adaptive choice (G5 level 2) and Batch A acceptance remain unclaimed.**

This successor contains two small post-`b7ea53b31` changes over the combined
evidence-strength/patch-invariant repair:

1. an established patch fact must bind a source reference with a stable
   identity (resource/source id, URI or hash) or an explicit authored
   authority — a nonempty free-form note is insufficient; and
2. an `authorize_execute` transition that advances `task_version` without
   changing `plan_revision` refuses the old patch, matching fact/teaching
   changes.

The full `b7ea53b31` bundle remains the primary evidence for the five repaired
contracts; this bundle binds the successor source and re-runs the affected
matrices.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree | `/private/tmp/atom-full-app` |
| Executed source | `b7ea53b31` (full SHA in `MANIFEST.json`) |
| Parent evidence | `employee_repair_1909cd23b` |
| Transport | controlled local service/DB; no live provider |

## The verifier patch probe and the version field

The original independent probe's helper builds `base_task_version` from
`task_revision.revision` — the objective revision. That is precisely the
contract being repaired: the authoritative lifecycle CAS field is
`record.task_version`. On this source the original probe's first apply is
therefore refused as stale, so its changed-content setup cannot run; its other
two assertions still pass.

`corrected-patch-invariant-probe.py` is the same probe with only that helper
changed to `record.task_version`. It passes **3/3**:

- upstream invalidation refuses a transitive uncertain descendant and keeps
  its status/operation id;
- a fact/teaching/authority state advance without a plan revision refuses the
  old patch;
- the same patch id with different material content conflicts.

No product fallback accepts the obsolete field; producers and repository
tests use `task_version`.

## Results

| Scope | Result |
|---|---|
| Integrated backend selection | **552 passed** |
| Frontend assignment/goal/approvals | **54 passed** |
| Evidence/G0/blocked-route probes | **9 passed** |
| Focused affected suites | **204 passed** |
| Patch invariants | **8 passed** |
| Two-domain deterministic campaign | **4 passed** |
| Corrected patch probe | **3 passed** |
| Original patch probe | **2 passed, 1 setup-stale** (documented) |

The eight repository patch invariants add authority staleness, stable fact
identity, forced-CAS callback purity, concurrent duplicate adoption, restart
replay, requirement weakening, mutation relabelling and transitive uncertain
descendants.

## Boundaries

- Deterministic mechanisms only; no served-model adaptive choice or raw model
  traces.
- Four `test_task_lifecycle.py` controls fail identically to the parent and
  are disclosed, not counted.
- No live provider action/send/credential/consent/spend; planner 5/5, goal
  router 1/2, alignment gap 3.0 and historical `111/123` unchanged.
