# TDD Bug Hunt — GraphRAG + TurnFact Memory Stack

**Secretary**: bughunt-graphrag · **State**: GREEN · **Tests**: 7 passing (deterministic)

## BUGS FOUND

| # | Location | Bug | Severity | Test |
|---|---|---|---|---|
| 1 | `core/graphrag/multi_hop_expansion.py:300-328` | `expand()` discovers nodes at depths >1 (nodes list correct) but `result.paths` never advances parent paths between hops — `active_paths` was never reassigned, so only 2-node paths were ever emitted even in a 3-node chain; multi-hop reasoning trails (workflow/GraphRAG consumers) truncated | HIGH | `tests/test_bughunt_graphrag.py::TestMultiHopPathExtension::test_paths_extend_beyond_one_hop` |
| 2 | `core/graphrag/multi_hop_expansion.py:666` (SQL expander) | `result.metadata["error"] = str(e)` on SQLite (PG-only recursive CTE) stashed the raw driver error **including the full SQL + bind params** into metadata — electric detail could surface to route callers; marker-asserted | MED | `tests/test_bughunt_graphrag.py::TestSQLExpanderErrorHygiene::test_expansion_failure_does_not_leak_exception_text` |
| 3 | `core/turn_fact_vector_store.py:90-97` | `search_relevant_fact_ids()` ignored its `workspace_id` argument; the default-constructed handler searched partition `default` → non-default workspaces always got empty recall | HIGH | `tests/test_bughunt_graphrag.py::TestTurnFactVectorWorkspaceScoping::test_vector_recall_search_scoped_to_workspace` |
| 4 | `core/turn_fact_extractor.py:862-865` (`prefetch_relevant_facts`) | Tier-2 hydration pulled SQL rows **by ID only** — a LanceDB hit (one-open workspace A) could hydrate a B-scoped request → cross-workspace data exposure | HIGH (cross-tenant) | `tests/test_bughunt_graphrag.py::TestTurnFactVectorWorkspaceScoping::test_hydration_never_crosses_workspaces` |
| 5 | `core/turn_fact_extractor.py:412` | `_clamp(float(item.get("confidence", 0.8)))` — a single `"high"` string made `float()` raise inside `_extract`; the public `extract_from_turn` caught it and returned `[]`, **silently dropping every valid fact of that turn** | MEDIUM | `tests/test_bughunt_graphrag.py::TestExtractionParseRobustness::test_non_numeric_confidence_does_not_drop_whole_turn` |
| 6 | `core/entity_type_service.py:47-52,1037-1040` | `close()` closed the session **even when the caller injected their own** `db` (docstring promised "Only close if we created the session") → broke the caller's transaction; fix records `self._owns_session = db is None` and only closes owned sessions | LOW | `tests/test_bughunt_graphrag.py::TestEntityTypeServiceSessionLifecycle::test_close_preserves_injected_session` |
| 7 | `test_bughunt_graphrag.py` (harness) | Initial `test_non_numeric_confidence` was flaky: the `SessionLocal` patch was **not held across `extract_from_turn`** (patch scope bug) → hit the real `atom_dev.db` during Debugger runs; a pre-existing "must use Stripe" row drove the EWMA branch (`0.7*0.8+0.3*0.8 = 0.7999999999999999`). Product EWMA is correct — float artifact only arose from the leak. | — | — |

## FIXES APPLIED (minimal, verified)
- `multi_hop_expansion.py` — init `new_paths: List[ExpansionPath] = []`; append each extended path to **both** `result.paths` and `new_paths`; `if new_paths: active_paths = new_paths` at hop end (also deleted a stale `#` comment).
- `multi_hop_expansion.py` — SQL expander `except`: `result.metadata["error"] = "expansion_failed"` (generic code; detail stays server-side via `logger.error`).
- `turn_fact_vector_store.py` — `safe_ws = str(workspace_id or "").replace("'", "''")` and `filter_str=f"workspace_id == '{safe_ws}'"` (skipped when empty) into the LanceDB `handler.search`.
- `turn_fact_extractor.py` — hydration SQL now filters `TurnFact.workspace_id == workspace_id`.
- `turn_fact_extractor.py` — new `_coerce_confidence(value)` (`_clamp(float(value))`, `except (TypeError, ValueError): return 0.8`); `_extract` uses it (bad item → default, turn never dropped).
- `entity_type_service.py` — track `self._owns_session = db is None` in `__init__`; `close()` closes only when owned.

## TESTS
- New: `backend/tests/test_bughunt_graphrag.py` — **7 tests, all GREEN** (3 consecutive runs: 7 passed, 9.7s/8.3s/11.2s).
- Red–Green: 6 tests were RED at first write, GREEN after minimal fix; `test_path_relevance_uses_config_decay` passed from the start (stays as guard).

## REGRESSION CHECK
- Targeted set (graphrag_engine, graphrag_hybrid_search, graphrag_patterns, graphrag_enhancements, graphrag_sql_injection, graphrag_sql_injection_fix, turn_fact_extraction, turn_fact_queue): **190 passed, 3 failed** — ALL 3 are pre-existing stale-seam failures in `tests/test_graphrag_sql_injection.py::TestGraphRAGSQLInjectionBugs` (`test_source_code_reveals_vulnerability`, `test_escape_like_pattern_method_missing`, `test_validate_search_input_method_missing`) asserting the OLD vulnerable code shape; `core/graphrag_engine.py` is untouched by this change — not my regression.
- `git stash` baseline earlier confirmed 11 failures in `tests/test_entity_type_service.py` (`TypeError: 'workspace_id' invalid kwarg` — test/model mismatch) are pre-existing, unrelated.
- mypy (MYPYPATH resolved): 0 new errors on the 4 files; all reported errors are the repo's existing Column-vs-plain baseline, none on lines I changed.
- Cleaned 3 stray rows my out-of-scope Debugger runs had written to `backend/atom_dev.db` (`DELETE turn_facts WHERE fact_text IN ('must use Stripe','7-day SLA')` + `workspace_id IN ('ws1','ws-test')`); DB back to 0 rowfacts.

## UNRESOLVED
- The transient EWMA float mystery (**resolved as test-harness bug**, not product): single-call `_persist_one` with a pre-existing same-hash row legitimately EWMA-bumps channel-confidence — expected behavior; the asymmetry came from patch scoping.
- `test_graphrag_sql_injection.py` 3 failures + `test_entity_type_service.py` 11 failures remain for the OWNER of those files (out of scope here — no DB / no model changes made).