# Assessment exact-content approval — route-level verification

This bundle closes the remaining assessment safety question at the boundary a
downstream consumer actually uses:

    assess -> unreviewed decisions refused -> approve the exact execution ->
    decisions allowed -> change one reviewed field with the stored hash
    untouched -> authorization, decisions and re-approval refuse.

The storage, approval, compare-and-swap and refusal paths are the real ones.
The structured review response is a controlled fixture; this is not a new
model-quality campaign and does not change the failed qualification verdict.

## Controls

| Control | Assertion |
|---|---|
| Unreviewed recommendation | `GET /capability/decisions` is refused with `review_required`; the assess response is `authorized=false`, `rendered=""` |
| Exact approval | `POST /capability/assess/{execution_id}/approve` authorizes only that execution at the captured source/policy/canvas revisions |
| Downstream use | after approval, `GET /capability/decisions` returns the canonical decision map |
| Content drift | changing one decision while leaving `assessment_content_sha256` untouched makes `GET /capability/authorization` report `content_drift`; decisions and re-approval refuse |
| Qualification gate | a confident `APPROVE` on a gap input fails `safe_abstention` and the judgment is `failed` (`unsupported_approval`) |
| Concurrent approval | two simultaneous approvals yield one transition; repeat approval is idempotent (service tests) |
| Stale session | a stale approval cannot overwrite a newer canvas; reassessment between review and approval requires fresh review (service tests) |

The default `ATOM_ASSESSMENT_REVIEW_POLICY=always` requires human review even
when the model reports no uncertainty. `scoped` autonomy requires both a
qualified registry entry and the owner's `canvas_assessment` policy.

## Result

`assessment-approval.log`: **106 passed**, 0 failed.

```
tests/test_canvas_assessment_routes.py
tests/test_canvas_assessment_concurrency.py
tests/test_canvas_assessment_authorization.py
tests/test_assessment_judge.py
tests/test_canvas_capability_service.py
tests/test_review_result.py
tests/test_review_contract.py
```

## Reproduce

```bash
cd backend
TESTING=1 PYTHONPATH=<pyarrow-overlay>:<repo>:<repo>/backend \
  <python> -m pytest -q \
  tests/test_canvas_assessment_routes.py \
  tests/test_canvas_assessment_concurrency.py \
  tests/test_canvas_assessment_authorization.py \
  tests/test_assessment_judge.py \
  tests/test_canvas_capability_service.py \
  tests/test_review_result.py \
  tests/test_review_contract.py
```

## Scope

- controlled structured-review fixture, not a model-quality result;
- one SQLite store; the route test uses a TestClient, the concurrency tests use
  two real sessions;
- no provider contact and no deployment;
- the previously recorded qualification failure (`Q-012`, `Q-021`) stands.
