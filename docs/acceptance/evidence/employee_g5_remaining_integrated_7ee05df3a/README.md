# Employee G5 remaining behaviors — integrated source 7ee05df3a

Runtime candidate: `7ee05df3ad54beb7581b7055d472e66caf93c572`
(branch `codex/brennan-full-app-20261102`). Both campaigns ran with
`source_id=7ee05df3ad54`, `dirty=false`. The browser world was
`g5-ui-integrated-final`; the API campaign used its own marked scratch world.

This is one integrated source with both evidence levels in one bundle:

- **ordinary Assignments UI** — explicit quote-document artifact journey;
- **normal application backend/API** — independent branch progress during a
  real durable wait, selective branch re-evaluation with retained receipts,
  cancellation plus late-response refusal, and controlled
  lost-confirmation/restart/reconciliation with no resend.

The material employee decisions in the earlier exact-run reconciliation
episode remain served-model choices. The artifact request here is an explicit
user deliverable control, and the branch addition is a deterministic versioned
plan patch. Those distinctions are stated rather than merged.

## UI artifact journey (10/10 checks)

Exact run: `bfed4e47-2570-4704-9aac-24a30598375e`.

- Uploaded `price-book.xlsx` through the page, entered objective
  "Prepare the customer quote document", selected a document deliverable and
  the authorized source, and supplied the quote line items.
- Captured the actual `POST /api/assignments` request/response and returned
  run id; clicked that exact summary, not a pre-mounted detail.
- Assignment completed with the `artifact_verified` criterion met.
- Downloaded the artifact through the normal route. Sha256
  `8605b8a82265ef7670936846244938a9d9d3e8305eead6704fea32c3112411ea`
  matches the recorded deliverable.
- DOCX text contains `370.00`, `price-book.xlsx`, and both lines.

## Normal-app API campaign (18/18 checks)

| Run | Purpose |
| --- | --- |
| `142e523f-664b-42d7-b127-5a364cc3684a` | requested document artifact (`370.00`) |
| `72076abf-ffb4-42f6-8a5a-6d602108df12` | wait + independent branches, selective retention, cancellation/late reply |
| `b1cd916b-232e-4d8f-ac81-94146490c0ff` | controlled uncertain effect, restart, reconciliation, no resend |

Branch evidence: `branch-a` changed from operation
`bbb0f65d-6532-4c93-8b5f-cea08f177cbb` to
`4a19acb1-2fa0-4305-b99c-608d07e1532f` with `prior_result_count=1`;
`branch-b` retained operation
`78c5fc28-c35d-4832-a496-4d19570cb77d`, value `750`, and summary; the
waiting operation `17e27163-a676-4d54-9392-d706417a29e9` stayed unchanged.
Cancellation returned 409 for the late reply and preserved the branch
receipts.

Uncertainty evidence: original operation
`69d2d329-34c8-4b61-8c46-6d375f0adab9` survived restart, reconciliation
applied to the same operation, the assignment completed, and the outbox still
contains exactly one effect with sha256
`46f37510fc3dc914c1988fdfaebc77d9c066cfb7987ef5db1c623f602fbd6aaf`
before and after.

## Tests

`focused-tests.log`: **305 passed** in 65.79 seconds on source `7ee05df3a`
across assignment routes/executor, employee proposal/adaptation/work requests,
retained authorized scope, prerequisite eligibility, patch invariants, proof
binding, campaign guard, document freshness, and the prior verifier probes.

## Boundaries

- No live provider, credential, consent, send, spend or deployment authority.
- Artifact request is explicit through the existing deliverable control; this
  bundle does not claim served-model artifact selection.
- Independent branch addition is a deterministic versioned plan patch; this
  bundle does not claim model branch discovery.
- The browser exact-run reconciliation episode and its model choices remain
  the earlier reviewed `employee_g5_ui_exact_continuation_ec2d9dbf0` bundle.
- Historical 111/123, previous tags/sources, planner 5/5, goal router 1/2 and
  alignment gap 3.0 are unchanged.
