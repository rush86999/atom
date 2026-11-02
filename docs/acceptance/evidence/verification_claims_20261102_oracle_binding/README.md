# Verification claims batch 1c — oracle request/readback binding

Status: **submitted for independent verification; not self-accepted.** This
continues the withheld ORACLE-01 repair matrix on top of the accepted TEAM-05
controlled service mechanism and the verified MEM-07 event-to-pending/review
boundary.

## Executed source

| Item | Value |
|---|---|
| Worktree | `/private/tmp/atom-canvas-successor` |
| Branch | `codex/brennan-canvas-successor-20261101` |
| Previous source | `22e7ab10a` (evidence tip for `6f0acd0bd`) |
| Executed source | `45d015fa3` |
| Tree at execution | clean |
| Runtime | local service/API tests; no browser claim in this bundle |

## Repairs

### Immutable request binding

`core.assignment_executor._action_registry_adapter` now passes the authorized
request digest, operation id, provider, organization and target as separate
`_oracle_expected_*` values. The untrusted returned envelope is never allowed
to overwrite them. `core.connected_actions.oracle_request_binding` derives the
same values from the authorized arguments using the canonical payload builders
the actions use before dispatch. The full approval digest remains enforced by
the task lifecycle; the provider material-payload digest is compared
separately.

### Fail-closed consumer

A dispatched mutating effect becomes `uncertain`, not `applied`, when:

- the oracle raises or is unavailable;
- the oracle returns `None`;
- the postcondition is refuted;
- the oracle result is malformed or carries no usable verdict.

The uncertain result retains `remote_id`, `provider_ref`, provider, operation,
provider receipt, digest and verification evidence. It is never eligible for
automatic resend. Read-only actions keep their separate outcome vocabulary.

The built-in verifiers are now imported when `core.oracle` is imported, so a
production consumer that only imports the oracle package does not see an empty
registry.

### Digest and identity checks

The connected verifier now requires:

- an explicit `verification` object with `status == "verified"`;
- empty `missing_fields` and `mismatches`;
- syntactically valid 64-character hexadecimal digests;
- agreement between the top-level and provider-receipt digests;
- expected request digest agreement when an authorized request digest exists;
- present and matching operation, provider, account/organization and target
  identity when expected;
- a non-empty material-field mapping with the action's required fields.

Missing verification, empty verification, malformed verification, mismatch or
incomplete status, digest drift, missing/wrong remote object, sparse material
fields and identity drift all refute.

### Commercial readback same-object binding

`core.commercial_readback.bind_remote_identity` binds the observed provider
object id to the create response before material fields count. A missing id is
incomplete; a different id is a conflict. Estimate and bill readbacks use it;
neither returns applied for the right fields on the wrong record and neither
creates a second object.

### Outlook draft readback

`core.connected_actions.outlook_create_draft` independently calls
`OutlookService.get_email_by_id` after the single create.

- Missing readback identity or material fields -> `uncertain`/`incomplete`,
  with `missing_fields`; requested identity is not reused as observed identity.
- Different observed object id -> `conflict`/`mismatch` on `remote_id`.
- Same object but wrong subject/body/recipients -> `conflict`/`mismatch`.
- Correct same object -> `applied`/`verified`.

Every branch preserves `requested_remote_id` and `observed_remote_id` in the
result and read receipt. No branch creates a second draft or sends mail.

### Runtime positive/uncertain/reconciliation journey

A real registered `connected.books.create_estimate` action runs with a
controlled provider transport. The provider create lands once, the estimate
readback verifies, and then the oracle raises. The executor records
`uncertain`, retains the remote identity and reconciliation requirement, and
does not dispatch a second create across a fresh lifecycle/session reload. A
dependent Outlook draft stays blocked. Reconciling the **original** operation
as applied then lets the dependent draft proceed once, with its own independent
readback.

## Tests

| Scope | Result |
|---|---|
| Oracle/TEAM/MEM + original and repair probes | **36 passed** |
| Connected actions, quote/document/real-effect journeys, canvas assignment | **77 passed** |
| Assignment routes/executor/quote + oracle confidence | **188 passed** |
| Canvas focused suite | **127 passed** |
| Teaching neighborhood | **203 passed** |
| Serialization + generic-agent oracle regression | **29 passed** |
| Frontend canvas suites | **7 passed** |

All logs are tracked in this directory. `oracle_registry.json` records the
registered mutation inventory: 6 mutating actions, all 6 covered, plus the
existing task/workflow verifiers.

## Carried forward

- TEAM-05 remains accepted at the controlled deterministic service seam.
- MEM-07 is closed at event -> pending candidate -> review; safe autonomous
  application and measured improvement are not claimed.
- Historical `111/123`, connected acceptance `6431bcb78`, typed-canvas
  `4859b0ce2477`, canvas assignment/teaching `a87882526323` and all tags are
  unchanged.

## Remaining open

ORACLE-01 coverage is the actual registered action-registry mutation classes
above, not a whole-application dispatch/coverage inventory; full marketing
closure still requires that inventory. ORCH-01/02/07 and GOAL-02 need
model-backed planning/utility work. MINI-03/04/05 need supported Linux/KVM.
INT-09 and ROUTE-07 need separate live-provider authorization. No live provider
lookup, refresh, write, send, credential change or spend occurred.
