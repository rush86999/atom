# Practical assignment recovery — browser journey

This bundle records the missing browser-level rerun of the five practical
assignment boundaries. User actions went through the real Assignments page;
the backend was the standalone acceptance server (real routes + real executor,
scratch SQLite world, controlled local outbox). No provider was contacted and
no real send occurred.

## Result

`browser-recovery.json`: **5/5 checks passed**, 0 failed. Controlled outbox
effects: **0**.

| Scenario | Browser actions | Assertion |
|---|---|---|
| Wait → restart → resume | Start a calculation assignment that waits on an external fact; stop the backend process; start a new process against the same world; reload the page; submit the correlated response; watch the artifact render | Backend PID changed (recorded in the JSON), the assignment was still `waiting` after the restart, and it completed with the calculated result `80` |
| Changed source revision | Start a mapped aggregate; change the dataset's active `content_hash`; click **Correct mapping** and apply a replacement column | The browser showed `Requested version 'aaaa…' is not the active version 'bbbb…'`; the mapping stayed `Total → Total`; the completed `85.00` result survived |
| Ambiguous mapping identity | Start a mapped aggregate with two confirmed mappings for `Total`; call the correction route without a sheet/version; then select the correctable card and apply `Unit Price` | The ambiguous correction was refused with `more than one confirmed mapping exists`; the page showed two candidates, one correctable and one disabled; choosing the identified mapping resolved to `Total → Unit Price` |
| Cancellation | Start a waiting assignment; click **Cancel**; reload; submit a late correlated response | The cancelled status survived reload; the late response returned the cancelled assignment and produced no effect |
| Duplicate resume | Open the same waiting assignment in two pages; submit the same correlated response from both at once | One calculation step applied, one result, `prior_result_count=0`; no second dispatch and no outbox effect |

Screenshots are in `screenshots/` and are named in the JSON check details.

## Reproduce

```bash
# backend acceptance server (fresh world)
export WORLD=/absolute/scratch/assignment-recovery-browser
export PYTHONPATH=<repo>:<repo>/backend:<pyarrow-overlay>
ATOM_ASSIGNMENT_BROWSER_WORLD="$WORLD" \
ATOM_ASSIGNMENT_BROWSER_WORLD_RESET=1 \
ATOM_ASSIGNMENT_BROWSER_PORT=8090 \
ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT=1 \
  <python> backend/scripts/assignment_browser_acceptance_server.py

# frontend (normal product page; the API points at the acceptance server)
cd frontend-nextjs
NEXT_PUBLIC_API_URL=http://127.0.0.1:8090 \
NEXT_PUBLIC_ALLOW_LOOPBACK=1 \
NEXT_PUBLIC_ASSIGNMENT_TRANSPORT=controlled \
  ./node_modules/.bin/next dev --webpack -p 3003

# the journey (the harness starts/restarts/stops its own backend)
ASSIGNMENT_UI_BASE=http://127.0.0.1:3003 \
ASSIGNMENT_API_BASE=http://127.0.0.1:8090 \
ASSIGNMENT_SOURCE_HEAD=$(git rev-parse HEAD) \
  node scripts/acceptance/assignment_recovery_ui.cjs
```

The acceptance server exposes `/_acceptance/state`, `/_acceptance/source-version`
and `/_acceptance/teach-mapping`. Those endpoints are setup-only; the product
routes used for every user action are the normal `/api/assignments` routes.

## Provenance

The journey was generated at `b24f67c29`. The four exercised files (acceptance
server, executor, assignment routes, Assignments panel) are byte-identical at
the final candidate `f8198c60e`; `browser-recovery.json` records their SHA-256
and the two source ids. The later commits on the candidate are assessment-only
and do not change the assignment recovery path.

## Scope

- one worker, one world, controlled outbox; no live provider, no real send;
- one browser and one scratch SQLite store; no multi-worker or soak claim;
- the scenario objectives carry a timestamp so reruns do not collide;
- the ambiguity scenario deliberately exposes the two-candidate UI and the
  route's identity requirement; the shared correction-form state keyed by
  concept is a UX limitation, not a safety claim.
