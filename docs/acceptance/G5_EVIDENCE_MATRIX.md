# Employee G5 — evidence reconciliation and held-out boundary

Date 2026-11-04. This is the one reconciliation of the remaining G5 rows
against the existing evidence. Product source for the completion contracts is
`2eb433f41`; the accepted employee episode remains frozen at `70a74cd02b5`.

Legend: **Demonstrated** = served product evidence at the named source;
**Regression-supported** = independent focused controls on the successor;
**Missing** = no qualifying evidence yet. A row is not upgraded by a different
row's evidence.

| G5 row | Status | Evidence / limit |
|---|---|---|
| Employee decides supported work from an ordinary objective | Demonstrated | Quote + procurement decisions in `70a74cd02b5` (run `279a603f…`); quote decision in `c7a265c37`; typed work request tests |
| Requested usable artifact from durable typed results, no supplied rows | Demonstrated | `employee_g5_ui_requested_artifact_c7a265c37` (22/22, 370.00); `70a74cd02b5` combined report (370.00 + 270.00) |
| Artifact verification gates completion; no partial publication | Demonstrated | `c7a265c37`; report-withholding controls in `2eb433f41` |
| Model-created durable wait + independent work + restart + same-job answer | Demonstrated | `employee_g5_durable_wait_70a74cd02b5` (16/16; 24/24 Git) |
| Real source/price version change with model reassessment and selective retention | Demonstrated | `employee_g5_integrated_change_62fa207647` (18/18) |
| Negative qualification twin (missing/false qualification stays blocked) | Demonstrated | `employee_g5_final_regressions_b4c29e2b6` |
| Cancellation and late-response refusal | Demonstrated; regression-supported | `employee_g5_regression_b4c29e2b6d9e` (18/18); `2eb433f41` focused suite |
| Controlled provider lost-confirmation/restart/reconcile/no resend | Demonstrated; regression-supported | regression bundle (11/11); `employee_g5_final_regressions_b4c29e2b6` |
| Exact namespaced identity and empty-scope result invariant | Demonstrated on successor | `employee_identity_repair_2eb433f41` (410 tests; 16/16 Git) |
| Held-out content with new identifiers/values and independent arithmetic | **Same-job recovery only; fresh unseen qualification missing** | `employee_g5_heldout_timeout_6bc97759284` remains the preserved negative (PO-7302/INV-4491; wait, quote 96.30, restart and answer passed; adaptation timed out; no 140.25, no artifact). `employee_g5_heldout_recovery_8995f433d` recovers the same frozen job after the compact schema-echo repair: quote 96.30 retained, reconciliation 140.25, artifact verified, 19/19 checks. The pre-dispatch wall-budget refusal was resolved by the supported owner extension/retry; values are now known. `employee_g5_heldout_continuation_60d464a5f` is a separate known-value HX recovery. Fresh unseen values still required |
| Held-out event order (e.g. independent work after restart, reply order) | **Partial — original order completed; alternate order missing** | The original order (wait -> quote -> restart -> reply -> reconciliation -> artifact) now completes on the frozen job in `employee_g5_heldout_recovery_8995f433d`; no served alternate order (restart while waiting, source authorized after restart). The ordering policy is covered by compiler/validation tests only |
| Held-out two-domain evidence selection without user-picked sources | **Missing (model-quality boundary)** | Prior probe `80e3bd702` / `20f3ffc19`: quote pass, procurement selection negative; invoice source omitted. Not repaired by the wait/identity work |
| Broad adaptive judgment / general model competence | **Not qualified** | Local 8B decisions are bounded to the recorded contexts; no general claim |
| Live cloud/provider breadth, Zoho/Microsoft, Linux/KVM, multi-worker/soak | **Out of scope / separate** | No credentials/platform/authority in this batch |

## Held-out batch outcome

The finite batch
`docs/acceptance/evidence/employee_g5_heldout_timeout_6bc97759284/` used new
identifiers, quantities and prices (quote 96.30, reconciliation 140.25). The
model selected the receiving wait and the independent quote, the wait survived
a real restart, and the same-job answer was accepted. The dependent
reconciliation was not produced: the local model's adaptation hit the bounded
deadline (initial and compact retries), so the job stayed blocked with the
required result unresolved and no artifact. This is evidence of the held-out
model/timeout boundary, not a completed held-out qualification.

Two same-job recoveries now exist at later sources:
`employee_g5_heldout_continuation_60d464a5f`
(HX-1/HX-2/PO-HX-7001; 125.00/101.00) and
`employee_g5_heldout_recovery_8995f433d` (the original PO-7302/INV-4491 job;
96.30/140.25). Both are known-value recoveries, not fresh held-out
qualifications. The original negative remains valid.

## What this reconciliation does not claim

- It does not merge the wait episode, source-change episode and controlled
  uncertainty/cancellation evidence into one served browser episode.
- It does not treat deterministic mechanism tests as served-model choices.
- It does not upgrade the negative procurement evidence-selection probe.
- It preserves the successful episode at its original identity and does not
  reattribute it to the successor repair.
