# Saved graph event registration

Source `df6f3219b` derives canonical subscriptions from registered trigger config (`config.event_subscription`) using the stable node ID. Explicit conflicting projection is refused; removing the last registered trigger clears its projection on the same revision save. Legacy definitions without registered triggers retain their existing behavior.

Twenty controlled public HTTP registration tests passed on Python 3.11. Tests use scratch SQLite connection metadata and temporary workflow catalogs. They do not establish real provider event delivery or web-editor completion. Those remain active work.

The previous pushed head failed the backend CI lane-preservation contract because its newly added test step was missing from the additive ledger/layout. The follow-up registers the exact existing command without changing the immutable baseline or existing step ownership.
