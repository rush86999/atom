# Verifier acceptance — 2026-11-01

**Status: accepted within the documented local and controlled-provider scope.
This is not a release, hosted deployment, publication or universal reliability
claim.**

> **Post-acceptance note:** the budget pause-credit defect was found after this
> acceptance. It is repaired in “Post-acceptance correctness repair” below
> (successor commit `f1ef414c3`, backend tree `c2963fbcdc8e`, 63 focused
> tests). The accepted identity above is preserved and is **not** retroactively
> described as unaffected.

## Accepted identity

| Item | Value |
|---|---|
| Accepted runtime source | `bec60978b03774f190d4e33d130a7fdf1fe60cd6` |
| Accepted evidence/docs source | `88bf413e843193cbe7a034028232b7e6f2b4e7f9` |
| Frozen functional breadth | **111/123 = 90.2%** |
| Acceptance tag | `accepted-local-2026-11-01-90pct` |
| Configuration | local, single worker, SQLite scratch worlds, controlled outbox, controlled local providers |
| Transport | controlled effects for this campaign; the separately accepted one-use Outlook send and Microsoft read-only qualification remain closed |

## Independently confirmed

- Frozen inventory still contains **123 functional claims**, with **111 marked
  verified**; claim IDs and acceptance criteria are unchanged.
- **57 independent focused tests passed** (55 executor controls plus both
  public-route cancellation tests).
- The original budget reproduction remains refused: **2,000 s elapsed − 100 s
  waiting = 1,900 s working**, over the 900 s limit.
- Repeated, concurrent and restarted retries no longer duplicate wait credit.
- All **97 manifest entries** exist in the committed Git tree and match their
  SHA-256 hashes and byte counts.
- The cancellation repair is included in this candidate.
- The genuine two-hour run remains evidence for elapsed waiting and recovery on
  its recorded source. Correct budget enforcement is established separately by
  the repaired-source controls; the two claims are kept distinct.

## Findings closed

1. **Retry could erase consumed working time.** Wait credit is now keyed by the
   persisted wait-operation identity, bounded by recorded start/end times, and
   ledgered once under the existing assignment CAS. Legacy rows with an
   existing pause are recorded as already credited rather than extended.
   Evidence: `docs/acceptance/readme_feature_readiness_2026-11-01/evidence/campaigns/budget-repair/`.
2. **Evidence was not checkout-verifiable.** The submitted manifest now has 97
   entries, all tracked in Git, including force-added evidence logs. The bundle
   verifies from `git show HEAD:<path>` with zero untracked entries and zero
   hash/byte mismatches. Evidence:
   `docs/acceptance/readme_feature_readiness_2026-11-01/README.md`.

## Post-acceptance correctness repair — stale live wait double subtraction

This finding was made **after** the acceptance above and is appended rather
than folded into the old baseline. The accepted tag
`accepted-local-2026-11-01-90pct` is preserved; the old baseline is **not**
described as unaffected by this defect.

| Item | Value |
|---|---|
| Finding | A legacy budget could carry `paused_seconds` for a completed wait and still keep the same interval in `waiting_since`; effective elapsed subtracted it twice, so 1500 s of real work against a 900 s budget reported ~0 s and was allowed. The legacy retry credit also left the live wait in place. |
| Repaired successor commit | `f1ef414c352f200301dc016ba1f9c3e3e00637b4` |
| Backend tree identity | `c2963fbcdc8e2448ac69fb4d5818c41d10ab2d33` |
| Repair commits | `bec60978b03774f190d4e33d130a7fdf1fe60cd6` (idempotent interval identity) + `019aa1eeba33c24be8171911c8366d96bba2b678` (clear matching live wait; do not double-subtract an already-credited timestamp) |
| Focused verification | **63 tests**: 61 executor tests + both public-route cancellation tests |
| Evidence | `docs/acceptance/evidence/budget_repair_20261101/` |

The repair clears the matching `active_wait`/`waiting_since` on every credit
outcome, ignores a `waiting_since` already present in the credit ledger, and
does not subtract a legacy paused interval twice when there is no live
active-wait identity. A genuinely new wait still records `active_wait`, so it
is still excluded. Genuine active-work exhaustion remains exhausted.

**Scope separation:** the genuine two-hour C2 run executes on its historical
source `414d8add3` / backend tree `715969f01d23`; it is elapsed-waiting and
recovery evidence, **not** verification of this repaired budget code. The
budget repair is verified by the 63 controls above and by the integrated
recovery controls on `c2963fbcdc8e`.

**Recommended launch path:** recent first-use changes after this tree (for
example `8b1abd7e6`, frontend `AssignmentPanel.tsx`) are outside the accepted
budget tree and need their own focused smoke before they become the recommended
launch path. They are not counted as accepted by this record.

## Launcher memory-path handoff (focused repair)

| Item | Value |
|---|---|
| Finding | The acceptance launcher exported `LANCEDB_URI` only. Workspace handlers read `LANCEDB_URI_BASE` and fell back to `./data/atom_memory`, which `_resolve_local_db_path` anchors to `backend/`, silently reusing the repository-shared memory root. |
| Repaired successor | `d8120737e` (launcher + evidence), backend tree `c2963fbcdc8e`, frontend tree `756642ecb165` |
| Fix | Both `LANCEDB_URI` and `LANCEDB_URI_BASE` point at `<world>/data/atom_memory`; no shared memory was copied, deleted or migrated. |
| Path verification | Fresh world log: `Connecting to LanceDB at <world>/data/atom_memory/default_shared`; zero occurrences of the repository-shared path. |
| First-use focused smoke | Current HEAD + repaired launcher on world `first_use_smoke_20261101`: assignments panel loads after login, Demo Assistant selectable, agents page reachable, no page errors, world-owned memory path. Evidence: `docs/acceptance/evidence/first_use_smoke_20261101/`. |

This is a focused smoke of the changed first-use surfaces and the launcher
memory path, not a re-run of the full clean-install/sample job. The previously
accepted clean-install path remains at its recorded source.

## Accepted practical scope

- Complex teaching, conflict/qualification refusals, unfamiliar-data mappings,
  correction while waiting, and active-snapshot retention in two domains.
- Durable waiting, real backend restart, same-assignment resume, cancellation,
  duplicate resume prevention and controlled-effect reconciliation.
- Clean local installation, first-use sample job, production login, artifact
  download/reopen, and ordinary UI teaching.
- Bounded controlled actions with exact payload approval and one-effect
  enforcement.

## Previously accepted live qualification

Separately from this campaign, **one specifically authorized Outlook send** and
**Microsoft read-only ingestion** were previously accepted under their recorded
authorizations. Those qualifications are closed and remain preserved. They are
not evidence of broader live-send reliability.

What remains unqualified is **broader live sending beyond that single authorized
send, autonomous live sending, and connector/recipient breadth**. This campaign
used controlled effects only and did not attempt a second live send.

## Explicit exclusions

- Universal feature reliability is not established.
- Qualified discretionary-model judgment remains failed/unsupported.
- Multi-worker execution and long soak behaviour are not claimed.
- Broader live sending, autonomous live sending, connector breadth and
  recipient delivery beyond the accepted one-use qualification are not claimed.
- Hosted deployment and publication remain deferred.
- The accepted Microsoft read-only and one-use Outlook send qualifications
  remain closed; no second live send was attempted.

## Marketing statement

> **Verified local AI employee workflows covering 90% of the frozen functional
> inventory, including complex teaching, unfamiliar-data work, durable waiting,
> restart/resume, artifacts and bounded controlled actions.**

Separately accepted under their recorded authorizations: **one specifically
authorized Outlook send** and **Microsoft read-only ingestion**. Broader live
sending, autonomous live sending, connector breadth and discretionary model
judgment are not claimed by this statement.

## Preservation

No historical tag was moved. The acceptance tag is a new annotated tag on the
accepted evidence/docs commit. The earlier `local-core-2026-10-30-final`,
conversation-learning, Microsoft read-only and Outlook send records remain
unchanged.
