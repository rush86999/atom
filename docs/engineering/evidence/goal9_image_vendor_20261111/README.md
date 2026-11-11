# Goal 9 — provider image usage authority + vendor embedding transports

Date: 2026-11-11
Base: `50a5dffd71bf2cc02198f14965f4f757ac96a095` (union PR840; inherits the
PR837 integration, pricing material, stream usage, and the OpenAI/Jina
embedding admission from the prior slice).
New append-only branch: `codex/agentB-image-vendor-transports-20261111`.
PR843/844 were not touched.

## 1. Provider-side image token accounting (was OPEN)

Admission for an image request is unchanged: no proven pre-dispatch image
bound, so hard_stop refuses and observe admission stays unknown. What changed
is **settlement**:

- when the provider's usage report is complete with a positive input token
  count (OpenAI-compatible prompt tokens / Anthropic-style input tokens, which
  aggregate image tokens), that report is authoritative for the image-bearing
  attempt and settles its exact cost;
- if the report discloses `prompt_tokens_details.image_tokens` /
  `input_tokens_details.image_tokens`, the value must itself be a non-negative
  integer; malformed detail keeps the settlement unknown;
- absent, partial, or zero input usage is **never** treated as an image zero:
  the reservation stays explicit unknown liability;
- a genuinely explicit `0/0` price remains authoritative free;
- textual accounting still replaces inline `data:` image bytes with a marker
  (no base64 token inflation).

Failure-first: on the base, an image request with complete usage was forced to
unknown. The retained negative run (`before/`) shows
`test_observe_image_authoritative_usage_settles_actual` and
`..._image_token_detail_is_consumed` **failing**, while the two unknown twins
(malformed detail, absent usage) pass. After the change all four pass.

## 2. Cohere / Nomic / Voyage embedding transports (was OPEN)

Inventory and action at the SDK edge:

| Provider | SDK surface | Default retries | Action |
|---|---|---|---|
| Cohere | `cohere.AsyncClient` (Fern-based) | SDK default (client accepts `max_retries`) | `max_retries=0` |
| Voyage | `voyageai.Client` | documented default `0`, now explicit | `max_retries=0` |
| Nomic | `nomic.Embedding` (requests-based) | no SDK retry knob / no default retry | none invented; documented |

Chargeable dispatch coverage uses the **existing** ledger/admission:

- the reachable consumer (`LLMService` → `BYOKHandler.generate_embedding(s)`)
  already admits one physical attempt and settles through `begin_llm_usage` /
  `record_llm_usage`; Cohere's `meta.billed_units.input_tokens` is now consumed
  for exact settlement, and absent billed units stay unknown;
- Cohere batch is one physical SDK request/attempt;
- the exported Voyage/Nomic provider classes have **no in-repo consumer**, so
  no second unscoped ledger writer was added inside them; their retry edge is
  fixed/documented here and admission belongs to the consumer boundary when
  they are wired.

Failure-first: `test_cohere_embedding_settles_billed_units` and
`test_vendor_embedding_classes_disable_sdk_retries` fail on the base
(`before/base50-failure-first.log`: 4 failed, 2 passed) and pass here.

## Gate counts (shared bounded gate, scratch SQLite)

| Gate | Result | Log |
|---|---|---|
| embedding vendor controls | **8 passed** | `after/embedding-vendor-controls.log` |
| physical + image accounting | **40 passed** | `after/physical-image-controls.log` |
| final shared gate (spend-window, embedding, physical, structured, pricing, stream, retry-state, atomic/durable/upgrade, CI lane, live feedback factory, feedback, w57, deepseek, six root probes) | **345 passed** | `after/final-shared-gate.log` |

Preserved negatives rerun at the final head: `root_physical_free_image_probe`,
`root_configured_price_material_probe` (6), and
`root_input_only_pricing_compat_probe` all pass, plus the invalid-price,
direct-bound and estimated-flag probes. The earlier 8de withholding and
pricing/stream packets remain unchanged in the tree.

## Boundaries

- Provider-side image **pre-dispatch** accounting remains unknown by design
  (hard_stop refusal); no image-token ceiling is claimed.
- Voyage/Nomic have no in-repo consumer; no speculative admission inside dead
  provider classes.
- PostgreSQL runtime concurrency remains open and was not attempted.
- No live provider/model/pricing/credential/spend/send/deploy; `TESTING=1`,
  explicit synthetic scratch DB/office/data and `SECRET_KEY` before imports.
- Goal 9 is not marked complete from this subset; root owns acceptance/merge.
