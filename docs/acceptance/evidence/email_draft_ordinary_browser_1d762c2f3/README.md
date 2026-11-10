# Ordinary email draft UI save → open → reload (frozen 1d762 source)

Bounded GOAL-11 email slice: one ordinary browser compose canvas, visible
subject/recipient/body edits, autosave, reload in a fresh browser context, and
an exact readback against the public GET plus the durable audit row. **No
send, no provider, no model, no credentials, no external mail.**

- Source: `1d762c2f3daee7746cf2430cd3ae37e8971364f7` (product bytes match clean
  PR829 `7fb2645c9`; branch deltas are evidence/CI only)
- Branch/worktree: `codex/web-email-ordinary-browser-20261110` at
  `/private/tmp/atom-goal11-office-browser-20261110`
- World: `office_ordinary_browser_1d762c2f3d_1794309563` (canonical symlinked
  worlds root; `ATOM_WORLD_STORAGE_PATHS=/Users/rushiparikh/projects/atom/backend/config`
  set before import; guard PASS, no mkdir/bypass/lock-split)
- Retained run: `run-b25cb62b465c` (resumed with
  `run_isolated.launch_server(reuse_run_dir=…)`; same DB/descriptor, same
  immutable source, no fresh world)
- **Exact canvas:** `2253b3b0-b51a-44b5-865a-7f50a1b7b10f`
- **Current audit:** `874d129f-37c7-4b2d-95e1-fec98a238bf0`
- Admin bootstrap account: raw `tenant_id=NULL`, `workspace_id=NULL`;
  resolved canvas scope `default/default`; ordinary UI login + already-durable
  onboarding passed.

## Seed disclosure (no UI-creation claim)

The ordinary UI create-draft control was not exercised. One email canvas was
seeded through the authorized public Canvas APIs:
`POST /api/canvas/email/create` followed by `PUT /api/canvas/{id}`. No
business job, agent turn, send, or external call was created.

Initial controlled values:

- `to  = seed@example.invalid`
- `cc  = oldcc@example.invalid`
- `subject = Email Draft OLD`
- `body = Old body OLD-1111`

## First attempt — preserved negative (honest)

The first seed also wrote a full legacy nested `draft` dict into the content.
The panel correctly sent its visible edits, but the write normalizer
`normalize_email_content` rebuilds canonical fields from a nested `draft` when
one is present, so three 200 OK autosaves persisted the OLD seed
(audits `d50f53ca`, `17aedd92`, `b8d4719c`, then `dd77d154`). This was a
**harness seed-shape defect**, not a failure of the ordinary panel or the save
transport. It is recorded in `diagnosis/` with a DB-free module-level proof
and exact source references. No API edit was substituted for a UI result.

The SAME canvas was then re-seeded, disclosed, to the ordinary
`{to, cc, subject, body}` shape only (no nested `draft`). No new canvas was
created.

## Ordinary UI result (PASS)

In the ordinary `/canvas/{id}` UI the harness:

1. verified the visible fields equal the controlled seed;
2. set `to = alpha@example.invalid, clear@example.invalid`;
3. set `cc` to a temporary address and then **cleared it** (cleared-field twin
   — final `cc = ""`);
4. set `subject = Email Draft CURRENT`;
5. replaced the body with `Current body NEW-EMAIL-7788` via the supported
   contenteditable editor;
6. waited for the ordinary 3 s idle autosave — **the Save Changes button was
   never clicked**.

Four ordinary UI autosave PUTs reached the exact canvas, all `200` with
`verification.status = "verified"` and advancing
`expected_prior_audit_id` values. The final body sent by the browser was the
ordinary shape (no nested `draft`).

Authoritative current state confirmed **before** any Save expectation:

| field | value |
|---|---|
| `to` | `alpha@example.invalid, clear@example.invalid` |
| `cc` | `""` |
| `subject` | `Email Draft CURRENT` |
| `body` | `Current body NEW-EMAIL-7788` |

- Public `GET /api/canvas/{id}` content: exact.
- Current audit: `874d129f-37c7-4b2d-95e1-fec98a238bf0` (new, not the seed).
- Email view `GET /api/canvas/email/{id}`: `to_emails` both addresses,
  `cc_emails=[]`, exact subject/body; OLD body absent.
- A **fresh browser context**, same ordinary user, reloaded the exact canvas:
  all four visible values matched the expected values and OLD was absent.
- That fresh reload also matched the public GET and a read-only fresh DB read
  whose latest audit is the same `874d129f…` row. Canvas scope stayed
  `default/default`; no foreign-scope leak and no stale nested-source
  resurrection (final content has no `draft` key).

## Send boundary

The product renders a Send button on the email panel. It was **never
clicked** and no `/send` request was made. Captured send requests: **0**.
Every request that carries a canvas UUID references exactly
`2253b3b0-b51a-44b5-865a-7f50a1b7b10f`.

## Restart / credential disclosure

Restoring ordinary login on the retained run required the existing bootstrap
fixture to reset the `admin@example.com` credential. Canvas content, audits,
and raw NULL scope were verified unchanged except for the edits above. The
generated password is not stored in this packet.

## Evidence map

- `capture/result.sanitized.json` — step statuses/checks, resume and stop proof
- `capture/put-requests.json` — the four ordinary UI PUT bodies and verified
  receipts (advancing prior-audit binding)
- `capture/canvas-id-requests.json` — every canvas-UUID request; exactly one ID
- `capture/request-summary.json` — zero send, exact-canvas derivation
- `capture/fresh-session.json` — fresh-context visible fields vs public GET/DB
- `capture/durable-state.json` — read-only current content, scope, audit history
- `capture/email-current.png` / `.page.txt` — edited canvas
- `capture/email-reloaded.png` / `.page.txt` — fresh-context reload (`v13`)
- `diagnosis/first-attempt.json` — preserved OLD-save negative
- `diagnosis/pure-function-proof.txt` — DB-free normalizer proof
- `diagnosis/source-references.md` — exact frozen-source excerpts

## Non-claims

This is one bounded ordinary email-draft save/open/reload episode on the
frozen integrated source. It is not general Office/email, whole-GOAL-11, app,
model, provider, or business-criterion acceptance. It does not claim a UI
create-draft path. Root owns the final independent review.
