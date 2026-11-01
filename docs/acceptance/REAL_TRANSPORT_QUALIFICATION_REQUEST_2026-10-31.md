# Real-transport bounded-authority qualification request — 2026-10-31

**Status: prepared, not executed. No live send has been performed.**

This request asks the owner to authorize exactly one bounded Outlook send so the
real transport can be qualified under the same standing-authority contract
already accepted for the controlled outbox.

## Configuration to qualify

| Item | Value |
|---|---|
| Transport | `email.send_outlook` (existing `EmailCanvasService` path) |
| Required runtime flags | `ATOM_ASSIGNMENT_ALLOW_LIVE_SEND=1` **and** `ATOM_ASSIGNMENT_ALLOW_STANDING_LIVE_SEND=1` |
| Authority | one explicit standing grant: `actions=["outbound"]`, `max_effects=1`, named recipient(s), optional expiry |
| Approval behavior | no per-send HITL within the grant; the grant itself is the human authorization |
| Out-of-scope | a second effect, a different recipient, attachments, bulk/recurring sends, autonomous substantive judgment |

The implementation is in place: the executor only covers `email.send_outlook`
when both flags are set, the grant names every recipient, the effect count has
not been exhausted, and the adapter is the real Outlook path. Otherwise the
send remains approval-required. The gate is pinned by
`backend/tests/test_assignment_live_standing_authority.py`.

## Requested authorization

The owner supplies and approves:

1. **Account**: the signed-in Outlook account / User id used by the local app.
2. **Recipient**: one owner-controlled test mailbox (not a customer or third
   party). Suggested placeholder: `owner-qualification@example.invalid`.
3. **Grant**: `max_effects=1`, `recipients=[that mailbox]`, expiry within 24h.
4. **Payload**: one prepared email with a fixed subject/body and no attachment;
   the exact payload SHA-256 is recorded before dispatch.
5. **Statement**: “I authorize one live Outlook send to <recipient> under this
   one-use grant.”

Without that statement and recipient, the request remains unexecuted.

## Evidence to collect on the authorized run

- grant id, use counter (`1/1`, `exhausted`), recipient set, payload SHA-256;
- provider acceptance response and `provider_ref`;
- a Sent Items read-back matching the exact subject/body (and content hash);
- exactly one Sent Items row for the payload; a repeat execute/resume adds none;
- no `assignment_approval` HITL row for the covered send;
- logs with no token, key or message body leakage;
- the existing controlled-outbox evidence remains separate.

## Failure/rollback

- If the provider rejects before effect: `failed_before_effect`, grant use
  released, no automatic retry.
- If the provider outcome is unknown: `uncertain`, full reserved bound charged,
  reconciliation required, no resend.
- If a duplicate or wrong recipient is observed: stop, preserve the ledger, and
  treat the live transport as unqualified.

## Explicit non-claims

This request does not qualify autonomous substantive judgment, multi-worker
execution, bulk/recurring sending, delivery to third parties, or universal
reliability. Hosted deployment and publication remain owner-deferred.
