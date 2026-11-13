# Opt-in invoice replay lane (`--live-flash`)

The signed-in invoice driver
(`scripts/acceptance/browser_invoice_partial_evidence.py`) defaults to the
scripted episode: authored completions from
`backend/scripts/orchestration_acceptance/provider_shim.py`, the existing
assertions, and `preflight.json`/`scenario.json` shapes that must not change.

`--live-flash` is a **second, opt-in** mode. It keeps the same signed-in
browser episode, the same synthetic invoice fixture
(`PO-TRIGGER-63`, `INV-TRIGGER-91`, total `140.25`), the same scratch world, and
the same deterministic production facts, and replaces the shim with a loopback
relay that forwards `chat/completions` to an OpenAI-compatible upstream.

## What this revision does NOT do

This revision is the **wiring** step, and its evidence says so:

- **No credential read, no live dispatch.** The relay
  (`backend/scripts/orchestration_acceptance/live_model_relay.py`) never reads
  the environment, holds no credential, and refuses any upstream that is not a
  loopback `http` endpoint. `LIVE_UPSTREAM_ENABLED = False`. The sandboxed
  server receives only the run-scoped placeholder
  (`relay-local-not-a-secret`) through the product's existing
  `OPENCODE_BASE_URL` / `OPENCODE_API_KEY` adapter seam.
- **One pinned route.** `opencode-go:deepseek-v4.1-flash`. The relay refuses any
  other model identifier before dispatch, the static provider catalog
  advertises only that pair, and the driver asserts served == requested.
- **Prices are not guessed.** Input/output per-1M prices come from
  `core.llm.opencode_catalog.OPCODE_KNOWN_PRICES`. If the pinned model has no
  catalog price, the lane refuses to start.
- **Bounded before dispatch.** A call slot plus the worst-case cost
  (`request bytes` priced as an upper bound on prompt tokens, plus
  `--max-output-tokens` at the output price) is reserved under the relay's lock
  *before* the upstream socket is opened. Once `--max-model-calls` or
  `--max-spend-usd` cannot fit, the relay answers `429`/`402` and no call is
  made. Settlement uses measured `usage`; if the upstream omits `usage`, the
  reservation stays charged (`usage_unknown`), so spend can only be
  over-estimated.
- **No whole-episode retry.** One episode, one relay process. Budget exhaustion
  is recorded as `failed_budget`, not retried until it passes.

## Why it exists

A live model may word the invoice question differently, may retain instead of
ask, or may ask without the invoice. That is a legitimate negative and must be
recorded as one. The lane therefore asserts the deterministic production facts
(partial upload accepted under its own document identity, question stays open,
no reconciliation; complete upload under a distinct identity; exactly one
applied `invoice.reconcile` of `140.25`; assignment completed; result visible
after reload) and treats model prose as evidence, not as a pass criterion.

## Operator command (manual, synthetic upstream)

CI never runs this lane. The dry run below uses the **existing authored shim**
as the relay's upstream, so it exercises the relay, the sandbox profile, the
provider adapter seam and every driver assertion without a single external
call:

```bash
# 1. Synthetic upstream: the authored shim on its usual port.
backend/venv314/bin/python \
  backend/scripts/orchestration_acceptance/provider_shim.py \
  --port 8107 \
  --script scripts/acceptance/fixtures/browser_invoice_partial_evidence_shim.json

# 2. The replay lane (fresh world + fresh out dir; never a live DB).
ATOM_LIVE_REPLAY_ACK=spend \
backend/venv314/bin/python scripts/acceptance/browser_invoice_partial_evidence.py \
  --execute --live-flash \
  --live-upstream-url http://127.0.0.1:8107/v1 \
  --relay-port 8117 \
  --world browser_invoice_partial_live_$(date +%Y%m%d_%H%M%S) \
  --out /tmp/invoice-live-replay \
  --backend-port 8037 --frontend-port 3137
```

`scenario.json` records `mode: live_flash`, the relay ledger (bounded,
response heads redacted), the requested/served pin, totals, caps, and:

```
live.live_upstream_enabled: false
live.upstream_kind: synthetic_loopback
live.credential_source: none: the relay holds no credential ...
live.budget.refusals.model_not_pinned: 0   # no other route was even attempted
live.episodes: 1
```

The labels state the same thing in prose: the transport is relayed, the served
completion in THIS revision is synthetic, and no live provider call, credential,
account, send or spend occurred.

## Enabling a real upstream later

`live_model_relay.validate_upstream_base_url` is the single gate. Enabling live
dispatch is one deliberate change there plus a credential seam in
`HttpUpstream` (read the operator's key at the relay boundary only, never in
the sandboxed server, never in the ledger), and flipping
`LIVE_UPSTREAM_ENABLED`. The driver's refusal matrix, the caps, the pin and the
assertions do not change.
