# GOAL-02 utility surface — prepared ordinary-UI episode work order

**Status:** prepared harness only. Root owns review, the single UI episode,
normal UI acceptance, PR/CI and merge. This slice does not launch a world,
browser, backend, frontend, app model or provider.

**Branch/worktree:** `codex/goal-utility-ui-prep-20261107` in
`/private/tmp/atom-goal-utility-surface-20261107`.

**Prepared source baseline:** `dc92728d6e1302e8718c9435c08c119972e6fca8`
(the frozen GOAL utility PR head). Root must re-resolve and pass the actual
frozen integrated source SHA with `--expect-source-sha`; do not assume this
commit remains the candidate.

**Driver:** `scripts/acceptance/browser_goal_utility_ui.py`

**Goal PR / production rule:** do not modify the goal PR branch, production
API/UI/runtime, existing tests or the source-answer driver in the other
worktree. This work order is a separate packet and must not be merged into the
goal PR as an acceptance claim.

---

## 1. User outcome

On the **enabled** Activity → Goal Run detail surface:

1. A supervisor signs in through the ordinary login form, navigates normally to
   Activity and opens one goal run.
2. The existing utility editor can set the existing supported target
   (`human_interventions` / `steps_executed` / `replan_count`, direction
   `minimize` / `maximize`, source `goal_run`).
3. Two eligible completed histories rank deterministically; the lower
   intervention count wins under `minimize`.
4. One failed candidate and one unknown-metric candidate are visibly withheld
   with truthful reasons; neither wins or gets a fabricated rank.
5. The target and ranking survive page reload and a fresh public API read.
6. A member in the same workspace sees the same target/ranking read-only and
   cannot mutate it through the UI or public API.
7. The supervisor clears the target through the same UI; the no-target state
   returns, ranking disappears, and the durable target is gone.
8. The goal's status/progress are unchanged by utility set/clear. Utility is an
   advisory optimization signal only; it never completes or advances the goal.
9. Each actual set/clear mutation returns one existing operation receipt
   (`verification=verified`, one operation/audit identity).

## 2. Explicit non-claims

- No served model, provider, inference, model judgment or model-quality claim.
- The seeded GoalRun rows are **not** completed agent work and must never be
  described as such.
- No source upload/answer, Generic model call, download, live connector,
  account, credential, send, spend, install, deploy, PostgreSQL, multi-worker or
  soak qualification.
- No full TASK-WAIT-01 or whole-app acceptance.
- No broader admin acceptance. The member fixture is a disclosed lower-role
  fixture, not a production authority grant.
- No token/cookie seeding. Both roles use the real login form.

## 3. Controlled analytics fixture (explicit disclosure)

The episode seeds **history**, never a target or winner:

| Fixture row | Status | Fixed metrics | Expected ranking |
|---|---|---|---|
| `eligible-low` | achieved | interventions 2, steps 5, replans 1 | eligible, rank 1 |
| `eligible-high` | achieved | interventions 5, steps 8, replans 2 | eligible, rank 2 |
| `failed-candidate` | failed | interventions 0, steps 4, replans 1 | withheld: `not_completed` |
| `unknown-candidate` | achieved | interventions -1, steps 6, replans 0 | withheld: `metric_unknown` |

- Rows are created through the existing `GoalRunService.create_run` /
  `activate` / `transition` path with `role="analytics_fixture"`.
- Fixed counters are a fixture input. **No utility target or winner is written
  by the fixture.** The target is set only through the existing public
  supervisor UI/API after the history exists.
- The goal title/description and every run role label this as a controlled
  analytics fixture. It is not real model work.
- The fixture is allowed because this is an analytics/ranking episode, not a
  claim that an agent completed real work.

**Role fixture:** a member user is created in the scratch admin's tenant/
workspace as a disclosed role fixture, with a random in-memory password hashed
through the app's existing password helper. The member then logs in through the
normal form. The password is never written to evidence. This is not a token,
cookie or production role grant; it creates only a lower-privileged member.

## 4. Preconditions

- Prepared frozen capture worktree with:
  - `backend/venv314/bin/python`
  - `frontend-nextjs/node_modules`
  - no `npm install` / `pip install`
- Free `--backend-port` and `--frontend-port`.
- A unique fresh `--world` name beginning `goal_utility_ui_`.
- Admin password source: `--admin-password-file` (0600) or
  `--provision-admin-password` for the scratch world.
- `TESTING=1`, fresh unique `DATABASE_URL`, `ATOM_DATA_DIR`,
  `ATOM_OFFICE_DIR`; synthetic per-run `SECRET_KEY` (driver sets one at
  execute, never evidence).
- Do not set `ATOM_PRODUCT_PROFILE=full` and do not force-enable deferred
  surfaces. The episode verifies the core profile with Activity enabled and
  Tasks/Boards still disabled.
- Do not pass `ATOM_WORLD_STORAGE_BYPASS=1`.

## 5. Preflight (safe; no launch)

Run from the prepared frozen capture worktree:

```bash
SCRATCH=$(mktemp -d /private/tmp/goal-utility-ui-preflight-XXXXXX)
mkdir -p "$SCRATCH/data" "$SCRATCH/office"
TESTING=1 \
DATABASE_URL="sqlite:///$SCRATCH/atom.db" \
ATOM_DATA_DIR="$SCRATCH/data" \
ATOM_OFFICE_DIR="$SCRATCH/office" \
SECRET_KEY="test-synthetic-goal-utility-ui" \
python3 scripts/acceptance/browser_goal_utility_ui.py --preflight \
  --expect-source-sha <frozen-source-sha> \
  --out "$SCRATCH/report"
```

Preflight must prove:

- scratch DB/data/office are outside the live tree;
- HEAD equals `--expect-source-sha`;
- tracked tree is clean;
- **per-file Git source proof** for every file in the driver's `SOURCE_FILES`
  (Git blob/SHA-256 equals the worktree bytes), including the goal routes,
  `GoalService`, `GoalRunService`, `goal_write_service`, utility target,
  personal scope, product profile, Goal Runs page and goal-run API client;
- the controlled analytics fixture ranks exactly two eligible rows, winner
  `eligible-low`, withheld reasons `not_completed` and `metric_unknown`;
- core profile has Activity/Goal Runs enabled, Tasks/Boards not forced;
- the world name has the required prefix and does not already exist;
- backend/frontend ports are free;
- storage guard configuration loads without error.

Preflight must not build a world, launch a server/frontend/browser, create a
GoalRun, set a target, call a model/provider or touch the live DB. The report
lists what was not exercised.

## 6. Root-owned execution (one episode; do not run during preparation)

```bash
python3 scripts/acceptance/browser_goal_utility_ui.py --execute \
  --expect-source-sha <frozen-source-sha> \
  --world goal_utility_ui_<frozen-sha10> \
  --backend-port 8041 --frontend-port 3141 \
  --out <scratch-evidence>/goal_utility_ui_<frozen-sha10> \
  --provision-admin-password   # or --admin-password-file <0600 file>
```

`--execute` must refuse:

- a missing `--expect-source-sha`;
- a dirty tracked tree or per-file Git mismatch;
- a world name without the `goal_utility_ui_` prefix;
- an existing world;
- a core profile without Activity/Goal Runs;
- busy ports or missing prepared deps;
- the live dev DB or any world-storage-guard bypass.

The driver reuses the existing `run_isolated.build_world/launch_server`, the
storage guard, `case5_browser_recovery.start_frontend_copy`, `browser_verify.ui_login`
and the existing `GoalRunService`/`GoalService`; it does not add an engine,
router, store, review lifecycle or model shim.

## 7. Episode assertions

All assertions use visible UI plus public API and read-only durable rows. Where
a UI action is asserted, also verify the corresponding API/DB state; do not
infer success from a heading or a console message.

### 7.1 Supervisor set

- Real login form succeeds; no token/cookie seed.
- `/goal-runs` is reachable through normal navigation; the run link opens
  `/goal-runs/<run_id>`.
- Utility card shows the no-target state and the supervisor editor.
- Selecting the existing metric/direction/description and clicking **Save**
  sends exactly one `PUT /api/goals/<goal_id>/utility`.
- Response has `verification.status=verified`, one `operation_id`, one
  `audit_id`.
- UI shows exactly two eligible ranking rows and one winner badge.
- Withheld text contains `not completed` and `metric unknown`.
- Public `GET /api/goals/<goal_id>/utility` target/winner/eligible IDs match
  the controlled fixture.
- Durable `GoalObjective.metadata_json.utility_target` matches the target.
- Goal status/progress are unchanged from before the set.

### 7.2 Reload / fresh read

- Reload the detail page; the target and two-row ranking persist.
- A fresh API client reads the same target/winner.
- No second PUT occurs on reload.

### 7.3 Member read-only

- Member logs in through the real form in the same workspace.
- Member sees the utility card, target and two-row ranking.
- Member sees the explicit supervisor-only note.
- No Save or Clear control is rendered.
- A direct member `PUT` to the public utility route returns 403; the target is
  unchanged after the refusal.

### 7.4 Supervisor clear

- Click **Clear** once; exactly one `DELETE /api/goals/<goal_id>/utility`.
- Response has a verified operation/audit receipt.
- UI returns to no-target; ranking is absent.
- Public API target is null and ranking is empty.
- Durable target is absent.
- Goal status/progress remain unchanged from before the set and after clear.
- No second set/clear request or duplicate receipt.

### 7.5 Profile and source boundary

- `GET /api/product/profile` reports `profile=core`, Activity enabled, and
  Tasks/Boards still disabled (deferred; not force-enabled).
- The built world marker names the frozen source SHA and the controlled
  analytics fixture.
- Backend export is bound to Git per-file; frontend snapshot files match the
  Git blobs for `lib/goal-run-api.ts` and `pages/goal-runs/[id].tsx`.
- No provider shim/model request is made; no source upload/download runs.

## 8. Evidence packet

The driver writes under `--out`:

- `source.json` — HEAD, expected SHA, per-file Git blobs/SHA-256, tracked
  cleanliness, runtime identity;
- `scenario.json` — every step/check, UI/API/DB readback, receipts, fixture
  labels, world marker, profile, source binding, actual result;
- screenshots: supervisor login, no-target, ranking, reload, member read-only,
  cleared;
- world `GOAL_UTILITY_UI_EPISODE.json` marker;
- backend/frontend logs in the world (root retains them).

Root should also retain command lines and actual exit codes. If any pytest is
run, it must use
`/private/tmp/atom-agent-cli/run_bounded_test_gate.py` with shared serialization,
a fresh unique scratch DB/data/Lance/output, `TESTING=1` and a synthetic
`SECRET_KEY`; bounded profile only for an exact ≤100-control focused selection
with ≥2 GiB free, heavy for a broad selection.

## 9. Failure handling

- Keep the failed world and the scenario JSON; never delete/rebuild a world in
  this driver.
- A failed source proof, dirty tree, existing world or profile mismatch must
  refuse before build/launch.
- A failed UI/API/DB assertion leaves the scratch world and screenshots for
  root diagnosis.
- Do not retry the episode on a changed source without a fresh source SHA,
  fresh world and fresh packet.
- Do not substitute direct DB target/winner injection, a fabricated UI
  response, a seeded auth token/cookie or a public member role escalation to
  make a check pass.

## 10. Root review checklist

- [ ] Harness reviewed before the single episode.
- [ ] Frozen source SHA explicit; per-file Git proof matches the executed
      world/export.
- [ ] Fresh marked world; storage guard honored; live DB untouched.
- [ ] Core profile verified, not force-enabled.
- [ ] Fixture history disclosed in goal title/description/run role; no target or
      winner pre-seeded.
- [ ] Supervisor set/clear through ordinary UI; member read-only; member API
      mutation refused.
- [ ] Two eligible ranks, failed/unknown withheld, reload/fresh read persist.
- [ ] Goal status/progress unchanged; utility advisory only.
- [ ] One verified operation receipt per actual set/clear mutation.
- [ ] No model/provider/live/source-upload/download/install/deploy claim.
- [ ] Packet separate from the Generic source-answer episode; no duplicate
      source-upload/model campaign.
- [ ] Root independently accepts or rejects; driver does not self-accept.

## 11. Relationship to the Generic source-answer episode

Both harnesses may use the same frozen integrated source and the same existing
world-build/startup infrastructure after the source-answer episode is accepted,
to avoid duplicate build/startup work. Their **packets must remain separate**:
this driver still requires its own fresh `goal_utility_ui_` world marker and
does not reuse, mutate or certify the source-answer world, job, HITL row,
source upload, model request or evidence.
