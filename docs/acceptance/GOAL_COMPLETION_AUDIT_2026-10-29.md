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
| 11 | Approval/eventual sending | Draft/approval + attachment-byte Y; send gated | Y | H (draft) | Y | Y | — | — |
| 12 | Usability/security/operations | Successor package prepared | Y (22 kit controls) | Y current mapping flows | Y | Y | — | Not deployed |

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
- **Goal 11**: draft and payload-bound approval work; real-provider send is
  **Partial/Blocked** until the qualification in
  `REAL_PROVIDER_SEND_QUALIFICATION_2026-10-29.md` passes.
- **Goal 12**: package, isolated smoke and rollback controls are prepared;
  production deployment is **not authorized** and therefore unverified.

No goal is marked fully complete where a promised behavior remains unqualified.
