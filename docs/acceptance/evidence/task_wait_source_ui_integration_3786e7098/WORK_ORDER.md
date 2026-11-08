# Integrated root work order — source-answer and Goal utility UI episodes

**Prepared, not executed.** Root owns review, both single episodes, normal UI
acceptance, PR/CI and merge. Prepared source: `3786e7098fa04dc26d8ba78c3847b5327ec215bd`. Pass the actual frozen
SHA you check out as `--expect-source-sha`; do not assume it is this commit.

## 1. Frozen source and branch

- Branch: `codex/task-wait-source-ui-integration-20261107`
- Reused dependencies: `backend/venv314` and
  `frontend-nextjs/node_modules` symlinks; never install/download.
- Canonical worlds symlink: `backend/data/acceptance_worlds` as verified by
  `core.world_storage_guard.preflight()`.
- Fixtures: `docs/architecture/orchestration_migration/acceptance/fixtures`
  with the verified 55-entry `SHA256SUMS`.
- No `ATOM_WORLD_STORAGE_BYPASS`; no world deletion/recreation; no dirty user
  repo pull/reset.

## 2. Preflight (safe; run before either episode)

```bash
SCRATCH=$(mktemp -d /private/tmp/atom-integrated-preflight-XXXXXX)
mkdir -p "$SCRATCH/data" "$SCRATCH/office"
cd <frozen-worktree>
EXPECTED=$(git rev-parse HEAD)

TESTING=1 SECRET_KEY=<synthetic> \
DATABASE_URL=sqlite:///$SCRATCH/atom.db \
ATOM_DATA_DIR=$SCRATCH/data ATOM_OFFICE_DIR=$SCRATCH/office \
backend/venv314/bin/python scripts/acceptance/browser_agent_source_answer.py \
  --preflight --out "$SCRATCH/source" --expect-source-sha "$EXPECTED"

TESTING=1 SECRET_KEY=<synthetic> \
DATABASE_URL=sqlite:///$SCRATCH/atom.db \
ATOM_DATA_DIR=$SCRATCH/data ATOM_OFFICE_DIR=$SCRATCH/office \
backend/venv314/bin/python scripts/acceptance/browser_goal_utility_ui.py \
  --preflight --out "$SCRATCH/goal" --expect-source-sha "$EXPECTED" \
  --world goal_utility_ui_${EXPECTED:0:10}
```

Both reports must show `ok=true` and all of: clean tracked HEAD, per-file Git
source proof, launcher paths, 55/55 fixtures, writable output parent, usable
worlds root, existing deps, and a fresh world path that was **not created**.
Any failure exits 2 before a world write.

## 3. One ordinary source-answer UI episode

Use the detailed README/work order in
`docs/acceptance/TASK_WAIT_SOURCE_UI_EPISODE_WORK_ORDER_2026_11_07.md` and the
integrated driver. Fresh world, free loopback ports, scratch output, no prior
world reuse:

```bash
WORLD=browser_source_${EXPECTED:0:10}_$(date +%H%M%S)
OUT=/private/tmp/atom-source-ui-evidence-$WORLD
backend/venv314/bin/python scripts/acceptance/browser_agent_source_answer.py \
  --execute --world "$WORLD" --out "$OUT" --expect-source-sha "$EXPECTED" \
  --backend-port <free> --frontend-port <free> --shim-port <free> \
  --provision-admin-password   # or --admin-password-file <0600>
```

The episode must use the normal login/onboarding, normal Agents Run dialog, the
ordinary Assignments upload, and the same job/wait answer. Upload alone stays
inert; a real backend+frontend restart preserves the same job/execution/wait;
the source-only answer resumes the same execution, `tasks.create` is
`oracle_verified`, and exactly one BoardTask exists. The controlled loopback
responses are **SIMULATED MODEL DECISIONS / CONTROLLED TRANSPORT**, not
served-model quality or live-provider evidence.

## 4. One ordinary Goal utility UI episode

Use `docs/acceptance/GOAL_UTILITY_UI_EPISODE_WORK_ORDER_20261107.md` and the
Goal driver. Fresh `goal_utility_ui_` world, separate output, no reuse of the
source-answer world:

```bash
WORLD=goal_utility_ui_${EXPECTED:0:10}_$(date +%H%M%S)
OUT=/private/tmp/atom-goal-utility-ui-evidence-$WORLD
backend/venv314/bin/python scripts/acceptance/browser_goal_utility_ui.py \
  --execute --world "$WORLD" --out "$OUT" --expect-source-sha "$EXPECTED" \
  --backend-port <free> --frontend-port <free> \
  --provision-admin-password   # or --admin-password-file <0600>
```

The synthetic analytics history is explicitly labelled and seeded only through
the existing GoalRunService path. The target is set/cleared only through the
normal supervisor UI/public API; the fixture never writes a target or winner.
The lower-role member uses the real login form and must be read-only. Goal
status/progress must be unchanged by utility set/clear. Both packets remain
separate.

## 5. Merge boundary

Only main `8ded00232`, reviewed Generic `2ef5c120c`, source/executor
`bd209add6` and prepared UI `b493abb30` are integrated here. Do **not** merge
the separate export or radio branches (PR756/757) or touch the Goal CI
synchronization worker as part of this packet.

## 6. Abort and evidence

Preserve the fresh world, screenshots, `scenario.json`, `durable.json`,
`source.json`, `stack.json` and logs on any failure. Abort before/at launch on a
dirty or mismatched source, missing launcher/fixture/deps/output, an existing
world, storage-guard refusal, live-origin request, upload settling the wait,
missing `oracle_verified`, or any HTTP-200-only success claim. Never fabricate
a UI/API/DB result, inject a token/cookie, hand-create a world or bypass the
guard. Root independently accepts or rejects.
