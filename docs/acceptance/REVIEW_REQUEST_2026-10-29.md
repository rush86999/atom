# Independent review request — connected guided assignment start

Frozen candidate: `40b3367d9` on `whole-app/successor-f5f`
Preserved start boundary: `44b62a6bb`.
Preserved correction pass: `322981bcc`.
Preserved executor evidence: `efc4bc9d5`.

This pass addresses the connected guided-start review findings: typed
resource-to-reader binding, real Parquet reads with provenance, rechecks before
resumed reads, bounded candidate selection, removal of generic-content
completion, substantive artifact checks, and a real scoped catalog → Parquet →
artifact → approval/outbox acceptance.

Please review read-only; do not restart the owner's runtime or run a live send.

## Scope

1. `POST /api/assignments`, `core/assignment_planner.py` and
   `core/assignment_resources.py`: accepted objective, permitted scope,
   teaching, discovered catalog resources, typed binding, derivation of
   deterministic `sum`/`count`, strict validation and owned output allocation.
2. `core/assignment_executor.py`: `dataset.read` / `dataset.aggregate`, typed
   binding recheck at every read, `__sheet_row` preservation, formula sidecars,
   grounded artifact composition and substantive checks.
3. Guided and explicit browser surfaces: discovery without server paths or
   output paths; advanced explicit form kept separate.
4. Evidence: `docs/acceptance/ASSIGNMENT_START_2026-10-29.md`,
   `docs/acceptance/evidence/durable_assignment_20261029/connected-guided/`,
   `browser-guided/`, and `browser-explicit/`.

## Questions for the reviewer

- Can a public proposal still supply a filesystem path, choose an output
  location, or make a plan step consume a path as resource identity?
- Does every connected read recheck the active grant, workspace, resource
  identity and source version immediately before reading, including a resumed
  read?
- Can discovery adopt the first result or the first sheet by recency/order, or
  collapse several plausible candidates into one?
- Can an artifact complete with only the objective and a generic “authorized
  source” label, or with content that disagrees with the accepted result?
- Is the accepted result, source provenance and teaching actually present in
  the saved artifact and grounded outbox body?
- Does the connected acceptance prove real catalog → real Parquet → correct
  rows/provenance without a mocked reader/catalog or prompt-supplied rows?
- Do guided and explicit evidence remain clearly separated?

## Post-review status

The frozen `40b3367d9` delta was reviewed in
`docs/acceptance/ASSIGNMENT_REVIEW_2026-10-29.md`. Five material findings were
reproduced and repaired in `294fdf0ec`; affected controls pass. The bounded
taught-method job is `de25c5148` and its controlled evidence is in
`docs/acceptance/evidence/durable_assignment_20261029/bounded-taught-job/`.
The prepared package is `13a7f82a2` under
`docs/acceptance/assignment-successor-package-2026-10-29/`.

Live OneDrive guided start and live changed-byte refresh remain blocked by
missing `MICROSOFT_CLIENT_ID`/`MICROSOFT_CLIENT_SECRET` and the disposable-source
authorization. See `docs/acceptance/LIVE_CONNECTED_GATE_2026-10-29.md`.

## Known boundaries

- Controlled outbox only; no live provider acceptance or delivery.
- The connected acceptance uses an isolated scratch database, a generated
  scoped catalog row, a real Parquet file and a real active grant row. It does
  not fetch a live OneDrive file; live OAuth is outside this slice.
- Guided deterministic calculation covers explicit `sum`/`count` objectives
  against one materialized source; compound/unstated calculations clarify.
- The bounded taught job covers one scalar method, one workbook row and one
  wait. It is controlled, not live-connected.
- One worker process per assignment is the verified topology.
- Production Outlook send still requires a prepared canvas and the existing
  approval path.
- Owner teaching working-tree files remain outside the scoped commits and must
  be included in a release checkout.
- No deployment, credential change or source modification.
