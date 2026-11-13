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

Two upstreams are supported:

| `--live-upstream-url` | transport | credential |
| --- | --- | --- |
| `http://127.0.0.1:<port>/v1` | `synthetic_loopback` | none |
| `https://opencode.ai/zen/v1` | `trusted_live` | `--live-credential-stdin` |

The trusted live destination is fixed. Any other scheme, host, port, path,
query, fragment or userinfo is refused before dispatch. No redirect is
followed, no request is retried, and only `chat/completions` is forwarded.

## What the live transport guarantees

- **Caller-supplied credential only.** The driver reads the key from operator
  stdin (`--live-credential-stdin`) and writes it once to the relay process's
  stdin. It is never placed in argv, an environment variable, the sandboxed
  server, a file, a log or evidence. The relay does not read the environment,
  `.env`, `auth.json` or any other auth file, and there is no fallback path that
  could discover one. A synthetic loopback upstream refuses a key outright.
- **One pinned route.** `opencode-go:deepseek-v4.1-flash`. The relay refuses
  any other model identifier before dispatch, the static provider catalog
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
- **One physical attempt.** `follow_redirects=False` and no retry loop. A 3xx
  is returned as a 3xx and a 5xx as a 5xx; either is one counted call.
- **Metadata-only ledger.** Entries carry sequence, timestamp, duration,
  operation, status, requested/served model, finish reason, usage counters,
  byte counts, cost and a response hash. Prompt/completion content, response
  bodies and request headers (including the credential) are never written to
  the ledger or the relay log.
- **No whole-episode retry.** One episode, one relay process. Budget exhaustion
  is recorded as `failed_budget`, not retried until it passes.
- **Synthetic invoice only.** The lane asserts the fixture's expected total,
  PO id and invoice id; the live model never sees a real customer document.

## Why it exists

A live model may word the invoice question differently, may retain instead of
ask, or may ask without the invoice. That is a legitimate negative and must be
recorded as one. The lane therefore asserts the deterministic production facts
(partial upload accepted under its own document identity, question stays open,
no reconciliation; complete upload under a distinct identity; exactly one
applied `invoice.reconcile` of `140.25`; assignment completed; result visible
after reload) and treats model prose as evidence, not as a pass criterion.

## Operator command: synthetic upstream (no external call)

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
metadata-only), the requested/served pin, totals, caps, and:

```
live.live_upstream_enabled: false
live.upstream_kind: synthetic_loopback
live.credential_source: none: the relay holds no credential ...
live.budget.refusals.model_not_pinned: 0   # no other route was even attempted
live.episodes: 1
```

## Operator command: real DeepSeek Flash transport (manual only)

This is the one command that spends money. Do not run it in CI, and do not
pre-seed the key in an environment variable, `backend/.env` or an auth file.
The key is read without echo and exists only on the pipe into the driver, then
on the relay's stdin:

```bash
# Read the key without echo; it never enters argv or the environment.
read -rs ATOM_LIVE_KEY; printf '\n'

# Fresh world + fresh out dir. The relay is the only process with the key.
printf '%s\n' "$ATOM_LIVE_KEY" | \
ATOM_LIVE_REPLAY_ACK=spend \
backend/venv314/bin/python scripts/acceptance/browser_invoice_partial_evidence.py \
  --execute --live-flash \
  --live-upstream-url https://opencode.ai/zen/v1 \
  --live-credential-stdin \
  --relay-port 8117 \
  --world browser_invoice_partial_live_$(date +%Y%m%d_%H%M%S) \
  --out /tmp/invoice-live-replay \
  --backend-port 8037 --frontend-port 3137

unset ATOM_LIVE_KEY
```

The defaults are deliberately small: `--max-model-calls 12`,
`--max-spend-usd 0.50`, `--max-output-tokens 1200`,
`--live-call-timeout-s 60`, `--max-wall-clock-s 1800`. Tighten or loosen them
on the command line; they are reserved before each physical call.

For this mode `scenario.json` records:

```
live.live_upstream_enabled: true
live.upstream_kind: trusted_live
live.credential_seam: operator_stdin
live.credential_present: true
live.credential_source: operator-supplied on stdin to the relay process only ...
live.secrets_recorded: false
live.model_content_recorded: false
live.credential_fields_recorded: false
```

and the same `relay_ledger` entries as the synthetic lane, with no content and
no credential fields. If the relay cannot start (busy port, malformed key,
non-fixed destination), the lane fails closed rather than falling back to the
shim or to a stored credential.

## Notes for future changes

`live_model_relay.validate_upstream_base_url(..., allow_live=True)` is the
single destination gate; `HttpUpstream` is the single credential consumer. Any
new provider route must be added there deliberately (and to the pin/refusal
tests), never as an implicit fallback. The driver's refusal matrix, caps, pin
and assertions apply to both upstream kinds.
