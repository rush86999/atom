# Consolidated authorization request — fda4f2dc9

Status: **three separately selectable operations; none authorized.** No
shutdown, deployment, token refresh, external lookup, real send, credential
change or source write occurred.

## Presence-only findings

| Item | Finding |
|---|---|
| App account | `admin@example.com` (application login, **not** proof of mailbox sender identity) |
| Microsoft OAuth | Token record present; `Mail.Send` scope present; access token expired `2026-10-30T04:33Z`; refresh token present |
| OneDrive/Zoho | Present but expired; not used |
| HARSLE dataset | Outlook-ingested `HARSLE press brake stock price list.xlsx`, sheet `库存产品`, 8 rows, hash `e0a7fb8a1b4757b7f6bef882b19cc4588d66246e` |
| HARSLE quantities | `QTY` sum = **8**, so “8 units” is source-supported; 8 rows alone is not the basis |
| HARSLE currency | No currency column exists; `USD` is **not** source-supported and is removed from the draft |
| Source service | PID `19046`, `atom-c912375de`, CWD `atom-releases/c912375de/backend`, DB `atom/backend/data/atom.db`, port `8001`, no supervisor; verification passes |
| `config/pilot_password` | Absent |
| `config/APPROVED` | Absent |
| Send restrictions | Enabled; live send disabled |

## Operation 1 — research qualification (two separate tests)

### 1A. Cross-source retrieval — select `[ ]`

- **Source:** existing read-only Outlook-ingested HARSLE workbook above.
- **Missing fact:** unit `Price` for serial `25206` (FlexBend 170T3200).
- **Scope:** `Serial Number = 25206`; source version `e0a7fb8a1b4757b7f6bef882b19cc4588d66246e`; no date range.
- **Independently checkable expected result:** `31800` in the source price units for QTY `1` (currency not established by the source).
- **Workflow:** assignment row without Price → `external.research` read-only lookup → validated evidence/provenance → calculation → document/email draft. Unknown serial must produce a typed obligation and resume the same assignment after resolution; restart must preserve evidence/result.
- **Limits:** one source, five read-only queries, 10 minutes, no writes/sends/purchases, no new credential.

### 1B. Live external read-only lookup — select `[ ]`

- **Source:** existing connected Microsoft 365 mailbox **or** OneDrive path, owner-selected. Proposed target: the original Outlook message/attachment for the HARSLE workbook, or a mailbox/OneDrive item containing serial `25206`.
- **Missing fact:** the same unit price for serial `25206`, not supplied by the assignment source.
- **Scope:** one owner-approved mailbox UPN or OneDrive drive/path; identifier `25206`; date window `2026-08-01..2026-10-30`; one live query plus one missing-result control.
- **Retrieval record:** source identity (mailbox UPN/drive id), message/attachment id, sender/from, received/modified time, bytes hash, retrieval time and returned excerpt.
- **Independent check:** compare the live evidence with the ingested HARSLE workbook and record agreement or conflict. The predeclared `31800` is not proof by itself; a conflict is preserved, not silently resolved.
- **Missing control:** query `SERIAL-NOT-FOUND-999`; must produce a typed `external_research` obligation, no fabricated value.
- **Conflicting control:** a controlled read-only fixture with two different prices for the same serial; must surface the conflict and require clarification.
- **Use in assignment:** validated evidence → calculation → deliverable; same assignment identity.
- **Limits:** one source, one live lookup plus controls, 10 minutes, read-only; no writes/sends/purchases; no new credential. A successful refresh of the existing Microsoft grant is required.
- **Authorization needed:** allow read-only Graph lookup and token refresh for the approved mailbox/OneDrive scope.

## Operation 2 — real-provider sending qualification

**Select:** `[ ] Authorize real-provider sending qualification`

### Sender identity — unresolved

`admin@example.com` is the application account. The connected mailbox sender
address is **not established** by local metadata. Before approval, the owner
must either:

- supply the actual authorized mailbox UPN, or
- authorize a read-only `/me` identity check after the existing grant refreshes.

The existing `Mail.Send` scope is present, but the access token is expired and
must refresh or be re-consented.

### Prepared payload

- **Recipient:** owner-supplied; not invented.
- **Subject:** `HARSLE press brake stock total — approval draft`
- **Body (verbatim):**

```text
Hello,

The HARSLE press brake stock price list totals 216,700.00 across 8 units.

The attached document records the itemized calculation and its source row. The source does not establish a currency; please confirm if one should be applied.

Regards,
Atom
```

- **Attachment:** `docs/acceptance/evidence/durable_assignment_20261030/successor-package-fda4f2dc9/send-review/harsle-live-price-total-currency-unstated.docx`
- **Attachment SHA-256:** `7b736fb16ca66f9a84a9d41dad49d7d0470d5b904aa3504ddc5a67ee257ff1f6`
- **Attachment size:** 37,082 bytes
- **Content check:** the saved DOCX contains `Currency: unstated by source.`, contains no `USD` claim, and its table carries the QTY-derived total.
- **Recheck:** full path, size, extracted content and SHA-256 immediately before transport.
- **Missing:** sender UPN, recipient, approval window, provider receipt source, reconciliation window.

**After authorization:** exact payload-bound approval → transport → provider
acceptance recorded separately from delivery → reconciliation → restart/
no-duplicate verification. No global send enablement.

## Operation 3 — deployment

**Select:** `[ ] Authorize deployment of fda4f2dc9`

| Item | Value |
|---|---|
| Product | `fda4f2dc9376f20a6e10de6d7d1e55cf16eeffd4` |
| Tag | `assignment-successor-2026-10-30-fda4f2dc9` |
| Product tree | `92924cd8f8f3cffa8e884a9a7fecc5f820f4f5ce8acbba60fdd257975df614fa` |
| Prepared root | `/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-30-fda4f2dc9` |
| Rollback | `901e5d77348e0c7b85b1f1291cbeb0fc50eb2ff0` |
| Kit tree | `5c58bdd36c109b11b14efb6ccf6d8f5410662beb930c7e08a8e2de24bea3ca26` |
| Frontend build | `7Y8qAVXDNHG0Q9YDMKwb4` |
| Duration | ~20–30 minutes plus ~5 minutes recovery |

Needs secure `config/pilot_password`, exact `config/APPROVED` with
`source_shutdown_scope`, and authorization to stop only verified PID `19046`.
The transaction includes quiescent refresh, fresh authenticated work, restart
agreement, atomic receipt, rollback to `901e5d773`, and restoration of the
original source service on failure.

## Owner response

1. Research 1A (internal cross-source): `[ ]`
2. Research 1B (live read-only external): `[ ]` — supply mailbox UPN or OneDrive path.
3. Sending: `[ ]` — supply sender UPN, recipient, window, receipt and reconciliation source.
4. Deployment: `[ ]` — create password file and exact `APPROVED` record.

No operation starts from this request alone.
