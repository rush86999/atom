# Scoped native source enrollment

Source enrollment reuses the existing TaskOperationRecord claim/CAS engine. The dispatch transition includes current owner, connection and registration claims in one database transaction. The native Outlook adapter uses exact scoped credentials, transmits the prepared receiver state through the existing service, reads back the created subscription, then atomically activates the settings target and its audit. An independent local readback precedes success.

Replay and competing requests create once. Lost confirmation or receipt persistence does not resend. Known provider refusal is effect=none; readback or activation failure is committed_unverified and can reconcile the original receipt without another creation. Complete receipt shape, audit action and enrolled target fields are checked. Provider-error logs preserve status/error class without echoed private values; existing service response shapes remain unchanged.

At source `f375b2798`, the controlled enrollment/preparation/receiver/CI-preservation gate passed 107 controls on Python 3.11. Final successor `6a07eed56` requires the exact requested expiry, including a changed-but-future negative; its 15 native enrollment controls pass. These are scoped selections, not a new combined 108-control run. The unchanged shell matrix was deselected in the combined selection.

[Microsoft documents clientState as write-only/null on GET](https://learn.microsoft.com/en-us/graph/api/resources/subscription?view=graph-rest-1.0). Readback accepts documented null and refuses an explicitly returned mismatch. The actual callback must separately prove delivery of the receiver state; this test packet does not claim that callback is implemented.

Actual SQLite state/operation/audit storage and encrypted synthetic credentials are used; only Graph HTTP transport is doubled. No application live-provider campaign, PostgreSQL/multi-worker qualification, merge or deployment occurred.

Still open: authenticated setup API, exact registered callback routing and content enrichment, recovery of uncertain enrollment from verified provider evidence, renewal/token maintenance and days-long behavior, ordinary source UI and browser journey, and another domain source through the same mechanisms. Legacy global Outlook token/state fallbacks are not workflow authority.
