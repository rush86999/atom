# Original goals 1–9 — current main-web gap reconciliation (read-only)

Date: 2026-11-10. This is a read-only reconciliation, not acceptance. The
canonical denominator is preserved: **143 historical claim identities / 18
goal-map rows**, with no rescore or historical-score change.

## Current identities

- Current remote `main`: `0d5132c2e060a5f2ac338bca143c5e138e607658`
  (PR824 integration; includes PR803 recovery/sessions, PR804 skills,
  PR812/813/815/818/824).
- Pending PR829 head: `08743676d57ec95eeae4351cc58abfdada5c32c3`
  (merge ref `7b46979d0`). It carries the accepted Office/email personal
  delivery **and** the email legacy-draft normalizer repair; the relevant
  normalizer and new test bytes are identical to the reviewed repair
  (`409cede1…` normalizer; test present).
- Pending PR830 head: `e5c75c538e426fbfb563676e5672810ed9946d6a`
  (merge ref `38087c9cd`). It carries the graduation candidate and the
  TrainingPanel race repair; the test file is byte-identical to the reviewed
  repair (`25186c86…`) and contains the deferred-stale control.
- My report branch is from current `main`; no main merge/PR/CI edit.

## Method and limits

- Sources: canonical `APP_GOALS_INDEX.json`, the unchanged 143-claim audit
  (`APP_COMPLETION_REQUIREMENT_AUDIT_2026_11_07.json`), the 2026-11-09 web
  reconciliation, current `origin/main` source, pending 829/830 refs.
- Old source alone is not a rerun reason. Where a later repair is pending, I
  compared relevant bytes/evidence identity (PR829/PR830 above) instead of
  replaying accepted browser/model campaigns.
- No implementation, tests, browser, model/provider, live DB, new world,
  installs, new engine, CI/goal-index edit, or main merge in this slice.
- Broad autonomy/model quality cannot be proved by unit gates; classifications
  below are evidence/source-bound and scope-limited.

Classification: `verified` (original scope fully evidenced), `scope-limited`
(bounded accepted subset; original breadth open), `regression-only`,
`missing`, `contradicted`, `unqualified` (implementation exists but the
required served/general qualification is absent).

## Goal 1–9 reconciliation

| # | Original goal (audit summary) | Strongest current evidence / code consumer | Class | Genuine gap |
|---|---|---|---|---|
| 1 | Setup and ordinary account use | PR803 `c8f8183e8` recovery/session authority; PR804 `20bf3dd93`; PR812 `e2cbff5b9`; auth routes/NextAuth + `pages/login`, settings/recovery pages. SSO candidate `b27551a9c` is **not main**. | scope-limited | Full ordinary recovery/OAuth/SSO; fresh-profile/sign-out and process-restart beyond tested seam; provider identity setup. |
| 2 | BYOK and suitable model selection | Main routing/BYOK commits (`94e9d2128`, `cdc8b9e9b`, `df57dc4fd`, `4d6ad8412`); controlled auto-selection matrix; `core/llm/byok_handler`, cost optimizer/router. | unqualified | Served multi-model quality/automatic selection beyond controlled routes; broad model quality cannot be unit-gated. |
| 3 | Authorized common data and search | Main 756 `343594621` stored export; 781 `8d04a1664` document browser; 813 `24de76a7f`; 815 `6f8c2a480`; 804; packets `document_stored_export_ui_491ac1612`, `document_delete_truth_20261106`, `agent4_upload_open_reload_20261106`, `document_export_authority_20261107`; `api/document_routes.py`, `pages/documents.tsx`. | scope-limited | Joined ordinary upload→search→export→delete→reload lifecycle as one boundary; export/grounding breadth; `/search` capability/deferred state. |
| 4 | Spreadsheet and calculation | Main 813 sheets/coding authority; 801 `89527616e`; sheets service + canvas routes; G5 episodes. | scope-limited | Full-population/reconciliation at ordinary served boundary; restart/export values; general model judgment. |
| 5 | Canvas and editable outputs | Main 813, 800 `5944700f4`, 799 `d542b3862`, 798 `4a4a83089`; accepted Office packet (pending PR829) and email UI packet (`013209bfa`, pending branch/PR829). | scope-limited | Remaining canvas families and ordinary reopen/export beyond the tested DOCX/PPTX/email slices; title/count-only evidence insufficient. |
| 6 | Teaching and reusable agent capability | Main 818 `750f42215` reviewed learning; 816 `310e72aec` authority/expiry; 810; training/playbook/memory consumers. | scope-limited | Served/general consumption after restart; generated-code promotion; MEM-07 remains finite local. |
| 7 | Assessment and unfamiliar work | Main 816; graduation candidate/controls pending PR830 (121 root proof `31ub0c6n`, source-equal); `agent_graduation_service`/`graduation_exam`/decision writer. | unqualified | New held-out/served-domain qualification and general adaptive judgment; broad capability/model judgment not unit-provable. |
| 8 | Durable employee objectives | Main 812 task persistence; 818; goal/task services; accepted bounded wait/progress/restart/reply episodes. | scope-limited | Served/cross-surface/event-order continuation beyond accepted episodes; TASK-WAIT-01 integration is goal 10 (other worker). |
| 9 | Runtime configured-budget enforcement | Main 722 `5b9610b56`; 142 focused + 323 shared controls; `BudgetEnforcementService`, `SpendAggregationService`, `AgentGovernanceService` preflight, `TokenUsage` ledger. | scope-limited | Concurrent spend is **not reserved**: preflight reads spend and returns allowed; spend is recorded after execution. Existing concurrent test covers checks, not spend admission. Failure degradation/PostgreSQL also open. |

No goal is marked `verified` because the original goal-map rows are broader
than the accepted bounded evidence. The 143 historical claims and 18 goal rows
are unchanged; `baseline-verified` claim evidence is historical and is not a
new whole-goal acceptance.

## Highest-impact genuinely unclosed next main-web slice

**Goal 9 — atomic concurrent-spend admission/reservation** (priority 1).

- Exact defect surface: `BudgetEnforcementService.check_budget_before_action_sync`
  (main `backend/core/budget_enforcement_service.py`) computes spend via
  `SpendAggregationService.update_tenant_spend(..., persist=False)` and returns
  `allowed` without reserving. `agent_execution_service` records spend after
  execution; `TokenUsage.cost_usd` is the ledger the preflight reads.
- Triggers/callers: `AgentGovernanceService._check_budget_sync/_async`
  (`agent_governance_service.py` ~786/805), `AtomMetaAgent._check_budget_before_react`
  (~1996), `GenericAgent` (~1368), and MCP/agent action admission.
- Existing mechanism: configured `TenantSetting['billing']` limit/mode,
  `SpendAggregationService`, `TokenUsage`/ACU ledger, budget refusal policy.
  No new authority, provider, table, or live spend is required for the test.
- Failure-first acceptance (proposed, not executed here): scratch SQLite,
  tenant limit `$100`, current `$95` via `TokenUsage`, hard-stop; run 2 (or 10)
  concurrent authorized action admissions that each insert a `$10` spend row
  after the check. Current code admits all at `$95` and total spend exceeds
  `$100`. The fixed path must admit at most the affordable count (or none) and
  keep ledger+reservation <= limit, with release/reconcile on failure. No
  provider/model/live dollar spend.
- Do not: relax enforcement modes, skip/xfail, add a parallel budget engine, or
  claim PostgreSQL/concurrency qualification from SQLite alone.

Runner-up user-facing slice: **Goal 3 joined ordinary document lifecycle**
(upload → search → export → delete → reload as one same-document boundary;
individual piece packets exist, the joined boundary is unproven). Goal 1
SSO/recovery is third but its remaining SSO leg needs a controlled issuer /
owner authority, so it is not the no-provider slice.

## Not next / owned elsewhere

- Goals 10–18 and the security fix are owned by another native worker; do not
  duplicate.
- ORACLE-01 whole-app mutation, served model quality, live providers,
  PostgreSQL/soak, performance/marketing, compatibility/mobile: not finite
  no-provider slices; require owner/environment authority.

## Non-claims

This report does not accept the app, change historical scores, or prove broad
autonomy/model quality. It records current source/evidence identity and a
small proposed queue for root decision.
