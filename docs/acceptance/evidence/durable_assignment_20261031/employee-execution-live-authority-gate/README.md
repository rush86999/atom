# Real-transport bounded authority — implemented, not sent

The real Outlook adapter (`email.send_outlook`) is now eligible for bounded
standing authority only when **both** explicit flags are set:

- `ATOM_ASSIGNMENT_ALLOW_LIVE_SEND=1`;
- `ATOM_ASSIGNMENT_ALLOW_STANDING_LIVE_SEND=1`.

Only then does the adapter opt into the same executor predicate used by the
controlled outbox. Coverage still requires an explicit one-use grant with the
named recipients and remaining effect count; the recipient set is checked
against the actual `to`/`cc` inputs; otherwise the send remains
approval-required. The default configuration is unchanged and approval-only.

Controls (`live-authority.log`, **2 passed**):

- with neither flag, with only the live-send flag, or with no grant, the
  adapter is not covered;
- with both flags and a matching grant, the adapter is covered;
- a recipient outside the grant is not covered.

**No live send was performed.** The concrete authorization request is
`docs/acceptance/EXTERNAL_QUALIFICATION_REQUEST_2026-10-31.md` (Part B) and
`docs/acceptance/REAL_TRANSPORT_QUALIFICATION_REQUEST_2026-10-31.md`; it lists
the account, owner-controlled recipient, one-use grant, fixed payload, evidence
and the exact statement required.
