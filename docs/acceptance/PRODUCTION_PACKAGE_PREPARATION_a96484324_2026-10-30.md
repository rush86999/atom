# Production package preparation — a96484324

Status: **durable production root prepared; data and required memory handed
off; rollback target prepared and actually started in isolation; deployment
still unauthorized.** No deployment, approval-file creation, credential change
or real send occurred.

## Parent and prepared root

- Parent directory: `/Users/rushiparikh/projects/atom-deployments`
- Prepared root: `/Users/rushiparikh/projects/atom-deployments/assignment-successor-2026-10-29-a96484324`
- Current: `releases/a9648432495f4f75f59bf4667cac3cb997d7f229`
- Previous/rollback: `releases/901e5d77348e0c7b85b1f1291cbeb0fc50eb2ff0`
- Frontend build: `9XAkf6w6bcGinpRtHpj8X`
- Product tree: `937d100838300c8ec703f5c8ee164f029acf4ecbe64d6a823bd994fa9070d8e6`

## Authoritative data and consistency boundary

- Authoritative source: `/Users/rushiparikh/projects/atom/backend/data`
- Database snapshot: SQLite backup API, source opened with URI `mode=ro`.
- Source DB SHA-256 before/after copy:
  `19e26d6f5cd7e57659f3eaff08e4bf50cc5bd5b16967b775fb79c3cd4278c0fe`
  (unchanged during the copy; the snapshot is internally consistent).
- Handoff snapshot SHA-256:
  `f0e651bd88116cd4ef2adc7d20c0bbacfc6d3c6a1c4ba1203702904b4f5565be`.
- Logical snapshot fingerprint: 389 tables; row-count/row-value digests stored
  in `run/freshness_baseline.json`. This is the cutover comparison point.
- The source is a live instance. The backup API snapshot is a consistent
  point-in-time copy; any source writes after it are expected and are what the
  cutover freshness gate detects.
- Copied: `atom.db`, `office/`, `sheet_datasets/`, `email_attachments/`,
  BYOK/OAuth files. 1,205 artifact/dataset files copied.
- Rows: 50 users, 481 dataset entries, 557 goal runs.
- Passwords: admin hash preserved; no password reset or generated pilot
  password. `config/pilot_password` is still missing.
- Configuration: `config/secrets.env` copied mode 600; Microsoft key names
  present; OAuth token record decrypts with the copied encryption key;
  DeepSeek-only provider policy; `ATOM_EMAIL_SEND_DISABLED=1`;
  `ATOM_ASSIGNMENT_ALLOW_LIVE_SEND=0`; `LANCEDB_URI_BASE` points at the
  production memory root.

## Schema-aware path migration

- Rewritten only current operational paths:
  `dataset_entries.parquet_path`, current assignment `inputs.path`,
  current `result.artifact.path`, current deliverable `artifact_path`, and
  optional `ingested_documents`/`accounting_documents` file paths.
- Not rewritten: `operations[].operation_binding`, prior results/artifacts,
  receipts/evidence history and provenance. Historical source references remain
  intentionally source-bound.
- Required structures abort on missing table/column or SQL failure; optional
  absent structures are recorded in the handoff manifest.
- Verification: 16,305 operations checked, **0 binding-digest mismatches**;
  4 current deliverables checked, hashes match; 481 dataset paths checked,
  2 assignment-referenced datasets resolve; 21 pre-existing missing historical
  dataset paths are recorded with dataset name, status, path, referencing
  assignments and retrieval consequence. None is referenced by a current
  assignment; they remain visible as retrieval gaps rather than being hidden.
- Representative completed assignment loads with the same ID/status/plan and
  artifact. No pending/waiting assignment exists in this dataset to sample.

## Freshness safeguard

A freshness baseline was created from the handoff snapshot
(`run/freshness_baseline.json`). `check_freshness.py` compares the current
source **logical** SQLite content (389 tables, row counts and row values),
target DB hash, LanceDB table versions/rows and referenced artifact/dataset
file hashes. Raw WAL bytes are deliberately excluded: WAL churn on commits and
checkpoints is not evidence that logical data changed.

`deploy_release.sh` runs this check **before backup or shutdown**; a stale
result refuses the transaction. The check after this handoff is fresh: 0 table
changes, memory unchanged, 461 referenced files checked. If the live source
advances before cutover, the gate will refuse and require a refresh; the final
cutover must therefore be performed against a quiescent or freshly refreshed
source.

The refresh procedure (move the current `data/` to `backups/`, rerun
`prepare_production_data.py`, `prepare_memory_handoff.py`,
`verify_production_handoff.py` and `check_freshness.py`) is in the runbook's
"Cutover freshness and refresh" section. Never refresh after the transaction
has begun shutdown.

## Memory store

Strategy: **read-only logical export of required tables**, not a copy of
mutable source files and not a second writer.

Migrated workspace `default`:

| Table | Rows |
|---|---:|
| documents | 44,908 |
| business_facts | 31,415 |
| agent_experience | 289 |
| chat_messages | 1,726 |
| ingestion_metadata | 4 |
| integration_zoho | 2,331 |
| formula_cards | 0 |

Small root-level tables were also exported (45 documents, 26 chat messages,
7 communications, 5 ingestion rows, 11 turn facts, 2 exchange examples).

Omitted and preserved at source:
- `default/atom_communications.lance` — 7.23 GiB (7.76 GB) communication
  archive. Its historical email/communication context is **not searchable** in
  the production copy.
- `default_shared` — 29.5 GiB (31.68 GB) legacy shared workspace, not used by
  the declared admin workspace. Its historical context is **not searchable**
  in the production copy.

Required export was ~0.86 GiB. Free space before: ~43.1 GiB; after: ~42.3 GiB,
retaining the 20 GiB operational headroom target. ANN/FTS indexes are
rebuildable from exported rows; data rows are preserved.

## Refresh history

Earlier handoffs were preserved under `backups/` and superseded by fresh
snapshots because the live source kept committing:
- `production-data-v2-20261030T012623Z/` — telemetry rows had advanced.
- `production-data-v3-20261030T013017Z/` — the hourly ingestion sync updated
  `ingestion_settings` at 01:27:57, after that snapshot; the freshness gate
  correctly detected the table change.

The current v4 snapshot includes that sync and checks fresh (0 table changes).
Nothing was deleted. The next scheduled ingestion sync is approximately one
hour later, so a cutover must either happen inside that quiet window or refresh
the handoff immediately before the transaction.

Teaching/context and retrieval verification before/after isolated restart:
- persisted teacher lesson `inventory check` remains readable;
- `documents` retrieval returns rows and `get_document_by_id` succeeds;
- results are identical before and after restart.

## Rollback qualification

The production root has a real `previous` link to `901e5d773`, and production
preflight now requires that exact commit/tag/tree before shutdown.

Actual isolated candidate-failure → rollback-start test, re-run against the
refreshed v4 handoff using disposable copies of the production
database/artifacts/memory:
- candidate `a96484324` started healthy;
- rollback selected `901e5d773`;
- `901e5d773` started healthy with the same data directory;
- row counts unchanged (50 users / 481 datasets / 557 runs);
- artifact SHA-256 unchanged (`e59d99141654c8a30047c80e62b19c57d946dfb5fb027d59f236a04e783d19f5`);
- 16,305 operations, 0 binding mismatches after rollback;
- database not restored; no new interactive approval required.

The refreshed v4 evidence is `rollback-before.json`,
`rollback-after-901.json`, `rollback-candidate-start.json` and
`rollback-receipt.json` in the production-package evidence directory.

Authentication was exercised in the same disposable copy with a generated
temporary password (production password untouched): normal login and
`/api/auth/me` succeeded on both `901e5d773` and `a96484324`. The production
root still has no `config/pilot_password`, so the final production login smoke
requires the owner to supply that file. No production rollback occurred.

## Remaining external authorization

1. Owner supplies `config/pilot_password` for the existing admin account.
2. Owner reviews and creates `config/APPROVED` with the exact identity in the
   decision document.
3. Owner authorizes one reversible deployment transaction.

Real-provider sending remains a separate authorization and is not part of this
deployment request.

## Evidence

- Production package evidence:
  `docs/acceptance/evidence/durable_assignment_20261029/production-package-a96484324/`
- Deployment decision:
  `docs/acceptance/DEPLOYMENT_DECISION_a96484324_2026-10-29.md`
- Package manifest:
  `docs/acceptance/assignment-successor-package-2026-10-29-a96484324/assignment_successor_manifest.json`
- Goal ledger:
  `docs/acceptance/PRODUCT_GOAL_LEDGER_2026-10-29.md`
