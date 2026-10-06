# Brennan release manifest — fixed six-case suite (2026-10-06)

Per `BRENNAN_FIRST_PRODUCT_COMPLETION_PLAN_2026_10_06.md`: the cases and
expected outcomes are recorded BEFORE further fixes; the suite runs only
after the browser submission blocker is resolved, against a frozen
candidate. Three trials per case, same candidate; every trial reported.

## Frozen candidate (fill at freeze time)

| Field | Value |
| --- | --- |
| Commit | **a4699860a** (2026-10-06) — carries e7cc7c893 (round-75 calculate lane) + 81a6fd867 (composer truthful-error rendering + this manifest) + a4699860a (backend credit-failure detector, committed on owner authorization; implementation is the backend owner's). Working tree clean of tracked modifications except `frontend-nextjs/next-env.d.ts` (generated churn, excluded). |
| Serving source | case 5: isolated acceptance world (snapshot of this tree), backend under the seatbelt profile with provider shim on 127.0.0.1; pid/ports recorded in the run's results JSON. Cases 1-4/6: dev stack, recorded per trial. |
| Configuration | ATOM_TASK_LIFECYCLE_ENABLED=1, CHAT_FINALIZATION_M1=1, CHAT_FINALIZATION_M2=1 (world launch flags); case 5 model egress = local shim only, never the real account |
| Database | case 5: per-run atom.db seeded from the world fixture inside `backend/data/acceptance_worlds/<world>/runs/run-*/`; identity (sha256) recorded in the results JSON. Cases 1-4/6: dev DB + pre-run snapshot. |
| Fixtures | case 5: seeded admin user + email canvas via the app's own model path (finish_line World.seed pattern). Cases 1-4/6: disposable fork canvas (not the original), trained agent 9837ec71, lessons: BurrKing basis / Tennsmith basis / Service estimate |

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
- Verdict: [ ] [ ] [ ]

### Case 2 — Subset request + "other machinery" follow-up
- Input: owner names a SUBSET of items; follow-up asks about "the other
  machinery".
- Expected: the subset does not expand to the whole canvas; the follow-up
  resolves to the remaining items (or asks precisely which); scope stays
  the owner's requested scope throughout.
- Verdict: [ ] [ ] [ ]

### Case 3 — Taught formula, missing input, answer, changed-input recalc
- Input: "Estimate this service job using our taught rates." (no inputs);
  owner answers "17.5 hours, no materials"; then "recalculate — 12 hours".
- Expected: ONE precise question for the missing inputs; computation via
  the engine ($2,625 then $1,800); each recorded as its OWN operation with
  inputs + content-derived policy version; distinctions preserved.
- Verdict: [~] [ ] [ ]
  - Trial 1 (2026-10-06, dev stack, provider deepseek-flash via API,
    canvas-free session `c3t1-c4fb4e12`, agent 9837ec71): **SPLIT —
    interaction PASS, durable recording FAIL.**
    - Interaction: PASS. One precise turn naming exactly the two missing
      inputs (hours, materials); then "$2,625 (17.5 hours × $150/hr, no
      materials)"; then "ROUNDUP(12 × $150 + $0) = $1,800". All figures
      correct.
    - Durable: FAIL. The conversation's job (goal_run c5dc43ab) holds
      three `retrieve running` operations and NO calculate operations —
      and the session's chat rows carry NO published calc records
      either. Root-cause evidence: these turns dispatched through the
      LLM TOOL PLAN ("tool plan executed: datasets.calculate:…"), which
      produced narrated figures WITHOUT either leg of the calculation
      record pipeline (`_publish_calc_record` + `_record_on_job`): no
      job op, no session record, no recording warning. The
      derivation-seam lane (this morning's canvas session, job
      e0170ffb) records both — the guarantee holds on ONE of the two
      calculate dispatch paths. A correct-looking narrated figure with
      no structured record is exactly the class this suite exists to
      catch.
    - Additional finding (bounded, correctness unaffected): on the
      tool-plan path the figure-grounding guard flagged the CORRECT
      engine figures ("reply states figures the evidence does not
      contain: $0, $17.50, 2,625.00…") and ran grounded regeneration;
      final replies stayed correct. The tool-plan path lacks the
      structured-record grounding the derivation-seam lane publishes.
    - Trials 2-3 PENDING: not run against a candidate with a known
      recording defect on this path — fix first, then run all three
      trials clean (this trial stays on record as the failure it is).

### Case 4 — Ambiguous item, conflicting source versions, approved manual value
- Input: an item code carried by multiple files/versions; one row holds an
  approved manual price.
- Expected: ambiguity → clarification (never first-match); conflicting
  versions → coherent-version or explicit conflict; the approved manual
  value is PRESERVED and marked; only real decisions block.
- Verdict: [ ] [ ] [ ]

### Case 5 — Provider failure then another message (browser leg)
- Input (UI): successful message → controlled provider failure (isolated
  stub or exhausted-test route, never the real account) → another ordinary
  message after failure → provider recovered.
- Expected: truthful terminal error (success=False, error_code, remedy);
  rows persisted with quality=error; the NEXT message dispatches (Send
  button AND Enter recorded separately); recovered provider succeeds;
  reload preserves history WITHOUT duplicates. A prior failed message
  must not permanently disable a new request.
- Status (2026-10-06 update): **BROWSER LEG PASSED (trial 1 of 3)** on
  the frozen candidate — trials 2-3 remain. The composer submission
  boundary is fully resolved (the earlier BLOCKED status and the
  2026-10-04 resolution evidence below are superseded by the passing
  trial).
- Verdict: [x] [ ] [ ]
  - Trial 1 (2026-10-06): **PASS** — 10/10 records green. Isolated world
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
    1. Under CHAT_FINALIZATION_M1/M2 the finalizer rebuilds the failure
       message from the execution record and DROPS the machine fields
       failure_reason=provider_credits_exhausted and
       recovery_url=/settings/billing that the ungated reply-assembly
       path sets (message text stays truthful and names the remedy).
       QUALIFICATION (owner, 2026-10-06): truthful displayed text
       passed, but STRUCTURED failure metadata did not survive
       finalization — open fix: preserve the fields through
       core/finalization.py with a focused regression.
    2. QUALIFICATION (owner, 2026-10-06) on the modal: the driver runs
       a dismiss-overlay probe before every send. In the PASSING trial
       the probe found NO overlay — recovery was uninterrupted. In the
       pre-final run (not a counted trial), a `fixed inset-0 z-50`
       backdrop with a centered dialog DID intercept clicks over the
       composer after the failed turn and blocked the Send button.
       Identity and trigger of that modal are UNIDENTIFIED; whether its
       dismissal is expected product behavior is UNRECORDED. Until it
       is identified, the passing trial proves recovery for the
       no-overlay case only; recovery WITH that dismissal is unproven.
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
- Verdict: [ ] [ ] [ ]

## Trial conventions

- No invisible retries; operator rephrase/seed/tool-select/state-repair/
  manual delivery ⇒ mark the trial ASSISTED. Genuine business
  clarifications allowed and counted separately.
- Result file rows: candidate identity, case/trial id, expected vs actual,
  job/operation/source ids, timings, cost when available, interventions,
  evidence link, verdict.
- One current support table; earlier artifacts remain as history only.

## Known state at manifest creation

- Transient test failure on record: `TestRound72VersionCoherence::
  test_dropped_cross_sheet_is_version_conflict` failed once in a full-file
  run and passed on rerun — INTERMITTENT, unexplained; do not treat the
  rerun as closure.
- Recovery claim scope: credit-failure recovery is proven at the BACKEND
  boundary (in-process regression); the browser submission path is the
  open blocker.
