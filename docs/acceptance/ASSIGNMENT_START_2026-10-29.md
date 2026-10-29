# Assignment starting boundary — accepted Chat objective → validated plan — 2026-10-29

Status: **local product boundary passed.** Preserves `efc4bc9d5` and its
two-domain executor evidence. No live send, deployment or source writeback.

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
(objective, authorized source, output path, deliverable kind, calculation,
test recipient and correlation id). It calls the same authenticated route and
refreshes the durable projection. It does not infer state from chat text.

### Two natural-language domains

The route test starts:

1. a workbook + calculation + document + controlled outbound objective;
2. a document + presentation objective under a different teaching set and
   output kind.

Both use the same route, planner, executor, teaching resolver and adapter
registry. The first waits for a correlated external reply, then approves and
completes; the second completes without an external action.

### Launcher safety

`core/assignment_launcher_guard.py` now requires a disposable directory under
the OS temp root or an explicitly configured scratch root. It refuses
`backend/data`, docs/acceptance, frontend source, release and home paths,
requires the launcher marker for reuse, and deletes only with both the marker
and `ATOM_ASSIGNMENT_BROWSER_WORLD_RESET=1`. The browser server no longer
calls `shutil.rmtree` unconditionally on import.

## Evidence

- `docs/acceptance/evidence/durable_assignment_20261029/browser-start/`
  — Playwright start-from-form run for both domains, approval, completion and
  reload; `playwright-restart.txt` and `status-after-restart.json` prove the
  completed assignments survive a backend restart.
- `docs/acceptance/evidence/durable_assignment_20261029/` — prior executor
  evidence remains untouched.
- Backend: `tests/test_assignment_routes.py` (start, teaching transfer,
  correlated response, approval, second domain, unregistered proposed
  adapter), `tests/test_assignment_launcher_guard.py`.
- Frontend component: `components/assignments/__tests__/AssignmentPanel.test.tsx`;
  TypeScript compile clean.

## Verification

- Focused backend suite: **97 passed**.
- Assignment component: **3 passed**.
- Playwright start/reload: **1 passed**.
- Playwright after-backend-restart: **1 passed**.
- `tsc --noEmit`: clean.

## Boundaries

- Controlled outbox only; no live provider acceptance or recipient delivery.
- The planner is a capability planner over registered adapters, not a new
  business workflow engine. It does not grant permissions or invent adapters.
- A production Outlook send still requires a prepared canvas and the existing
  approval path; the start form marks the controlled transport only for
  acceptance.
- No deployment, credential change or source modification.
