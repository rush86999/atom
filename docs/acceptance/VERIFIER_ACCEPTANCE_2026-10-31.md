# Verifier acceptance — 2026-10-31

**Status: accepted within the tested scope below. This is not a release,
hosted deployment or universal reliability claim.**

## Accepted source and configuration

| Item | Value |
|---|---|
| Accepted product source | `b7ee7ee2206cde1752b81f7dd3896bab8144f89a` |
| Branch | `codex/employee-execution-readiness` |
| Configuration | local, single worker, SQLite scratch world, controlled outbox |
| Transport | `ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT=1`; no live provider, no real send |
| Autonomy | explicit bounded standing authority (named recipients, 1–20 effect bound, optional expiry) |
| Cost | adapter-declared conservative bounds; hard pre-dispatch reservation; explicit soft-limit path |
| Waiting | durable wait, real backend restart, same-work resume |
| Assessment | human review required; model qualification remains failed |

## Independently confirmed

- **151 evidence entries across 14 manifests** at the accepted snapshot: no
  hash mismatches.
- Browser rerun bound to `b7ee7ee22`; all **five recorded source-file hashes**
  match.
- **5/5 browser checks passed**, including a real backend restart.
- Sales and grants completed with **85** and **4250**.
- Exactly **two controlled effects**, **zero assignment approvals**, and
  **one grant use per job**.
- The nine focused execution-boundary controls independently run by the
  verifier passed: post-effect runtime/parse/timeout/cancellation uncertainty,
  trusted before-effect failure, hard cost refusal, concurrent reservations,
  soft-limit authoring, and wall-time enforcement.

## Supported milestone

**Local, single-worker execution with bounded standing authority, durable
waiting/restart/resume, controlled outbound effects, uncertainty handling and
declared adapter cost bounds.**

## Explicit exclusions

- **Autonomous substantive judgment is not qualified.** The model
  qualification still failed: **17/18 on V1** and **18/19 on V3/post-restart**
  (94.4% / 94.7%), with the stable `Q-021` review and the false `APPROVE` on
  `Q-012` (Amount 0). Human review remains required.
- **Autonomous live sending is not supported.** Only the controlled outbox
  opts into standing authority; live email send remains approval-required.
- **Multi-worker execution and soak behaviour are not claimed.**
- **Universal feature reliability is not claimed.** The separate README breadth
  result is **99/123 (80.5%)** within its own controlled-test scope and is not
  restated as overall application acceptance.

## Preserved tags and failure records

- `local-core-2026-10-30-final` → `da9cc8b12de3639f59cc5b8ea84338c5f507dc6d`
- `conversation-learning-2026-10-30` → `d2b297deb846df548b6cfe6ab5b0bf9724fcad69`

The failed qualification, the earlier failed-closed cloud attempts and the
historical live-connector records are preserved; none were rewritten or merged
into this acceptance.

## Evidence identity

- Canonical browser evidence:
  `docs/acceptance/evidence/durable_assignment_20261031/two-domain-autonomous-journey/`
  (`two-domain.json` source `b7ee7ee22`; 5/5, 2 effects, 0 approvals).
- Execution-boundary controls:
  `.../employee-execution-execution-boundaries/` (81 assignment tests).
- Autonomy controls:
  `.../employee-execution-autonomy-boundaries/`.
- Assessment clarification/approval:
  `.../employee-execution-assessment-clarification/`,
  `.../employee-execution-assessment-approval/`.
- A later duplicate rerun bundle,
  `.../two-domain-autonomous-journey-repaired/`, reproduces the same 5/5 on the
  same source and is supplementary; it does not move the accepted source.

No further repair campaign is indicated by this verification round. No model
campaign, README breadth campaign, deployment, real send, credential change or
connected-system write was performed.
