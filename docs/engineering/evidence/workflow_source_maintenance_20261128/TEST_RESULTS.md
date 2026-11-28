# Existing-worker source lease maintenance

Executed source: `4e09108ffbb33aa83c56268441cad5430b279de4`. Final frozen Python3.11 gate:

```text
= 310 passed, 625 deselected, 83 warnings, 18 subtests passed in 216.46s (0:03:36) =
```

All15 selected source/test/CI hashes stayed unchanged across execution and match Git objects at the source. The exact command is retained in frozen-verification.json. The expanded event/credential/renewal/maintenance gate and CI-preservation contract run together; the unchanged625 real_gate_shell matrix remains deselected locally. No local Python3.14 result is claimed.

## Behavior and evidence

The existing lifespan-owned workflow event worker now owns one bounded source maintenance task. It scans a keyset page of actual hashed workflow_event_source registry rows, closes the listing DB before awaiting provider I/O, skips malformed/disabled entries, and advances across refused/slow rows. It calls the existing durable renewal service with current actor/connection authority. Per-source timeout leaves interrupted PATCH arbitration durable for GET-only recovery. Source network waits do not stop ordinary event polling. Shutdown, direct parent cancellation and restart tests prove maintenance task ownership and cleanup; there is no second runner or queue.

Real scratch registry/audit/operation effects qualify a due source renewal and replay, keyset fairness after malformed/disabled rows, a slow first source followed by a real later renewal, and timeout after actual controlled PATCH followed by read-only reconciliation. The slow-first orchestration fault is injected; the later source uses the real service. Lifecycle tests control timing and event-drain transport to examine ownership independently. The existing worker-ownership unit fixture explicitly stubs maintenance to prevent default-DB access.

A separate controlled-clock regression renews through three lease generations, preserving every original enrollment field and replaying without additional create calls. It is simulated time, not a live days-long soak. Original enrollment/public-callback/worker/credential and additive CI controls remain included.

One no-tools OpenCode Go DeepSeek proposal informed the patch (CLI reported cost0; no paid fallback). Root rejected its invented key schema and batch-timeout cursor starvation, then used real registry fixtures and owned-finally cleanup. The worker had no tool events and did not apply or accept code.

## Open scope

This schedules due lease renewal only. Initial enrollment still lacks lifecycleNotificationUrl. Proactive token/subscription reauthorization, authenticated lifecycle handling, missed-event delta recovery, removed/expired subscription succession, days-offline operation, full-main/fresh-rule browser qualification and applicable PostgreSQL/multi-worker/soak remain open. No live application model/provider, credential campaign, deployment or merge occurred. Whole-app completion remains open.

References: [Microsoft subscription update](https://learn.microsoft.com/en-us/graph/api/subscription-update?view=graph-rest-1.0) and [lifecycle guidance](https://learn.microsoft.com/en-us/graph/change-notifications-lifecycle-events). Maintaining lease expiry does not prove recovery of notifications lost during an authorization or availability gap.
