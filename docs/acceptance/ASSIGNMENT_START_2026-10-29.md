# Assignment starting boundary — accepted Chat objective → validated plan — 2026-10-29

Status: **connected guided-start boundary passed.** Preserves `efc4bc9d5` and
its two-domain executor evidence, `44b62a6bb` and `322981bcc`. No live send,
deployment or source writeback.

## What changed

### Accepted objective to assignment

`POST /api/assignments` (authenticated Chat surface, also used by the
Assignments tab) accepts:

- objective text;
- optional employee (`employee_id`) and teaching employee (`agent_id`);
- explicit authorized sources (workbook/document locator, never prompt rows);
- required deliverables (document/presentation/spreadsheet/email draft);
- optional calculation expression and outbound action;
- task context and an optional proposed plan.

The route resolves the authenticated workspace/tenant, employee scope and
applicable teaching through `resolve_artifact_teaching`. Teaching
`needs_context`/`conflict` returns 409 with the targeted clarification rather
than guessing. The accepted objective and teaching revision are persisted in
the assignment plan.

### Capability planner and validation

`core/assignment_planner.py` builds steps over the registered adapter
registry. It does not execute arbitrary code, does not accept model-invented
adapter names, and does not infer permissions from the plan.

Validation before creation checks:

- every adapter is registered;
- every dependency exists and the graph is acyclic;
- explicit workspace scope and at least one authorized source;
- bounded step budget;
- required deliverables reference real steps;
- external steps carry approval or standing authorization;
- outbound steps name a recipient;
- the plan declares acceptance criteria.

A caller-supplied `proposed_steps` plan is validated by the same function;
unknown capabilities become 422, not a new adapter.

### Chat/Activity surface

The existing Assignments tab now includes a **Start durable work** form
(objective, deliverable kind, optional advanced artifact content, calculation,
test recipient and correlation id). The ordinary path uses **Discover an
authorized resource from a scope**; it does not ask for a server path, output
path, formula argument or catalog id. The advanced path accepts a controlled
fixture reference only for isolated tests. The form calls the same
authenticated route and refreshes the durable projection. It does not infer
state from chat text.

### Two natural-language domains

The route starts:

1. a workbook + calculation + document + controlled outbound objective;
2. a document + presentation objective under a different teaching set and
   output kind.

Both use the same route, planner, executor, teaching resolver and adapter
registry. The first waits for a correlated external reply, then approves and
completes; the second completes without an external action.

The connected guided acceptance then starts two materially different
objectives against a real scoped catalog entry and real materialized Parquet
rows:

1. **Sum the total for the scotch parts price list** → `dataset.aggregate`
   (`sum` of `Total` = `85.00 USD`), grounded document, controlled approval,
   grounded outbox body;
2. **Count the records in the scotch parts price list** → `dataset.aggregate`
   (`count` = `3`), grounded presentation.

No prompt rows, developer-authored Python plan or mocked reader/catalog. The
accepted plan carries a path-free typed resource binding.

### Launcher safety

`core/assignment_launcher_guard.py` now requires a disposable directory under
the OS temp root or an explicitly configured scratch root. It refuses
`backend/data`, docs/acceptance, frontend source, release and home paths,
requires the launcher marker for reuse, and deletes only with both the marker
and `ATOM_ASSIGNMENT_BROWSER_WORLD_RESET=1`. The browser server no longer
calls `shutil.rmtree` unconditionally on import.

## Correction pass — review findings

### Server-resolved resources and outputs

Public proposals no longer accept filesystem paths. `core/assignment_resources.py`
resolves a catalog reference through the existing
`resolve_dataset_entry_scoped_sync` / `connected_parquet_path` path, checks
workspace scope, the active connected grant, source version and
materialization coverage, and returns the authoritative local path to the
read adapter. A controlled fixture path is accepted only with
`ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS=1` and a path under the configured
fixture root.

Output paths are allocated server-side under owned artifact storage; a client
supplies a title/kind, never a path.

Negative controls cover another workspace's resource, forged catalog
reference, revoked grant, stale source version, a local file outside the
fixture scope, and output allocation under the authenticated user's store.

### Authority independent of the proposal

The planner no longer unions proposed operation types into
`authorized_actions`. Each adapter now carries trusted metadata (effect class,
required actions, approval requirement, standing-authorization policy), and
validation rejects:

- an external adapter declared `read_only`;
- `action.registry` invoking a concrete write action while declared retrieval;
- caller-invented `standing_authorization`;
- an action outside the accepted source/action scope.

`action.registry` resolves the concrete action before validating its effect.
The route rejects direct public `proposed_steps` unless the controlled
proposal flag is set.

### Deliverable validation

Every required deliverable’s `step_id` must be an actual planned step, the
step may produce only the matching artifact kind, deliverable identities must
be unique, and two deliverables cannot claim one step. Read steps cannot
claim a DOCX deliverable.

### Guided versus explicit setup

The explicit form remains the advanced/controlled setup path. A guided path
(`discover: true` + permitted `source_scope`) lets the route discover an
authorized catalog resource through existing retrieval, gather teaching, and
validate the same plan boundary without the user supplying a server path,
formula argument or correlation id. Unknown content requirements yield a
clarification/pending state rather than generic prose being treated as a
grounded deliverable.

## Connected guided correction — 2026-10-29

### Typed resource-to-reader contract

The plan carries a typed `resource_binding`, not a path:

- catalog/resource identity (`resource_id`, `dataset_name`, `external_id`);
- representation (`parquet_frame` / `xlsx` / `file`);
- original file identity (`original_file_name`) and source kind;
- active source version;
- sheet/entity identity;
- actual physical and numeric columns;
- materialization coverage;
- authenticated access scope (user, workspace, tenant).

Connected materialized datasets are read by `dataset.read` / `dataset.aggregate`
with pandas Parquet over the server-resolved path. `openpyxl` remains only for
an actual authorized workbook representation. `__sheet_row` is preserved on
every row, and formula sidecars are filtered to the matched rows. No XLSX is
manufactured to satisfy an adapter.

Every read re-resolves the binding through
`resolve_dataset_entry_scoped_sync` + `_assert_connected_source_access` +
`_validate_connected_coverage` immediately before reading. A path resolved at
start is not continuing access: a revoked grant or superseded version stops the
read with a durable source-access gap. The executor-level control resolves the
source, starts a durable wait, revokes the grant, resumes, and proves the read
step waits with `source_access_revoked` without reading stale rows.

### Bounded candidate selection

`select_resource_candidates` scores every active catalog entry against the
accepted objective/scope, actual columns and coverage. It never adopts the
first result:

- one justified match → adopt;
- several plausible files/sheets → 409 clarification with candidates;
- explicit sheet → select that sheet;
- required multiple sources → preserve distinct resources;
- no justified match → explicit pending work;
- wrong workspace → 403.

The controls cover a distractor ranked first by recency, the same workbook with
several plausible sheets, an explicit sheet, two required sources, no match,
and a real cross-workspace refusal.

### Grounded artifacts, not generic prose

Generic objective + “authorized source” completion is removed. When content is
missing:

- a validated calculation/aggregate is composed into the artifact from the
  actual previous read/calculation results; or
- the route returns `artifact_content_required` / `outbound_content_required`
  clarification/pending work.

Every saved artifact is checked after rendering: the accepted result value,
actual source reference(s), covered subjects/records, and the teaching format
must all be present. A file opening is not task completion.

The calculated outbound body is composed from the same result and source
evidence; the controlled outbox record contains the value and source, not a
generic placeholder.

### Real connected acceptance

`backend/scripts/assignment_connected_acceptance.py` runs the production route
against an isolated scratch database with:

- an authenticated user/workspace/tenant;
- a real `DatasetEntry` and real Parquet file under the dataset root;
- a real active integration grant;
- teaching for document and presentation output;
- real `dataset.aggregate`, artifact renderers and `__sheet_row` provenance;
- the environment-gated controlled outbox only.

It produces `connected_acceptance.json` plus the saved document/presentation.
The two objectives yield `85.00` and `3`; the sum document includes rows 2, 3
and 4 and `scotch-parts.xlsx`; approval completes the assignment; the outbox
body carries the result and source; rebuilding the executor from durable state
reports both assignments completed.

## Evidence

- `docs/acceptance/evidence/durable_assignment_20261029/connected-guided/`
  — real scoped catalog → real Parquet → validated plan → grounded
  document/presentation, `connected_acceptance.json`, stored artifacts,
  approval/outbox, durable reopen.
- `docs/acceptance/evidence/durable_assignment_20261029/browser-guided/`
  — guided browser run for the same two objectives, approval, completion,
  reload, `playwright-restart.txt`, `status-after-restart.json`.
- `docs/acceptance/evidence/durable_assignment_20261029/browser-explicit/`
  — explicit advanced-form run, kept separate from guided discovery.
- `docs/acceptance/evidence/durable_assignment_20261029/browser-start/`
  — preserved earlier start-boundary evidence.
- `docs/acceptance/evidence/durable_assignment_20261029/` — prior executor
  evidence remains untouched.
- Backend: `tests/test_assignment_routes.py` (guided real catalog, distractor,
  no match, wrong workspace, owned output, teaching, approval, second domain,
  unregistered proposed adapter), `tests/test_assignment_resource_boundary.py`
  (typed binding, real Parquet reader, candidate selection, revoked grant at
  resumed executor read, stale version, forged/cross-workspace resource,
  authority and deliverable controls), `tests/test_assignment_executor.py`,
  `tests/test_assignment_launcher_guard.py`.
- Frontend component: `components/assignments/__tests__/AssignmentPanel.test.tsx`;
  TypeScript compile clean.

## Verification

- Focused backend suite: **126 passed**.
- Assignment component: **3 passed**.
- Guided Playwright start/reload: **1 passed**.
- Guided Playwright after backend restart: **1 passed**.
- Explicit Playwright start/reload: **1 passed**.
- Explicit Playwright after backend restart: **1 passed**.
- Connected acceptance script: **passed** (`85.00`, `3`, both reopened).
- `tsc --noEmit`: clean.

## Boundaries

- Controlled outbox only; no live provider acceptance or recipient delivery.
- The connected acceptance uses a real scoped `DatasetEntry`, real Parquet
  rows, the real resolver/reader and a real active grant row in an isolated
  scratch database. It does not fetch a live OneDrive file; live OAuth remains
  outside this slice.
- The guided deterministic calculator covers explicit `sum`/`count` objectives
  against one materialized source. Compound or unstated calculations produce a
  clarification rather than an invented method.
- The explicit advanced form remains available for controlled fixtures; it is
  not evidence of autonomous discovery. The guided browser evidence and the
  explicit browser evidence are stored separately.
- The planner is a capability planner over registered adapters, not a new
  business workflow engine. It does not grant permissions or invent adapters.
- A production Outlook send still requires a prepared canvas and the existing
  approval path; the start form marks the controlled transport only for
  acceptance.
- No deployment, credential change or source modification.
