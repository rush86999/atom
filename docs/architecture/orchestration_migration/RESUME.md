# Resume — chat-orchestrator preview + search-correctness slice

Last updated: 2026-09-27. Read this first, then
`notes/AGENT_COORDINATION.md` (tail) for the full narrative.

**The single next task is `PREVIEW-01`.** Do not start ranking work, the mailbox
gate, the reranker benchmark, or the lifecycle matrix until it is fixed and
re-verified in the UI.

---

## 1. Right now

| | |
|---|---|
| Preview (leave running) | **http://localhost:3091** — `admin@example.com` / `preview-only-local-2026` |
| Isolated backend | `http://127.0.0.1:8091` (pid 19840) |
| World / fingerprint | `search_preview`, export `cab156952d250411`, built 22:44:37 |
| Real model | `llama3.1:8b` via Ollama on loopback; UI badge reads `o4-mini` (an alias to the same weights) |
| User's env | **untouched** — live backend `:8001`, frontend `:3000`. Never restart them for the preview. |
| Credential isolation | **proven** against the running server's DB |
| HEAD at time of writing | `59f6ca6d5` |

Verified in real Chromium: **11 pass / 0 fail / 1 cosmetic** (empty `<title>`).
Working: login, general chat with a real model, formatting, explicit re-search,
reload, WebSocket status updates. Broken: **the named-file price lookup**.

---

## 2. `PREVIEW-01` — the next task, already diagnosed

**Symptom.** *"In Consolidated Price List 2019.xlsx, what is the list price for
U-22 and SLE24-16?"* answers `no matching row in the indexed content searched`
for both — for rows that exist.

**Isolated trigger.** Asked **first** in a fresh session it WORKS and returns the
exact binding:

> `U-22 - 1,777 (LINMAC!R26 matched at A26, column C26 'List Price'; also M26 'List Price_2' 1,777)`

Asked **after any general-chat turn** it MISSES. Not scale, not the short form,
not the data, not the fixtures.

**First divergence is AFTER retrieval.** The failing turn's durable scan trace
records:

```
per_item: {"U-22": "matched", "SLE24-16": "matched"}
dataset_entries: 46   catalog_rows_seen: 47   catalog_truncated: false
probe_failed: false
```

…and the reply still says "no matching row". The assistant message has
`structured_result: None` plus `pending_file_result` and `_pending_file_task`.

**Mechanism.** Two readers of the same dataset disagree *inside one turn*. The
planner's named-file scan matches; the pending-file direct reader misses; and the
**pending result is what gets rendered and pinned**. The pending objective is
reconstructed from history (`[pending-file-task] legacy recovery`), and that
history-tainted context is what the reader runs with.

**Files, in the order the evidence points at them:**

| File | What to look at |
|---|---|
| `backend/integrations/chat_orchestrator.py` | `_direct_confirmed_file_read` (~7166) — passes `history[-6:]` + the reconstructed objective into `_datasets_named_file_block`. Also ~4438 and ~4990–5060 where `_pending_file_result` is read and pinned. |
| `backend/core/pending_file_task.py` | `recover_pending_task_from_history` / `matching_pending_task` — the reconstruction that taints the context. **⚠ another stream has ~254 uncommitted lines here.** |
| `backend/core/answer_presentation.py` | `_render_target` (~387) emits the "no matching row" sentence from `identity.status == "none"`. **⚠ ~309 uncommitted lines from another stream.** |

**Where to start.** The cheapest discriminating experiment: in
`_direct_confirmed_file_read`, log the `original` objective, the resolved
`item_tokens`, and the per-item outcomes it receives, then reproduce the
general-chat-then-lookup sequence. If the item tokens or the history-tainted
context differ from the working case, the fix belongs in the reconstruction; if
they are identical, the fix belongs in the render precedence (the pending result
must not outrank the turn's own scan).

**Do not** make the pending result win by suppressing it wholesale — the resume
path exists for a reason (2026-09-23: a timed-out turn lost the user's read
entirely). The fix is precedence *within* a turn that ran its own scan, not
removal of the feature.

**Definition of done:** M02 returns the bound price in the UI; formatting,
re-search and reload still work; a NEW fingerprint is taken; then M02 goes back
on the supported list in `MANUAL_TEST_QUICKSTART.md`.

---

## 3. Concurrency — read before you touch anything

**Another stream is working in the same area.** At time of writing:

- Uncommitted by them: `core/answer_presentation.py` (+309), `core/pending_file_task.py` (+254), `scripts/orchestration_acceptance/preview_server.py` and `preview_stack.py` (new, competing preview infrastructure), `MANUAL_TEST_QUICKSTART_PREVIEW_V1.md`, `acceptance/preview_browser/`.
- They are mid-way through a WebSocket churn fix: `59f6ca6d5` — *"HAZARD IDENTIFIED, FIX NOT TEST-VERIFIED"*, explicitly unproven, and they note the regression suite does not pass.
- They independently diagnosed the same socket churn I measured. Coordinate rather than duplicate.

**House rules here:** stage by path, never `git add -A` (it has already absorbed
other people's in-flight work twice today — `6995c7e27` swept mine in). Do not
commit another stream's uncommitted files. Do not edit an export under a running
server.

---

## 4. Environment gotchas that cost real time

1. **A stale world export silently invalidates every result.** `build_world` only
   runs with `--rebuild-world` (or a missing `MANIFEST.json`), so after a
   production edit the server keeps executing the *previous* immutable export.
   This made a fixed bug look unfixed. **Always `--rebuild-world` after a
   production change** and re-fingerprint.
2. **`TESTING=1` overrides `DATABASE_URL`** (`core/database.py`) and forces
   `backend/test_integration.db`. Out-of-band writes silently land in the wrong
   database. Isolate with an explicit `DATABASE_URL` instead.
3. **The world is an immutable export; `run_isolated.py` is owned by another
   stream.** Import its machinery, don't edit it.
4. **Disk.** Acceptance worlds are ~1.7 GB each; the directory reached 68 GB and
   exhausted twice, truncating an export mid-build into a spurious `OSError`.
   Check `df` before building. Only worlds *you* created should be removed.
5. **A stale provider shim on `:8099`** serves an old script and produces a
   false failure. Check the port before running Layer 2.
6. **Next.js refuses a second `next dev`** in one directory, and Turbopack
   rejects out-of-root symlinks — hence the symlink farm plus `--webpack`.
7. **The router inherits learned preferences** from the developer's DB
   (254k `llm_routing_feedback` rows) and steers chat at cloud providers the
   sandbox denies. Worked around with the app's own `OPENAI_BASE_URL` +
   `ATOM_PROVIDER_MODEL_CATALOG_PATH` and an Ollama alias for the route name the
   complexity map selects.
8. **First turn after launch is slow** (50–95s) and can hit the turn budget.
   Both model names are warmed at launch; if a first message returns "ran past
   its time budget", send it again.

---

## 5. Done — do not redo

**Search correctness** (`acceptance/search/`, README §1.1 has two corrections).
51 labeled scenarios, 17 categories, 16 held out by category. Candidate 51/0/0.
Baseline `52e6193a7` on the same corpus: 32p/13f/6b — **13 previously-failing
cases now pass, 6 previously-blocked cases are now exercised and pass, 0
regressions.** The false-absence category went 0/6 → 6/6. Eleven confirmed
defects fixed (per-leg coverage envelope, lexical-leg error swallowing,
destructive query truncation at 5 sites, embedding-checkpoint-as-reranker,
blocking inference, positional score mapping, hardcoded store path, and three
found by the harness in my own new code). Evaluator 13/13 negative controls.

**Credential isolation** (`acceptance/preview/credential_isolation.py`) — closed,
with a proven negative control.

**`PROBE-CACHE-01`** — fixed and pinned (`tests/test_named_file_probe_regressions.py`,
6 tests). A probe MISS is no longer cached for 300s. **This is not the
`PREVIEW-01` cause**; the browser repro still misses with the fix in place.

**Also unclaimed, deliberately:** mailbox `hybrid_min` gate unmeasured; no real
reranker evaluation; contextual indexing not attempted; token streaming
unexercised (0 token events — status only); C00–C26 lifecycle matrix open;
canvas editing / sandboxed outbound / live connectors excluded and unverified.

---

## 6. File map

```
docs/architecture/orchestration_migration/
  MANUAL_TEST_QUICKSTART.md            ← what the user reads (M02 currently off the list)
  acceptance/preview/
    preview_launch.py                  launch / isolation / credential sanitize+prove / --stop
    preview_login.py                   sets the world-local admin password, logs in for real
    preview_verify.py                  11 browser checks + screenshots
    credential_isolation.py            sanitize + independent proof
    preview_verification.json          incl. reporting_corrections + preview_01_trace
    preview_state.json                 live pids/ports/paths/model/fingerprint
  acceptance/search/                   the search corpus, evaluator, runners, baseline ablation
backend/tests/
  test_search_outcome_contracts.py     30 tests (coverage, constraints, reranker)
  test_named_file_probe_regressions.py 6 tests (miss-freezing, short form)
```

Re-verify the preview: `preview_login.py` then `preview_verify.py`.
Restart it: `preview_launch.py --port 8091 --frontend-port 3091 --name search_preview`
(add `--rebuild-world` after any production change).
