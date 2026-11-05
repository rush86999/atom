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
| Held-out content with new identifiers/values and independent arithmetic | **Demonstrated and accepted at controlled local scope** | `employee_g5_heldout_two_order_fresh_3ccad7a5a`: QH-21/QH-22/PO-QH-8100/INV-QH-99, two runs, quote 145.00, reconciliation 113.00, both review documents, **22/22** named finish checks (11/11 per run; earlier 10/10 omitted `same_wait`). The original negative `employee_g5_heldout_timeout_6bc97759284` and the same-job recoveries (`8995f433d`, `60d464a5f`) remain separate. Runtime successor `5abbeaa48` and packaging/source-attribution corrections are accepted at their tested scopes |
| Held-out event order (e.g. independent work after restart, reply order) | **Demonstrated and accepted at controlled local scope** | Fresh `3ccad7a5a`: order 1 source authorized before restart; order 2 restart while waiting, source authorized after restart. Both preserved run/wait/quote identity and produced the dependent result + artifact. The earlier frozen-job recoveries remain order-1-only |
| Held-out two-domain evidence selection without user-picked sources | **Demonstrated and accepted at controlled local scope** | `employee_g5_procurement_selection_7d4358ea6`: 7-document authorized pool with current invoice `ap-inbox-0412.json`/PO `po-archive-88.json`/receiving `dock-receipt-19.json` plus wrong-PO, superseded, wrong-receiving and prompt-injected distractors. The served model's bounded correction selected the current chain; reconciliation 121.00, 12/12 positive checks. Missing-source twin asked for `INV-SEL-77`/`PO-SEL-520`, stayed unfinished, and recovered on the same job after authorized addition: 121.00, 14/14 checks. 26/26 total; 323 affected tests; 33/33 Git. Accepted at this scope. Earlier negative `80e3bd702` / `20f3ffc19` remains historical |
| Automatic BYOK selection | **Available one-route scope accepted; controlled two-route matrix accepted; served multi-model quality not qualified** | `employee_byok_auto_selection_0e04286b2` (source `0e04286b2`, evidence `896925d22`): five unpinned employee evidence-selection calls auto-selected/served `ollama/llama3.1:8b` with raw route, usage and latency (28,034/1,058 tokens, 98.78 s). Controlled real LLMService/BYOKHandler two-route matrix covers cheaper capable choice, measured semantic-failure exclusion, costlier failure, scope/deadline refusal and honest no-suitable receipts: 9 consumer tests + 114 successor tests; 14/14 Git. Not a served multi-model comparison |
| Evaluated business outcome → scoped routing feedback | **Shared business/legacy writer CAS repaired and requalified at controlled scratch-DB scope** | `employee_feedback_shared_cas_c1cd3bea5` (shared-CAS source `c1cd3bea5`; final executed source `4e98ec5ab`, with test isolation `8b0fb2f0b` and insert-before-cache `4e98ec5ab`; predecessors `employee_feedback_cas_6cdc50cc7`, `employee_feedback_boundary_e4f3733c1` and original `employee_business_feedback_2ab959fc0` preserved). Business and legacy grounding/fabrication annotations use one database-enforced CAS and one monotonic `evaluation_revision`. A pending business marker skips when any verdict committed; a stale legacy grounding reader skips when a business failure committed; stronger judgement wins; duplicate verdicts are idempotent; changed binding refuses. Legacy keeps its generation+model binding without employee fields; business keeps its exact receipt binding; no dirty ORM flush; cache invalidates only after commit; an unresolved business marker no longer hides a legacy verdict. **39 feedback/interleaving/cross-writer/probe controls on Python 3.11.16 and 3.14; 476 broad affected tests on both; 3/3 legacy cross-writer probes, 2/2 race probes and 3/3 boundary probes on both; explicit order repro 65/65; the verifier's order-sensitive empty-pool failure is isolated by a test-local health monitor and BYOK memo/cooldown cleanup, so the 476-test broad run passes on both versions**. Scratch SQLite and doubled transport; PostgreSQL CAS implemented but not runtime-qualified. Not live inference or served multi-model comparison |
| Pending/grounding capability classification | **Repaired at controlled scratch-DB scope** | `employee_feedback_classification_f091904ce` (source `f091904ce`): an unresolved/pending/unknown business result plus ONLY a positive `grounding_ok`/`grounding_passed` marker is excluded from capability quality samples. Real fabrication, ignored-evidence, business-failure and unsafe judgements remain observable as non-success samples; explicit validated decision success and genuinely satisfied results still contribute; legacy rows without a business-outcome marker keep their established compatibility behavior. The durable row and fabrication/grounding accounting are preserved. **7 classification controls; 47 feedback/classification/probe controls; 483 broad affected tests on Python 3.11.16 and 3.14; independent pending-quality probe 1/1**. Scratch SQLite and doubled transport; no model inference; PostgreSQL runtime qualification not claimed |
| Employee wait-choice bounded consumer | **Schema/no-result recovery accepted; semantic wait acceptance withheld** | `employee_wait_choice_5cc897dbb`: the captured 27,513-char / 104.9 s wait-choice no-result was a validation failure (empty `blocks`, untyped `new_steps`), not transport. A focused typed wait context/schema now returns a model-selected `await_evidence` in **13.15 s** on the existing local route (`342` merged affected tests; 17/17 replay checks). This is schema-recovery evidence only: the replay waited for an invoice already present under an ambiguous prerequisite, so it is not a satisfactory business wait choice. Original negative remains at `employee_byok_auto_selection_0e04286b2` |
| Employee wait-choice semantic policy guard | **Demonstrated at controlled consumer/route scope; no inference** | `employee_wait_choice_policy_0a9df5377` (guard `0a9df5377`, integrated feedback `e4f3733c1`, genuine-missing follow-up `fea7948af`): waits are validated against trusted readiness and `allowed_proposal_kinds` before adoption. Rejects all-read ambiguity under clarify/retain-only policy, ambiguous/already-ready records, unnamed missing roles, unread authorized evidence, explicit contradictory `blocks_operation`, and multiple missing prerequisites without a named blocked operation. A genuine missing external fact still waits, including under the clarify/retain default; ready independent work remains available. Rejection retains applied results/requirements and returns deterministic clarify/retain; the public route persists the targeted question without creating a wait step. **368 affected tests; 20 guard-focused; independent probe passed; no model/provider call** |
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
until another route is configured and authorized.

The evaluated-outcome feedback loop is repaired and requalified at the
controlled scratch-DB scope in `employee_feedback_shared_cas_c1cd3bea5`
(shared-CAS source `c1cd3bea5`; final executed source `4e98ec5ab`, with test
isolation `8b0fb2f0b` and insert-before-cache `4e98ec5ab`; predecessors
`employee_feedback_cas_6cdc50cc7`,
`employee_feedback_boundary_e4f3733c1` and original
`employee_business_feedback_2ab959fc0` preserved unchanged). The employee
consumer annotates the exact served generation with its profile/version,
workspace/tenant, provider/model and deterministic `failure_kind`; three
evaluated `wrong_evidence_selection` outcomes persisted as 3 samples / 0
successes / 3 semantic failures, and the next unpinned decision excluded that
route and served the one eligible alternative.

The successor closes the shared-writer gap. Business and legacy grounding/
fabrication annotations now use one database-enforced CAS and one monotonic
`evaluation_revision`: a pending business marker cannot erase a committed
legacy verdict, a stale legacy grounding reader cannot erase a committed
business failure, a stronger judgement wins, duplicate verdicts are idempotent,
and a changed binding refuses. Legacy keeps its generation+model binding
without employee fields; business keeps its exact receipt binding. No dirty ORM
flush follows the CAS, the cache invalidates only after commit, and an
unresolved business marker no longer hides a legacy verdict. The generation
receipt and served route survive an awaited child task, and `model_wait_choice`
remains non-successful until an explicit verdict. **39 feedback/interleaving/
cross-writer/probe controls on Python 3.11.16 and 3.14; 476 broad affected
tests on both; 3/3 legacy cross-writer probes, 2/2 race probes and 3/3 boundary
probes on both; explicit order repro 65/65; the verifier's order-sensitive
empty-pool failure is isolated by a test-local health monitor and BYOK memo/
cooldown cleanup, so the 476-test broad run passes on both versions**. Scratch
SQLite and doubled transport; PostgreSQL CAS is implemented but not runtime-qualified. This is not
live inference or served multi-model comparison. No model/UI replay was used
for the mechanical corrections above.

The pending/grounding classification is repaired at
`employee_feedback_classification_f091904ce` (source `f091904ce`). An
unresolved/pending business result plus only a positive grounding marker is
excluded from capability quality samples rather than credited through
transport success; real fabrication, ignored-evidence, business-failure and
unsafe judgements stay observable as non-success samples. Explicit validated
decision success and genuinely satisfied results still contribute, and legacy
rows without a business-outcome marker keep their established compatibility
behavior. Durable rows and fabrication/grounding accounting are unchanged.
**7 classification controls; 47 focused controls; 483 broad affected tests on
Python 3.11.16 and 3.14; independent pending-quality probe 1/1.** No model
inference or browser replay; PostgreSQL remains unqualified.

The bounded wait-choice consumer is demonstrated at
`employee_wait_choice_5cc897dbb` as schema/no-result recovery only: the
captured 27,513-char / 104.9 s no-result was a validation failure, not
transport. The focused typed wait context now returns a model-selected
`await_evidence` in 13.15 s on the existing local route; 342 merged affected
tests and 17/17 replay checks. The replay's wait targeted an invoice already
present under an ambiguous prerequisite, so semantic wait acceptance remains
withheld. The original negative remains preserved. The direct replay did not
use an application DB, so the feedback-persistence row remains Agent 2's
scratch-DB evidence above.

The semantic guard is demonstrated at
`employee_wait_choice_policy_0a9df5377` (guard `0a9df5377`, integrated
feedback `e4f3733c1`, genuine-missing follow-up `fea7948af`). It validates an
expanded wait against trusted
readiness and `allowed_proposal_kinds` before adoption: all-read ambiguity
under a clarify/retain-only policy, ambiguous/already-ready records, unnamed
missing roles, unread authorized evidence, explicit
contradictory `blocks_operation`, and multiple missing prerequisites without a
named blocked operation are refused. A genuine missing external fact still
waits, including under the clarify/retain default; ready independent work
remains available. Rejection retains applied results and
unresolved requirements, returns deterministic clarify/retain, and the public
route persists the targeted question without a wait step. **368 affected
tests; 20 guard-focused; independent probe passed; no model/provider call.**
The captured replay remains unchanged as schema-recovery evidence.

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
