# Campaign C — durable assignment across a product upgrade

This is the **restart/upgrade control**, not the elapsed-gate run. It resumed
11 minutes before the owner's two-hour gate and is kept intact rather than
back-dated. The qualifying elapsed sibling is `../long-run-20261101_b`.

## Timeline (UTC)

- `15:04:44Z` — campaign start (first attempts failed before any durable wait)
- `15:37:56Z` — durable external-fact wait reached on run `790dc6cd-…`
- `16:42:15Z` — real backend stop → restart against the same stores
- `17:26:58Z` — correlated answer delivered; assignment completed
- elapsed after the wait at completion: **1 h 49 m** (below `17:37:56Z`)

## Product source

| Phase | Backend tree | Commit served |
|---|---|---|
| Work before the wait | `68aa1a826d0d` | `2d01d31772da-dirty.537a04f47d08` |
| Restart and resume | `715969f01d23` | `cf102eeac1ce-dirty.b0c55aa8fb39` |

The restart intentionally moved the same SQLite stores to the tree containing
the durable-wait wall-budget fixes (`02f3ae2cd`, `198b64e51`, `5b8bf1e0c`,
`a1862fec7`). The assignment id, teaching revision, mapping and `source-1`
operation survived unchanged. The checkout is dirty by one harness file
(`launch_integrated_local_candidate.sh`, `ATOM_FRONTEND_DIR`), not product code.

## Completed work at the wait (authoritative step receipt, not the counter)

`goal_runs.steps_executed = 0` is a stale summary counter. The assignment's
`source-1` step is `applied`, operation `6fff72ff-…`, `attempts=1`, result
`sum of Gross Amount = 400.00 USD across 3 row(s)` with row receipts
`C2=100.00`, `C3=250.50`, `C4=49.50` and `observed_status="confirmed"`.
Independent arithmetic: **400.00**. After the restart the same step still has
operation `6fff72ff-…` and `attempts=1` — it was not re-executed.

## Resume result

- same run `790dc6cd-0804-422c-b7f4-b44d27672da2`, assignment
  `asg-247f745f83484fc3`, status `achieved` / `completed`
- teaching revision unchanged `8735dd7b3648a7d8+a52a495bf104849f+map`
- `wait` applied with the correlated reply, `deliverable-1` and `send` applied
- artifact `sum-price-for-the-integrated-quote-sheet-7ae420b6.docx`,
  **37 187 bytes**, SHA-256 `9c44aeeb…4466d806`, Normal **Arial 11.0**,
  body `sum of Gross Amount: 400.00 USD` plus the reply fact
- exactly **one** controlled outbox line, operation `7243572b-…`, subject
  `[Quote] Sum Price for the integrated quote sheet`
- budget `paused_seconds = 6525.69` against `max_wall_seconds = 900`

## Correction while waiting

A `task_scope=revised` lesson (Calibri 14) was taught before the reply was
delivered. The active run kept Arial 11 and revision `8735…`. New revised work
used revision `0ceff61904cb889b+map`, produced **Calibri 14** and `2225.75 USD`
(1250.50 + 900.00 + 75.25), SHA-256 `f875e98b…496acb6` (run `d74e637f-…`).

## Evidence

`part1.json`, `state-waiting.json`, `state-after-restart.json`,
`state-completed.json`, `timing.txt`, `first-conflict.*`,
`missing-qualification.*`, `waiting-before-restart.png`,
`part2/active-completion.*`, `part2/long-run-revised.*`.

`part2.json` was not produced: the script's follow-on revised run could not
find a CSV that had not been uploaded. The active completion is recorded
independently in `state-completed.json`, the downloaded DOCX and the outbox;
the failed follow-on is preserved, not hidden.
