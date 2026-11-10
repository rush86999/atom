# Web canvas authority repair evidence — 82b29cfcc

Executed source: `82b29cfcc7c6ad46c605c59328476fbb157b38aa` on
`codex/web-canvas-authority-20261109`.

This packet preserves the independent root verification of the finite
sheets/coding canvas authority repair. It is not a whole-app acceptance claim.

## What was repaired

- Sheets and coding canvas reads and mutations now resolve the current active
  `User` row and its existing tenant, then apply the accepted creator-or-
  historical-coeditor canvas policy plus authoritative tenant/workspace scope.
- Reads and mutations are enforced in the services as well as the routes, so
  direct agent-tool calls cannot bypass the public route gate.
- Mutation appends claim the exact actor and freeze the exact Canvas row
  (tenant/workspace/creator/status) or the authorized latest audit row
  (id/tenant/author/type/action) with guarded no-op DML before the append.
- Creation reserves the existing Canvas primary key before the audit append.
  Concurrent same-id creates have one winner; another owner, the same owner and
  a cross-family id receive a typed 409. No audit migration or new table was
  added.
- The accepted historical-coeditor policy is preserved: a genuine same-scope
  historical coeditor still works. Legacy unauthorized audit rows created
  before this repair are not rewritten or purged; this packet does not claim
  that they were cleaned up.

## Root verification (same HEAD before and after)

- Normal root conftest controls: **17 passed, 39 warnings, 30.65s**.
- Original independent ASGI probe: **1 passed, 2.88s**.
- Independent repair assertions passed: **8 original peer/collision cases
  refused**, **16 scenarios overall**, owner cases preserved, exact row
  before == after.
- The copied `root-independent-case-results.json` retains its probe-template
  `source_only_cases` text verbatim; in this repaired run
  `runtime_reproduced` is false because the original failures are refused.
  That stale template sentence is not a claim about the repaired source.

Raw `normal.log`, `original.log`, scratch databases and tokens remain private
under `/private/tmp` and are not committed.

## Files

- `verification.json` — root before/after source identity and command exits.
- `root-independent-case-results.json` — root's independent ASGI scenario
  results, copied verbatim.
- `root-proof-summary.json` — safe summary of the root run and its counts.
- `independent-probe.py` — root's independent ASGI probe source.
- `original-negative-reproduction.json` — preserved pre-repair negative
  reproduction; its original capture timestamp is unchanged.
- `commands.json` — sanitized commands/results; raw logs stay private.
- `MANIFEST.json` — strict Git source/artifact identity.

## Limits

- No frontend, browser, live DB, provider, model, account, install, deployment,
  PR or merge was performed.
- No broad normal-suite or Python 3.14 claim is made.
- One generic same-second canvas-version restore-ordering failure remains
  observed and pending qualification; it is outside this sheets/coding repair
  and is not claimed fixed.
- Root resolves the 812/main integration separately; this evidence branch does
  not merge or open a PR.
