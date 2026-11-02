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

### Discount rule language (Agent 1, final boundary)
- Supported executable schema: percentage `rate` (0..1), optional
  `discount_type` in percent/percentage/rate, optional `basis` in
  rate/percentage/percent. Metadata is separate.
- Monetary caps, fixed/other discount types, unsupported bases and unknown
  material fields now produce a targeted `discount_rule_unsupported` obligation
  **before selection or arithmetic**. Cap currency/unit ambiguity is refused.
- Comparison and execution share one normalized percentage representation;
  the calculation receipt and row rule reference preserve normalized rate,
  type, basis, lesson id and revision. The executor JSON bound was raised so
  the nested representation is not replaced by an ellipsis.
- Public-route controls: supported rule → 180.00 with complete receipt; capped
  rule → waiting/refusal with no calculation or document.

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

### Executable data transfer (Agent 1 consumption)
- Serialization now separates diagnostics from executable fields. Rows, items,
  line items, bytes/content_b64, records, receipts and evidence are preserved
  in full up to explicit bounds; oversized executable values refuse instead of
  being sliced. Diagnostic summaries remain bounded.
- Actual registered WorkDrive read → executor → row mapping → quote calculation
  controls at 79, 80 and 81 rows: all rows survive, content_b64 is byte-exact,
  multibyte text is preserved, read receipt is complete/not truncated, and the
  quote total uses every row.
- A 501-row bounded read returns partial coverage and blocks full-population
  calculation; oversized inline content fails explicitly with no downstream
  work.

### Serialization budget (Agent 1 consumption)
- One shared budget covers the complete executable result: **4 MiB UTF-8**,
  **100,000 nodes**, **100,000 dictionary/list entries**, **512-character
  keys**, plus per-value and nesting limits. The budget is not reset per child.
- Aggregate overflow, oversized keys and multibyte over-budget content raise
  `ExecutablePayloadTooLarge`; no silent truncation.
- A read over budget returns a typed payload-too-large failure. A mutation over
  budget after dispatch raises uncertainty with the remote identity preserved;
  it is never classified as proof of no effect.
- Actual WorkDrive read → executor → calculation controls at 79/80/81 rows and
  a 501-row partial read remain green.

### Public assignment connected-data path
- `POST /api/assignments` now accepts `evidence_reads` and resolves a read
  result reference in `calculation.line_items`.
- Control: actual registered `connected.workdrive.read_file` returns 81 CSV
  rows; the public assignment reads them, maps them into `quote.calculate`,
  completes at **81.00**, and preserves the complete/non-truncated read
  receipt.

## Remaining joint gaps

- WorkDrive/OneDrive bytes → parsed typed records → quote line items is still
  not wired through the public assignment; connected reads are contract-level.
- Quote-specific browser close/restart/source-change journey is not yet run.
- No live provider credentials/actions; Outlook draft only.
