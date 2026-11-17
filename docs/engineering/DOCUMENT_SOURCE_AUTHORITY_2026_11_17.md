# Document source authority and derived-data lifecycle — 2026-11-17

Status at product qualification (pre-merge): independently verified locally;
publication and exact-head CI were pending.
Product source: `0249f3eaaabf50db1b022d96a6ee7fb2b58e5f3b`.
This is bounded document/API evidence, not whole Goal 3 or app readiness.
The original 143 claims / 18 goals and `app_complete: false` are unchanged.

## Release status

PR [#978](https://github.com/rush86999/atom/pull/978) merged as
`02c9b16744e4fc9cfe7c81dce2ebf82cac7bf909` after all 15 exact-head checks
passed. Root independently fetched the actual merge and verified its tree and
single parent. Post-merge main Docker succeeded; CI is still running at this evidence
cut, so no full post-merge green is claimed. Later source-bound browser and restart
evidence is recorded [separately](DOCUMENT_FORMAT_BROWSER_RESTART_2026_11_17.md).

## User-visible behavior

Authorized document reads and search use the authenticated workspace. SQL
freshness tombstones govern the vector mirror: a removed, stale, outdated or
superseded source cannot reappear through a stale vector copy, cached listing,
chunk read or grep. An unreadable authority store withholds the affected
content; it does not prove absence. Legacy vector-only documents remain
readable when authoritative queries succeed and find no source row.

Deleting a document also revokes its automatically derived sheet datasets.
Source-document identity is persisted; independently saved datasets, other
sources with identical bytes, and foreign workspaces are preserved. Legacy
upload matching uses exact byte identity only where no different document
already owns the derivative. Filename equality never authorizes deletion.
Deletion receipts include the derived effect and retain unknown/partial
outcomes rather than claiming verified removal. Durable tombstones prevent
queued materialization from resurrecting a removed source.

A source-status read failure, including a missing authority table, withholds
linked derivatives and marks affected scans incomplete. A successfully queried
empty source table remains distinct from failure. Unlinked independent data
remains usable. This prevents incomplete catalog scans from supporting a
false assertion that no matching value exists.

Connector ingestion computes lineage from the actual durable document id.
Existing bare and source-prefixed identities remain discoverable and are
updated in place; the repair does not re-key stored files. Workspace overrides
resolve one scoped handler before both lookup and write. An unavailable
scoped handler returns an error before materialization; it never falls back
to another workspace's store.

## Independent verification

At the clean product source above, root ran **162 tests, all passed** across
these complete files:

- `tests/test_document_lineage_upgrade.py`
- `tests/test_document_derived_dataset_lineage.py`
- `tests/core/test_knowledge_vfs_scope_freshness.py`
- `tests/test_document_connector_lineage.py`
- `tests/test_noop_completion_authority.py`
- `tests/test_document_delete_truth.py`
- `tests/test_document_joined_lifecycle.py`
- `tests/test_assignment_resource_boundary.py`

The authenticated public-API harness
`backend/scripts/documents_common_formats_public_api_acceptance.py` also
passed with one synthetic DOCX, PDF and CSV, real JWTs for two users in
separate workspaces, real parsers/SQLite/LanceDB/Parquet, and cached local
FastEmbed embeddings (384 dimensions). It verifies scoped upload/open/search,
stored-text export, deletion/readback and refusal of stale references. For
CSV it verifies an active derivative/value hit/row before deletion, revoked
resolution/no hit/no row afterward, and an unrelated same-filename peer that
remains active. No generative model or paid-provider request was used.

Run from `backend/` with dependencies already installed:

```sh
PYTHONPATH="$PWD" PYTHON_DOTENV_DISABLED=1 HF_HUB_OFFLINE=1   python scripts/documents_common_formats_public_api_acceptance.py   --scratch /absolute/path/to/a/new/empty/scratch-directory
```

The harness refuses protected or nonempty scratch destinations before creating
its database. It sets isolated test paths before app imports. An uncached
embedding model is not a semantic retrieval pass; inspect the result's
retrieval status rather than assuming availability.

The final native worker also ran the exact promoted document CI batch:
**43 passed**, and CI lane-preservation contracts: **628 passed**. All prior
CI selections and gates remain; the new step selects complete regression
files. These are local results, not GitHub-hosted CI acceptance.

## Existing installations

The nullable `DatasetEntry.source_document_id` column is added by SQLite
startup drift repair and by guarded Alembic revision
`20261117_dataset_entry_lineage` for managed existing databases. The migration
preserves old rows, the version constraint and existing indexes, adds the
lineage index, and is safe when the table/column already exists or the table
is absent. Fresh installations retain their normal schema-creation path.
Legacy rows are not assigned guessed document lineage.

Nine real scratch SQLite upgrade tests cover preservation, partial index
repair, idempotence, fresh/absent-table paths and downgrade/re-upgrade.
PostgreSQL coverage here is static dialect DDL inspection only; no real
PostgreSQL upgrade/runtime acceptance is claimed.

## Retained failures and remaining acceptance

Root initially reproduced fresh-vector resurrection of SQL tombstones and
readable vector-only removal markers; those counterexamples were preserved
and then refused by the repaired point-read boundary with readable owner
controls. Review additionally found and corrected unreadable-authority
fail-open behavior, collateral revocation of an independently linked
same-byte file, a connector bytes-versus-text identity crash, legacy identity
re-keying, and workspace-override fallback to the default store.

Broader native runs retained failures and paired them against their named
unchanged baselines, including absence-guard wording and system-interpreter
FastEmbed availability. They are not converted into passing results. The
independent 162-test run uses the cached working interpreter and has no
failures or skips.

This evidence is TestClient/public API, not an ordinary-browser multi-format
journey, live WorkDrive, original-binary download, process restart, parser
variant breadth, real-model answer quality, PostgreSQL runtime or whole Goal
3/4 acceptance. Later [browser/restart evidence](DOCUMENT_FORMAT_BROWSER_RESTART_2026_11_17.md)
retains its own runtime source and scope. Broader gaps remain in the
[current goal map](CURRENT_GOAL_MAP_2026_11_17.md).
