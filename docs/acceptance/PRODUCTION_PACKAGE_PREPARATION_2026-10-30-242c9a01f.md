# Production package preparation — 2026-10-30-242c9a01f

Status: **successor root prepared; data, required memory, configuration and
rollback verified; cutover blocked on the live source writer and the two owner
inputs. No deployment, approval-file creation, credential change or real send
occurred.**

## Root and identity

- Root: `/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-30-242c9a01f`
- Current: `releases/242c9a01ff9aebb0467ad7a619ea7e4e468f454d`
- Previous/rollback: `releases/901e5d77348e0c7b85b1f1291cbeb0fc50eb2ff0`
- Product tree: `c20bb599ff7ab65913f42cd14a5a93012b6817c93b6b0b5eddfb7c056e24c9b7`
- Frontend build: `K3N6o-mTkpSVJ7sj00FLu`
- Kit tree: `629f369dfc98472e786b0e9ba2499f95958ffdf6abfbd349401e1d220f061de5`

## Data and memory

The successor root was handed off from the live authoritative source with the
SQLite backup API. The prior v4 copy remains preserved under `backups/`.

- Rows: 50 users / 481 dataset entries / 557 goal runs.
- 1,205 artifact/dataset files; 4 current deliverable hashes verified.
- 16,305 operations, **0 binding-digest mismatches**.
- 21 pre-existing missing historical dataset paths recorded with dataset name,
  status, path, referencing assignments and retrieval consequence. None is
  referenced by a current assignment; the 2 referenced datasets resolve.
- Memory: 44,908 documents; 31,415 business facts; 289 experiences; 1,726 chat
  messages; 2,331 Zoho rows; small root tables. 0.86 GiB required, preserving
  more than 20 GiB internal headroom.
- Omitted and preserved at source: 7.23 GiB communications archive and 29.5 GiB
  legacy `default_shared`; their historical context is not searchable in the
  production copy.
- Secrets/BYOK files are mode 600; the existing OAuth token decrypts; provider
  policy is DeepSeek-only; `ATOM_EMAIL_SEND_DISABLED=1` and
  `ATOM_ASSIGNMENT_ALLOW_LIVE_SEND=0`.

## Freshness and quiescence

The logical baseline covers 389 SQLite tables, memory table versions/rows and
461 referenced files. The prepared snapshot was logically current when
captured. The latest check is stale: four telemetry/ingestion tables advanced
(`ingestion_settings`, `knowledge_patterns`, `llm_routing_feedback`,
`rate_usage_records`) and the live source writer pid `19046` still holds the
database/WAL open. This is intentional: a pre-backup check alone would race a
live writer. Stop the writer with operational authorization, refresh the
handoff, then rerun the check before the transaction.

`deploy_release.sh` now:
1. checks freshness and quiescence before backup;
2. rechecks after backup;
3. rechecks after the scoped stop immediately before activation.

A post-backup change refuses before shutdown. A pre-activation change triggers
the verified rollback path. The check is read-only; it never kills or locks a
writer. To proceed, the owner must stop that writer with operational
authorization (or authorize an equivalent quiescence window) and refresh if the
source advanced. The runbook contains the exact refresh commands.

## Rollback qualification

The disposable successor root was started from the new release, then rolled
back to `901e5d773` against the refreshed data:
- candidate `242c9a01f` started healthy;
- `901e5d773` started healthy with the same data directory;
- row counts and artifact hash unchanged;
- 16,305 operations, 0 binding mismatches;
- database not restored; no new interactive approval;
- memory retrieval identical before/after restart.

## Remaining external inputs

1. `config/pilot_password` for the existing admin account.
2. `config/APPROVED` with the exact successor identity.
3. An authorized source-writer quiescence boundary (or a final refresh after
   stopping the writer) immediately before the transaction.

Real-provider sending remains a separate authorization and is not part of this
deployment request.

## Evidence

`docs/acceptance/evidence/durable_assignment_20261030/successor-package-242c9a01f/`
