# Final employee G5 regressions — b4c29e2b6

Runtime candidate: `b4c29e2b6d9e0d788f6a95e8a1b6c836bd0c3aa9`
(branch `codex/brennan-full-app-20261102`). The focused/regression runs used
this clean source. The main integrated product campaign is the companion
bundle `../employee_g5_integrated_change_62fa207647/` (executed product source
`648aa9487`; 18/18 checks).

This bundle supplies the final-source regression evidence for the two
behaviors that remain separate from the artifact/version campaign:

1. **Controlled provider lost confirmation** through the real normal-app
   backend, process restart, original-operation reconciliation and no resend.
2. **Evidence-sensitive reassessment** controls: a new real source version
   lets the reasoner choose quote work again, while the prior quote receipt
   and an unrelated note read are retained; an in-place source value change
   re-renders only the dependent artifact; missing/unknown qualification
   stays blocked.

## Controlled provider recovery (11/11)

- Run: `c9689e03-b2f2-4b65-9f0c-0cecdaacccd3`
- Original operation: `d0567341-ce66-4f15-a4a4-25a8113ddb26`
- Outbox sha256: `2825947be9a780d63a071e6ddc8282dedd44a2aac37c20f7d4cd454921e8ade1`
- Provider accepted then confirmation was lost; assignment blocked with one
  controlled effect.
- Real process restart preserved the same uncertain operation.
- Reconciliation `applied` completed the assignment without a second effect;
  the operation id and outbox hash stayed the same.

Full report: `uncertainty-report.json`; process log:
`uncertainty-server.log`.

## Evidence-sensitive reassessment

Companion integrated campaign (same source, exact run
`f6465719-3cf6-4087-913c-4d0c1b2a1a93`):

- employee-decided requested DOCX from the read workbook, 370.00, no supplied
  line items;
- revised workbook version persisted with version
  `a519254f8ccef6e9d52c3545a63b4c3a3f58926f`;
- served model chose `quote_calculation` again with no technical fallback;
- quote changed to 425.00 and the artifact re-rendered while the earlier quote
  operation `718e4a0e-d480-4ad0-921f-14c756cbe567` and unrelated note
  operation `d963c2b1-5ceb-4cdc-9b82-154870fae9a9` were retained.

The companion bundle has 18/18 checks, both phase artifacts and exact
request/response lineage.

Additional deterministic controls in this bundle:

- `evidence-tests.log`: **2 passed** — the new-version model-choice test and
  the in-place source-value change test. The in-place report is
  `source-change-report.json`: SC-1 price 10 → 40, quote 105.00 → 165.00,
  artifact revision changed, unrelated note operation
  `3147412f-ea56-41c3-9536-6f2b02695785` retained.
- `negative-twin.log`: **2 passed** — unknown qualification blocks the
  dependent read; missing qualification waits and resolves only through the
  explicit answer.

## Tests

`focused-tests.log`: **370 passed** in 74.24 seconds on source `b4c29e2b6`
across assignment routes/executor, employee proposal/adaptation/work requests,
artifact/version reassessment, retained source scope, patch invariants, proof
binding, campaign guard, document freshness, and prior verifier probes.

## Boundaries

- No live provider, credential, consent, send, spend or deployment authority.
- The integrated campaign is normal UI for phase 1 and normal API/UI for the
  revised-version phase; the model chose the typed work, while execution and
  artifact mechanics are deterministic compiler-owned steps.
- The in-place source-value test uses a controlled catalog fixture; the
  integrated campaign uses a real revised workbook upload.
- Historical 111/123, previous tags/sources, planner 5/5, goal router 1/2 and
  alignment gap 3.0 are unchanged.
