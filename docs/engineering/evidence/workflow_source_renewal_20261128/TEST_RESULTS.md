# Controlled native source renewal

Executed source: `82b1af399547999098573a60e9e4f650c0505520`. Python3.11 final gate:

```text
= 302 passed, 625 deselected, 83 warnings, 18 subtests passed in 221.50s (0:03:41) =
```

The wrapper records the exact command and verifies all12 selected source/test/CI hashes are unchanged across the run. Git objects at the executed source match those hashes. The command is the expanded event CI selection plus CI preservation; the unchanged625 real_gate_shell cases are deselected locally. Source files are frozen during this final run.

Coverage: exact native PATCH and readback; original enrollment proof preserved; durable pending lease; actor/connection/encrypted-grant/document claim before dispatch; peer actor/target/original-receipt races; one PATCH under competition; timeout and wrong readback GET-only reconciliation; audit/receipt rollback; wrong current lease/audit/receipt/scope refusal; confirmed4xx refusal; strict server clock; changed credentials retain uncertainty; independent fresh-process GET-only recovery; renewed anonymous callback through the real engine to one durable scoped notification. Existing source/credential/event/worker/CI controls remain included.

Current lease, audit and successful TaskOperationRecord receipt commit atomically through the existing transition_effect hook. Full current documents remain audit-bound; no renewal fields are stripped out to make old audit digests pass. Enrollment replay and callback consumers require fresh local lease proof before using renewed expiry. Source ids, preparation, original request/receipt and receiver state remain unchanged.

## Provenance and limits

Graph HTTP and authentication transport are controlled; authority rows, SQLite, audit, operation ledger, graph execution and notification are real scratch implementations. No live application model/provider, credential campaign, deployment or merge. The authorized development CLI request is disclosed below. Python3.14, PostgreSQL/soak, multi-worker and full-main browser qualification are not claimed. No new schema, queue or runner. This callable is not scheduled yet; proactive token/subscription reauthorization, lifecycle events, missed-event delta recovery and days-offline operation remain open. Whole-app completion remains open.

Intermediate logs retain original bytes from uncommitted harness snapshots: the first had an incompatible test-clock isinstance check; the second injected a competing SQLite writer after acquiring the operation write lock. They are disclosed harness failures, not product-baseline regressions or final-source results. Clock semantics and the before-claim race seam were corrected. A final review added a real original-enrollment-proof race control. These logs are not claimed as exact-source negative baselines.

One no-tools OpenCode Go DeepSeek proposal informed the implementation. Root corrected its unsupported Graph data= keyword, incomplete audit projection, callback consumers and failure handling. CLI reported cost0; no paid fallback. The free endpoint returned429 and was not retried. No proposed code was self-accepted.

References: [Graph renewal](https://learn.microsoft.com/en-us/graph/api/subscription-update?view=graph-rest-1.0) and [lifecycle guidance](https://learn.microsoft.com/en-us/graph/change-notifications-lifecycle-events). Token refresh alone does not certify subscription continuity; one PATCH can renew and reauthorize, while missing notifications require separate recovery.
