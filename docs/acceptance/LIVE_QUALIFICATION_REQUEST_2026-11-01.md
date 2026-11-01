# Concrete live qualification request — 2026-11-01

**Status: prepared, not executed. No live Graph read and no live send have been
performed.** This document does not authorize either operation by itself. Reply
with an explicit selection and statement for A and/or B.

Candidate: product source `bc164fb96632` (docs head `f00c2ea7d`), frontend build
`qEeLBEVZSyQjyn3v-Wnjh`. Configuration: local single-worker app,
`ATOM_PRODUCT_PROFILE=core`, controlled assignment transport. The live-send
flags are currently unset; they are enabled only for an authorized Part B run
and reverted afterwards.

## What is already known locally (no owner re-discovery needed)

| Item | Value |
|---|---|
| Microsoft account | `rish@brennan.ca` (`userPrincipalName` / `mail`, Graph user id `2927f127-c837-4f4b-beac-5c7b723bf887`) |
| Tenant | `8899c7a5-b671-4f16-bb48-15d5e78158af` |
| Existing grant | `integration_tokens` provider `outlook` / `microsoft`, status `active`; access token expired `2026-11-01T11:26:12Z`; refresh token present |
| OAuth client configuration | present in the private runtime environment; tenant/client keys are not printed or committed |
| Application login | `admin@example.com` (this is **not** the Outlook mailbox identity) |
| Live-send flags | `ATOM_ASSIGNMENT_ALLOW_LIVE_SEND` and `ATOM_ASSIGNMENT_ALLOW_STANDING_LIVE_SEND` currently unset/0 |

Normal refresh of the existing grant is included in Part A: the normal
`OneDriveService.get_access_token_resolution` resolver uses the stored refresh
token and the same approved client/scopes. It creates no new consent and changes
no permissions. If refresh fails (`invalid_grant`, `invalid_client`, revoked or
missing), execution stops for reconnect; cached rows or another account are not
substitutes.

---

# A — Microsoft read-only qualification

## Authorized source

The genuine workbook is also the genuine email attachment; no unverified
OneDrive item is assumed.

| Field | Value |
|---|---|
| File | `HARSLE press brake stock price list.xlsx` |
| Source | Outlook message attachment |
| Message id | `AAMkADdlNTY5N2I1LTQwNTMtNDQ2OC04MzBlLTU5OGFmZGQ2MzRmYQBGAAAAAADWztKWmJlHSYU0pqyNk-0MBwDEtbYrrPLwTae3iXb78LoOAAAAAAEMAADEtbYrrPLwTae3iXb78LoOAAHGYBeeAAA=` |
| Attachment id | `AAMkADdlNTY5N2I1LTQwNTMtNDQ2OC04MzBlLTU5OGFmZGQ2MzRmYQBGAAAAAADWztKWmJlHSYU0pqyNk-0MBwDEtbYrrPLwTae3iXb78LoOAAAAAAEMAADEtbYrrPLwTae3iXb78LoOAAHGYBeeAAABEgAQANdlswFjNGRFjGrTB3LgbWY=` |
| Existing catalog entry | `00399616-42f7-4f7d-8867-822752b15a46` |
| Sheet | `库存产品` |
| Materialized rows | 8 |
| Price column | `Price` |
| Price values | 24000, 27500, 24000, 27500, 25000, 31800, 27900, 29000 |
| Independent sum | **216700** |
| Content hash (SHA-1) | `e0a7fb8a1b4757b7f6bef882b19cc4588d66246e` |
| Content hash (SHA-256) | `5cd746af2c46dfe3979b1881cb8623dff149958b4cadd97bd69da1e489c9dcb4` |
| Size | 10,249 fetched bytes (10,765 metadata bytes) |
| Last modified | `2026-10-23T06:13:03Z` |

These values are the predeclared expected values from the current catalog and
the earlier independent Graph fetch. Execution re-fetches the current bytes and
reports any changed version; it does not coerce a changed file to this hash.

## Exact Graph operations (read-only)

1. `GET https://graph.microsoft.com/v1.0/me?$select=id,userPrincipalName,mail,displayName`
2. `GET https://graph.microsoft.com/v1.0/me/messages/{messageId}?$select=id,subject,receivedDateTime,hasAttachments`
3. `GET https://graph.microsoft.com/v1.0/me/messages/{messageId}/attachments?$select=id,name,contentType,size`
4. `GET https://graph.microsoft.com/v1.0/me/messages/{messageId}/attachments/{attachmentId}/$value`

The only non-Graph call is the normal OAuth refresh
(`POST https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token`,
`grant_type=refresh_token`) using the existing client and scopes. There are no
`POST`/`PATCH`/`PUT`/`DELETE` Graph calls, no send, no source write, no
permission change and no credential rotation.

## What will be run after authorization

1. resolve/reuse the existing grant through the normal product connection path
   and assert `GET /me` identity matches the table above;
2. re-fetch the attachment bytes with the four read-only Graph calls, record
   provider id/version/SHA-256, and compare the independent sum `216700`;
3. ingest the current bytes through the product (no seeded catalog row, grant or
   supplied rows), then confirm materialization coverage and sheet identity;
4. create an assignment from the materialized sheet and ask the employee to
   retrieve/calculate `Price` without prompt-supplied data; compare with the
   independent Graph read;
5. verify citations bind file, sheet, rows and source version;
6. restart the backend against the same stores, reopen the result, and confirm
   the same version/result;
7. preserve any permission/expiry failure as a failure, with no fallback.

## Part A authorization statement

> “I authorize read-only use of the Microsoft account `rish@brennan.ca`
> (tenant `8899c7a5-b671-4f16-bb48-15d5e78158af`) for the Outlook workbook
> attachment `HARSLE press brake stock price list.xlsx` under the four read-only
> Graph operations above, including normal refresh of the existing grant. No
> writes, sends, permission changes or credential rotation.”

Select: **[ ] A authorized**  **[ ] A declined / changes requested**

---

# B — Outlook send qualification

## Identity and recipient

| Field | Value |
|---|---|
| Mailbox identity | `rish@brennan.ca` (must be rechecked via `GET /me` immediately before send) |
| Application login | `admin@example.com` (not the mailbox identity) |
| Proposed owner-controlled recipient | `rish@brennan.ca` (self-send; replace with another owner-controlled mailbox if preferred) |
| Attachment | **None** |
| Effects | **One** (`max_effects=1`), no automatic resend |

## Frozen payload

Subject:

```text
[Atom qualification] One authorized send 2026-11-01
```

Body (fixed qualification text):

```text
This is the single authorized Outlook qualification message from Atom.

It verifies the real send path, one-use authorization, and Sent Items reconciliation. No action is required.
```

The qualification assignment uses a fresh employee with no email-format
teaching, so the only body transformation is the account's existing stored
signature, which the product appends to agent-initiated sends. The exact final
body, including that signature, has SHA-256:

```text
e9c70d6f532d31d22455a2ecd7ba5cd45ec537a921686b6466f2ce2a3e8bf58d
```

The canonical content hash over
`{to, cc, subject, body, attachments}` (with `to=["rish@brennan.ca"]`,
`cc=[]`, `attachments=[]`) is:

```text
1b0ce7903a14361502bdc9d18d90b7e6d1bb1b93341c8f330a7f4c73326bb183
```

Immediately before transport the product payload is re-hashed; any mismatch
aborts the send. If you require a body without the stored signature, say so;
signature suppression is not currently exposed as a product option and would
need a separate decision.

## Approval window and reconciliation

- **Grant:** one-use, `actions=["outbound"]`,
  `recipients=["rish@brennan.ca"]`, `max_effects=1`.
- **Window:** proposed start `2026-11-01T12:00:00Z`, expiry
  `2026-11-02T12:00:00Z` (24 hours). If you authorize later, the exact start is
  the authorization timestamp and expiry is +24 hours; both are recorded in the
  grant.
- **Sent Items scope:** folder `Sent Items`, exact subject and recipient,
  search window `[start − 5 min, start + 30 min]`; expect exactly **one**
  matching message. A repeat resume/reconcile must add **zero**.
- **Uncertainty:** reconcile the existing durable operation; never create a
  second send to obtain a green result.
- **Provider acceptance** and **recipient delivery** are reported separately.

## What will be run after authorization

1. enable both live-send flags only for this run;
2. recheck `GET /me` mailbox identity, recipient, grant window and revocation;
3. prepare the exact draft, re-hash subject/body/payload, atomically claim the
   durable operation;
4. send through `email.send_outlook` under the one-use grant;
5. record provider acceptance separately, reconcile the exact Sent Items row,
   verify recipient/subject/body, and confirm no second effect after resume;
6. restart, confirm terminal state and zero additional Sent Items rows;
7. restore the default flags and preserve the grant/receipt.

## Part B authorization statement

> “I authorize one live Outlook send from `rish@brennan.ca` to
> `rish@brennan.ca`, with the exact subject/body and payload hashes above, no
> attachment, one effect, and the stated Sent Items reconciliation window. If
> the outcome is uncertain, reconcile the existing operation; do not resend.”

Select: **[ ] B authorized**  **[ ] B declined / changes requested**

Recipient change (if not self-send): `________________________`

---

## Reply format

Reply with one or both of:

```text
A authorized: yes/no
B authorized: yes/no
B recipient: rish@brennan.ca or <other owner-controlled mailbox>
B window: 2026-11-01T12:00:00Z → 2026-11-02T12:00:00Z (or <start/end>)
Statement: <the applicable statement(s) above>
```

No live action will be taken until the selection and statement are present.
