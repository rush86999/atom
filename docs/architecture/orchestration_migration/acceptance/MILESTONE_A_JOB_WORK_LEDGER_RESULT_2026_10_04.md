# Milestone A — job-work ledger + reliable multi-source investigation (ZCode, round 34)

Date: 2026-10-04 · Guide: `BUSINESS_DECISION_SYSTEM_AGENT_GUIDE_2026_10_04.md` · Revised after reviewer correction (same day).
Serving identity: backend pid 29881 → restarted for the correction arc; HEAD through the chain-accounting commit; DB snapshot `atom-pre-restart-20261004-111025.db.gz`.

## Completion status (reviewer wording, binding)

> Execution tracking improved, with several live-discovered defects repaired. Milestone A remains incomplete: chained lookups lacked complete operation accounting, query/context construction could misdirect retrieval, and no single run produced evidence-backed dispositions for all eight items.

The seven defects below are fixed in source and pinned; the correction arc adds receipt-based accounting, unresolved-work query construction and chained-operation records, but the original job has NOT yet been re-run to certification after these fixes.

## Fixtures

- Original canvas `0e4defa5-a0f3-4e56-b8a7-976c0a93d4fb` — untouched; content SHA-256 prefix `f028613cf755564d`, byte-identical before and after all runs.
- Disposable fork `9d2b0f4a-4f1e-4f2b-855b-4a89f66fce6f` — same SHA; draft never edited, never sent.
- Trained agent `9837ec71-4f1b-41db-b014-119862362d44` (46 durable lessons). Guide prompt verbatim, fresh session per run (msA…msA8), real API, no operator reformulation.

## Seven defects found live and fixed (all pinned)

| # | Run | Defect | Fix | Commit |
|---|-----|--------|-----|--------|
| 1 | msA1 | `shared_tool_state` NameError — recovery block read the turn blackboard it never received | Parameter wired at the single call site | `79763c376` |
| 2 | msA1 | `_deadline` NameError — arms read another method's clock | Own `deadline` param with None-guard; pinned with a REAL TurnDeadline | `d7a17cfa6` |
| 3 | msA2 | Singleflight ledger bypass — reused executed lookups left NO retrieve operation (settle sat inside the named-file gate) | Settle follows execution, ungated | `3202021d5` |
| 4 | msA3 | Double-settle crash `running -> running` on declined lookups | `_ms_dispatched` flag | `3202021d5` |
| 5 | msA3 | Canvas-deixis false decline — correct canvas-derived query refused (canvas subject only admissible on edit-shaped turns) | `_canvas_referencing_message` predicate; stale-plan protection intact | `3202021d5` |
| 6 | msA2–msA6 | **The whole recovery block lived inside the planner-wait except handler** — unreachable on the success path it was built for | Relocated to the shared continuation; decision-point observability added | `43e851e8e` |
| 7 | msA6/msA7 | Chain re-ran an already-executed source; planning exhaustion recorded nothing durable | Executed service credited; exhaustion recorded as not_dispatched with an open re-run question | `43e851e8e` |

## Reviewer correction arc (this revision)

1. **Chained query from unresolved work** — the chain's `query=message[:200]+…` shortcut (correction 1) is removed. The chained lookup now queries the resolved item set (`_requested_targets` / stored requested items) plus the canvas subject via `canvas_topic_text` — research context only, edit authorization untouched (the chain executes on the read path with the same context keys the fresh-exec seam passes: agent_id, message, bounded history, workspace_id). With neither items nor topic derivable, the chain is skipped honestly rather than chained blind.
2. **Receipt-based accounting** — `_search_execution_receipt(plan, block)` separates DISPATCH (text/structured presence) from RETRIEVAL (structured receipts: `searched_threads`, `read_outcomes`, `source_observations`, `storage_read`/`file_read`/`structured_result`). NEGATIVE CONTROL pinned: a deliberately irrelevant result (junk filename matches, blank rows, or an error-explanation block) reads dispatched=True / retrieved=False. Seam and prefetch settles record `search_returned_no_receipt` / `read_returned_no_receipt` instead of success; `_complete` requires a receipt. Source coverage credit is receipt-based.
3. **Chained attempts get their own operation** — every chained lookup begins a lifecycle operation before dispatch and settles it on all paths (result, timeout, error, no-receipt) with receipt-derived outcomes; open questions recorded when the receipt is absent.
4. **Order-independence is INTENDED, not verified** — workbook-first was exercised live (msA6 chained datasets after datasets-text-only; the mailbox-first direction has NOT been separately demonstrated); the chain picks the first missing source deterministically.

## Metrics (corrected)

Unnecessary clarification asks: the per-run "which next?" question must be split — a next-step question after evidence is genuinely absent is workflow steering (avoidable once chaining completes both sources in-turn), while the run-3 source-identity question ("which workbook?") was a teaching-resolution failure, not a business clarification. Neither class is acceptable for Milestone A sign-off. Unauthorized edits: 0 (scope gate denied all edit attempts; all recorded as cancelled operations). Template fallbacks: 0 after fix #1.

## Supporting evidence (retained)

Preserved draft (SHA-identical fork and original across 8 runs); recorded operations incl. denied edit (cancelled + reason) and executed retrieval (`search_succeeded`, `live`, planning provenance) on goal run `2a668b6a`; five exception-class repairs pinned with a real turn deadline. Suites: 259 passed, 7 pre-existing pending-file refresh failures (worktree-baselined at HEAD).

## Remaining before Milestone A sign-off

Re-run the original fresh-session job after this correction arc: require all-eight evidence-backed dispositions, both taught sources performed-or-blocked WITH separate operation records, and no avoidable steering question. Attribution of any residual failure to model quality is premature until this run is on record.

## Round-35 live verdict (runs msA10–msA12, serving pid 35154, HEAD 6a0…guard+shape commits)

Two more deterministic defects found by the rerun — NOT model quality:
- msA10: chain query called `canvas_topic_text(canvas_context)` on a bare
  canvas-id string → whole response died to template. Guarded (isinstance).
- msA11: `_requested_targets` holds plain strings on some paths →
  `(t or {}).get("item")` killed the response. Shape-tolerant extraction.

**Negative control confirmed IN VIVO (msA12)**: the chained datasets
attempt returned 2641 chars of text with NO structured receipt and the
code refused to credit it — logged "returned NO usable receipt — the
obligation stays open". Ledger for run `17f669b4`: edit cancelled +
primary retrieve (read_failed, incomplete) + chained retrieve (own
operation, begun and settled incomplete).

**Measured status: Milestone A remains incomplete.** Both taught-source
attempts now leave durable operation records including reused/chained
execution; the reply is honest and draft-identical (SHA f028613c…
unchanged on fork and original; no sends). Not yet met: all-eight
evidence-backed dispositions in one run; the outlook source was not
reached inside the bounded turn (the re-attempted datasets chain consumed
the budget — only one chain attempt per turn); the chained operation's
execution-facts attach silently failed (op shows running, facts absent —
the `attach_operation_field` swallow in `finish_retrieval_turn`); and the
reply still ends with a steering question. First divergences were all
deterministic; the residual gaps are enumerated above, not attributed to
the model.

## Round-36 common-cause corrections (runs msA13–msA14, serving pid 40630)

Reviewer's bounded assignment executed as one writer (claimed in the
coordination doc):
1. **Persistence root cause** — the attach sat BELOW `finish_retrieval_turn`'s
   incomplete early return; every failed/chained settle persisted a fact-less
   operation row. Reproduced (begin→execute→settle→RELOAD: facts MISSING),
   fixed (attach before the completeness branches; genuine failures now log),
   outcome vocabulary extended so `search/read_returned_no_receipt` and
   `search_succeeded_empty` persist verbatim. Reload pin: chained + reused
   operations both carry facts.
2. **Receipt production at the sweep boundary** — `_datasets_search_block`
   attaches a `datasets_search` receipt (files searched / hits / tokens /
   matched files / query) via optional plan kwarg; live-verified: receipt =
   {files_searched: 94, hits: 2}.
3. **Bounded unfinished-work loop** — every missing taught source gets its
   own attempt + operation + per-attempt budget; msA14 log shows datasets
   AND outlook both attempted and receipted in one turn (outlook: 6 threads,
   3 reads); a receipt-less first attempt no longer blocks the second. A
   live UnboundLocalError (nonlocal `_tool_block`) was found and fixed by
   the run itself.
4. **Input normalization consolidated** at the loop boundary
   (shape-tolerant items, canvas-context shape, canvas-id resolution);
   no raw-message query; missing context → explicit skip log.

**Measured status (msA14)**: both taught-source attempts durably recorded
(applied, with facts); all eight rows individually accounted in the reply
(row 3 correctly untraceable until the flanger's make/model is identified);
draft SHA-identical; nothing sent. Still open for Milestone A sign-off:
irrelevant hits are recorded as retrieval with coverage_items empty (the
obligation-vs-coverage semantic split needs its completion rule — what
closes an obligation whose search succeeded but matched nothing relevant),
and the per-row traces (value_trace per model) remain the next turns'
durable work rather than same-turn execution. These are enumerated gaps,
not model-quality attributions.

## Round-37 finishing the job (same session msA14-…-9077, continued from persisted work)

Continuations of the SAME job (no fresh-session campaign): the bare
"continue" turns ran generic scans and re-asked (recorded finding: the
continuation path does not carry the job's recorded next_action into plan
context), and two response-killers were found and fixed en route
(unbound `_plan` on prefetched-block turns; the taught value_trace
refinement now drives the datasets chain when sweep coverage was
irrelevant). Executing the agent's OWN proposed searches produced the
evidence-level comparison:

**Eight-row comparison delivered (cont7, draft untouched):**
- Rows 5–7 (SLE24-16 $8,880/11–12wk, TK 1624 $8,040/4–6wk, TK Multi
  $12,838/In Stock): CONFIRMED against the Chandrakant "Quote for
  Slitter" email, Sept 18 2026, to Steve (AlumaSafway) — prices,
  delivery and CAD/FOB boilerplate cited.
- Row 8 (GSL48-16 $14,166): discrepancy PRESERVED — July 2026 Belroc
  thread shows $13,285/11–12wk; flagged as the one item to verify
  before sending, not silently resolved.
- Rows 1, 2, 4 (No. 381, U-22, No. 622): value_trace returned no other
  cataloged document — draft figures preserved as UNSOURCED, owner
  decision preserved; the manual $2,902 for No. 381 kept per lesson.
- Row 3 (Manual Flanger): FOUND in Consolidated Price List 2019.xlsx —
  the stored-data lead exists (answering the reviewer's Flanger point:
  the app investigated before asking); the exact cell read is the
  recorded remaining step.

**Durable closure:** the job ledger holds 18 operations spanning the arc
(4 search_succeeded, 4 search_returned_no_receipt, 2
read_returned_no_receipt, plus the pre-fix rows) — proposals,
invocations and outcomes linked by operation id across turns.
**Status: multi-source execution demonstrated; evidence-level
investigation delivered for rows 3, 5–8; rows 1, 2, 4 recorded as
unsourced with the exact missing fact (no cataloged document carries
them) and the next actions scoped. Not sent. Original canvas untouched.

## Round-38 continuation binding (closeout instruction executed)

**Binding fix**: bare "continue" over a job whose settled obligations
record no open questions now re-plans the session's ORIGINAL authorized
ask (the job's own authorization text) instead of reconstructing a task
from the word "continue". Live-verified across three consecutive bare
continuations (cont8–cont10, same job/session, zero operator steering,
zero permission questions): each turn executed the job's lookups
(datasets.value_trace over all eight items ran; the mailbox grep ran),
reported receipts honestly, and autonomously discovered new evidence —
the TK Multi Wheel Gang Slitter vendor thread (Chandrakant, 21-Jul)
confirming a 10%-off special offer on list price, CAD, FOB Woodstock —
while explicitly REJECTING coincidental numeric matches ($1,624.51
Victoria Shipyards invoice) as not pricing. Executed facts persist per
operation.

**Accurate status**: useful evidence gathered; independent continuation
of the authorized job is now demonstrated (no operator reformulation, no
permission asks across three turns); **plan-level convergence remains
unproven** — the planner re-selects broad sweeps rather than the
recorded next steps (open the full "Quote for Slitter" thread by message
id; read the located Flanger cell in Consolidated Price List 2019.xlsx;
grep the workbook for rows 1–4), so the last-mile reads did not execute
autonomously.

**Required wording corrections recorded for the comparison**: the
September email supports "quoted on September 18" — NOT current
availability or delivery today; the July GSL48-16 figure ($13,285,
11–12wk) is a historical alternative whose supplier/specification/terms
comparability must be established before it is treated as a direct
conflict with $14,166.

## Round-39 shell diagnosis and persistence fixes (cont11–12, pid 52818)

**Diagnosed (not assumed)**: the job was a shell because
`_resolve_or_create` binds objective/entities ONLY at creation — this job
was created by the denied edit lane with an empty objective, and settles
reconcile entities only from structured_result.requested_items which the
sweeps never provide.

**Fixed**: (1) `begin_retrieval_turn` backfills an existing task's empty
objective via revise_objective — which itself now WRITES objective_text
(previously it only handled entities/fields; live-verified: objective
bound, 11 item identities persisted). (2) chain settles pass
requested_items so the reconcile binds the resolved set. (3) value_trace
attaches a per-item receipt (item→[documents]); the settle records
per-item open questions naming the exact document to read. (4) BOTH
DIRECTIONS gate: the continuation fallback seeds only an incomplete job —
entities all covered by successful retrievals = complete = NOT restarted.

**Verified live (cont12)**: bare "continue" resumed the healed job, rows
5–8 re-grounded against the Sept 18 email, the GSL48-16 July discrepancy
surfaced for owner decision, rows 1–4 honestly no-receipt per the
training rule ("won't substitute a recalled figure"). Remaining precise
defects, enumerated: the backfilled objective wording takes the last
begin's message (singleflight) rather than the original ask; the chain's
named-file-first path skips the receipt-producing sweep (no
datasets_search/value_trace meta on those attempts); plan-level
convergence on the recorded targeted reads (Flanger cell, full-thread by
id) is still not demonstrated. Draft untouched; nothing sent; original
canvas untouched.

## Round-40 coherent correction (cont13, pid 61445)

**Scope protection**: the reconcile bound observation aliases as new
entities (8→11) and could drop tasked items on partial observations.
Observation now binds NEW DISTINCT items only (normalized-overlap check);
tasked items are never removed by observation. The 11 existing identities
remain in the old record — the canonical eight live in the comparison;
aliases are coverage, not scope.

**Receipt guarantee**: every datasets return carries a receipt;
prose-only returns are marked `datasets_prose_only` and read as
dispatched-but-NOT-retrieved. **Completion rule**: an item resolves only
by an actual content read (`read_succeeded`) or an explicit per-item
status — search success, document hits, and missing receipts resolve
nothing. **Gate loss found and fixed**: the round-39 completion gate was
silently lost (its script wrote the file but a SyntaxError aborted the
chain before commit captured it — the commit message claimed a gate the
code did not contain); reapplied and pinned.

**Live (cont13)**: the run AUTONOMOUSLY surfaced a training-based
discrepancy — the taught workbook note records No. 381 at **$3,254.00**
vs the draft's $2,902.00 — correctly flagged as "needs a source read,
not an assumption." Rows 5–8 re-confirmed with the corrected
quoted-September-18 wording. **Still not demonstrated**: the targeted
reads execute only "on your word" — the per-item questions do not
persist because the value_trace receipt requires `intent=value_trace`,
which the chain plans only when session-held items exist (they do not on
these turns), and the seed still selects the original ask (actions
empty). The binding executes the job; action-level selection of recorded
targeted reads is the remaining acceptance item.

## Round-41 durable-entity continuation (cont14–15, pid 76236)

**Delivered**: (1) role-annotated scope correction — one traceable
revise_objective per job marks entities carrying the open canvas's own
items as REQUESTED; the rest are discovered aliases/candidates, kept but
excluded from completion; (2) durable job entities feed planning — the
chain reads the persisted entities whenever session carriers are absent
(defeating-session-dependence fixed); (3) the bare-continue seed names
the unfinished REQUESTED items explicitly; the completion gate counts
only role=requested entities.

**Live (cont14–15)**: bare "continue" drove value_trace from DURABLE
entities — **Manual Flanger, TK 1624, GSL48-16 → Consolidated Price List
2019.xlsx** (the Flanger's located workbook, reproduced from persisted
state); the mailbox grep re-grounded rows 5–8; evidence scoping is
honest ("scoped to that search only — I'm not making a universal
claim"). The permission ask that remains is about DRAFT EDITING —
correctly withheld ("Don't change the draft yet").

**Still open — the last link**: value_trace coverage does not persist as
selectable per-item actions (open_work actions remain empty), so the
targeted cell read dispatches only when the sweep refires, not as a
selected recorded action. The defect is localized to the
settle→question-recording→seed-selection link. Status: **evidence-level
investigation reproducible from durable state; autonomous action-level
continuation (pending read → invocation → persisted → disposition →
not re-selected) remains the unmet acceptance requirement.** Draft
untouched; nothing sent; original canvas untouched across ALL runs.

## Round-42 receipt-to-action failure: reproduced and fixed at the boundary

**Deterministic root cause (reproduced in a scratch-DB regression, not
inferred)**: the per-item questions were gated behind settle
completeness — `[] if _complete else (...)` — and a value_trace receipt
locating a workbook IS complete (retrieved=True), so the located document
silently produced no pending action. Discovery was treated as completion.

**Fix**: `_value_trace_pending_reads(receipt)` — a module-level helper —
derives one executable question per covered item ('read <document> for
<item>') on EVERY settle, at BOTH paths (primary seam + chain), ungated.
`add_unresolved_questions`' (item, text) idempotency prevents duplicates;
a fresh-evidence exhaustion reset re-selects questions exhausted during
the broken-loop era. **Regression (scratch DB, real settlement path)**:
cont14 fixture → 3 pending reads → selected by `next_unfinished_work` →
repeated receipt adds nothing → targeted read executes (read_succeeded +
explicit status) → resolved → not selected again; irrelevant discovery
creates no false obligation. 29 ledger tests green.

**Live status (cont16–17)**: the primary-plan value_trace runs still show
`added=0 / open(actions=0)` — the coverage questions are not yet reaching
the persisted record on those settles; the next diagnosis step is the
value_trace meta attachment on the PRIMARY plan's `_result_meta` at the
exact execution path (the chain path is proven by the regression). This
is the single remaining boundary; everything upstream (durable entities,
role-annotated scope, both-directions gate) is live. Draft untouched;
nothing sent; canvas untouched.

## Round-43 boundary corrections (cont18, pid 81056)

**Delivered**: (1) retry semantics corrected — identical rediscovery
neither duplicates nor replenishes; a ONE-TIME recorded attempt-budget
migration repairs pre-fix exhaustion; a standing MATERIAL-CHANGE rule
resets only when a re-derived read targets a different source/action
(`record_unresolved` now supports set-based attempt transitions);
(2) receipt bound to the EXECUTION — the singleflight arm records the
full result meta on the turn blackboard (`primary_result_meta`) and the
seam settle falls back to it when no plan object survives; (3) the
regression runs UPSTREAM — the real `execute_tool_plan` value_trace
branch produces the receipt (fixture-backed trace) carried through the
production question derivation into settlement and selection, covering
both the normal and plan-absent paths. 31 ledger + 54 chain green.

**Live findings (cont18) — two precise boundaries remain, recorded for
the next diagnosis**:
1. The attempt-budget migration is gated behind non-empty
   extra_questions (`if extra_questions:` guards
   `add_unresolved_questions`) — a settle with no derived questions
   never runs the migration. The migration must run on every settle.
2. `tool plan executed: None` while the reply narrates a value_trace —
   narration vs invocation again: the reply described cached/prior
   results, not a fresh execution. The pending-read creation is
   receipt-driven and correct; the missing piece is a FRESH value_trace
   invocation reaching a settle.

Status: the receipt→pending-action→selection→retirement transition is
proven by regression through the real executor and production handoff;
the live demonstration awaits the migration fix plus one fresh
value_trace invocation. Draft untouched; nothing sent; canvas untouched.

## Round-44 migration-on-every-settle + transition loop live (cont19–20, pid 82486)

**Fixed**: (1) the attempt-budget migration moved into
`migrate_attempt_budgets()`, invoked by `record_read_outcome` on EVERY
settle — the previous placement inside `add_unresolved_questions` meant a
settle with no derived questions never repaired broken-era exhaustion;
(2) set-based attempt transitions REAPPLIED (lost with an earlier
failed-script edit — the migration's `set: 0` wrote nothing until now).
Pinned: a settle with NO new questions repairs the budget and the pending
read becomes selectable. 32 ledger + 54 chain green.

**Live transition (cont19–20)**: bare "continue" now SELECTS the
persisted action (open_work actions carries the question with its id),
EXECUTES the recorded next action (the agent re-ran the datasets
value_trace per the recorded text), and the attempt is durably tracked
(0→1 across the turns). The reply correctly refuses to substitute
adjacent-but-unmatched values (Menzies $5,742 Linmac L-24 ≠ U-22 bead
roller) and preserves the draft per training.

**Remaining**: the per-item coverage questions (Flanger→workbook cell
read) still require the primary-plan `value_trace` meta to reach the
seam settle — the execution meta attachment at the primary path is the
single recorded boundary between the current generic-question loop and
the per-item targeted reads. Draft untouched; nothing sent; canvas
untouched.

## Round-45/46: THE TARGETED-READ TRANSITION, LIVE (cont21–27, pid 87133)

**Migration one-time, verified and pinned**: get_task does not surface
decision_log — the original done-marker read an always-empty list and the
migration would have re-applied on every settle at cap (the reviewer's
exact concern). The marker now lives in the task revision
(attempt_budget_migrated). Pinned: repeated settles leave a normally
exhausted question exhausted; identical rediscovery replenishes nothing;
a fresh TaskLifecycle over the same store (restart) sees the marker.

**Handoff traced, disappearance point fixed**: cont19/20's value_trace
executed in the canvas-edit leg and reached settlement ONLY through the
singleflight/reuse arm — which never derived questions. The reuse settle
now derives pending reads from the blackboard's ORIGINAL receipt
(primary_receipt); regression covers the reuse handoff shape. Retry
machinery untouched thereafter, per instruction.

**Retirement wired with the right semantics**: read_succeeded with an
explicit per-item status resolves VERIFICATION-kind questions only —
owner DECISIONS are never settled by a read (pinned both directions;
search success retires nothing).

**THE LIVE TRANSITION (the reviewer's success criterion)**:
1. cont21: value_trace (canvas-edit leg → singleflight) → reuse settle
   persisted three targeted reads ("read Consolidated Price List
   2019.xlsx for {Manual Flanger, TK 1624, GSL48-16}").
2. cont23–24: the generic re-run question climbed to cap.
3. cont25: **the cap held** (no reset — the marker works); selection
   moved to targeted reads; the workbook read executed and surfaced a
   REAL discrepancy with cell provenance: SLE24-16, Tennsmith sheet,
   row 101, PRICE $8,984 vs the draft's $8,880 — flagged for owner
   confirmation, not auto-applied.
4. cont26: the Flanger targeted read EXECUTED FROM DURABLE STATE:
   "Manual Flanger — 1,631 'Price' (Tinknocker sheet, row 42, cell D42;
   also 950 'Factory Price' H42) — from the saved copy (2026-10-03),
   searched all 46 sheets; a newer version may differ" (honest freshness
   scoping). Ledger: read_succeeded, items {"Manual Flanger": "single"}.
5. cont27: the Flanger question is **resolved** ("targeted read
   executed — evidence on the operation") and NO LONGER SELECTED; TK 1624
   and GSL48-16 remain as the next targeted reads.

Draft SHA-identical throughout (f028613c…); nothing sent; original
canvas untouched. 35 ledger tests green.

## Round-47 final: queued reads finished; the complete eight-item comparison (cont28–30)

Three user-triggered continuations executed the two queued targeted
reads and retired them (TK 1624 needed one identity-match fix: the
workbook key "1624" vs the question's "TK 1624" — normalized-containment
retirement, unrelated strings never resolve; GSL48-16 then retired on
its first read). Resolution scope now records what a read ESTABLISHED
(saved-copy reads say "freshness against the live source is NOT
established" — verification-kind no longer absorbs current-price
verification). Retry machinery and the ledger design untouched
otherwise, per instruction.

### FINAL EIGHT-ITEM COMPARISON (draft preserved throughout)

| # | Item | Draft | Workbook (SAVED COPY 2026-10-03, 46 sheets) | Vendor email | Remaining action |
|---|------|-------|---------------------------------------------|--------------|------------------|
| 1 | Roper Whitney No. 381 | $2,902 (manual vendor-quote, owner-confirmed) | not carried by other cataloged docs (value_trace, token-scoped); teaching lead: Tennsmith sheet row 338 | — | **Owner decision** (manual price preserved per lesson) |
| 2 | Linmac U-22 | $1,777, In Stock | not carried | — | **Owner decision** (manual price) |
| 3 | Manual Flanger | $1,609 | **D42 = 1,631 Price; H42 = 950 Factory Price** (Tinknocker sheet) | — | Read COMPLETE, freshness-limited; **$1,609 vs $1,631 discrepancy → owner decision** |
| 4 | Roper Whitney No. 622 | $2,421 | not carried; identity historically ambiguous (8 candidates) | — | **Owner decision** (identity + price) |
| 5 | SLE24-16 | $8,880 / 11–12wk | row 101: **$8,984** (see note below) | **Sept 18 2026: $8,880 ✓** (quoted-then, not current availability) | **Owner decision** ($8,880 vs $8,984) |
| 6 | TK 1624 | $8,040 / 4–6wk | **D101 = 8,143 Price; H101 = 3,950 Factory** (Tinknocker sheet) | Sept 18 2026: $8,040 ✓ | Read COMPLETE, freshness-limited; **$8,040 vs $8,143 → owner decision** |
| 7 | TK Multi Wheel Gang | $12,838, In Stock | not carried | Sept 18 2026: $12,838 ✓; **July 21: 10%-off-list special offer** condition | Verified vs quote-then; offer condition recorded for the owner |
| 8 | GSL48-16 | $14,166 / 6–8wk | **E106 = 14,318 PRICE / AA106 = 14,317.99 CDN LIST** (+ US list/cost, full-cost CDN columns) | Sept 18 2026: $14,166 ✓; July Belroc $13,285 (HISTORICAL alternative, comparability unestablished) | Read COMPLETE, freshness-limited; **$14,166 vs $14,318 → owner decision** |

**cont25's SLE24-16 result, explained separately**: it came from the
named-file workbook read during the targeted phase — NOT a completion of
another item's action (SLE24-16 had no targeted question: value_trace
reported it not carried, a token-scoped miss the sheet read then
corrected at row 101). It is recorded here as row 5's workbook column.

**Categories**: workbook reads COMPLETED for rows 3, 6, 8 (saved-copy,
freshness-limited, discrepancies surfaced — none auto-applied); row 5
workbook value from the sheet read; rows 5–8 vendor-quote-verified as of
**Sept 18, 2026** (quoted-then wording preserved — not current
availability); rows 1, 2, 4 remain genuine **owner decisions** (manual
prices preserved per training; No. 622 identity unresolved). Every
remaining action is completed, concretely scoped, or an explicit owner
decision. Draft SHA-identical (f028613c…); **nothing sent**.

**Continuation count**: 3 for this finishing instruction (cont28–30);
12 across the whole resumable arc (cont19–30). This proves resumable
execution from durable state — it does NOT yet demonstrate an employee
finishing within one autonomous run.

**Regression evidence preserved**: the one-time migration tests and the
demonstrated Flanger transition remain in test_job_work_ledger.py
(35 green).

## Round-48: evidence package tightened and CLOSED

1. **Freshness is a distinct obligation**: a saved-copy read now resolves
   the READ question and spawns its successor — "freshness against the
   live source unverified" — as a selectable open question (deferred past
   the resolution loop so it cannot be consumed by the item-scoped
   resolution). Pinned. An empty action queue after saved-copy reads now
   means only that the freshness obligations are ALSO exhausted or
   blocked — the queue itself is not the proof.
2. **Rows 1/2/4 precision**:
   - **No. 381**: the $2,902 manual vendor-quote price is an OWNER
     INSTRUCTION already on file — no new decision is owed; the workbook
     leads (Tennsmith sheet row 338; the $3,254 training note) are
     investigation leads, not competing claims requiring action.
   - **No. 622**: the identity choice (8 historical workbook candidates)
     is a genuine owner decision — the workbook carries multiple rows
     and no authorized source distinguishes which machine the customer
     means.
   - **U-22**: the decision required is **accept the manual $1,777 as
     the quoted price, or authorize a supplier inquiry**. Further
     authorized research cannot answer it because both taught sources
     are exhausted for this item — value_trace found no cataloged
     document carrying it and the mailbox grep surfaced no vendor quote
     for a U-22 bead roller (the Menzies thread's $5,742 figure is a
     different machine, L-24) — and the remaining route (asking Linmac)
     requires OUTREACH, which is a send-class action outside the
     read-only boundary of this job.
3. **Containment requires verified context**: normalized containment now
   resolves only on a UNIQUE (question, read-key) pairing — ambiguous
   candidates resolve neither (pinned). It remains a plausibility
   heuristic valid inside a verified read context, never authoritative
   identity.

**Evidence package closed.** The twelve-continuation run is not extended
further. Product status: **durable, resumable investigation demonstrated;
autonomous completion still to be proven.**

## Round-49 setup: the autonomous-completion milestone

Mechanism added for the next milestone: an IN-TURN PENDING-ACTION LOOP —
targeted-read actions created during the turn (or left from before)
execute within the remaining turn budget (bounded: at most 2 per turn,
each ≥18s of budget), settling through the same receipt/retirement/
freshness pipeline. The fresh-job fixture: new session, the ORIGINAL
eight-item prompt, no pre-seeded answers, no continues.
