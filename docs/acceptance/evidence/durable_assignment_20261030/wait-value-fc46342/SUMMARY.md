# Wait-value resolution evidence — fc46342

Source commit: `fc46342ed77df624b8922a0fc4d834935fc4f481`  
Source tree: `38618c7bc806b741498eab539c14345bb1054efe`

This directory closes the verifier's remaining wait-resolution bypasses. The
accepted local-core evidence and the positive UI twins from `e27ec63` are
preserved unchanged; no deployment, real send, or broad campaign was run.

## Verifier bypasses reproduced and closed

`wait-value-contract-repro.json` runs the resolver directly against the three
reported shapes:

| Case | Result |
| --- | --- |
| Inline receipt with `truncated=true` and one USD row | `incomplete` / `accepted_coverage_incomplete` |
| Inline receipt accepts rows 2 and 3 but supplies only row 2 | `incomplete` / `inline_rows_do_not_match_accepted_population` |
| Aggregate `subtotals={"USD": ...}` requested as `Price` | `unavailable` / `aggregate_dimension_unbound` |
| Complete inline row (positive control) | `established` / `USD` |
| Aggregate with explicit `measure` + `group_by=currency` (positive control) | `established` / `USD` |

The same contract is covered by
`tests/test_assignment_executor.py::test_fact_evidence_branch_matrix`
(complete, truncated, missing-row, blank, mixed, absent-field and
wrong-dimension evidence across inline, Parquet and aggregate receipts) and by
`tests/test_assignment_routes.py::test_incomplete_inline_evidence_cannot_resume_route`
(public route keeps the assignment waiting with `source_fact_incomplete`).

## Contract

- Coverage (`known`, `truncated`) and the receipt's own `truncated` flag are
  validated before any representation is selected.
- Accepted row identities must agree with the receipt's `selected_count`; a
  capped identity list is incomplete, not a sample.
- Inline rows must cover the accepted `__sheet_row` identities exactly and
  carry the fact field. An absent field is incomplete; only a present blank
  cell is `missing`.
- Parquet reads are filtered to accepted identities. Without identities the
  whole frame is never scanned; unreadable evidence is `unavailable`.
- Aggregate receipts must declare `measure` and a `group_by` /
  `grouping_dimension` equal to the requested fact. A subtotal key cannot
  establish an unrelated measure. `group_by` is persisted with the applied
  result so the binding survives the receipt boundary.

## Test results

- Executor: **35 passed** — `executor-tests.log`
- Assignment suite (executor, routes, send policy, resource boundary, gate,
  deterministic plan, launcher guard): **126 passed** —
  `backend-targeted-tests.log`
- Branch matrix: **1 passed** — `branch-matrix.log`
- Public-route negative: **1 passed** — `public-route-negative.log`
- Frontend (AssignmentPanel, TrainingPanel, AgentCard, serialized):
  **31 passed** — `frontend-targeted-tests.log`
- Teaching/renderer (five files): **137 passed** —
  `teaching-targeted-tests.log`
- `test_teach_thread_reply.py`: **4 failed, 12 passed** —
  `teaching-thread-reply-preexisting.log`. The same four tests fail
  identically on the clean `e27ec63` artifact; they are a pre-existing
  Outlook patch-boundary issue, unrelated to wait-fact resolution.

## Preserved accepted positives

`preserved-from.json` records the byte-for-byte copies of the positive twins
and the contradictory negative control generated against `e27ec63`. They were
not regenerated for this resolver-only change; the new source is covered by the
unit-level blank/agreeing/mixed/conflict twins in `executor-tests.log` and by
the branch matrix.

## Runtime

`runtime.json` records only the existing source service on port 8001
(PID 19046). No listener remains on 8071 or 3130. The deployment package
`assignment-successor-2026-10-30-fda4f2dc9` exists but has no
`config/APPROVED` marker and was not executed.
