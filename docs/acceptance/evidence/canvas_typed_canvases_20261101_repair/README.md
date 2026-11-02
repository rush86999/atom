# Canvas successor — consolidated verifier repair

Status: **submitted for independent verification; not self-accepted.** This
repairs the three findings in `CANVAS_REPAIR_BATCH.md` for the typed-canvas
successor. Connected-batch acceptance remains bound to `6431bcb78` and is not
relabelled here.

## Executed source

| Item | Value |
|---|---|
| Worktree | `/private/tmp/atom-canvas-successor` |
| Branch | `codex/brennan-canvas-successor-20261101` |
| Previous reviewed source | `5ebe361aa13fadf28bcee9808fd1ddb7c80c0227` |
| Product repair source | `1d7f96f1e` |
| Executed clean tip | `e7c4641701f3` |
| Tree at execution | clean (`dirty=false`) |
| Backend identity | pid `79812`, source `e7c4641701f3`, instance `e7c4641701f3.79812.1793595326` |
| World | isolated local world `canvas-successor-20261101-repair-final` |
| Frontend | production build on `127.0.0.1:3133`, build id `3GFWeWvtCydaBRfYM0_RY` |
| Backend | `127.0.0.1:8092`, real routes/executor/sqlite |

`git diff 1d7f96f1e..e7c464170 -- backend frontend-nextjs` is empty; the later
tip contains the acceptance runner and evidence/docs only. The backend health
identity, frontend health/build identity and world marker are captured in the
JSON files in this directory.

## Repairs

### 1. Old open clarifications cannot edit a replacement dataset

Every question captures its authoritative state revision, manifest/policy
revision, source identity/version/hash, subject value, complete row digest and
field mapping/type/unit binding. The answer path reloads the canvas, requires
all captured bindings to still match, and refuses before any edit when the
source, row subject, field mapping, manifest or revision changed. The refusal is
recorded as a refused attempt; a fresh derive opens a new question for the
replacement subject. The edit, answered derive and resolution commit in one
transaction; a failed derive rolls the edit back and leaves the question open
with the refused attempt.

The browser bundle includes a public/UI-page control: question opened for item
`A`, source replaced with item `B`, old answer submitted with the new revision
-> `409 stale_clarification`, no edit to `B`, new question for `B`, then the
new answer completes at `2000.00`.

### 2. Derived arithmetic enforces dimensions and currencies

Manifest save and derive consumption validate the expression contract:

- `+`/`-` require the same unit or the same ISO currency; `USD + CAD` and
  `currency + hours` refuse.
- A USD field whose expression yields CAD refuses; a decimal field cannot hide
  a currency (no relabelling).
- Multiplication supports the documented bounded rate contract:
  quantity/unit × currency/per-unit (quote `quantity * unit_price`, service
  `hours * rate`). Currency × currency, unit × unit and implicit conversion
  refuse.
- Division is limited to a scalar divisor or a same-dimension ratio; the
  result must match the declared field dimension.
- Unknown/ambiguous dependencies refuse before any total or receipt.

The independent verifier probes `/private/tmp/test_verifier_canvas_boundaries.py`
now pass; the probe and its log are included as `verifier-probe.py` and
`verifier-probes.log`.

### 3. Manifest-listed evidence is tracked

`frontend-build-id.txt`, `run.log`, test logs and the verifier probe/log are
force-added despite the repository's `*.txt`/`*.log` ignore rules. The
historical `canvas_typed_canvases_20261101/MANIFEST.json` no longer lists the
two artifacts that were untracked in that submission; the old screenshots and
results remain under their actual `5ebe361aa` source.

## Three canvases through the ordinary UI

| Canvas | Independent total |
|---|---|
| Industrial quote (table, quantity × unit price) | `350.00 USD` |
| Service proposal (form, hours × rate) | `630.00 CAD` |
| Non-sales exception queue (count + amount by status) | `170.00 USD`, 3 exceptions |

Browser result: **16/16 checks passed**, no page errors. See `result.json`,
`run.log` and the four screenshots.

## Tests

| Scope | Result |
|---|---|
| `tests/test_canvas_typed_fields.py` | **21 passed** |
| Canvas capability/assessment/routes/crud/fork focused suite | **113 passed** |
| Independent verifier probes | **2 passed** |
| Frontend canvas capability suites | **6 passed** |
| Browser three-canvas + source-replacement journey | **16/16 checks** |

Logs: `typed-tests.log`, `backend-tests.log`, `verifier-probes.log`,
`frontend-tests.log`, `run.log`.

## Changed files vs reviewed source

```text
backend/core/canvas_capability_service.py
backend/tests/test_canvas_typed_fields.py
scripts/acceptance/canvas_typed_canvases_local.py
```

## Exclusions

- Isolated local world and production frontend build; not hosted deployment or
  public publication.
- No live external provider call, refresh, write or send.
- Canvas action declarations are validated against registered actions but are
  not executed from the canvas; connected effects remain assignment-owned.
- The derive clarification is canvas-state and reuses the edit/derive
  operations; assignment-task resume is not claimed in this batch.
- The expression grammar is `+ - * /` with the documented bounded rate
  contract; it is not a general unit algebra or currency converter.
- No independent unfamiliar-user utility study was run.
- No universal mini-app/runtime claim follows from three supported canvases.
