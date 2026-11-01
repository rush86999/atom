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
- **no resume before `20:04:53Z`** (two real hours after the wait)

## Completed work before the wait

`source-1` is `applied`, operation `3e8eba43-a0b5-4443-9a75-6042d01db20c`,
`attempts=1`, value `110.00` USD over four rows
(`15.10 + 20.20 + 30.30 + 44.40 = 110.00`). `wait` is `waiting` with
operation `517f45fc-5f23-41f6-a2be-4c58bcac7ebd`.

## Resume assertions (to fill after `20:04:53Z`)

1. Snapshot the durable state, stop **only** pid 66715, restart against the same
   stores, verify the same run is still `waiting` with the same revision and
   correlation.
2. Deliver the correlated reply; assert the same run/assignment, `source-1`
   still `attempts=1` with the same operation id, expected artifact content,
   SHA-256 and one controlled effect; no second send.
3. Record elapsed after the wait, budget `paused_seconds`, and the serving
   identity after restart.
