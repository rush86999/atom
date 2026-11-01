# Consolidated external qualification request — 2026-10-31

**Status: prepared, not executed.** Nothing in this document authorizes a
connection, a token renewal, a source write or a send. It is the single request
for the two inputs that cannot be produced by local engineering alone.

**Concrete current proposal (2026-11-01):**
`LIVE_QUALIFICATION_REQUEST_2026-11-01.md` identifies the current account,
tenant, genuine workbook/attachment, expected values, exact read-only Graph
operations, mailbox identity, frozen payload hashes and reconciliation scope.

Fill in the bracketed fields and reply with the statement for each part. Until
then, both remain unexecuted and the local engineering continues against
controlled fixtures.

## Overall completion

Two current-candidate live qualifications remain:

1. **Part A** — Microsoft read-only connection, ingestion and agent retrieval.
2. **Part B** — one Outlook send with the exact authorized account, recipient,
   payload/attachment and reconciliation scope.

Hosted deployment and publication are **deferred, not completion gates**.
The accepted local UI, workbook, deterministic-rule and durable-execution
evidence is closed; do not repeat those campaigns without a relevant source or
product change. Failed discretionary-model judgment remains a separate,
unsupported capability and does not invalidate the qualified deterministic
taught-policy path.

---

## Part A — Microsoft read-only qualification (goals 4 and 5)

Purpose: demonstrate the supported Microsoft workflow through the normal
Data/Settings and employee surfaces, without writing to the source.

What I need from you:

| Field | Value |
|---|---|
| Account / tenant to use | `[account or tenant id]` |
| Is an existing authorized connection reusable? | `[yes/no]` |
| If yes, connection label / resource id | `[connection reference]` |
| One workbook to read (path or item id) | `[workbook]` |
| One email attachment to read (message id or search term) | `[attachment]` |
| Read-only confirmation | `[yes]` |

Statement requested:

> “I authorize read-only use of `<account>` for the workbook `<workbook>` and
> the email attachment `<attachment>`. No writes, no sends, no token changes.”

What will be run (all read-only):

1. connect/reuse the connection through Settings → Data;
2. ingest the genuine workbook and the email attachment;
3. retrieve rows without supplying them in the request;
4. calculate and cite the complete eligible population;
5. show stale, revoked and inaccessible resource handling;
6. refresh one disposable changed source and show affected results invalidated
   while prior provenance is preserved;
7. restart and reopen.

What will **not** be done: source modification, token renewal, writes to
connected systems, or manufacturing catalog rows/permissions to make a gate
pass.

Evidence produced: connector run JSON (resource ids, versions, hashes),
retrieval citations, refresh/invalidations, restart identity.

---

## Part B — One authorized live Outlook send (goals 8 and 11)

The adapter and grant gating are implemented; the live path is disabled by
default. Detail and evidence checklist:
`REAL_TRANSPORT_QUALIFICATION_REQUEST_2026-10-31.md`.

What I need from you:

| Field | Value |
|---|---|
| Sending account (signed-in Outlook user id) | `[account]` |
| One owner-controlled test recipient | `[mailbox]` |
| Grant | `max_effects=1`, `actions=["outbound"]`, `recipients=[mailbox]`, expiry ≤ 24h |
| Payload | fixed subject/body; either **no attachment** or exactly one owner-named file with path and SHA-256. The exact payload SHA-256 is recorded before dispatch. |
| Reconciliation scope | Sent Items folder and search window, expected exactly one matching row; a repeat resume adds none. |
| Runtime flags | `ATOM_ASSIGNMENT_ALLOW_LIVE_SEND=1` and `ATOM_ASSIGNMENT_ALLOW_STANDING_LIVE_SEND=1` |

Statement requested:

> “I authorize one live Outlook send to `<recipient>` under a one-use grant
> with the exact payload/attachment and reconciliation scope stated above.”

What will be collected: grant id and `1/1 exhausted`, payload SHA-256 (and the
authorized attachment hash when one is named), provider acceptance ref, Sent
Items read-back within the stated reconciliation scope, exactly one Sent Items
row on repeat resume, no assignment-approval HITL row for the covered send, and
no token/key/body leakage in logs.

Provider acceptance, Sent Items confirmation and recipient delivery are three
distinct claims and will be reported separately.

---

## What these requests do not cover

- Hosted deployment or publication (owner-deferred, not a local gap).
- Any second recipient, an additional attachment beyond the one explicitly
  named, bulk or recurring send.
- Multi-worker/soak certification.
- Discretionary model judgment: the deterministic taught-rule path is already
  qualified; model access is optional and would be requested separately only
  if discretionary work is needed.

Absent a filled field and its statement, the corresponding action remains
unperformed.
