# TDD Bug Hunt Log — End-to-End (Frontend → Backend)

Phased red-green bug hunting across full-stack flows. Each entry: a test was
written first (red), the root cause confirmed, then the minimal fix applied
(green). Mirrors the Phase 301 bug-catalog convention from `.planning/STATE.md`.

## Bugs Found & Fixed

### BUG-001 — Agent crash-recovery doesn't stamp a recovery marker
- **Flow:** Phase 1.1 — Background jobs + crash recovery (backend core)
- **Symptom:** `reconcile_orphaned_executions()` recovers orphaned
  `AgentExecution` rows but leaves `metadata_json` untouched, so operators
  cannot distinguish a crash-recovered agent failure from a genuine logic
  failure. The module's own docstring (execution_recovery.py:52-53) promises
  the marker should exist; only the `WorkflowExecution` path actually stamps it.
- **Root cause:** `_recover_agent_executions` set `status`/`error_message`/
  `completed_at` but never wrote a `recovery` marker, unlike the sibling
  `_recover_workflow_executions` which stamps `context`.
- **Test:** `tests/test_execution_recovery.py::TestReconcileOrphanedExecutions::test_agent_recovery_stamps_metadata_marker`
- **Fix:** Stamp `metadata_json["recovery"] = {"crashed": True, "recovered_at": <iso>}` in `_recover_agent_executions`.

### BUG-002 — `budget_exceeded` sentinel leaks into `execute()` return payload
- **Flow:** Phase 1.3 — Agent ReAct loop + budget gate (backend core → API/WS)
- **Symptom:** When the pre-LLM budget gate denies, `GenericAgent.execute()`
  breaks the loop with the internal sentinel `status="budget_exceeded"` and
  returns it verbatim in the result payload. The DB-persistence path in
  `atom_meta_agent` maps it to `"failed"` before committing, but the
  **returned** payload (serialized into the HTTP response and WS broadcast)
  carried the invalid `"budget_exceeded"` value. Any frontend/API consumer
  branching on status would hit an off-enum value.
- **Root cause:** The normalization (`budget_exceeded → failed`) existed only
  at the DB write site, not at the execution-return boundary, so the in-memory
  return value and the persisted row could disagree.
- **Test:** `tests/test_budget_control.py::TestBudgetExitStatusContract::test_execute_returns_valid_status_when_budget_denied`
- **Fix:** Normalize `budget_exceeded → failed` in `GenericAgent.execute` just before constructing the return payload, so the returned status is always a valid `ExecutionStatus`.

### BUG-003 — `compute_freshness_status` crashes on tz-naive `now` (TypeError)
- **Flow:** Phase 1.5 — Doc freshness → GraphRAG cascade (backend core)
- **Symptom:** `compute_freshness_status(last_verified_at, now=naive_now)` raises
  `TypeError: can't subtract offset-naive and offset-aware datetimes` when a
  caller passes a tz-naive `now` (e.g. from a SQLite cell or `datetime.utcnow()`)
  while `last_verified_at` is tz-aware (the Postgres storage type). This would
  crash the entire freshness re-evaluation sweep on the production path.
- **Root cause:** The `_aware()` coercion helper was applied to
  `last_verified_at` and the source-modified timestamps but NOT to `now`, so
  the subtraction at line 111 mixed offset-aware and offset-naive datetimes.
- **Test:** `tests/test_doc_freshness_service.py::TestFreshnessMath::test_naive_now_with_aware_last_verified_does_not_crash`
- **Fix:** Apply `_aware(now)` before the subtraction in `compute_freshness_status`, symmetric with the other operands.

### BUG-004 — `useWebSocket` streaming-clear keys on redundant `complete` flag, not message `type`
- **Flow:** Phase 3.1 — WebSocket canvas sync (frontend hook → backend WS)
- **Symptom:** `useWebSocket.ts` deletes an accumulated streaming buffer only when
  `message.complete` is truthy (line 98), but enters the streaming branch on
  `message.type === "streaming:complete"` (line 90). These are two independent
  signals. A `streaming:complete` message without the redundant `complete: true`
  field leaves the partial text in `streamingContent` forever → stale streaming
  text lingers in the UI after the stream finishes.
- **Root cause:** The deletion predicate was coupled to a redundant field
  (`complete`) instead of the authoritative signal (`type`). Both backend
  emitters (`atom_agent_endpoints.py:1971`, `agent_execution_service.py:332`)
  happen to send `complete: true` today, so the bug is latent — but any backend
  change that drops the redundant field silently breaks the UI.
- **Test:** `frontend-nextjs/hooks/__tests__/useWebSocket.test.ts` → "clears streamingContent on streaming:complete WITHOUT a redundant complete flag"
- **Fix:** Key the deletion on `message.type === "streaming:complete"` in `useWebSocket.ts`.

### BUG-005 — `useWebSocket.sendMessage` throws `InvalidStateError` while socket is CONNECTING
- **Flow:** Phase 3.3 — WebSocket canvas sync (frontend hook)
- **Symptom:** `sendMessage` calls `wsRef.current?.send(...)` which only guards
  `null`. A real browser `WebSocket.send()` throws `InvalidStateError` while the
  socket is still CONNECTING (readyState 0). A canvas component that calls
  `sendMessage` synchronously on mount — before `onopen` fires — crashes.
  `subscribe`/`unsubscribe` already guarded on `readyState === OPEN`; `sendMessage`
  was the inconsistency.
- **Root cause:** Missing `readyState === OPEN` guard, unlike the sibling
  `subscribe`/`unsubscribe` helpers in the same hook.
- **Test:** `frontend-nextjs/hooks/__tests__/useWebSocket.test.ts` → "does not throw on sendMessage while socket is CONNECTING"
- **Fix:** Guard `sendMessage` on `wsRef.current?.readyState === WebSocket.OPEN`.

### BUG-006 — `SlashCommandBar` masks 200-with-error-body responses as success
- **Flow:** Phase 3.4 — SlashCommandBar → `/api/atom-agent/chat` (frontend → backend)
- **Symptom:** The bar extracts `data.response?.message || data.message || 'Done.'`
  and always calls `toast.success(...)`, without checking `data.success`. The
  backend frequently returns HTTP 200 with a logical error envelope
  `{success: false, error: "..."}` (governance denial, internal error — see
  `core/atom_agent_endpoints.py:204,238,693,946`). On such a response the bar
  shows a misleading "Done." success toast and clears the input, so the user
  believes their command ran when it was rejected.
- **Root cause:** Missing `data.success === false` check before the success path.
- **Test:** `frontend-nextjs/components/boards/__tests__/SlashCommandBar.test.tsx` → "shows an error toast (not success) for a 200-with-error-body response"
- **Fix:** Check `data.success === false` in `SlashCommandBar.submit` and surface an error toast (and don't clear the input).

### BUG-007 — `ViewOrchestrator` crashes on a `view:switch` message with no `data` field
- **Flow:** Phase 3.5 — WebSocket canvas sync (frontend canvas component)
- **Symptom:** A `view:switch` WebSocket message with a valid `type` but no
  `data` wrapper causes `TypeError: Cannot read properties of undefined
  (reading 'layout')` at `ViewOrchestrator.tsx:70`. The handler's `try/catch`
  does NOT catch it because the error is thrown inside the
  `setOrchestration(...)` updater callback, which React invokes asynchronously
  outside the try/catch. The uncaught error propagates to React's error boundary
  and takes down the entire canvas UI.
- **Root cause:** No null-guard on `lastMessage.data` before the type branches;
  the state updater dereferenced `data.layout`/`data.views` directly. The broad
  try/catch gave a false sense of safety but doesn't cover async state updaters.
- **Test:** `frontend-nextjs/components/canvas/__tests__/view-orchestrator.test.tsx` → "ignores a view:switch message with a missing data field without crashing"
- **Fix:** Early-return when `data` is missing in the `ViewOrchestrator` WS effect.

### BUG-008 — Admin budget routes return logical errors as HTTP 200
- **Flow:** Phase 2.4 — Admin budget route (backend API)
- **Symptom:** The new admin budget endpoints returned logical errors with HTTP
  200: GET for a nonexistent tenant returned `200` with a default budget body
  (no existence check at all); PUT for a nonexistent tenant returned `200` with
  `{"error": "Tenant not found"}`; PUT with an invalid `enforcement_mode`
  returned `200` with an error body. Any client checking `response.ok` would
  silently treat these failures as success.
- **Root cause:** Handlers returned plain dicts for error cases instead of
  raising `HTTPException` with the appropriate 4xx status code; GET didn't
  verify tenant existence.
- **Test:** `tests/test_admin_budget_routes.py` (4 tests covering 404/422/200 contracts)
- **Fix:** Raise `HTTPException(404)` for unknown tenants (GET + PUT) and `HTTPException(422)` for invalid enforcement_mode in `api/admin/budget_routes.py`.
