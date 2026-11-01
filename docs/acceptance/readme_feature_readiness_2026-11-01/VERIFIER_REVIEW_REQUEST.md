# Independent verifier review request — 2026-11-01

**Candidate:** `bec60978b` (runtime code); evidence bundle `76ac5528f`.
**Branch:** `codex/employee-execution-readiness`
**Claimed breadth:** **111/123 = 90.2%** functional claims, frozen denominator.
**Practical scope:** local, single-worker, SQLite scratch world, controlled
outbox, no cloud credential, no live send, no connected-system write.

The verifier remains the acceptance authority. Please treat this as three
grouped submissions; do not pause after each individual test.

## Submission 1 — runtime/enforcement batch

Claims: **ORCH-08, TEAM-01, ASK-03, GOAL-04, WF-05, GOV-04** plus recovery
controls.

Evidence:
- `evidence/claims/orch-team/fleet-pytest.log` — 16 controls, whole-graph depth,
  all-edge cycles, descendant over-limit, foreign scope, no mutation, exactly-one
  contract.
- `evidence/claims/ask-runtime/pytest.log` — 12 controls, runtime gate,
  revocation persistence, re-entry threshold, fail-closed store.
- `evidence/claims/wf-hitl/pytest.log` — 7 controls, payload-bound durable HITL,
  duplicate/fresh-engine resume, crash-after-dispatch.
- `evidence/claims/training-lifecycle/pytest.log` — 4 controls, proposal →
  approval → session/guidance → evidence completion → promotion.
- `evidence/claims/goal-no-progress/pytest.log` — 10 controls, real loop halt and
  strategy-change directive.
- `evidence/claims/orch-team/full-runtime-batch.log` — **229 passed** on the
  earlier runtime source.
- `evidence/campaigns/budget-repair/focused-executor-tests.log` — **55 passed**
  on the final source, including the verifier’s double-credit reproduction,
  repeated/restart/concurrent retries, multiple waits and genuine active-work
  exhaustion.
- `evidence/campaigns/budget-repair/full-runtime-batch.log` — **235 passed** on
  the repaired runtime source.
- `evidence/campaigns/recovery/execution-boundaries.log` — **18 focused**
  recovery/effect controls.
- `evidence/campaigns/recovery/browser-final/browser-recovery.json` — **5/5**
  browser recovery checks (wait/restart/resume, changed source, ambiguity,
  cancellation, duplicate resume) with source-file hashes.

Expected checks: no effect before approval, exactly one after; refusal on wrong
step/execution/payload/row; no resend after crash/uncertainty; duplicate resume
adds nothing; revocation survives restart and new sessions; existing descendants
cannot be pushed over the fleet depth limit.

## Submission 2 — product batch

Claims: **CORE-06, ROUTE-06, ROUTE-03, GRAPH-05, INST-01, GOV-05**.

Evidence:
- `evidence/claims/core06/result.json` — save → chat, replace → chat, delete →
  fail-closed without restart; deleted key not resent.
- `evidence/claims/routing/pytest.log` — local OpenAI-compatible dispatch,
  first public chat, absolute fallback, and two-provider fallback with a
  policy-denied third endpoint receiving zero calls.
- `evidence/claims/graph05/result.json` + `graph-explorer.png` — real browser,
  3 nodes/2 relationships, selected node relationship panel, no page errors.
- `evidence/claims/install01/` — fresh worktree, own venv and `node_modules`,
  `make setup`, empty data root, generated `.env`, documented uvicorn bootstrap,
  real restart, production build; `install-result.json` has login, durable task,
  workflow restart and canvas state.
- `evidence/claims/oidc/pytest.log` — 20 tests against a real controlled local
  IdP, including invalid state/nonce/issuer/signature/audience/token/callback.

Expected checks: no borrowed venv/overlay/absolute `node_modules`; no restart
needed for credential changes; local dispatch with no cloud key; populated graph
not an empty/API-only route; OIDC callback establishes a session and rejects
every invalid path.

## Submission 3 — final integrated candidate

Claimed:
- **111/123** frozen functional claims (inventory and evidence index above).
- Clean install → first successful sample job: **13 seconds** after backend
  start on the clean-install world, result `232990.00`, DOCX
  `e71f40c31211f28a188a04d44b43bfbf69bfd3a0ee06e9a1805aede493152900`.
- Complex teaching sales + grants campaign: **passed**; evidence under
  `evidence/campaigns/teaching-two-domain/` and
  `docs/acceptance/evidence/complex_teaching_20261101/`.
- Genuinely elapsed two-hour assignment: **passed**; started
  `2026-11-01T13:40:04Z`, resumed after the real two-hour mark, source `550.00`
  preserved, one controlled effect, duplicate resume/late reply added none.
  Evidence under `evidence/campaigns/long-run/`.
- Recovery browser: **5/5**; execution-boundary controls: **18 passed**.
- One source/build identity; the serving process reports its source id at
  `/health` and on `X-Atom-Source`.

Preserved boundaries:
- deterministic taught policy is distinct from discretionary model judgment;
- the failed discretionary-model qualification is unchanged;
- controlled effects are distinct from live sending; no second live send was
  attempted;
- the accepted Microsoft read-only and one-use Outlook send qualifications
  remain closed;
- no deployment or connected-system write was performed.

Every `MANIFEST.json` entry is tracked in Git (force-added where global
`*.log`/`*.txt` ignore rules would hide it). Verify the manifest from the
committed tree with the command in `README.md`; the submitted tree reports
**94 entries, 0 untracked, 0 hash/byte mismatches**. Please also verify the
excluded claims in the inventory and the negative controls listed above. A numerical threshold alone
is not the release criterion; the practical teaching, recovery, installation and
first-use gates must hold together on this candidate.
