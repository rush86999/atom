# Goal Completion Delta — 2026-11-06

Owned reconciliation by Agent2 (OpenCodeGo / DeepSeek V4.1 Flash).

This document reconciles the canonical **143-claim** README baseline
(**123 functional + 20 separately tracked**) against the current merged and
submitted evidence at `origin/main` `248a2329623b433e68104c4d89d2965683d81013`
(PR #696 merge). It is a read-only audit and coordination input. It grants no
acceptance, changes no claim denominator, and does not re-score the historical
**111/123 (90.2%)** result.

## 0. Baseline, evidence cut, and rules

| Item | Value |
|---|---|
| Historical functional score | **111/123**, 90.2%, unchanged; tag `accepted-local-2026-11-01-90pct` → `88bf413e8431`, runtime `bec60978b` (COMMON.md lines 18–19) |
| Canonical committed inventory mirror | `docs/acceptance/readme_feature_readiness_2026-11-01/CLAIM_INVENTORY.json`, Git blob `e20f5a8bc749606104f438d7ca9d05db0d2bb611` |
| Private bootstrap input | `CLI_BASELINE_CLAIMS.json` (not staged) |
| Evidence cut | `origin/main` `248a23296`; open PR heads read back with read-only `gh pr view` |
| Scope of this audit | Claim/requirement reconciliation, gap classification, three next slices, one read-only mutation-family contract |
| Not done here | Runtime edit, tests/campaigns, credentials, providers, live accounts, send/spend/download, deploy, merge, review, comment, issue mutation |

**State vocabulary.** `baseline-verified` means the 2026-11-01 source-bound
result is preserved, not re-run. `accepted-bounded` means an independent lead
decision accepted a narrower scope than the original claim. `submitted-open`
means the code/evidence exists on an open PR but is not merged. `open` means the
original user outcome is not established. `external-blocked` and
`environment-limited` are not reproduced product failures. A merge, green CI,
or a bounded mechanism proof never promotes a broad claim by itself.

## 1. Denominator accounting — all 143 claims accounted for

| Slice | Count | Current accounting |
|---|---:|---|
| Functional claims eligible for the 123 denominator | 123 | **111 baseline-verified + 12 open** |
| Separately tracked: Security | 8 | 8 baseline-verified; affected paths re-checked separately, not a new whole-security pass |
| Separately tracked: Performance | 3 | 3 unverified; no new measurement |
| Separately tracked: Compatibility | 4 | 4 unverified; COMPAT-01 has bounded guard evidence only; PostgreSQL/mobile/menubar are not qualified |
| Separately tracked: Comparative/marketing | 5 | 5 unverified; no sourced/reproducible comparison added |
| **Total** | **143** | 111 + 12 + 8 + 3 + 4 + 5 |

The 12 open functional claims are exactly:
`ORCH-01`, `ORCH-02`, `ORCH-07`, `ORACLE-01`, `TEAM-05`, `MEM-07`,
`MINI-03`, `MINI-04`, `MINI-05`, `INT-09`, `ROUTE-07`, `GOAL-02`.
They are reconciled individually in §3. Every other functional claim remains
`baseline-verified`; no reviewed record in this audit refutes a specific
baseline-verified claim.

### 1.1 Category reconciliation (all 143 claims)

Counts below are from the frozen inventory. “Current evidence” points to the
baseline bundle plus the newest relevant merged/submitted family; it does not
re-open an old claim merely because the baseline is old.

| Category | Total | Baseline verified | Open / separate | Current evidence and disposition |
|---|---:|---:|---|---|
| orchestration | 8 | 5 | 3 open | ORCH-01 bounded acceptance + merged public scope; ORCH-02/07 controlled fleet acceptance. §3.1–3.3 |
| governance | 8 | 8 | 0 | Preserved; no new governance-wide claim. |
| oracle | 6 | 5 | 1 partial | ORACLE-01 scoped acceptance; whole-app coverage still open. §3.4 |
| ask | 5 | 5 | 0 | Preserved. |
| agent-teams | 6 | 5 | 1 partial | TEAM-05 controlled scheduled entry; real transport/elapsed gap. §3.5 |
| memory | 7 | 6 | 1 open | MEM-07 canonical Memento path now exists; consolidated end-to-end evidence still open. §3.6 |
| hybrid-search | 5 | 5 | 0 | Preserved; `/search` UI is release-deferred, not a new functional pass. |
| vfs | 4 | 4 | 0 | Preserved. |
| agent-radio | 4 | 4 | 0 | Preserved. |
| office | 8 | 8 | 0 | Preserved; presentation binding accepted at `0d8767e3a`. |
| mini-apps | 5 | 2 | 2 environment-limited, 1 architecture-only | MINI-03/04/05 require KVM/Linux. §3.7 |
| graphrag | 5 | 5 | 0 | Preserved. |
| integrations | 9 | 8 | 1 external-blocked | INT-09 live-provider qualification. §3.8 |
| gateway | 6 | 6 | 0 | Preserved. |
| routing | 7 | 6 | 1 open | ROUTE-07 live subscription qualification. §3.9 |
| interoperability | 6 | 6 | 0 | Preserved. |
| goals | 5 | 4 | 1 open | GOAL-02 utility target ranking/persistence. §3.10 |
| workflows | 7 | 7 | 0 | Preserved; public approval scope merged as `49d45c7f3`. |
| core-workspace | 7 | 7 | 0 | Preserved. |
| installation | 5 | 5 | 0 | Preserved; COMPAT-01 remains separately tracked. |
| security (separate) | 8 | 8 | 0 | Affected current paths re-checked; no whole-security claim. §4 |
| performance (separate) | 3 | 0 | 3 unverified | No reproducible measurement added. §4 |
| compatibility (separate) | 4 | 0 | 4 unverified | COMPAT-01 guard only; PostgreSQL/mobile/menubar open. §4 |
| comparative (separate) | 5 | 0 | 5 unverified | No sourced comparison. §4 |

## 2. Current GitHub integration state (read-only readback)

`origin/main`: `248a23296` (PR #696 merge, 2026-11-06). The following key
families are **merged** on main:

| Ref | Family |
|---|---|
| `49d45c7f3` | PR #682 — public workflow approval scope |
| `78d2e0ca8` | PR #684 — scheduled real-workflow approval join |
| `b9ed05c6f` | PR #693 — scheduled approval join across a process restart |
| `e2ba4b01c` | PR #676 — scheduler pause/cancel/restart recovery |
| `e93982eec` | PR #695 — agent stop/cancel scope, material, receipt |
| `c7f581af5` | PR #681 — agent PUT replacement scope/material/receipt |
| `93e19ed78` | PR #675 — agent run admission |
| `184639a28` | PR #673 — agent delete |
| `05a9d69d7` | PR #670 — chat-session fork |
| `66e09c5ee` | PR #689 — JWT WebSocket/request-log redaction |
| `213e75c43` | PR #694 — independent review of #689 |
| `aadb75ec1` | PR #687 — protected deep links through login |
| `11a116593` | PR #692 — login-return evidence identities |
| `248a23296` | PR #696 — account-return / expired-session evidence |
| `baa695775` | PR #659 merge — fleet ORCH-07/02 integrated repair |
| `6a7e85c6d` | PR #668 — COMPAT-01 quickstart Python guard |

Open, unmerged at readback (`mergeable=MERGEABLE`, `mergeStateStatus=BLOCKED`
by required review/merge policy, not a merge conflict):

| PR | Head | Title / scope |
|---|---|---|
| #704 | `3cf413d58` | Settings BPE link gated on governance |
| #703 | `9f0ce26ac` | Recording review scoped to recording tenant (Agent1) |
| #702 | `5e056e234` | Agent stop failure truth (successor to merged #695) |
| #701 | `54f5f178c` | Agent3 review of #698 stderr fallback |
| #700 | `39d2cdc6c` | Settings/Assignments deferred-link gates |
| #699 | `da879a1c1` | Agents deferred Marketplace/Automations affordances |
| #698 | `db96775df` | Malformed log-record stderr redaction |
| #697 | `4ef61ef2c` | Documents search card release alignment |

These open PRs are **submitted evidence, not merged product**. In particular,
#702 contains the consolidated stop failure-truth repair; the merged #695
source remains the current main behavior until #702 is owner-merged.

## 3. The 12 open functional claims — requirement, evidence, gap

### 3.1 ORCH-01 — structured workflow blueprint

| Field | Reconciliation |
|---|---|
| Original requirement | Plain-language workflow request → structured, persisted workflow blueprint; ordered steps and a HITL gate before a mutating step (`CLAIM_INVENTORY` ORCH-01). |
| Current evidence | Bounded acceptance at blueprint generation, scoped persistence/readback, executable binding and durable checkpoint: source `0fae2d46c`, evidence `943fb32d7`, bundle `docs/acceptance/evidence/employee_orch01_workflow_blueprint_0fae2d46c_repair/`; verifier `VERIFIER_ORCH01_0FAE_ACCEPTANCE_20261105.md`. Public approval scope is merged `49d45c7f3` (bundle `docs/acceptance/evidence/workflow_public_approval_scope_20261106/`); scheduled join `78d2e0ca8`; process-restart proof `b9ed05c6f`. |
| Current disposition | `accepted-bounded` plus merged public-scope/scheduler repairs. The 0fae acceptance explicitly does not certify a new served-process or general execution-quality result. |
| Remaining gap | The accepted package exercises the mounted route with a controlled `LLMService.generate_structured_response` (see `backend/tests/test_orch01_workflow_blueprint.py:142-190`). There is no accepted evidence for one real served request through `backend/core/agents/queen_agent.py:174-220` with production scope/deadline/route selection. This is a local **evidence/qualification** gap, not a reproduced runtime defect. |
| Owner | Agent1 (also owns #703 recording review; do not take that slice). |

### 3.2 ORCH-02 — specialist work in an open-ended TASK response

| Field | Reconciliation |
|---|---|
| Original requirement | Route an open-ended TASK intent to recruited specialists; the response cites their actual work (`CLAIM_INVENTORY` ORCH-02). |
| Current evidence | Accepted at controlled local consumer/binding scope: source `68c5bf960`, evidence `14420401c`, bundle `docs/acceptance/evidence/employee_fleet_b9_581_integrated_68c5bf960/`; merge `baa695775` (PR #659). Predecessors `581654d21` and `b9ba56995` preserved. Verifier `VERIFIER_FLEET_68C5_ACCEPTANCE_PR659_20261105.md`. |
| Current disposition | `accepted-bounded` for controlled specialist response consumption, exact chain/scope/cache material and terminal truth. Not served model quality, live provider breadth or universal employee competence. |
| Remaining gap | A real served-model / ordinary-route TASK response that cites recruited work, and model-quality attribution. The accepted run doubled the specialist/model transport. This is **local + a separately authorized served-model action**, not a deterministic code gap. |
| Owner | Agent1. |

### 3.3 ORCH-07 — governed fleet-routing audit

| Field | Reconciliation |
|---|---|
| Original requirement | Eligible TASK records a governed fleet-routing audit row with candidates, chosen specialist and mode/shadow (`CLAIM_INVENTORY` ORCH-07). |
| Current evidence | Same accepted fleet bundle `68c5bf960` / evidence `14420401c` / merge `baa695775`; ORCH-07 gate `65/65` on 3.14 and 3.11 per `employee_fleet_b9_581_integrated_68c5bf960/README.md`. |
| Current disposition | `accepted-bounded` for controlled decision/outcome binding, complete scope, eligible calibration and generation-owned provenance. |
| Remaining gap | The served model/provider attribution and the actual ordinary TASK path under an authorized route. Not a reason to rerun the accepted fleet campaign. |
| Owner | Agent1. |

### 3.4 ORACLE-01 — postcondition oracle coverage

| Field | Reconciliation |
|---|---|
| Original requirement | Oracle enabled by default and covering the documented mutation classes; README wording “every mutating action is re-derived” is the broad target (`CLAIM_INVENTORY` ORACLE-01). |
| Current evidence | Scoped oracle repair accepted at `0f9796401` (`VERIFIER_ORACLE_SCOPED_RESULT.md`); exact canvas/presentation binding at `0d8767e3a`; whole-app inventory at `95454de7a` / `docs/acceptance/evidence/oracle_whole_app_inventory_20261102/`. Merged local mutation families now include document settings `703efedd2`, agent decision `9c6ac2b39`, memory write `b721d2313`, skill review `f2fdde97e`, community skill `28e524b32`, evolution review `c1871e064`/`60a1171b8`, workflow template `d5137ef0b`, marketplace `d7280b04f`, chat `71f9e22b4`, chat fork `05a9d69d7`, agent delete `184639a28`, agent run `93e19ed78`, agent replace `c7f581af5`, stop/cancel `e93982eec`, and direct HTTP canvas `326534847`. |
| Current disposition | `open` at the whole-app promise; scoped mechanisms are accepted. The inventory remains discovery evidence, not runtime coverage. |
| Remaining gap | The inventory recorded **827 mutating HTTP routes**, **366 high-risk names/paths** and **311 provider-adapter write methods** unqualified (`oracle_whole_app_inventory_20261102/README.md:14-18,48-50`). The inventory has not been re-based after the later merged families. A real uncovered local family is knowledge-document deletion (§6). Do not call full ORACLE complete. |
| Owner | Agent2. |

### 3.5 TEAM-05 — opt-in nightly alignment sweep

| Field | Reconciliation |
|---|---|
| Original requirement | Nightly alignment sweep records findings without changing policy unless the configured consent mode permits it (`CLAIM_INVENTORY` TEAM-05). |
| Current evidence | Controlled service and scheduled entry evidence: `docs/acceptance/evidence/verification_claims_20261102/` (21 tests) and `docs/acceptance/evidence/claim_progress_20261102/README.md:53-67`. `run_auto_certification` opens its own session; notify/approve modes leave flags off and do not requeue. |
| Current disposition | `open` / partially supported. The sweep's LLM transport is injected; the real transport and a real 24-hour scheduling boundary were not observed. |
| Remaining gap | One real scheduled fire through the configured transport and persisted finding readback. A 24-hour elapsed observation is **not** a soak claim and must not be described as soak or multi-worker qualification. Local + elapsed, no live provider grant implied. |
| Owner | Agent1. |

### 3.6 MEM-07 — tool error → reviewable evolution candidate

| Field | Reconciliation |
|---|---|
| Original requirement | A tool error produces a pending evolution candidate; no code/config change without approval (`CLAIM_INVENTORY` MEM-07). |
| Current evidence | Canonical path now exists: `record_tool_error` (`backend/core/auto_dev/tool_error_signals.py:47`), Memento pending candidate (`backend/core/auto_dev/memento_engine.py:282`), review/approve/apply/reject routes (`backend/api/autodev_review_routes.py:214,282,328`). The reviewed prompt-skill apply lifecycle was accepted at `c1074f0a9` / evidence `952fcbdf8`; ordinary-work consumption at `5538a654d` / evidence `d30130d1f` (`VERIFIER_REVIEWED_IMPROVEMENT_C1074_RESULT.md`, `VERIFIER_REVIEWED_SKILL_CONSUMPTION_5538_RESULT.md`). |
| Current disposition | `open` for the broad claim; the old `agent_evolution_candidate` HITLAction slice was removed in favor of the canonical Memento lifecycle (`docs/acceptance/evidence/full_app_consolidated_20261102/README.md:39`). |
| Remaining gap | One consolidated evidence chain: real tool-error signal → pending Memento candidate → review → apply → fresh-session consumption, with generated code never promoted and agent config unchanged. The pieces are accepted separately; the combined MEM-07 user outcome is not independently accepted. Local, deterministic. |
| Owner | Agent2 (durable skill/review boundary), coordinating with Agent1 on ordinary-work consumption. |

### 3.7 MINI-03 / MINI-04 / MINI-05 — mini-app runtime

| Field | Reconciliation |
|---|---|
| Original requirement | Dev-run/test, installed stateful instance, and per-instance isolation on the supported secure runtime. |
| Current evidence | Baseline evidence records fail-closed behavior on this macOS host; `backend/data` runtime is Firecracker-only. No KVM. |
| Current disposition | `environment-limited` / `architecture-only`. Not a product defect and not a local deterministic fix. |
| Remaining gap | Authorized Linux/KVM host with Firecracker. No host-code fallback, no cloud substitute. |
| Owner | Shared/platform; owner decision for environment. |

### 3.8 INT-09 — live provider qualification

| Field | Reconciliation |
|---|---|
| Original requirement | Live qualification of the 46+ provider claim against real external accounts/permissions. |
| Current evidence | Controlled catalogue/adapter/route evidence only; live connectors were never exercised in this baseline. |
| Current disposition | `external-blocked`. |
| Remaining gap | Per-provider accounts, scopes, consent and live data calls. Explicitly separate from local connector preparation. |
| Owner | Agent2 local preparation; owner grants each live qualification. |

### 3.9 ROUTE-07 — opencode-go subscription provider

| Field | Reconciliation |
|---|---|
| Original requirement | Resolve the `opencode-go` provider, catalogue, rate limits/headroom; live call externally qualified. |
| Current evidence | Provider resolution and catalogue/limit behavior exist; no live subscription call was made (`CLAIM_INVENTORY` ROUTE-07 notes). |
| Current disposition | `external-blocked` for live qualification; local catalogue/headroom tests remain possible. |
| Remaining gap | Real subscription key and an authorized live call/spend. |
| Owner | Agent2 local contract; owner for the key/spend. |

### 3.10 GOAL-02 — utility targets

| Field | Reconciliation |
|---|---|
| Original requirement | Score candidate trajectories against a utility target; a higher-utility outcome ranks higher and the target is persisted (`CLAIM_INVENTORY` GOAL-02). |
| Current evidence | The objective runtime exists (`backend/core/agent_objective.py:30-64`). The current “utility” is a maturity success-ratio delta injected as prompt text (`backend/core/generic_agent.py:1312-1321`); it is not a two-outcome ranking or a persisted target/score. |
| Current disposition | `open`; the baseline harness explicitly skipped model-backed scoring (`backend/scripts/readme_acceptance/groups_graphrag.py:305-310`). |
| Remaining gap | A deterministic two-outcome scoring/ranking and persistence contract, plus a negative for missing/invalid targets. This does not require or prove general model judgment. Local. |
| Owner | Agent1. |

## 4. The 20 separately tracked claims

### 4.1 Security — 8 claims, separately tracked (not in 123)

Baseline controls are preserved. Current affected-path evidence:

| Path | Evidence | Scope |
|---|---|---|
| WebSocket/request JWT redaction | `66e09c5ee` merged (PR #689); review `213e75c43`; evidence `docs/acceptance/evidence/security_ws_log_redaction_clean/`, `docs/acceptance/evidence/agent3_pr689_review_2026_11_06/` | Normal and rejected handshakes preserve path/status, no raw synthetic token. |
| Malformed log record → stderr fallback | PR #698 head `db96775df`, PR #701 review head `54f5f178c`; verification `VERIFIER_LOG_REDACTION_STDERR_REPAIR_20261106.md`, `VERIFIER_PR695_DELIVERY_AND_PR698_STDERR_ACCEPTANCE_20261106.md` | Submitted, not merged; bounded formatting-failure path. |
| Login/deep-link return | `aadb75ec1` merged; evidence `11a116593`; acceptance `VERIFIER_MERGED_AUTH_AND_NEXT_UPLOAD_JOURNEY_20261106.md` | Relative internal path/query preserved; external/protocol-relative targets refused by existing guard. |
| Account return / expired session | `248a23296` merged; evidence `docs/acceptance/evidence/agent4_account_return_20261106/`; acceptance `VERIFIER_AGENT4_ACCOUNT_RETURN_ACCEPTANCE_20261106.md` | Cleared-cookie/new-tab/login/expired-session recovery; not JWT revocation, process-restart recovery, SSO or password reset. |
| Stop failure truth | PR #702 head `5e056e234`; evidence bundle `employee_agent_stop_failure_truth_f2a31d0` on that PR; order `VERIFIER_STOP_FAILURE_TRUTH_REPAIR_20261106.md` | Submitted; three bounded failure-truth cases. |

Do **not** call the eight security claims “complete.” The audit only confirms
that the affected current enforcement paths were re-checked at their recorded
scope; no new whole-security campaign was run.

### 4.2 Performance — 3 claims

`PERF-01/02/03` remain unverified. No reproducible hardware/configuration,
cold/warm separation, percentile or throughput measurement was added. Test counts
and local latency are not performance qualification.

### 4.3 Compatibility — 4 claims

| Claim | Reconciliation |
|---|---|
| COMPAT-01 (Python range) | Guard evidence accepted at source `bad2f9596`, merge `6a7e85c6d`, bundle `docs/acceptance/evidence/compat01_quickstart_python_20261106/`. The guard accepts 3.11–3.13 and rejects 3.14 before any install; 3.12/3.13 were exercised through fake interpreters only, and the full quickstart install/run path was explicitly not exercised (`README.md:66-74`). Claim remains unverified. |
| COMPAT-02/03/04 | PostgreSQL, mobile and menubar/platform combinations remain unverified. SQLite CAS does not qualify PostgreSQL; a web UI does not qualify mobile/menubar. External/platform. |

### 4.4 Comparative/marketing — 5 claims

`MKT-01` through `MKT-05` remain unverified. No new reproducible comparison
basis, dated pricing source, or competitor matrix verification was added. These
statements do not count toward functional coverage.

## 5. Full product goal map (not only the 12 open README claims)

The rows below follow the directive’s §5 goal groups. “State” uses the same
vocabulary; “Gap” distinguishes local engineering from external/owner gates.

| Goal group | Product result and completion evidence | Current evidence | State | Remaining gap / owner |
|---|---|---|---|---|
| Setup and ordinary account use | Install/start, login, onboarding, roles, logout, reload, actionable session expiry, effective runtime config | Onboarding `671986755` (evidence `onboarding_first_run_20261106/`); account return `248a23296`; deep link `aadb75ec1`; install/COMPAT-01 guard `6a7e85c6d` | accepted-bounded | Fresh-profile/sign-out beyond the tested seam, process-restart session recovery, SSO/provider setup, password reset. Agent1/Agent4; provider setup external. |
| BYOK and suitable model selection | Authorized routes satisfy workload, economy, explicit pins; no-suitable actionable; truthful failure attribution | Accepted `5bbefe4c2` (durable incident identity), `0e04286b2` (served auto-selection/controlled matrix); BYOK contract | accepted-bounded | Served multi-model quality and automatic selection beyond controlled routes. No new key/spend authority. Agent2. |
| Authorized common data and search | Upload/connect, list/open/search/export, complete extraction with resource/version/scope/coverage, ambiguity clarified | Freshness `9b6e01e90`; extraction prefix `637a6e178`; upload import `e6bfdb0e6`; upload/open/reload checkpoint `agent4_upload_open_reload_20261106/`; documents card #697 | accepted-bounded | UI upload click and `/search` remain deferred/unqualified; export/grounding not exercised in that journey; delete family truth gap (§6). Agent2/Agent4. |
| Spreadsheet and calculation | Full-population filter/select/formula/reconciliation, decimal arithmetic, identifiers, units, currency, row/cell provenance | Currency repair `ff00e2cfc` accepted; term role/validity `36fd2670b`; quote/invoice compilers; G5 episodes | accepted-bounded | Full-population/reconciliation at the ordinary served boundary; restart and export values. General model judgment not claimed. Agent1/Agent2. |
| Canvas and editable outputs | Create/edit/export/reopen current content exactly once; unrelated/protected material survives | Direct HTTP canvas `326534847`, `82ac/fe401` acceptance; presentation binding `0d8767e3a`; Office evidence | accepted-bounded | No title/count-only certification; remaining canvas families and ordinary-user reopen/export. Agent2. |
| Teaching and reusable agent capability | Create/select employee, teach method/context/qualification/format, correct it, consume it in ordinary work after restart | Teaching acceptance `a87882526323`; reviewed prompt-skill apply `c1074f0a9`; consumption `5538a654d`; MEM-07 canonical path | accepted-bounded | Combined MEM-07 evidence chain (§3.6); generated code never promoted. Agent1/Agent2. |
| Assessment and unfamiliar work | Evidence-grounded decisions on unseen records; unknown/conflicting/expired qualification produces a targeted gap; independent work continues | G5 API campaign `a9cdac474`; header eligibility; currency/freshness; event-order `3ccad7a5a`; procurement `7d4358ea6` | accepted-bounded | New held-out/served-domain qualification; general adaptive judgment remains unqualified. Agent1/Agent2. |
| Durable employee objectives | Model-selected useful work and legitimate waits, same-job replies, restart, changing evidence, selective retention, cancellation, late-response refusal | Durable wait/progress/restart/reply `70a74cd02b5`; identity `2eb433f41`; goal-run mode/cancel `96d838d5c` submitted | accepted-bounded | Served qualification/event-order beyond the accepted episodes; whole-app completion not claimed. Agent1/Agent2. |
| Documents, presentations and email drafts | Usable editable output with current verified results/provenance; download/readback agree; no partial artifact while a result is unresolved | Office/DOCX evidence; presentation binding `0d8767e3a`; controlled Outlook draft evidence (no send) | accepted-bounded | Ordinary document journey + provider draft/readback; recipient delivery is separate; one-use send authority exhausted. Agent1/Agent2. |
| Repeatable workflows and schedules | Reviewable blueprint, honest `execution_ready`, real approval/rejection, registered actions, safe run/pause/cancel, durable schedule/restart | ORCH-01 `0fae2d46c`; public scope `49d45c7f3`; scheduler join `78d2e0ca8`; restart `b9ed05c6f`; scheduler recovery `e2ba4b01c` | accepted-bounded | ORCH-01 served-process evidence; full scheduled real-workflow result/receipt; PostgreSQL/multi-worker/soak separate. Agent1/Agent2. |
| Fleet, goals and background work | Actual specialist work, exact execution/outcome linkage, useful progress, truthful terminal states, no duplicate effect after restart | Fleet `68c5bf960` merged `baa695775`; goal-run family `96d838d5c`; background/cancel evidence | accepted-bounded | Served model quality and broader operational reliability; no shadow-success claim. Agent1/Agent2. |
| Direct mutations and whole-app ORACLE | Every reachable family enforces current authority/material, exact operation, durable effect and independent readback; replay/rollback/unknown truthful | Scoped oracle `0f9796401`; merged families #650–#695; stop truth #702 submitted; inventory `95454de7a` | open | 827 routes / 311 provider writes unqualified; next family §6; full ORACLE not complete. Agent2. |
| Remaining exposed application | Tasks/boards, communication, search, calendars, marketplace, admin and other enabled surfaces perform their advertised primary action with real state | Marketplace #661; admin/auth/memory/chat families merged; deferred-affordance PRs #697/#699/#700/#704; documents card accepted at component scope | open/partial | Tasks/boards and other surfaces need a primary-action/durable-readback audit; a capability placeholder is not feature acceptance. Agent1/Agent4/Agent2. |
| Installation, compatibility and operations | Supported build/documented versions; backup/isolated restore/rollback; paths/data survive restart | Historical install evidence; COMPAT-01 guard `6a7e85c6d`; restart evidence in several accepted families | open | COMPAT-01 full install/run; PostgreSQL runtime; mobile/menubar; backup/restore/rollback; KVM. Shared/owner. |
| Performance and comparative promises | Reproducible measurement with declared environment/workload/sample sizes/sources; comparative claims supported | None new | unverified | PERF-01/02/03 and MKT-01/05 measurement/source work; no invented numbers. Product/lead. |

## 6. Next local mutation family — knowledge-document deletion (read-only trace)

This is the one bounded family traced in this audit. It is chosen because it is
local, reachable through an ordinary authenticated API, not owned by Agent1’s
recording-review slice, and currently reports a success state without an
independent effect receipt.

### 6.1 Current path (read-only)

| Step | Current code |
|---|---|
| Route | `backend/api/document_routes.py:508-578`, `DELETE /api/documents/{doc_id}`, `@require_governance(action_name="delete_document")`. |
| Scope | Workspace resolved from the authenticated user via `_resolve_ws_id`; no tenant/workspace body input. |
| Existence | Exact id lookup, then chunk-family prefix lookup (`<doc_id>::`); unknown id/family → 404. |
| Effect | `delete_documents_by_id("documents", doc_id)` then a **best-effort** `delete_documents_by_prefix("documents", f"{doc_id}::")`. |
| Truthfulness | Prefix-delete exceptions are logged and swallowed; the prefix helper’s `False` return is ignored; the route returns `success_response(message="Document '<id>' deleted")` with no operation id, receipt, counts or readback. |
| Handler | `backend/core/lancedb_handler.py:1592-1638`: exact-id delete and prefix delete each return `True`/`False`; prefix delete uses a single `LIKE` predicate; failure returns `False`. |
| Existing test | `backend/tests/test_document_vector_family_cleanup.py:203-217` explicitly asserts `success is True` when prefix cleanup raises. This documents the current (not desired) behavior; it is not independent acceptance. |

### 6.2 Reproduced first failure

A delete of a base row that has a live chunk family returns a clean success even
when the family cleanup raises or returns `False`. The base row is gone, but
chunks remain retrievable in LanceDB and can still be returned by search. The
caller receives no operation identity and no indication that the effect is
partial. This is a **local, deterministic defect**, not an external-account
gap. The current test expectation is direct evidence of the behavior.

### 6.3 Executable contract

**Operation.** Authenticated `DELETE /api/documents/{doc_id}` for the caller’s
current workspace, with optional caller-supplied `operation_id`.

**Authoritative inputs.**
- Current principal/tenant/workspace resolved server-side; never from a body or
  a default alias.
- Exact `doc_id`; accepted set = exact base row and/or rows whose id starts with
  `doc_id + "::"`.
- Governance outcome from the existing `@require_governance` path.
- No provider, model or live-account action.

**Durable effect.** Remove the exact base row and the full chunk family. Record
the pre/post row and chunk-family counts. Write one `AuditLog` receipt bound to
actor, operation, tenant/workspace, exact document identity and counts.

**Truthful outcomes.**
- `verified` only after a fresh readback proves base row absent, chunk family
  absent, and list/get/search no longer return the content.
- `uncertain` / `committed_unverified` when the base row was removed but family
  cleanup failed, returned `False`, or the readback is unavailable. Preserve the
  operation identity and the known base-row effect; do not return a clean
  success and do not claim rollback.
- `already_applied` for the same operation id with the same material; return
  the original receipt without a second deletion.
- `no_change` when the document/family is already absent under a verified
  readback; do not invent a new receipt.
- `refused` / `404` for unknown id or a document outside the caller’s
  tenant/workspace; no deletion and no foreign identity disclosure.
- Because LanceDB and SQL are separate stores, do **not** claim one atomic
  transaction. Use the existing compensation/reconciliation contract; an
  operation-local lock is not distributed atomicity.

**Valid twins.**
1. Base row + chunk family → one verified deletion; fresh list/get/search and
   prefix readback all empty; exactly one receipt.
2. Chunk-only family (`doc::c0…`) → verified deletion of the family; no 404;
   one receipt.
3. Prefix cleanup raises or returns `False` after the base delete → a
   non-success/partial outcome with the original operation id, known base
   effect and `do_not_repeat` until reconciliation; chunks are still readable
   only as an explicit uncertain state, never as clean success.
4. Unknown id and foreign-workspace id → 404/refused, zero deletes, zero rows.
5. Replay same operation id → one effect, original acknowledgement; different
   `doc_id` under the same operation id → conflict.
6. Restart/fresh session → readback and receipt survive; no duplicate deletion
   and no invented success.

**Implementation constraints.**
- Reuse the existing `AuditLog` / operation-id / replay pattern (for example the
  merged agent stop service `backend/core/agent_decision_write_service.py`) and
  the existing LanceDB deletion methods. Do not add a second deletion engine.
- Keep `@require_governance` and the current workspace resolution.
- Do not weaken unknown-id 404, chunk-family deletion, or ordinary delete
  authorization.
- One focused route/service matrix plus a real scratch LanceDB control is
  enough; no broad campaign.

**Owner:** Agent2. **Files:** `backend/api/document_routes.py`,
`backend/core/lancedb_handler.py` (only if the return/verification contract
needs a small helper), `backend/tests/test_document_vector_family_cleanup.py`
(update the old “cleanup failure is success” expectation) and one new focused
contract test.

## 7. Three highest-impact unblocked engineering slices

### Slice A — ORCH-01 served production boundary (Agent1)

- **Impact:** closes the largest remaining evidence gap on a headline workflow
  promise; reuses the accepted `0fae2d46c` blueprint/binding/checkpoint work and
  the merged public-scope/scheduler repairs.
- **First failure / current boundary:** the accepted package drives the mounted
  route through `TestClient` with `LLMService.generate_structured_response`
  patched (`backend/tests/test_orch01_workflow_blueprint.py:142-190`); the
  production method `QueenAgent.generate_workflow_blueprint`
  (`backend/core/agents/queen_agent.py:174-220`) has not been exercised through
  a real served process. This is an evidence gap, not a proven defect.
- **Decisive probe:** one scratch uvicorn process, ordinary authenticated
  request to `POST /api/v1/workflows/generate-from-agent`, production consumer,
  controlled model transport only at the LLM boundary. Assert one persisted
  workflow, ordered steps, HITL before a mutating step, and durable readback.
- **Valid twins/negatives:** empty prompt → 422 and no row; no-suitable route →
  503 and no row; duplicate/retry → one workflow; foreign scope cannot read the
  workflow.
- **Owner / sequence:** Agent1 after the #703 recording-review slice; do not
  take #703 or touch its files.

### Slice B — ORACLE-01 knowledge-document deletion truth (Agent2)

- **Impact:** closes a concrete local data-integrity/safety defect: a deletion
  can report success while searchable chunks survive. It is the next reachable
  mutation family, independent of Agent1’s recording review.
- **First failure:** reproduced by code and the existing test expectation:
  `backend/api/document_routes.py:562-578` swallows prefix-cleanup failure and
  returns success; `backend/tests/test_document_vector_family_cleanup.py:203-217`
  asserts that behavior.
- **Decisive probe:** real scratch LanceDB with one base row + chunk family;
  inject a prefix-delete `False`/exception after the base delete. Expect a
  partial/uncertain outcome with operation identity and known base effect, not
  200 “deleted”.
- **Valid twin:** normal base+family delete is verified by fresh list/get/search
  and prefix readback with exactly one receipt; chunk-only id works; unknown id
  404; foreign workspace refused; replay is idempotent.
- **Contract:** §6.
- **Owner / sequence:** Agent2 as prepared successor after the current stop
  failure-truth review (#702) is resolved; no shared files with Agent1.

### Slice C — COMPAT-01 full quickstart install/run (Agent2)

- **Impact:** turns the accepted interpreter-guard control into an actual
  install/start qualification for the supported Python range, which the product
  promise requires. It is a separate tracked claim, not part of the 123.
- **First failure / current boundary:** the accepted evidence explicitly did not
  install dependencies, create a venv or start the app; 3.12/3.13 were fake
  interpreters only (`docs/acceptance/evidence/compat01_quickstart_python_20261106/README.md:66-74`).
  The full quickstart path on those versions is unproven.
- **Decisive probe:** clean scratch root, documented `scripts/quickstart.sh`
  path on 3.11 and one of 3.12/3.13; assert the server reaches `/health/ready`,
  one ordinary login, and no 3.14 install attempt.
- **Valid twins/negatives:** 3.11 install/run; 3.12 or 3.13 install/run; 3.14 is
  rejected before venv/install with the documented message.
- **Owner / sequence:** Agent2 after Slice B; requires only ordinary package
  installation, no live provider/model/account.

### Next after these (do not start in parallel)

`GOAL-02` two-outcome utility ranking/persistence (Agent1) and `TEAM-05` real
transport/scheduled fire (Agent1) are the next bounded claim-closing slices.
`ORCH-02`/`ORCH-07` served-quality work and `MEM-07` consolidated evidence are
prepared but remain separate; `INT-09`/`ROUTE-07`/`MINI-*` stay external or
environment-gated.

## 8. External accounts, KVM, and owner decisions — kept separate

| Boundary | Items | What can continue locally |
|---|---|---|
| Live provider accounts/permissions | INT-09, ROUTE-07, Zoho/Microsoft/Outlook live qualification, provider breadth | Contracts, adapter/catalogue checks, controlled doubles, exact qualification requests |
| Send/spend | One-use Outlook send is exhausted; no new send/spend authority | Draft-only/controlled transport, readback contracts, reconciliation |
| KVM/Linux/Firecracker | MINI-03/04/05 | Fail-closed behavior, typed interface and runtime contract; no host-code fallback |
| PostgreSQL / multi-worker / soak | Explicitly not qualified by SQLite or single-process evidence | Portable SQL/CAS checks, reproducible setup plan; no qualification claim |
| Merge/review/deploy | Open PRs #697–#704 and owner merge gates | Local evidence, exact-head CI handoff, next independent slice |
| Policy/claim acceptance | Promotion of a claim, denominator change, whole-app readiness statement | This reconciliation; no self-acceptance |

## 9. Reference verification performed

All quoted refs were checked read-only at this evidence cut.

| Check | Result |
|---|---|
| `pwd` | `/private/tmp/atom-cli-agent2` |
| `git rev-parse HEAD` / `FETCH_HEAD` / `origin/main` | all `248a2329623b433e68104c4d89d2965683d81013` |
| `git log -1 49d45c7f3`, `78d2e0ca8`, `b9ed05c6f`, `e93982eec`, `c7f581af5`, `93e19ed78`, `184639a28`, `05a9d69d7`, `66e09c5ee`, `aadb75ec1`, `baa695775`, `6a7e85c6d` | each resolves to the named commit; ancestry on `248a23296` checked with `git log --ancestry-path <sha>..248a23296` |
| Accepted source refs `0fae2d46c`, `68c5bf960`, `0f9796401` | resolve on main ancestry; evidence bundles present under `docs/acceptance/evidence/` |
| Canvas/ORACLE inventory | `docs/acceptance/evidence/oracle_whole_app_inventory_20261102/README.md` (blob `3f09abc08b27957f2fbdd74cccdaf95f1e3e7522`) records 90 registered actions, 827 mutating routes, 311 provider writes |
| ORCH-01 acceptance bundle | `docs/acceptance/evidence/employee_orch01_workflow_blueprint_0fae2d46c_repair/README.md` (blob `879d6bd1daf5dd9f83e116703449ec21ea9abfd3`) |
| Open PR state | `gh pr view` for #697–#704: open, `mergeable=MERGEABLE`, `mergeStateStatus=BLOCKED`; heads recorded in §2 |
| Baseline counts | committed inventory blob `e20f5a8bc749606104f438d7ca9d05db0d2bb611`: 143 total, 123 functional, 20 separate, 111 verified functional |
| Document-delete trace | `backend/api/document_routes.py:508-578`; `backend/core/lancedb_handler.py:1592-1638`; `backend/tests/test_document_vector_family_cleanup.py:203-217` |
| GOAL-02 trace | `backend/core/agent_objective.py:30-64`; `backend/core/generic_agent.py:1312-1321`; `backend/scripts/readme_acceptance/groups_graphrag.py:305-310` |

No runtime file was edited, no test/campaign was run, and no credential,
provider, live account, send, spend, download, deployment, merge, review or
comment action was performed.

## 10. What this document changes — and does not

- It **does not** change the historical 111/123 result, the 123 denominator, the
  20 separately tracked claims, or any tag.
- It **does not** promote a bounded acceptance to a broad claim.
- It **does not** call general adaptive judgment, PostgreSQL, multi-worker,
  soak, live provider breadth, whole-app ORACLE, or whole-app readiness
  complete.
- It records current dispositions, exact source refs, remaining gaps, three
  next slices, and one executable local mutation contract for independent
  review.
- The private operational bootstrap files — `opencode.jsonc`,
  `CLI_WORK_ORDER.md` and `CLI_BASELINE_CLAIMS.json` — are intentionally not
  staged or committed.
