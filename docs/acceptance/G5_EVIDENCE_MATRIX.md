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
| Held-out content with new identifiers/values and independent arithmetic | **Demonstrated on fresh source; bundle acceptance withheld** | `employee_g5_heldout_two_order_fresh_3ccad7a5a`: QH-21/QH-22/PO-QH-8100/INV-QH-99, two runs, quote 145.00, reconciliation 113.00, both review documents, **22/22** named finish checks (11/11 per run; earlier 10/10 omitted `same_wait`). The original negative `employee_g5_heldout_timeout_6bc97759284` and the same-job recoveries (`8995f433d`, `60d464a5f`) remain separate. Acceptance remains withheld for combined review; runtime successor `5abbeaa48` records both worker repairs (15/15 matrix, 198 affected regression), and packaging/source-attribution corrections are included in this submission |
| Held-out event order (e.g. independent work after restart, reply order) | **Demonstrated both required orders; bundle acceptance withheld** | Fresh `3ccad7a5a`: order 1 source authorized before restart; order 2 restart while waiting, source authorized after restart. Both preserved run/wait/quote identity and produced the dependent result + artifact. The earlier frozen-job recoveries remain order-1-only. Same runtime/packaging caveat |
| Held-out two-domain evidence selection without user-picked sources | **Demonstrated and accepted at controlled local scope** | `employee_g5_procurement_selection_7d4358ea6`: 7-document authorized pool with current invoice `ap-inbox-0412.json`/PO `po-archive-88.json`/receiving `dock-receipt-19.json` plus wrong-PO, superseded, wrong-receiving and prompt-injected distractors. The served model's bounded correction selected the current chain; reconciliation 121.00, 12/12 positive checks. Missing-source twin asked for `INV-SEL-77`/`PO-SEL-520`, stayed unfinished, and recovered on the same job after authorized addition: 121.00, 14/14 checks. 26/26 total; 323 affected tests; 33/33 Git. Accepted at this scope. Earlier negative `80e3bd702` / `20f3ffc19` remains historical |
| Automatic BYOK selection | **Available one-route scope accepted; controlled two-route matrix accepted; served multi-model quality not qualified** | `employee_byok_auto_selection_0e04286b2` (source `0e04286b2`, evidence `896925d22`): five unpinned employee evidence-selection calls auto-selected/served `ollama/llama3.1:8b` with raw route, usage and latency (28,034/1,058 tokens, 98.78 s). Controlled real LLMService/BYOKHandler two-route matrix covers cheaper capable choice, measured semantic-failure exclusion, costlier failure, scope/deadline refusal and honest no-suitable receipts: 9 consumer tests + 114 successor tests; 14/14 Git. Not a served multi-model comparison. Next: persist evaluated business outcomes into scoped feedback and prove the next decision changes |
| Broad adaptive judgment / general model competence | **Not qualified** | Local 8B decisions are bounded to the recorded contexts; no general claim |
| Live cloud/provider breadth, Zoho/Microsoft, Linux/KVM, multi-worker/soak | **Out of scope / separate** | No credentials/platform/authority in this batch |

## Held-out batch outcome

The frozen negative
`docs/acceptance/evidence/employee_g5_heldout_timeout_6bc97759284/` used new
identifiers, quantities and prices (quote 96.30, reconciliation 140.25). The
model selected the receiving wait and the independent quote, the wait survived
a real restart, and the same-job answer was accepted. The dependent
reconciliation was not produced: the local model's adaptation hit the bounded
deadline (initial and compact retries), so the job stayed blocked with the
required result unresolved and no artifact. This remains valid negative
evidence of the held-out model/timeout boundary.

Two same-job recoveries exist at later sources:
`employee_g5_heldout_continuation_60d464a5f`
(HX-1/HX-2/PO-HX-7001; 125.00/101.00) and
`employee_g5_heldout_recovery_8995f433d` (the original PO-7302/INV-4491 job;
96.30/140.25). Both are known-value recoveries, not fresh held-out
qualifications.

The fresh two-order batch
`employee_g5_heldout_two_order_fresh_3ccad7a5a` (QH-21/QH-22/PO-QH-8100/
INV-QH-99; 145.00/113.00) demonstrates both required event orders, 22/22 named
finish checks, and documents whose totals and hashes match. The three fresh
logs are now Git-tracked; the recovery manifest's loaded-source hash is
corrected to `8995f433d` with the superseded working-tree hash disclosed.

Runtime successor `5abbeaa48` and the packaging/provenance corrections are
accepted at their tested scopes. The runtime records both worker repairs
(caller context preserved at the thread bridge; cleanup bound to the claim
generation) with a 15/15 worker/context matrix and 198 affected tests; an
independent Agent 1 re-run at that runtime source passed 69 tests, including
both verifier probes.

Independent procurement evidence selection is demonstrated and accepted at the
controlled local scope in `employee_g5_procurement_selection_7d4358ea6`: from
a seven-document authorized pool, the served model's bounded correction
selected the current invoice, matching PO and current receiving; reconciliation
121.00, missing-source twin asked for the specific invoice and recovered on the
same job after authorized addition; 26/26 checks, 323 affected tests and 33/33
Git. The earlier `80e3bd702` / `20f3ffc19` negatives remain historical at their
sources.

Automatic BYOK available one-route selection and the controlled two-route
consumer matrix are accepted at `employee_byok_auto_selection_0e04286b2`
(114 affected tests; 14/14 Git). Served multi-model comparison remains open
until another route is configured and authorized. The next finite priority is
not another campaign: persist evaluated business outcomes into scoped routing
feedback and prove the next decision changes. No model/UI replay was used for
the mechanical corrections above.

## What this reconciliation does not claim

- It does not merge the wait episode, source-change episode and controlled
  uncertainty/cancellation evidence into one served browser episode.
- It does not treat deterministic mechanism tests as served-model choices.
- It preserves the earlier procurement-selection negative at its source; the
  new SEL-77 pool closes that row only at the controlled local scope. Separate
  evidence at `employee_byok_auto_selection_0e04286b2` demonstrates single-route
  auto-selection and a controlled two-route matrix, but not served multi-model
  comparison.
- It preserves the successful episode at its original identity and does not
  reattribute it to the successor repair.
