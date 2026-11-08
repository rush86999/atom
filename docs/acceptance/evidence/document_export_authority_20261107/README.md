# Document export authority — strict scope and freshness repair

**Branch:** `codex/document-stored-export-20261107`

**Base main:** `cf5e981917bc31809ca9e8824a2363bdbc9c8f68`

**Predecessor source (withheld):** `11a50ce23ff0731162daa00aaa751cdbc24a9f68`

**Permanent leading probe:** `605d1c767175a1d33a371bb13e9841de5650ff74`

**Actual source:** `df845d83d15487b176f880682ac9d5740c676d02`

**Runtime tree:** only `backend/api/document_routes.py`, the existing export
tests and the new leading probe changed. No frontend/API family, router, store,
tenant model or trust flag was added.

## Root negative preserved

At `11a50ce23`, the permanent probe
`backend/tests/test_lead_document_export_authority.py` produced **3 failed,
1 passed** (actual exit 1):

- indexed metadata workspace conflict → wrongly **200** authoritative;
- indexed metadata tenant conflict → wrongly **200** authoritative;
- empty/unknown freshness (`""`) → wrongly **200** authoritative;
- matching exact scope/revision → **200** valid twin.

Raw evidence: `predecessor-root-negative.log`,
`predecessor-root-negative.spec.json`,
`predecessor-root-negative.exit.json`.

The earlier separate probe that used freshness `None` and an invalid NOT NULL
fixture remains preserved separately and is **not** treated as a product bug.

## Repair

- Indexed/vector document row identity, `pg_document_id`, and present
  workspace/tenant scope must agree with the authoritative SQL row and request
  scope before any body is produced.
- The existing Personal-Edition NULL/default policy is preserved by comparing
  only values actually present on both sides. A NULL/legacy SQL tenant is
  absence, not contradiction.
- Only an explicit SQL `freshness_status='fresh'` row is authoritative.
  `removed` remains 404; empty/NULL/unknown/revoked/pending/stale/outdated/
  superseded all fail closed with 409 `DOCUMENT_NOT_CURRENT`.
- Manual/opaque exact revisions still bind through the existing
  `current_extraction_revision` matcher.
- Genuine manual/vector-only legacy rows without any SQL/index binding remain
  explicit `snapshot_only` + `source_version_status=unknown`, never labelled
  authoritative/fresh.
- Manual SQL row with no version remains snapshot-only; automated SQL row with
  no version remains fail-closed `DOCUMENT_IDENTITY_UNVERIFIABLE`.
- No new storage/router/tenant model/trust flag, no search/profile broadening,
  no original-binary claim. UI Download control unchanged.

## Executed checks

All pytest went through
`/private/tmp/atom-agent-cli/run_bounded_test_gate.py --profile bounded` with a
fresh unique scratch SQLite/Lance/data/office/output/basetemp, `TESTING=1` and a
synthetic `SECRET_KEY`. No live DB/model/provider/browser/install/deploy.

| Gate | Result | Artifact |
|---|---|---|
| Leading 4 + existing 26 export controls + expanded freshness matrix | **34 passed**, exit 0 | `backend-export-34.log`, `backend-export-34.exit.txt` |
| Existing ingestion/parser/scope/search neighborhood | **99 passed**, exit 0 | `backend-neighborhood-99.log`, `backend-neighborhood-99.exit.txt` |
| Python compile | **exit 0** | `pycompile.log`, `pycompile.exit.txt` |

The 34-control gate retains the normal upload/open/export, full >20k
non-truncation, manual opaque, manual snapshot-only, vector-only legacy,
automated missing-binding, contradictory revision, old extractor, foreign
workspace, removed/stale, header safety, format/path refusal and oversize
controls. The expanded matrix covers empty/unknown/revoked/pending freshness and
the exact workspace/tenant conflict cases.

## Boundaries

- This is a bounded local fix; not whole-app, whole-ORACLE, PostgreSQL,
  multi-worker or deployment acceptance.
- No file paths, source URLs, private metadata or original bytes are exported;
  JSON provenance remains allowlisted and body/source/text digests stay
  distinct.
- Root retains independent review, PR/CI and merge. No self-acceptance.
