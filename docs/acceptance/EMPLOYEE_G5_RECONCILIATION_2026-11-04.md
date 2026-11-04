# Employee G5 reconciliation — 2026-11-04

Product contract source: `2eb433f41fdcaeca1a51dd774bfe6bea5b9791be`.
This is a one-time reconciliation of the frozen G5 rows against existing
evidence. It is not a new acceptance claim and does not relabel any historical
episode as execution on a different source.

## Row status

| G5 row | Status | Evidence and exact scope |
|---|---|---|
| G0 material-state / projection driver | Accepted / regression-supported | Prior accepted G0 controls; focused successor regression at `2eb433f41`. |
| G1 canonical employee job view, identity and criteria | Accepted / regression-supported | Fresh-session requirement/identity controls at `2eb`; original UI episode at `70a`. |
| G2 readiness, useful independent work and typed blockers | Demonstrated | `70a` episode: quote completed while receiving wait stayed open; unresolved invoice result remained visible. |
| G3 typed proposal, compiler adoption and CAS | Demonstrated | `70a` model-selected wait/quote/reconciliation; `2eb` text/CAS/requirement regression controls. |
| G4 event-driven continuation, recovery and objective verdict | Demonstrated at separate scopes | `70a` restart/answer/completion; `b4c29e2b6` cancellation, late reply and controlled uncertainty regressions. |
| G5 known-data durable-wait product episode | Demonstrated at original source | `70a74cd02b5` / `4fd8951cc`; 16/16 episode, 24/24 Git, quote 370.00, reconciliation 270.00, combined artifact `8d0d4877…`. |
| G5 employee-decided requested artifact from quote | Demonstrated at original source | `c7a265c37` and `62fa207647`; model-selected quote, verified receipt, artifact rendering and real revised-price reassessment. |
| G5 real changed-source selective reassessment | Demonstrated at original source | `62fa207647` / `b4c29e2b6`; 370.00 → 425.00, prior and unrelated operation ids retained. |
| G5 cancellation, late response, uncertain effect | Demonstrated at separate regression scope | `b4c29e2b6d9e`; not part of the single served browser episode. |
| G5 held-out content / identifiers | **Demonstrated and accepted at controlled local scope** | Fresh unseen `QH-21`/`QH-22`/`PO-QH-8100`/`INV-QH-99` batch at `3ccad7a5a`: two runs, quote 145.00, reconciliation 113.00, published review documents, **22/22** named finish checks (11/11 per run; the earlier 10/10 summary omitted `same_wait`). The runtime successor `5abbeaa48` and packaging/source-attribution corrections are accepted at their tested scopes. Evidence: `employee_g5_heldout_two_order_fresh_3ccad7a5a`. Earlier same-job recoveries (`367efddf…` at `8995f433d`, `d40c94ee…` at `b16172c8d`) remain separate known-value recovery evidence. |
| G5 held-out event ordering | **Demonstrated and accepted at controlled local scope** | Both required orders on the fresh batch: (1) source authorized before restart; (2) restart while waiting, source authorized after restart. Both preserved the same run/wait/quote identity, replied on the same wait and produced the dependent reconciliation + artifact. The earlier frozen-job recoveries remain order-1-only. Accepted at this scope; earlier frozen-job recoveries remain order-1-only. |
| G5 independent procurement evidence selection | **Demonstrated and accepted at controlled local scope** | `employee_g5_procurement_selection_7d4358ea6`: from a seven-document authorized pool, the served model selected the current invoice `ap-inbox-0412.json`, matching PO `po-archive-88.json` and current receiving `dock-receipt-19.json` after a bounded model correction; reconciliation **121.00 USD**, 12/12 positive checks. The missing-source twin asked for `INV-SEL-77`/`PO-SEL-520`, stayed unfinished with no reconciliation or artifact, then recovered on the same job after the authorized invoice addition to **121.00 USD** (14/14 checks). 26/26 total; 323 affected tests; 33/33 Git. The user authorized the pool but did not name the answer subset or role mapping. One pinned local route; automatic multi-model BYOK selection remains separate. Earlier negative probes `80e3bd702` / `20f3ffc19` remain historical at their sources. |
| G5 automatic BYOK selection | **Available one-route scope accepted; controlled two-route matrix accepted; served multi-model quality not qualified** | `employee_byok_auto_selection_0e04286b2`: 5/5 unpinned employee evidence-selection calls auto-selected and served `ollama/llama3.1:8b` (28,034 prompt / 1,058 completion tokens; 98.78 s; raw route/usage journal). Controlled real LLMService/BYOKHandler two-route matrix: economy picks the cheaper capable route; measured semantic failure excludes it and serves one eligible alternative; a failed costlier route cannot displace the cheaper one; both failed -> deterministic/no-suitable with receipts retained; scope and deadline refusal; dedicated wait-choice and compact profiles. **9 consumer tests + 114 successor tests; 14/14 Git**. Only one route was configured/authorized, so served multi-model comparison is not claimed. |
| G5 evaluated business outcome → scoped routing feedback | **Demonstrated at controlled scratch-DB scope** | `employee_business_feedback_2ab959fc0`: the employee consumer annotates the exact served generation with `failure_kind`, profile/version, workspace/tenant and provider/model. Three evaluated `wrong_evidence_selection` outcomes persisted as **3 samples / 0 successes / 3 semantic failures**; the next unpinned decision excluded `local_ctrl1234/llama3.1:8b` and served the one eligible alternative `local_pricey/pricey-model`. Also covers post-execution `objective_met=False` capability failure, satisfied-outcome annotation, workspace/tenant/profile-version isolation, compact-profile scoping and deterministic-fallback refusal. **7 feedback controls (included in 213 affected) + 180 broader tests**. Scratch DB and doubled transport; no live model or served multi-model claim. |
| G5 breadth of adaptive judgment / general model competence | **Not qualified** | A finite campaign cannot establish general employee judgment. History and prior model verdicts are unchanged. |
| Full G5 / whole-app ORACLE / live-provider breadth | **Not claimed** | Requires separate qualifications and authorities. |

## What the supported episode does establish

One ordinary employee objective, from the normal UI, demonstrated:

**model-chosen durable wait → useful independent quote → process restart →
same-job authorized answer → model-selected dependent reconciliation →
requested internal review document containing both verified results.**

The episode's selected route and served model are recorded. Step ids,
correlations, dependencies, receipt verification, artifact composition and
completion remain compiler/executor-owned. The report is an internal review
document, not a customer-facing quotation template or accounting submission.

## Why the known-data episode did not establish the held-out row

The earlier successful episode used known acceptance-style values and a single
order: wait, quote, restart, source add, reply, reconciliation, artifact. The
G5 acceptance campaign requires unseen values/identifiers and at least two
meaningful event orderings. Those rows were not established by the known-data
episode or by the separate cancellation/uncertainty regressions; the fresh
`QH` two-order batch above is the controlled local result for them.

## 2026-11-04 same-job continuation result

The frozen failed job `d40c94ee-2128-4f56-8165-1d2b8fcbd01a` was continued
without re-uploading sources or restarting the task. The durable wait
`await-e94400ac76450659e0de` and quote operation `9ea5f0de…` stayed intact.
Three compact model calls were diagnosed in order:

1. 20.5 s, malformed schema-shaped output (`$ref` evidence, numeric field-map
   value) → the compact invoice request now exposes only the model-owned
   operation, role step IDs and currency; field maps stay compiler-owned.
2. 11.2 s, valid typed reconciliation, adoption refused because the model
   omitted opaque observation IDs → the compact call now binds exactly the
   observations it was built from.
3. 4.28 s, valid typed reconciliation, adoption applied, then the executor
   refused the dependent step at the assignment wall/step budget → an
   increase-only owner budget route preserved the job and retried the step.

The same job then completed: reconciliation **101.00 USD**, quote **125.00 USD**,
every business requirement satisfied, requested document applied with sha256
`0271e107…`, and 9/9 recovery checks. The served route was
`ollama/llama3.1:8b` under the separately declared
`employee_adaptive_planning_compact` capability profile; the all-purpose
`employee_adaptive_planning` profile remains measured-failure-disqualified in
this world. This recovery alone is not a fresh held-out content or event-order
qualification; the separate QH batch below is the controlled local fresh
result.

## 2026-11-04 original PO-7302 / INV-4491 recovery (8995f433d)

The original held-out timeout job `367efddf-c4b3-4e02-9ab2-23c737fd162e`
was also continued on the same frozen state. At `3b3f9ef92` the compact call
returned instructor's injected JSON schema (7 validation errors, no proposal).
The prompt repair `e95d06bc9` / `8995f433d` names the instance shape and
forbids schema echo; one bounded call then returned a valid typed replan in
57.67 s on the pinned `ollama/llama3.1:8b`
`employee_adaptive_planning_compact` route. The compiler adopted
reconciliation, the executor refused the step pre-dispatch because the 900 s
wall budget had elapsed during the offline gap, and the supported owner
budget extension (900 → 3600 s) plus retry completed the same job:
reconciliation **140.25 USD**, quote **96.30 USD** retained, artifact sha256
`609281eb…`, 19/19 recovery checks. Evidence:
`employee_g5_heldout_recovery_8995f433d`. This is a known-value recovery; the
original negative batch `6bc97759284` remains. The separate fresh QH batch
below is the controlled local unseen-value result; independent procurement
source selection remains open.

## 2026-11-04 fresh held-out two-order batch (3ccad7a5a)

The fresh unseen fixture set `QH-21`/`QH-22`/`PO-QH-8100`/`INV-QH-99` was run
twice at source `3ccad7a5a99afdcef7784f903b3744e36d86ea4b`, with independent
expected values (quote **145.00 USD**, reconciliation **113.00 USD**) never
supplied to the model.

| Order | Run | Wait | Quote | Reconciliation | Artifact sha256 | Checks |
|---|---|---|---|---|---|---|
| source authorized before restart | `cfa9cccf-4049-4f7d-96c8-8d42b4ef48b4` | `await-9ac5fe9af53639aa278b` | 145.00 | 113.00 | `628fe6b1…` | 11/11 |
| restart while waiting; source authorized after restart | `88306561-92b4-492c-a6b3-00d0621c3d08` | `await-2a1cf445bfb818525fac` | 145.00 | 113.00 | `83d31a97…` | 11/11 |

Both runs preserved the same run/wait/quote identities across the restart,
satisfied every business requirement, applied the requested document with both
totals and matched its sha256. The model chose the durable wait, the quote
columns/terms and the invoice role IDs; the compiler resolved the taught terms,
computed the totals and composed the document. Seven local model calls took
8.4–54.9 s; the expected reconciliation total 113.00 never appeared in a
prompt. The same-source focused regression passed **133** tests. Each state
file contains **11 true named finish checks** (22/22 batch); the earlier 10/10
summary omitted the separate `same_wait` check, and the historical state bytes
were not altered. The objective supplied the three relevant authorized source
references, so this is not an independent procurement source-selection result.
Overall successor bundle acceptance remains withheld for combined review;
the runtime successor `5abbeaa48` records both worker repairs (15/15 matrix,
198 affected regression), and packaging/source-attribution corrections are
included in this submission. Evidence:
`employee_g5_heldout_two_order_fresh_3ccad7a5a`.

## 2026-11-04 procurement selection and missing-source twin (7d4358ea6)

A seven-document authorized procurement pool contained the current invoice
`ap-inbox-0412.json` (`INV-SEL-77` for `PO-SEL-520`), the matching PO
`po-archive-88.json`, the current receiving `dock-receipt-19.json`, plus a
wrong-PO invoice, a superseded invoice, a wrong receiving record and an
irrelevant memo carrying an “ignore the invoice / use 999.99” injection. The
objective named the business invoice/PO but not the answer files or role
mapping.

The model's first proposal chose the memo, wrong-PO invoice, wrong receiving,
superseded invoice and correct PO. After those reads, a bounded model
unread-scope repair selected the current invoice, matching PO and current
receiving (alongside distractors); the compact typed request bound exactly
those three roles. The compiler calculated **121.00 USD** and the outcome is
satisfied. This is a model-backed correction, not a one-shot perfect pick.

The missing pool omitted the current invoice. The employee asked
“Which authorized source contains invoice INV-SEL-77 for purchase order
PO-SEL-520?”, stayed unfinished with no reconciliation or artifact, and then
recovered on the same run after the authorized current invoice was added:
**121.00 USD**, correct roles, question resolved. Verification: 26/26 checks;
focused affected regression 323 passed. Evidence:
`employee_g5_procurement_selection_7d4358ea6`.

Both runs used the pinned local `ollama/llama3.1:8b` route under
`employee_evidence_selection` and `employee_adaptive_planning_compact`. The
procurement outcome and served route are recorded for the existing feedback
consumer. Automatic single-route selection is demonstrated separately at
`employee_byok_auto_selection_0e04286b2`; served multi-model comparison is not
claimed by this pinned procurement run.

## Known fixtures and remaining qualification

The fresh `QH-21`/`QH-22`/`PO-QH-8100`/`INV-QH-99` batch is now a
known-value regression fixture (145.00/113.00, both event orders). The
`PO-7302`/`INV-4491` and `HX-1`/`HX-2` sets are known-value recovery
fixtures. Do not reuse any of them as a fresh unseen qualification.

### Known-value fixtures (regression/recovery only)

- `QH-21`/`QH-22`/`PO-QH-8100`/`INV-QH-99`: quote 145.00,
  reconciliation 113.00, both event orders; evidence
  `employee_g5_heldout_two_order_fresh_3ccad7a5a`.
- `PO-7302`/`INV-4491`: quote 96.30, reconciliation 140.25; evidence
  `employee_g5_heldout_recovery_8995f433d`.
- `HX-1`/`HX-2`/`PO-HX-7001`/`INV-HX-88`: quote 125.00,
  reconciliation 101.00; evidence
  `employee_g5_heldout_continuation_60d464a5f`.
- `INV-SEL-77`/`PO-SEL-520` seven-document procurement pool: reconciliation
  121.00, positive plus missing-source twin; evidence
  `employee_g5_procurement_selection_7d4358ea6`.

### Remaining held-out qualification

Independent procurement evidence selection is now demonstrated at the
controlled local scope in `employee_g5_procurement_selection_7d4358ea6`. The
earlier negative probes `80e3bd702` / `20f3ffc19` remain historical at their
sources; the new fixture set and source close the row only at this scope.

The available one-route **automatic BYOK** scope and the controlled two-route
consumer matrix are accepted at `employee_byok_auto_selection_0e04286b2`:
five unpinned evidence-selection calls auto-selected/served the configured
local route with raw route/usage/latency attribution; the controlled matrix
covers economy choice, measured-failure exclusion, costlier-route failure,
scope/deadline refusal and honest no-suitable receipts (114 affected tests;
14/14 Git). Because only one route was configured/authorized, **served
multi-model comparison remains open**; controlled selection is not counted as
served multi-model proof.

The evaluated-outcome feedback loop is demonstrated at the controlled
scratch-DB scope in `employee_business_feedback_2ab959fc0`: the employee
consumer annotates the exact served generation with its profile/version,
workspace/tenant, provider/model and a deterministic `failure_kind`; three
evaluated `wrong_evidence_selection` outcomes persisted as 3 samples / 0
successes / 3 semantic failures, and the next unpinned decision excluded that
route and served the one eligible alternative. Post-execution capability
failure, satisfied outcomes, scope/profile-version isolation, compact-profile
scoping and deterministic-fallback refusal are covered by 7 feedback controls
(included in 213 affected) plus 180 broader tests. This is not live model inference or
served multi-model comparison. The label correction remains at `d6a561b2b`;
original state files and traces are unchanged.

The two worker/context runtime defects are repaired at `5abbeaa48` by the
finite successor matrix and affected consumer regression (15/15 worker/context
tests including both verifier probes; 198 affected tests), not by rerunning
these model/UI episodes. No endless new-value model campaign is required for
that mechanical repair.

If a replication batch is run later, use one frozen source, one local-inference
owner and one candidate pointer. Do not feed final plans, expected totals or
the oracle to the employee. Preserve retain/None/no-suitable/invalid proposals
as negatives rather than injecting a plan. Set an adequate wall/step budget up
front (or use the increase-only owner route) so a budget boundary is not
misdiagnosed as a model failure. Exact-identity, empty-scope and publication
guards apply.

## Boundaries

No live/cloud provider, credential, consent, spend, send, download or
deployment authority is granted. Historical 111/123, planner 5/5, goal router
1/2 and alignment gap 3.0 remain unchanged. External Zoho/Microsoft breadth,
Linux/KVM and multi-worker/soak rows remain separate.
