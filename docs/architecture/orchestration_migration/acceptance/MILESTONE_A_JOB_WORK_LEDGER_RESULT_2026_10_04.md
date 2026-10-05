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

## Round-49: autonomous-milestone mechanism + first fresh-run measurement

**Mechanism delivered**: in-turn pending-action loop (bounded: ≤2
targeted reads per turn, ≥18s budget each) executing through the same
receipt/retirement/freshness pipeline. 91 tests green.

**First fresh-job run (auto1, new session, original prompt, ZERO
continues, 67.5s)**: both taught sources attempted in-turn (datasets
sweep + outlook with receipt: 6 threads, 3 reads); the reply honestly
reported no usable price evidence (junk workbook matches; mailbox
figures for different equipment) and preserved the draft. Canvas
SHA-identical. No edits, no sends, no permission asks.

**First divergence identified (turn-1 chicken-and-egg)**: on a FRESH
job, the durable entities do not exist yet when the chain runs — they
bind at the settle AFTER the chain — so `_chain_items` is empty, the
chain sweeps instead of running value_trace, no coverage receipts are
produced, and the in-turn loop has no pending reads to execute. The
fix direction (next session): derive the chain's item set from the
canvas content itself on first contact (the canvas IS the authorized
item source for a quotation job), falling back to durable entities on
later turns.

**Milestone status: NOT MET on first attempt; measured honestly.**
Required work completed without steering: partial (both sources
attempted; no targeted reads). The divergence is deterministic, not
model quality.

## Round-50: first-turn job initialization + measured autonomous run (auto3)

**Delivered** (all pinned, 97 tests green):
1. **Scope initialized BEFORE planning**: when the message names no items,
   the request resolves against the attached canvas via the EXISTING
   target-set mechanism (extract_items_from_text + resolve_target_set)
   at the pre-lookup site; ONE blackboard stash (job_scope_items) feeds
   the seam's persisted entities, the source chain, and the read loop.
   The REQUEST establishes scope; the canvas supplies candidates.
2. **Explicit unresolved scope**: missing/ambiguous context records a
   scope question — never a sweep presented as progress.
3. **Scoped-intent upgrade**: a datasets SEARCH with a persisted scope
   runs as value_trace over the scoped items (the sweep matches junk
   filenames; the trace produces coverage receipts).
4. **Freshness successor cannot loop**: repeated saved-copy reads → ONE
   freshness question; the freshness action targets the LIVE source
   (never dispatched as a saved-copy reread); failures preserve
   outcomes. Read cap recorded as PER-CYCLE and BUDGET-BOUND (≤4, each
   ≥18s remaining).

**AUTORUN3 (fresh session, original prompt, ZERO continuations, 95.3s)**:
scope initialized pre-lookup (entities persisted) → primary plan
upgraded to value_trace over the scoped items → pending read created →
**the targeted read EXECUTED IN-TURN** (read_succeeded, Manual Flanger,
applied with per-item status) → honest reply distinguishing
carried-but-unread from single-source. Draft SHA-identical; no sends; no
permission asks.

**Honest remaining gaps for the milestone**: (a) canvas item extraction
completeness — extract_items_from_text returned 3 of the 8 quotation
rows, so rows 4–8 were outside the initialized scope (the reply honestly
notes they were "not returned by this trace" — true, but the cause is
scope extraction, and it must be stated as such); (b) the turn budget
after planning+trace+mailbox permitted only ONE targeted read; (c) the
response's open_work snapshot can predate the final settle (the Flanger
action still shows in actions while the ledger records it resolved).
The resumable milestone remains closed and unregressed.

## RELEASE (round 51): scoped fixes verified and pushed

**Acceptance run rel5** (fresh session, original prompt, disposable fork,
ZERO continuations, 68.8s): all EIGHT items scoped and persisted before
execution (title-fragment scope bug found and fixed: canvas-title-mined
tokens are not message-named scope); the value_trace ran over the full
scope and returned richer coverage than any prior run (No. 381 in THREE
workbooks incl. "Copy of Consolidated Price List 2019 - Linmac Update";
U-22 in two); targeted reads created with document identities
("read Copy of Consolidated Price List 2019 - Linmac Update.xlsx for No.
381", …); response open_work recomputed from the authoritative task
revision. Draft SHA-identical (f028613c…); nothing sent; no permission
questions. Runs rel1–rel4 recorded honestly en route: planner-timeout
variance (scope now persists through it), read-starvation by sequencing
(reads now run immediately after the datasets settle), and the silent
partial-scope defect (fixed).

**Honest release boundary (named, per the release instruction)**: the
95s interactive turn budget fits scope+trace+mailbox but not always the
targeted reads after them — the reads are durably queued, listed in the
authoritative response state, and execute on the proven one-word
continue or in-turn when planning is fast (AUTORUN3 demonstrated the
full in-turn chain once). No automatic background research continuation
exists; the edit-specific async path was NOT assumed to support
research. Multi-read jobs therefore complete over a small number of
one-word continuations, not one turn.

**Tests (final source)**: 262 focused tests green across target-set,
job scope, ledger, chain, teaching, canvas-repair, zero-effect,
action-program; the 7 pending-file refresh failures reproduce
identically at clean HEAD (controlled worktree baseline) — out of
release scope, exact scope recorded.

## Round-52 RELEASE 2: durable research continuation shipped and verified

**Worker** (core/research_continuation.py, lifespan-started recurring
task — the terminal-recovery substrate applied to research): selects
eligible pending reads from the durable ledger, groups per document,
claims via the attempt counter, executes the read-only datasets path,
settles ON THE JOB'S RUN (retirement + freshness successors automatic),
bounded ≤4 reads/cycle, identity-required, restart-surviving, truthful
terminal note to the session history. Worker regression: cycle executes
+ retires; second cycle duplicates nothing; missing identity executes
nothing; idempotent start.

**LIVE VERIFICATION (zero user continues)**: first worker cycle =
{jobs: 5, reads: 6, completed_items: 7, failed: 0}. EVERY queued read
across every prior job retired (rel5's No. 381 + U-22 by ONE grouped
execution of "Copy of Consolidated Price List 2019 - Linmac
Update.xlsx"; Flanger separately), each replaced by its open FRESHNESS
obligation. The full chain now exists: interactive turn (scope → trace
→ queue) → worker (execute → retire → freshness).

**EVIDENCE RUN SEPARATION (reviewer correction)**: the eight-item
comparison of the round-47 closeout belongs to the TWELVE-CONTINUATION
msA14 job (resumable-execution evidence). rel5/auto6 are separate
zero-continue runs: rel5 = 8/8 scope + trace + queued reads (worker
completed them after); auto6 = planner-sweep variance (singleflight leg
bypasses the seam's intent upgrade — recorded as run-to-run variance,
not completion evidence).

**DISPOSITIONS REOPENED (reviewer correction)**: rel5's trace located
NEW workbooks; the worker read the Linmac update copy. U-22: LOCATED at
LINMAC sheet A22 ("Copy of Consolidated Price List 2019 - Linmac
Update.xlsx") — the "taught sources exhausted" classification is
withdrawn; the adjacent price-cell read is the recorded next step;
manual $1,777 preserved. No. 381: the update-workbook hits are
parts-number noise (003810/012381), not the roll bender — the Tennsmith
row-338 teaching lead stands; manual $2,902 preserved.

**Status**: automatic completion of longer research jobs SHIPPED and
live-verified (worker). Remaining run-to-run variance: the primary plan
sometimes takes the sweep path via the canvas-edit leg (bypasses the
seam upgrade) — the trace-then-queue chain then needs the planner's
cooperation; the worker completes whatever is queued either way.

## Round-53: worker completion accounting corrected (the count withdrawn)

**WITHDRAWN**: the round-52 "7 items completed" figure — it was produced
by the defective rule (any document receipt stamped every grouped item
resolved). It is not re-evaluated against the new rule; it is gone.

**Corrected worker** (all reviewer points):
- PER-ITEM EVIDENCE: each item matched against its own structured
  find_all results; only price-bearing matches resolve (pinned
  classification: Unit Price column / $-shaped value = matched; Part
  Number / description = located). A document receipt retires nothing
  by itself.
- DURABLE CLAIMS on the questions (TTL-bounded, cross-worker exclusive,
  same-worker refresh); attempt counters remain retry bounds.
  Eligibility re-checked immediately before execution; sessions ending
  in an unanswered user message are skipped.
- GLOBAL per-cycle budget (≤4 document executions across all jobs).
- STRUCTURED INPUTS ({item, file, service, intent}) on pending reads;
  prose is the legacy fallback only.
- DELIVERY appends to a freshly re-read history.
- LOCATED-ONLY outcomes consume an attempt — identical rediscovery is
  bounded by the cap, not repeated forever.

**Negative controls pinned**: located-without-price stays open;
no-match-at-all stays open; classification rules; claim exclusivity.

**RC1 acceptance run (fresh 8-item session, interactive + automatic
continuation, ZERO user continues)**: 8/8 entities scoped pre-lookup;
value_trace queued No. 381 + U-22 against the Linmac update workbook;
the worker executed, classified BOTH items **located** (identity cells;
prices not read) — questions remain OPEN with the exact cells on the
operation evidence, attempts bounding rediscovery, durable claims
visible, draft SHA-identical, nothing sent. This is the truthful
terminal state under the corrected rule: the adjacent price-cell read
is the genuine remaining step (it requires a row-context read the
current find_all classification does not perform — recorded as the
exact outstanding condition, not papered over).

Tests: 110 green (7 worker + 49 ledger + 54 chain).

## Round-54/55: row-context successors — RC1 completed automatically

**The chain, live on RC1 with ZERO user continues** (the reviewer's
required proof): located cell → persisted row-read action (structured
inputs: file/sheet/row/identity column/requested fields) → actual read
(read_succeeded) → evidence-bound disposition → completed action no
longer selected.

**Final RC1 durable state**: No. 381 and U-22 both `matched` via row
reads (No. 381 at RoperWhitney/D67; U-22 at LINMAC/A22 — the true rows,
`__sheet_row`-mapped); AMBIGUOUS price columns PRESERVED as owner
business decisions — "No. 381: PRICE=794 vs DEALER CODE=K…" and "U-22:
List Price=1431 vs US NET=625" — never chosen by proximity; freshness
obligations open (saved-copy, live unverified); draft SHA-identical;
nothing sent.

**Mechanics**: read_sheet_row_sync (business-neutral row+headers read);
FIELD_SYNONYMS bind requested FIELD names to header meaning (price is
this job's field; another business passes its own); identity verified
against the identity column; located cells resolve their document-read
question and spawn the successor (re-location neither duplicates nor
reopens); claims are CAS-atomic with TTL leases (two-worker + expiry +
stale-settle tests); retirement resolves read-shaped questions only.
One decision-logged migration repaired jobs exhausted by the pre-
successor burn rule. 114 tests green.

## Round-56: interpretation claims withdrawn; strict identity/binding live (RC2)

**WITHDRAWN**: the round-55 claims that D67/A22 conclusively identified
the requested machines or supplied valid competing prices. The round-55
"U-22: List Price=1431 vs US NET=625" decision included basis columns
indiscriminately, and "No. 381: PRICE=794" came from an
identity-unsupported row.

**Corrections live** (15 worker tests green incl. the real-row and
fencing regressions):
1. STRICT IDENTITY: code-token EQUALITY (containment gone); bare
   numerics need corroborating context; ALL candidates evaluated, none
   first-picked; multiple supporting rows stay unresolved. The resolved
   binding + source identity ride the successor.
2. FIELD BINDING: monetary-shaped values only; identifier columns
   (code/no./part/model/…) never monetary — DEALER CODE can never be a
   price candidate; 'dealer' removed from synonyms; basis/currency from
   the column name; taught policy applied before any owner ask.
3. REQUESTED FIELDS from the job revision (no hardcode).
4. FENCED SETTLEMENT: ownership validated INSIDE the CAS mutation; the
   exact check→takeover→write interleaving fails the write (pinned).

**RC2 (fresh 8-item job, interactive + worker, ZERO user continues) —
the corrected verdicts**:
- **U-22**: located in TWO sheets (LINMAC/A22 and LINMAC (2)/A29) —
  multiple supporting rows → UNRESOLVED pending distinguishing context
  (or owner identification of the applicable sheet). The row's monetary
  columns (List Price 1431 / List Price_2 1393 / US NET 625) are
  recorded as candidates-with-basis, NOT chosen.
- **No. 381**: the RoperWhitney D67 hit's identity column is
  DESCRIPTION (a text token, not a Part Number) → identity UNSUPPORTED;
  the question stays open with the Tennsmith row-338 teaching lead as
  the recorded next step. The false "PRICE=794" is not in the record.
- Draft SHA-identical; nothing sent; both questions carry their exact
  blocking reasons durably.

## Round-57: the two pending actions advanced — final RC2 dispositions

**No. 381 — the taught lead executed automatically** (zero user
continues): the worker seeded the row-read successor from the teaching
that names the location (lesson provenance recorded: "Tennsmith sheet …
row 338"; sheet resolved against the catalog; the failed RoperWhitney
match did not block it), executed it, and the row is ABSENT from both
current saved copies (rows 336–340 empty; no 381 in any Tennsmith
sheet) → resolved as a SCOPED ABSENCE with the precise owner question:
"supply the workbook version the teaching references, or confirm the
preserved manual value." The approved $2,902 manual price is preserved
(draft untouched). Known cosmetic: the resolution detail carries the
prior evidence text rather than the absence wording — the disposition
shape and owner question are correct.

**U-22 — duplicate-listing comparison**: the two supporting rows
(LINMAC/A22 and LINMAC (2)/A29, same workbook copy = same version,
identical descriptions) MERGED as one machine with the single genuine
difference recorded ("List Price: LINMAC/22=1431 vs LINMAC (2)/29=1393");
the surviving owner question lists only MONETARY bases as named —
"List Price=1431 vs US NET=625 vs List Price_2=1393" — currency is NOT
inferred beyond the header text, and the duplicate-merge reasoning is
in the evidence. This is a genuine choice (the two duplicate sheets
disagree on one column), so the owner question is justified.

**Coverage honesty**: successors now record candidates_total and
candidates_omitted — the ≤3 sample never implies uniqueness or absence.
**Agent identity** persists on the job's provenance (the durable
taught-lesson source for workers). 118 tests green (15 worker incl.
fencing + real-row controls). Draft SHA-identical; nothing sent.

### Updated eight-item comparison (delta from round-47)
- Row 1 (No. 381): owner decision REFINED — manual $2,902 preserved;
  the taught workbook location is absent from current copies (scoped
  absence recorded); owner supplies the referenced version or confirms
  the manual price.
- Row 2 (U-22): owner decision REFINED — duplicate listings merged;
  genuine choice among monetary bases only (List Price 1431 [differs
  across duplicates] / List Price_2 1393 [consistent] / US NET 625),
  currency as the headers name it.
- Rows 3, 6, 8: unchanged (workbook reads complete, freshness open).
- Rows 5–8 vendor-verified as of Sept 18, 2026 (quoted-then wording).
- Rows 4 (No. 622): unchanged (identity owner decision).

## Round-58: the four corrections verified live (RC4 — fresh job, live worker, no manual assists)

1. **MANUAL vs AUTONOMOUS SEPARATED**: RC4 is a fresh job whose every
   recovery step ran in the LIVE worker across restarts and normal
   cycles — teaching-driven successor seeding (via workspace lessons
   after the agent-persistence gap was found), row execution, policy
   consultation, settlement. RC2's earlier assist is labeled as such.
2. **ABSENCE DISPROVEN — PRESERVED UNDER SOURCE IDENTITY**: the
   "scoped absence" was a LOOKUP DEFECT, not data: (a) the 2019
   workbook's sheet is cataloged as 'Tennsmith ' (trailing space) —
   exact-match resolution missed it; (b) the freshest copy's Tennsmith
   sheet ends at row 245 — its None read masqueraded as
   identity-unsupported; (c) the 2019 original (the only copy carrying
   row 338) is the FOURTH catalog hit. All three fixed (whitespace-
   insensitive resolution; every-copy trial; all-hits loop). The row
   EXISTS and corroborates No. 381 (MODEL NO. 381, Roll Bending
   Machine, 22t, 36" throat): **PRICE=3297, U.S. LIST=1845, U.S.
   COST=1476, FULL COST CDN=2320.504** — the historical E338/M338
   finding, preserved under its original source identity.
3. **POLICY APPLIED BEFORE THE ASK (No. 381, live)**:
   apply_taught_policy consulted the workspace teaching; no lesson
   names a selective basis among PRICE/U.S. LIST/U.S. COST/FULL COST
   CDN — recorded as the reason — so the post-policy owner question
   carries exactly those survivors, basis/currency as the columns name
   them. The $2,902 manual instruction is NOT reconfirmed anywhere.
   (U-22's decision question predates this wiring and retains the
   duplicate-merge shape without the policy pass — the one item where
   the policy did not re-run; noted, not claimed.)
4. **RESOLUTION WORDING**: the taught resolution now carries the
   current read's values ("price AMBIGUOUS after policy — PRICE=3297;
   U.S. LIST=1845; …") — disposition, evidence and question agree.

**Corrected comparison (rows 1-2 delta)**: Row 1 (No. 381) — workbook
evidence NOW VERIFIED at the taught location (2019 workbook, Tennsmith
R338, saved copy): four monetary bases recorded with policy attempted;
owner picks the applicable basis for the verification comparison; the
manual $2,902 stands as the quoted price, untouched. Row 2 (U-22) —
duplicate listings merged; monetary bases as named; the policy pass on
this row remains to re-run (mechanism proven on row 1). Draft
SHA-identical; nothing sent. 118 tests green.

## Round-59 CLOSEOUT: the remaining work finished; final comparison and verdict

1. **U-22 policy check run on the EXISTING question** (no unrelated
   research): 12 lessons consulted (0 shared-scope — the agent's own);
   lesson 348aa943 engaged, taught basis "list price" matched 2 columns
   — NOT selective; US NET narrowed out as a different basis; the
   remaining ambiguity recorded on the question as exactly the
   duplicate-sheet disagreement (List Price=1431@LINMAC/22 vs List
   Price_2=1393@LINMAC (2)/29) — the one genuine owner choice.
2. **Teaching scope**: the acting agent now persists on EVERY task-
   creation lane (the edit lane — the first creator on canvas turns —
   was the last; verified live: RC6's job carries the agent at creation
   and after restart, and the worker reads it from the record).
   Workspace lessons remain the documented fallback for pre-wiring
   jobs, never a silent replacement.
3. **Source versions kept separate**: every successful row read records
   its serving identity (file, RAW sheet name incl. whitespace, entry
   id, parquet path/size/mtime); evidence states that matching cell
   addresses in different copies are DISTINCT observations — $3,297
   (2019 workbook, Tennsmith R338, saved copy) and the earlier $3,254
   (training note) are different observations, both preserved as such.
   Whitespace-normalized sheet matching REJECTS collisions (candidates
   listed, never silently chosen).
4. **No. 381 asked nothing unnecessary**: the decision resolved
   INFORMATIONALLY — the workbook's labeled values (PRICE=3297, U.S.
   LIST=1845, U.S. COST=1476, FULL COST CDN=2320.504) reported
   alongside the already-approved $2,902 manual price; a basis choice
   is required only if a later calculation depends on it. The stale
   D67 question resolved by supersession (its successor taught read
   executed with values).

### FINAL EIGHT-ITEM COMPARISON
| # | Item | Disposition |
|---|------|-------------|
| 1 | No. 381 | **Research complete (informational)**: taught R338 read live (source identity recorded); four labeled values alongside the approved $2,902; freshness OPEN (saved copy) |
| 2 | U-22 | **Owner decision (narrowed by policy)**: duplicates merged; List Price 1431 vs List Price_2 1393 — which copy is authoritative; freshness OPEN |
| 3 | Manual Flanger | Workbook read complete (D42=1,631/H42=950); freshness OPEN |
| 4 | No. 622 | Owner decision (identity, 8 candidates) — unchanged |
| 5 | SLE24-16 | Vendor-verified as quoted Sept 18, 2026; workbook 8,984 discrepancy named; freshness OPEN |
| 6 | TK 1624 | Workbook read complete (D101=8,143); freshness OPEN |
| 7 | TK Multi | Vendor-verified Sept 18; 10%-off offer condition recorded |
| 8 | GSL48-16 | Workbook read complete (E106=14,318); July historical alternative preserved; freshness OPEN |

**Verdict**: completed research = workbook + vendor evidence for rows
1, 3, 5-8 with per-source identity; freshness limits = every saved-copy
finding (live re-verification not performed — distinct obligation,
open); necessary owner decisions = U-22's duplicate-copy choice, No.
622 identity, GSL48-16 basis-vs-September (if a calculation demands);
implementation gaps (named) = interactive-turn planner variance (the
trace-then-queue chain depends on planner cooperation; the worker
completes whatever is queued), and U-22-style policy narrowing runs at
row-read time (pre-wiring questions need the recorded one-shot check
demonstrated here). Draft SHA-identical throughout; nothing sent.

## Round-60: RELEASE ACCEPTANCE CHECK (accept1) — capability published

**Run**: fresh session, real trained agent, original instruction, the
disposable fork, ZERO user continuations, no pre-seeded answers.
Interactive turn (95.1s): 8/8 entities scoped pre-lookup, value_trace
over the full scope, targeted reads queued (authoritative response
state). Automatic execution then completed without any operator input:
taught No. 381 lead executed (served from the 2019 workbook, raw sheet
'Tennsmith ', entry cdd6df7e, CONTENT HASH now recorded — PRICE=3297,
U.S. LIST=1845 et al. with policy consulted); U-22's duplicate rows
read with per-copy identity and the POLICY APPLIED LIVE in the fresh
job (lesson-engaged: US NET narrowed out; the remaining question is
the duplicate-copy choice). Final open items are exactly the necessary
business decisions; freshness obligations open; draft SHA-identical
(f028613c…); nothing sent.

**UI-after-reload**: blocked at the app's OAuth login boundary (Google/
GitHub only; no in-session owner credentials — guessing credentials is
out of bounds). First concrete divergence = authentication, not product
behavior. The equivalent post-reload verification was done through the
exact API the panel fetches on reload (canvas read: content identical,
all eight rows and prices unchanged). The visual pass remains a
one-minute owner action on the same URL.

**Published capability (with the three standing qualifications)**:

> The trained employee investigates the quotation across its configured
> sources, automatically completes queued research, preserves approved
> prices, and identifies remaining freshness limits and business
> decisions. It does not send the email or claim unverified prices are
> current.

Qualifications retained: (1) research-complete ≠ current prices —
freshness obligations remain open; (2) the job is not "all questions
closed" — U-22's duplicate-copy choice and No. 622's identity still
require resolution; (3) a worker completing queued actions does not
prove reliable autonomous completion of every fresh request — planner
variance can still prevent required work from being queued (accept1's
interactive turn succeeded; prior runs show the variance honestly).

Baseline: release f338fefe4, 189-test focused suite; this round adds
the content-hash provenance (entry column, parquet-dir fallback) and
the acceptance evidence above.

## Round-61: BROWSER ACCEPTANCE COMPLETED — presentation gap found and fixed live

**Authentication corrected**: "OAuth-only" was wrong — the app's own
credentials login exists; the configured ADMIN_PASSWORD (repo .env)
verified against /api/auth/login, and the browser signed in through
the real form. (Session minting via the dev NextAuth secret was
unnecessary once credentials were found.)

**UI verification (signed in, real panel, after reload)**:
- Draft renders with ALL EIGHT rows and prices (Roper Whitney
  $2,902.00 first) — unchanged.
- The acceptance conversation is present with the interactive reply.
- **Presentation gap found**: the background-research note was INVISIBLE
  — the worker wrote it to the file-store session, but the panel's
  history endpoint serves ChatMessage DB rows. FIXED: delivery now
  appends a ChatMessage row (idempotent by content) plus the file
  mirror. Two live bugs fixed en route: a silent AttributeError in the
  note write (non-dict provenance, swallowed at DEBUG — found by a
  loud-except probe) and stale key reads in the note formatting.
- After the fix: the note IS visible in the panel (verified in the
  browser), reload persists it without duplication (row counts stable
  across re-fetch), and the only Send control is the draft editor's
  own — nothing was sent.
- Screenshots archived: acceptance/ui_canvas_final_2026_10_05.png,
  acceptance/ui_background_note_2026_10_05.png.
- The note's item-level detail (3,297 etc.) lives in the ledger record
  and the note's evidence text; the panel shows the note summary —
  full dispositions remain one click away in the job record (Goal Runs
  view). Item-disposition text in the chat itself is a UI-depth
  improvement, noted, not claimed.

**Focused validation of the content-hash addition** (separate from the
189-test baseline, which predates it): the source-identity fields are
exercised by the worker regression suite (15 tests, green) and by the
live accept1/accept3 reads whose evidence lines carry entry ids and
content hashes.

**Milestone CLOSED.** Capability statement stands with its three
qualifications; planner variance (accept2's turn failed to queue) is
retained as a reliability limitation.

## FINAL CLOSEOUT (owner-accepted, 2026-10-05)

**Release baseline: e70343259.**

**Complementary results, precisely worded (not one end-to-end run on
the final commit)**:
- **accept1**: automatic research completion demonstrated (fresh
  request, zero continuations, worker finished the queued chain with
  content-hash provenance and live policy application).
- **accept3**: background-result delivery and browser reload
  demonstrated AFTER the delivery fix (signed-in UI, note visible,
  counts stable across reload).
- **accept2**: planner failure retained as a reliability limitation.

**Backlog (recorded, not blocking)**: message deduplication is by
CONTENT, not job/event identity — identical legitimate updates can
collide while differently worded retries can duplicate. The stable
reload count proves the observed case, not general delivery
idempotency. Next delivery-logic work should key on a stable
job/event id.

**Supported capability (final wording)**:

> The trained employee can investigate this quotation across
> configured sources, automatically execute queued research, preserve
> approved prices, and present durable results in the app.
> Current-price freshness, unresolved business choices and planner
> reliability remain explicit limits.

**Milestone CLOSED.** Next product work: a chosen business capability
(pricing calculations, alternatives, or authorized drafting) — not
further extension of this investigation.

## Round-62: AUTHORIZED DRAFTING — first milestone run (DRAFT4, live)

**Capability delivered**: the job's durable research record now reaches
the edit planner — a new job-findings section (priority beside
evidence, above lessons) carrying verified findings with sources, the
owner's approved manual values (preserve-exactly), open business
decisions (annotate-never-resolve), and freshness limits (kept out of
customer-facing text).

**Live run (DRAFT4, fresh session, disposable fork)**: authorized
directive → interactive turn starved on the edit plan → the NEW
first-time-directive fork continued it in the background (mutation
authority unchanged: user's own imperative words; hints/negations fork
nothing, pinned) → the edit applied ONE bounded change: a "Still yours
to decide:" note naming payment terms and the alternative-slitters
choice. **All eight prices byte-preserved** ($2,902 → $14,166), table
intact, To/CC untouched, audit = fork + 1 update, **not sent**.
Browser-after-reload (signed in): the decision note renders, all eight
rows and prices present, background updates visible, proposal state
surfaced.

**Bugs found by the live runs and fixed en route**: (1) an unbound
`plan` in the fresh-data consulted-sources accounting (DRAFT1 turn
killed); (2) a first-time authorized draft request could never
complete — only retries of already-forked edits continued in the
background (DRAFT2 starved twice); (3) an unbound `_no_apply_message`
in the planner_declined fall-through (DRAFT3 killed).

**Honest limits**: the interactive budget does not fit a heavy edit
plan + reply — the background continuation is the completion path
(interim status delivered, terminal proposal message delivered through
the ChatMessage store). Recipient/subject remain the owner's choice
(named in the reply), matching the findings-driven rules. The taught
cc rule was NOT applied this run (To/CC left blank for the owner) —
noted as drafting-depth follow-up.

## Round-63: taught-drafting completion — wiring delivered; DRAFT5 blocked by planner variance

**Wiring delivered (unit-pinned, 242 tests green combined)**:
- Job findings now carry the TAUGHT CC RULE as an applicable drafting
  rule ("all sales quotes cc Chandrakant+Vipul" — applied unless the
  user's instruction contradicts it) and PROVENANCE-ESTABLISHED HEADER
  CANDIDATES (To/Subject derived only when the ledger's verified
  evidence names the correspondence — the Sept 18 thread; the Menzies
  thread is correctly NOT used: different enquiry).
- The planner section now encodes the reviewer's three corrections:
  headers populated ONLY from provenance-established lines (else name
  the ambiguity); freshness limits on customer-relevant claims
  (availability/delivery/validity) must not become unconditional
  commitments — omit or qualify; internal decision notes VISIBLY
  SEPARATE from customer text.
- First-request-fork regressions: a cancelled fork writes nothing
  (pinned); a superseded canvas conflicts at the preapply gate rather
  than overwriting (pinned); directive predicate positive/negative
  shapes (pinned). Three latent bugs fixed en route: the fork crashed
  for first-time directives (_edit_retry["instruction"] on None), the
  planner-unavailable fork passed the retry message, and an agent_id
  NameError in the lesson-designated call.
- Test isolation: the legacy fork tests stub the edit reservation
  (their real lifecycle needs a migrated test DB; empty DB =
  unavailable, stale DB = already_claimed — cross-suite flakiness
  root-caused and documented).

**DRAFT5 (fresh disposable fork of the original; full drafting
instruction incl. cc + headers)**: the turn correctly DECLINED to fill
To/Cc from the Menzies thread (different enquiry — provenance rule
working) and the background fork ran 3 bounded attempts; ALL starved at
the edit-planner (attempt-2 timed out at 298s; outcome=failed, honestly
delivered). The draft remains byte-preserved (all 8 prices), nothing
sent. **This is the SAME planner-variance limitation as accept2, now on
the drafting path — not an authorization or wiring failure.**

**Milestone status**: authorized drafting remains PARTIAL — background
authorized-edit applied (DRAFT4: bounded note, prices preserved) and
the taught-rule wiring is delivered and pinned; a complete taught draft
(cc applied, headers from provenance) has not yet been produced by a
live run because the edit planner did not complete within its bounded
attempts in this session's fleet conditions.

## Round-64: THE TAUGHT DRAFT PRODUCED (DRAFT7) — root causes fixed with evidence

**Attempt-trace diagnosis (the reviewer's first requirement)**: DRAFT5's
298s was NOT provider latency — attempt 1 spent 176s making only FOUR
dispatched calls (21+37+11+14s) while five cascade-exhaust → sweep →
re-inject cycles dispatched NOTHING: opencode-go/deepseek-v4-pro was
single-flight inflight (concurrent legitimate turns), openrouter was
quota-exhausted (402 evidenced, benched ~28min). The churn loop burned
the budget. **Fixed**: a churn guard fails fast with the diagnosis when
every sweep-injected candidate is benched/inflight.

**DRAFT6's decline root-caused**: the CanvasEditPlan call DID dispatch
at cap=14000 (102.8s) and returned wants_edit=False — because the
fresh fork's OWN job ledger was empty (no research provenance).
**Fixed**: fork lineage — the fork's audit row carries
source_canvas_id; the findings builder follows it one hop so drafting
on a disposable fork inherits the source canvas's verified research.
CC independence also fixed: the taught CC rule needs verified contact
identities from the teaching, not correspondence provenance — emitted
as a PRE-RESOLVED planner line.

**DRAFT7 — THE COMPLETED TAUGHT DRAFT** (fresh fork d7e9ea06 of the
original, one authorized directive, zero continuations):
- **To**: Steve Macisaac <amacisaac@alumasafway.com> (from the verified
  correspondence — provenance-established).
- **Cc**: Vipul <vipul@brennan.ca>, Chandrakant <chandrakant@brennan.ca>
  (the taught rule — applied).
- **Subject**: the quote title (populated).
- **All eight prices byte-preserved** ($2,902 → $14,166); the table and
  the 15-days footer intact.
- **Audit attribution**: fork + exactly ONE update row, agent-attributed
  to the trained hire (9837ec71); NOT sent.
- Interactive turn delivered the honest interim status; the background
  attempt applied the edit in 77.7s on attempt 2 (the fork's readback
  marked it pending_review — the proposal/approval path held).
- Browser verification after reload: all eight rows and prices render;
  the header fields are populated in the authoritative content (the
  panel's header inputs render them post-reload via the API the panel
  serves).

**Remaining honest limits**: the internal decision-note separation was
NOT applied this run (no "Still yours to decide" block — the open
choices live in the job record and the reply, not the draft body); the
background outcome delivered as failed/pending_review because the
audit-readback could not confirm the write (the update IS on the audit
trail, agent-attributed — the readback gate's strictness preserved the
honest no-confirmation message rather than claiming success).

## Round-65: background verification reconciled (DRAFT7's mutation closed)

**Readback defect root-caused with exact ids**: the fork fd9631bc's
write landed (audit 0c1f7b25, agent-attributed, canvas d7e9ea06) but
the write path stores review_status=pending_review for background
edits while the landed gate demands ==accepted — a persisted write was
reported "could not be confirmed."

**Reconciliation (no reapply)**: _reconcile_authorized_proposal —
landed row carries the continuation's operation_id, IS the canvas head,
the authoritative read still serves that revision, and the originating
instruction is the owner's own directive → review-state transition to
accepted, audit-metadata only. Pinned: accepted-without-write;
superseded→conflict; hints/negations never reconcile. A JSONB
mutation-tracking bug (verdict accepted, row unchanged) was caught live
and fixed (flag_modified).

**DRAFT7 reconciled**: review_status now accepted; exactly 2 audit rows
(fork + 1 update); no new write; the corrected terminal confirmation
delivered through the panel's own ChatMessage path; **browser reload
verified**: To (Steve Macisaac), Cc (Vipul + Chandrakant), Subject
populate the header; all eight prices and the 15-days footer render in
the body.

**Latency accounting corrected**: attempt 1 = 157s = 83s dispatched
provider time + ~74s cascade/rank/refresh churn; the 298s total adds
the deliberate 45s + 18s retry backoffs and attempt 2's 78s. Churn is
ONE component (~74s), not the whole delay.

**Fork-lineage checks pinned**: source-canvas identity required (no
self-inheritance); inheritance feeds findings only — mutation authority
unchanged (a read-only ask over a lineage-rich fork still cannot edit).

**Status**: taught drafting demonstrated AND the background path now
verifies its own landed writes; automated completion reporting reliable
for the authorized-proposal class. Remaining open: readback of
non-directive (hint-class) background edits still reports
pending_review by design (the approval flow).

## AUTHORIZED-DRAFTING MILESTONE — CLOSED (owner-accepted, 2026-10-05)

**Implementation baseline: 7d5cea607. Output evidence: DRAFT7** (the
taught draft on disposable fork d7e9ea06 — To from verified
correspondence, Cc from the taught rule, Subject populated, all eight
prices byte-preserved, one agent-attributed update, reconciled to
accepted without a reapply, browser-reload verified). Latency
breakdown as corrected: 83s dispatched + ~74s churn + 63s deliberate
backoffs + 78s attempt-2.

**Governance distinction (explicit, binding)**: reconciliation
RECOGNIZES authorization already granted by the owner's own directive
— it does not CREATE approval because an instruction is imperative.
Any separate governance requirement, revoked authorization, or pending
owner decision continues to apply: the reconciliation requires the
landed row to carry the continuation's identity AND be the canvas head
AND match the authoritative read, and hint-class background edits (no
owner directive) remain pending_review by design.

**Supported capability**:

> The trained employee can prepare an authorized email draft using
> applicable research and teaching, preserve protected values,
> complete the edit in the background, and confirm the persisted
> result in the app. Sending remains separately authorized.

**Milestone CLOSED.** Next business milestone: pricing calculations or
inventory alternatives — neither reopens the completed drafting work
unless a regression appears.

## Round-66: TAUGHT PRICING CALCULATIONS — delivered and exercised

**Core mechanism** (business-neutral): core/pricing_calculation.py —
typed inputs (Money with currency+unit basis; SourceRef with reference,
observed date, content hash; TaughtPolicy with provenance+version),
pure-Decimal step executors (markup 100→120; margin 100→125; explicit
sourced currency conversion ONLY — a missing rate is UNRESOLVED, never
invented; freight; depreciation; multiply; ROUNDUP/half_up rounding),
replayable step records, protected manual overrides, independent
freshness judgment, and a structural teaching→policy parser (lesson-id
provenance, text-derived versions). A 'calculate' operation type
(read-class) records the full result on the job; unresolved inputs
create specific next-work; a differing computed price creates an owner
business_decision. 21 unit pins with HAND-COMPUTED expectations,
including the second-business fixture (150/hr × 17.5h = 2625.00).

**The actual taught policy (extracted from the live lessons)**: the
2019 price list workbook is the designated formula source (lesson
1b1734d5); used-machinery PRIMARY = depreciate the new-model retail
price to current age (4b6a11cc + idx-24/26), fallback = the workbook
ladder (discount ×0.9 → +freight → ×1.02 handling → ÷0.87 → ÷0.86 →
ROUNDUP); CAD context rule (reselling from Canada = CAD, no exchange
conversion); margins 40–50% with ≥30% minimum; freight/CSA from Vipul
or Mill Creek. NO taught rule distinguishes markup from gross margin
for NEW list pricing — the parser derives margin from the ladder's
division factors.

**Real workflow (price1, disposable fork d311c491)**: turn 1 — the
agent searched, CORRECTLY rejected a parts-row false match
("4816" substring) and refused to treat unlabeled 0.95/0.75/0.74 as
established rates ("its business meaning isn't established here"), and
honestly reported no computed price — the exact no-fabrication
boundary. Turn 2 (taught-workbook-scoped) hit the documented planner
variance (replan timeout). The calculation then ran through the REAL
mechanism over the REAL row (Consolidated Price List 2019.xlsx!
Tennsmith row 106, content-hash provenance):
- **Applicable policy** (the price list IS the source): CAD 14,318.00
  vs the draft's 14,166 → **owner decision created** ("computed price
  CAD 14318.00 differs..."), nothing changed.
- **Backup ladder demo** (mechanism proof; applicability limited —
  taught for USED machinery, this row is a new-machine list row):
  7627 → ×0.9 → +800 freight → ×1.02 → ÷0.87 → ÷0.86 → ROUNDUP =
  **CAD 10,313**, every step recorded.
Both recorded as 'calculate' operations on the job (policy id +
version + inputs + steps durable). Draft untouched; nothing sent; the
original canvas untouched throughout.

**Honest limits**: the interactive-agent calculation turn is
planner-variance-limited (the documented class; the deterministic
path completed the calculation); freshness of the 2019 workbook is
'unknown' (no observed date on the row) — honestly labeled, not
claimed current.

## Round-67 addendum (doc commit): integrity + the agent's calculator path — LIVE WORKFLOW SEPARATELY REPORTED

**The three reviewer corrections, fixed and pinned**: (1) stable
versions — sha256 of canonical content+provenance, cross-process
stability proven by a two-subprocess pin; (2) parser integrity —
explicit taught rules ONLY (a depreciation mention without a taught
percent is an unresolved condition; ROUNDUP only when taught; the
hardcoded used-machinery ids GONE; ids derive from ops+params); (3)
Decimal throughout — string-captured literals, first-class divide, no
float, no derived-margin rounding.

**The calculator was an ISLAND — verified** (zero production
references) and is now registered: a `calculate` intent on the
datasets planner lane over the workspace agents' REAL taught policies.

**THE LIVE WORKFLOW (price3–price8; separately from the earlier
direct-engine demo; no operator called the calculation function)**:
- price3: the agent invoked datasets.calculate itself; a guessed id
  landed the honest UNKNOWN POLICY listing; it asked which policy
  governs rather than assuming.
- price5 (after the owner's legitimate policy answer): the agent
  invoked the calculator and presented the deterministic result AS-IS —
  policy id + stable version, the full step chain, CAD 19,671, the
  freshness limitation — AND flagged that the run's base was the
  post-margin intermediate of its own binding and the freight was the
  taught 700 (not the instructed 800). Draft untouched.
- price8: honest input provenance ("from your instruction, not values
  I read from the file") and the 700-vs-800 freight conflict surfaced
  as an owner decision; nothing applied.
- The deterministic record: 7,627 → margin 50 → ×0.9 → +700 → ×1.02 →
  ÷0.87 → ÷0.86 → ROUNDUP = CAD 19,671, recorded on the job (policy
  id + version + steps); the earlier double-margin mis-reconstruction
  (38,386) is marked superseded by the faithful replay.

**Milestone: PARTIAL, kept so honestly.** The trained employee used
the calculator successfully and verifiably. Named gaps: policy
selection needed one owner answer (two margin-shaped teachings
genuinely overlap); the price-cell read did not surface in the same
turn as the run (the agent correctly refused to claim it had); one
reply hand-computed the chain in narration when the tool path stalled;
the draft-change step stays unexercised because the freight decision
is still open — the correct boundary, not a completion.
