# Ordinary browser document pagination — development runtime

## Source and provenance

- Product source: `c4bc1d4b623eb56d54491e4c79052885b5950cff` (frozen repair).
- Capture HEAD: `0b0bbaa35e5c08e14946c6922cbda75b4f4716f2` (evidence-only
  commit; the browser bytes are the product source above).
- Harness: `browser_harness.py`,
  sha256 `0263c715960029a1550f78bacdc3ac790641153b63c2aa0a72ffbd04f2ce3bd4`.
- Mode: **development main-web server (`next dev`)**; no optimized build and
  no optimized-build claim. HTTP loopback only; no TLS claim.
- Root independent review: `root_independent_review.json`; 85/85 retained
  observations reevaluated true.

## Bounded browser observations (85/85 checks true)

- Fresh Chromium context: cookies/local/session storage empty.
- Ordinary signup: landed `/dashboard`, one register call, one user row,
  workspace-bound; onboarding completed through visible UI.
- Fixture: 130 authorized rows, 7 foreign rows and 3 shared distractor rows
  seeded directly through the real LanceDB handler. This is **not** 130
  ordinary uploads and **not** a semantic-extraction proof.
- `/documents`: HTTP 200.
- Page 1: API 200, total 130, count 100, `has_more=true`, next offset 100;
  exact DOM/API order `w1-doc-129 … w1-doc-030`; 100 cards; no foreign,
  unknown or duplicate cards; Next enabled, Previous disabled.
- Page 2: API 200, total 130, count 30, `has_more=false`, no next offset;
  exact `w1-doc-029 … w1-doc-000`; 30 cards; Next disabled, Previous enabled.
- Previous: back to exact `w1-doc-129 … w1-doc-030`; API 200/total 130/count 100.
- Reload: page 1 exact `w1-doc-129 … w1-doc-030`; total 130. The current UI
  intentionally fetches offset 0 on mount; **no offset-survival claim**.
- API offset 200: 200, count 0, total 130, `has_more=false`, no next offset.
- Canonical identity: session/me 200; me = session = DB id; decoded SDK id
  matches; same backend generation; SDK cookie encrypted, not raw, HttpOnly;
  one user; workspace-bound and workspace id matches.
- Store health: 130 authorized rows unchanged, scoped path, 7 foreign / 3
  shared rows isolated.

## Cleanup

Owned backend PID 93085 exited `-15`; frontend PID 93116 exited `0`.
Generated dev dist removed: **322,629,922 bytes**; `next-env.d.ts` restored;
ports 18390/18391 closed; cleanup errors none. Raw env/DB/auth/logs/cookies
remain in the private 0700 world; no raw token or environment value is
published.

## Original failed run — not a pass

The prior corrected-run failure remains distinct and is **not** relabelled:

- World: `/private/tmp/root-web-doc-pagination-world-newpiy5f`
- Harness: `/private/tmp/root-web-document-pagination-browser-20261110.failed-1b0208fc.py`,
  sha256 `1b0208fc3be51a8fff3fce49d89dac5ad41d713f203a2059f35ce46ff8ddd694`
- Root reports 53 pagination observations only; canonical/store were not
  captured; overall not pass. Cause: private harness `session_cookie` parser
  `int('session-token')`, not a product failure.

## Retained existing proof

- Backend API controls: 13.
- Frontend component tests: 23.
- Original real-130 API packet:
  `docs/engineering/evidence/web_documents_pagination_b333221b2/`
  (`root_independent_original_130_results.json`).
- The original 100/30 overlap-30/missing-30 negative remains preserved.

## Screenshots

Five screenshots are included. The synthetic identity panel at the sidebar
bottom was redacted in `02`–`05`; the originals remain private. No JWT, cookie,
password, environment value or full email is published.

## Limits

Development runtime, HTTP loopback, controlled synthetic fixture. No live
database, provider, model, embedding, download or deployment. No concurrent
write snapshot guarantee; ordering is stored `created_at` string descending
then opaque `id` descending. No PR/merge.

## Secret scan

Checked 11 actual private environment/DB values. Real secret hits: 0; no JWT, Bearer token or external email is published. Two fixed non-secret placeholders remain in the harness code (`distinct-unused-backend-key` and `capture@example.com`). The synthetic identity panel was redacted from screenshots 02-05. Original screenshots remain private.
