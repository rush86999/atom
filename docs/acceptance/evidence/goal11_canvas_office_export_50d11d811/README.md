# GOAL-11 generated Canvas document/presentation Office export — successor

Packet: `docs/acceptance/evidence/goal11_canvas_office_export_50d11d811/`

This bundle is bound to the actual executed repair source
`50d11d81154251a7de3dc794bce03177b22a1781` and its predecessor fix
`7afcf65deabe4dbfde51de93e68b7ea01fedc23f`. It does **not** replace or
re-attest the frozen `b9b3ebbb6` packet.

## Predecessor attribution

The original packet `docs/acceptance/evidence/goal11_canvas_office_export_b9b3ebbb6/`
has been restored byte-for-byte to its frozen state at
`08b5fdfd6d2e4c7fb5782071c64cbf475399bbd8`. That b9 acceptance remains
**WITHHELD**: root's independent six-control integrity probe failed 5/6 on it
(reordered DOCX, H2 demotion, shadowed requirements, `[None]` requirements,
and actor revocation during render). Its original failure facts are preserved
in this successor under `gates/root_independent_original_fail5.summary`. The
raw log containing dumped DOCX response bytes is retained privately only and
is deliberately not committed or reproduced.

## Repair source

- Base: `750f42215229fde8d516c700c6a8de0fd3a5a111`
- Inspected failed runtime: `b9b3ebbb631bf2ced3b71303e765d29cc735c918`
- Integrity repair: `7afcf65deabe4dbfde51de93e68b7ea01fedc23f`
- Authoritative job/artifact binding repair (actual source):
  `50d11d81154251a7de3dc794bce03177b22a1781`

Only `backend/api/canvas_routes.py`, `backend/core/assignment_executor.py`
(additive `content_sha256` on artifact results), and the export tests changed.
`office_service`, `employee_business_outcomes`, and `canvas_authority` bytes
are unchanged from the inspected runtime.

## Independent root evidence (distinct sources)

| Source run | Result | Time | Exit / source |
|---|---|---|---|
| Original 6 integrity on b9 (`0he0pq97`) | 5 failed, 1 passed | 7.38s | exit 1, same_source true |
| Original 6 integrity on repair (`yv2q_p3c`) | 6 passed | 6.62s | exit 0, same_source true |
| Job-binding on 7af (`u5dmjpd8`) | 1 failed (fake flags certified) | 4.32s | exit 1, same_source true |
| Job-binding on repair (`ebh0hplc`) | 1 passed | 3.78s | exit 0, same_source true |
| Real artifact controls on repair (`40ybdhwv`) | 3 passed | 5.80s | exit 0, same_source true |

That is 10 independent cases across three root runs, using real JWT and the
actual development-audience guard. The real-artifact run used the frozen
creation helper `/private/tmp/root-office-real-job-fixture-20261110.py`
(SHA-256 `a8fe4753c081be904e3866c881642212772dfbb286063a80d136fb35d38d107f`,
byte-identical to this branch's export test module at the captured source).

Attribution note: the root runner's four-file hash set covers
`canvas_routes`, `office_service`, `employee_business_outcomes` and
`canvas_authority`. The additionally changed `assignment_executor.py` and the
creation-helper bytes are recorded explicitly in `manifest.json` so root can
compare them independently before stronger frozen attribution.

## Defect fixed after the integrity repair

The integrity repair still trusted a CanvasAudit-carried `assignment` with a
truthy `run_id` and embedded applied/verified steps. A fake
`run_id=job-that-does-not-exist` therefore certified
`required_results_verified` with no persisted job. Fix:

- Resolve the canonical job only from the server-owned `Canvas.goal_run_id`
  or a run whose exact `provenance.canvas_id` is this canvas, through the
  existing workspace-scoped `GoalRunService` / `TaskLifecycle`. Audit
  `run_id`, `assignment`, `steps` and requirement booleans are claims only.
  No first-available-job fallback; no caller-controlled path from a raw
  `run_id`.
- A claim with no canonical job, a dangling/foreign binding, or a
  failed/cancelled job refuses 409.
- Re-derive step results from the run's applied operation records. A step
  flagged applied without a matching applied operation is downgraded to
  unverified; copied audit steps never enter the receipt path.
- A verified business result alone does not certify an arbitrary document.
  With requirements present, the visible saved body must have an exact
  output/body binding: a matching applied `artifact.document` /
  `artifact.presentation` result (`content_sha256`) or a producer-recorded
  body digest. No binding refuses 409; a mismatch (manual edit) refuses 409.
- Recorded revision/manifest/source/audit/body bindings are compared to the
  current canvas; stale or old source/version refuses. Reusing another job's
  real receipt for this canvas cannot satisfy the binding.
- Reuse the existing artifact composition path; the executor now persists the
  rendered body digest in the durable artifact result. No new store, router
  or verification engine.

The genuine positive executes the real `AssignmentExecutor`
`quote.calculate` adapter plus an `artifact.document` step; exact-body export
returns 200 `required_results_verified`. Negatives cover copied flags with a
missing job, same-owner unrelated job, foreign-workspace job, stale source
revision, calculation-only job with an arbitrary contradictory total and no
exact output binding, and manual edit after a verified artifact. Unscoped
drafts still export with `not_claimed`; bound jobs with no requirements do not
claim verified business results.

## Gates

| Gate | Result | Log |
|---|---|---|
| Backend public-route/package controls | 26 passed | `gates/backend_export_26.proof` |
| Assignment executor suite | 107 passed | `gates/assignment_executor_107.proof` |
| CanvasPanel controls | 47 passed | `gates/canvas_panel_47.proof` |
| Existing office-file/co-editing selection | 32 passed, 1 pre-existing failure | `gates/office_file_compat_32pass_1pre_existing.proof` |
| Root integrity six on repair | 6 passed | `gates/root_integrity_six_pass.proof` |
| Root job binding on repair | 1 passed | `gates/root_job_binding_pass.proof` |
| Root real artifact controls on repair | 3 passed | `gates/root_real_artifact_pass.proof` |
| Baseline export route absence | 404 / no route | `baseline/base_export_route_absent.proof` |

The one office compatibility failure is the pre-existing
`TestPresentPersistence::test_explicit_canvas_id_respected`
(`/present` lacks `canvas_id`), unrelated to this route and preserved. The
broader canvas API submit 403s are pre-existing test-auth/audience failures,
confirmed at baseline in `compat/`.

## Evidence hygiene

- Frozen predecessor packet restored to `08b5fdfd6`; do not overwrite its
  11/47/32 logs with successor runs.
- Original five-negative root facts: `gates/root_independent_original_fail5.summary`
  and sanitized review; raw binary-bearing `controls.log` remains private.
- Job-binding failure at 7af: safe controls/review in `negative/`.
- No raw DB, tokens, env dumps, binary response body or emails are committed.

## Non-claims

- Ten independent root cases across three bounded runs are not full browser or
  whole-GOAL-11 acceptance.
- No CI/PR/merge; PR number is not guessed. Root owns independent review.
- PR 824 excludes this unreviewed Office feature.
