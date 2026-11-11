# Goal 9 — embedding physical attempts + image accounting (follow-through)

Date: 2026-11-10
Base: `af4436c35f7c82fb6f360ad315a0dffafa3a9c6f` (PR837 integration
`merge: advance PR837 to current main be8bb29 (UI838) with additive union`).
New append-only branch from that base; PR837's branch was not pushed to or
rebased. Worktree reused in place (no copy; disk ~4 GiB).

This closes the two OPEN rows from the physical retry inventory.

## 1. Embedding admission/settlement (was OPEN)

The real cloud embedding consumer is `LLMService.generate_embedding(s)` →
`BYOKHandler.generate_embedding(s)`. That dispatch called
`client.embeddings.create` directly with the SDK's default retries and only an
in-memory chars/4 estimate — no durable pre-dispatch admission, no exact
settlement.

Contract now (same adapter/ledger, no second accounting engine):

- one physical SDK call = one server-owned attempt:
  `embedding-<uuid>:1`, provider/model/workspace/tenant bound;
- `_admit_embedding_attempt` uses the existing `begin_llm_usage` with an
  input-only quantity (`output_token_quantity=0`): an absent output rate is
  genuinely unused basis, not an invented price; missing/invalid input pricing
  still refuses under hard_stop before the SDK call;
- `_settle_embedding_response` records provider usage (`prompt_tokens`/
  `input_tokens`) exactly when present, with cost from the configured
  input-only price; absent usage stays explicit UNKNOWN with the reservation
  retained (never fabricated zero); a genuine numeric-zero bound stays free;
- batch embedding is ONE physical attempt (one admission/settlement) because
  it is one SDK request;
- `max_retries=0` at the SDK edge for the exported OpenAI/Jina embedding
  provider classes as well as the handler clients (already 0). The durable
  admission owns retry/attempt identity; no blanket SDK retry change.

Failure-first: `before/embedding-failure-first.log` shows **5 failed** on the
base (no ledger rows, no hard-stop refusal, provider classes without
`max_retries`). After: **5 passed**.

## 2. Provider image token accounting (was OPEN)

No fabricated image accounting:

- inline `data:` image bytes are replaced by `<inline-image>` before bounding;
  a 1 MiB base64 image produces the same text bound as a 2-byte one
  (`after/physical-image-controls.log`);
- a provider usage report for an image request in observe mode settles
  explicit UNKNOWN (`cost None`, `pricing unknown`, reservation retained), not
  `$0`;
- paid image under hard_stop still refuses before dispatch; a genuine explicit
  `0/0` price still keeps the free route. The existing physical controls and
  root's free-image probe are unchanged and rerun at this head.

## Preserved negatives (rerun at this head)

- `root_physical_free_image_probe.py` — pass
- `root_configured_price_material_probe.py` — 6/6 pass (6 invalid/material
  twins + explicit free/priced)
- `root_input_only_pricing_compat_probe.py` — pass (input-only 1.0)
- `root_atomic_invalid_price_probe.py`, `root_atomic_direct_bound_probe.py`,
  `root_atomic_estimated_flag_probe.py` — pass
- 8de withholding evidence and the pricing-compat/stream packets remain in
  the tree (`docs/engineering/evidence/goal9_pricing_compat_20261110`,
  `goal9_stream_usage_20261110`); this packet does not relabel them.

## Gates (shared bounded gate, scratch SQLite)

| Gate | Result | Log |
|---|---|---|
| embedding controls | **5 passed** | `after/embedding-controls.log` |
| physical + image accounting | **37 passed** | `after/physical-image-controls.log` |
| final shared bounded gate (embedding/physical/structured/pricing/stream + retry-state + atomic/durable/upgrade + CI lane + live feedback factory + feedback + w57 + deepseek + six root probes) | **336 passed** | `after/final-shared-gate.log` |

CI: the additive `Run per-physical-attempt reservation controls` step now also
runs the embedding suite; the immutable baseline and all union steps are
preserved (CI-lane contract inside the 336).

## Boundaries

- Provider-side image token accounting is still UNKNOWN by design; no
  authoritative image-token ceiling is claimed.
- Cohere/Nomic/Voyage embedding transports use non-SDK clients and were not
  changed; OpenAI/Jina SDK edges are covered.
- No live provider/model/pricing fetch/credential/spend/send/deploy; scratch
  DB only (`TESTING=1`, synthetic `SECRET_KEY`).
- Goal 9 is not marked complete from this subset; root owns acceptance/merge.
