# Release candidate `68ec00b85` — launch-blocker repair and freeze

**Prepared:** 2026-10-26
**Predecessor:** `ae0c2fda3` (third attempt failed product smoke; rolled back)
**Commit:** `68ec00b851be254c251e70d814fb76e5ab13a77c`
**Status:** code frozen; packaged smoke and isolated rehearsal pending.

## Launch promise (frozen for this release)

> Upload documents or supported spreadsheets, obtain sourced answers and
> calculations, and receive taught, evidence-bound recommendations — with
> honest gaps, saved history and restart persistence.

Explicitly outside this release: mixed-source reconciliation, five-order
reviews, general policy transfer, unknown-header mapping UX, and additional
integrations. They are not advertised as complete.

## Repairs from the third-attempt failures

### 1. Delivered partial vs complete calculation

`settle_retrieval_task` separates three facts:

```text
retrieval_finished   = a read receipt matching the requested scope exists
answer_delivered     = the response carrying that answer reached the user
calculation_complete = no required-input gaps remain
```

A delivered subtotal-with-gaps is terminal as a SOURCE LOOKUP
(`status=delivered`), keeps `calculation_complete=false`, and retains
`open_requirements` with the named gap. The confirmed-read lane and the
new-ask lane both use this settlement. The smoke helper no longer sends a
confirmation after a valid delivered answer, independently of stale session
state.

Captured control: Adjustments −700.00 CAD, gap 0055/C5, grand total withheld →
delivered, gap retained, no second request.

### 2. Source authority

`core/source_requirements.py` derives required sources from:

1. the accepted task/request itself;
2. an explicit affirmative instruction in the operating agent's OWN
   applicable lesson.

Sibling lessons are knowledge, not authority. A service merely mentioned in a
retrieved lesson is not an obligation. Every considered lesson is recorded with
its id, topic, scope, goal id and source-agent id; rejected candidates carry a
reason.

The smoke agent's own two lessons name no correspondence. Thirteen sibling
email/attachment lessons (Sales Agent, Chat Assistant, atom_main) previously
forced `required=['datasets','outlook']`; they are now recorded as rejected
candidates and the captured review request resolves to `['datasets']`.

### 3. Review recovery

The accepted original objective owns the review contract. `review_requested`
reads it across confirmation and recovery text, so “go ahead” cannot downgrade
“assess this record” into “show this workbook”. Recovery stages a stored read
as evidence for narration rather than serving it as the answer. If narration is
unavailable, a review turn returns no deterministic raw read and remains
incomplete for recovery.

Captured control: review requested → read persisted → narration interrupted →
structured review still required; narration success → validated review
completes without a re-read.

### 4. Confirmation latency

For an accepted pending task plus an exact confirmation, the stored objective
and resolved file are reused before general interpretation. The general model
call is skipped and the interpretation stage is logged in seconds. Deadlines
and provider choices are unchanged.

## Verification at freeze

- Captured launch journey: 1 test covering ordinary completion, missing data,
  source authority, confirmation and review recovery.
- Blocker regressions: 21 tests across partial delivery, source requirements,
  review obligation, aggregate gap facts, review delivery-retry and pending-task
  fast path.
- Focused backend suite: **624 passed, 2 xfailed, 171 targeted tests pass**.
  The **14 failures** also fail unchanged on baseline `0271a10df` (refresh
  verdicts, two contrast fixtures, two NLU/designation fixtures) and are not
  introduced here.
- Smoke helper unit suites: **53 passed** against the packaged successor copy.
- Real captured lessons control: `required=['datasets']`; 13 sibling email
  lessons recorded as rejected candidates.

## Second independent review remediation

The first independent pass (before rehearsal) found five blocker paths and two
weak smoke assertions. They were repaired before this freeze:

- The stored-read delivery-retry lane now detects an outstanding review and
  routes to narration with the read as evidence; it never serves the raw block
  as a completed assessment.
- Recovered review payloads merge the matching durable structured result so the
  review contract receives subjects/evidence.
- Review delivery is marked before the durable session write; restart no longer
  resurrects a pending task after a delivered partial or review.
- `aggregate_calculation_facts` reads gaps from the actual aggregate record, not
  the boolean `storage_read` marker. A failed aggregation is not settled as
  delivered.
- Reply-leg tasks persist source requirements; explicit source exclusion is
  honored; document sources are derived; an empty derivation cannot erase an
  accepted obligation.
- Smoke now requires a delivered task receipt and the 0055/C5 gap for
  Adjustments, and binds persisted review evidence to this turn's execution.


## Evidence handling

Attempt-three evidence is preserved unchanged at
`/Users/rushiparikh/projects/atom-releases/ae0c2fda3/evidence/cutover/attempt-20261026T234157Z/`.
The raw candidate server log contains credential-bearing integration URLs and
remains private until scrubbed.

### Second review remediation (before rehearsal)

The second pass found the review blocker still reachable through the
stored-read delivery-retry lane, format requests, a pending review task
re-read, and the first review ask. It also found failed reviews marked
delivered and the smoke gap field mismatch. The freeze now:

- keeps the review objective/evidence hints alive into narration instead of
  resetting them;
- gates both the delivery-retry and format-request branches on an outstanding
  review;
- skips the direct re-read lane when the stored read is evidence for a review;
- sets prefetched review evidence in the ask, direct and recovery lanes;
- runs the review output contract even when no generic tool block exists;
- marks a review delivered only when `review_result.ok` is true; a failed or
  unvalidated review stays retrieved;
- passes the agent id to the task-outcome builder so the durable outcome keeps
  the review contract;
- stages reply-leg partial calculations as retrieved with gaps instead of
  leaving them pending;
- accepts the product's gap `identity` field (0055) in the smoke check.

### Third review remediation (before rehearsal)

- Repeated identical review asks now reuse the stored read (no new read or
  task operation) because the ask lane respects the stored-review gate.
- Durable-only recovery synthesizes structured subjects/evidence from its
  findings and carries a content hash, so a recovered review can be validated.
- Reply-leg partial aggregates settle the task with gaps and
  calculation_complete, not just the persisted result.
- Ask-lane review withholding requires a real decision schema; review-worded
  reads without Process/Escalate options settle as ordinary sourced reads.
- Review delivery requires the review contract to have actually been appended
  (`review_required`), so failed/unvalidated reviews stay retrieved.

### Final review remediation

A review narration exception returned before the `review_required` marker. The
delivered gate now also checks the request-local review-path flags, requires a
validated `review_result`, and keeps the task/PFR non-delivered on narration
failure. A regression asserts this exact path.
