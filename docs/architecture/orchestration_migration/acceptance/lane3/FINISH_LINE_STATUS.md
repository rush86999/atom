
# FINISH_LINE_STATUS — current status ledger for the D5 browser-edit closeout

> **ONE accounting table in this file:** "F01–F12 accounting — CURRENT" at the
> bottom, bound to the pinned browser candidate P. The candidate-A results (F02b,
> F09, F10) were merged into it on 2026-09-28; the earlier duplicate tally is
> gone and its evidence is preserved in `lane3/f02_negative_control/`,
> `lane3/f10_keyed_retry/` and `tests/test_f09_supersede_terminal_delivery.py`.
>
> Companion authorities: `acceptance/FINISH_LINE_ACCOUNTING_2026_09_28.md` (REV 2),
> `lane3/FINISH_LINE_CURRENT_STATUS.md`, `lane3/CANDIDATE_FREEZE.json`,
> `lane3/RESUME_finish_line.md`.

Date: 2026-09-28. Assignment: `FINISH_LINE_EXECUTION_GUIDE_2026_09_28.md`.
**This is the only current status for this assignment.** Older lane evidence is linked, never rewritten.

Guide §3 forbids world deletion, sidecar removal, retention apply and portable-drive
relocation. All were observed as violated *before* this ledger existed; they are
recorded here as pre-existing state, not as work performed under this assignment.

---

## 1. Source provenance

Base commit: `1a953b58934d` — matches the guide's stated HEAD. Rechecked.
Planner contract commit `6e34725c7` is in history.

The serving source is **dirty**. sha256 (16) of the included product files:

| File | sha256(16) |
|---|---|
| `backend/core/chat_canvas_editor.py` | `c26e9a892f9c4bef` |
| `backend/core/chat_tool_planner.py` | `9ffaad02421039b3` |
| `backend/integrations/chat_orchestrator.py` | `e14101821aed9248` |
| `backend/core/async_turn_continuation.py` | `ffb44bf857b1cb08` |
| `backend/core/acceptance_barrier.py` | `a059dfca3f73a046` |
| `backend/core/db_safety.py` | `39bacf243002aba8` |
| `backend/tools/canvas_crud_tool.py` | `eb43c63931a1e40d` |

Harness/storage files, sha256 (full):

| File | sha256 |
|---|---|
| `backend/scripts/orchestration_acceptance/storage_policy.py` | `788b3e6a64e2a4a3ace442b24ef6efeb00b1500a23d17758ad0dcc4d06e73ced` |
| `backend/scripts/orchestration_acceptance/run_isolated.py` | `8c4e16bb5cdca56f1e79b22b7a7dc2dd19a133cab07d632d4712bb46389e54d4` |
| `backend/scripts/orchestration_acceptance/preview_stack.py` | `0cef2d53b2f17ed58f2e18c98776c51a347027fb9764038648d8007110cf3737` |
| `backend/tests/core/test_storage_policy.py` | `70e1f6ba214df23cb360745e26e1a5a3998f44777299f595d8c2cb326d40630b` |
| `backend/tests/core/test_storage_policy_fail_closed.py` | `a7d826559ed1aff0ff0eafcb63140493072fbcbc291ca42f34cff6f0fdb3518f` |
| `backend/tests/core/test_storage_policy_launcher_wiring.py` | `86486a90acf348dcd64e93db8a27e7f43c5f97f849ae056ac0dc7e6692b9a8cb` |
| `backend/tests/core/test_acceptance_storage_policy.py` | `88cf72e1b8c6e388570a7734ae8aa8c890aac64ab921b887bd26f93cfe927bf2` |
| `backend/tests/test_db_safety_atomicity.py` | `d23f4ab39777b85335df9cfebd8084bd1e598eb1d98f3aa0447a3f9d8e90203f` |

**Named exclusions from the candidate:** `frontend-nextjs/**` (separate farm, guide §3),
`backend/data/**` (disposable worlds; never hashed into a source identity),
`docs/**` (evidence, not code).

No export of the working tree has been frozen for this closeout yet. **F01 is therefore
INCOMPLETE**: there is no export-tree hash and no loaded-module evidence for a serving
process, because no candidate for this assignment has been launched.

### 1a. Candidate launched (2026-09-28, after this ledger was first written)

One small API-seeded candidate, as authorized. `run_isolated.py --name finish_line
--port 8086 --snapshot-working-tree`:

| Item | Value |
|---|---|
| World | `backend/data/acceptance_worlds/finish_line` |
| Run dir / serving DB | `runs/run-f929f7cd2484/data/atom.db` |
| Export tree | `ec0ef5725893…` (46 parquets verified) |
| Revision | `d5d6705960` |
| World identity | `1a953b58934d-dirty.78e1d` — matches the ledger's HEAD |
| Port | 8086 (backend) |
| Seatbelt | yes, credential-free; contract preflight `ok=True` |
| Fixture | `api-seeded-fixture`, 367 tables, 8,477,720 B, **0 dev rows**, live DB not read |
| Bootstrap | app created 1 user (`admin@example.com`, `workspace_admin`), 1 tenant, 1 workspace in the run-dir DB |

The candidate launches, serves healthy, mints a token, and runs cases to completion.
Workbook-read cases then report `requested item absent from artifact` — **expected and
not a write-path failure**: the small fixture deliberately carries no sheet dataset, so
those cases are NOT APPLICABLE on this fixture rather than failed. The full-dev-DB path
remains available only behind `--full-dev-db-snapshot`.

### 1b. The candidate that is ACTUALLY SERVING (read from the process, not the harness)

`preview_stack.json` records a stack for `finish_line` started 15:34:51 local by a
cancelled lane, and its backend is the one answering :8086. Read from
`GET /api/health` on the live process:

| Item | Value |
|---|---|
| `source_id` | `1a953b58934d-dirty.526a9a7135e8` (dirty digest `526a9a7135e8`) |
| `instance_id` | `1a953b58934d-dirty.526a9a7135e8.4988.1790624091` |
| `git_commit` / `revision` | `1a953b58934d` / `1a953b58934d144b2cd149c557d1243e9e16ea1c` |
| pid / port | 4988 / 8086 |
| cwd | `…/acceptance_worlds/finish_line/backend_root` |
| serving DB | `runs/run-cfb0605d01ce/data/atom.db` |
| code snapshot | `f7bb91218dee27532551c366c5d13d57dda5a46e89088568e0eafb7e8c909ec2` |
| BYOK | present in the world (`backend_root/data/byok_keys.json`) → real provider access |
| frontend | **`api-only`; no frontend process, no frontend port** |

**The dirty digest differs from the §1a launch** (`78e1d` vs `526a9a7135e8`) because the
working tree changed between the two launches. Per the guide's identity rule, **all
results in this ledger are attributed to `dirty.526a9a7135e8`**; the §1a launch
(`ec0ef5725893…`) is superseded for result attribution. Loaded-module hashes from the
serving process remain outstanding for F01, and F06/F07 are **blocked** until a frontend
is launched — which additionally requires the farm routing fix (defect 1).

---

## 2. Live-data protection gate (guide §3 precondition)

| Item | State |
|---|---|
| Verified live backup | `backend/data/backups/atom-incident-20260928-20260928-103805.db.gz`, 73,232,526 B, `integrity_check: ok`, 384 tables |
| Backup vs live counts | users 14/14, canvases 94/94, chat_sessions 499/499, chat_messages 2751/2751 — equal |
| Method | validated `mode=ro` → `Connection.backup` → `.partial` → validate → `os.replace` → gzip → decompress-and-revalidate |
| Wipe-detection baseline | `backend/data/db_fingerprint.json`, 736 B, valid JSON, counts `{users 14, agent_registry 9, canvases 94, chat_sessions 499, chat_messages 2751}` |
| Gate state | **ARMED** — `check_wipe_at_startup()` returns without a CRITICAL |

Two facts about that baseline must not be glossed:

1. It is a **CANDIDATE baseline read from the verified backup at 10:38 today**, not a
   recovered pre-incident fingerprint. The original was destroyed by the
   truncate-before-dump defect (missing `import json` in `db_safety.py`), so **a wipe
   that occurred before 10:38 today would not be detected by it.**
2. It is installed mode `0444` deliberately. Pids 71383 (since Sep 16) and 76942
   (since Sep 26) still hold the **pre-fix** module in memory, so their maintenance
   cycle calls `open(path,"w")` and re-truncates it to 0 bytes every cycle — observed
   again at 11:03, after the fix landed at ~10:51. Guide §3 forbids restarting the
   user's :3000/:8001 stack, so the file is made read-only instead: the pre-fix
   `open(...,"w")` now raises `PermissionError` (swallowed at debug, baseline survives)
   while the fixed `os.replace` path still succeeds, because replace needs only
   directory write permission. Verified on a scratch file before applying. **Revert with
   `chmod 644` once those two processes have restarted on the fixed code.**

---

## 3. Storage state (guide §3)

| Item | State |
|---|---|
| `backend/data/acceptance_worlds` | 2 worlds / 20 GB: `write_combined`, `write_verify_0928` |
| Worlds lost 2026-09-28 ~09:32 | 19 worlds, ~80 GB. **Cause NOT established.** |
| Recovery options | none: no Time Machine, empty `~/.Trash`, no APFS Data snapshot, Seagate holds 15 MB + 552 MB of evidence, not worlds |
| Results marked unavailable | 116 result files across 14 deleted worlds — see `backend/data/incident_20260928/worlds_impact.md` |
| Free space | 53 GB of 460 GB (87% used) |
| Deletion/creation policy | **paused by user instruction.** No new full-size worlds. |

Default fixture, **measured**: `provision_api_seeded_fixture` produces
**8,477,720 B (8.09 MiB)** with **367 tables and 0 rows in every one**, against a
32 MiB enforced ceiling (`SMALL_FIXTURE_MAX_BYTES`); exceeding the ceiling raises
`StoragePolicyError`. It is a bare schema, not a seeded world — the name
`api-seeded-fixture` overstates it. Anything needing a user or a canvas must be seeded
through supported API calls at world setup. **Open item for the candidate launch.**

---

## 4. Process and preview state

| Port | Process | World | State |
|---|---|---|---|
| :8004 | pid 71383 `app_r8verify:app`, up since Sep 16 19:49 | live dev DB | holds `atom.db` |
| :8001 | pid 76942 `main_api_app:app`, up since Sep 26 09:40 | live dev DB | holds `atom.db` |
| :3101 / :8051 | preserved read preview (`preview_v1`) | **directory deleted** | **not restartable**; must not be mutated |
| :3102 / :8071 | `candidate_fix1` | **directory deleted** | **not restartable**; must not be mutated |

The two previews are still listening, so they still answer, but their worlds' run dirs
and code exports are gone. They are **not** restartable previews and their availability
must not be promised. Guide §3 forbids restarting them and forbids mutating their worlds.

---

## 5. Candidates in play

**There is ONE accounting table in this file: "F01–F12 accounting — CURRENT" at the
bottom.** It is authoritative. The rows for candidate A's F02b, F09 and F10 have been
merged into it. This section only defines the candidates, because a result belongs to the
candidate and artifact that produced it and `source_id` alone is not an identity.

| ID | World / run | Identity | Configuration | Cases |
|---|---|---|---|---|
| **P** pinned browser *(this table's primary)* | `write_verify_0928` / `run-7240b4691cc1` | base `1a953b58934d`, export `f530c509948d947d`, identity in `CANDIDATE_FREEZE.json` | ports **:8140/:3140**, pin **`deepseek/deepseek-v4-pro`** (disclosed), seeded BYOK, no shim on the F06 path | F01, F02a, F02b, F06, F07 |
| **A** API-only write-path | `finish_line` / `run-cfb0605d01ce` | snapshot `f7bb91218dee…`, `1a953b58934d-dirty.526a9a7135e8` | **api-only, no frontend**; fixture `api-seeded-fixture` (0 dev rows); M1+M2+lifecycle; barrier disarmed; planner unpinned | F02b, F09 (unit/boundary), F10 |
| **S** shim world | `write_combined` / `run-a00d7f4f1105` | export `451468608d397dcb…`, `1a953b58934d-dirty.66597276e30d` | M1+M2+lifecycle, provider = local shim (execution/persistence/verification/delivery production) | F03–F05, F08–F12 branch evidence |
| **D** older browser track | `d5_browser_edit` / `run-26ebe1ca462c` | rev `6e34725c70179…`, export `4f6844df5909…` | ports :8086/:3106, pin `deepseek/deepseek-flash`, injection none | preserved separately; **does not replace P** |

A case one candidate cannot exercise is a **limitation of that candidate**, never a
project-level blocker, and never resets another candidate's result. Do not rebuild the
browser setup or re-run F06/F07 because candidate A has no frontend.


## 6. F10 — keyed retry and payload conflict on candidate A: **PARTIAL**

Evidence: `lane3/f10_keyed_retry/` (`f10_keyed_retry.py` re-runnable, `result.json`).
Candidate A, `run-cfb0605d01ce`, DB `…/runs/run-cfb0605d01ce/data/atom.db`, snapshot
`f7bb9121…`, api-only, M1+M2+lifecycle, barrier disarmed, planner unpinned.

**PARTIAL, not PASS.** Two things are missing: **restart-pin survival is not tested on A**,
and **one assertion failed**. Matching execution ids, identical bytes and zero new
effects are necessary, but on their own they do not establish *which store* answered — so
that was checked directly rather than inferred.

### What was measured

| Case | Result |
|---|---|
| first send | HTTP 200, `execution_id=aee32d68-79b8-41cd-bf23-e06e1bb0cd0a`, executions 8 → 9 (delta 1) |
| replay, same key + same payload | HTTP 200, **same `execution_id`**, **byte-identical answer**, same session, executions 9 → 9, `canvas_audit` 11 → 11 |
| same key + **changed** payload | **HTTP 409**, `execution_id=None`, executions 9 → 9, `canvas_audit` 11 → 11 |

### Which storage mechanism supplied the response — checked, not assumed

The authoritative record is `chat_request_records`, and the resolver is
`reserve_or_replay` in `core/chat_transport.py:64-86`: it queries by
`(tenant_id, user_id, session_id, request_id)` and, on `state == COMPLETED`, returns
`("replay", record)` when `payload_sha256` matches and `("conflict", record)` when it does
not. The live record for the measured key:

```
request_id  5780e096-cc10-4466-a696-2aab633ee604     rows for key: 1
state       completed
payload_sha256  e9f48b7952d553de9763273e5195657eb8ceace0e39b3808a98489d2976b9c42
execution_id    aee32d68-79b8-41cd-bf23-e06e1bb0cd0a   <- matches the replayed response
assistant_message_id  9cc28c29-9823-4b0c-9eb5-17420df71ae7
finalized_response length  830
```

So the replay was served from the **durable** record — one row, `COMPLETED`, carrying the
very `execution_id` the replay returned — and the 409 was the `conflict` branch on the same
table. That is the evidence the earlier "reporting gap" claim needed, and it now holds.

### The failed assertion

`replay_pin` is `null` on this plain chat turn, while the F02b **canvas-edit** turn on the
same candidate reported `{"status": "pinned", "durable": true}`. Given the record above,
the pin is present in the store and the replay honoured it, so the null is a **reporting**
inconsistency in the response body — not a correctness defect. Logged as open defect 8.
**Not counted as a pass.**

### Not covered here

* **Restart-pin survival on A** — untested. Separate established evidence exists on
  candidate **S** (kill mid-flight → `409 {"error":"request_crashed"}`; completed pin
  survives restart as an identical replay, run 6), but that is a different candidate and
  does not complete A's row.
* The `in_progress` and `crashed` resolver branches were not exercised on A.

---

## 7. F02 — the wrong-field change

The guide's F02 has two halves and they are **not** the same result. Keeping them apart
matters: F02b is a *recreated* scenario, not the historical execution.

### F02a — the historical wrong-field write: **UNEXPLAINED. Evidence unavailable.**

The reported failure wrote the **subject**, verified `postcondition_verified: true`, and
told the user "Updated the canvas and refreshed the subject line" for a request about
**body** quote validity. Its run directory, world and log were among the 19 worlds
deleted at 09:32 today. The original evidence **cannot be re-read** and is not
reproducible from what survives.

What survives is a written account of the mechanism, in
`core/chat_canvas_editor.py:2596-2625` (bounded repair → re-ask in replace mode → a full
content payload that changed `subject` → merged field-scoped → written → verified), plus
the earlier attribution to a mismatched scripted `find` string, which remains
**unproven** and is not supported by anything measured here.

**F02a stays unexplained.** The mechanism is documented and fenced; the occurrence is not
attributable to a specific boundary from surviving evidence.

### F02b — recreated missing-target control: **PASS, 9/9**

Evidence: `lane3/f02_negative_control/` (`f02_negative_control.py` re-runnable,
`result.json`, `planner_trace.log`).

**This is a relevant missing-target scenario, not a reproduction of the historical
execution.** A request about the body whose target (`45 days`) is absent from the
canvas, seeded through the product's own endpoints on candidate A.

| Assertion | Observed |
|---|---|
| SUBJECT untouched | `subject_after='Quote for Steve'` |
| subject not replaced with the wrecked variant | `False` |
| body's real text still present | `True` |
| absent target **not invented** into the body | `False` |
| **zero** update audit rows after the seed | `update_rows=0` |
| reply does not claim the subject changed | `False` |
| + 3 seed/baseline assertions | pass |

Durable read, not the transcript. Truthful decline: `no_apply: true`,
`reason: planner_declined`, `outcome: refused`, `background_started: false`, reservation
released, `persistence.status: persisted`, `replay_pin: pinned/durable`.

**Summary line: F02b PASS, 9/9; contradictory plan repaired to an honest decline.**

### F02c — the controlled widening test: **SEPARATE, PENDING**

The ladder's fence against a *widening* repair is **not** exercised by F02b, because
F02b's repair declined rather than widening. Guarded by 15 unit tests in
`backend/tests/test_canvas_repair_scope.py` (**15 passed**); reaching the widening branch
at acceptance level requires controlled plan injection and is **NOT RUN**.

### Model selected for the F02b call

`opencode-go/glm-5.3-flash`, BPC cost-priority for `task_type=planning`. Read from that
call's `[structured-trace]` — not from a provider availability probe.

---

## 8. Blocking preconditions before any candidate launch

1. **World creation is paused by user instruction.** F01–F12 all need a candidate world.
   This is the single blocker; it is a policy decision, not a technical one.
2. If a small candidate is authorised: confirm the storage preflight and the
   `world_storage_guard` interlock are honoured, and seed the required user/canvas through
   supported APIs (the default fixture is an empty 367-table schema).
3. Do not reuse the deleted-world result directories as if they were re-runs.

## 9. Defects found — repaired, and open

### Repaired during candidate launch (all three blocked the supported flow)

| # | Defect | Fix |
|---|---|---|
| R1 | `run_isolated.py:944` called `SP.BUILD_MARKER.name`, but `BUILD_MARKER` is a **filename string**, not a `Path`. `AttributeError` aborted the launch *after* the world was fully built, leaving a build marker that a retention pass is then right to refuse. | Join first, then take `.name`: `(world / SP.BUILD_MARKER).name`. Checked for the same shape on `RUN_LIVE_MARKER` — no other instance. |
| R2 | The harness set `os.environ["DATABASE_URL"]` to the world **after** `core.database` had already been imported. `core/database.py:175` resolves the URL once at import and builds module-level `engine`/`SessionLocal` from it, so the assignment was **inert** and the process stayed bound to whatever it resolved at import — for a repo-root launch, a relative `sqlite:///./data/atom.db` against the checkout root, where a **0-byte `data/atom.db` exists** (dated 2026-09-14). The path-anchoring class AGENTS.md warns about. | New `_point_process_at_world(db_path)` disposes the stale engine, rebinds `DATABASE_URL`/`engine`/`SessionLocal`, and then **verifies the binding against the path it was given**. |
| R3 | Even with R2 fixed, the harness pointed at the **world root's** `data/atom.db` — the frozen fixture, which has no rows and never will. The app bootstraps its admin/tenant/workspace into the **run directory's** DB, which is what the server is launched against (`launch_server.last_run_dir`). So the harness asked a fixture for a user only the run dir had. | Point at `launch_server.last_run_dir / "data" / "atom.db"`. The mint failure now names the database actually bound (`core.database.DATABASE_URL`) instead of blaming the world. |

R2 and R3 were each independently sufficient to produce the same opaque
`could not mint token from scratch DB` while the world was perfectly healthy. That
message named the wrong culprit, which is how a pointer fault gets read as a product
fault.

### Open, not repaired

| # | Defect | Where | State |
|---|---|---|---|
| 1 | `frontend_farm.py` symlinks top-level entries, so the farm's `pages` is one symlink and `next dev --webpack` registers **no dynamic page route**. | `lane3/frontend_farm.py` | **RESOLVED for candidate B** by `lane3/frontend_farm_recursive.py` (427 lines). `/canvas/[id]` loaded and served candidate B. Still a latent trap in the original farm. **Not** an F06 blocker. |
| 2 | `lib/pdf-worker-src.ts` is a bare package specifier inside `new URL(…, import.meta.url)`; webpack refuses it, 500ing the canvas page via `CanvasPanel → PdfFileCanvas`. | `frontend-nextjs/lib/pdf-worker-src.ts` | **OPEN, worked around in the farm** on candidate B by a declared farm shim (both sha256s recorded). The product file is still broken; an email canvas never touches the PDF path, which is why the page served. |
| 3 | `CanvasPanel` applies its `lastMessage` prop only when the parent passes no socket listener, and `/canvas/[id]` passes both — canvas area blank on load and after reload. | `frontend-nextjs/components/canvas/CanvasPanel.tsx` | **OPEN.** This is exactly candidate B's `V2_…rendered_its_content_on_load` and `V6_reload_shows_the_same_canvas_state` failures. A real product defect, not a harness artifact. |
| 4 | API-created canvases have `title: null`, so the canvas detail header falls back to `Canvas <uuid>`. | canvas creation path | **OPEN.** Candidate B's `V2_the_page_shows_the_canvas_type` failure. |
| 5 | A clean planner decline is not quotable without a re-run: the plan's shape is logged only on a contract violation. | planner logging | **PARTLY CLOSED.** The `repair exchange \|` line does carry the original plan's shape, its violation and the repair. A *clean* decline with no contradiction still logs nothing. |
| 6 | `restart_backend.sh` may pass a different snapshot label than the filenames it creates (`atom-pre-restart-*` vs `atom-cycle-*`), so its retention pruning may not match its own files. | `scripts/restart_backend.sh` | **OPEN, unverified.** |
| 7 | `conftest.worker_database` leaves `expire_on_commit=True` while the product's `SessionLocal` sets it `False`; 6 order-dependent failures in `test_canvas_manual_retype.py` / `test_canvas_crud.py` are this mismatch, itself an instance of "a post-commit failure reported as a refusal". | `backend/tests/conftest.py` | **OPEN**, documented follow-up. |


Defects **3** and **4** are the only ones still costing candidate B assertions. Defect
**2** is a live product bug that candidate B did not exercise. Defects 6–7 are follow-ups.

### Export relationship (precise)

The world was **not rebuilt** after the two harness-driver edits, so the export
fingerprint **`f530c509948d947d…` is unchanged** — it is the same tree that
produced F06/F07 and the tree still on disk. The 16 serving application modules
are byte-identical because the exported tree is literally the *same tree*, not
merely an equivalent one.

What did change is the **checkout copies only**; the world export retains the
older copies:

| File | checkout | world export | change |
|---|---|---|---|
| `provider_shim.py` | `05b2b8e1bcec` | `a7542d6c1952` | tool-name-first selection + `selected_by` capture |
| `canvas_write_verify.py` | `e87321a0ff24` | `41f20753370a` | `--expect/--old/--new/--field` for the F07 second edit |

Both are client-side harness drivers run from the checkout as separate processes.
Neither is imported by the serving app, and neither appears among the 16
fingerprint modules. **F06/F07 retain their evidence.**

If a case requires a rebuild, record the **new** export fingerprint alongside
`f530c509948d947d…` and re-verify the 16 module hashes — do not overwrite this
one and do not assert equivalence.

## F01–F12 accounting — CURRENT

Candidate: `write_verify_0928` / `run-7240b4691cc1`, ports :8140 (backend) /
:3140 (frontend), export `f530c509948d947d…`, base commit
`1a953b58934d144b2cd149c557d1243e9e16ea1c`, **planner pin
`deepseek/deepseek-v4-pro`** (disclosed). Identity:
`CANDIDATE_FREEZE.json`. Resume direction: `RESUME_finish_line.md`.

Statuses are PASS / FAIL / INCONCLUSIVE / NOT RUN. A scenario that never reaches
its required branch is INCONCLUSIVE, not a pass. Nothing is removed from the
denominator.

| ID | Status | Evidence / reason |
|---|---|---|
| F01 | **PASS** | Provenance repaired and verified: 15/15 launch checks, **16/16 serving modules** matched to the immutable export, **0** from the mutable checkout, live dev DB untouched (`887` rows / `2026-09-26 10:37:11.129501`) on every run. Farm outside the checkout frontend dir; farm writes symlink-contained. |
| F02a | **UNEXPLAINED** | The 2026-09-27 subject-for-body edit did **not** reproduce on current code; the "mismatched scripted `find`" attribution remains unproven. Fixture deliberately not aligned. Separate from F02b. |
| F02b | **PASS** | Current mismatched-target negative test: target absent → **zero** unrelated mutation, no success claim, `explicit_no_apply`. Does not claim F02a fixed. |
| F03 | PASS (2026-09-28) | Controlled synchronous edit, world `shim_controlled_full` (full dev snapshot, run `run-360b3ac7fd0b`/latest, export `3d557bb137709161`, :8191). `correct_completion=True`, unsupported_claims=0. Injection: 1 `CanvasEditPlan` call, `selected_by=tool+match`, 0 mismatched. Effect: OVLAP-A + "30 days" present, "15 days" gone, audit row carries a real `operation_id`; canonical readback after re-opening the run DB still carries the edit. Reaching this needed 8 harness fixes (shim loader dropped tool-scoped entries; live `__main__` path ignored `tool`; envelope unwrap served empty completions while the capture logged the selection; bare tool key collided across two plans; append-only capture read as cumulative; stale leaked shim on :8099 served an unrelated script; shim leaked on failure; case-side DB access used the working DB while the server used the run-dir clone). Controlled-shim evidence only — implies nothing about the real planner. | Precondition **partially met**: the shim's 2 `CanvasEditPlan` entries are **parser-validated offline against production code** (2/2, `wants_edit=True ops=1`, no contract violation) and selection is now tool-name-first with `selected_by` recorded. Needs a live run to prove selection, acceptance, consumption and one verified mutation. |
| F04 | **PASS** (2026-09-28, controlled shim) | fork proven (stall consumed + durable continuation row), outcome=applied, audit delta 1, audit_id linked | Controlled background success; fork and terminal state must be proven before judging delivery. |
| F05 | **PASS** (2026-09-28, controlled shim) | fork proven, outcome=failed after 3 attempts, audit delta 0, honest summary, no success claim | Controlled background failure. |
| F06 | **PASS (re-verified on the final candidate, browser)** | `79b2a41032c3`, export `64b44f29`, pin `deepseek/deepseek-v4-pro`. Real Chromium, real login, real composer, real canvas page: '15 days' -> '30 days' in the durable canvas, exactly ONE update audit row attributable to an operation_id, survives a real reload, reply truthful ('Changed quote validity from 15 days to 30 days.'). **Functional edit checks all passed; the strict origin-isolation check FAILED**: the canvas page loads Monaco from cdn.jsdelivr.net (26 requests per the run summary; no per-request capture persisted). The capture shows all API/WebSocket traffic on localhost origins; the CDN requests themselves transmit network information and load external code, and no claim is made about their contents. Disclosed exception, kept visible. Negative control on the same candidate with the UNPINNED default: `outcome=explicit_no_apply`, zero mutation, truthful decline. |
| F07 | **PASS** | Second **distinct** supported edit (payment terms `Net 30` → `Net 45`): body changed, subject unchanged, delta exactly 1, operation-linked audit `e8f4e709…`, survives reload, 11/11. Legitimate decline (target absent): **delta 0**, zero update rows, `explicit_no_apply`, 6/6. Restraint under the pin demonstrated. |
| F08 | **PASS** (2026-09-28, controlled shim) | connected leg: exactly 1 chat_continuation frame (status=applied); empty-channel and disconnected legs: 0 frames, both recovered from the durable record; 1 mutation, no duplicate effect | Connected / disconnected / empty-channel completion recovery. |
| F09 | **PASS** (2026-09-28, candidate `d78613777598`, export `5d2bed16f52bbe74`) | Both overlapping turns forked; EACH execution got its own terminal frame AND its own durable record: a=live applied/durable applied, b=live failed/durable failed. No duplicate message, no cross-turn identity mixing, one mutation with one operation id. Exec b's failure is truthful: turn a applied the 15->30 change first, so b's target no longer existed. The earlier PARTIAL run on export `3d557bb13` is retained as `F09_overlap_duplicate_terminal_events.PARTIAL.json` and is NOT combined with this claim. |
| F10 | **PASS** (2026-09-28, re-verified on the current candidate) | 9/9: same key + same payload -> same execution_id, byte-identical answer, 0 new executions, 0 new canvas_audit rows; changed payload -> HTTP 409 with no execution and no effect. Resolved on `chat_request_records`. Serving-module equivalence re-checked: 15/16 byte-identical, `integrations.chat_orchestrator` differs only by the env-gated `ATOM_ACCEPTANCE_BARRIER` test hook and a `log_redaction` import. Restart pin carried from candidate A (6/6) and NOT re-run here. |
| F11 | **PASS 7/7** (2026-09-29, candidate `79b2a41032c3`, export `64b44f29`) | The confined barrier HELD at `continuation_after_effect`; the mutation had committed with no durable terminal record; the process group was SIGKILLed while parked; the effect survived; the restart reused the SAME run dir with no reseed; **no second write**; and after restart the sweep reported "reconciled 1 agent execution with a VERIFIED dead owner" and the session received a truthful terminal message. The missing sweep was NOT the cause -- `_recover_agent_executions()` existed in `d78613777` all along. Three measured defects were on the path: `os.kill(pid,0)` succeeds for a zombie so a killed-but-unreaped owner read `live`; the sweep logged "no orphaned executions found" whenever nothing was RECONCILED, hiding rows left alone; and the state read used /proc then `ps`, which the acceptance seatbelt DENIES, so it silently no-op'd. psutil reads it with no subprocess. Ownership safeguards unchanged: `live`, `unknown` and the pid-reuse check all still hold, and no row is reconciled on unverified ownership. Post-expiry delivery stays covered by its own tests, not by the F09 overlap run. |
| F12 | **PASS 8/8 (API) + PASS 8/8 (real browser)** | `79b2a41032c3`, export `64b44f29`. API-driven: all six workflows answered, four workbook steps grounded with cell references, no mutation claimed, canvases and canvas_audit unchanged, transcript persisted. Real browser (F12B): Chromium, real login form, all eight steps ok, M02 returns real prices with citations, network isolation held. Two setup corrections were required: the workbook had to be REGISTERED in dataset_entries with status='active', workspace_id in context, ONE external_id for the whole workbook, and an ABSOLUTE parquet path; and the first-run 'Welcome to Atom' onboarding wizard had to be dismissed, because its scrim intercepts the composer click. |

### Addendum 2026-09-28 23:03 — F09 automatic post-lease recovery: PASS, live (10/10)

**Export-binding correction (2026-09-29):** this addendum originally cited the
code snapshot as `0d3bd68378faa4ef…`. That was the `write_combined` world's
export, recorded because the results writer read a HARDCODED world's manifest;
the run actually executed world `f09_delivery`'s immutable export
**`80905c7bf1788d2b…`**. The driver is fixed to bind to the run's own world.
See the reconciliation addendum below for what else differs between the two
exports.

`lane3/f09_auto_recovery_0928/result.json`, run
`f09_delivery/runs/run-e1b198fd3421`, code snapshot
`80905c7bf1788d2b…` (corrected; see above), planner = controlled shim (effect-layer evidence
only; implies nothing about the real planner). Real claim-boundary
sequence, nothing seeded: parked at `continuation_after_claim`
(session-matched marker), pre-kill verified (claim taken, terminal message
absent, worker alive, no release), SIGKILLed while held (pid dead, never
released), restarted on the same run dir/DB with the barrier disarmed 9s
later — before lease expiry (lease 90s, interval 5s, both explicit). The
boot pass DEFERRED on the unexpired claim; the recurring task in that SAME
process delivered at claim+93.7s (3.7s after expiry): exactly one terminal
row, wording "already applied … the change is on the canvas" with
`effect_on_canvas=landed`, canvas audit stable, one notification.
Timestamped checkpoints per action: `f09_auto_recovery_0928/checkpoints.jsonl`.

Driver defects fixed to obtain this (harness only, `f09_targeted_cases.py`):
`ensure_shim_alive` crashed on a `SHIM_PORT` NameError (the 21:32 and 21:39
attempts died there and persisted no results); a stale phase-1 arrival
marker made `parked` spuriously true; the fixed 6s/18s observation window
closed ~44s before the 90s lease expired, so a working recovery (delivery
at turn+94s, verified in run-2316226346e7's DB) was recorded as FAIL; and
the wording check's `and` returned a truthy list that `record()`'s `is
True` gate read as FAIL. INVALID gates were exercised en route (run 2
ended INVALID — claim not yet taken at the after-effect boundary — a
scenario correction, not a product defect; no kill performed).

Open observation, recorded not chased: in run-2316226346e7 a later restart
produced two duplicate same-second "could not finish" notifications
(01:29:42 UTC) for an already-delivered outcome.


### Support boundary

Editing is supported **only** for the explicitly disclosed
`deepseek/deepseek-v4-pro` pin, and only for the browser body-edit workflow
measured above. The **unpinned default `opencode-go/glm-5.3-flash` declined every
clear edit, repeatably** — that result is not generalised. The combined preview
is **not promoted**: F03–F05 and F08–F12 remain outstanding.

### Verified-unverified limits (do not report as done)

- PDF worker: asset emitted, served (200, 1.38 MB) and runnable **only as a module
  worker**; the running app has not been observed to request it, so **PDF
  rendering is unverified**.
- Unrelated, unfixed: frontend requests
  `/api/v1/preferences?user_id=${getCurrentUserId()}&workspace_id=default`.
| 8 | `replay_pin` reported `null` on a plain chat turn. **RESOLVED as a harness bug, not a product defect** (2026-09-28): the contract is `metadata.replay_pin`, and the plain-chat turn does report it `pinned`/`durable`. The harness read a non-existent top-level field. | — | **CLOSED** |
| 9 | `tests/core/test_storage_policy_fail_closed.py` is **order-dependent**: **45 passed** alone, but 4 fail (`test_a_complete_scan_can_still_produce_deletion_candidates`, `test_all_three_gates_together_do_delete`, `test_active_pinned_and_evidence_runs_are_never_deletion_candidates`, `test_rewriting_a_classification_cannot_make_a_protected_run_droppable`) when run alongside the continuation/canvas suites in one process. The file never references the changed module, so this is cross-test pollution, not a regression — same class as defect 7. | `backend/tests/core/test_storage_policy_fail_closed.py` | **OPEN.** Not chased: the storage gates were verified green both in isolation and in the policy-only run. |
| 10 | F09's atomic terminal-delivery claim is verified only **within one process**. Two servers on the same world database can interleave check-and-insert freely; a conditional UPDATE is what covers that, and no single-process test can simulate it. Recorded as a limitation, not a gap in the claim. | `core/async_turn_continuation.py::_claim_terminal_delivery` | **OPEN, by design limit.** |
| 10 | F09's terminal-delivery claim is arbitrated by a single conditional `UPDATE` decided on `rowcount`, verified with **two real OS processes** on one database (disabled → 2 rows, enabled → 1). It is **not** exactly-once delivery across the database, the WebSocket and the notification service: a process dying between the claim and the broadcast leaves the live bubble missing while the durable row exists. | `core/async_turn_continuation.py::_claim_terminal_delivery` | **OPEN, by design limit**, stated rather than claimed away. |
| 11 | A terminal-delivery claim is a **lease** (`ATOM_TERMINAL_DELIVERY_LEASE_SECONDS`, default 300s). A crashed holder's outcome is recovered only after the lease ages out, so recovery is delayed by up to the lease. A bare flag cannot be reclaimed on sight — that displaced a live in-flight holder and produced 2 terminal messages. | `core/async_turn_continuation.py::_terminal_delivery_lease_seconds` | **OPEN, by design limit.** The lease value is untuned against real delivery latency. |
| 12 | An expired terminal-delivery claim was never retried. `recover_missing_terminal_deliveries()` now scans for terminal continuations with no durable message and re-delivers them through the same claim and fence, repeatably and without the scheduler, never replaying the mutation. It is **not yet wired into a boot or maintenance path** — it must be invoked. | `core/async_turn_continuation.py::recover_missing_terminal_deliveries` | **WIRED BUT NOT OBSERVED.** A recurring task is started from the FastAPI lifespan outside the scheduler gate and cancelled at shutdown, but on a live restart onto this code it did not start and neither it nor the neighbouring startup block logged. The guard preventing it was not located, so the running-system gap is still open. |
| 13 | `TestRecoveryPass` set `ATOM_DELIVERY_LEASE_DISABLED=1`, an env var implemented nowhere; the class failed on a misleading `canvases.tenant_id` error because the lease query against a stub session raised. The flag now exists and **disables only the wall-clock condition, never the fence**, and all 6 tests pass with their assertions intact. | `core/async_turn_continuation.py::_terminal_delivery_lease_seconds` | **CLOSED.** |

---

## 10. Promotion decision — 2026-09-28

> **SUPERSEDED 2026-09-29** by the Promotion section at the end of this file and
> by `lane3/CURRENT_SUPPORT_TABLE.md` (the authoritative final table). The rows
> below are retained as the 2026-09-28 snapshot; several were subsequently
> closed on later exports — F11 → PASS 7/7 and F12 → PASS 8/8 (+F12B browser) on
> `79b2a41032c3`/`64b44f29`, and F09's automatic recovery → PASS 10/10 on
> `80905c7b` (see the reconciliation addendum). Do not quote the verdict
> paragraph below as current.

One table. Verdicts are for the export/configuration named in that row and for no other. A case that did not run on the final export is **not** reported as if it had.

| Case | Verdict | Export / configuration | Evidence |
|---|---|---|---|
| F01 provenance | PASS | P: base `1a953b58934d`, export `f530c509948d947d`, ports :8140/:3140, pin `deepseek/deepseek-v4-pro`; 15/15 launch checks, 16/16 serving modules vs the immutable export | `lane3/CANDIDATE_FREEZE.json` |
| F02a wrong-field | **UNEXPLAINED** | original evidence deleted with its world | `chat_canvas_editor.py:2596-2625` documents the mechanism only |
| F02b missing-target | PASS 9/9 | A: `finish_line`/`run-cfb0605d01ce`, snapshot `fbf…`, api-only, unpinned | `lane3/f02_negative_control/` |
| F02c widening repair | **PENDING** | needs controlled injection | — |
| F03 sync edit | see REV 2 | S: `write_combined`, shim | `FINISH_LINE_ACCOUNTING` §F03 |
| F04 background success | see REV 2 | S, shim | §F04 |
| F05 background failure | **PASS** (controlled shim, 2026-09-28) | shim world, fork proven, outcome=failed after 3 attempts, audit delta 0, honest summary, no success claim | authoritative row in §5 of this file; the earlier C16 artifact `write_combined_c16/c16_controlled_bg-failure.json` (24/24 applicable) is **retained** under its own fingerprint and is not discarded |
| **F06 browser edit** | **PASS** (pinned) | **P**, export `f530c509948d947d`, :8140/:3140, `deepseek/v4-pro`; 4 runs, each 11/11; 1 update row, operation-linked audit, survives reload | `lane3/FINISH_LINE_CURRENT_STATUS.md` §F06 |
| **F07 second edit + decline** | **PASS** (pinned) | P, same fingerprint; `Net 30`→`Net 45` 11/11, audit `e8f4e709…`; decline `explicit_no_apply` 6/6 | §F07 |
| F08 completion recovery | PARTIAL | S, shim | 3 named gaps (§F08) |
| **F09 superseded delivery** | **NOT PROMPTED — automatic recovery unobserved** | code+boundary verified: `test_f09_supersede_terminal_delivery.py` 14, `test_f09_two_process_delivery.py` 2 (disabled→2 rows, enabled→1), `test_f09_recovery_gap.py` 4, `TestRecoveryPass` 6; fence+persist one transaction; lease + fencing token; recurring task verified starting with `ENABLE_SCHEDULER=false` on export `7c0d299d2575…` | live proof **blocked**: the public turn applied the edit **synchronously**, so no continuation forked and the claim barrier never parked (`background_started: None`, plan AUTHORIZED `wants_edit=True ops=1`) |
| **F10 keyed retry** | **PASS** | A: replay identical `execution_id`, 409 on changed payload, restart survival 6/6 on the same run dir; contract is `metadata.replay_pin` | `lane3/f10_keyed_retry/` |
| F11 effect-before-kill | PARTIAL | S, shim | mutation survives restart, audit stable; missing pre-kill proof |
| F12 read workflows | **NOT EXERCISED** | — | only canvas fields vs audit were read |

**Verdict (2026-09-28 snapshot — SUPERSEDED, see the banner above):** editing was NOT promoted as of this table. F06/F07 stood on a pinned browser candidate whose world and export differed from every candidate built since; F12 was never exercised; F02a is unexplained; F09's automatic recovery was unobserved. All of those except F02a were subsequently closed on the final candidate; F02a remains UNEXPLAINED and F02c remains PENDING.

**Preview:** the preserved read preview on :3102 remains the only browser preview whose world still exists; the `write_verify_0928`/`f09rec`/`f09crash` worlds are API-only and one of them has no restorable world. Do not present :3102 as restartable.

**Explicit exclusions:** cross-host execution; streaming as a supported capability; any ranking or connector claim; the shim world's results as evidence about a real planner; and F06/F07's pinned evidence as evidence about any export other than `f530c509948d947d`.

## Promotion (2026-09-29): **PROMOTE** on candidate `79b2a41032c3` / export `64b44f29`, with two disclosed conditions -- editing only under the disclosed pin (the unpinned default declines truthfully with zero mutation), and the canvas page loading Monaco from a public CDN (0 foreign backend requests).

### Closeout reconciliation (2026-09-29, auditor) — fingerprints, notifications, preview

**1. Exact fingerprint relationship.** Three export identities are in play and
are NOT interchangeable:

| Identity | Export sha256(16) | Source | Carries |
|---|---|---|---|
| Candidate P (2026-09-28 browser F06/F07) | `f530c509948d947d` | base `1a953b58934d` dirty, world `write_verify_0928`, ports :8140/:3140 | the original 4-run browser edit evidence (retained, not merged) |
| F09 recovery evidence (2026-09-28 23:03) | `80905c7bf1788d2b` | world `f09_delivery` snapshot of the DIRTY tree at ~21:39 (base `79b2a41032c3`) | the 10/10 claim-boundary recovery run `run-e1b198fd3421` |
| **Promotion candidate** | **`64b44f297617b050`** | **`git archive 79b2a41032c3` (clean commit)**, worlds `cand_79b2a4103` / `cand_79b2a4103_preview` | F11 7/7, F12 8/8 API, F12B 8/8 browser, F06B browser edit (functional checks pass; strict origin-isolation check failed on the CDN load — disclosed) + unpinned negative control |

`80905c7b` vs `64b44f29`: 1,146 backend product files compared, **5 differ** —
`core/acceptance_barrier.py`, `core/async_turn_continuation.py`,
`core/execution_ownership.py`, `core/execution_recovery.py`,
`core/models.py` — exactly the recovery/ownership path (the working tree
carries the uncommitted variants; the promotion export carries the committed
ones). The other 11 fingerprint modules are byte-identical. An earlier
"candidate family" reading is withdrawn: the exports are genuinely different
code.

**Consequence, measured rather than argued:** the five-fact recovery scenario
was rerun on `64b44f29` (world `cand_79b2a4103`, run `run-119c838071a8`,
results `f09_auto_recovery_0928/result.export-64b44f29.json`) and ended
**INVALID at the prerequisite gate, no kill performed**: the turn never parked
at `continuation_after_claim` because the COMMITTED
`acceptance_barrier.py` defines only `continuation_after_effect` and
`chat_turn_after_claim` — **the claim-stage test seam exists only in the
uncommitted working tree**. The recovery MECHANISM itself
(`AsyncDeliveryLease`, `recover_missing_terminal_deliveries`, recurring task)
IS in the committed code (imports at `async_turn_continuation.py:541ff`; the
run's schema sync auto-created `async_delivery_leases`). So the 10/10 recovery
pass is export-bound to `80905c7b` as SUPPORTING evidence for the promotion:
mechanism present on `64b44f29`, crash-before-delivery seam absent. To bind
the five-fact case to the promotion export, the working tree's seam
(`acceptance_barrier.py` +8 lines and the `async_turn_continuation.py`
rewrite) must first be committed and a new export built — a commit decision
outside this closeout. Crash recovery ON the promotion export remains covered
by F11 7/7 at the after-effect boundary.

**2. Duplicate-notification observation: RESOLVED, no defect.** The two
same-second "could not finish" notifications at 2026-09-29 01:29:42 UTC in
`run-2316226346e7` belong to **two different continuations**:
`99bdcc3c…` (session `f09-unrel-ddf553f2`, phase 2c's failed Z edit) and
`cc07cd76…` (session `f09-unrel-other-aac74b`, the unrelated kappa turn,
which also forked because the controlled shim serves a `CanvasEditPlan` for
EVERY tool request — a harness artifact, not production routing). Each
continuation has exactly one truthful notification and one terminal row. The
earlier same-continuation reading is withdrawn. One terminal database row
plus one notification per continuation is the observed steady state.

**3. Scoped preview decision (published).** The promotion preview is LIVE and
verified on 2026-09-29: backend pid 40833 on :8072, frontend on :3160 (world
`cand_79b2a4103_preview`, run `run-098f9b3f86fd`, started 2026-09-28 23:32 by
the promotion stream), health identity `git_commit 79b2a41032c3`, database
inside the world run dir, `GET /login` 200, and the served bytes of six key
modules (`async_turn_continuation`, `execution_recovery`,
`execution_ownership`, `acceptance_barrier`, `chat_orchestrator`,
`main_api_app`) are byte-identical to the `64b44f29` archive manifest.
Advertised flows, exactly as evidenced: login + general chat and the six read
workflows incl. the named-file price lookup (F12B, real browser, 8/8);
canvas edit under the disclosed `deepseek/deepseek-v4-pro` pin (F06B:
functional edit checks passed, the strict origin-isolation check failed on
the disclosed Monaco-CDN load) and a truthful
zero-mutation decline on the unpinned default. NOT advertised: crash
recovery at the claim boundary (supporting evidence on `80905c7b` only, seam
absent on this export — F11 7/7 after-effect is the export-bound crash
evidence), streaming, cross-host, ranking/connectors. The preserved :3102
preview stays untouched and non-restartable; :8140/:3140 remain candidate P's
stack, retained for the original F06/F07 evidence.

**4. Deliberately preserved, unchanged.** F02a remains UNEXPLAINED (evidence
lost with its world; not reconstructed). F02c (widening-repair control)
remains PENDING — needs controlled plan injection; not silently dropped. The
`F09A_stale_holder_fenced_out` scenario's failed `A_parked_holding_claim`
check (writer's run, 21:31, run-2316226346e7) stands UNREPEATED under its own
scenario — phases 2b/2c were not re-run in the closeout and no delivery-dup
claim is extended to them.
