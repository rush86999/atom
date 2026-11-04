# Test results — final employee G5 regressions

Source: `b4c29e2b6d9e0d788f6a95e8a1b6c836bd0c3aa9`.

## Focused suite

Command: the 20-file/370-test matrix used by the integrated campaign,
including assignment routes/executor, employee proposal/adaptation/work
requests, both evidence-sensitive change tests, campaign guard, proof
binding, document freshness and prior verifier probes.

Result: **370 passed, 761 warnings in 74.24s**. Log: `focused-tests.log`.

## Evidence-sensitive controls

`evidence-tests.log`: **2 passed**.

- `test_new_source_version_triggers_model_chosen_reassessment` — a new active
  catalog version changes a real unit price; the completed job accepts the
  version and the adaptation contract chooses fresh quote work. The prior
  quote operation/receipt and unrelated read are retained; the artifact
  re-renders at the new total.
- `test_real_source_value_change_reopens_only_the_dependent_artifact` — in-
  place SC-1 price 10 → 40 changes the evidence-derived quote 105.00 → 165.00
  and artifact revision. The unrelated note operation
  `3147412f-ea56-41c3-9536-6f2b02695785` and its result stay identical.
  Structured lineage: `source-change-report.json`.

`negative-twin.log`: **2 passed** — unknown qualification blocks the
dependent read, and missing qualification waits for an explicit resolution
rather than substituting a default.

## Controlled provider recovery

`uncertainty-report.json`: **11/11 checks passed**.

- Run: `c9689e03-b2f2-4b65-9f0c-0cecdaacccd3`
- Original operation: `d0567341-ce66-4f15-a4a4-25a8113ddb26`
- Outbox sha256 unchanged:
  `2825947be9a780d63a071e6ddc8282dedd44a2aac37c20f7d4cd454921e8ade1`
- Provider accepted, confirmation lost, assignment blocked, real restart,
  same operation uncertain, reconcile applied, assignment completed, one
  effect and no resend.

## Integrated companion

The normal-product artifact/version campaign is recorded separately at
`docs/acceptance/evidence/employee_g5_integrated_change_62fa207647/`:
**18/18 checks**, run `f6465719-3cf6-4087-913c-4d0c1b2a1a93`, phase 1
artifact 370.00 (`4486b127...`) and phase 2 artifact 425.00
(`5d26049c...`).
