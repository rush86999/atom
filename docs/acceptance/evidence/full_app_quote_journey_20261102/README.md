# Normal full-app quote/service/exception journey

Status: **submitted for independent verification; not self-accepted.**

## Executed source

| Item | Value |
|---|---|
| Worktree | `/private/tmp/atom-full-app` |
| Branch | `codex/brennan-full-app-20261102` |
| Executed source | `6f697cd9d` |
| Tree at execution | clean |
| Runtime identity | `source_id=6f697cd9d642 ... dirty=False (0 modified, 0 untracked)` |
| World | `backend/data/acceptance_worlds/full-app-quote-20261102` |
| Ports | API `8096`, frontend `3137` |
| Transport | controlled canvas action; no live provider |

## Journey

The ordinary application is served by the real backend and frontend. The
journey logs in through `/login`, creates typed canvases from real CSV bytes,
configures schema-2 fields and derived totals, binds the source, promotes a
document lesson, starts an ordinary assignment from the server receipt,
restarts the real backend, approves the declared registered canvas action,
downloads the produced DOCX, and continues with service-proposal and exception-
queue variants plus cancellation.

`result.json` records **15/15 checks passed**:

1. promoted document lesson is explicit and source-bound;
2. quote receipt starts an ordinary assignment;
3. real backend restart preserves the prepared action;
4. prepared action survives restart without dispatch;
5. quote assignment completes after action approval;
6. quote document artifact is attached;
7. quote document contains the server total and provenance;
8. quote document consumes the promoted lesson (Georgia 18);
9. declared registered action has readback evidence (`remote_id` present);
10. duplicate continuation does not dispatch the action again;
11. source change produces a new server receipt (450.00);
12. old source receipt is refused after the change (409 `stale_revision`);
13. service proposal completes with a document artifact;
14. exception queue completes with a document artifact;
15. cancelled action assignment is terminal.

The downloaded artifact is `quote-document.bin` (DOCX) and the browser evidence
is `quote-journey.png`.

## Identity-persistence repair

`backend/core/assignment_executor.py` now persists `remote_id` in the applied
operation `execution` record, alongside `provider_ref`, and exposes it in the
assignment API operations. The action step's readback check therefore sees the
actual canvas identity. The duplicate approval returns 404 and leaves the same
remote id, so no second effect is dispatched.

## Tests

| Scope | Result |
|---|---|
| Canvas assignment/typed/capability + assignment executor | **139 passed** |
| Canvas capability frontend suites | **7 passed** |

Logs: `focused-backend.log`, `frontend.log`, `journey.log`.

## Boundaries

- This is a controlled local/browser journey. No live provider lookup, refresh,
  write, send, credential/consent change or spend occurred.
- The journey covers quote, service proposal, exception queue, source change,
  restart, duplicate continuation and cancellation. It does **not** yet cover
  the supplier-invoice-to-Zoho-Books bookkeeping loop.
- It does not close whole-app ORACLE-01 coverage; the mutation-surface
  inventory remains open.
- Historical `111/123`, connected `6431bcb78`, typed-canvas
  `4859b0ce2477`, canvas assignment/teaching `a87882526323` and tags are
  unchanged.
