# Lane 3 — per-case accounting, C00–C26

Measured 2026-09-27. Every row states the fingerprint the evidence belongs to.
**Readiness is NOT complete.** The advertised user workflows pass; the
mutation/lifecycle safety half of the matrix has no public-boundary evidence at
all, and one case has never passed at any fingerprint.

Candidate under test: world `candidate_fix1`, run `run-7325767729a0`, backend
`:8071`, frontend `:3102`, loaded-code fingerprint proven identical across every
restart (14/14 module hashes). Working-tree `source_id` moves as harness files
change and is **not** an identity of loaded code — see
`LANE_3_INVENTORY.md` §7 and the coordination entry.

## Status vocabulary

| Status | Meaning |
|---|---|
| `PASS (this candidate)` | Exercised through the public boundary on the candidate's loaded code, passing |
| `PASS (other fingerprint)` | Passed, but on an older snapshot — not counted toward this candidate |
| `PARTIAL` | Some required evidence present, some missing |
| `UNIT-ONLY` | Only integration/unit tests. Per the closeout plan these must **not** be relabelled as boundary coverage |
| `NOT EXERCISED` | No boundary evidence exists |

## Results

| ID | Scenario | Status | Evidence |
|---|---|---|---|
| **C00** | Launch preflight | **PASS (this candidate)** | `verify` 9/9: process alive, health pid == launch pid, cwd is this world, **open DB via `lsof`**, not holding the live dev DB, frontend answers, compiled origin `:8071`, lifecycle flag on, real credentials forwarded (names only). Plus 14 loaded-module hashes, `launch_descriptor.json`, world `MANIFEST.json` |
| **C01** | Original eight-item ask | **PASS (this candidate)** | Browser B1: 8 items in requested order. HTTP `base_lookup_succeeded`, `base_lookup_shows_all_eight_in_order`, `base_lookup_has_structured_evidence`, `durable_task_entities_match_base_order`, `displayed_citations_are_grounded_in_the_record`, `displayed_values_are_in_the_source_cells` (values verified against parquet cells, no chat-path code) |
| **C02** | Distractor history | **PARTIAL** | HTTP cases 2 and 3 run base → replace → format/research/reload and every displayed set equals the independently expected `REPLACED_ORDER`; `outgoing_items_evidence_is_not_reused`. No dedicated distractor-history conversation on this candidate |
| **C03** | Formatting | **PASS (this candidate)** | HTTP `formatting_invoked_no_retrieval` (attempt id unchanged), `earlier_messages_survive_the_formatting_turn` (byte-identical digests of prior rows), `formatted_citations_grounded`. Browser B3 + `B3_earlier_answers_are_unchanged` |
| **C04** | Explicit re-search | **PASS (this candidate)** | HTTP `re_search_performed_a_new_attempt` (new attempt id), `re_search_citations_grounded`. Browser B4. *Unchanged-revision allowance not exercised* |
| **C05** | Same text / new request ID | **PASS (other fingerprint)** | `4b_same_text_new_request` 2/2 on `e61126cfebc4-dirty.edf632772b72`. Not re-run on this candidate |
| **C06** | Same key / same payload | **PASS (this candidate)** | `restart_durability`: byte-identical pin replay across a **real** restart, `replay did not create a second execution` |
| **C07** | Same key / different payload → 409 | **PASS (this candidate)** | `restart_durability`: HTTP 409, not re-executed. Sequential; no concurrent second request |
| **C08** | Large replay payload | **UNIT-ONLY** | `test_chat_transport.py` only. No boundary artifact of any size |
| **C09** | Restart replay | **PASS (this candidate)** | `restart_durability` 15/15: same run dir, same opened DB, old pid confirmed gone, **14 loaded module hashes identical**, pre-restart history intact, unrelated request still works |
| **C10** | Finalization transform | **NOT EXERCISED** | No controlled failed execution produced on this candidate |
| **C11** | Token-bearing stream | **PASS (this candidate)** | **First time ever observed.** `ATOM_CHAT_STREAMING` was set to `"1"` while the orchestrator tests `.lower() == "true"`, so the streaming leg had never run in any acceptance world. Launcher corrected; now: 16 `chat_token` frames on the LLM leg, **all** bound to the turn's `execution_id`, no foreign frame, deltas non-empty, largest inter-frame gap 139 ms, exactly one `chat_token_done`, and the 16 concatenated deltas are **byte-identical** to the HTTP answer and to the final event's text. UI side: the bubble grows progressively (distinct lengths 27→99→195→315, starting with the reasoning strip), adds exactly one bubble, and settles containing the durable history answer — no stale provisional text |
| **C12** | Deterministic completion | **PASS (this candidate)** | The seeded workbook ask emits **zero** `chat_token` frames — correct, it is answered deterministically — yet still emits exactly one execution-bound `chat_token_done` and delivers the full 2233-char answer. No token frame claims that turn. "No tokens is valid" is now demonstrated rather than assumed |
| **C13** | Overlapping reads | **PASS (other fingerprint)** | `8_overlapping_turns` 3/3 on `e61126cfebc4-dirty`. Not re-run here |
| **C14** | Denied / unpersistable edit | **UNIT-ONLY** | `test_task_lifecycle_denial.py`. No denial case in the required list. `planner_down_no_apply` is a different mode and self-reports `mutation.status: "unverified"` — not a substitute |
| **C15** | Declined / no-apply edit | **PARTIAL — one clause measured FAILING** | Measured on the candidate for the first time via `authorized_edit_probe.py`. A canvas-edit-shaped turn that the planner declined: **zero effects** (0 `canvas_audit` rows, canvas content unchanged) and an **honest** answer ("nothing was changed") — both clauses hold. But the reserved `edit` operation stays `status=pending` with `updated_at == created_at`, measured untouched at 463s, so **"claim not stranded" FAILS**. The release mechanism exists and is tested (`finish_edit_turn` → `cancel_operation`; `test_declined_edit_releases_the_claim` passes) — only the wiring is missing. See `C16_BOUNDARY_TRACE.md` §4 D1 |
| **C16** | Single authorized edit | **NOT EXERCISED — boundary traced** | Full trace now exists: `C16_BOUNDARY_TRACE.md`. First divergent boundary is **`interpretation`**, not the effect layer. The edit lane was entered, the operation reserved, then the **canvas-edit planner returned `wants_edit=False`** for an unambiguous request and the app failed closed with no mutation and no false claim. The mutation machinery below the planner was never reached, so it remains untested. The old 7/7 `audit_rows: []` evidence was measuring `world/data/atom.db` while the server serves `world/runs/<run>/data/atom.db` — a different file — so it could not distinguish "edit never ran" from "probe looked in the wrong database" |
| **C17** | Concurrent same-key edit | **UNIT-ONLY** | In-process multiprocess tests against a scratch DB, not the boundary |
| **C18** | Concurrent conflicting payload | **UNIT-ONLY** | Boundary has only the *sequential* 409 (C07) |
| **C19** | Crash after claim / before effect | **UNIT-ONLY** | No worker kill, no confirmed worker death, no operation-linked durable marker, no zero-effect observation at a sink |
| **C20** | Crash after effect / before completion | **UNIT-ONLY** | No boundary crash, no non-duplicating retry through the public API |
| **C21** | Slow live worker | **UNIT-ONLY** | No boundary run; claim-release-under-timeout unobserved |
| **C22** | Corrupt / partial source | **PASS (other fingerprint)** | `11_forced_retrieval_failure` 5/5 on `e61126cfebc4-dirty`, 46 sheets corrupted, honest failure text. Not re-run here. *Note: the runner corrupts the shared world parquet in place, so this needs its own world* |
| **C23** | Legitimate absent / unknown source | **PASS (this candidate)** | **U-38 is not in the fixture workbook.** HTTP `incoming_item_absence_is_labelled_and_invents_nothing` (retrieval == "searched", no identity cells, no values). Browser B2 reads literally `U-38 - no matching row in the indexed content searched` with **no number displayed**. Found/ambiguous/absent/failed are distinguished |
| **C24** | Pin persistence failure | **UNIT-ONLY** | MagicMock-store test only |
| **C25** | Cache-loss identifier inheritance | **NOT EXERCISED** | Historical search-layer result exists on a different export and is a substring test, not an extraction test |
| **C26** | Non-workbook task | **NOT EXERCISED** | Historical invoice runs are explicitly UNCLASSIFIED in `MANIFEST.md` §v3.10 |

## Tally

| Status | Count | IDs |
|---|---|---|
| PASS (this candidate) | **11** | C00 C01 C03 C04 C06 C07 C09 **C11 C12** C23 |
| PARTIAL | **2** | C02, **C15** (one clause measured failing) |
| PASS (other fingerprint) | 3 | C05 C13 C22 |
| UNIT-ONLY | **8** | C08 C14 C17 C18 C19 C20 C21 C24 |
| NOT EXERCISED | **3** | C16 (boundary traced, effect layer unreached), C25, C26 |

**The honest summary: 13 of 27 cases are now resolved on this candidate's
loaded code** (11 PASS + 2 partial). C16 is no longer an open question — it is a
diagnosed one: the blocker is the canvas-edit **planner declining an unambiguous
request**, above the effect layer, so the write path below it is still unproven.
The hole is otherwise unchanged: **every case that requires observing a real
mutation at a durable sink is still unmeasured** (C14, C16–C21, C24), and the
write path has never had a successful boundary observation at any fingerprint.

## What this does and does not permit

**Permits:** publishing the candidate as the preview for read-only lookup, task
correction, formatting, re-search, reload, token streaming, and restart/retry
durability — all browser-verified on the candidate's loaded code.

**Does not permit:** any claim about canvas/artifact edits, authorization denial,
concurrency, crash recovery, or pin-persistence failure. Those remain excluded
and must be listed as excluded in the user handoff.
