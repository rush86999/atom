# Brennan connected-workflow batch — review candidate

Status: **submitted for independent verification; not self-accepted.** This is
additional business-workflow qualification. Historical 111/123 scope is
unchanged, and no live provider lookup, refresh, write or send occurred.

## Frozen source

| Item | Value |
|---|---|
| Worktree | `/private/tmp/atom-brennan-review` |
| Branch | `codex/brennan-joint-review-20261101` |
| Base candidate | `c442cd9d7eeba44e17feada5e452c0c46fc9be13` |
| Executed source head | `6431bcb7857fd43dffc1ed685fffe47044669e5c` |
| Tree at execution | clean (`dirty=false`) |
| Browser artifact commit | `f8a55adf9` |
| Manifest | `MANIFEST.json` (this directory) |

The backend captured its own boot identity once and exposed it through
`/api/health`, `/_acceptance/state` and `/_acceptance/connected/state`. The
browser asserted the backend's revision, clean source id, process start, PID,
repository/backend paths and scratch world/database — not the runner's git
state. A mismatched source, world or occupied port fails the gate instead of
reusing an unknown server. The manifest/TEST_RESULTS commit is docs-only after
the executed source and artifact commits and was not served.

## Verified findings closed

1. **Hard persisted-byte bound.** Executable results are measured with the
   persistence JSON settings (`ensure_ascii=True`, default separators). The
   boundary accepts exactly 4,194,304 UTF-8 bytes and refuses limit-plus-one,
   backslashes, quotes, control characters, multibyte keys/values, many short
   values and nested receipts. Read overflow is a typed failure; post-dispatch
   mutation overflow is uncertain with the original operation/remote identity
   and reconciles through a fresh session without a resend.
2. **Genuine runtime attestation.** PID, process start, source revision, clean
   source id, instance id, repository/backend tree and world/database identity
   are served by the backend and asserted by the browser. The former
   `version === "v1"` check is retained only as a connected-provider source
   version check, not as code identity. The runner also refuses an occupied
   acceptance port before spawning.

## Connected browser journey — 25/25

The real Assignments page runs against the standalone assignment acceptance
server (real routes/executor/sqlite); only provider services are faked. The
production registered `connected.workdrive.read_file` action and CSV parser are
retained.

- occupied acceptance port is refused, not reused
- pause on discount qualification, leave, restart the real backend process
- restart serves the declared clean source/tree/world; health and connected
  routes identify the same instance
- obligation survives restart; v1 calculation completes before correction
- source changes to v2, the affected read branch is invalidated, and the
  corrected calculation reaches estimate approval
- current rows cite v2 with the complete WorkDrive receipt/hash; v1 rows remain
  only in `prior_results`
- estimate readback is `376.75`; dependent Outlook draft uses `376.75`
- no send: `send_attempts == 0` (not a draft-text heuristic)
- duplicate resume from two independent pages does not bypass approval or
  duplicate effects
- cancellation refuses a late correlated response, gap resolution and resume
- provider acceptance with lost readback is `uncertain`; the dependent draft
  stays pending
- the uncertain job survives a real backend restart with the same provider
  effect/call counts (persisted fake-provider world), so no second create
- reconciliation settles the original estimate; only then does the dependent
  draft complete without a send

## Supporting controls

| Command scope | Result |
|---|---|
| `tests/test_assignment_quote.py tests/test_assignment_executor.py tests/test_assignment_routes.py tests/test_quote_evidence.py` | 178 passed |
| joint core (routes/executor/quote/evidence/transfer/readback/Agent 2 connected/bookkeeping) | 284 passed |
| Agent 2 focused (connected/readback/bookkeeping/checkpoint/accounting) | 279 passed |
| tracked transfer boundary (`serialization_budget`, `quote_rows`, joint document flow) | 32 passed |
| consolidated batch (all tracked focused files above plus campaign/real-effect) | 312 passed |

The tracked transfer command excludes the verifier's external probe file. The
independent verifier's own run remains separate and is not required for this
manifest.

Public-route coverage added in this batch:

- missing qualification opens a typed `discount_scope` gap; resolving
  `licensed` completes at `90.00`, an identical replay is idempotent, and a
  different answer is refused;
- equally specific conflicting discounts open `discount_rule_conflict`; an
  unrecognized answer produces no arithmetic and re-asks, then a named rule
  completes at `90.00`;
- a non-sales expense reconciliation uses the same assignment API, maps
  miles/nights, computes `260.40 USD`, and produces a document artifact.

Bookkeeping route coverage includes evidence → vendor/CoA/period resolution →
balanced proposal → bound approval → one create → full readback, with
missing/ambiguous vendor, closed period, changed payload, incomplete duplicate
sweep and incomplete/mismatched readback refusing or reconciling as
appropriate. Payment/posting authority is never inferred from a readable
invoice. OneDrive XLSX is covered through the public route with the production
registered action/parser.

## Changed source and tests vs base candidate

```text
backend/core/assignment_executor.py
backend/core/connected_actions.py
backend/core/quote_rows.py
backend/core/runtime_identity.py
backend/scripts/assignment_browser_acceptance_server.py
backend/tests/integration/test_brennan_joint_real_connected_effect.py
backend/tests/test_assignment_routes.py
backend/tests/unit/test_brennan_bookkeeping_registered.py
backend/tests/unit/test_quote_rows.py
backend/tests/unit/test_serialization_budget.py
scripts/acceptance/brennan_connected_browser.cjs
```

## Exclusions

- Standalone acceptance server, not full-app authentication/profile/navigation
  proof.
- No live Zoho/Microsoft credentials, refresh, write or send; the earlier
  one-use Outlook authorization remains exhausted.
- No universal mini-app/canvas runtime claim.
- Executed source and artifact commits are distinct from this docs-only
  manifest commit; the manifest commit itself was not served.
- Historical 111/123 milestone is unchanged; this batch is additional workflow
  qualification.

## Next

After independent verification, continue the user-authored-canvas successor on
a separate branch under `docs/engineering/USER_AUTHORED_CANVASES.md`.
