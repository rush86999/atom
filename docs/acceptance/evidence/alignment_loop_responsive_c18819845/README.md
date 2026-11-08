# Alignment certification responsiveness

Frozen runtime: `c1881984528bce79c7299a30024406ca935399f9`.

The scheduled automation loop and public run-now consumer invoked synchronous certification on the application event loop. The independent heartbeat queued from the controlled pass could not execute while that pass waited (baseline exit 1). The repair uses one shared asynchronous offload boundary, copies ContextVars, holds the pass exclusion until the worker actually exits, and routes notifications back to the original application loop. Failed cross-thread scheduling closes its unscheduled coroutine. Authentication, consent, flag and interval semantics are unchanged.

## Qualification

- Unchanged d9a45f559 baseline: 31 existing controls pass.
- Candidate: 40 affected controls pass on Python 3.11 and 3.14, including real scratch SQLite pending-consent/fresh-session readback.
- Existing CI-lane preservation contract: 27 pass. The required alignment CI step now includes all affected modules.
- Independent heartbeat: baseline fails, final candidate passes.
- Candidate runs were performed before commit, with their accepted base and exact three runtime/test file hashes recorded in each spec. Those hashes match the frozen runtime commit; the original logs are not relabelled as a clean-base run.

The native DeepSeek Flash author worked from four verified public source files. One attempted shell listing was denied and not executed. Root inspected and executed the proposal, supplied the explicit interval fixture, unified the actual public consumer, and added shutdown-race coverage.

## Retained diagnostic and limits

An initial partial snapshot omitted runtime-settings dependencies. Its scheduler-only fixture failed before reaching the controlled timer, repeatedly logging an exception. The run was interrupted; a bounded traceback diagnostic terminated with exit -11. This is retained as an incomplete-harness diagnostic, not a production regression or passing test. The final fixture explicitly supplies the interval rather than accessing a DB for a scheduling-only control.

Cancellation releases the awaiter, not a physical worker; a replacement pass skips while that worker retains the gate. This is process-local exclusion, not distributed locking or PostgreSQL/multi-worker/soak qualification. The public caller test uses the actual consumer with its owned pass and registration doubled; authentication is not its claim. No real model/provider, external notification, deployment or elapsed overnight campaign ran. TEAM-05 real scheduled configured-transport qualification remains open.

References: [asyncio blocking I/O offload and ContextVars](https://docs.python.org/3.11/library/asyncio-task.html#asyncio.to_thread), [cross-thread coroutine scheduling](https://docs.python.org/3.11/library/asyncio-task.html#asyncio.run_coroutine_threadsafe).
