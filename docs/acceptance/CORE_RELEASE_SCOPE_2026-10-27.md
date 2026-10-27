# Core release scope — 2026-10-27

This is the current product decision. It **supersedes** the whole-app finish
line in `WHOLE_APP_COMPLETION_2026-10-27.md` for this release. The tested
base remains `f5f3148d2`; the scope change is a successor, not a new product.

## Product promise

> Bring your data, teach an agent how you work, ask it to produce a result,
> review or correct that result, and reuse the work.

The workspace is general: field meanings come from the source or an explicit
mapping, business rules come from teaching and the assignment, and decision
choices belong to the task. Procurement, grants, helpdesk and other domains
run through the same mechanism; they are fixtures and templates, not the
execution engine.

## Exposed surfaces

| Surface | Route | Job |
|---|---|---|
| Chat | `/chat` | Ask questions and direct work. |
| Data | `/documents` | Upload, find and inspect company records. |
| Workspace | `/canvas` | Review and edit deliverables: documents, tables, email drafts and presentations. |
| Agents | `/agents` | Create, teach and correct an agent. |
| Activity | `/goal-runs` (+ `/execution-history`) | See results, failures and unfinished work. |
| Settings | `/settings/*` | Sign-in, providers and data configuration. |
| Approvals | `/approvals` | Safeguard retained for supervisors; not an ordinary work surface. |

## Deferred from this release

Workflow builder/scheduling/unattended automation, marketplace, Dev Studio
and self-healing tools, sales/marketing/finance/support dashboards, Kanban,
calendar, voice, broad connector management, team chat, unified search and
the admin/governance band.

Deferred code, routes and recorded data stay in the installation. They are
not deleted and not rewritten. Direct links render an explicit scope page
(`components/ProductSurface/NotInRelease.tsx`) instead of a working shell.

## One configuration

`backend/core/product_profile.py` is the single capability configuration.
`GET /api/product/profile` serves it to the frontend; the sidebar, dashboard
links and direct-page gate all read that document.

- `ATOM_PRODUCT_PROFILE=core` (default): the table above.
- `ATOM_PRODUCT_PROFILE=full`: restores the wider surface.
- `ATOM_PRODUCT_PROFILE_PATH=/path.json`: deployment overrides.

In the core profile the backend applies worker defaults **before** services
start: `ENABLE_SCHEDULER=false`, `ENABLE_INGESTION_SYNC=false`,
`ATOM_AGENT_EVOLUTION_ENABLED=false`. Explicit operator settings still win.

## Core materials

| Material | Implemented path | State |
|---|---|---|
| Text/CSV/XLSX/XLS | `core/auto_document_ingestion.py` | Existing, exercised by preserved evidence. |
| PDF/DOCX/PPTX | `core/auto_document_ingestion.py` | Parsers exist; PPTX text/tables/notes parser added 2026-10-27. Format-by-format browser evidence is still being collected. |
| Email files (`.eml`) | `_parse_eml` (stdlib RFC 822) | Added 2026-10-27: participants, date, subject, thread headers, plain body and attachment names. A connected mailbox is a separate capability. |
| Email drafts | Canvas `email` type + `api/canvas_email_routes.py` | Existing; sending remains an explicit authorized action. |
| Presentations | `core/office_service.py`, canvas `office_pptx` | Existing create/revise path; verified through unit/api tests, not yet a browser deliverable check. |
| Tables/calculations | `core/dataset_aggregation.py` | `line_total`, `sum` and `count` operations with the same provenance/gap discipline. |

## Domain independence

Rules enforced in the core path:

- No platform-owned decisions. `build_review_result` rejects a review without
  task-supplied `allowed_decisions`, and rejects any decision outside them.
- No fixed record-ID shape. Subjects are plain resolved identities; codes,
  references and names are all valid.
- No quantity × price assumption. `line_total` is one operation; `sum` and
  `count` use a single explicitly named measure (or no measure).
- No business nouns as routing authority. Workbook operations are classified
  by operation shape; missing field roles require clarification or an
  explicit mapping.
- Industry examples live in fixtures/tests, not the execution engine.

Evidence: `backend/tests/test_core_domain_independence.py` runs the same
code over procurement, grant applications and helpdesk records, with
different schemas, subjects and decision sets.

## Training

Training remains a core capability: `/teach` (chat), the canvas Training tab,
teaching-point edit/delete, and scoped lessons (global vs goal). The trained
employee acceptance loop is:

> teach through the UI → unfamiliar task on ordinary materials → inspect the
> deliverable and sources → correct the work → a different task → restart →
> the correction persists without affecting unrelated work.

Storing a lesson is plumbing; the gate is measurable improvement on later
work. That loop needs a configured model and is **not yet claimed** here.

## Current status

See `CORE_RELEASE_LEDGER_2026-10-27.md` for the machine-readable readiness
ledger. Passing today:

- the core surface configuration is served and enforced in the browser
  (`docs/acceptance/evidence/whole_app_20261027/browser-core-surface.json`):
  13 core routes load, 23 deferred routes render the scope page, the sidebar
  shows only core surfaces, no page errors, no 5xx;
- the generic calculation and task-defined decision contracts pass
  domain-independence tests;
- `.eml` import and the PPTX parser pass unit tests.

The production build of this successor passes (139/139 pages).

The shared **table-selection operation** is now implemented and verified:

- the ask is classified before item extraction; columns come from the bound
  sheet's headers and the predicate from a header/value comparison or a
  recorded cell value;
- the exact grants ask returns three rows (`GR-2026-014/021/033`) with
  `Application Ref` and `Requested Amount`, excludes the Withdrawn row, and
  renders a deterministic table (`selection_api_verified.json`);
- renamed-schema and helpdesk twins pass through the same code; the live
  helpdesk ask returns `Ticket`/`Hours` for Open rows and excludes Closed
  (`selection_helpdesk_api.json`);
- the grants selection is unchanged after a real backend restart
  (`selection_after_restart.json`);
- a model-written table never becomes the delivered facts; rejected content
  is private diagnostics only;
- a selection turn completes only with a bound source, resolved columns,
  predicate and row references; an unknown file yields `success=false` with
  no table (`selection_missing_file_guard.json`).

The assessment pipeline is now wired through the existing review machinery:
validated selection rows are adapted into a structured review artifact
(subjects, row references, source identity/version, evidence index), one
generation receives the task-defined decisions + evidence/policy IDs, and the
final table is rendered from validated assessments joined to authoritative
rows. Response, persisted row and fresh history agree on one run, and a
malformed model block delivers the deterministic rows with no accepted
decision.

The trained-employee loop still **fails at judgment quality**: in the one
structurally valid run, GR-2026-033 (4800) was labeled FUND although the
newest taught correction says below 5000 = DECLINE; a later generation emitted
no valid block and was safely rejected. That is recorded as CR-009 (failed)
and CR-014 (partial), not rounded up. The structural pipeline is CR-016
(verified); judgment that reliably follows the current correction remains the
next repair. The earlier fabricated `Roper-011`,
`Tennsmith-001`, `GL001` and `GL002` attempts remain preserved as history.

Not yet claimed: a validated assessment decision table, the full teach →
unfamiliar task → correct → restart loop, format-by-format browser imports
(PDF/DOCX/email/PPTX), and browser deliverable checks for email/presentation.
