# Consolidated authorization request — fda4f2dc9

Status: **three separately selectable operations; none authorized.** No
shutdown, deployment, real send, credential change or source write occurred.
Approve any subset; approval of one operation does not authorize the others.

## Presence-only configuration check

| Item | Finding |
|---|---|
| Microsoft OAuth token | Present for `admin@example.com`; `Mail.Send` scope present; access token expired `2026-10-30T04:33Z`; refresh token present |
| OneDrive/Zoho tokens | Present but expired; not used by this request |
| HARSLE source dataset | Present: Outlook-ingested `HARSLE press brake stock price list.xlsx`, sheet `库存产品`, 8 rows, hash `e0a7fb8a1b4757b7f6bef882b19cc4588d66246e` |
| Source service | PID `19046`, `atom-c912375de`, CWD `atom-releases/c912375de/backend`, DB `atom/backend/data/atom.db`, port `8001`, no supervisor; verified read-only |
| `config/pilot_password` | Absent |
| `config/APPROVED` | Absent |
| Send restrictions | `ATOM_EMAIL_SEND_DISABLED=1`, `ATOM_ASSIGNMENT_ALLOW_LIVE_SEND=0` |
| Credential values | Not read, printed or stored in this request |

## Operation 1 — bounded research qualification

**Select:** `[ ] Authorize bounded research qualification`

- **Source:** existing read-only Outlook-ingested HARSLE workbook above. No
  live mailbox call is required; no token refresh is required for this option.
- **Missing fact:** unit `Price` for serial `25206` (FlexBend 170T3200).
- **Identifier/date scope:** `Serial Number = 25206`; source version
  `e0a7fb8a1b4757b7f6bef882b19cc4588d66246e`; no date range.
- **Independently checkable expected result:** `31800` USD for QTY `1`;
  calculated total `31800.00`.
- **Workflow:** assignment source row with serial/QTY but no Price →
  `external.research` read-only lookup → validated evidence/provenance →
  calculation → document/email draft. A second run with an unknown serial must
  produce a typed `external_research` obligation; resolving it must resume the
  same assignment and preserve teaching. Restart must preserve evidence and
  the result.
- **Limits:** one source, up to five read-only queries, 10-minute budget, no
  writes/sends/purchases, no new credential.
- **Authorization needed:** permission to use the existing ingested copy for
  read-only retrieval and to record the excerpt in assignment evidence.

## Operation 2 — real-provider sending qualification

**Select:** `[ ] Authorize real-provider sending qualification`

Prepared payload for review:

- **Sender:** `admin@example.com` — owner must confirm this is the intended
  mailbox. Existing `Mail.Send` scope is present; the access token is expired
  and must refresh (or the owner must re-consent if refresh fails).
- **Recipient:** owner-supplied; not invented.
- **Subject:** `HARSLE press brake stock total — approval draft`
- **Body (verbatim):**

```text
Hello,

The HARSLE press brake stock price list totals USD 216,700.00 across 8 units.

The attached document records the itemized calculation and its source row.

Regards,
Atom
```

- **Attachment:** `/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-30-fda4f2dc9/data/office/assignments/default/b83eb105-d9e7-41a5-83e3-a632b15b9ee3/draft-3d906339cbe3/harsle-live-price-total-6c095beb.docx`
- **Attachment SHA-256:** `e59d99141654c8a30047c80e62b19c57d946dfb5fb027d59f236a04e783d19f5`
- **Attachment size:** 37,271 bytes
- **Approval window:** owner-supplied start/end.
- **Provider receipt source:** Graph message id / Sent Items.
- **Reconciliation window:** owner-supplied; ambiguous outcomes are not retried
  until reconciled.

**Workflow after authorization:** exact payload-bound approval → transport →
provider acceptance recorded separately from delivery → reconciliation →
restart/no-duplicate verification. No global send enablement.

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
| Expected duration | ~20–30 minutes plus up to ~5 minutes recovery |

- **Source shutdown scope:** only verified PID `19046`; no supervisor found;
  no other process holds the source DB. `source_service_control.py verify`
  passes; `stop` refuses a PID-only or changed process.
- **Required secure input:** `config/pilot_password` created without posting it
  in chat.
- **Required approval:** `config/APPROVED` with the exact identity and
  `source_shutdown_scope` from `config/source_shutdown_scope.json`.
- **Transaction:** approval → source stopped-check → freshness/quiescence →
  preflight → verified backup → post-backup recheck → scoped stop → stopped
  preflight → pre-activation recheck → start → normal auth → fresh retrieval/
  calculation/artifact → provider policy → send denial → restart/reopen →
  atomic receipt.
- **Failure behavior:** pre-shutdown failures leave services untouched;
  post-shutdown failures roll back code to `901e5d773` and restore the original
  source service command/CWD/environment; data is preserved; the first failed
  boundary is reported. A consumed authorization is not retried.

## Exact files

- Deployment decision: `docs/acceptance/DEPLOYMENT_DECISION_fda4f2dc9_2026-10-30.md`
- Source scope: `docs/acceptance/SOURCE_SERVICE_SHUTDOWN_SCOPE_fda4f2dc9.md`
- Research plan: `docs/acceptance/RESEARCH_SCOPE_DECISION_2026-10-30.md`
- Send qualification: `docs/acceptance/REAL_PROVIDER_SEND_QUALIFICATION_2026-10-29.md`
- Package: `docs/acceptance/assignment-successor-package-2026-10-30-fda4f2dc9/assignment_successor_manifest.json`

## Owner response

Approve by selecting one or more operations and supplying only their missing
inputs:

1. Research: `[ ]` approve; confirm the source/excerpt retention.
2. Sending: `[ ]` approve; sender confirmation, recipient, window, receipt and
   reconciliation source.
3. Deployment: `[ ]` approve; create password file and exact `APPROVED` record.

No operation starts from this request alone.
