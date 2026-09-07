# File Update Pipeline — Administrator Guide

How connected file storage (WorkDrive, Google Drive, OneDrive, Dropbox, Box)
stays current for agents, how to enable real-time updates, and how to
troubleshoot the pipeline.

**Last Updated:** September 2026

---

## How file updates reach agents

There are three paths. They compose — enable all three.

| Path | Trigger | Freshness | Setup needed |
|------|---------|-----------|--------------|
| **Push** (real-time) | A webhook fires the moment a file is edited | Seconds to ~1 minute | Env secret + webhook registration (below) |
| **Pull** (hourly) | The scheduled sync walk | Up to one sync cycle (`sync_frequency_minutes`, default 60) | None — automatic |
| **Read-through** | An agent opens the file at answer time ("open the price list") | Always current | None |

The pull path also detects: content changes (hash), extraction-improvement
re-processing (automatic after upgrades), and truncated/partial writes
(self-healing on the next pass).

---

## Enable real-time push updates

Push uses per-provider webhook secrets, stored as backend environment
variables. **Fail-closed**: if a secret is unset, that provider's webhook
endpoint rejects every request with 401 (the hourly pull still works).

### 1. Set the secret(s) on the backend

```bash
# backend/.env — set only the apps you use
WORKDRIVE_WEBHOOK_SECRET=<random string>
GDRIVE_WEBHOOK_SECRET=<random string>
ONEDRIVE_WEBHOOK_SECRET=<random string>
DROPBOX_WEBHOOK_SECRET=<random string>
BOX_WEBHOOK_SECRET=<random string>
```

Then restart the backend (`scripts/restart_backend.sh`).

### 2. Register the webhook in each app's admin

The endpoint URL is always
`https://<your-atom-host>/api/webhooks/storage/<provider>?token=<the same secret>`

| App | Where to register | Events to select |
|-----|-------------------|------------------|
| **Zoho WorkDrive** | Custom Apps → Webhooks → Create New Webhook | File edited / created on the team folder(s) agents read |
| **Google Drive** | Drive API push channel (or via your Google Cloud project) | Changes to watched folders |
| **OneDrive / SharePoint** | Microsoft Graph subscription (`changeNotifications`) | Drive item changes |
| **Dropbox** | App console → Webhooks → endpoint URL | (Dropbox pings on any change; Atom re-walks) |
| **Box** | Dev console → your app → Webhooks | `FILE.UPLOADED`, `FILE.PREVIEWED`… — use `FILE.UPLOADED` + edit events |

WorkDrive puts the auth token in the endpoint URL (`?token=...`); other apps
may send it as a Bearer header — both are accepted.

### 3. Verify

```bash
# wrong token must be rejected (fail-closed)
curl -s -X POST "https://<host>/api/webhooks/storage/zoho_workdrive?token=wrong" \
  -H "Content-Type: application/json" -d '{}' -w "%{http_code}\n"
# -> 401

# edit a file in the connected storage app, then confirm within a minute:
#   backend log shows "workdrive webhook: refreshed <file> -> ingested"
#   (or "unchanged" if the edit did not change the extracted text)
```

---

## What each status means

| Message | Meaning | Action |
|---------|---------|--------|
| `ingested` | New or changed content was stored | None |
| `unchanged` | The extracted text is byte-identical to what is already stored (e.g. a save with no edits) | None — this is correct behavior |
| `write_failed (…)` | The store **rejected** the write (disk, schema, embedding outage) | Check backend logs; retry after fixing |
| `content_mode_hybrid` skipped | The integration is in index-only mode | Ingest on demand ("open this file"), or switch the integration to full-content mode |

---

## Freshness guarantees for agents

- Every stored file copy is stamped with its **ingestion date**. When an
  agent quotes a figure from a file, the evidence carries that date and the
  agent is instructed to cite it ("$14,145 — per the price list as ingested
  2026-09-04").
- **"Open the file" is always current**: when a user asks the agent to open
  a file, it is downloaded live at answer time, not served from the cache.
- For pricing and quoting decisions, the recommended user phrasing is
  *"open the price list and give me the current price of X"* — this forces
  the live read path.

---

## Onboarding a new business or storage app

- **New business, supported app:** connect the app (OAuth) → set the webhook
  secret → register the webhook URL in that app's admin. Nothing else.
- **New storage app (developer work):** implement its connector's
  `ingest_file_to_memory` + `full_sync` (existing examples:
  `integrations/box_service.py`, `integrations/dropbox_service.py`), add one
  payload parser + one entry in
  `integrations/storage_change_events.py`, and add its secret env to
  `_STORAGE_WEBHOOK_SECRET_ENVS` in `api/webhook_routes.py`. The ingestion
  funnel, update detection, structured extraction, and agent tooling are
  shared and require no per-business changes.

---

## Troubleshooting

- **401 on the webhook endpoint** — secret mismatch or unset. Compare the
  `token` in the registered URL with the backend env var exactly.
- **Edits not appearing** — check the backend log for
  `workdrive webhook: refreshed …` / `Ingested …`; if absent, the webhook
  never fired (re-check registration and events). If present with
  `unchanged`, the edit did not change extractable content.
- **Slow re-ingest of a huge workbook** — large files are chunked and
  embedded (~3.4k chunks ≈ 9 minutes on contended hardware). Avoid running
  multiple full syncs simultaneously.
- **Old values still quoted by an agent** — the evidence carries its
  ingestion date by design; ask the agent to *"re-open the file and confirm
  the current value"* (live read).
