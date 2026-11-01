# README feature-readiness — integrated 2026-11-01

**Status: 111/123 = 90.2% self-assessed, awaiting independent verifier
acceptance. This is not a release declaration.**

- Candidate source: `a0fce85b0`
- Branch: `codex/employee-execution-readiness`
- Frozen denominator: **123 eligible functional claims** (unchanged)
- Prior accepted local milestone: 99/123 at `29d9075b6` / accepted execution
  milestone at `b7ee7ee22`; both remain preserved.
- No deployment, credential change, live send or new external effect was
  performed. The accepted Microsoft read-only and one-use Outlook send
  qualifications remain closed.

Machine-readable result:
[`CLAIM_INVENTORY.json`](CLAIM_INVENTORY.json) and
[`evidence/claims/INDEX.json`](evidence/claims/INDEX.json).

## 1. The 12 claims added in this batch

| Claim | Result |
|---|---|
| ORCH-08 delegation depth | **verified** — whole proposed graph: longest-path depth, all-edge cycles, existing descendants pushed over the limit, foreign scope, no mutation on refusal; wide shallow fleet allowed (16 fleet controls). |
| TEAM-01 single accountability | **verified** — exactly-one accountable agent; zero/multiple/duplicate forms rejected before the link exists. |
| ASK-03 runtime revocation | **verified** — verified regression blocks the runtime gate immediately; 1 and 19 new successes stay blocked, 20 re-earn; survives restart/new session; unreadable authority fails closed; post-wait assignment resume requires new approval. |
| GOAL-04 no-progress handling | **verified** — real `GenericAgent` loop halts before a third identical dispatch and records `stuck_reason`; the second identical observation adds a strategy-change directive. Not a live-model quality claim. |
| WF-05 policy pause/resume | **verified** — durable HITL row binds execution/step/action and exact payload; zero effects before approval; one after; wrong step/execution, rejected row, payload drift, crash-after-dispatch and fresh-engine/duplicate resume add none. |
| GOV-04 training lifecycle | **verified** — supervisor start creates a pending proposal; approval creates a persisted session with guidance; linked evidence completion promotes to INTERN; duplicate/invalid transitions refused; no evidence raises `InsufficientTrainingEvidenceError`. |
| CORE-06 Settings credentials | **verified** — save → chat, replace → chat, delete → fail-closed, all without restart; deleted key never resent; no key material in logs. |
| ROUTE-06 local endpoint | **verified** — provider registered through the product `/api/local-models` and capability routes; first public chat and absolute fallback reach the controlled local endpoint with no cloud key; unconfigured/uncapable controls dispatch nowhere. |
| ROUTE-03 fallback | **verified** — allowed primary 502 → allowed secondary response with provider provenance; policy-denied third endpoint receives zero calls. The scratch catalog is empty, so provider/model compatibility for the two isolated endpoints is pinned; policy, fallback order, HTTP dispatch and provenance are real. |
| GRAPH-05 graph explorer | **verified** — real browser: 3 nodes, 2 relationships, select `Atlas`, relationship panel shows 2 incoming/outgoing edges, zero page errors. |
| INST-01 pristine bootstrap | **verified** — fresh worktree at `aba2754ec`, own `backend/venv` and `node_modules`, `make setup`, empty data root, generated `.env` with valid SECRET/JWT/Fernet keys, documented uvicorn bootstrap, real restart, production frontend build and browser login. No borrowed venv, overlay or absolute node_modules link. |
| GOV-05 OIDC lifecycle | **verified** — 20 tests against a real controlled local IdP: redirect/state/nonce, callback/token exchange, verified ID-token claims and session; every invalid state/nonce/issuer/signature/audience/token/callback path refused. |

## 2. Runtime failure classes

One reusable acceptance world now lives at
`backend/tests/acceptance/fixtures.py` (file-backed SQLite, foreign keys ON,
explicit tenant/workspace/user/agent rows, replaceable session factory,
observable effect ledger, deterministic fault points).

Full runtime batch at `a0fce85b0`: **229 passed**.

The recovery controls cover crash before dispatch, after dispatch/before receipt
persistence, cancellation, duplicate correlation, reconciliation `applied`,
`not_applied` and `insufficient` without resend, changed artifact invalidation,
stale source revisions and provider-accepted-then-worker-lost uncertainty.
Evidence: [`evidence/campaigns/recovery/execution-boundaries.log`](evidence/campaigns/recovery/execution-boundaries.log)
(**18 focused controls passed**).

## 3. Practical campaigns

| Campaign | State |
|---|---|
| A — complex teaching, transfer and correction | **Passed** in two domains. Sales: taught method/document/expedited/email/expired/conflict through Training; conflict and missing qualification refused; mapping confirmed; active run completed `550.00` Arial 11; revised teaching while waiting left the active snapshot unchanged and new revised work produced `610.00` Calibri 14. Grants: 25-row unfamiliar sheet, `14687.50` Arial 11 active; revised `18650.00` Calibri 14. Wrong-context (grants lesson in a sales run) and expired Courier New were excluded. Agent 1’s browser bundle also covers the expedited exception, clarification, cancellation and a 506.00/676.50 twin. Evidence: `evidence/campaigns/teaching-two-domain/` and `docs/acceptance/evidence/complex_teaching_20261101/`. |
| B — long-running ≥2h | **Passed.** Part 1 waited from `2026-11-01T13:40:04Z`; a real backend restart resumed the same run after the genuine two-hour mark; source `550.00` stayed applied; the correlated reply arrived at `15:43:27Z`; the DOCX rendered (`4a91281abe91d303...`); the controlled send was approved and applied **once**; duplicate resume and a late reply left the outbox at **1 line**. Evidence: `evidence/campaigns/long-run/`. |
| C — ordinary usability | **Passed within scope.** Clean install, production login, upload/discovery, clarification, calculation, DOCX download/reopen, restart/recovery and first-use sample job (`232990.00` in 13s) all exercised through ordinary interfaces. Large-workbook navigation is the 25-row grants run; a multi-hundred-row soak is not claimed. |

### Budget repair found by the long-run

The first resume exposed a real defect: the 15-minute wall budget counted the two-hour durable wait as working time and failed the wait step. The failure is preserved in `evidence/campaigns/long-run/budget-failure-preserved.json`. The repair credits each actual wait interval **once**, keyed by the persisted wait operation id and bounded by the recorded wait start and external response time; no interval is inferred from unrelated steps or extended to a retry. Legacy assignments with an existing `paused_seconds` record the interval as already credited instead of adding it again. The `wait_credits` ledger is written under the existing assignment CAS, so repeated, concurrent and post-restart retries cannot double-credit. A pre-dispatch budget refusal keeps its real attempt count and is admitted for the repair retry; genuine active-work exhaustion still refuses.

Evidence: `evidence/campaigns/budget-repair/repair.json`, `focused-executor-tests.log` (**55 passed**) and `full-runtime-batch.log` (**235 passed**).

The earlier two-hour run remains historical elapsed/resume evidence. Its successful completion is **not** used as proof of correct budget enforcement; the focused repair controls are.

Recovery browser evidence:
[`evidence/campaigns/recovery/browser-final/browser-recovery.json`](evidence/campaigns/recovery/browser-final/browser-recovery.json)
— 5/5: wait/restart/resume, changed source revision, ambiguity, cancellation,
duplicate concurrent resume; source hashes bound to the runtime files at the
candidate source.

### First-use path

On the clean-install world at `a0fce85b0`, after `make setup` and the documented
backend start, `make sample` created/reused *Sample Quote Analyst*, uploaded
`sample-workspace/sample_quote.csv`, recorded two editable lessons, started one
assignment, resolved the single compatible mapping and completed in **13
seconds** with result **232990.00** and a downloadable DOCX
(`e71f40c31211f28a188a04d44b43bfbf69bfd3a0ee06e9a1805aede493152900`).
Evidence: [`evidence/first-use/sample-load-clean-install.json`](evidence/first-use/sample-load-clean-install.json).
No cloud credential, connector or outbound step was used.

## 4. Preserved boundaries

- **Deterministic taught methods** remain the supported capability; the failed
  discretionary-model qualification is unchanged.
- **Autonomous substantive judgment** remains unqualified; human review remains
  required where the accepted evidence says so.
- **Live sending** remains approval-required; the controlled outbox is the only
  transport used here. No second live send was attempted.
- **Registration counts, source inspection and mock-only answers** are not used
  as qualification. Each counted claim has a runtime/API/UI boundary with at
  least one discriminating negative control.
- Failed attempts and superseded drafts are retained in git history and in the
  evidence directories; they are not rewritten into passes.

## 5. Verifier submissions (grouped, three requests)

1. **Runtime/enforcement batch** — ORCH-08, TEAM-01, ASK-03, GOAL-04, WF-05,
   GOV-04, recovery controls. Evidence:
   `evidence/claims/{orch-team,ask-runtime,wf-hitl,training-lifecycle,goal-no-progress}`,
   `evidence/campaigns/recovery/execution-boundaries.log`.
2. **Product batch** — CORE-06, ROUTE-06, ROUTE-03, GRAPH-05, INST-01, GOV-05.
   Evidence: `evidence/claims/{core06,routing,graph05,install01,oidc}`.
3. **Final integrated candidate** — 111/123 plus the completed teaching and
   long-running campaigns on `a0fce85b0`, with the final manifest and hash
   verification.

The verifier remains the acceptance authority; this report does not
self-accept.
