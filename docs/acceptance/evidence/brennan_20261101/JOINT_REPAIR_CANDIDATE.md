# Joint repair candidate — pricing, outcome mapping, readback

Status: focused implementation + component/joint controls. Not verifier
acceptance; no live provider action. Historical 111/123 remains unchanged.

## Candidate

| Item | Value |
|---|---|
| Branch | `codex/brennan-joint-r2` |
| Candidate base | Agent 1 complete repair `0aebf372e` |
| Agent 2 provider base | `b9c8ba654` (merged) |
| Agent 2 readback repair | `703439f2b` |
| Review base requested | `b9c8ba654` |
| Configuration | local scratch DB/artifacts, controlled providers, no live Zoho/Microsoft credentials |

## Blocking findings closed

### Discount unknown context (Agent 1)
- Candidates are true / false / unknown. Higher-specificity or equal-specificity
  unknown rules are retained and compared by normalized material pricing
  behavior (Decimal rate, discount basis/type, cap/amount).
- Missing qualification with general 5% + licensed 10% now raises a durable
  `discount_scope` obligation; licensed → 10%, unlicensed → 5%.
- Missing effective date asks; equivalent rates/behavior do not; definitively
  excluded exceptions do not block; equal established rules still conflict.
- Obligation binds assignment, line identity, missing fields, candidate rules
  and revisions, teaching revision and source versions; the answer resumes the
  original calculation. Wrong-line/stale answers refuse; duplicate answer does
  not repeat work.
- Completion-oracle tests enumerate fully specified completions.

### Executor outcome consumption (Agent 1)
- Verified applied → applied.
- Trusted no-effect (`proven_not_applied`) → before-effect failure with
  distinct `error_class`; unavailable read → failed/unavailable.
- Possibly applied / readback conflict → uncertain, durable reconciliation,
  dependent work blocked, remote identity retained in evidence.
- Mutating generic exceptions → uncertain; malformed mutation envelopes fail
  closed; uncertain steps cannot be retried until reconciled.
- Public-route real `connected.books.create_estimate` control: provider accepts,
  readback connection dies, assignment uncertain (not completed), dependent
  work blocked, retry/restart creates no second effect, reconcile settles the
  original operation.

### Commercial readback (Agent 2)
- Sparse readback (ID + total) is `incomplete`, not verified.
- Wrong item/quantity/rate with matching total is `mismatch` with line conflicts.
- Customer/currency/date/reference/tax/totals and canonical line multiset are
  compared; provider-managed fields are excluded. Readback retry never repeats
  the create.

## Verification

| Suite | Result |
|---|---|
| Joint route/executor/quote/evidence + commercial readback + Agent 2 connected/checkpoint/bookkeeping + joint campaigns | **258 passed** |
| Retrieval selector | 8/8; selection/sufficiency 1.0; mean 0.045ms (selector only, not end-to-end ingestion/provider latency) |

## Remaining joint gaps

- WorkDrive/OneDrive bytes → parsed typed records → quote line items is still
  not wired through the public assignment; connected reads are contract-level.
- Quote-specific browser close/restart/source-change journey is not yet run.
- No live provider credentials/actions; Outlook draft only.
