# Goal completion audit — 2026-10-29

Durable reference: `docs/acceptance/PRODUCT_GOAL_LEDGER_2026-10-29.md`.
Product candidate: `a9648432495f4f75f59bf4667cac3cb997d7f229` (tag
`assignment-successor-2026-10-29-a96484324`). Rollback: `901e5d773`.

Legend: **Y** = current evidence on this candidate/package; **H** = historical
evidence bound to an earlier source, not automatically a successor pass;
**—** = not claimed/not applicable; **Partial** = bounded subset only.

| # | Goal | Implementation | Unit/API | Browser | Restart | In package | Externally qualified | Deployed |
|---|---|---|---|---|---|---|---|---|
| 1 | Domain/business-independent work | Y for tested domains | Y | H | Y | Y | — | — |
| 2 | Teaching context/formatting | Y | Y | Y | Y | Y | — | — |
| 3 | Unfamiliar sheets/mappings | Y for tested workflows | Y | Y | Y | Y | — | — |
| 4 | Connected ingestion/retrieval | Y for Microsoft scope | Y | H | Y | Y | H (earlier live gates) | — |
| 5 | Large spreadsheets/formulas | Y published subset; 24-sheet current | Y | H | Y | Y | — | — |
| 6 | Excel-like canvas | Y for table adapter | Y | H | Y | Y | — | — |
| 7 | Grounded selection/calculation/assessment | Y for tested contracts | Y | H | Y | Y | — | — |
| 8 | Email/documents/presentations | Y draft/format/reopen | Y | H | Y | Y | Send — | — |
| 9 | User-created canvases inherit capabilities | Y table adapter; two shapes current | Y | H | Y | Y | — | — |
| 10 | Long-running employee work | Y controlled wait/approval/restart | Y | H | Y | Y | — | — |
| 11 | Approval/eventual sending | Live provider acceptance + exact Sent Items match Y; delivery not independently confirmed | Y | Y | Y | Y | Y | — |
| 12 | Usability/security/operations | **Bounded local core complete for documented supported workflows**; hosted deployment/public release deferred | Y | Y clean install + composite local UI | Y real process restart | Y | — | Local only |

### Live research qualification — observed

- Bounded live read-only Microsoft lookup passed on `rish@brennan.ca`; actual
  message/attachment, retrieval time, SHA-256, parsed price and QTY sum were
  recorded.
- Missing-result control produced a typed obligation and resumed the same
  assignment; conflicting prices were surfaced as a conflict.
- Live evidence was consumed by calculation and a product-rendered DOCX;
  restart preserved state and artifact.
- Real sending and deployment remain outstanding.

## Core completion successor — fda4f2dc9

- Product: `fda4f2dc9376f20a6e10de6d7d1e55cf16eeffd4`, tree
  `92924cd8f8f3cffa8e884a9a7fecc5f820f4f5ce8acbba60fdd257975df614fa`.
- Bounded external research through the shared action registry: read-only
  action allowlist, result validation, typed obligation, same-assignment
  resume, evidence-only provenance.
- 581 release-affected passed / 2 skipped; 25 kit controls; four mapping
  browser flows passed.
- Deployment and real-provider sending remain external gates.

## Core completion successor — 242c9a01f

- Product: `242c9a01ff9aebb0467ad7a619ea7e4e468f454d`, tree
  `c20bb599ff7ab65913f42cd14a5a93012b6817c93b6b0b5eddfb7c056e24c9b7`.
- Current acceptance: 578 release-affected passed / 2 skipped, 127 targeted
  passed, 22 kit controls passed; four mapping browser flows passed.
- New current boundaries: attachment-byte approval binding; 24-sheet workbook;
  cross-sheet formula text; teaching correction/restart journey; two canvas
  shapes; artifact-restart no-duplicate work.
- Rollback to `901e5d773` verified against refreshed data; 0 binding mismatches,
  no database restore, no new approval.
- Deployment remains unauthorized; `config/APPROVED` and
  `config/pilot_password` are absent. The live source writer pid `19046` still
  holds the database/WAL, so the cutover gate refuses until an authorized
  quiescence window or final refresh.
- Real-provider sending remains separately unauthorized; local payload,
  approval, attachment-byte, reconciliation and no-duplicate controls are
  implemented and tested.

## Current verification on the frozen candidate

- Mapping browser flows: B `35.00`, C `75.00`, correction `100.00 -> 80.00`,
  waiting restart `35.00`.
- Mapping regressions: 98 passed. Release-affected regressions: 508 passed,
  2 skipped.
- Full isolated deployment transaction passed: approval, preflight, verified
  backup, scoped stop/start, fresh normal login, existing taught assignment,
  fresh calculation/artifact, DeepSeek policy, HTTP 422 send denial, restart
  agreement and atomic receipt. The first attempt failed at the onboarding
  modal and is preserved.
- Production root prepared with authoritative data/artifacts and required
  memory; actual rollback to `901e5d773` re-verified against the refreshed
  handoff in an isolated copy with the same database/artifact world and zero
  binding mismatches. A logical freshness gate refused a stale snapshot and
  the current v4 handoff checks fresh. Normal login and `/api/auth/me` were
  verified on both releases in the disposable copy; the production pilot
  password is still owner-supplied.
- No production deployment, real send, credential change or source writeback.

## Remaining original-goal limitations

- **Goal 1**: tested domains only; arbitrary domain competence is not claimed.
- **Goal 3**: tested mapping/confirmation/correction/restart workflows only;
  automatic understanding of arbitrary schemas is not claimed.
- **Goal 4**: Microsoft-connected scope only; other connectors are optional/out
  of scope.
- **Goal 5**: supported large-workbook and same/cross-sheet formula subset;
  arbitrary Excel compatibility and unsupported formulas as certified
  recalculation are not claimed.
- **Goal 8**: image/chart understanding excluded; real-provider sending is
  separate and unauthorized.
- **Goal 9**: supported table adapter only; every future canvas component is not
  claimed.
- **Goal 10**: one worker per assignment; multi-worker campaigns and
  unrestricted autonomous browsing are not claimed. Bounded external research
  through the shared action registry is implemented and controlled-tested.
- **Goal 11**: payload-bound approval and one authorized real-provider send
  are qualified to provider acceptance and exact Sent Items confirmation.
  Recipient delivery is not independently confirmed. No standing permission
  and no new send; normal sending remains disabled.
- **Goal 12**: the bounded local core is complete for the documented supported
  workflows. Hosted deployment, public release and publication are deferred
  and not claimed.

No goal is marked fully complete where a promised behavior remains unqualified.

### Real send qualification — observed

- Payload-bound approval, provider acceptance, exact Sent Items message and
  attachment-hash match passed for `rish@brennan.ca` → `rish.maniar@gmail.com`.
- Restart preserved one sent message and no duplicate operation.
- Delivery remains unconfirmed; deployment remains unauthorized.

### Local core acceptance — observed

- Isolated local start on the exact product; browser auth/UI, integrated job,
  teaching/calculation/missing-info/artifact/approval, restart persistence and
  sanitized fresh install passed.
- Hosted deployment/public release/publication are deferred and not claimed.

## Final local closure — e27ec63a

- New clean clone, new Python 3.11.16 venv, pinned wheel-backed install, new
  `npm ci` and build; new empty data root.
- First start and restart without `ADMIN_PASSWORD`; normal browser login; no
  failed JS/CSS/public assets and no page errors.
- One supported UI operation: CSV upload → source selection → `2225.75 USD`
  sum → DOCX download; restart preserved the artifact hash.
- Composite long-running journey: complex teaching policy, conflict and
  missing-qualification refusals, mapping, source result `400.00`, browser
  close, real backend process restart (`34360` → `35413`), waiting-state
  reopen, active teaching snapshot retention, new Calibri lesson, correlated
  response, exact approval with the taught email protocol, one controlled outbox line, the `delivery_term` wait and its contradictory-response negative control, reload, and a
  revised-scope second run `2225.75` at Calibri 14.
- Wait-value repair: blank `Currency` cells accept an authorized resolution;
  agreeing established values are confirmations; conflicting established
  values stay waiting; mixed rows remain record-specific unresolved work.
  The blank-currency assignment completed, survived a real restart with the
  same artifact hash, and applied exactly one wait operation.
- Current-source regressions: 98 assignment/executor/send/resource tests and
  137 teaching/renderer tests passed; 31 frontend tests passed.

## Final wait-value representation closure — fc46342

Final local source `fc46342ed77df624b8922a0fc4d834935fc4f481` (tree
`38618c7bc806b741498eab539c14345bb1054efe`, tag
`local-core-2026-10-30-final`) closes the verifier's alternate-representation
bypasses.

- Coverage and accepted population are validated before selecting inline
  rows, Parquet or aggregate evidence.
- Inline rows must cover the accepted `__sheet_row` identities exactly and
  carry the fact field. A truncated receipt or missing accepted row is
  `incomplete`; an absent field is not a verified blank cell.
- Parquet reads are filtered to accepted identities and never scan the whole
  frame without identities.
- Aggregate receipts must name their `measure` and a matching
  `group_by`/`grouping_dimension`; a subtotal key cannot establish an
  unrelated measure. `group_by` is persisted with the applied result.
- Verifier reproductions: truncated inline receipt → `incomplete`; accepted
  rows 2 and 3 but only row 2 supplied → `incomplete`; subtotal `USD`
  requested as `Price` → `unavailable`.
- Current-source regressions: 35 executor tests, 126 assignment tests, 137
  teaching/renderer tests and 31 frontend tests passed; the branch matrix and
  public-route incomplete-inline negative pass separately.
- The accepted `e27ec63` positive twins and contradictory negative control
  are preserved byte-for-byte in `wait-value-fc46342/preserved-from.json`.

Evidence:
`docs/acceptance/evidence/durable_assignment_20261030/wait-value-fc46342/`
and
`docs/acceptance/evidence/durable_assignment_20261030/final-local-closure-fc46342.json`.

Conclusion: **Bounded local core complete for the documented supported
workflows.** Hosted deployment, public release and publication remain
deferred. Compatibility limits remain explicit.
