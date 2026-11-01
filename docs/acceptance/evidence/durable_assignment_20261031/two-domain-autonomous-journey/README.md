# Integrated two-domain autonomous journey — browser, 5/5

The ordinary user starts two unfamiliar-dataset jobs from the Assignments page,
grants each one bounded standing authority for its single send, leaves while
both wait, the backend restarts, and both jobs complete on return without a
per-send approval.

| Domain | Source | Result | Delivery |
|---|---|---|---|
| Sales | `scotch-parts.xlsx` / `US$ SCOTCH PARTS` | `85` | document + one send to `sales@example.invalid` |
| Grants | `grant-applications.xlsx` / `GRANT APPLICATIONS` | `4250` | presentation + one send to `grants@example.invalid` |

## What the run proves

- both jobs entered `waiting` and survived a real backend restart
  (the PIDs are recorded in `two-domain.json`);
- each send was covered by its own 1-use grant and recorded a
  `standing_authority_receipt`;
- both grants are `used_effects=1`, `max_effects=1`, `status=exhausted`;
- the controlled outbox contains exactly two effects, one to each named
  recipient;
- **zero** `assignment_approval` HITL rows were created;
- the page never showed an approval prompt for either send.

`two-domain.json` records the objectives, run ids, step statuses, outbox rows,
PID identities, screenshot paths and source hashes. The recorded run is source
`b7ee7ee22` after the post-effect classification and hard-cost fixes. Screenshots are in
`screenshots/`.

## Reproduce

```bash
# backend acceptance server (fresh world)
export WORLD=<scratch>/two-domain-autonomous
export PYTHONPATH=<repo>:<repo>/backend:<pyarrow-overlay>
ATOM_ASSIGNMENT_BROWSER_WORLD="$WORLD" \
ATOM_ASSIGNMENT_BROWSER_WORLD_RESET=1 \
ATOM_ASSIGNMENT_BROWSER_PORT=8090 \
ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT=1 \
  <python> backend/scripts/assignment_browser_acceptance_server.py

# normal Assignments page pointed at the acceptance server
cd frontend-nextjs
NEXT_PUBLIC_API_URL=http://127.0.0.1:8090 \
NEXT_PUBLIC_ALLOW_LOOPBACK=1 \
NEXT_PUBLIC_ASSIGNMENT_TRANSPORT=controlled \
  ./node_modules/.bin/next dev --webpack -p 3004

# journey (the harness starts/restarts/stops its own backend)
ASSIGNMENT_UI_BASE=http://127.0.0.1:3004 \
ASSIGNMENT_API_BASE=http://127.0.0.1:8090 \
ASSIGNMENT_SOURCE_HEAD=$(git rev-parse HEAD) \
  node scripts/acceptance/two_domain_autonomous_ui.cjs
```

## Scope

- one worker, one scratch world, controlled outbox; no provider or real send;
- the two datasets are seeded unfamiliar-schema fixtures, not live connectors;
- no multi-worker, multi-day soak or arbitrary-domain claim;
- the standing grant covers only the named recipient and one effect per
  domain; live email send remains approval-required.
