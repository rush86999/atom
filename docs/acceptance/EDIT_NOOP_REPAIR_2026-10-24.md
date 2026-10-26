# Edit → verified no-op repair — 2026-10-24

**Candidate:** product `8912eba5dac56e3c6a29d18e380b1b1cf5adb3ea`
**Status:** edit/no-op sequence **verified** on the final code. Full-workflow
cutover remains held for the separate S7/route-profile items.

## Failures addressed

- **Attempt 10:** edit succeeded, but the identical re-ask entered planner
  retries.
- **Attempts 11–12:** the accepted new edit was declined by the planner.

These are distinct: `planner_unavailable` (no plan) and `planner_declined`
(served decline) remain separate diagnoses.

## Changes

1. **Provable no-op before planning.** For a single explicit assignment, the
   existing `requirement_check` runs against the authoritative artifact and
   revision before `plan_canvas_edit`. A complete, authorized,
   revision-bound receipt renders the existing `noop_completion_reply` and
   returns without dispatching the planner. A planner outage cannot defeat
   a provable no-op.
2. **Narrow deterministic compiler.** Exactly one user-supplied assignment
   that binds through the existing field vocabulary, appears verbatim in the
   artifact, has a scalar replacement, and is not negated/mixed/stale can be
   compiled into the existing `CanvasPatchOp` shape. The common apply
   validator, revision guard, preservation checks, audit, and readback still
   run.
3. **No false completion for mixed requests.** Requests with a second edit
   clause, verbless clause, source reference, unresolved addition, header
   edit, unsafe value, or ambiguous field stay on the planner; the receipt
   adds `mixed_obligations` and cannot certify.
4. **Object canvases.** Patch ops use the actual content key (`body`), not
   the record label. Replace-mode factual validation is not re-run against
   serialized object content for patch plans.
5. **Field safety.** Exact label identity (location words removed) is
   required for deterministic mutation; the reviewed `payment terms` →
   `Terms` mapping is allowed only in a document-type section
   (quotation/draft/invoice/proposal/estimate) and vetoed in
   warranty/contract/agreement/policy/terms/conditions.

## Verification

- **399 backend focused tests passed** across the edit/no-op, canvas,
  authorization, BYOK policy, LLM service, chat history/finalization, and
  orchestration suites.
- Independent review rounds found and we fixed: email field shape, mixed
  values, verbless clauses, clause-distance negation, warranty sections,
  Unicode apostrophes, prose-valued assignments, and header-only mixed
  receipts.
- **Attempt 13** (full configured profile, final code): edit compiled
  deterministically, re-ask completed via pre-plan no-op, zero planner
  dispatch; 60/62 checks, only the historical intended-route checks failed.
- **Attempt 14** (latest compiler): edit compiled deterministically and the
  re-ask completed as a pre-plan no-op. The S7 continuation leg failed
  independently (`continuation_not_date_only_completed`), so the full
  workflow did not pass on this run.

## Remaining blockers (separate)

- S7 continuation is flaky on the final code (attempt 14). The edit/no-op
  task itself passed.
- The full configured provider profile still fails the historical
  Ollama/DeepSeek intended-route checks; that profile decision remains.
- No cutover has been executed. The pilot remains `8c593e57031e`.

Evidence:
`release_evidence_20261024/byok_policy_attempts/attempt13_final/` and
`attempt14_final2/`.
