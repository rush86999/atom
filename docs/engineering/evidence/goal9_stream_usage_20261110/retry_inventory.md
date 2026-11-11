# Physical-request retry inventory (caller map)

Read-only audit at the current PR837 head. One admitted handler attempt is one
HTTP request; this map records every other construction that can retry
transparently, with the concrete caller trace.

| Surface | Construction / call | Retry configuration | Charge/admission today | Status |
|---|---|---|---|---|
| BYOK handler LLM clients (lux, ollama, provider loop, registered-local, sync+async) | `byok_handler.py` 7 sites | `max_retries=_SDK_MAX_RETRIES = 0` | `begin_llm_usage` per physical attempt (stream/chat/ordinary/structured) | closed |
| Structured instructor | `_create_kwargs["max_retries"] = 0` (`byok_handler.py`) | explicit 0 | same per-attempt admission/settlement | closed |
| OpenAI embeddings | `core/llm/embedding/providers.py` `AsyncOpenAI(api_key=...)` | SDK default (2) | **no TokenUsage admission/settlement in the embedding provider path** | OPEN — needs an embedding charge contract before a retry change is meaningful |
| Jina embeddings | `core/llm/embedding/providers.py` `AsyncOpenAI(api_key=..., base_url=...)` | SDK default (2) | same as above | OPEN |
| Cohere / Voyage / Nomic embeddings | same module, provider-specific HTTP clients | provider/client-specific | same | OPEN (not audited to call level yet) |
| `core/llm/registry/fetchers.py`, `curated_overrides.py`, `provider_auto_discovery.py` | pricing/catalog metadata fetchers | n/a (not completion transport) | n/a | out of scope |
| Integrations using the handler | via `BYOKHandler` clients | inherits 0 | inherits per-attempt admission | closed |

## Why the embedding rows stay open

The embedding providers price per 1M tokens (`cost_per_1m_tokens`) but the
provider classes call `client.embeddings.create` directly and no
`TokenUsage`/`begin_llm_usage` producer exists on that path. Setting
`max_retries=0` there alone would reduce hidden requests without creating the
missing durable charge/attestation contract, so it is **not** changed under a
blanket SDK edit. The bounded next step is an embedding admission/settlement
slice (same ledger, same attempt identity) and then the retry configuration.

No blanket SDK change was made; this map is the prerequisite for a traced
repair.
