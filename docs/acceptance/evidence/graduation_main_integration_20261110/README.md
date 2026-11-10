# Graduation main integration checkpoint (2026-11-10)

Status: focused integrated checkpoint for independent root verification. This is
**not** a full-app, ordinary-UI-journey, live-model-competence or marketing
acceptance claim.

## Commits and source attribution

| Commit | Role |
|---|---|
| `0d5132c2e060a5f2ac338bca143c5e138e607658` | Current main integrated into this branch |
| `8c3f1483ff68f7d4d2ac00b88e6df67604e386d2` | Merge commit; resulting tree `840f142947d6334bbe4c72c2c2815efe8bdcaa6a` exactly matched the root merge-tree preview |
| `f3c284aaee856220d44e6c41e74806542b1f4ffb` | Final backend source: awaited notification, strict policy selectors, rubric-shape validation, Personal regression twin |
| `cef304a18d994c14a770b3df2a02f6cb22a5474a` | Test-fixture and graduation-docs successor; no production change |
| `7be407677a2d66908228c3b9464eabf739dbf372` | Prior frozen packet, preserved byte-for-byte |
| `c37cd3dfd0df247733cf12830aa20d1c4be45639` | Prior graduation successor, preserved |

The merge did not overwrite accepted main scope/wait/feedback/Canvas fixes. The
merge tree is identical to the prior graduation tree for backend and frontend
source at that point; no Office829 imports were added.

Frontend source parity: **0 changed frontend files** between `c37cd3dfd` and the
integrated tree. The prior packet's full `tsc --noEmit --incremental false`
(exit 0) and 90 TrainingPanel/AgentMaturityGuide/SelfDirectedPathwayCard/
Approvals/maturity-api tests remain bound to the identical frontend source in
`docs/acceptance/evidence/graduation_qualification_ui_scope_20261110/`.

## Authoritative root proof

The root independently reran the unchanged 21-case set at frozen backend
`f3c284aa`:

- **21 passed, exit 0, same_source true**
- **15/15 captured runtime source hashes** match `f3c284aa`
- Covers original-10, policy/notification-5, rubric-shape-3 and Personal-3

Files: `root-final21-review.json`, `root-final21-controls.log`,
`root-final21-parity.json`.

## Bounded gates

| Gate | Result |
|---|---|
| Root final 21-case probe at `f3c284aa` | **21 passed**, 15/15 source parity |
| Backend policy/qualification gate (48 qualification + 15 assessment rules + 10 notification) | **73 passed** |
| Local same-source probe reruns (rubric/original10/combined5/Personal3) | **3 + 10 + 5 + 3 passed** (supporting) |
| Candidate fixture corrections | **3 passed** (governance unqualified + supervision authorized/blocked) |
| Full integration selection, final | **316 passed / 7 failed** |
| Full integration selection, initial | **309 passed / 9 failed** |
| Docs source-signature/link check | **PASS** (41 links, 0 missing; 11 source signatures) |
| Frontend | exact source parity; prior tsc exit 0 and 90 UI/API tests reused |

## Failure classification (no green claim)

The initial full gate had 9 failures. Root independently reproduced the exact
main baseline:

- **7 failures are unchanged main baseline** in
  `tests/test_student_training_service.py`; the root main `0d5132c2e` baseline
  is **7 failed / 1 passed**, same_source true. Exact identities:
  1. `TestTrainingProposalCreation::test_create_training_proposal_success`
  2. `TestTrainingSessionLifecycle::test_approve_training_success`
  3. `TestTrainingSessionLifecycle::test_approve_training_with_modifications`
  4. `TestTrainingSessionLifecycle::test_approve_training_proposal_not_found`
  5. `TestTrainingSessionLifecycle::test_approve_training_invalid_status`
  6. `TestTrainingCompletion::test_complete_training_promotes_to_intern`
  7. `TestTrainingCompletion::test_complete_training_confidence_boost`
- **1 supervision old-test intent failure** passed on main but correctly failed
  under the new qualification gate. The fixture now injects the shared
  `commit_qualified_transition` explicitly: authorized → promotes; missing
  receipt → stays SUPERVISED. Production supervision code is unchanged.
- **1 candidate-only governance failure** was not on main and used a
  `SimpleNamespace` without `id`. The fixture now supplies a complete agent id,
  an empty pending-review query, and a non-excepted id for the unqualified
  negative. Production fallback was not added.

Final full selection is therefore **316 pass / 7 fail**, with only the exact
main-baseline student-training identities remaining. No test was deleted,
skipped, xfailed, or given a new global exemption.

## Personal bootstrap path

The root Personal NULL probe passed **3/3** at the integrated source:
actual controlled task/output fixture, raw-NULL supervisor/reviewer, default
agent/evidence, request/review/promotion, foreign and inactive refusals, no
fabricated HITL rows. A permanent regression twin now covers the same path
using the real `ensure_admin_user`/default bootstrap functions.

## Docs follow-through

`docs/agents/graduation.md` and `docs/agents/TRAINING_AND_GRADUATION.md` now
distinguish experience readiness from scoped capability qualification; document
explicit task/output selection, current human review, frozen rubric, exact
policy/source/scope binding, missing/failed/stale states, supported and rejected
owner-policy selectors, every upward writer using the shared gate, and truthful
notification/replay behavior. Stale promotion/HITL examples and method names
were corrected. Historical exams are legacy evidence, not qualification.

Unrestricted autonomy with domain-specific exceptions remains the product
destination. Current maturity does not remove domain/action/access/budget
policy, and AUTONOMOUS is not universal competence.

## Checkout-only gap

The sparse worktree previously lacked existing tracked files
`scripts/acceptance/substantive_assessment_campaign.py`,
`scripts/acceptance/deterministic_assessment_qualification.py` and
`scripts/acceptance/qualification/*.json`, plus `docs/agents/`. These were
checked out from the same Git source via sparse checkout. No product stub,
copy, dependency or new module was created.

## Honest scope

- Scratch SQLite and `TESTING=1` only; no live DB, provider, model, browser,
  external email/notification send, download, deployment, PR or merge to main.
- Controlled mechanism verification, not an ordinary-UI journey or live model
  competence claim.
- No new engine, store, schema, judge, router, lifecycle, CI yaml or goal index.
- Prior frozen packets and negatives remain preserved.
