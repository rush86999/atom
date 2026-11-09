# Mobile offline queue preservation — controlled checkpoint

Source11be7eb1c repairs the existing OfflineSyncService and PendingActionsList. Queue writers serialize within one JavaScript runtime. Checked queue writes are the acknowledgement boundary; metadata projections cannot revoke them. Quota is rebuilt from the retained queue payload budget, with a separate metadata key in the existing storage instance. No new queue, storage engine or schema migration was introduced.

Unsent/failed work survives maintenance, cache clearing, retry exhaustion and fourteen simulated offline days. Corrupt bytes are retained rather than reset. Typed UI commands persist retries, priority and deletion from fresh rows; in-flight edits refuse, and removed/stale material cannot dispatch. Failed/skipped/cancelled cycles are non-success, and unreadable work is not shown as All Caught Up. Existing cases are retained with explicit corrections to destructive and false-success expectations.

Evidence: original five losses fail at the frozen predecessor; old-UI composite has two failures and a valid delete twin; load-truth has one failure/four valid; corrected queue-key claim/caching has two failures/eight valid; projection boundary has four failures/ten valid. Final17-file selection passes743/743, no skips. Full mobile compiler still exits2 with409diagnostics.

Raw capture source was dirty. Every captured input file is bound to an exact Git ref or an explicit reconstruction whose bytes match its captured digest. Reconstructions are minimal validated edits, not regenerated historical logs or silently changed runtime attribution. The final positive247source-file hashes match frozen11be7eb1c. A prior claim probe targeted the sync-state projection rather than the queue write; it is excluded from claim evidence.

The bounded public-source Flash review was independently adjudicated. Metadata/quota findings were reproduced and repaired; incorrect call-graph assumptions and automatic retries of exhausted work were rejected. Research pattern: https://github.com/DirtyHairy/async-mutex — asynchronous exclusive execution and release on either promise outcome. No new dependency was required.

Open: production initialization/current-session ownership, interrupted claims and uncertain-effect replay, native encrypted migration/storage, JSON-valid malformed-row qualification, physical device/network operations and a complete mobile build/journey. Fake-clock14days is not real elapsed soak. No app model/provider/account, native permission, business effect, deployment or historical score change.
