# Canvas lifecycle current-scope delete/undelete — lead evidence 8e4b494d7

Status: **evidence-only delivery for independent root verification. Not
self-accepted, not merged. Whole-app ORACLE remains open.** This packet records
the root-completed gates at the frozen runtime source and does not repeat the
inference campaign that produced the repair.

## Executed source and baseline identity

| Item | Value |
|---|---|
| Candidate branch | `codex/canvas-lifecycle-verified-20261107` |
| Candidate source | `8e4b494d722b5ca07c79cc487adab65e1350f2b8` |
| Candidate tree | `c2c8abf6661d98fc54ff0cd5da15736e6d59c321` |
| Candidate backend tree | `ae203eef0063835ce6d3f5a034b2126e65b49dce` |
| Baseline source | `27a1830a27e73ed30124a82d01bb710e26bc7113` |
| Baseline tree | `cd5bc30aaa8ed41af5f625e697dd4e27eb850468` |
| Baseline backend tree | `5a8ff02bf90dafe34e99cf564d50f8929b7fec17` |
| Main-equivalent source | `8ded00232c30961a990e675e06ec672ef6a43910` |
| Main-equivalent backend tree | `5a8ff02bf90dafe34e99cf564d50f8929b7fec17` |
| Baseline backend equals main backend | yes (`5a8ff02b…`) |
| Runtime | real mounted routes, real scratch SQLite, fresh sessions for readback |
| Model / provider / browser calls | none |
| Live PostgreSQL / multiworker / soak | not run and not claimed |

The exact tree identities are also in `SOURCE_IDENTITY.json`. They were read
with `git rev-parse <commit>^{tree}`, `git rev-parse <commit>:backend`, and
`git show <commit>:<path>`; no hash was invented.

## What the frozen source contains

The direct HTTP `DELETE /api/canvas/{canvas_id}` and
`POST /api/canvas/{canvas_id}/undelete` routes, and their ToolRegistry/MCP
equivalents, share one verified lifecycle consumer:

- the actor's **current** tenant/workspace is authorized against the
  authoritative `Canvas` row in the same transaction as the append;
- audit-only canvases authorize the newest audit tenant and record workspace as
  legacy;
- the server owns the logical operation id, the prior/tombstone/source CAS and
  the exact content digest;
- replay returns the original audit id without a second row or broadcast;
- a committed result is independently re-read in a fresh session; an unknown
  commit is reported as `effect_unknown`/`do_not_repeat`.

This packet does not re-argue the design. It records the independent gates that
root actually ran against `8e4b494d7`.

## Gates (do not sum these numbers)

The selections overlap and are different kinds of evidence. The numbers below
are deliberately **not added together**.

### 1. Independent root probe — 9 passed on candidate

Root-authored portable probe:
`independent-probe.py` (origin: docs branch
`codex/current-claim-reconciliation-20261107`, commit
`de180672830e66e49ed87bcf4f7abedf9ff0f199`, blob
`ede2276fa2292558d77ed2b12928b887d1d6414d`). The probe uses real mounted
routes, real scratch SQLite with foreign-key enforcement, injected current-user
dependency, real writer/service/readback and immutable-history snapshots.

Candidate result: **9 passed** (`candidate-independent-8e4.log`).

Tests (9 cases from 3 functions):

| Case | Candidate | Baseline |
|---|---|---|
| former coeditor, delete, tenant move | pass | **fail** |
| former coeditor, delete, workspace move | pass | **fail** |
| former coeditor, undelete, tenant move | pass | **fail** |
| former coeditor, undelete, workspace move | pass | **fail** |
| supported owner delete | pass | pass |
| supported same-scope coeditor delete | pass | pass |
| supported owner undelete | pass | pass |
| supported same-scope coeditor undelete | pass | pass |
| stranger without authorship | pass | pass |

The baseline was run against the main-equivalent backend
(`27a1830a…` backend tree `5a8ff02b…` = main `8ded0023…` backend tree
`5a8ff02b…`) and produced **4 failed, 5 passed**
(`baseline-portable-4fail5pass.log`). The four failures are exactly the four
current foreign-scope former-coeditor cases above; they are the confirmed
defect, not a relabel of an old pass. The five passes are the preserved
supported/stranger controls.

### 2. Native product suite — 31 passed on candidate

`tests/test_canvas_lifecycle_verified.py` at `8e4b494d7`: **31 passed**
(`candidate-native-8e4.log`). This is the product-authored suite added with the
repair; it is supporting evidence, not a second independent capability count.

### 3. Affected regression selection — 175 passed, 2 failed on candidate

The affected selection (7 files: canvas CRUD, direct canvas oracle writes,
canvas postcondition, generic real-MCP budget contract, budget caller
transaction contract, R79 action-registry RPC and action-registry coverage) is
**175 passed, 2 failed** on the candidate
(`candidate-affected-8e4.log`). The main-equivalent baseline rerun of the same
7 files is also **175 passed, 2 failed**
(`baseline-affected-main27a.log`).

The two failures are identical on both sources and are recorded in
`affected-comparison.json` (`identical_failure_ids: true`):

- `tests/test_r79_action_registry_rpc.py::TestRpcRouteAuthenticated::test_list_actions_includes_registered_names`
- `tests/core/test_action_registry_coverage.py::TestDocumentsSearchAction::test_search_legacy_path_flag_off`

They are pre-existing affected-selection failures outside this canvas lane.
They are **not** claimed as passing and are not canvas lifecycle regressions.

## How the counts are used

- The independent probe is the only independent capability gate. Its new
  capability result is: **4 previously failing current-foreign-scope negatives
  now pass**, while **5 supported/stranger controls remain passing**.
- The native 31 and affected 175 are supporting/regression evidence. They are
  not added to 9, 4, 5, 31 or 175 to produce a larger capability count.
- The baseline's 5 passes and 175 passes are preservation evidence. They are
  not counted as new capability.
- The intersection/overlap between the focused probe, native suite and affected
  selection is not resolved into a sum. No arithmetic total is claimed.

## Inherited runner label is cosmetic

The helper runner used by root prints:

```text
Actual SQLite feedback gate exit: <code>
```

from a generic `print(...)` line in the root runner script. That text is an
inherited runner-template label, **not** a test name, a capability claim or a
statement about a "SQLite feedback gate". The actual scope is established by
each `*.spec.json` command and its named source files:

- `candidate-independent-8e4.spec.json`: the canvas lifecycle scope probe;
- `candidate-native-8e4.spec.json`: `tests/test_canvas_lifecycle_verified.py`;
- `candidate-affected-8e4.spec.json` and
  `baseline-affected-main27a.spec.json`: the seven-file canvas/oracle/budget/
  action-registry affected selection.

No claim in this packet depends on the runner label.

## Historical negatives are untouched

This packet does not edit, copy, relabel or rescore the prior evidence. In
particular, these remain exactly as they were:

- `/private/tmp/atom-agent-cli/canvas-lifecycle-confirmed-negative.json`
- `/private/tmp/test_lead_canvas_lifecycle_scoped_history.py`
- `/private/tmp/root-canvas-lifecycle-scoped-history-authorized.log`
- the prior canvas lifecycle work order and scoped-history packet

The baseline `4 failed, 5 passed` log in this packet is the original baseline
result; it is retained as a failure baseline, not relabeled as a pass. The
candidate `9 passed` result is a new frozen-source gate, not a rewrite of the
historical negative.

## Secret scan and raw-byte preservation

The logs in this packet were scanned for common credential patterns
(`sk-…`, `ghp_…`, `github_pat_…`, `AKIA…`, private-key headers, bearer tokens,
`password`/`client_secret`/`refresh_token`/`access_token` assignments) and for
email addresses. No credential pattern or email address was found. The only
secret-looking literal is the synthetic fixture string
`secret-internal-detail` in the RPC error-redaction test log; it is a test
fixture, not a credential, and is preserved as part of the raw log.

The raw `.log`, `.spec.json` and `.exit.json` bytes were copied without
transformation and re-hashed after copy. `independent-probe.py` was copied from
its committed docs-branch blob and re-hashed. All artifact SHA-256 values in
`MANIFEST.json` were computed from these exact bytes; none were invented.

## Boundaries

- No live provider, browser, PostgreSQL, multi-worker or soak run is claimed.
- No whole-app ORACLE coverage is claimed.
- No merge, deployment, review comment, spend or send is claimed.
- The independent probe injects the current-user dependency; it is not a
  normal-login/browser qualification.
- The native suite and affected selection are supporting evidence, not a
  second independent oracle.
- The two identical affected-selection failures remain open and unclaimed.

## Artifacts

`candidate-independent-8e4.{log,spec.json,exit.json}`,
`candidate-native-8e4.{log,spec.json,exit.json}`,
`candidate-affected-8e4.{log,spec.json,exit.json}`,
`baseline-affected-main27a.{log,spec.json,exit.json}`,
`affected-comparison.json`,
`baseline-portable-4fail5pass.{log,spec.json,exit.json}`,
`independent-probe.py`, `SOURCE_IDENTITY.json`, `README.md`,
`TEST_RESULTS.md`. `MANIFEST.json` records the SHA-256 of every artifact and of
the source files executed at `8e4b494d7`. Its `source_files` map contains the
seven files changed by `8e4b494d7` plus the unchanged
`backend/core/models.py` model dependency used by the portable probe; every hash
is read from the executed commit, not a later working tree.
