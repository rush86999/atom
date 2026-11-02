# Full-app quote / service / exception batch — evidence bundle

Status: **submitted for independent verification; not self-accepted.**

This bundle consolidates the normal full-app journey, the affected regression
set, the baseline 17-check canvas journey, and the uncertain-effect
reconciliation control on one frozen source. It extends — without modifying —
the earlier `../full_app_quote_journey_20261102/` bundle committed concurrently
by the other agent for the same source.

## Executed source

| Item | Value |
|---|---|
| Worktree | `/private/tmp/atom-full-app` |
| Branch | `codex/brennan-full-app-20261102` |
| Base source | `69a7de28de9a3988696909d858eccefdcb6ce84c` |
| Executed source | `6f697cd9d642940221046353d72937040e61b009` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime identity | `source_id=6f697cd9d642 revision=6f697cd9d642 dirty=False` |
| Packaging HEAD | `609dc4144df05185b9a050dd8acefbd256d1512e` (docs-only evidence from the other agent) |
| Frontend build | `qPTn5x9z4xY8Qfz1O8SRp` |
| World | `backend/data/acceptance_worlds/full-app-quote-20261102` |
| Ports | API `8096`, frontend `3137` |
| Transport | controlled canvas action; no live provider |

The packaging HEAD is a docs-only commit created in the same worktree after
the campaign finished. The served code was `6f697cd9d` with a clean tree; the
runtime identity log is in `runtime-identity.txt`.

## Journey

The real backend and frontend serve the normal application. The journey logs in
through `/login`, creates typed canvases from real CSV bytes, configures
schema-2 fields and derived totals, binds the source, promotes a document
lesson, starts an ordinary assignment from the server receipt, restarts the
real backend and frontend, approves the declared registered canvas action,
downloads the produced DOCX, then runs the service-proposal and
exception-queue variants, a source change, a duplicate continuation and a
cancellation.

`campaign-result.json` records **15/15 checks passed**. `baseline-17.log` and
`baseline-17-result.json` record the pre-existing **17/17** canvas journey on
the same source.

## Effects (measured)

| Effect | Count / identity |
|---|---|
| `canvas.present_markdown` dispatches | **1** (`e33a850a-a213-481c-8cb8-f31059ea2a07`) |
| Duplicate approval | `404`; same remote id before and after |
| Quote document | `88bd8bd2…`, sha256 `e9fc6f13…`, total `350.00` |
| Service document | `c9a1dc7c…`, sha256 `3bc48625…`, total `630.00 CAD` |
| Exception document | `4f10e5fa…`, sha256 `e51ed8ae…`, count `3`, amount `170.00` |
| Reconciliation | one draft; uncertain → reconcile `applied` → completed; still one draft |

All three documents consumed the promoted lesson: `Normal` style is
**Georgia 18 pt**.

## Negative / continuity controls

- The old source receipt is refused after a source change (`409
  stale_revision`); the new receipt totals `450.00`.
- Restarting the real processes preserves the prepared action and does **not**
  dispatch it; approval is still required afterwards.
- A duplicate approval is refused and does not create a second effect.
- Cancellation before approval is terminal.
- A provider timeout *after* a draft landed is classified `uncertain`,
  blocks, reconciles with readback evidence, completes, and leaves exactly one
  draft (`reconciliation-control.log`).

## Reproduction

```bash
# world (reuses the durable DB; no reseed)
WORLD=$PWD/backend/data/acceptance_worlds/full-app-quote-20261102 \
ADMIN_PASSWORD='FullApp-2026!' BACKEND_PORT=8096 FRONTEND_PORT=3137 \
ATOM_FRONTEND_DIR=$PWD/frontend-nextjs PYTHON=<venv>/python \
bash scripts/acceptance/launch_integrated_local_candidate.sh

# 15-check campaign
TESTING=0 BRENNAN_PYTHON=<venv>/python PYTHONPATH=$PWD/backend \
<venv>/python scripts/acceptance/full_app_quote_journey.py \
  --frontend http://127.0.0.1:3137 --api http://127.0.0.1:8096 \
  --password-file $WORLD/canvas-password.txt \
  --agent-id 5ef8be20-1528-42d2-86e0-5c932c4a45e4 \
  --out-dir /private/tmp/full-app-quote-run

# baseline 17-check journey
TESTING=0 PYTHONPATH=$PWD/backend <venv>/python \
scripts/acceptance/canvas_typed_canvases_local.py \
  --frontend http://127.0.0.1:3137 --api http://127.0.0.1:8096 \
  --password-file $WORLD/canvas-password.txt \
  --agent-id 5ef8be20-1528-42d2-86e0-5c932c4a45e4 \
  --out-dir /private/tmp/full-app-baseline-final
```

## Exclusions

- No live provider lookup, refresh, write, send, credential or spend.
- No database reseed; the same durable world was restarted in place.
- No change to the 123-feature denominator, accepted tags/sources or the
  historical 111/123.

## Environment note

Under concurrent agent load this host occasionally renders a canvas page
slowly (one probe measured ~90 s to create/attach, with the renderer briefly
busy). The harness default action timeout is therefore 120 s; the same build
had already passed 16/16 before that slow run and passed 15/15 after, and an
idle-machine probe completed normally. This affected harness timing only, not
the product assertions above.
