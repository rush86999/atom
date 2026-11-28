# Durable source registration preparation

The private preparation service uses existing settings, audit and connection encryption. Current owner/manage authority and exact active connection metadata are claimed with the setting write. Competing requests preserve one operation and receiver state; audit failure rolls back both. Replays verify the full stored result against the original audit, not only the request digest. Public projection excludes encrypted receiver state and its commitment.

Python 3.11: 17 preparation controls and 67 affected CI-preservation controls pass (84 total). Four changed-state negatives failed before full result verification and pass after it. Scope is real scratch SQLite and fresh database sessions; no live provider or source UI campaign occurred.

Next: consume this prepared record through the existing `core.outbound_operation_claim` TaskOperationRecord arbiter before provider dispatch. Preserve its operation identity and encrypted receiver value on retries; a dispatching/uncertain operation must not enroll twice. Activation must reconcile the provider result and current connection owner. Route verified callbacks by exact registration/subscription identity and enter the existing intake/worker chain. Legacy global Outlook state and token fallback are not eligible workflow authority.

This checkpoint does not implement provider enrollment, callback routing, renewal, source-selection UI, or their public journey. PR remains draft; no merge or deployment.
