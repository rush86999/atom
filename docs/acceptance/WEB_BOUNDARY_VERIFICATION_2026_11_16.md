# Main-web boundary verification — November 16, 2026

This is bounded acceptance evidence, not release approval. The original 143
claims and 18 goals remain intact; no readiness numerator was recomputed.

## Source and environment

The product source was PR #963 head `e58bdf314a5eea6f53a98ee540792968c072914e`,
whose Git tree `446a723e1ad5ae5e76b51b383ade0964a481668e` is identical to merge
`2346e6b6bd9334441bc17d5f09f1ca88ef2a07c7`. The actual running source identity was
`e58bdf314a5e-dirty.7d401fa39a75`: Next generated the sole tracked difference,
`frontend-nextjs/next-env.d.ts`, changing its generated type import.

An isolated synthetic SQLite world used the core product profile and a
selected-empty provider policy. No external model request or live connector
operation occurred. TCP access was restricted to the isolated frontend/backend;
Chrome could bind its local Unix startup socket. Independent probes confirmed
external TCP and the local model port were denied. Owner data was not used.

A production Webpack build passed with type validation enabled (94.208 seconds).
Two earlier default Turbopack attempts failed under the test restrictions and
remain negative evidence. This does not qualify the default Turbopack build.

## Observed boundaries

| Original goal | Evidence | Limit |
|---|---|---|
| 1: ordinary account use | Real browser login form and session reload passed; no token injection. | Synthetic administrator only in this run; not SSO, signup, recovery delivery or backend-restart acceptance. |
| 1 / 15: account and sessions | Settings run: 25 pass, zero fail, one missing, one skipped. Password change/reload/restore passed. Revoking a disposable browser session yielded secondary 401 while primary remained 200. | Overall settings result remains incomplete: environment-managed AI policy save returned 409. |
| 1 / 15: 2FA | Follow-up: 23 pass, zero fail, one missing, four skipped. Routed authenticated enable/disable requests returned 200; the account UI showed enabled/disabled after navigation. A real TOTP step elapsed; final state was disabled. | Not user-click setup-wizard or login-challenge coverage. Password checks were intentionally skipped in this follow-up because the preceding run covered them. No combined full-settings pass is claimed. |
| 2 / 15: provider and routing settings | Disposable provider registration, reload persistence and deletion passed. Routing UI matched actual backend telemetry and refreshed it; empty telemetry stayed empty. | No provider connection, Discover/Test, inference, routing quality or model suitability measurement. AI policy mutation remained environment-locked. |
| 3: documents | One synthetic TXT uploaded through the UI (200); the same document reopened after reload. UI download matched all 88 original bytes. UI deletion returned 200, list remained absent after reload, detail returned 404. | No backend restart in this run, other-format breadth, retrieval quality, independent vector-store audit or whole-goal acceptance. |
| 15: exposed core pages | Documents, Agents, Learning, Assignments, Approvals, Activity and Settings rendered after real login with no page exceptions. | Navigation/rendering only, not workflow execution. Task tracking is intentionally deferred by the core profile; this does not waive its original claims. |

The document test retained two failed attempts: the asynchronous welcome tour
blocked card clicks, and an early Escape preceded its mounting. The final
follow-through waited for the tour to become visible, dismissed it normally,
and continued the same upload. There was no duplicate upload or forced click.

Independent read-only SQL/file inspection confirmed the materialized upload
was absent and its SQL record had `freshness_status=removed`, with zero active
SQL rows and zero eligible lexical-search rows. Physical SQL/FTS tombstones
remain intentionally, preventing stale producers from recreating deleted
content. This is revocation, not physical erasure of all stored text. An initial
incorrect zero-physical-rows assertion failed and remains recorded.

## Fleet diagnostics remain separate from application acceptance

The earlier capped live fleet test failed. It produced no delegation chain;
its exact physical-request count and upstream HTTP status were not retained.
Those historical values remain unknown. No new live allowance was consumed.

A separate private verifier candidate passed 11 offline fault controls with all
networking denied: delivery callback contract, exception-preserving final
receipt, exclusive receipt creation, numeric upstream status propagation,
and guard accounting. One test distinguished 17 attempted forwards from 16
actual synthetic send starts and verified the seventeenth was refused.

This candidate is not a product change or live qualification. Its transport
adapter is not yet wired for live use; full controller integration, concurrent
cleanup/drain accounting, fresh source preparation and a new bounded owner
allowance remain prerequisites. The application's fleet/model-quality failure
is unresolved. Original negative evidence and the one-shot marker are preserved.

## Evidence retention and next gates

Source-bound reports, hashes, failed attempts and root adjudications are retained
in the operator's local handoff bundle. They are private runtime evidence, not
committed credentials or portable CI fixtures. The browser test processes were
gracefully stopped after their ownership was verified; their world remains.

Remaining priorities include capable-model fleet delivery, ordinary unfamiliar
work and training outcomes, backend-restart acceptance at current source, live
connector/recipient delivery where required, and the real elapsed TASK-WAIT-01
soak. Its 48-hour boundary is no earlier than November 16 at 06:42:25 UTC; this
record does not advance the clock or transfer a historical pass.
