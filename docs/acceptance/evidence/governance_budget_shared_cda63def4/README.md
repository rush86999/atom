# Shared governed budget decision and caller-transaction safety

The precursor governance_budget_context_89c75f061 packet remains unchanged:
actual governed Generic→MCP→registry exposed a configured-account hard-stop
bypass because workspace_id was passed as tenant_id. The bounded resolver
repair and31-control async gate are preserved at their own sources.

Whole-caller review then found five additional failing cases: sync utilities
inside async routes skipped their check, and sync hard/soft stops could propose
ordinary action review. The12-case before matrix fails5/passes7. The existing
budget decision has zero await points and uses the caller's synchronous ORM
Session. It now has one explicit sync body and its compatible async wrapper;
no nested loop, worker thread or second financial engine is added. The scope
and refusal policy are shared. Legacy unbound utilities restrict against the
actual agent account rather than using a default-workspace alias; explicit
request bindings remain exact. This is budget restriction, not actor authority.

A second independent probe showed spend-rollup refresh committed unrelated
caller edits (dirty and already-flushed both fail). Preflight now requests
persist=False from the existing aggregation service and neither commits nor
rolls back caller-owned work or mutates cached rollup fields. Explicit rollup
writers keep default persistence. Both original negatives are retained, with
new read-error preservation and a real explicit-rollup compatibility positive.

## Frozen final results

At sourcecda63def4 the exact new normal-CI gate passes45 controls, actualexit0:
23actual MCP/scope/mode +5transaction/rollup +17existing budget controls.
The broader existing-governance and real-workflow checkpoint selection passes
146, fails the one known unchangedw29 confidence0.5 assertion, and skips one
legacy unavailable budget module; its true overall exit1 is retained. This is
not presented as an all-green full suite. The intermediate140/2/1 run and its
Mock fluent-query protocol correction remain recorded; no assertion was
weakened, no tests deleted or xfailed. Source-bound logs/exits/JUnit/commands
are included rather than converting prior evidence to the current source.

Design references: FastAPI documents that ordinary utility functions invoked
from async code run directly, and SQLAlchemy distinguishes synchronous Session
work from AsyncSession/run_sync. Atom already uses a sync Session and a sync
ledger body here; this repair shares that implementation without pretending
it is nonblocking or transferring the Session to another thread.
https://fastapi.tiangolo.com/async/#other-utility-functions
https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
The precursor AST extraction check is explicitly at62e0; later persist=False
is a disclosed behavior change for preflight, not a claim that final AST bytes
are identical to the original rollup-writing implementation.

Existing service-error degradation, concurrent spending reservations, budget
changes mid-dispatch and broad financial safety remain outside this bounded
proof. No live model/provider, credential, actual charge/send, guest, browser,
Postgres/multiworker or deployment operation was used. The app is single tenant
and keeps its existing personal null/default compatibility. Full app completion
and TASK-WAIT-01 remainopen.
