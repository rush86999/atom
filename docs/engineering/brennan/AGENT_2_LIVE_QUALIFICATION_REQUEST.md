# Agent 2 live qualification request

Status: **not yet executed**. Prepared only after the controlled Agent 2
suite reached 227+ passing tests. No live Zoho/Microsoft credential, read,
refresh, write or send has been used. The earlier one-use Outlook send
authorization remains exhausted and is not requested here.

## Scope requested

One reviewable, bounded qualification in a sandbox organization and a test
folder/library. Read-only qualification first; one financial write only after
a separate written authority reference is issued.

| Provider | Account / scope | Read | Write requested |
|---|---|---|---|
| Zoho Books | sandbox organization ID (to be named by the owner) | organizations, chart of accounts, vendors/contacts, bills/estimates, one bill readback | one `create_bill`; no payment, void, delete or period close |
| Zoho CRM | same sandbox tenant | one account/contact/deal record | none |
| Zoho Inventory | same sandbox organization | one item and observed stock | none |
| Zoho WorkDrive | one test workspace/folder | page listing, one file metadata/download | none |
| Microsoft 365 / OneDrive | one test drive/site/folder | Graph page listing, one file download | none |
| Outlook | one test mailbox | none required for this request | one draft only; no send |

Exact scopes: Zoho Books/CRM/Inventory/WorkDrive OAuth scopes already required
by the adapters; Microsoft Graph `Files.Read.All` (or the site-specific
`Sites.Selected` grant) and `Mail.ReadWrite` for the draft. The owner names the
organizations, drive/site/library, folder IDs and mailbox before any call.

## Fixture and exact payload

1. **Quote readback (read-only):** Brennan fixture `A 2 x 100`, `B 3 x 50`
   with 5% discount on B only, freight `20`, no tax. Expected total
   **362.50**. The action must read back the provider estimate and compare
   `total`, `currency_code`, customer ID, reference and date.
2. **Supplier bill (one write):**
   - vendor: existing sandbox vendor ID resolved by exact name; no creation
   - external/reference: `ATOM-QA-<date>-001` (owner may replace)
   - document date: within the open sandbox period
   - currency: sandbox organization currency
   - lines: two lines with existing CoA account IDs, exact decimal strings
   - total: independently calculated from the lines; no tax unless the
     sandbox configuration explicitly supplies it
   - payment: none posted; any accompanying payment evidence remains evidence
   - authority reference: issued separately for this one operation
   - durable operation ID: generated before dispatch and recorded in the
     request/approval

## Effect bounds and controls

- At most one provider create per action call and one logical bill per
  reference. A duplicate reference must return `duplicate` without a POST.
- The action performs an exact duplicate sweep over the complete bounded bill
  list before create, verifies the complete chart of accounts, and reads the
  created bill back. A readback mismatch is `conflict`; a lost confirmation is
  `uncertain`; neither is reported as applied.
- No automatic retry. No blind resend after a lost create response.
- Expected remote object: new bill ID, reference/bill number, vendor ID, date,
  currency, total, and organization ID. Record the provider correlation ID.
- Cleanup: void/delete only under a separate explicit authority; this request
  does not authorize destructive cleanup. The test bill remains in the sandbox
  for independent verification.

## Evidence to capture

- Sanitized read receipts with provider, organization/site/drive/folder,
  resource ID, version, retrieved time, coverage and access outcome.
- The exact prepared payload and its SHA-256; authority reference; operation
  ID; approval/authority revision.
- Provider response/correlation ID, created bill ID and authoritative
  `get_bill` readback.
- A changed-remote control: modify the sandbox bill after create and confirm
  the next read reports the changed version/total; do not overwrite it.
- A revocation control: revoke the test grant after read-only qualification
  and confirm the next read is a typed `auth_revoked`/`auth_unavailable`, not
  an empty success. Reconnect only with owner consent.

## Explicitly not requested

- No payment, credit application, journal posting, period close, delete or
  void.
- No Outlook send, reply or calendar invite. Draft only.
- No live customer, price, vendor or account creation.
- No production organization, production mailbox or production SharePoint
  library.
- No reuse of the exhausted one-use Outlook send authorization.

## Acceptance for this request

1. Owner names the sandbox orgs, folder/drive/site/library, mailbox and open
   accounting period.
2. Read-only qualification returns non-empty, typed receipts for each named
   source and a clean revocation result.
3. A separate one-use authority reference is issued for the single bill write.
4. The write returns `applied` only after the authoritative readback matches
   the authorized payload; the duplicate and changed-remote controls pass.
5. Evidence is stored separately from the controlled fixtures; no marketing or
   acceptance status changes until an independent verifier agrees.

## Current blocker

No live Zoho/Microsoft credentials or tokens are available in the base
checkout. This request is a preparation artifact, not a live qualification
claim.
