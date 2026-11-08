# Agents run canonical URL + one-hop transport classification

**STATUS: PREPARED — NOT EXECUTED. Root owns review and the next ordinary UI
episode. This packet does not claim the old episode passed or that the UI is
fully qualified.**

## Root negative preserved

Root ran the ordinary source-answer UI episode at frozen
`0bb9318313bf5dbae8753c3a20e82bd46c30929c`. The retained scenario is **overall FAIL** and stays that way:

- only `single_run_post` failed; all other `source_answer_verified` business
  checks passed (HTTP 200, same execution, job success, outcome success,
  `tasks.create` step, default Oracle verified, one answer POST, no advance);
- the run stopped before the final UI/idempotence steps, so those controls
  were not reached;
- one job (`c262a73e-df9f-4cf2-9840-9203a92aa978`), one execution
  (`15e48c9d-759d-4d67-9fcd-cd7ba40338ef`) and one task (`4e192bf5-cc76-4d2a-bdb1-30e11e6e3219`) were confirmed by
  root's read-only DB read;
- the retained `shim_capture.jsonl` has exactly **3**
  provider calls. No correlation/HITL id or Authorization header is in that
  capture.

The retained world and capture were only read, never rebuilt, reused, deleted
or regenerated.

## Diagnosis

The retained server log shows the real transport cause:

```text
POST /api/agents/<id>/run/ -> 307 Temporary Redirect
POST /api/agents/<id>/run  -> 200 OK
```

The normal Agents page called `${API_BASE}/api/agents/<id>/run/`; the backend
canonical route is `@router.post("/{agent_id}/run")` at
`backend/api/agent_routes.py:669`, with no explicit trailing-slash alias. The
307 is FastAPI/Starlette automatic `redirect_slashes`, **not a second logical
admission**. Playwright recorded both POST request events, so the old harness
counted 2 raw run posts. The access log does not print the Location header; the
redirected `/run` request and the two raw paths prove the target. No foreign
origin or arbitrary redirect was observed.

## Fix

- `frontend-nextjs/pages/agents/index.tsx` now calls the canonical `/run`
  URL; the unnecessary 307 is removed. `AgentStudio.tsx` already used `/run`.
- `frontend-nextjs/tests/pages/agents-information-job.test.tsx` now matches the
  exact canonical path, asserts POST + same `Authorization`/`Content-Type` +
  the same objective body, and asserts no `/run/` call. The role/recovery/
  source positive/negative cases remain.
- `scripts/acceptance/browser_agent_source_answer.py` records each run
  request's safe identity (method, origin, exact path, body SHA-256, operation
  id, unique chain node id) and the response status/Location, then counts
  **logical** admissions. One validated 307/308 same-origin/same-agent/
  same-body/same-operation hop is one intent; two independent non-redirect 2xx
  admissions, a foreign origin, a changed agent/path/body/operation or a
  non-307/308 redirect still refuse. Raw paths/statuses and the scoped
  job/execution stay in the scenario details.
- Six pure classifier twins and the existing frontend contract tests cover the
  positive and negative cases.

The fix does **not** change the backend route, role, access/authority checks,
reviewer CAS, current-actor authority, source version, namespace behavior or
the Goal utility driver. Those files are byte-identical to `0bb9318313bf5dbae8753c3a20e82bd46c30929c`
(`fix-scope.json`).

## Evidence

| Item | Result | Artifact |
|---|---|---|
| Retained root scenario | **FAIL**, only `single_run_post` | `root-negative-scenario-excerpt.json` |
| Server 307 chain | `/run/` 307 -> `/run` 200 | `root-negative-server-307-excerpt.log`, `root-negative-transport.json` |
| Provider shim calls | **3** | `root-negative-shim-calls.json` |
| Runtime milestone | one job/execution/task; business step passed | `root-negative-runtime-milestones.json` |
| Retained-chain classification | one logical admission (1 hop) | `root-negative-classification.json` |
| Two-independent admission twin | refuted (2 logical) | same artifact / classifier tests |
| Source-answer preflight at `fcf91bdd518a39a579ff64f041782572a0cea7ce` | ok, 9/9 files, 55/55 fixtures | `preflight-source.json`, `preflight-source.log` |
| Goal preflight at `fcf91bdd518a39a579ff64f041782572a0cea7ce` | ok, 13/13 files, 55/55 fixtures | `preflight-goal.json`, `preflight-goal.log` |
| Harness classifier tests | 11 passed | `harness-classifier-tests.log` |
| Frontend run/contract tests | 2 suites, 38 passed | `frontend-agents-run-tests.log` |

Canonical per-file source SHA-256: `ac3c86947747dec83732e3cdb99f3628418916daa14724287b861cf3f06ac559`. Per-file Git blob/SHA-256
identities are in `source_identity.json`. The fix commit is `fcf91bdd518a39a579ff64f041782572a0cea7ce`; the old
branch `codex/task-wait-source-ui-integration-20261107` remains at `0bb9318313bf5dbae8753c3a20e82bd46c30929c`.

## Non-claims

No browser, world, server, frontend, model/provider, live DB, install,
download or deploy was used in this preparation. The old packet is not
rewritten or labelled PASS; the failure is not labelled a product resend or
model failure; the business-step milestone is not a full UI pass or Goal
completion. Root runs the next fresh ordinary episode after review.

## Sanitization

Only controlled objective/method/path/op identities, statuses, model labels
and the public job/execution/task IDs are retained. No Authorization header,
bearer token, cookie, password value, JWT or raw environment was committed. The
root spec contains only the CLI flag `--provision-admin-password`, not a
password value.
