# Verifier acceptance — 2026-11-01

**Status: accepted within the documented local and controlled-provider scope.
This is not a release, hosted deployment, publication or universal reliability
claim.**

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
