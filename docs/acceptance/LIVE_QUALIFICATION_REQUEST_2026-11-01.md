# Concrete live qualification request — 2026-11-01

**Status: executed 2026-11-01.** The owner authorized both operations; Part A
read-only and Part B one-use send ran on `0aa6105e4872` and were verified after
restart at `74464af69f98`. Evidence:
`docs/acceptance/evidence/live_qualification_20261101/`. This document remains
the frozen scope; it is not a self-acceptance.

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

### Verbatim final body — exact bytes

This is the full body that will be placed in the assignment and therefore bound
in the approved operation. It already contains the account's stored signature;
the product will not append a second signature. The authoritative bytes are in
`LIVE_QUALIFICATION_B_BODY.txt` (UTF-8, no trailing newline); the block below is
the same string for review.

~~~text
This is the single authorized Outlook qualification message from Atom.

It verifies the real send path, one-use authorization, and Sent Items reconciliation. No action is required.

</div><div style="font-family:Aptos,Aptos_EmbeddedFont,Aptos_MSFontService,Calibri,Helvetica,sans-serif; font-size:12pt; color:rgb(0,0,0)">Regards,</div><div style="font-family:Aptos,Aptos_EmbeddedFont,Aptos_MSFontService,Calibri,Helvetica,sans-serif; font-size:12pt; color:rgb(0,0,0)"><br></div><div style="font-family:Calibri,Helvetica,sans-serif; font-size:18pt; color:rgb(0,0,0)"><b><i>Rish M.</i></b></div><div style="font-family:Calibri,Helvetica,sans-serif; font-size:18pt; color:rgb(0,0,0)"><b><i>Brennan Machinery Inc.</i></b></div><div style="font-family:&quot;Segoe UI&quot;,sans-serif; font-size:13.5pt; color:rgb(0,0,0)"><span style="color:black"><b><i>Visit Our Web Site</i></b>&nbsp;</span><span style="color:blue"><a href="http://www.brennan.ca/" target="_blank" rel="noopener noreferrer" style="color:blue; margin:0px"><u>www.brennan.ca</u></a></span></div><div style="font-family:Calibri,sans-serif,serif,EmojiFont; font-size:12pt"><span class="spanWithBackgroundColor" style="color:red; background-color:rgb(255,255,255)"><b><i>How am I doing?</i></b></span><span class="spanWithBackgroundColor" style="color:rgb(68,84,106); background-color:rgb(255,255,255)"><b><i>&nbsp;</i></b><a href="https://forms.zohopublic.ca/brennanmachineryinc1/form/Howarewedoing/formperma/TK5qza8iSjh9aFRaFykDnScn0UALNkPgoEYN_hdq3g0" title="https://forms.zohopublic.ca/brennanmachineryinc1/form/Howarewedoing/formperma/TK5qza8iSjh9aFRaFykDnScn0UALNkPgoEYN_hdq3g0"><b><i>Rate&nbsp;my performance</i></b></a><b><i>.</i></b></span></div><hr style="border-width:1px; border-style:none none solid; border-color:currentcolor; display:inline-block; width:98%"><div style="font-family:Aptos,Aptos_EmbeddedFont,Aptos_MSFontService,Calibri,Helvetica,sans-serif; font-size:12pt; color:rgb(0,0,0)"><b>Reclaim your floor space and monetize your idle equipment.</b>&nbsp;</div><div style="font-family:Aptos,Aptos_EmbeddedFont,Aptos_MSFontService,Calibri,Helvetica,sans-serif; font-size:12pt; color:rgb(0,0,0)">Simply reply with your machine specs, and we'll leverage our buyer network to get it sold for you.</div><hr style="border-width:1px; border-style:none none solid; border-color:currentcolor; display:inline-block; width:98%"><div style="font-family:Aptos,Aptos_EmbeddedFont,Aptos_MSFontService,Calibri,Helvetica,sans-serif; font-size:12pt; color:rgb(0,0,0)"><span class="spanWithBackgroundColor" style="background-color:rgb(255,255,255)">All quotes are valid for 15 days only, thank you for understanding.</span></div><div style="font-family:Aptos,Aptos_EmbeddedFont,Aptos_MSFontService,Calibri,Helvetica,sans-serif; font-size:12pt; color:rgb(68,84,106)"><span class="spanWithBackgroundColor" style="background-color:rgb(255,255,255)"><br></span></div></div><div id="appendonsend">
~~~

The exact Graph wire body is `_body_to_html(final_body)`; it is saved byte-for-byte
in `LIVE_QUALIFICATION_B_BODY.html`. A rendered preview is
`LIVE_QUALIFICATION_B_BODY.png`.

### Frozen hashes

| Object | SHA-256 |
|---|---|
| Final body (`LIVE_QUALIFICATION_B_BODY.txt`) | `0b8c96d5aab954cc4b5a879ea95c37b7680a7b0984d877d526294385d8a1e696` |
| Graph wire HTML (`LIVE_QUALIFICATION_B_BODY.html`) | `ef3472ddc5401b8ab700b9545f75193042afc8958c9ec3f0994680cfd9783e67` |
| Canonical content `{to, cc, subject, body, attachments}` | `0610425628b13cb08f7b38309a27a33720dd6b7c675afd626c95482e6323a74e` |
| Subject | `7434a12f5d2e84dfc6d302909ade326198207fd0f4ba8c9a85042cf890dc3f4f` |

Canonical content uses `to=["rish@brennan.ca"]`, `cc=[]`,
`attachments=[]`, and the final body above. If the recipient, signature or body
changes, the payload binding must be regenerated and re-authorized before
sending. The pre-dispatch check recomputes all four hashes; any mismatch aborts
the send.

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
3. prepare the draft from `LIVE_QUALIFICATION_B_BODY.txt` exactly (the body
   already contains the signature, so no second append), re-hash subject, final
   body, wire HTML and canonical payload, then atomically claim the durable
   operation; any mismatch aborts;
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
