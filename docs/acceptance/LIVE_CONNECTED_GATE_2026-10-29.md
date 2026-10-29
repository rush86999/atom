# Live connected assignment gate — 2026-10-29

Status: **blocked by owner configuration/authorization.** No live Connected
browser start, changed-byte refresh, source writeback or send was attempted.

Integrated candidate: `02822343d` (runtime `9a89471cc`).
The exact combined authorization request and procedures are in
`docs/acceptance/OPERATIONAL_AUTHORIZATION_2026-10-29.md`.

## Current preflight

The approved Microsoft client configuration was restored to the qualification
worktree on 2026-10-29. Presence-only check now reports:

```
configured: true
missing: []
placeholders: []
source: process_environment_after_dotenv
```

Normal token resolution reports `state=valid`, `token_available=true`,
`requires_reconnect=false`. Secret values were not printed or stored.

The live guided gate still cannot use the named workbook: its catalog rows are
`zoho_workdrive`, and the Zoho access token expired on 2026-10-24. No genuine
Microsoft/OneDrive catalog entry for that workbook exists. Cached rows were not
used; no replacement catalog/grant was seeded.

A reproduced access-control defect was fixed: an `active` token row with an
expired `expires_at` was previously treated as current access. It now raises
`source_access_expired`. See `gate-result.json` and the live-connected README.

## What remains blocked

### Guided browser start against the real OneDrive workbook

Required after the configuration is restored:

- use the existing ingested OneDrive workbook/catalog rows;
- do not seed a replacement catalog row, materialization, grant or fake token;
- discover among the actual catalog distractors;
- select the intended sheet or return an honest sheet clarification;
- calculate over the full eligible sheet, not a display page;
- save a source-bound artifact;
- pass controlled outbound approval;
- restart and fresh-read the same result.

Not run. No substitute was created.

### Live changed-byte refresh

The prepared protocol remains `docs/acceptance/CHANGED_SOURCE_REFRESH_PROTOCOL.md`.
It requires one combined authorization covering:

- restoration of the existing approved Microsoft client settings;
- creation/modification of the exact disposable workbook
  `AtomAcceptance/connected-refresh-20261029-0120Z/refresh_probe_f5f_20261029.xlsx`;
- product sync, changed-version materialization, stale-reuse invalidation,
  fresh calculation/assessment, restart and download.

Not run. The production price list was not modified.

## What is verified instead

- Connected guided start on an isolated scratch catalog with real
  `DatasetEntry`, real Parquet rows, real resolver/reader and controlled
  outbox: `docs/acceptance/evidence/durable_assignment_20261029/connected-guided/`.
- Guided browser run for the same two objectives:
  `docs/acceptance/evidence/durable_assignment_20261029/browser-guided/`.
- Explicit advanced-form browser run, kept separate:
  `docs/acceptance/evidence/durable_assignment_20261029/browser-explicit/`.
- Controlled bounded taught-method job:
  `docs/acceptance/evidence/durable_assignment_20261029/bounded-taught-job/`.

These are not live-connected claims.

## Unblock checklist

1. Restore the existing approved `MICROSOFT_CLIENT_ID` and
   `MICROSOFT_CLIENT_SECRET` into the runtime environment (presence/length
   only; never commit or print values).
2. Verify startup preflight reports `configured: true`.
3. Verify a token refresh returns `refreshed`, not `invalid_client`.
4. Grant the exact disposable-source authorization.
5. Run the live guided start and changed-byte protocol without seeding a
   replacement catalog/grant.
