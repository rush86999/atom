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
