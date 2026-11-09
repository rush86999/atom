# Shared web credential identity

Frozen source: 22a6c77725575f7a17faebdfcd49c56a5a89eb6a.
Both existing NextAuth credential providers now share the canonical backend
login and exact issued-bearer /me readback. Parallel JS SQL/admin enrichment,
email-shaped super-admin inference and tenant-hint re-login are removed.
The single10s deadline covers dispatch and parsing; no credential retry.
Existing 2FA challenge codes remain, and expired late bodies are not adopted.

106 source-frozen frontend controls pass and TypeScript is clean. The frontend
artifact is derived from the retained successful Jest JSON without console
output; negative observations are sanitized, not a raw runtime trace. Both
original callback files retain their15 and11 existing static case names.
The earlier web_session_logout_identity_e173791ef packet remains at its original
source, with101 backend and93 frontend checks; these overlapping counts must
not be summed. No new backend runtime changes occur in this successor.

Existing API-first login UI, OAuth database paths, browser credential reset,
already-open connection revocation, PostgreSQL/soak and general app readiness
are separate boundaries. No live model/provider/account/email/deployment action
was performed. Main web first; mobile UI last.
