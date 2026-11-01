# Campaign C2 — the elapsed-gate run (fresh identity)

C2 exists because Campaign C resumed 11 minutes before the owner's two-hour
gate. C's clock was not reset; C stays intact as the upgrade/restart control.
C2 is a separate assignment on a separate world with independent operation and
effect counters.

## Identifiers

| Item | Value |
|---|---|
| World | `backend/data/acceptance_worlds/long_run_20261101_b` |
| Backend / frontend | `8085` / `3145` (dedicated build retargeted to 8085) |
| Run | `cac9cbd6-f72b-4fbb-b106-f0990fc5b191` |
| Assignment | `asg-bc8171a465894137` |
| Objective | Sum Price for the second integrated quote sheet |
| Teaching revision | `851207ec455336d3+cabba8f03b6894fa+map` |
| Correlation | `quote-missing-currency-2` |
| Serving source | `d535aa7d36cf-dirty.f394d13406d1` (product tree `715969f01d23`) |

## Timeline (UTC)

- `17:55:59Z` — campaign start
- `18:04:53Z` — durable external-fact wait reached
- `18:14:50Z` — **real backend restart while waiting**: pid 66715 stopped,
  pid 68921 started against the same database/stores; the run is still
  `waiting`, same assignment, same teaching revision, `source-1` still
  `110.00` with operation `3e8eba43-…` and `attempts=1`
- `18:37:40Z` — **pinned restart** for closure: pid 73022 started from the
  clean worktree `/private/…/c2-pin` at `414d8add3` (backend tree
  `715969f01d23`); same waiting state and receipts (`state-pinned.json`).
  The cancellation repair `f5d2e085a` is a separate source and is not loaded
  by this process.
- **no resume before `20:04:53Z`** (two real hours after the wait)

The restarts moved from source `d535aa7d36cf` to `414d8add3112`; the product
trees are identical (`backend 715969f01d23`, `frontend c921cb82e784`), so the
only change is harness/test history. The pinned closure process serves
`414d8add3112` from `c2-pin`. See `state-after-restart.json` and
`state-pinned.json`.

## Completed work before the wait

`source-1` is `applied`, operation `3e8eba43-a0b5-4443-9a75-6042d01db20c`,
`attempts=1`, value `110.00` USD over four rows
(`15.10 + 20.20 + 30.30 + 44.40 = 110.00`). `wait` is `waiting` with
operation `517f45fc-5f23-41f6-a2be-4c58bcac7ebd`.

## Closure (after `20:04:53Z`)

- gate check: **7,239.8 s** elapsed after the recorded wait (>= 7,200 s)
- status: `waiting` → `completed`; same run `cac9cbd6-…`, same assignment
  `asg-bc8171a465894137`, same teaching revision
  `851207ec455336d3+cabba8f03b6894fa+map`
- `source-1`: **110.00** USD (15.10 + 20.20 + 30.30 + 44.40), operation
  `3e8eba43-a0b5-4443-9a75-6042d01db20c`, **attempts=1** before and after;
  not recalculated or dispatched again
- `wait`: applied with the correlated reply; `deliverable-1`: applied;
  `send`: applied (operation `2a593acd-…`)
- artifact: `sum-price-for-the-second-integrated-quote-sheet-20d32298.docx`,
  **37,211 bytes**, SHA-256 `bce1a2ad9f74fc09c81896b282adf9a49a079a89c461d5d5a5bdaf6768fe6a94`,
  Normal **Arial 11.0**, body `sum of Gross Amount: 110.00 USD`
- exactly **one** controlled outbox line, operation `2a593acd-…`
- **explicit controlled approval**: `send` required approval, payload
  `ca0ab0a5ed05688f28339e0f3d0e68f56aa9d7a863bb3ff528aacab7c6320cf6`,
  purpose “Send the prepared response”. This is recovery with a human/controlled
  approval step, **not** approval-free autonomous completion.
- duplicate resume twice: 200 / `completed`, no extra effect; duplicate
  correlated reply: 404 `No open gap carries this correlation id…`
- final restart: pid 87659 from `c2-pin` at `414d8add3112`; run remains
  `achieved`, artifact SHA matches, outbox remains one line (`state-final.json`)

### Budget snapshots (pre-repair source `414d8add3`)

| Stage | paused_seconds | waiting_since | active_wait |
|---|---|---|---|
| before response | 0.0 | `18:04:41Z` | null |
| after response | **7251.69** | null | null |
| after approval | 7251.69 | null | null |
| after resume | 7251.69 | null | null |
| after completion | 7251.69 | null | null |
| after duplicate response | 7251.69 | null | null |

The interval was credited **once**; approval/resume/duplicate did not add it
again. This source predates the budget pause-credit repair, so it is historical
execution evidence, **not** verification of the repaired budget code. The
repair is verified separately by the 63 focused controls on backend tree
`c2963fbcdc8e` (commit `f1ef414c3`).
