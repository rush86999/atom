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
  (unchanged; not provisional).
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
  dataset paths are recorded, not caused by this handoff.
- Representative completed assignment loads with the same ID/status/plan and
  artifact. No pending/waiting assignment exists in this dataset to sample.

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
- `default/atom_communications.lance` — 7.76 GiB communication archive, not
  required for document/assignment retrieval.
- `default_shared` — 31.68 GiB legacy shared workspace, not used by the
  declared admin workspace.

Required export was ~0.92 GiB. Free space before: ~52.5 GiB; after: ~51.5 GiB,
retaining the 20 GiB operational headroom target. ANN/FTS indexes are
rebuildable from exported rows; data rows are preserved.

Teaching/context and retrieval verification before/after isolated restart:
- persisted teacher lesson `inventory check` remains readable;
- `documents` retrieval returns rows and `get_document_by_id` succeeds;
- results are identical before and after restart.

## Rollback qualification

The production root has a real `previous` link to `901e5d773`, and production
preflight now requires that exact commit/tag/tree before shutdown.

Actual isolated candidate-failure → rollback-start test, using disposable
copies of the production database/artifacts/memory:
- candidate `a96484324` started healthy;
- rollback selected `901e5d773`;
- `901e5d773` started healthy with the same data directory;
- row counts unchanged (50 users / 481 datasets / 557 runs);
- artifact SHA-256 unchanged (`e59d99141654c8a30047c80e62b19c57d946dfb5fb027d59f236a04e783d19f5`);
- 16,305 operations, 0 binding mismatches after rollback;
- database not restored; no new interactive approval required.

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
