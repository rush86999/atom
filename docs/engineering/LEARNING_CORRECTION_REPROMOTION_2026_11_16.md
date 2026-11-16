# Correcting a reviewed lesson — November 16, 2026

A reviewer can edit a lesson and its method in Learning, save the correction on
the same candidate, and approve the corrected revision before promoting it again.
Cancel discards the edit. Saving clears the old confirmation and marks the
previously promoted lesson stale so it cannot silently remain current.

## Evidence and source

The [sanitized root receipt](evidence/learning_correction_20261116/result.json)
is bound to integrated candidate `1d4f409e15174a63d7ec09a4658bca5180310d34`,
on main `7316a015527a0ed362d345e6840a15f3af0d6d6f` (#974).
Native product commits `762419840` and `9513b0d98` were integrated as
`6ddb29ef6` and `700c1b5fe`. Root verified identical backend product hashes
and the complete frontend tree against the independently tested native source.
Later documentation does not change those product bytes.

Independent checks passed: 162 backend tests across learning, native chat,
teaching and assignment callers; 12 frontend tests in four complete suites;
and 642 CI/matrix contracts after preserving the existing gates and adding the
learning controls. A real peer SQL transaction committed after the route's
initial load: the stale correction returned 409 and retained the peer's
revision 2. The earlier loaded-object-only guard failed that counter and was
replaced before qualification.

## Ordinary browser boundary

A new local world contained a synthetic persisted native-chat instruction and
an owned employee. No candidate, confirmation or promoted lesson was seeded.
The production frontend used normal form login and a real matching web session;
no cookies, tokens, browser storage or HTTP responses were injected.

The seven native Learning actions created, confirmed and promoted revision 1,
corrected the same candidate to revision 2, then freshly confirmed, promoted and
applied the correction. Canceling an intervening edit sent no Learning write.
The correction changed `Price` to `UnitPrice`, preserved customer and
qualification scope, cleared confirmation and disabled promotion until reviewed
again. Applying quantity 2 and UnitPrice 7.50 returned exactly **15 USD** for one
selected row. This was deterministic method execution, with no LLM provider.

After stopping both app processes and restarting the same world, a fresh browser
was refused by the unsigned API (401), reached `/login` with the exact Learning
callback, signed in normally, and read the same revision and lesson IDs. The
old lesson remained stale/revalidation-required and the new lesson current,
verified both through the real API and read-only SQL. Restart checks performed
zero Learning mutations. All owned app processes were stopped afterward.

## Transaction and caller behavior

Correction, confirmation, promotion, rejection and resolution use the same
existing candidate mutation guard. SQLite acquires writer admission with
`BEGIN IMMEDIATE`, rereads durable state and compares revision/status before
writing. Correction, old-lesson retirement and journal changes commit together.
The existing PostgreSQL employee-row lock path is retained; this episode does
not qualify PostgreSQL concurrency. No process-local mutex or new registry was
introduced. This follows SQLite's documented [transaction behavior](https://www.sqlite.org/lang_transaction.html),
which permits one writer and distinguishes an initial read snapshot from
immediate writer admission. Mutation callers were traced before accepting the
transaction-owner behavior.

## Retained diagnostics and limits

The initial fixture refused Personal Edition NULL scope before committing;
a separately marked fixture used its existing canonical default scope. The
first browser failed before any Learning write because its default hostname
differed from the configured login origin; the matching localhost case passed.
The first read-only restart attempt recorded an actual 401 but stopped on an
absent `WWW-Authenticate` header. A read-only continuation completed the remaining
checks. These attempts and markers remain retained; no completed Learning
mutation was replayed. Header preservation is not claimed.

This qualifies one synthetic native-chat correction/reuse journey. Live model
quality, external indexed resources, PostgreSQL concurrency and the broader
Learning and app goals still require their own evidence. The original **143
claims / 18 goals**, historical scores and `app_complete: false` remain intact.
