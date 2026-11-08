# Root next ordinary source-answer episode

**Prepared, not executed.** Use a fresh world and the new frozen SHA; do not
reuse, rebuild or delete the retained `browser_source_0bb931831_root_20261107`
world or its capture.

## Preflight

```bash
SCRATCH=$(mktemp -d /private/tmp/atom-agents-run-preflight-XXXXXX)
mkdir -p "$SCRATCH/data" "$SCRATCH/office"
cd <frozen-worktree>
EXPECTED=$(git rev-parse HEAD)
TESTING=1 SECRET_KEY=<synthetic> \
DATABASE_URL=sqlite:///$SCRATCH/atom.db \
ATOM_DATA_DIR=$SCRATCH/data ATOM_OFFICE_DIR=$SCRATCH/office \
backend/venv314/bin/python scripts/acceptance/browser_agent_source_answer.py \
  --preflight --expect-source-sha "$EXPECTED" --out "$SCRATCH/report"
```

Require `ok=true`, 9/9 source files, 55/55 fixtures, clean tracked HEAD,
usable worlds root, writable output and no world creation.

## Execute (root-owned, one fresh world)

```bash
WORLD=browser_source_${EXPECTED:0:10}_$(date +%H%M%S)
OUT=/private/tmp/root-source-ui-canonical-$WORLD
backend/venv314/bin/python scripts/acceptance/browser_agent_source_answer.py \
  --execute --world "$WORLD" --out "$OUT" --expect-source-sha "$EXPECTED" \
  --backend-port <free> --frontend-port <free> --shim-port <free> \
  --provision-admin-password
```

Expected on the new world:

- exactly one successful `POST /api/agents/<id>/run` with **no 307**;
- one logical run admission, one job, one execution, one operation identity;
- normal login/onboarding, ordinary upload, upload-alone inert, real backend+
  frontend restart with the same wait/correlation/question/source picker;
- one source-only answer, same execution, `tasks.create` with
  `oracle_verified=true`, exactly one task;
- duplicate source answer creates no second task/provider call and no `/advance`;
- final UI/API/DB readback and the retained scenario details record raw paths,
  statuses and the scoped job/execution.

Never set `ATOM_WORLD_STORAGE_BYPASS`; never hand-create/delete a world; no
install/download/model/provider/browser download/live DB. The Goal utility
driver and source remain unchanged; its episode is separate if root runs it.
