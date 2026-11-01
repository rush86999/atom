# Final local-app acceptance — 2026-11-01

**Status: accepted by the independent verifier within the documented supported
scope.** This record is a post-acceptance bookmark; the acceptance itself is
bound to the evidence head below.

## Binding

| Item | Value |
|---|---|
| Product source | `a49b854ce660` |
| Evidence/documentation head | `d3e8ba961` |
| Frontend build | `qEeLBEVZSyQjyn3v-Wnjh` |
| Configuration | local single-worker app, `core` profile, controlled outbox; one authorized Microsoft read-only qualification and one authorized one-use Outlook send |
| Qualification world | `live_qualification_20261101` (isolated) |

The one-use send qualifies on product `0aa6105e4872`; `a49b854ce660` adds the
rejection boundary for oversized executable inputs and the connector
entry-point evidence. Evidence head `d3e8ba961` also carries the route-level
boundary test and the omitted-input compatibility fix; it does not change the
accepted scope. The accepted send was not repeated.

## Accepted scope

- Local app, deterministic taught-policy path, canvas/workbook behavior,
  durable execution and restart/recovery.
- Live Microsoft read-only connector entry point: `email_ingest_message` via
  the product API refreshed the genuine HARSLE Outlook attachment and a fresh
  assignment returned **216700.00** across 8 rows.
- One live Outlook send: exact body binding, provider acceptance, exactly one
  Sent Items row, exhausted 1/1 grant, restart terminal and no second effect.

Evidence: `docs/acceptance/evidence/live_qualification_20261101/` (30 files,
manifest hash-verified) and the accepted local bundles (27 manifests / 248
entries).

## Explicitly not claimed

- Unrestricted discretionary-model judgment; only the deterministic
  taught-policy path is qualified.
- Recipient inbox delivery; provider acceptance and Sent Items reconciliation
  are the send claims.
- Unrelated connectors, multi-worker/soak, universal Excel compatibility, image
  or chart understanding.
- Hosted deployment and publication remain deferred, not completion gates.

## Change rule

No further acceptance campaign is required unless implementation or the
supported scope changes. Do not repeat the accepted live send, model campaign
or broad local campaign for this binding.
