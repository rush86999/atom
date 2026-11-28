# Native renewal adapter checkpoint

Python3.11: 40 passed, 2 warnings, 19.91s. New native adapter protocol controls plus all17 existing enrollment controls. Graph transport alone is doubled; scratch SQLite used by enrollment tests. No live provider call.

The adapter freezes a new71-hour expiry independently of the original enrollment plan, PATCHes only the escaped original subscription id, sends expiry only, and requires exact renewed id/resource/changeType/callback/expiry and receiver-state readback. It preserves ambiguous transport failures and rejects invalid material before dispatch. Malformed receipts cannot certify a renewal. Existing enrollment verification remains bound to its original expiry.

This is an internal protocol checkpoint, not an activated renewal service. Durable pending intent, authority CAS, receipt/audit atomicity, uncertain replay reconciliation, current-lease registration proof, worker integration, reauthorization, missed-event recovery and days-long qualification remain open. The new methods have no production caller yet. No release, permission or scheduling gate changed.

Reference: Microsoft Graph [update subscription](https://learn.microsoft.com/en-us/graph/api/subscription-update?view=graph-rest-1.0). The provider documents PATCH of the existing subscription and changing only supplied fields. Existing Microsoft365Service request transport is reused directly; its legacy renewal wrapper catches ambiguous exceptions and logs raw exception text, so this adapter preserves the transport exception for the durable arbiter instead.

Command from repository root:

```sh
TESTING=1 DATABASE_URL=sqlite:////private/tmp/atom-renewal-adapter-final-20261128.db SECRET_KEY=synthetic-renewal-test-key PYTHONPATH="$PWD/backend" /usr/local/bin/python3.11 -m pytest -p no:randomly backend/tests/test_workflow_event_source_renewal_adapter.py backend/tests/test_workflow_event_source_enrollment.py -q --tb=short --timeout=120 --timeout-method=thread
```

The restored-checkout baseline additionally passed25 atomic-transition/enrollment controls before editing. That baseline is a tool-output summary, not this retained final log. Python3.14 and hosted checks for this checkpoint are not claimed.
