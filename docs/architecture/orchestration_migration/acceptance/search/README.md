# Search acceptance — completion package

Work order: `docs/architecture/orchestration_migration/AGENT_SEARCH_WORK_ORDER_2026_09_26.md`
Date: 2026-09-26. Owner: this stream, end to end (the work order assigns the
whole surface; there was no separate integration or harness owner, and nothing
here is left as a handoff).

---

## 1. What was measured, and against what

| | |
|---|---|
| Frozen source | `77f2c96c2` + uncommitted working-tree changes, hash-pinned (see the correction in §1.1) |
| Layer 2 export sha256 | `a3169e895fe0638a…` (immutable working-tree export) |
| Layer 2 world / port | `search_l2`, `:8072`, own server, seatbelt local-only, credential-scrubbed |
| Effective flags | `ATOM_TASK_LIFECYCLE_ENABLED=1` (verified inside the launched server's environment by `runtime_contract_preflight`; `missing_tables=[]`) |
| Corpus | 51 labeled scenarios, 17 categories, 16 held out **by category, declared before any run** |
| Evaluator | `evaluate.py`, 13/13 negative controls held |
| Provider (Layer 2) | deterministic shim — **the real planner/model path is not covered by Layer 2** |

Production files changed (sha256 prefix):

```
0fcd84430347f763  backend/core/hybrid_search/documents_hybrid.py
1edb87140a0b2d59  backend/core/hybrid_search/lexical_ranker.py
240687c5309bb722  backend/core/identifier_search.py
d3259796dfebf307  backend/core/chat_tool_planner.py
f6ebea1853f57ee3  backend/core/hybrid_retrieval_service.py
901af64547f2d1a7  backend/core/memory_context_assembler.py
a033c7b42531eba1  backend/tools/drive_tool.py
```

Reproduce:

```
python3 build_scenarios.py                                   # corpus + held-out split
python3 evaluate.py --selftest                               # must print "evaluator valid"
backend/venv314/bin/python run_layer1.py                     # production search stack
backend/venv314/bin/python run_layer2.py --port 8072         # public boundary
python3 evaluate.py --runs runs.json runs_layer2.json
```

---

## 1.1 Corrections to the first report of this package

**1. "19 fixed" conflated two different things.** The accurate statement is:
**13 cases that previously FAILED now pass, and 6 cases that were previously
BLOCKED (never exercised) are now exercised and pass.** The 6 blocked ones were
not defects found and repaired — they were cases no layer could reach until the
public-boundary driver existed. Conflating them overstates the defect count.

**2. The frozen source was mislabelled.** This package first reported
`813b24c3b5` as the frozen source. That was read from `git rev-parse HEAD` at
report-writing time, not captured at run time — the same stale-fingerprint error
class these work orders keep warning about. The Layer-2 world was built at
`20:27:02`; `813b24c3b5` was committed at `20:29:33`, **2.5 minutes later**, and
is therefore NOT in the export. The real source is `77f2c96c2` plus the
uncommitted working-tree changes captured in export `a3169e895f…`. The export
hash, not a commit id, is the durable pin, and it is recorded above and in
`runs_layer2.json`.

**3. The citation-anchor question is RESOLVED, not open.** This package
reported the `R<row>` vs `A<row>` citation-anchor contract as still open and
not mine to decide. It is closed. The identity-coordinate work landed in
`72590256e` → `166c6614a` → `77f2c96c2`, all of which **precede** this
package's snapshot, and the identity-evidence code is present in the export.
That is consistent with the lifecycle report's C01 identity/value binding pass.
Note separately that `813b24c3b5` — the commit this package mislabelled itself
as — is a *harness* fix ("decide absence from structured coverage, not reply
wording") that changes the lifecycle evaluator's C23 verdict logic. It postdates
this snapshot, so the lifecycle matrix must be re-run on a fingerprint that
includes it; the search results here are unaffected because they are scored by
`evaluate.py`, which is independent of that harness.

**4. A repo-hygiene incident worth flagging separately:** commits `72590256e`
and `77f2c96c2` committed `frontend-nextjs/.preview-instance/` build caches —
61,643 and 6,150 changed lines respectively. That is generated build output
under version control. It is why `git status` is noisy and why a bare
`git add -A` is dangerous in this repo. Not this work's change; not fixed here.

---

## 2. Route map (Phase A)

```
public chat  POST /api/chat/message
  └─ chat_orchestrator.process_chat_message
       ├─ task lifecycle (ATOM_TASK_LIFECYCLE_ENABLED)  — the durable task revision
       └─ chat_tool_planner.plan_tool_use → execute_tool_plan
            ├─ named-file / cached-materialized scan   ── invocation_events scan_start/scan_end
            ├─ _ingested_mailbox_lines                 ── figure tokens → address scan → attachment leg
            │     └─ DocumentsHybridSearch (count gate below hybrid_min)      ← mailbox hybrid lane
            ├─ _memory_hybrid_block
            │     └─ _hybrid_search_preserving_constraints → DocumentsHybridSearch.search
            │          ├─ lexical leg  search_documents_lexical (BM25/FTS5 → ILIKE fallback)
            │          ├─ vector leg   LanceDB `documents`
            │          ├─ hydration    IngestedDocument identity resolution
            │          └─ conversations leg  comms memory store (owner-scoped)
            └─ answer_presentation / workbook_read_artifact   ── evidence binding, delivery
```

Second, independent consumer of the same reranker loader:
`memory_context_assembler.assemble_memory_context` → `_rerank_lines` (probe in
`warm()`, prediction already offloaded via `asyncio.to_thread` — the work
order's caution was correct, so no blanket change was made there).

Third: `hybrid_retrieval_service.HybridRetrievalService` →
`retrieve_semantic_hybrid` → `_rerank_cross_encoder`, reachable from
`core/atom_agent_endpoints.py` (`/agents/{id}/retrieve-hybrid`).

---

## 3. Findings: confirmed / hypothesis / not-reached

### Confirmed defects (each reproduced, each fixed, each pinned by a test)

1. **A failed search was indistinguishable from a successful zero-match search.**
   `documents_hybrid.search` returned `success: True`, `hybrid: "no_results"`,
   `results: []` for a raising leg, a failed gather, *and* for a corpus that
   genuinely matched nothing. The label was computed from which legs
   *contributed hits*, not which legs *ran*. Consumers read `results` only, so
   every one of them — including `action_registry.documents.search`, which
   returns the envelope verbatim to the agent — could not tell the difference.
   An absence claim built on this is a fabricated claim.

2. **A hydration failure silently relabelled source identity.** A failed
   `IngestedDocument` lookup turned every vector hit into
   `source:"vector", bridged:false` while the envelope still claimed semantic
   coverage: a broken PG read looked exactly like a corpus of genuinely
   unbridged rows.

3. **The lexical leg swallowed its own failures.** `search_documents_lexical`
   caught every exception and returned `[]` — byte-identical to "no matches".
   Found by tracing past the two sites the work order named.

4. **Destructive query truncation dropped constraints silently.**
   `query[:200]` (twice in `chat_tool_planner`), `query[:500]` (the conversations
   leg, `drive_tool`, the assembler's rerank). A truncated query is a *valid*
   query, so the search reported a clean zero-match answer for the half it
   never sent.

5. **The reranker was an embedding checkpoint.** `CrossEncoder("BAAI/bge-large-en-v1.5")`
   ranks by cosine geometry, and the scores were min-max normalised per query
   into a confident-looking `[0,1]`. A ranking artefact presented as relevance.

6. **Blocking inference inside a coroutine, with a timeout that could not
   preempt it.** `model.predict()` ran on the event-loop thread under
   `wait_for(0.200)`; on CPU the whole process stalled for the duration.

7. **Scores were mapped back to candidates by position** and normalised, so a
   short or NaN score vector produced a confident ordering over the *wrong*
   records.

8. **`_load_documents_df` / `_load_documents_table` hardcoded
   `backend/data/atom_memory`**, bypassing `LANCEDB_URI_BASE` and
   `LanceDBHandler._resolve_local_db_path`. The documented root-vs-backend
   divergence class, and it made the excerpt path non-isolatable for evaluation.

### Found by the acceptance harness, in code written earlier in this same task

9. **Window edges cut mid-token.** `"invoice 4417"` became `"nvoice 4417"`,
   and `query_coverage` reported the run *complete* because the surviving
   fragment `4417` matched. The coverage check could not see the drop it
   existed to detect.

10. **The decomposed merge let one source class erase another.** Six windows,
    every one searched, zero conversation hits survived the final cut — the
    early prose windows filled the budget. Reported as `success`. This is the
    original defect class, reintroduced by the fix; the harness caught it.

11. **Bounded admission released its permit on cancellation**, so an orphaned
    inference handed its slot back while still burning CPU and repeated
    timeouts accumulated unbounded background work. Caught by the test written
    against the work order's warning.

### Hypotheses NOT promoted to findings

- The document leg has no per-owner filter. `IngestedDocument` has no
  `owner_user_id` column; the ownership dimension for documents is
  `workspace_id`/`tenant_id`. The access-scope scenario was retargeted to the
  mailbox, which is the surface that *claims* an owner boundary
  (`search_communications(owner_user_id=...)`). No access-scope violation was
  observed. Whether the document leg *should* be workspace-scoped is a
  product decision, not a defect this run can assert.
- The mailbox `hybrid_min` count gate. Structurally it subordinates semantic
  evidence to exact hits, but changing it is a ranking change and the work
  order gates it on measurement. The gate is unchanged and **unmeasured**; see
  §7.

### Not reached / disabled

- `HybridRetrievalService` is reachable only via `/agents/{id}/retrieve-hybrid`
  and the assembler. The Layer-1 corpus does not exercise the reranker end to
  end; its degradation modes are covered by unit tests only (§4, §7).
- `action_registry.documents.search` is covered by its own suite, not by the
  51-scenario corpus.

---

## 4. Before / after

| # | Before | After | Pinned by |
|---|---|---|---|
| 1 | one `success` flag, no per-leg state | `status` success\|partial\|failed, per-leg `legs{}` (status, error **category**, hit_count, duration), `coverage{}`, `ranking{}` separate, `absence_claimable` | `test_raising_vector_leg_is_partial_not_silently_lexical_only` and 9 more |
| 2 | failed hydration → `bridged:false`, coverage claimed | `hydration` reported as a failed leg; hits still returned (they are real candidates) | `test_hydration_failure_is_recorded_because_it_costs_source_identity` |
| 3 | lexical exceptions → `[]` | `raise_on_error=True` for the one production caller; default never-raises preserved for any other | `test_both_legs_failing_is_failed_and_forbids_absence` |
| 4 | `query[:N]` | `bounded_query_variants` (token-snapped overlapping windows; identifiers get their own variants) + `query_coverage` so a drop is *detectable* | `test_bounded_variants_cover_every_identifier_a_head_cut_would_drop`, `test_identifier_straddling_a_window_boundary_survives` |
| 5 | embedding checkpoint as reranker | `ATOM_RERANK_MODEL` (default `BAAI/bge-reranker-base`), `_classify_checkpoint` rejects a single-logit encoder, `local_files_only` so no request-time download | `test_embedding_checkpoint_is_rejected_as_a_reranker`, `test_default_reranker_is_a_trained_cross_encoder` |
| 6 | blocking predict on the loop | one named worker, off-loop, `RERANK_LEG_TIMEOUT_SECONDS` budget | `test_blocking_inference_does_not_block_the_event_loop` |
| 7 | positional score mapping + min-max | cardinality + finiteness validated; raw model scale kept; permit released by the worker | `test_short_score_vector_cannot_reorder_records`, `test_scores_stay_on_the_model_scale_and_are_not_normalised`, `test_timed_out_inference_is_bounded_not_accumulated` |
| 8 | hardcoded store path | resolves via `LANCEDB_URI_BASE` → `LanceDBHandler._resolve_local_db_path` | Layer-1 corpus runs in a redirected scratch root |
| 9 | mid-token window edges | edges snap to a token boundary | `test_identifier_straddling_a_window_boundary_survives` |
| 10 | merge cut erased source classes | per-class budget reservation; a bounded output reports `partial` | `mailbox_long_address_tail` (fails on the baseline, passes here) |
| 11 | permit released on cancel | released by the worker thread | `test_timed_out_inference_is_bounded_not_accumulated` |

---

## 5. Results

Per category, numerators/denominators. `blocked` is excluded from the
denominator — a path that never ran is not evidence.

**Read this table together with §7.** "51 passed" is a *search-correctness*
result measured against a synthetic fixture corpus at one retrieval layer plus
four public-boundary lifecycle cases. It is not a statement that the chat
orchestrator is ready to use: the real planner/model path is not covered here,
the mailbox gate is unmeasured, and the reranker is not exercised end to end.

### Candidate (this change)

| Category | pass | fail | blocked | denom |
|---|---|---|---|---|
| absent_within_coverage | 4 | 0 | 0 | 4 |
| ambiguous_identity | 3 | 0 | 0 | 3 |
| conflicting_stale_sources | 4 | 0 | 0 | 4 |
| crowded_lexical | 3 | 0 | 0 | 3 |
| distractors_replacement | 2 | 0 | 0 | 2 |
| exact_named_file | 3 | 0 | 0 | 3 |
| explicit_research | 1 | 0 | 0 | 1 |
| formatting_followup | 3 | 0 | 0 | 3 |
| long_request | 2 | 0 | 0 | 2 |
| mailbox_identity | 3 | 0 | 0 | 3 |
| multi_source | 3 | 0 | 0 | 3 |
| paraphrased_question | 2 | 0 | 0 | 2 |
| partial_failed_search | 6 | 0 | 0 | 6 |
| reranker_degraded | 4 | 0 | 0 | 4 |
| restart_retry | 2 | 0 | 0 | 2 |
| similar_identifiers | 3 | 0 | 0 | 3 |
| source_owner_restriction | 3 | 0 | 0 | 3 |

| Split | pass | fail | blocked | denom |
|---|---|---|---|---|
| development | 35 | 0 | 0 | 35 |
| **held out** | **16** | **0** | **0** | **16** |
| total | 51 | 0 | 0 | 51 |

### Baseline ablation (same corpus, same evaluator, same fixtures, pre-change tree `52e6193a7`)

| | baseline | candidate |
|---|---|---|
| pass | 32 | 51 |
| fail | 13 | 0 |
| blocked | 6 | 0 |
| development | 18p / 11f / 6b | 35p / 0f / 0b |
| held out | 14p / 2f / 0b | 16p / 0f / 0b |

**13 previously-failing cases now pass; 6 previously-blocked cases are now
exercised and pass; 0 regressions.** The largest single movement is
`partial_failed_search`: **0/6 → 6/6**. That category is the false-absence gate
and it was failing completely before this change — a broken leg produced a
confident "not found". The held-out split moved 14→16 with no development/held-out
divergence, which is the only evidence here that the corpus is not simply
fitted to the tuning set.

### Layer 2 — public boundary, own isolated server, own port

| Case | Verdict | Evidence |
|---|---|---|
| `formatting_zero_retrieval` | pass | 1 scan on turn 1, **0** on the formatting turn |
| `explicit_research_new_attempt` | pass | scans 2 → 3, i.e. a genuinely new read attempt |
| `restart_retry_keyed` | pass | **0** scans on retry; pinned bytes byte-identical |
| `restart_retry_survives_restart` | pass | server stopped and relaunched against the same world; all 3 identifiers present in the follow-up |

Retrieval invocations are counted from `invocation_events.scan_start` — the
durable per-execution record the production scan path already writes — not from
persisted attempt counts, timestamps or log text.

---

## 6. Gates

| Gate | Result |
|---|---|
| no access-scope violations | **met** — 3/3, incl. the second owner's mailbox message; no violation observed |
| no false absence on injected failures | **met** — 6/6; baseline 0/6 |
| no lost explicit constraints in the frozen cases | **met** — `long_request` 2/2, incl. identifiers past character 200 and a straddling identifier |
| no fabricated bindings | **met** — value/unit/basis/row binding asserted per item; the harness can only report a binding it read out of the retrieved evidence |
| no lifecycle regression in exercised cases | **met** in the exercised set (6 Layer-2 cases above). Pre-existing lifecycle gates from the prior session remain open and are **not** claimed here |
| ranking promotion justified by measurement | **not attempted** — no ranking change is promoted. See §7 |

---

## 7. Limitations, honestly

1. **The mailbox `hybrid_min` count gate is unchanged and unmeasured.** It
   subordinates semantic evidence to exact hits by construction. Changing it is
   a ranking change, the work order gates it on measurement, and no measured
   basis exists yet. **This is the largest open item in the work order.**
2. **The reranker is not exercised end to end by the corpus.** The four
   `reranker_degraded` cases assert that a degraded ranking is *reported
   observably* and never claimed as full coverage; they do not drive a real
   cross-encoder. Its rejection, bounded admission, cardinality and finiteness
   behaviour is covered by unit tests only. The corpus's 4/4 on that category
   is a weaker claim than the other categories' and should not be read as
   "the reranker was measured working".
3. **Layer 2 runs against a deterministic provider shim.** The seatbelt
   profile blocks external egress, so the real planner/model path is not
   covered at the public boundary. Labelled in `runs_layer2.json.isolation`.
4. **The Layer-1 fixture corpus is synthetic** and shares no vocabulary with
   the original eight-machine workbook. The workbook remains a regression
   fixture; it is not this benchmark.
5. **Contextual indexing (Phase D item 7) was not attempted.** It is gated on
   this baseline, which now exists.
6. **A stale shim on port 8099 produced one false failure** during
   development — an orphaned process from an earlier run served a stale script,
   and the restart case reported a provider error that was recorded as a
   constraint-loss failure before the cause was found. Anyone re-running Layer 2
   should confirm port 8099 is free. This is a harness hazard, not a system
   finding, and it is why the failure was re-derived before being believed.
7. **Acceptance worlds are ~1.7 GB each** and the directory held 52 GB. Nine
   intermediate worlds created during this work were removed (only ones this
   work created; other streams' worlds untouched). Disk exhaustion mid-run
   produced a truncated world export and a spurious `OSError`.

---

## 8. Rollback / configuration

Every change is additive and flag-neutral; no default behaviour a caller
depends on was removed.

| Control | Default | Effect |
|---|---|---|
| `ATOM_RERANK_MODEL` | `BAAI/bge-reranker-base` | the reranker checkpoint |
| `ATOM_RERANK_MODEL_LOCAL_ONLY` | `1` | never download during a request; set `0` only where a download is acceptable |
| `ATOM_RERANK_ALLOW_EMBEDDING_CHECKPOINT` | `0` | set `1` to accept the old embedding-checkpoint ordering deliberately |
| `ATOM_RERANK_WORKERS` / `ATOM_RERANK_MAX_QUEUE` | `1` / `2` | bounded inference admission |
| `HYBRID_RERANK_TIMEOUT_S` | `0.200` | rerank budget |
| `LANCEDB_URI_BASE` | unset | now honoured by the document-excerpt helpers (default unchanged) |

To revert entirely: `git revert` the commits touching the seven production
files above. The envelope fields are additive — `success`, `query`, `results`,
`hybrid`, `stats` are unchanged, which is what the four in-repo consumers read.
`success` is now `False` when the search genuinely failed; that is the one
intentional contract change and it is the point of the work.

---

## 9. Files

```
search/
  README.md                  this package
  build_scenarios.py         corpus generator; expectations authored from the
                             fixture, never read back from the system
  scenarios.json             51 cases, 17 categories, held-out split frozen
  evaluate.py                independent scorer + 13 negative controls (--selftest)
  run_layer1.py              drives the production search stack
  run_layer2.py              public boundary, on run_isolated.py's isolation machinery
  runs.json / runs_layer2.json          per-case run records
  scorecard.json / scorecard_baseline.json   candidate and baseline
  ../fixtures/provider_shim/search_layer2.json  authored provider completion
```
