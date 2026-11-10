# Graduation qualification UI truth + pending-review scope fix (2026-11-10)

Status: focused checkpoint for independent root verification. This is **not** a
claim that graduation or the whole application is complete, and it makes no
model-competence claim.

## What this checkpoint covers

- **Backend frozen baseline:** `498f3d22d410932c1d4b24546d52db9fc8e8e109`
  (root's original four counterexamples passed there).
- **Backend successor / final frozen source:** `cf2c7c707d81af2d5ebf5bf78d75a34190a35d95`
  (authorized finite pending-policy / durable-scope repair + semantic
  task-completion rubric criterion). No other backend policy expansion.
- **Frontend successor:** `015515ad140c642185a652915a52b1740bac9dc4`
  (ordinary TrainingPanel / AgentMaturityGuide / Approvals truth and tests).
- **Evidence commit:** the commit that adds this directory; it only adds
  evidence files and does not change product source.

## Verified gates

| Gate | Command | Result |
|---|---|---|
| **Root final 10-case gate at frozen `cf2c7c707`** | 6 probe files: pending policy, moved review scope, actual-output positive + fresh-session replay, inactive request, history-only, upward writers | **10 passed, exit 0, same_source true, 6/6 source parity** |
| Backend qualification controls | scratch SQLite, `pytest tests/api/test_graduation_qualification_join.py -q` | **34 passed** |
| Pending exact-duplicate + moved/missing/wrong-type scope | focused selection of the same file | **7 passed** |
| Frontend type gate | Node20, `tsc --noEmit --incremental false` | **exit 0** |
| Frontend UI/API suites | Jest TrainingPanel, AgentMaturityGuide, SelfDirectedPathwayCard, Approvals, maturity-api | **90 passed** |
| Local supporting reruns at final source | pending-policy and pending-scope probes | **2 + 2 passed** (supporting, not the root proof) |
| Original frozen-498 counterexamples | history-only, inactive request, upward writers | **4 passed** (supporting regression check) |

The authoritative frozen-source proof is the **root final 10-case gate**:
`root-final-ten-review.json`, `root-final-ten-controls.log`, and
`root-final-ten-parity.json`. It records `actual_exit: 0`, `same_source: true`,
and exact parity for all six captured sources at `cf2c7c707`.

Earlier root individual runs are retained honestly as **intermediate**, not as
the frozen-source proof:

- `/private/tmp/root-graduation-pending-policy-independent-20261110-2rm1rfnn`
  passed at predecessor source `4f018a...`, before the final durable-scope type
  guard; no exact `cf2` parity.
- `/private/tmp/root-graduation-pending-scope-independent-20261110-j869ues3`
  passed at predecessor source `3ce805...`, before the final durable-scope type
  guard; no exact `cf2` parity.

The earlier pre-repair failures are also preserved, not erased:
`/private/tmp/root-graduation-pending-policy-independent-20261110-yutjctot`
(1 FAIL / 1 PASS) and
`/private/tmp/root-graduation-pending-scope-independent-20261110-jd6_7uox`
(2 FAIL). Their review JSON is copied here for the record.

The backend gate used a fresh scratch SQLite database and `TESTING=1`; it never
touched the live development database.

## Pending-review repair (root counterexamples)

Root independently captured two defects against the frozen backend:

1. A changed assessment policy revision still reused the old pending action id.
2. Moving the durable `HITLAction.tenant_id` / `workspace_id` still reused the
   old pending action id even though `params` were unchanged.

The repair requires the **complete current material** before reuse: schema,
agent, current/target tier, durable row tenant/workspace, policy revision and
digest, rubric version and criteria, source revision, normalized evidence, and
requester. Durable scope must be an exact string, so missing or wrong-type
values are never reusable. A changed policy/scope produces a fresh review; the
old row stays pending and fails closed on approval (the approvals route may
truthfully return 404 for a foreign row, or 409 when reachable but stale). No
foreign row is rewritten or moved back.

Exact duplicates still reuse the same action id (no needless second review).

## Frontend truth

- Pending copy is shown only for genuinely pending
  `unresolved_missing` / `unresolved_failed` assessments with
  `allowed !== true`. Valid/already-reviewed receipts carry an approved
  `review_action_id` but never show "Review pending in Approvals."
- Missing assessment defaults to `unknown` / blocked, never allowed or "Ready."
- User-facing state labels are plain language; the raw state stays in `title`.
- TrainingPanel requires the supervisor to select explicit task/output evidence;
  it never auto-selects history statistics.
- No test was deleted, skipped, or xfailed, and no production mock bypass was
  added. Existing UI safety tests were preserved with explicit valid-assessment
  fixtures plus missing-negative twins.

## Honest scope / unresolved items

- **SQLite scratch only.** No PostgreSQL, live development DB, live provider,
  browser, model, credential, send, or spend was used.
- **Controlled human review v1 only.** The default rubric now includes an
  explicit semantic `task_completion` criterion ("Task objective is completed;
  output is correct against the expected/evidence result"). There is no model
  judge, no new score engine, and no automatic approval.
- **Unresolved policy selectors:** `default_required` and exception `domains`
  are accepted schema fields but are **not used** by `tier_required` or
  `scoped_exception`. They must not be advertised as effective exemptions.
  Resolving them would require a separate root-authorized policy change.
- **No full-graduation, app-completion, or model-competence claim.** This packet
  binds the scoped qualification join/UI checkpoint only.
- **Disclosed warnings:** the final 10-case controls log contains
  `RuntimeWarning: coroutine 'NotificationService.send_notification' was never
  awaited` for the positive-replay cases. These warnings are disclosed as-is;
  they are not hidden or suppressed, and the promotion behavior was still
  committed and verified by the gate.
