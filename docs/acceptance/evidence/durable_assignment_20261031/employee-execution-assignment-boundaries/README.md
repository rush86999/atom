# Practical assignment — the five open boundaries as executable controls

The practical gate passed retrieval/calculation/artifact/approval/durable
reopen. Its report left five boundaries open. Each now has a named executable
control that passes; this bundle records the run.

**Level of evidence:** executor and route boundaries against the real
assignment services and a scratch store. These are not browser-journey reruns;
the browser journey remains the evidence for the flow itself.

| Boundary | Control | What it asserts |
|---|---|---|
| Process restart while waiting | `test_crash_after_wake_before_advance_recovers` | work is recovered after a crash between wake and advance; no lost step |
| Changed-revision invalidation | `test_stale_task_revision_prevents_dispatch` | a stale task revision cannot dispatch work |
| Ambiguity | `test_ambiguous_mapping_correction_requires_source_identity` | an ambiguous mapping correction is refused without source identity |
| Cancellation | `test_cancellation_prevents_unstarted_effect`, `test_approval_after_cancellation_is_refused`, `test_cancelled_assignment_cannot_be_approved` | a cancelled assignment cannot start an effect or be approved afterwards |
| Duplicate resume | `test_two_concurrent_resume_requests_dispatch_once`, `test_external_reply_matches_exact_correlation_once` | two concurrent resumes dispatch once; a duplicate correlated reply is idempotent |

## Result

`boundaries.log`: **8 passed**, 54 deselected, 0 failed.

```
TESTS=(
  test_cancellation_prevents_unstarted_effect
  test_external_reply_matches_exact_correlation_once
  test_stale_task_revision_prevents_dispatch
  test_crash_after_wake_before_advance_recovers
  test_approval_after_cancellation_is_refused
  test_two_concurrent_resume_requests_dispatch_once
  test_ambiguous_mapping_correction_requires_source_identity
  test_cancelled_assignment_cannot_be_approved
)
pytest tests/test_assignment_executor.py tests/test_assignment_routes.py -v -k "..."
```

## Not claimed

- A browser-level rerun of these five boundaries on the current candidate.
- Multi-worker or multi-day soak behaviour.
- Real-provider send (controlled transport only).
