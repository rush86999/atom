# Lane 3 — live inventory, fingerprints and support matrix

Measured 2026-09-27 09:57–10:30 EDT by the Lane 3 agent. Every claim here was read
from a live launch descriptor, a `/api/health` identity block, or `lsof` — not from
a narrative file. Historical artifacts are marked as historical and are not counted
toward any readiness claim.

Repo HEAD throughout: `a8bc48dc1` ("wip(preview): sweep in a second agent's settled
preview work at the user's request"). Working tree is dirty; fingerprints below are
`source_id` values of the form `<commit>-dirty.<digest>`.

## 1. Live processes

| Role | Port | PID | World | Verdict |
|---|---|---|---|---|
| User's own stack — **DO NOT TOUCH** | :8001 / :3000 | 76942 / 66579 | live dev | preserved, never restarted or modified |
| Measured preview — **PRESERVE** | :8051 / :3101 | 97410 / 97424 | `preview_v1` | healthy, `verify` 9/9 |
| Candidate (unpromoted) | :8071 (API only) | 11007 | `candidate_fix1` | `verify` **7/9** — both failures are frontend |
| Verification app (other stream) | :8004 | 71383 | `r8verify` | not this lane's |
| Other preview stream | :3090 | 9894 | `/private/tmp/preview_frontend` | not this lane's |

No maintenance interlock is held. `core.world_storage_guard check` passes; worlds root
is a real local directory (`layout: "local"`), so the portable-drive relocation is
**staged, not completed**.

## 2. The two worlds that matter

### Measured preview — `preview_v1` (PRESERVE)

| Field | Value |
|---|---|
| Backend / frontend | :8051 / :3101 |
| Run dir | `runs/run-75c6ae75fb08` |
| Open DB (from `lsof`) | `…/preview_v1/runs/run-75c6ae75fb08/data/atom.db` (+ `-wal`, `-shm`) |
| `source_id` | `a8bc48dc13e5-dirty.57b79514a80f` |
| `git_commit` / `revision` | `a8bc48dc1` / `a8bc48dc13e56c93d54e3a2ba954138e7388e7d5` |
| Effective flags | `ATOM_TASK_LIFECYCLE_ENABLED=1`, `CHAT_FINALIZATION_M1=1`, `CHAT_FINALIZATION_M2=1`, `ATOM_CHAT_STREAMING=1`, `ATOM_SHEET_DATASETS=1` |
| `goal_runs` rows in this run DB | **0** |
| `verify` | 9/9 |

**This preview predates the task-correction fix.** It cannot serve M06 (item
replacement) and must not be promoted as-is. It is the fallback if everything else
fails, so it stays up.

### Candidate — `candidate_fix1` (unpromoted)

| Field | Value |
|---|---|
| Backend | :8071 (no frontend) |
| Run dir | `runs/run-7325767729a0` |
| Open DB | `…/candidate_fix1/runs/run-7325767729a0/data/atom.db` — **matches the DB the 4/4 result names** |
| `source_id` | `a8bc48dc13e5-dirty.58293b7b2484` |
| `goal_runs` | 4 rows, one per acceptance conversation |
| `verify` | **7/9** |
| Task-correction acceptance | **4/4 PASS**, generated `2026-09-27T10:10:30-0400` |

## 3. `verify` 7/9 — both failures are the same root cause

```
PASS  backend process alive                                    11007
PASS  health identity pid matches launch                        11007 vs 11007
PASS  health identity cwd is this world                         …/candidate_fix1/backend_root
PASS  process has our run db OPEN                               run-7325767729a0/data/atom.db{-wal,-shm}
PASS  process is NOT holding the live dev db                    ✓
FAIL  frontend answers                                          ConnectError [Errno 61]
FAIL  frontend compiled API origin is THIS backend             no chunk referenced :8071
                                                              (scanned 27 chunks; other loopback
                                                               origin seen: http://localhost:8051)
PASS  effective lifecycle flag is on                            1
PASS  real model credentials were forwarded                     names only, no values
```

**The second failure is the serious one and it is a cross-world contamination, not a
missing server.** The candidate has no frontend of its own, so `verify` scans the
*shared* farm at `frontend-nextjs/.preview-instance`, whose single `distDir`
(`.next-preview`) was compiled for `:8051`. The chunks physically reference the
**preserved preview's backend**. If a browser were pointed at a candidate frontend
today it would silently talk to the preview's world.

Root cause is structural: there is exactly one farm (`preview_stack.py:73`,
`PREVIEW_FE = FRONTEND / ".preview-instance"`) with exactly one `distDir`, and Next 16
takes an exclusive lock at `<distDir>/dev/lock`. Two backends coexist; two frontends
cannot. The candidate therefore needs **a second farm with its own distDir** before
any browser claim is possible. That is the first thing Lane 3 must build.

## 4. The 4/4 result is real and correctly bound — but not self-attaching

`docs/…/acceptance/task_correction_results.json` reports 4/4. I verified it
independently rather than trusting the artifact:

- The `db` it names is `…/candidate_fix1/runs/run-7325767729a0/data/atom.db`.
- The live :8071 server's `/api/health` identity names **that same run dir** and
  `lsof` shows it open. So the artifact is graded against the database the server was
  actually using — not a stale export.
- All four `tc-*` conversations are present in that DB with real rows:
  `tc-replace-1790518183` (2 user / 2 assistant, 14:09:49→14:09:54 UTC),
  `-fmt-` (3/3), `-research-` (3/3), `-reload-` (2/2), ending 14:10:30 UTC.
- The durable revision is genuinely correct, read straight from `goal_runs`:
  `parameters.task_lifecycle.task_revision.entities` =
  `No. 381, U-38, No. 622, TK Manual Flanger, SLE24-16, TK 1624, TK Multi Wheel Gang Slitter, GSL48-16`
  — **U-22 removed, U-38 present, order preserved**.
- The `decision_log` for the replacement turn shows the correct sequence:
  `task_created(1) → task_revision(2) observed items differ → task_revision(3) observed retrieval evidence → delivery → task_revision(4) "user edited the requested items: replace -['U-22'] +['U-38']" → task_revision(5) → task_revision(6) observed retrieval evidence → delivery`.

**The gap:** the artifact records `base`, `db` and `generated_at` but **no
`source_id`/fingerprint**. A reader cannot tell from the file alone which code produced
4/4. I fixed exactly this in `restart_durability.py` (identity before/after is now
recorded); the same fix is owed in `task_correction_acceptance.py`, which is Lane 1's
file. Sent as proposal P1 in `TASK_CORRECTION_RUNNER_PROPOSALS.md`.

**Also note:** 9 turns completed in ~41 s (1–4 s per turn). That is the deterministic
`sheet_datasets` path, not model latency, and the answers carry real retrieved content
from the saved copy, so the run is not a stub. It should still be reproduced on the
final frozen candidate before promotion.

## 5. Artifacts that describe worlds which no longer exist

These are the reconciliation traps the resumed-agent review warned about. They are
git-tracked and will be read by someone as current.

| Artifact | World / ports it describes | Reality |
|---|---|---|
| `acceptance/preview/preview_state.json` | `consolidated_preview`, :8092/:3092 | **dead** — both ports closed |
| `acceptance/preview/preview_verification.json` | `search_preview`, :8091/:3091 | **dead** — both ports closed; carries open blocker `PREVIEW-01` |
| `acceptance/restart_durability.json` | `preview_v1` run `run-560c6ce8afe9` | historical; **no `source_id` recorded**, so it cannot be attached to any fingerprint |
| `acceptance/preview_browser_results.json` | `preview_v1` :8051/:3101 | historical; **no `source_id`**; `login.attempted: false` (M01–M08 ran on a seeded session token) |
| `backend/data/acceptance_worlds/preview_v1/live_acceptance_result.json` | `preview_v1` run `run-65fdffe7d20c` | historical; older than the currently live preview process |
| `backend/scripts/orchestration_acceptance/live_integration_results/*.json` (31) | `gate_world` :8025, `m1_world` | historical; only 3 of 31 carry a launch descriptor; **all 31 are `all_pass: false`** |

`preview_state.json` and `preview_verification.json` also carry `boundary_verified:
false` and a withdrawn streaming claim — the socket carries status transitions only, and
zero `chat_token` frames have ever been observed. **Streaming must not be advertised.**

## 6. Dominant fingerprints in the existing result corpus

Do not pool these. Per closeout plan §9.7 the final matrix runs on one frozen export.

| Fingerprint | Result files | Note |
|---|---|---|
| `39d6532d5af3` / archive `4d86bd5ed9e1` | 108 of 163 in `acceptance/results/` | dominant **and oldest**; predates identity evidence and the transport fix |
| `d5d670596078` + 5 different dirty digests | 6 | five incompatible working-tree exports of one commit |
| `813b24c3b518` | 10 | |
| `52e6193a7734` | 10 | pre-transport-fix: `keyed_retry` 500s |
| `2cdc2f98b7e0-dirty.*` | all of `live_integration_results` that has any identity | |
| `e61126cfebc4-dirty.edf632772b72` | `preview_v1/live_acceptance_result.json` | |
| `a3169e895fe0` (search layer 2) | `acceptance/search/` | real invocation counts exist **only here** |
| **`a8bc48dc13e5-dirty.58293b7b2484`** | **the 4/4 correction result only** | the current candidate |

**Nothing in the corpus was measured on the final candidate.** The whole C00–C26 matrix
has to be re-run on one frozen export that includes Lane 1's staged fix and Lane 2's
frontend work.

## 7. Ownership observed at 10:28 EDT

| Lane / writer | Status | Files |
|---|---|---|
| Lane 1 (task correction) | **settled** — all five files staged at 10:13:20, quiet since | `chat_tool_planner.py`, `chat_orchestrator.py`, `task_correction_acceptance.py`, `test_reply_leg_name_safety.py`, `test_workbook_structured_delivery.py` (+ untracked `test_task_correction_routing.py`). Staged, **not committed**. |
| Lane 2 (frontend streaming) | **active** — appeared during this session | new untracked `hooks/chat/__tests__/fixtures/`, `useChatInterface.turn-binding.test.ts`, `useWebSocket.stale-callbacks.test.ts` |
| Storage-guard writer | **active** | `world_storage_guard.py`, `run_isolated.py`, `preview_stack.py`, `preview_server.py`, `preview_launch.py`, `worlds_delete_audit.py`, `verify_world_migration.py`, `drive_status.sh`, `AGENTS.md` (new world-storage section), `WORLDS_RELOCATION_RUNBOOK.md` |
| Lane 3 (this) | active | `restart_durability.py` (one scoped fix), `acceptance/lane3/**` |

Lane 1's work is **staged but uncommitted**, so HEAD is still `a8bc48dc1` and any
fingerprint computed from `git rev-parse` understates the source actually running. The
launchers' `source_id` correctly encode the dirty digest, which is why the two live
worlds have different `source_id` values at the same commit.

## 8. Security finding: two secrets are committed in a tracked file

`docs/…/acceptance/preview/preview_state.json` is **git-tracked** and contains:

- line 36 `preview_secret_key` — 64-char urlsafe-base64, a `secrets.token_urlsafe(48)`
  JWT signing key, committed in `a8bc48dc1` and earlier in `9e46185df`.
- line 60 `credential_isolation.sanitize.world_unique` — a 44-char Fernet key, written
  verbatim by `credential_isolation.py:121`.

Both belong to **dead** worlds (`:8092/:3092` and `:8091/:3091`, both closed).
`git log --all -S<value>` shows each value appears in that one path and nowhere else, so
containment is complete. Because the values are per-world throwaways and both worlds are
stopped, **rotation is a no-op**; the correct remediation is a forward redacting commit
plus `.gitignore`, not a history rewrite (which this lane forbids). Full analysis and
remediation ordering: `CREDENTIAL_SCRUBBING_REVIEW.md`.
