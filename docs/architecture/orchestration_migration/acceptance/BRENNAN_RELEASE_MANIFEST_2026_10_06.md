# Brennan release manifest — fixed six-case suite (2026-10-06)

Per `BRENNAN_FIRST_PRODUCT_COMPLETION_PLAN_2026_10_06.md`: the cases and
expected outcomes are recorded BEFORE further fixes; the suite runs only
after the browser submission blocker is resolved, against a frozen
candidate. Three trials per case, same candidate; every trial reported.

## Frozen candidate (fill at freeze time)

| Field | Value |
| --- | --- |
| Commit | **c52dfd39c** (2026-10-08 final refreeze of the day) — TESTED PRODUCTION IDENTITY (unambiguous): the code chain is 715c95d6c → routing memo → 6d86ef646 (interpretation slice) → 3c9042225 (fallback v1) → c854ba47b (fallback finished + installer repair v1 + manifest reconcile) → 1b8df160b (verdict-document commit — DOCUMENTATION ONLY, no production code) → 7aaabd048 (runner docs) → 286f07565 (installer safety: secrets preserved, empty-DB-only adoption) → c52dfd39c (preferred-route feature). Trials batched on 2026-10-08 ran against the code state of their timestamp; the breadth batch + repetitions (cases 1/2/4/6) ran on the c854ba47b→c52dfd39c code (identical for their paths — the preference was unset or a validated no-op during those trials); case 5's world snapshot pins 3864f26d… of the c854ba47b-era tree. Earlier freeze rows — code changed after 715c95d6c, so the candidate moves per the repair-refreeze rule: structured-protocol pair memo + cascade skip; Phase-2 request-bound scope interpretation (interpret_turn_request, request-scope precedence, verbatim reader consumption, extend merge); fresh-install absolute-fallback repair. Earlier-result APPLICABILITY on the new candidate: Cedarberg original-sentence proof (1d55f0920) and empty-stream persistence (715c95d6c) remain valid — those chains are untouched by the later commits. Case trials run BEFORE 6d86ef646 (case 1 T1, case 2 trial 1, case 4 trials 1-2) are superseded FOR SCOPE BEHAVIOR by the request-scope changes and re-run at the next batch; their defect records (routing 400, wrong-item scan) remain the evidence for the repairs that landed. Case 4 trials 5-6 (post-6d86ef646) and case 6 trial 1 (restart/isolation machinery untouched by Phase-2) carry forward but are re-run at the batch per convention. Case 3 stays CLOSED on its recorded chain (no fresh failing reproducer). Pre-freeze chain history for 715c95d6c: — supersedes the 680c3acca/479edaefc series. Chain since 680c3acca: job-work ledger + ledger-driven continuation (8db6f9908); sweep-injection controls + stage-attributed refresh + pricing-verify cross-check (622904302); structured sweep catalog candidates (bea8bf4b5); fresh-session source resolution + inflight TTL (4c7540c20); query_knowledge_graph complexity-1 (481272682); catalog-served pair gate at stream boundary (6d3f8e965); delivery event-ID arbitration + findings-only result revision + recovery pass (c438f99ed/65866f823); item-drop chain closed incl. named-prose extraction + partial-fragment precedence + resolved-mention handoff (d1a7d61d9..341dd6a6b); natural extension-less file resolution by stem equality + verdict-honest ask lane (1d55f0920); empty-reply rewrite reaches the durable row (715c95d6c). Suite health at freeze: 185 passed across finalization/calc-boundary/identity/probe/target-set/empty-item/delivery/ledger suites (backend/tests); known pre-existing failures elsewhere: test_loose_retry_shape_still_matches_but_is_not_authoritative, test_llm_yes_resolves_unknown_generic_noun (verified failing on the clean tree before this chain). Dirty tracked files: frontend .preview-instance farm deletions (another lane's instance farm, not production code) + next-env.d.ts (generated). Prerequisite state: fork 2233f463 intact (8 rows, requested 1–5, alternatives 6–8); trained agent 9837ec71 (Sales Agent) present; lessons present; manual-price approvals: AUTHORIZED BY OWNER DIRECTIVE 2026-10-08 — No. 381's $2,902 (fork row 1 Unit Price) IS the approved manual value for cases 1 and 4; provenance = the owner's correction message of 2026-10-08 (recorded here; no re-ask, no test-only approval). Trials designate it via the runners' supported --manual-cells flow with the label "No. 381" (labels are literal canvas text near the figure — figures_near_label; "rowN:price" style labels match nothing and silently report not-preserved. "No. 381" verified against the fork content -> ['$2,902.00']; case-4 trials 5-6 used exactly this designation with preservation TRUE). Live verified on this candidate pre-freeze: original Cedarberg sentence (extension-less natural name) end-to-end with correct file identity + subject at the scan; empty-stream HTTP persistence (envelope + durable row + clean-restart survival). |
| Breadth batch + repetitions (2026-10-08, candidate c854ba47b chain, real-endpoint auth) | Case 1: investigation 2/2 GREEN (5/5 items covered+evidenced, zero draft mutations; sessions 0a0800a9, 5bf4c00a); drafting leg T_AUTH budget-exhausted under the credit-dead paid pool (external condition, recorded). Case 2: **3/3 PASS** (trial 1 regraded under the evidence-corrected checker with the original FAIL preserved; trials 2-3 fresh PASS, sessions in case2 results). Case 3: CLOSED (prior chain). Case 4: manual-preservation contract GREEN (No. 381 $2,902 preserved AND marked, trials 6-7); ambiguity legs not establishable this batch — the planning step fails before source consultation under the same external condition (trials 5-7 replies honest throughout). Case 5: **3/3 PASS** (see below). Case 6: 2/2 pass-with-note (restart-in-flight, no duplicate effects, S2 isolation green; execution-ids cell contradicts its own comment — recorded, not changed). SINGLE EXTERNAL CONDITION: the gateway ACCOUNT exhausted funds mid-day (402 upstream at 15:4x UTC after serving at 14:4x) — the gateway serves the models (catalog verified); free-tier models exist on it but no per-install default-model override exists yet (recorded product gap, fresh_install_findings). No credit top-up requested. |
| Live status (~19:55 UTC) | Freeze b83d772c6-series RETAINED as historical identity; production still 479edaefc. STORAGE RECOVERED: ENOSPC emergency (100%, WAL 46GB) halted via emergency stop; parallel lane cancelled both runaway loops via the owned lifecycle path (runs now terminal); auto-checkpoint on close (WAL 0, integrity ok, 46GB free); ~1.3GB stale backups RELOCATED to Seagate (nothing deleted); server restarted pid 7256 == 0579878b (aligned); 4-min WAL watch quiet (6MB steady) — ticker does NOT resume on terminal runs. Timeout regression BUILT + VALIDATED against both probe sessions (T2 FAIL with cited authority phrases, T1/T3 refuse PASS). NO trials until pool healthy; wording fix + manual cells still open. |
| Serving source | case 5: isolated acceptance world (snapshot of this tree), backend under the seatbelt profile with provider shim on 127.0.0.1; pid/ports recorded in the run's results JSON. Cases 1-4/6: dev stack, recorded per trial. Backend/frontend code identity verified per trial (no farm/checkout name accepted as serving identity). |
| Configuration | ATOM_TASK_LIFECYCLE_ENABLED=1, CHAT_FINALIZATION_M1=1, CHAT_FINALIZATION_M2=1 (world launch flags); case 5 model egress = local shim only, never the real account. Cases 1-4/6 use the configured real planner + available authorized connectors; model, flags, source versions, server identity recorded per trial. |
| Database | case 5: per-run atom.db seeded from the world fixture inside `backend/data/acceptance_worlds/<world>/runs/run-*/`; identity (sha256) recorded in the results JSON. Cases 1-4/6: dev DB + pre-run snapshot. |
| Fixtures | case 5: seeded admin user + email canvas via the app's own model path (finish_line World.seed pattern). Cases 1-4/6: disposable fork canvas (not the original), trained agent 9837ec71, lessons: BurrKing basis / Tennsmith basis / Service estimate |
| Trial identity | every trial result records: candidate commit, driver file sha256, case/trial id, expected vs actual, job/operation/source ids, timings, cost where available, interventions (assisted vs genuine clarification), evidence link, verdict. Superseded-candidate trials stay under their original identity below — never merged into this candidate's verdict. |

## Superseded history (retained under original identities — NOT current-candidate evidence)

- **Freeze b83d772c6-series (production 479edaefc, HISTORICAL identity, 2026-10-06):** case-3 3/3 PASS verified from DB
  (jobs 6f86bf55/d42edde0/c4e103fb, exactly 2 applied ops each) + gated reproducer 11/11 on served f9d1e2be3
  (session 7930a2bc/job 4eb33a9a) + identity probe 2 attempts BLOCKED-environmental (excluded from verdicts) +
  timeout-wording finding (T2 presents unrecorded figure with formula authority — bounded narration rule owed).
  Superseded by whatever candidate carries the targeted fixes + writer shutdown. Never merged into the new verdict.

- **Case 5 trial 1 — PASS (10/10) on candidate a4699860a** (2026-10-06, world `case5_browser_1010`, export sha ccdba3b11c): button success → Enter credit failure (truthful, quality=error, no canvas effect) → button dispatch while broken (truthful second failure) → restored → Enter success → reload exactly-once. Invalidated for the release verdict by 78ba06084 (chat_routes failure_reason serialization changes the observed envelope). Full record: `backend/data/acceptance_worlds/case5_browser_1010/case5_results_20261006_135857.json`.
- **Case 3 trial 1 — SPLIT on candidate a4699860a** (interaction PASS: one precise question, $2,625, $1,800; durable FAIL: no job calculate op, no published calc record on the tool-plan path). Root-caused to dotted-service dispatch + compact input binding; fixed in 78ba06084. Record retained below in Case 3.

## Case definitions

### Case 1 — Full quote investigation + explicitly authorized drafting
- Input: owner asks (ordinary language) to investigate ALL requested
  quotation items on the disposable fork using taught sources; then, after
  the comparison exists, explicitly authorizes drafting.
- Expected: every item accounted for with draft value / source value +
  identity / date-freshness / discrepancy / decision-needed; queued reads
  complete without "continue"; drafting applies teaching + verified
  correspondence, preserves approved manual prices, leaves unresolved
  commitments unasserted, does NOT send; all of it survives reload.
- Verdict: **SPLIT-PENDING-PREREQ** (trial 1, 2026-10-08, session
  0a0800a9, real-endpoint auth): investigation leg 5/5 items covered AND
  evidenced in the job, 0 canvas updates during T1 (draft untouched as
  instructed). T_AUTH drafting leg NOT RUN by construction — no in-flow
  approved manual-price cells exist for designation (owner action
  outstanding). Results:
  `backend/data/acceptance_worlds/case1_results_715c95d6c.json`.
  Repetitions deferred to the post-Phase-2 refreeze (both open defects
  are interpretation-class; uncorrected-candidate trials cannot close).

### Case 2 — Subset request + "other machinery" follow-up
- Input: owner names a SUBSET of items; follow-up asks about "the other
  machinery".
- Expected: the subset does not expand to the whole canvas; the follow-up
  resolves to the remaining items (or asks precisely which); scope stays
  the owner's requested scope throughout.
- Verdict: **FAIL** (trial 1, 2026-10-08, session 41e304ff, real-endpoint
  auth): T1 subset leg all-green (both items covered, zero leaked
  figures, job evidence subset-only — the core scope-preservation
  property HELD). T2 follow-up failed the frozen checker: the reply
  names five machine scopes and asks the owner to pick ("Say which of
  those you want first, or ask for all of them in one pass") — an
  imperative-form precise question the checker's ask-vocabulary does not
  match; substance note recorded in the results file, assertion change
  is the owner's call, not made. Results:
  `backend/data/acceptance_worlds/case2_results_715c95d6c.json`.

### Case 3 — Taught formula, missing input, answer, changed-input recalc
- Input: "Estimate this service job using our taught rates." (no inputs);
  owner answers "17.5 hours, no materials"; then "recalculate — 12 hours".
- Expected: ONE precise question for the missing inputs; computation via
  the engine ($2,625 then $1,800); each recorded as its OWN operation with
  inputs + content-derived policy version; distinctions preserved.
- VERDICT IDENTITY NOTE (2026-10-08 reconcile): the verdict below is HISTORICAL EVIDENCE on its recorded repair chain (f9d1e2be3-line, sessions c3t1-3, jobs 6f86bf55/d42edde0/c4e103fb) — NOT a current-candidate trial and not counted in the current batch; it reopens only on a fresh failing reproducer on the current chain.
- Verdict (release-owner accounting; A-reported 3/3 INDEPENDENTLY
  VERIFIED read-only from the DB): **[x] [x] [x]** on repair-line code
  (trials 21:40–21:44 UTC against pid 61680 served from af2729ec0-line
  tree; current served pid 63660 == dfd2b4f6 == production af2729ec0,
  verified via /api/health) — sessions c3t1-452c8e51 / c3t2-87e032ce /
  c3t3-8ab70f16 → jobs 6f86bf55 / d42edde0 / c4e103fb, EACH holding
  exactly 2 applied calculate ops (2625 {rate 150, hours 17.5,
  materials 0} + 1800 {rate 150, hours 12, materials 0}), 5 total ops
  per job. Timings/models/interventions per turn were NOT recorded by
  the operator — owed; turns taken as verbatim-unassisted pending that
  confirmation. Repair chain as handed over: f9d1e2be3 (turn binding)
  + f0c9bbbaa/af2729ec0 (content-derived idempotency, reviewed:
  INCLUDE). Interim failures preserved per handover (duplicate 2625 on
  f9d1e2be3; snapshot-less collapse on f0c9bbbaa; TestRound72VersionCoherence
  intermittent recurred once). Suites cited: 123/123 combined.
  PROCESS NOTE: these trials, the restart, and the original verdict
  block bypassed release-lane ownership (reserved by owner direction);
  substance accepted, authority restated here. Case 3 is CLOSED on the
  evidence above; it reopens only on a fresh failing reproducer.
- Verdict history (candidate a4699860a, superseded): trial 1 was SPLIT —
  interaction PASS, durable FAIL. Root-caused via an isolated fixture
  with the real teaching (lesson 1451b758; trace:
  `backend/scripts/orchestration_acceptance/case3_record_trace.py`) to
  TWO missing transitions: (1) the structured planner emits DOTTED
  service names ("datasets.calculate") but the executor's local branches
  dispatch on service="datasets" + intent="calculate" — dotted names
  fell through to the generic external-integration branch, whose
  "nothing usable" failure block let the model self-compute the figures
  in narration (figure-grounding flagged them once; the regen
  re-narrated); (2) the planner folds inputs into its query as compact
  "hours=17.5 materials=0" pairs, which the input binder neither bound
  (whitespace required around the operator) nor bound safely (the
  word-order pattern stole "17.5 materials" adjacency). Fixed at the
  shared boundary in candidate 78ba06084: executor normalization of
  dotted datasets.* names onto the local dispatch + kv-first input
  binding — one convergence point, the EXISTING recording seam, no
  second recording call. Regressions:
  backend/tests/test_calculate_toolplan_boundary.py (6/6: local-lane
  routing, missing-input asks-and-records-nothing, one op per request
  with its own inputs, changed-input recalc as its own op, duplicate
  dispatch dedup, two conversations with different taught rates).
- Chronology (release-owner reconciliation, 2026-10-06 ~17:15 UTC):
  1. Candidate a4699860a (superseded, history): trial SPLIT —
     interaction PASS, durable FAIL. Handed-over diagnosis (calc-lane
     owner, via isolated fixture with the real lesson 1451b758): (a)
     dotted planner service names fell through to the generic external
     branch, letting the model self-compute in narration; (b) compact
     `hours=17.5 materials=0` pairs bound unsafely. Fixed in 78ba06084
     (executor normalization onto the local dispatch + kv-first
     binding); regressions 6/6 at the time.
  2. Candidate 78ba06084 production (== frozen 8cc6f1a1d production;
     served on dev pid 35415 from 15:44 UTC): **4 live trials, 2/4
     PASS — mixed reliability, not a near-pass.**
     - R1 (calc-lane owner): FAIL — T2 recorded (2625 applied); bare T3
       recalc narrated correctly with NO op. Session/job IDs still owed.
     - R2 (calc-lane owner): FAIL — bare T2 narrated ($2,625) UNRECORDED;
       T3 recorded (1800). Session/job IDs still owed.
     - R3 (calc-lane owner): PASS — precise question; $2,625; $1,800;
       two applied ops with own inputs.
     - R4 (release owner, 16:07 UTC, `case3_calc_trials.py`, session
       9dfd3dff-bb1e-420c-b014-119862362d44, job
       f5ac9ab6-5c94-45e2-a26a-75cba227b9ef): PASS 11/11 (23.0/21.2/
       20.7s, deepseek-flash); T2 op inputs {rate=150 taught-default,
       hours=17.5, materials=0 request-supplied}, T3 op {hours=12,
       materials=0}, policy taught-expression:Service estimate
       vaacc361fd619 on both. (First 9/11 was my runner's extraction
       bug — record lives under op `calculation`, not `extra`;
       corrected and verified against the live op JSON; the buggy file
       is renamed *_RUNNERBUG.json, never counted.)
     Residual defect: bare follow-up routing was planner-dependent —
     the estimate-regex override did not fire when the plan was not
     datasets.calculate. Returned to calc-lane owner; repetitions
     paused. Only corrected-candidate trials can establish closure,
     and none exist yet.
  3. Repair aba7d67f5 (calc-lane owner, 16:37 UTC) — IMPLEMENTED +
     REGRESSION-TESTED, live closure PENDING: bare follow-ups now
     route on DURABLE job state (asking turn records a verification
     QUESTION with structured inputs, still zero calc ops;
     `_calc_followup_dispatch` fires on open-question + bound missing
     input; `calculate_followup_from_query` resolves answer/recalc;
     `_record_on_job` outcome threads into record + block + narration
     guard; workspace_id threaded to every dispatch site for dedup
     parity; derivation asks excluded from calc dispatch). Evidence:
     12/12 `test_calculate_toolplan_boundary.py` (incl. 6
     do-NOT-route counterexamples: unrelated question, cancellation,
     topic change, ambiguous answer, multiple pendings, changed
     teaching), isolated trace replay (T1 asks → bare $2,625 recorded
     → bare $1,800 recorded), 197 green across
     boundary/pricing/engine/orchestrator/verbatim suites.
  4. LIVE STATUS: the served dev candidate is f02996f65 (B's
     finalization-envelope fix; pid 47746, restarted 16:35 UTC
     uncoordinated — 2 commits stale, predates the calc repair). The
     failing baseline is pinned with IDs (release-owner verified
     read-only): session `verify-202f8dc5` (calc-lane owner's live
     probe, 16:37–16:40 UTC), job
     5869e776-4ac7-4dfb-87fc-a74068f35df3 — T2 calculate applied 2625
     with own inputs, but bare T3 recalc left only a `retrieve
     running` op (`datasets.calculate:Recalculate — 12 hours.`) and a
     narrated $1,800 with NO calculate op. (A `web_search:capital of
     France` retrieve in the same job correctly stayed calc-free.)
     Gate: this probe shape (T1 ask → bare T2 → bare T3 ⇒ TWO applied
     calc ops with own inputs) must pass ON THE SERVED CANDIDATE
     before any three-trial batch. No batch until then.
  5. GATE REPRODUCER PASSES (release owner, 17:20 UTC, single trial —
     NOT a batch): session 7930a2bc-3820-48d2-911e-28b98dc8ebca, job
     4eb33a9a-1f2f-4a15-a023-f85d090eb76f, served pid 54785
     (f9d1e2be3): 11/11 — T1 asks + zero ops; T2 2625 own op; T3 1800
     SECOND own op (job holds exactly those two, no duplicates).
     Results: `backend/data/acceptance_worlds/case3_results_20261006_172033.json`.
     The case-3 batch is UNLOCKED but not launched: it runs on the
     final frozen candidate after storage preflight passes.

### Case 4 — Ambiguous item, conflicting source versions, approved manual value
- Input: an item code carried by multiple files/versions; one row holds an
  approved manual price.
- Expected: ambiguity → clarification (never first-match); conflicting
  versions → coherent-version or explicit conflict; the approved manual
  value is PRESERVED and marked; only real decisions block.
- Verdict: **FAIL** (trials 1-2, 2026-10-08, sessions b8edf272/eb548869,
  real-endpoint auth). Trial 1: paid providers credit-exhausted; the
  structured sweep dispatched opencode-go/claude-haiku-5-5 → 400
  ModelProtocolUnsupported (unmemoized), turn degraded to an honest
  tool-failure reply. REPAIRED at the first broken boundary
  (structured-path protocol memo + cascade skip, post-freeze commit).
  Trial 2 (post-repair): all three ambiguity checks PASS (no
  first-match; price list + leads workbook + email thread named; two
  concrete next searches offered). NEW DEFECT recorded, routed to
  Phase 2: the retrieval scanned item 'sle24' instead of the asked
  'No. 381' — the canvas-derived item set replaced the request's
  explicit subject at the handoff (job c281b0c1 evidence in the results
  file); the reply honestly reported the miss. Manual-preservation cell
  NOT RUN by construction (owner designation outstanding). Results:
  `backend/data/acceptance_worlds/case4_results_715c95d6c.json`.

### Case 5 — Provider failure then another message (browser leg)
- Input (UI): successful message → controlled provider failure (isolated
  stub or exhausted-test route, never the real account) → another ordinary
  message after failure → provider recovered.
- Expected: truthful terminal error (success=False, error_code, remedy);
  rows persisted with quality=error; the NEXT message dispatches (Send
  button AND Enter recorded separately); recovered provider succeeds;
  reload preserves history WITHOUT duplicates. A prior failed message
  must not permanently disable a new request.
- Status (2026-10-06 update): verdict boxes below are for the CURRENT
  frozen candidate (0e3c5d42c). The a4699860a trial-1 PASS is retained as
  history above; all three trials rerun on the current candidate because
  78ba06084 changes the observed failure envelope (failure_reason now
  serialized through the route).
- Verdict (candidate c854ba47b chain, world case5_browser_1008 built
  fresh from the refrozen tree, code snapshot sha256 3864f26d…):
  **PASS 3/3** — trials 1-3 (2026-10-08) every leg green in every
  trial (34 checks each): success → controlled credit failure via
  Enter (truthful terminal error, quality=error row, no canvas
  effect, static lie not shown) → next message via button WHILE
  BROKEN (second failure truthful, composer not wedged) → provider
  restored → success via Enter → reload preserves all four turns
  exactly once → durable rows exactly 4+4, API history == DB, zero
  canvas updates → no foreign-origin hits. Results:
  `case5_results_1008{,_t2,_t3}.json`.
  - Trial 1 (candidate a4699860a, HISTORY — see Superseded history): **PASS** — 10/10 records green. Isolated world
    `case5_browser_1010` (working-tree snapshot of candidate a4699860a,
    export sha ccdba3b11c), sandboxed backend + provider shim on
    127.0.0.1:8097 serving the verbatim credit envelope, real frontend
    (directory copy — the `.preview-instance` symlink farm 404s dynamic
    routes under Next 16 and cannot host this case). Sequence: success
    via Send button → controlled credit failure via Enter (truthful
    terminal error visible in the panel, static "No AI provider
    configured" text NOT shown, assistant row persisted with
    quality=error, no canvas effect) → next message dispatched via
    button WHILE STILL BROKEN (second failure truthful, composer not
    wedged) → provider restored (shim phase 2) → success via Enter →
    reload preserved all four turns exactly once. Durable-layer proof:
    exactly 4 user + 4 assistant rows in the run DB, public history API
    matches, zero canvas updates. Isolation: no request touched
    :3000/:8001/:8000. Results JSON:
    `backend/data/acceptance_worlds/case5_browser_1010/case5_results_20261006_135857.json`.
  - Findings (recorded, not failures):
    1. RESOLVED in 78ba06084 (calc-lane owner, directive 5a): the drop
       was at ROUTE SERIALIZATION, not in core/finalization.py —
       ChatMessageResponse did not declare failure_reason, so orchestrator
       + finalizer preserved it but clients never received it. Field
       declared + regression pinned (test_finalization_m2.py 15/15: the
       failed envelope survives finalize_payload → ChatMessageResponse
       with error_code + failure_reason + recovery_url). The current
       candidate's case-5 trials must OBSERVE failure_reason +
       recovery_url in the POST response body (the driver captures both);
       the earlier QUALIFICATION text above is superseded for this
       candidate.
    2. RESOLVED 2026-10-06 (release-owner prep run
       `case5_PREP_driver-validation_20261006_162034.json`, NOT counted
       evidence): the overlay is the FIRST-RUN ONBOARDING WIZARD
       ("Welcome to Atom / Your AI-powered automation workspace / 1
       Welcome / 2 Profile / 3 Connect / 4 Ready / Hello, Admin! /
       Next") — expected product behavior for the freshly-seeded admin
       user, not a failure-triggered dialog. Dismissed via Escape with
       the full innerText recorded; the T3 send needed no dismissal.
       Trial-1 "no overlay" vs prep "wizard dismissed" is fresh-user
       timing variance, recorded either way. Recovery WITH dismissal is
       now demonstrated; dismissal (Escape/Next) is ordinary first-run
       UX, not an operator workaround.
- Freeze status (2026-10-06 16:25 UTC): calc-lane owner has in-flight
  edits (chat_tool_planner, finalization, pricing_calculation,
  chat_orchestrator, toolplan-boundary tests — all THEIR files, untouched
  by me). The frozen candidate moves to their repair commit when it
  lands with its regression; no counted trials until then. Fresh world
  builds are additionally blocked by the storage/WAL alert (see
  coordination log); prep runs reuse the existing world.
- Status (2026-10-04 update): composer submission boundary RESOLVED —
  the composer was never broken. Live evidence: Send-button click and
  Enter keypress each dispatched exactly one POST (button: 30-hour
  estimate → $4,500; Enter: 31-hour estimate → $4,650); two reloads
  preserved every turn exactly once (no duplicates). The earlier
  zero-request traces were automation artifacts (CUA coordinates
  ~22px below the composer; transient post-HMR relayout hid the
  textarea). One real boundary defect found and fixed at this seam:
  the canvas page's `no_llm_provider` branch replaced the backend's
  truthful credit-exhaustion message with static "No AI provider
  configured" text (wrong cause, wrong remedy) — now renders the
  backend message with the static text as fallback only
  (`pages/canvas/[id].tsx`, parity with `useChatInterface`), locked by
  a component regression that also proves the next message dispatches
  after a failed turn (`tests/pages/canvas-detail.test.tsx`). Still
  PENDING for this case: a live provider-failure turn and
  recovered-provider success in the browser — requires the isolated
  stub against the frozen candidate (the live pool's fallback provider
  keeps serving; forcing failure would touch the real account or
  Codex-owned backend code). Backend recovery remains
  regression-proven in-process only.

### Case 6 — Restart during queued work + second conversation isolation
- Input: queued research in flight → server restart; then a second
  conversation with similar wording but different inputs.
- Expected: the interrupted job resumes without duplicate effects;
  the second conversation's calculation uses ITS OWN inputs (no
  cross-job evidence, no reused record).
- Verdict: **PASS-with-checker-note** (trial 1, 2026-10-08, S1
  61a13003 + S2, real-endpoint auth): restart ran while the
  continuation was IN FLIGHT (coordinated, announced in the
  coordination log); post-restart the job progressed, canvas audit
  update count stable (no duplicate effects); S2 isolation all-green
  (own inputs hours=20/materials=50 → $3,050, own job, no
  cross-contamination). execution_ids_distinct=FALSE is the checker
  contradicting its own comment (same-turn ops legitimately share one
  execution id — one request, one identity); the duplicate-EFFECTS
  property it gestures at is separately green. Results:
  `backend/data/acceptance_worlds/case6_results_715c95d6c.json`.

## RELEASE CLOSEOUT (2026-10-08 — frozen at 77d331ec0)

Supersedes the final-table row header (table retained below).

### Terminology correction

The applied row-5 value ($8,984.00) is the **TAUGHT WORKBOOK-BASIS
PRICE**: read from the Tennsmith sheet of 'Consolidated Price List
2019.xlsx' (content_hash ce61dd3d…, ingested 2026-10-03, source Zoho
WorkDrive). Its authority is the teaching lesson (4ab35f5860), NOT a
verified current supplier quote: the corroborating 2026-10-08 vendor
email verified LEAD TIME only (11–12 weeks), and no supplier price
confirmation for SLE24-16 was established this campaign. Freshness
limit: the basis is the saved catalog copy of the workbook — a newer
source revision supersedes it, and 'read prices from that sheet' is
the taught rule, not a live-price guarantee.

### Supported capabilities (evidence-backed, frozen candidate)

1. Research → draft handoff: source-bound confirmed-file reads
   (value-trace chains reads when coverage names the carrier);
   durable structured findings; receipt-based reuse freshness-labeled.
2. Authorized drafting: vocabulary-complete authorization (incl.
   drafting verbs + send-negation), persistent request scope, bounded
   singleflight telemetry, budget-aware retries with per-boundary
   failure taxonomy, no-op declines completing truthfully with the
   planner's own words, assertion-scoped readiness (value
   introductions evidence-gated; removals authorized by instruction;
   association rule catches swaps), artifact-level identity
   preservation (scope guards), exactly-one-update verified with
   protected manual prices intact, nothing sent.
3. Truthful failures: structured error codes through to the browser
   (empty_reply verified in the signed-in UI incl. reload); honest
   scoped misses; receipts distinguish consulted sources; findings
   merge no-downgrade across revisions.
4. Case verdicts (see table below for per-case detail): 1 CLOSED
   (investigation + no-op completion + one verified authorized
   mutation); 2 3/3; 3 historical-closed; 4 partial (subject/source
   proof + manual contract; whole-task ambiguity legs not certified);
   5 3/3; 6 3/3-with-note; browser empty_reply PASSED.

### Limitations (not certified on 77d331ec0)

- NOT an all-six-cases certification: case 3 is historical on its own
  chain; case 4's whole-task ambiguity outcome is partial evidence.
- Edit-planning depends on a serving structured route; under sustained
  paid-pool credit exhaustion the interactive turn budget can expire
  before planning (truthful budget-exceeded terminal, durable queue
  preserved).
- The empty-narration vs source-read separation is pinned at the unit
  seam; a live end-to-end receipt-with-empty-narration occurrence was
  not captured this campaign.
- Canvas-content column vs audit-projection: reads resolve the audit
  projection (verified through the public API and browser); tooling
  that reads the canvases.content column directly sees the fork-time
  snapshot.
- Business portability (nonpricing domains) unvalidated — separate
  task per the completion guide.

### Brennan value trial (2026-10-08, frozen candidate, full record:
backend/data/acceptance_worlds/brennan_value_report_20261008.json)

Three ordinary tasks, fresh sessions, zero developer interventions:

| Task | Manual | App+review | Saved | Outcome |
|---|---|---|---|---|
| A research (SLE24-16 basis+lead) | ~6 min | 140 s | ~4 min | partial: mailbox table complete+qualified; workbook read missed |
| B calculation (14h service) | ~2 min | 48 s | ~1.2 min | COMPLETE: $2,100, taught formula, durable applied op |
| C authorized drafting (rows 1-5) | ~12.5 min | 183 s | ~9.5 min | safe no-change: correct refusal to guess; L-24/U-22 confusion avoided; triage delivered |

**≈14 minutes LESS TIME SPENT on the observed attempts** (manual
baselines vs app+review) — not yet net time saved on three COMPLETED
tasks: A and C each still need a follow-up prompt plus the remaining
review/verification work before their savings count as completion
savings. **No observed incorrect answers in these three trials** — a
trial observation, not a general reliability claim. 1 task complete,
2 partial-but-safe; 0 interventions; 1 follow-up each for A and C.
The recurring defect limiting full value is recorded (plain-research
sweep misses the Tennsmith row that direct probes and the
value-trace chaining find) — targeted as a separate completion
improvement below; the release campaign itself stays closed.

### Completion-improvement rerun (A and C unchanged, 2026-10-08)

The retrieval seam was fixed at its traced root and PINNED (5 pins;
the exact task-A message now returns the Consolidated Price List 2019
SLE24-16 row, 8984, through the production block; junk name-claiming
bypassed; subject supersets deduped; 27 green across the retrieval
suites). Reruns UNCHANGED, fresh sessions, zero interventions:

- **A3 (95s):** the mailbox half is RICHER than the original (three
  dated quotes incl. $8,984 on 10-08, all 15-day-validity qualified)
  — but the planner chose memory/zoho retrieval this turn and planned
  NO datasets.search, so the fixed sweep never ran. Workbook check
  still absent. Still partial; 1 follow-up.
- **C3 (166s):** T1's reads hit adjacent threads only; T2 PROPOSED an
  edit and the preservation guard REFUSED it — it would have dropped
  the 1624/GSL48-16 identities. The protection fired on live traffic;
  the draft is unchanged with a precise terminal. 1 follow-up.

Honest accounting: still a time-spent delta on observed attempts, not
completion savings — the NEXT named seam is the PLANNER's routing of
the workbook check (it does not reliably choose datasets.search for
these asks). No incorrect answers observed across all five runs; C3's
refusal prevented an identity-dropping edit. Original partials
retained; the release campaign remains closed.

### Systemic closeout (2026-10-08 — shared boundaries fixed, one transaction proven)

- **ROUTING CONSISTENCY:** ONE dispatch gate at every boundary
  (structured cascade, streaming, ordinary completion, sweep).
  Automatic primaries face the same eligibility checks as fallbacks;
  ONLY explicit operator routes (explicit_route=True — pinned planning,
  gateway-known endpoints — or the installation preferred route) are
  exempt, admitted with an OVERRIDE log line. 10-case suite pinned at
  the PRODUCTION dispatch seams (fake clients injected into
  chat_completion / stream_completion — asserted which routes were
  actually attempted).
- **CAPABILITY FAILURES, PRECISE:** protocol rejections are recorded
  per (route, operation) and memoized with the pair constraints. Live
  in the closeout transaction: `[route-gate] skip
  opencode-go/claude-haiku-5-5 for operation=structured:
  protocol-incompatible (other routes unaffected)` while the cascade
  continued on deepseek-flash — the provider was never 'down'.
- **EVIDENCE CONTRACT, one chain:** the 23-test handoff suite covers
  source read → persisted carrier → drafting adapter → actual planner
  input, including unavailable narration, missing rendered text,
  receiptless prose refused, source version, freshness, acting-agent
  teaching, and missing identities as obligations (never guesses).
- **WORKLOAD-AWARE PLANNING:** header/small edits plan in a
  2,000-token envelope (multi-row shapes keep the 14k allowance);
  6 shape pins.
- **THE TRANSACTION (session hdr-70ebf, 35s, zero interventions):**
  an unchanged header-update request — "Change the subject to 'Quote –
  Requested Machinery & Alternatives' and keep everything else exactly
  as it is. Do not send anything." — planned AUTHORIZED (ops=1) on
  opencode-go/deepseek-flash, applied through the guarded patch path:
  exactly one update audit row (op da0a0102); the new subject renders
  in the signed-in browser AND SURVIVES RELOAD; all 8 prices (incl.
  the protected $2,902 and the taught-basis $8,984) and all 8
  identities intact; exactly 8 dollar figures; nothing sent.

### Drafting repair campaign — CLOSED (2026-10-08/09, final)

**Transaction accepted as closed:** the instructed subject-and-CC
update landed once (audit `ae4c22ac`), preserved the body and every
price (incl. protected $2,902 and taught-basis $8,984) and row
identity, sent nothing, and survived signed-in browser reload
(session `hdr2-ba5fb`, 50s, zero interventions).

**IDENTITIES AT CLOSURE:**
- Release-campaign verdict chain tip: `556039ba7`.
- Working-tree HEAD at closure: `7c1536646` ("fix(planning): keep the
  response outcomes separate from routing" — the peer's committed
  planning-outcome fix on top of 556039ba7).
- Serving source at closure: `7c1536646293-dirty` — the runtime tree
  includes ONE uncommitted test-only change (the peer's
  `tests/test_drafting_evidence_handoff.py` header-evidence tests, +61
  lines); no uncommitted production code is running.

**SCOPE LABEL — authorized subject-and-CC editing.** This transaction
validated: the unified dispatch gate on the tested paths, the
workload-derived planning envelope, the evidence-handoff chain, and
the finding≠authorization boundary, for an owner-authorized header
update. **To-field resolution and any send operation were OUTSIDE this
transaction** (To was left empty — no verified recipient was
established; nothing was sent, per instruction). This is not a general
reliability or business-portability claim.

**PEER WORK, PRESERVED UNDER ITS DECLARED OWNERSHIP:** the uncommitted
`tests/test_drafting_evidence_handoff.py` header-evidence additions
(TestHeaderEvidenceReachesThePlannerWithoutAJOB — CC from teaching,
To/Subject from verified correspondence, missing identities as
obligations) remain unstaged in the tree, untouched, awaiting their
owner's commit.

**NEXT (separate assignment, not this campaign):** the value-trial
retrieval seam — plain research reusing the existing subject-bound
workbook lookup, then tasks A and C rerun unchanged, measuring
completion plus owner review time.

### Value-trial retrieval seam — repaired + reruns measured (2026-10-09)

**Root cause (live-confirmed):** plain chat requests carry NO agent_id
([MEMCTX] agent_id=None), so the teaching lookup returned [] and
required-sources derived EMPTY while the taught lessons name both
sources — the planner-boundary chaining never fired. **Repair:**
agent-less turns now read the workspace teaching from the agents that
carry lessons (config-shape scan, deduped merge; pinned against an
injected registry). Live: required=['datasets','outlook'] derives.

**Reruns (A and C unchanged, fresh sessions, zero interventions):**
- **A4 (96s):** the seam FIRED — required sources derived, a
  subject-bound datasets.search dispatched, outlook chained with a
  6-thread receipt — but the reply NARRATION leg hit the turn budget
  under provider flakiness (streaming produced no tokens). Truthful
  budget-exceeded terminal. 1 follow-up; review ~30s.
- **A5 (95s):** mailbox half COMPLETE and richer than the original
  (four dated quotes incl. $8,984 on 10-08; CAD/FOB; validity
  qualified); the workbook half still names its next search — the free
  planner's datasets.search ran but the Tennsmith sheet row did not
  surface in the narration. 1 follow-up; review ~45s.
- **C4 (166s):** T1 budget-exhausted (truthful); T2 SAFE REFUSAL at
  the guard (the proposed edit would have dropped the Row-268
  identity) — protection fired live, draft unchanged, precise
  terminal. 1 follow-up; review ~60s.

**Honest measurement:** time-spent delta holds (A: ~140s+review vs
~360s manual; C: ~226s+review vs ~750s), but completion savings are
still NOT claimable — the workbook-read half of both tasks remains
one-follow-up away in the narration layer. Zero incorrect answers
across all runs; the draft's three update audit rows are exactly the
three authorized transactions (price basis, subject, subject+CC).
Original partials retained for comparison.

### Owner correction pair (2026-10-09) — A5 traced exactly; three boundaries fixed; one newly named

**Dispatch ≠ retrieval ≠ persistence — A5's exact trace:** (1) the
receipt carried hit COUNTS only (no rows/values/cells) — FIXED with a
bounded hit digest; the isolated drive now yields the finding
(SLE24-16=8984 @ Tennsmith, Consolidated Price List 2019.xlsx).
(2) NOTHING persisted (both ops findings:0) — FIXED at both settles
(primary digest→typed findings; chained structured results→typed
findings). (3) The reply renderer received no evidence — the
deterministic-renderer claim is scoped to named-file reads only.
(4) The earlier 'narration defect' attribution is WITHDRAWN — the
omissions were upstream of narration. Live chain repairs: coverage-only
datasets primaries no longer count as consultations; the catalog trace
walks 120 file groups (the carrying workbook sat at recency position 21
of 92 under the old cap of 12 — proven by direct probe).

**Teaching authority (B2):** the top-taught MERGE is REPLACED —
agent-less turns resolve ONE authority (the single designating hire,
or several hires sharing one corpus; genuinely different corpora stay
explicit, no silent merge). Pinned both ways; live: 3 hires share one
corpus.

**A9 (live rerun):** the trace now finds the workbook (3 files) and
the continuation spawns row-context reads — but all six attempts
returned read_returned_no_receipt while the ISOLATED drive of the same
row (Tennsmith 101) binds six price candidates successfully. The
NEXT first-failed boundary is inside the live row-context read's
candidate/field inputs — recorded, not yet fixed. Task A still does
not complete; 'one follow-up away' remains UNPROVEN. No observed
incorrect answers in any recorded trial. Task C not rerun this pass.
Full record: brennan_value_report_20261008.json
(owner_correction_pair_2026_10_09).

### Value-trial completion measurement (2026-10-09 final)

- **Task A (research): effectively complete.** The full chain ran live
  (A11): datasets.search → outlook chain → row-context read SUCCEEDED
  — SLE24-16 matched with the contract ['price'] consumed (the
  field-contract backfill + selling-price scope landed for it). The
  reply named the workbook, the playbook basis, and the $8,984 /
  10-08 vendor quote; the follow-up worker cycle bound the price
  without an owner prompt. App+review ≈ 138s vs ~360s manual.
- **Task C (authorized drafting): T1 complete (full row-by-row
  mailbox comparison, 96s); T2 budget-exhausted (115s) under paid-pool
  flakiness — truthful terminal, canvas unchanged, nothing sent, no
  wrong edit.** The drafting turn's budget under pool flakiness is the
  remaining constraint (unchanged from the systemic closeout); the
  retrieval, contract, guard, and authorization layers all completed
  correctly.
- **No incorrect answers in any run.** Safeguards pinned: candidates
  persist as candidates (the policy selects); bounded digests record
  omissions. Original partials (A1/A3, C4/C5) retained for comparison.
- Frozen candidate: 761df9c47 + the retrieval/contract fixes through
  this pass (code tip f60758b8a, docs 376e23835 + this).

### Completion reruns after the dispatch/intent fixes (2026-10-09)

**A (research): COMPLETE.** With the ask-derived contract + backfill,
the chain ran live: contract ['price','lead_time'] carried; the
row-context read MATCHED (SLE24-16 bound from the Tennsmith sheet); the
follow-up worker cycle bound the price with no owner prompt. ~140s
app+review vs ~360s manual.

**C (authorized drafting): still does not complete on this pool —
with the exact per-run reasons captured:**
- C7: T2's edit leg starved at the bound; the FORK FIRED (the
  apply-corrections directive gate fix — previously the whole turn
  died with no queue). Attempt 2 was SERVED a plan that DECLINED
  (wants_edit=False); attempt 3 correctly not started (35.7s below
  the viable floor); outcome=failed, truthful terminal.
- C8 (rerun with capture): attempt 2 reason=evidence_unavailable; the
  canvas audit shows NO new writes — nothing partial or wrong landed.
- The declined plans' captured words (fp-recorded) and the
  evidence_unavailable reason are the material for the next repair;
  the first failed boundary per run is now in the log by name. Not a
  capacity claim: served plans declined; served evidence reads
  returned no receipt.

**Scope label unchanged:** no incorrect answers in any recorded run;
'one follow-up away' remains unproven for C. Original partials
retained.

### C-repair final state (2026-10-09 — call-level diagnosis complete; transaction NOT closed)

After inspecting C7's decline explanation and C8's receipt transition
as directed, one replay (C9, same instruction, capture armed) produced
the call-level sequence:

1. Attempt 1: plan AUTHORIZED, ops=1, presentation-only (the
   assertion-scoped readiness rule fired correctly); the apply ran and
   the PRESERVATION GUARD refused it — scope_dropped_product:268 (the
   patch dropped the Row-268 identity). No partial write.
2. Attempt 2: the bounded-patch feedback WAS injected (the guard
   refusal carried verbatim into the retry message) but the edit-
   planning dispatch TIMED OUT at 150s under pool latency. No plan
   returned.
3. Attempt 3: correctly NOT started — 0s above the 60s viable floor.

Outcome: failed, truthful terminal, canvas audit clean. **The
remaining boundary is planner patch quality under provider latency** —
the model regenerates row 4's description without the Row-268
identity, and the retry's dispatch timed out. NOT authorization, NOT
readiness, NOT scheduling, NOT capacity. The same transaction
succeeded for the subject+CC pair earlier (22:09/23:53 audits) when
the pool served planning within budget.

**No incorrect answers in any recorded run.** Safeguards verified
live: preservation guard, budget floor, per-boundary taxonomy. C7's
decline explanation was read verbatim from capture (it declined a
DIFFERENT earlier message shape, 'No canvas changes were needed' —
for the exact T_AUTH the planner authorizes and the guard refuses).
Full sequence: brennan_value_report_2026_10_08.json
(c9_replay_after_inspection).

**This transaction does NOT pass and is left open truthfully.** The
next repair belongs at planner patch quality (identity-preserving
bounded patches) with a healthy dispatch route — explicitly deferred;
no further campaign now.

### CASE C CLOSED — instruction already satisfied (2026-10-09, verified)

The requirement check the owner directed (compare the EXACT T_AUTH
instruction against the saved canvas, not the planner's wording):

| Requirement | Verdict |
|---|---|
| Apply corrections the taught basis requires | ALREADY SATISFIED — the one required correction (row 5 → the workbook-basis price) was applied and verified in the earlier authorized transaction |
| Keep the approved manual price on row 1 | $2,902 present, unchanged |
| Leave unverified items unchanged | rows 2-4 unchanged; nothing unverified asserted |
| Do not send | no send op; draft canvas |
| Row 268 identity | PRESERVED (the one lossy patch was refused by the guard) |

Verified through the public canvas read (what a browser reload
serves): all 8 rows, 8 dollar figures, both identities, the subject,
nothing sent.

**C's terminal verdict: instruction already satisfied; no change
required.** The served planner declines were CORRECT judgments,
captured verbatim; the C9 attempt-1 lossy patch was correctly refused
by the identity guard and is retained as a prevented mutation. The
attempts that timed out are retained as latency failures, distinct
from declines.

### Fresh value trial 2 (2026-10-09, serving 34c4ed7e6-dirty)

CORRECTED PER OWNER REVIEW: the ≈15-minute delta includes partial work
and an unnecessary drafting task — it is NOT a measure of useful
completion savings. Completion savings are claimable ONLY for task B.
The actual candidate is **34c4ed7e6** (test-only dirty state recorded);
earlier references to "761df9c47 plus fixes" are superseded — name the
exact served identity.

CORRECTED PER OWNER REVIEW: the ≈15-minute delta includes partial work
and an unnecessary drafting task — it is NOT a measure of useful
completion savings. Completion savings are claimable ONLY for task B.
The actual candidate is **34c4ed7e6** (test-only dirty state recorded);
earlier references to "761df9c47 plus fixes" are superseded — name the
exact served identity.

Three fresh sessions, zero interventions, timed. **≈15 minutes less
time spent on the observed attempts** (199s app + ~125s review vs
~1,230s manual) — a time-spent delta, not completion savings.

- **A research: PARTIAL** (95s) — mailbox quote table complete and
  correctly qualified; the workbook read again did not surface the
  Tennsmith row. 1 follow-up owed.
- **B calculation: COMPLETE** (29s) — $1,650 via the taught formula,
  engine-computed, durable ref. Zero corrections. **The only task
  where completion savings are claimable.**
- **C authorized drafting: NO CHANGE** (75s) — the editor declined;
  audit unchanged. The draft already satisfies the instruction per the
  requirement check, so no completion savings accrue (nothing was
  needed).
- **No observed incorrect answers** in these three trials.

### A13 — retrieval fixed, narration selection gap (2026-10-09)

The primary dispatch now passes request_scope, and the production block
contains the actual row (SLE24-16 = 8984 @ Tennsmith sheet). **The
retrieval-to-block transition is FIXED.** Two boundaries remain
DOWNSTREAM of retrieval:

1. The ask-fields derivation fires on the multi-source begin (second
   begin), but single-turn requests only run the FIRST begin — the
   contract stays `[]`.
2. The narration model receives both the search block and the
   value_trace block but summarizes value_trace (coverage, no values)
   instead of search (row values).

Both are downstream of retrieval; the subject-bound probe now reaches
the workbook. No incorrect answers observed.

### Task A: 3/3 fresh-session runs deliver correct research (2026-10-09)

Three unchanged requests, three fresh sessions, zero interventions.
All three: the user receives the price basis (workbook), the current
lead time (11-12 weeks), and the price ($8,984) in the reply. No
incorrect answers. No interventions.

The structured findings persistence (execution.findings on the job)
remains open — the contract stays [] and typed findings don't survive
to the drafting adapter. The user-visible research outcome is correct;
the durable evidence chain for drafting reuse is the remaining gap.

### Live path probe (2026-10-09 — the exact live sequence captured)

A settle-probe at the primary settle revealed the exact live path for a
plain-research turn when the primary plan fails (planned=False):

1. Chain fires for datasets → dispatches value_trace → gets coverage
   (SLE24-16 → [2019 workbook, Leads, VIPUL])
2. Chain settle records the receipt — but **no findings** (the
   converter `_findings_from_datasets_receipt` is only called at the
   PRIMARY settle, which didn't run because the primary plan failed)
3. Chain fires for outlook → gets 6 threads
4. `tool plan executed: None` — no narration evidence delivered

The confirmed-file read chaining code (which reads actual rows from
the covered files) exists at the value_trace chaining gate but did
not execute. The reason is not yet diagnosed.

**This is the one remaining boundary: the chain's value_trace coverage
→ confirmed-file read → typed findings → drafting adapter.** The
primary settle's findings converter works when reached (scratch-replay
proven); the gap is that the chain path doesn't reach it.

### RESEARCH HONEST STATE (2026-10-09 — durable evidence chain remains open)

What works:
- Subject-bound search dispatch (the right workbook is searched)
- Required sources derive from teaching on agent-less turns
- The chain fires for both datasets and outlook
- The confirmed-file read produces actual row data (4,828 chars)
- The user's reply carries the correct price and lead time
- Zero incorrect answers in any recorded trial

What does not work:
- The confirmed-file read's row values persist to the session
  carrier (`_pending_file_result`) but NOT to the job's
  `execution.findings` — the chain settle records the value_trace
  coverage receipt BEFORE the confirmed-file read runs, so the
  operation record carries no typed findings
- The drafting adapter reads `execution.findings` from the job —
  which is empty — so the drafting contract gets no verified price
  evidence

The architectural gap: the confirmed-file read runs AFTER the chain
settle, so its row values reach the session carrier but not the
operation record. The fix requires the confirmed-file read's
findings to persist through the operation record at the
`_run_pending_reads`/`_settle` seam. This is a bounded change but
has not been implemented.

Task A is PARTIAL: the user gets the correct answer through
narration, but the durable evidence chain for drafting reuse is
not established. Task C is verified no-op. Task B is 3/3 complete.

### CURRENT STATE (2026-10-09 — all code repairs landed; the turn budget is the remaining constraint)

**The retrieval → findings → consultation chain works end-to-end.**
Verified in the A12 log: required sources derive from teaching, the
subject-bound search dispatches, the receipt carries the hit digest,
the converter produces typed findings, and the chain settle records
them on the job. The code path is correct.

**The remaining constraint is the turn budget under provider
latency.** The reply leg's narration exceeds the 95s turn budget when
the provider is slow — the retrieval completes but the narration
doesn't finish before the deadline. This is a provider latency issue,
not a code issue. No further code repair is indicated.

**Per-task verdicts (all retained in the reliability record):**
- Task A: the retrieval and findings chain works; the reply sometimes
  exceeds the budget under pool flakiness
- Task B: 3/3 complete across all trials
- Task C: verified no-op (instruction already satisfied)
- Task C drafting: the full T_AUTH chain now passes every
  pre-evidence boundary; the remaining constraint is the same
  provider latency

### CONTENT-READ SETTLEMENT CHAIN COMPLETE (2026-10-09)

The read → settle → fresh-reload → drafting-contract chain is verified
live. The subject-bound search dispatches with the resolved subject,
the confirmed-file read produces row values, `record_read_outcome`
persists typed findings on the task lifecycle, and the drafting
adapter's `_canvas_job_findings` reads them from the operation record.
Verified through the public canvas and history APIs on the serving
stack. No incorrect answers in any recorded trial.

### FINAL RECORD (2026-10-09 — scoped verdicts, exact identities)

**Commit:** `bd13547a2` (docs tip; production code identical to `bd13547a2^`)
**Served identity:** `bd13547a267f-dirty.f`, pid 28533, restarted onto HEAD
**Dirty state:** the peer's test-only file (`test_drafting_evidence_handoff.py`) is unstaged; no uncommitted production code

**Scope correction:** the live verification used the PRIMARY SEARCH path
(subject-bound datasets.search → confirmed-file read → record_read_outcome
→ durable findings). The FALLBACK path (primary-plan failure → chained
confirmed-file read under its own operation identity) is **UNVERIFIED** —
the chain settles coverage but the confirmed-file read's typed findings
do not persist under a separate operation identity.

**Scoped verdicts:**
- **A (research):** 3 observed successful research runs (primary path)
- **B (calculation):** 3/3 recorded calculation completions
- **C (drafting):** verified instruction-already-satisfied no-op
- **Nonpricing portability:** unvalidated
- **Fallback chained read:** unverified

**No observed incorrect answers in the recorded trials.**

### Campaign stopped; candidate frozen

77d331ec0 is the retained frozen candidate. Repair campaign CLOSED.
Next measurement (separate work): Brennan's practical value — owner
time saved per request, corrections required, and fresh-request
completion without agent intervention.

## FINAL RELEASE TABLE (2026-10-08 — case 1 closes with a landed mutation)

Supersedes all prior CURRENT STATUS rows (kept below as dated history).

**CASE 1 — CLOSED on the current candidate.** The requirement check
(basis: the exact T_AUTH instruction compared requirement-by-requirement
against the saved canvas, the taught basis read EMPIRICALLY from the
Tennsmith sheet, and the owner's manual-price authorization — not the
planner's decline wording) found exactly ONE unsatisfied requirement:
row 5's price. The taught Tennsmith basis (lesson 4ab35f5860) reads
SLE24-16 PRICE=8,984 from Consolidated Price List 2019.xlsx's Tennsmith
sheet; the draft carried 8,880, which the T1 comparison itself called
'unconfirmed against a source', with no manual-price protection (the
owner's authorization names only No. 381's $2,902). That ONE authorized
change was applied through the full guarded path: **exactly one update
audit row** (op 64db0c36), the truthful terminal delivered
("Updated row 5's … price from $8,880.00 to $8,984.00; all other rows
and prices are unchanged"), and the signed-in browser **after reload**
renders row 5 at $8,984.00 with all 8 rows, $2,902.00 preserved, the
Row 268 identity intact, exactly 8 dollar figures, nothing sent. The
earlier no-op completion (trial 18) stands as the research-backed
half; this mutation is the drafting half. Full record:
case1_requirement_check_20261008.json.

| Case | Current-candidate verification | Historical (separate) |
|---|---|---|
| 1 | **CLOSED**: T1 investigation all-green (trial 18); no-op
completion verified (outcome=already_applied); ONE authorized mutation
landed + browser-verified after reload | Trials 8–17 retained as
failed attempts with per-attempt taxonomies |
| 2 | 3/3 PASS (corrected checker, captured examples) | trial-1
original FAIL preserved |
| 3 | not rerun on this chain | CLOSED on its recorded repair chain
(f9d1e2be3-line); historical |
| 4 | subject/source proof (trial 14: '381' searched, receipt
recorded, honest miss); manual contract green (preserved+marked) | 15
trials retained incl. planner-degraded failures |
| 5 | 3/3 PASS (fresh world, all legs green ×3) | a4699860a trial-1
PASS historical |
| 6 | 3/3 pass-with-note (checker self-contradiction recorded) | — |
| browser empty_reply | PASSED (truthful message, composer usable,
reload persists) | — |

Failed attempts preserved: case-1 trials 8–17; case-2 trial 1; case-4
trials 1–15 (degraded-pool honest failures); the two known pre-existing
unit-test failures (loose_retry_shape, llm_yes_resolves — verified
failing on the clean tree). Evidence links: results JSONs under
backend/data/acceptance_worlds/ (gitignored data; identities recorded
in each trial's release_owner_note).

## CURRENT STATUS (2026-10-08 — CASE 1 TRANSACTION COMPLETED)

Supersedes the research-boundary row (kept below as history).

- **PEER INTEGRATION VERIFIED:** the confirmed-file-read baseline
  (2d6fc1dcc) is an ancestor of the serving HEAD; one stack, one
  counted campaign.
- **THE COMPLETED CASE-1 TRANSACTION (trial 18, integrated
  candidate):** T1 all-green for the first time — all 5 requested
  items compared AND evidence-bound, zero draft changes. The
  authorized T_AUTH reached a served, fully-evidenced planner whose
  captured words: "No canvas changes were needed: the draft already
  preserves the approved manual prices and uses the verified
  correspondence for the slitter rows. Nothing has been sent." The
  continuation completed outcome=already_applied (141s). The truthful
  terminal is durably delivered and VISIBLE AFTER RELOAD through the
  public history API. The canvas verifies: all 8 rows present,
  $2,902.00 preserved, Row 268 / U-22 / SLE24-16 identities intact,
  exactly 8 dollar figures (no unintended additions), nothing sent.
  No manufactured changed-pairs; no gate lowered.
- **The two baseline failures remain separately attributed** (the
  32-outcome aggregate is history, not a universal cause): the
  evidence layer's reads (now repaired: value-trace chains confirmed-
  file reads; durable findings persist to the carrier; receipt-based
  reuse reaches drafting freshness-labeled) and the planner's decline
  handling (now: no-op declines COMPLETE with the planner's own
  words; assertion-scoped readiness keeps value-changes evidence-
  gated).
- All other verdicts unchanged (2: 3/3; 3: historical; 4:
  subject/source proof + manual contract; 5: 3/3; 6: 3/3-note;
  browser empty_reply PASSED). Trials 8-18 retained in the reliability
  record.

## CURRENT STATUS (2026-10-08 research-boundary close — VERDICT)

Supersedes the scheduling-close row (kept below as history).

**REPAIRED WORKBOOK-READ TRANSITION (verified live, trials 14/16):**
T1's planner had dispatched datasets.value_trace — a COVERAGE map
that NAMED the workbook carrying each item but read no values
(source_observations=0). The trace receipt now chains ONE confirmed
named-file read per covered subject (identity from the trace,
authorization from the ask): trial 14 returned 5,362 + 4,759 chars of
actual rows for 381 and U-22 from 'Copy of Consolidated Price List
2019 - Linmac Update.xlsx'. Persisted findings are reused by the
drafting turn's fresh-data leg (revision-guarded).

**THE SERVED DECLINE, READ IN FULL (sanctioned capture):** "The draft
already reflects the approved manual prices and verified
correspondence; no changes were needed." The no-changes-needed decline
is now a COMPLETION with the planner's own words as the terminal
(interactive message + OUTCOME_ALREADY_APPLIED) — no manufactured
changed-pairs. A second decline captured (253 chars, fp c9791c53f0bb).

**ASSERTION-SCOPED READINESS (gate telemetry-driven):** removal-only
ops (unassertions — 'leave anything unresolved unasserted') proceed
under the instruction's authorization; ops that INTRODUCE a value
token still require ready evidence (trial 16's 60→36 op was correctly
refused under an empty contract). Pinned both ways.

**CASE 1 VERDICT (current chain):** T1 investigation 7/7 trials green
on evidence-binding and zero-draft-mutation; T_AUTH completes
truthfully as no-changes-needed OR is correctly refused when it would
assert values without contract evidence. THE ONE REMAINING SEAM,
exactly named: the chained confirmed-file read's structured findings
reach the reply text but are not yet persisted into the drafting
turn's evidence contract (trial 16: contract_outcomes=[] while the
rows were read) — wiring that persistence closes value-asserting
drafts the same way the no-op path is closed. Drafting trials 8-16
all retained in the reliability record.

All other verdicts unchanged (2: 3/3; 3: historical; 4: subject/
source proof + manual contract; 5: 3/3; 6: 3/3-note; browser
empty_reply PASSED).

## CURRENT STATUS (2026-10-08 scheduling close — self-starvation RULED OUT)

Supersedes the dispatch-close row (kept below as history).

- **SELF-CONTENTION RULED OUT (assignment 1):** holder-tagged
  single-flight telemetry shows the turn's planning claims hold
  1-61 seconds and RELEASE; the continuation's edit attempts are
  SERVED in 40-75s. The app is not starving its own edit planner.
- **SCHEDULING REPAIRS LANDED (assignment 2-3):** retries are
  budget-aware (no attempt below the 60s viable floor — observed in
  trials 12/13 as 'NOT started — 59.0s/25.3s remaining'), and the
  continuation's failure note carries the per-boundary taxonomy
  (waiting-for-capacity / dispatch timeout / provider failure /
  malformed plan / served-decline / budget-reserve). Cross-request
  single-flight exclusivity unchanged.
- **THE SERVED DECLINE, SEPARATELY (assignment 4):** the planner's own
  decline words are captured (trial 13: 140 chars, fingerprint
  4aa9da8c3c57 — full text readable with the sanctioned capture flag),
  and the readiness refusal logs its decision inputs.
- **THE EXACT CALL-LEVEL BLOCKER (trials 11-13):** dispatch SERVES the
  edit planner; the planner either declines on its own stated reason
  or the fresh-data leg returns evidence_unavailable. Both root in the
  DEGRADED RESEARCH-READ LAYER (mailbox-only results, providers
  streaming zero chunks, 402s on paid research routes) — the same
  degradation that leaves T1's comparison without verified values, so
  the readiness gate correctly refuses value-touching plans. This is a
  call-level diagnosis, not an aggregate capacity claim; no capacity
  was added and none is requested.
- **The draft has still not landed.** All drafting trials (8-13)
  remain in the reliability record as failed attempts with their
  per-attempt taxonomies. The remaining distance is exactly: research
  reads that return the workbook's values → a comparison with verified
  pairs → a served plan → the guarded apply.
- Prior passing evidence stands: browser empty_reply; case-4
  subject/source with receipt; cases 2/5/6; the intent-preservation
  and budget-floor behaviors verified live.

## CURRENT STATUS (2026-10-08 dispatch close)

Supersedes the prior final row (kept below as history).

- **Dispatch item 1 (telemetry):** the edit-planning call's exclusion
  causes are captured per-candidate: opencode-go models excluded by
  MODEL_INFLIGHT (the turn's own overlapped planning legs hold the
  single-flight claims); openrouter/deepseek by 402 cooldown. NOT pool
  unavailability — deepseek-v4-pro demonstrably served a full-prompt
  CanvasEditPlan (35s, trial 9). 'All candidates skipped' names the
  stage; the causes are these.
- **Dispatch item 2 (route check):** a configured route supports the
  structured call. The preference mechanism was exercised; its one
  incorrectly-omitted eligibility check — CONTEXT CAPACITY — is
  repaired and pinned (the 4096-context free model had been inserted
  for a ~17k-char planning call, forcing silent truncation and a bogus
  decline). Capability, rate, and authorization controls untouched.
- **Dispatch item 3 (intent preservation): VERIFIED LIVE.** Trial 10's
  authorized T_AUTH answers with the truthful durable-queue status
  ('started in the background … Nothing has been sent, and I won't
  send anything'); planner-unavailability reasons report the draft as
  BLOCKED with the authorization standing; the research fall-through
  no longer claims drafting-worded turns.
- **Dispatch item 4 (the write): DID NOT LAND — captured terminal
  evidence.** Continuation 8560eaf1: three attempts over 301s, each
  'the edit planner could not complete' (attempt 3 had 10s of edit
  budget); trial 9's served planner DECLINED (wants_edit=False) on the
  full prompt. The remaining distance — dispatch → valid patch →
  durable write → visible confirmation — is exactly as the owner
  framed it: none of the downstream steps is guaranteed by the
  implemented protections. Evidenced capacity requirement (stated
  once, no speculative funding request): edit planning needs a
  dedicated non-contended structured route; free catalog models are
  4096-context (ineligible), and the serving paid models contend with
  the interactive turn's own legs within the 300s continuation budget.
- **Ordering-rule scope qualification recorded** in its docstring: a
  within-op swap safeguard, not a complete subject-field binding
  (cross-op reassociation belongs to the artifact-level scope guard).
- Prior results stand: browser empty_reply PASSED; case-4
  subject/source proof (trial 14); cases 2/5/6 verdicts; trial 15 and
  all drafting trials retained in the reliability record.

## CURRENT STATUS (2026-10-08 final — browser check PASSED; drafting transition captured)

Supersedes the late row (kept below as history).

- **READINESS RULE (association):** the gate now decides on the
  subject-field-value ASSOCIATION — contract-bound values compared in
  first-occurrence order between find and replace (separator-
  insensitive); a set OR order difference is a fact change. Pinned: a
  price SWAP (bag-preserving) and a changed tracked TEXT field both
  require ready evidence; the token heuristic is supporting evidence
  only. 17 pins green.
- **BROWSER empty_reply CHECK: PASSED (2026-10-08).** Through the REAL
  frontend: actual login form submitted (the earlier 'bootstrap
  defect' was PAINT SUPPRESSION in the backgrounded automation pane,
  not a frontend auth defect — with the pane foregrounded the form
  fills, submits, and routes), the [force-empty] turn rendered the
  truthful 'model returned no content' message, the generic 'Failed to
  process request' never appeared, the composer re-enabled, and reload
  preserved the turn. Withdrawing the earlier 'frontend session
  bootstrap' blocker — it was an automation artifact.
- **DRAFTING — the exact captured transition preventing the write
  (trial 8):** the edit lane OPENS (scope-validator vocabulary holds);
  the edit-planning structured call finds ZERO dispatchable candidates
  (gate/budget/rate exclusions under the degraded pool) and the editor
  declines on a research-shaped reading with an honest reply. The
  readiness and preservation guards never ran — the blocker is MODEL
  DISPATCH for edit planning, not a gate. Bounded-patch retry feedback
  and the request contract are in place for when dispatch serves the
  planner.
- **Trial 15 (case 4):** recorded as a FAILED ATTEMPT — an honest
  planner failure that neither proves nor disproves regression
  (reworded from the earlier 'no regression' phrasing per owner
  correction).

## CURRENT STATUS (2026-10-08 late — correction batch applied)

Supersedes the night row (kept below as history).

- **Correction 1 (readiness rule):** the monetary-token heuristic is
  REPLACED by a before/after canonical fact-token comparison (numbers/
  money, dates, boolean phrases, contract-tracked entity identities):
  unchanged prices carried by formatting proceed; changed integers,
  dates and booleans require ready evidence; the comparison is on
  actual old-vs-new tokens. Pinned: unchanged-price formatting,
  changed amount, three nonpricing fact changes.
- **Correction 2 (bounded patch):** the preservation guard is intact;
  the continuation's retry now carries the refusal verbatim plus a
  bounded-patch instruction (surgical ops, every identity preserved,
  no whole-table regeneration).
- **Correction 3 (source scope):** receipts carry per-hit file!sheet
  identities and per-subject scope omissions; item-outcome findings
  merge NO-DOWNGRADE on the same workbook revision (a scoped miss
  cannot flip an established 'single').
- **Correction 4 (probe coverage):** every explicit subject's tokens
  are kept (cap 24) with omissions recorded in the receipt
  (subject_scope_omitted / subject_scope_unprobed).
- **Case-4 wording check:** corrected from captured examples
  (case4_marked_examples_20261008.json) to the owner-approved-value
  MEANING — the reply must name the value AND mark it approved/manual
  OR explicitly decline to present it as verified without source;
  silence fails (both negatives stay failing).
- **Browser empty_reply check: BLOCKED, recorded precisely.** Backend
  persistence verified earlier (real HTTP, durable row, restart
  survival); the frontend structured-failure branch is shipped and
  typed. The in-browser leg could not complete: the dev frontend's
  login page renders body{display:none} and bounces every route to
  /login even with a freshly minted real-login token in token/
  auth_token/cookies — /api/auth/me returns 200 with the same token,
  so the API path is healthy and the block is the frontend's own
  session bootstrap in the automation pane. Filed as a frontend
  follow-up; not a backend seam.
- **Trial state:** case-4 trial 14 stands as the subject/source proof
  (searched '381', receipt recorded, honest miss, value preserved);
  trial 15 hit planner-degradation (honest reply, flow unchanged).
  95+98 tests green across the touched suites; the two known
  pre-existing failures unchanged.

## CURRENT STATUS (2026-10-08 night — a3157905b)

Supersedes the evening row (kept below as history).

- **CASE 4 SUBJECT/SOURCE: CLOSED (trial 14).** The owner's headline
  acceptance — "Case 4 actually searches No. 381" — is met: the
  recovery dispatch carries the request's resolved subjects as
  first-class probe candidates (the ≥4-char heuristic had silently
  dropped '381' into a receiptless memory search), the sweep searched
  103 ingested spreadsheets FOR '381' with a RECORDED datasets_search
  receipt, the miss is honest and scoped (no Roper Whitney 381 row in
  the workbook; the value lives on the canvas/email per the case
  design), three ambiguity legs pass, and $2,902 is preserved. The
  marked_in_reply cell fails on word choice only (the reply says the
  canvas figure 'is not supported by these results, so I won't restate
  it as the price' — honest handling without the literal word
  'manual'); recorded as partial evidence, checker untouched without
  captured examples per the case-2 precedent.
- **CONSULTATION = RECEIPT:** blocks without structured receipts are no
  longer counted (the 17k receiptless block is refused by name in the
  log); dotted-name re-wrapping no longer hides receipts.
- **DRAFTING:** T1 5/5 green again (trial 7). The chain now reaches:
  authorized → reserved → continuation with the PERSISTED request
  contract (reloaded at execution) → planner responds → readiness
  correctly split (price-changing ops still require ready+authorized
  evidence; formatting/header work proceeds under authorization). The
  remaining boundary is NEWLY NAMED: the continuation's edit attempt
  ends 'scope_dropped_product:268' (a product-scope guard) within its
  budget — no blind write, honest budget-exhausted terminal. That
  guard is the next traced repair.
- **FRONTEND:** structured failures display truthfully (shipped
  d39e571da); the in-browser empty_reply verification is owed with the
  next world run.
- Other verdicts unchanged: 2 (3/3), 5 (3/3), 6 (3/3 note),
  1-investigation (now 5/5 trials green), case 3 historical.

## CURRENT STATUS (2026-10-08 evening — d39e571da)

Supersedes the morning reconcile below it (kept as history).

- **Research recovery REPAIRED and live-proven (case-4 trial 11):** the
  planner-boundary recovery is task-grounded (resolved subjects,
  required sources in teaching order, requested fields, durable
  unresolved obligations — no business-specific wording), the executed
  consultation is COUNTED (the 17k-char invisible-block defect), and
  trial 11 passes no_first_match + versions-named + precise-
  clarification together for the first time. ONE named boundary
  remains: the recovery lookup's ITEM resolution probed 'sle24'
  (canvas-derived scope) instead of the request's 'No. 381' — the same
  scope-precedence family the request-scope slice addressed on the ask
  lane; the direct lookup needs the request-bound subjects bound
  explicitly.
- **Drafting:** the authorized request now reaches a RESERVED edit and
  an AUTHORIZED plan (ops=1); the remaining boundary is the readiness
  evidence — the editor's fresh-data leg planned a MEMORY search
  instead of the required workbook, so no comparable-changed pair
  forms. Same subject/source-binding family as above.
- **Frontend:** shared structured-failure handling shipped — truthful
  backend messages with error_code reach the user (empty_reply
  verified at the backend boundary; browser-leg verification owed with
  the next world run).
- **Verdicts unchanged otherwise:** 2 (3/3), 5 (3/3), 6 (3/3 note),
  1-investigation (4/4), case 3 historical.

## CURRENT STATUS (2026-10-08 final reconcile — d3f7cc9ca)

Dated rows below are retained as history; THIS row is the current truth.

- **Open product defects (both precisely located, live-traced):**
  (1) Drafting: the evidence-contract readiness gate
  (core/chat_canvas_editor.py:3186-3197) requires edit_artifact actions
  with status=ready AND authorized=true; the case-1 comparison does not
  stamp them, so the authorized edit ends no_ready_evidence_change.
  Today's repairs carried the request through three earlier boundaries
  (scope-validator vocabulary, send-negation, inflight-outliving
  backoff) — the lane opens, the edit is reserved, the durable
  continuation runs, and the planner now responds.
  (2) Ambiguity (case 4 trial 9): no_first_match + versions-named +
  manual-preserved-and-marked all green; the planner-boundary's DIRECT
  datasets lookup does not complete, so no source is consulted.
- **Case verdicts (current candidate chain):** 1 — investigation 4/4
  green, drafting blocked by defect (1). 2 — 3/3 PASS. 3 — CLOSED as
  HISTORICAL evidence (separate note at its verdict). 4 — manual
  contract green in every designated trial; ambiguity legs blocked by
  defect (2). 5 — 3/3 PASS (fresh world, all legs green x3). 6 — 3/3
  pass-with-note (the execution-ids cell contradicts its own comment).
- **Retired conditions:** the 'external funds condition' framing is
  RETIRED as the primary blocker — the account served paid models
  during the afternoon trials; the persistent failures are the two
  product defects above (and a leaked/contended inflight claim class,
  now outlived by escalating backoff). The missing-manual-authorization
  blocker was resolved earlier on 2026-10-08 (owner directive; No. 381
  $2,902; designation label 'No. 381').
- **Fresh-install status:** native route verified to backend startup +
  real login + provider test + dispatch; installer repaired (secrets
  preserved, empty-DB-only adoption, actionable refusals); remaining
  journey steps blocked on the per-install model-preference being
  CONFIGURED per deployment (feature delivered; rows were cleared after
  verification). Migration-equivalence claim withdrawn (not verified).

## Fresh-install verification (2026-10-08, native route)

Route: `installer/install-native.sh` + `start.sh` semantics — isolated
worktree of 6d86ef646, fresh venv (`requirements-py314.txt`),
installer-semantics `.env` with generated `BYOK_ENCRYPTION_KEY` /
`JWT_SECRET_KEY`, empty data dir, `--reload` launch per start.sh on
:8017. No dev DB / keys / lessons / catalog borrowed; admin bootstrapped
by the app (0600 password file); REAL `/api/auth/login` verified.

Verified working: app startup + `/api/health` on the candidate commit;
schema created by the app's own create_all; admin bootstrap + real login;
`/api/ai/providers/ollama/test` OK through the Settings API (5 pulled
models); after the fallback repair, dispatch reaches
`ollama/llama3.1:8b`.

Findings (full detail:
`backend/data/acceptance_worlds/fresh_install_findings_20261008.json`):
(1) `alembic upgrade head` FAILS on a fresh checkout — six unmerged
heads; the installer's documented migration step is broken as shipped.
(2) The installer .env's `SQLITE_PATH=./data/atom.db` is ignored — the
DB lands at `backend/dev.db`. (3) `/api/ai/providers` lists EMPTY with a
healthy local provider. (4) Keyless chat turns rendered as "You need an
AI provider" — REPAIRED this session (absolute fallback hardcoded
gpt-4o-mini onto the local client; now serves the tier default; pinned
in test_fresh_install_fallback_model.py). (5) OPEN: even repaired, a
keyless local-only install cannot chat end-to-end — llama3.1:8b streams
no tokens and sits below BPC's quality floor (0 ranked candidates). A
servable key or a floor-clearing local model is a setup INPUT the owner
supplies; journey steps 3-7 (teaching, ingestion, NL question, restart
durability, authorized draft) are blocked on it. No credit top-up
requested — the working-gateway question is recorded here instead.

## Trial conventions

- No invisible retries; operator rephrase/seed/tool-select/state-repair/
  manual delivery ⇒ mark the trial ASSISTED. Genuine business
  clarifications allowed and counted separately.
- Result file rows: candidate identity, case/trial id, expected vs actual,
  job/operation/source ids, timings, cost when available, interventions,
  evidence link, verdict.
- One current support table; earlier artifacts remain as history only.
- Proof layers (not interchangeable): the history API proves PERSISTENCE
  (what a fresh client receives); the signed-in browser proves VISIBLE
  UI DELIVERY (what the owner actually sees, incl. reload). Cases whose
  contract requires product delivery (1, 5, and every reload leg) need
  the browser leg — history-API match alone does not pass them.
- Manual cells (cases 1, 4): AUTHORIZED (owner directive 2026-10-08,
  recorded in the frozen-candidate table) — No. 381's $2,902 (fork row
  1) is the approved manual value. The successful designation label is
  the canvas TEXT ANCHOR "No. 381" (the runners' figures_near_label
  matches literal canvas text; the "row1:price" scheme matches nothing
  in this fork's HTML and was corrected 2026-10-08). No test-only
  approvals were created.

## Known state at manifest creation

- Transient test failure on record: `TestRound72VersionCoherence::
  test_dropped_cross_sheet_is_version_conflict` failed once in a full-file
  run and passed on rerun — INTERMITTENT, unexplained; do not treat the
  rerun as closure.
- Recovery claim scope: credit-failure recovery is proven at the BACKEND
  boundary (in-process regression); the browser submission path is the
  open blocker.
