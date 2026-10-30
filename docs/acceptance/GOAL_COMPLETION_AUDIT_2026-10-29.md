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
| 5 | Large spreadsheets/formulas | Partial supported subset | Y | H | Y | Y | — | — |
| 6 | Excel-like canvas | Y for table adapter | Y | H | Y | Y | — | — |
| 7 | Grounded selection/calculation/assessment | Y for tested contracts | Y | H | Y | Y | — | — |
| 8 | Email/documents/presentations | Y draft/format/reopen | Y | H | Y | Y | Send — | — |
| 9 | User-created canvases inherit capabilities | Partial table adapter | Y | H | Y | Y | — | — |
| 10 | Long-running employee work | Y controlled wait/approval/restart | Y | H | Y | Y | — | — |
| 11 | Approval/eventual sending | Draft/approval Y; send gated | Y | H (draft) | Y | Y | — | — |
| 12 | Usability/security/operations | Package prepared | Y (19 kit controls) | Y full isolated transaction | Y | Y | — | Not deployed |

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
- **Goal 10**: one worker per assignment; multi-worker campaigns and autonomous
  third-party research are not claimed.
- **Goal 11**: draft and payload-bound approval work; real-provider send is
  **Partial/Blocked** until the qualification in
  `REAL_PROVIDER_SEND_QUALIFICATION_2026-10-29.md` passes.
- **Goal 12**: package, isolated smoke and rollback controls are prepared;
  production deployment is **not authorized** and therefore unverified.

No goal is marked fully complete where a promised behavior remains unqualified.
