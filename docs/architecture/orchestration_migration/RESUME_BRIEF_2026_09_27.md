# Resume brief — chat orchestrator app readiness

Written 2026-09-27. Everything below was **measured**, not remembered. Where a
result did not reproduce, that is said plainly rather than carried forward as a
finding.

Read this first, then the two documents it points to. Do not re-derive state
from the coordination notes — they are append-only and contain superseded
claims from several agents, including two of mine.

| Document | What it is |
|---|---|
| `CHAT_ORCHESTRATOR_READINESS_REPORT.md` | The evidence. §1–§10 the preview milestone; **Addendum (A1–A9)** the task-correction work and every remaining gate. |
| `MANUAL_TEST_QUICKSTART_PREVIEW_V1.md` | What a human tests, and the explicit **excluded** list. |
| `notes/AGENT_COORDINATION.md` | Append-only log. Last two entries are mine (2026-09-27); earlier ones include superseded claims. |

---

## 1. Bottom line

**The manual-test preview milestone is met. The supported-workflow readiness
gate is NOT.** Replacement of a list item is a **correctness blocker** and is
**excluded** from the verified support list.

| Claim | State |
|---|---|
| Isolated app, browser-drivable, real model | **met** — 9/9 isolation checks, `opencode-go`/`kimi-k2.7-code` |
| Workbook eight-item lookup vs frozen expectations | **met** — 8/8 (was 2/8) |
| Restart durability incl. byte-identical pin survival | **met** — 11/11 |
| Honest failure reporting (corrupt source ≠ absent) | **met** — 5/5 |
| Credential isolation | **met, after fixing a real gap** |
| Cold-world initial request | **met** — 4/4; the earlier 1/4 did not reproduce |
| **Truthful task correction (replacement)** | **NOT MET — 0/4** |
| Finalization failure (`5b`) | **NOT MET — 0/4** |
| Streaming / transport-retry matrix cases | **NOT EXERCISED** |

## 2. Live state right now

| | |
|---|---|
| Measured preview | **http://localhost:3101** (backend :8051) — `verify` = **9/9** |
| Preview world / fingerprint | `preview_v1`, `code_snapshot_sha256=d1288df33d2f…`, run `run-75c6ae75fb08`, pid 22715 |
| Candidate (unpromoted) | backend :8071, world `candidate_fix1`, `ff582c5dc8659…`, run `run-28e1c915d640`, pid 22881 — `verify` = 7/9 |
| Your own stack | backend :8001 (pid 76942) and frontend :3000 — **never restarted or modified** |
| Model access | `opencode-go`, `deepseek`, `openrouter` keys seeded (encrypted BYOK store) |
| git | **nothing committed.** All work is unstaged working-tree changes |

The candidate is at 7/9 rather than 9/9 for one reason only: the preview
frontend is a symlink farm with a **single** `distDir`, so a second frontend
instance collides on Next's lock. Two backends coexist fine; two frontends need
a second farm. The candidate is API-only for that reason — which is all the
public-boundary tests need.

**Do not delete acceptance worlds.** An earlier pass reclaimed 17.5 GB by
removing stale `runs/` dirs in worlds with no live process; that is done and no
further cleanup is needed or wanted.

## 3. Commands

```bash
cd /Users/rushiparikh/projects/atom/backend

# state
venv314/bin/python scripts/orchestration_acceptance/preview_stack.py --world preview_v1 verify
venv314/bin/python scripts/orchestration_acceptance/preview_stack.py --world candidate_fix1 verify

# restart a stack (--world goes BEFORE the subcommand)
venv314/bin/python scripts/orchestration_acceptance/preview_stack.py --world preview_v1 down
venv314/bin/python scripts/orchestration_acceptance/preview_stack.py --world preview_v1 up \
  --backend-port 8051 --frontend-port 3101

# re-snapshot a world onto the current working tree (creates a NEW database)
venv314/bin/python scripts/orchestration_acceptance/run_isolated.py \
  --name <world> --port <p> --cases true_eight --samples 1 --lifecycle \
  --snapshot-working-tree --rebuild-world --refreeze-db
```

## 4. The blocker, and exactly where it is

`Replace U-22 with U-38` returns the previous list. **Four** layers, not the
three first identified (detail in report Addendum A1):

1. **FIXED** — `supersedes_pending_task()` matched the verb and *popped* the
   stored file task, destroying the objective before any lane could revise it.
2. **FIXED** — `_continuation_decision`'s docstring advertises retrieval
   operations `none/read/rerun/refresh`; **`read` was never returned by any code
   path in the repo.** A set edit is exactly the `read` case.
3. **FIXED** — `_resolve_active_items` had only "replace everything" and
   "inherit". No add/remove/replace-one existed. `entity_set_edit` added.
4. **NOT FIXED — this is the whole remaining blocker.** The turn is claimed by
   an unrelated lane first: it answers *"I've added 'Replace U-22 with U-38' to
   your Tasks"*, i.e. `_handle_task_request`
   (`chat_orchestrator.py:14151`) creating a real task row, reached via
   `ChatIntent.TASK_MANAGEMENT → FeatureType.TASKS` (`:13819`). The intent
   classifier reads "replace" as an action verb, so the turn never reaches the
   resume lane where fixes 2 and the durable revision live.

Verified in isolation against the candidate world, all three fixed gates behave
correctly: `supersedes_pending_task → False`, `matching_pending_task → MATCH`,
`entity_set_edit → {replace, −U-22, +U-38}`. **The machinery is right and not
connected.**

Also found while unwinding this: the durable task's `entities` had **no
production reader** — write-only bookkeeping. A corrected revision would have
changed nothing on its own.

## 5. Next steps, in order

1. **Stop the intent classifier routing a set edit to `FeatureType.TASKS`** when
   an active file objective exists — and confirm the resume lane is actually
   *entered* for the turn. A second gap sits alongside: even with TASKS excluded
   the resume lane is not entered. Everything else is already in place beneath
   this, so this is one focused change, not a redesign.
2. Re-run the gate. Replacement returns to the support list **only at 4/4**:
   ```bash
   venv314/bin/python scripts/orchestration_acceptance/task_correction_acceptance.py \
     --base http://127.0.0.1:8071 --db <candidate run db>
   ```
   Covers replacement, replacement→formatting, replacement→re-search, and
   reload-after-replacement. Each asserts four properties: task revision,
   real retrieval, evidence bindings, displayed list.
3. `5b` finalization: the forced-failure injection does not fail the execution
   (`execution_status: success`), so nothing downstream is measured. Get the
   injection to actually fail, then capture pre- and post-finalization output.
4. `6_streaming_consistency`: run the token-bearing shim. The real-model
   browser smoke is liveness, **not** a stream-protocol test; the plan's shim
   requirement is half met.
5. Only then re-take a fingerprint and run the complete matrix.

## 6. Constraints that were given, and are still in force

- **Do not commit the combined unstaged changes wholesale.** Several belong to
  other agents; commits by other streams (`a3ebb7837`, `00084a575`,
  `d5d670596`, `9e46185df`, `e61126cfe`) already swept in-flight edits in.
- **No further world deletion.**
- **Preserve the measured preview**; do replacement work on a separately
  fingerprinted candidate. That is the current arrangement.
- Replacement stays excluded until it passes.

## 7. Things that will waste time if rediscovered

- **`live_integration_acceptance.py` could not run at all** before this session —
  `--code-dir` was registered twice and argparse aborted. Its restart env was
  also a hand-copied list that had already drifted (it omitted
  `ATOM_TASK_LIFECYCLE_ENABLED`), so a "history survived restart" pass would have
  measured that drift. Both fixed.
- **`oauth_tokens` was missing from `CREDENTIAL_TABLES`** and two active
  Zoho/Microsoft grant rows were inherited from the dev snapshot. They survived
  because the stored values are *hashes*, so the table looked harmless. Fixed;
  three secret-*shaped* tables that are genuinely not secrets are now
  documented as deliberately preserved so nobody "fixes" them.
- **The earlier "one named cause" for the 6/8 workbook failures was wrong.**
  There were two independent causes and the real one was neither recorded: the
  evaluator read identity references at the *candidate* level of the artifact
  while production wrote them there and the target level had no `references`
  key. See report §2.
- **A cold world is not slow or broken.** The first ask on a freshly seeded
  world returns all eight items in ~14s. Do not build a cold-start theory
  without a reproduction.
- **`load_structured_result` now requires an `execution_id`.** It deliberately
  refuses a recency fallback, so calling it without one returns `None` — that
  is identity-substitution protection, not a bug.
- **A validator that fails correct output is worse than none.** The
  evidence-binding validator was wrong three times before it was right; its
  first version passed a reworded sheet name, an invented price and a stale
  list. Gating checks are now separated from advisory ones for that reason.

## 8. Where the evidence lives

```
docs/architecture/orchestration_migration/
  CHAT_ORCHESTRATOR_READINESS_REPORT.md      findings + Addendum A1–A9
  MANUAL_TEST_QUICKSTART_PREVIEW_V1.md       human test script + exclusions
  MANUAL_TEST_QUICKSTART.md                  ANOTHER agent's preview (:3091)
  acceptance/
    task_correction_results.json             0/4 — the blocker, itemised
    restart_durability.json                  11/11
    preview_browser_results.json             M01–M08, isolation proven
    preview_browser/*.png                    per-step screenshots
backend/scripts/orchestration_acceptance/
  preview_stack.py           isolated stack, launch, 9 isolation checks
  browser_verify.py          Playwright; records every request/WS origin
  restart_durability.py      restart through the real launch path
  task_correction_acceptance.py   the 4 replacement sequences (0/4)
  run_isolated.py            world build, evaluators, 50 selftest assertions
  live_integration_acceptance.py  the 12-case matrix
```

Another agent maintains a **second** preview on :3091/:8091 and owns
`MANUAL_TEST_QUICKSTART.md`; it independently recorded the workbook lookup as
open defect `PREVIEW-01`. The two corroborate each other. Do not clobber
either — the filename collision already cost one quickstart.
