# Structured model requests — exact route and endpoint contracts

**Bounded offline result: 97 focused tests and 11 existing quota-routing
controls passed independently**, with network access denied. Product source:
`73953836890d1a94f532845c50961647e302bc5c`; release CI source:
`86abf6839`. The three qualified product/test file hashes are retained in the
[filtered result](evidence/structured_wire_contracts_20261117/result.json).
This is not live provider or model-quality acceptance, and does not repair or
qualify fleet case8's missing specialist delegation.

## Behavior and evidence

Structured output uses the existing Instructor validation path. A new sourced
catalog declares contracts for exact provider, model and actual SDK base URL
combinations. Provider labels and model-family prefixes do not prove wire
behavior, especially when a base-URL override sends a familiar label to a
different gateway.

| Route | Qualified declaration | Evidence limit |
|---|---|---|
| Native `deepseek/deepseek-flash` and `deepseek/deepseek-v4-pro` | At the official native base and documented `/v1` alias, use forced tools with documented `reasoning_effort=none`; retain documented optional log probabilities. | Current vendor contract plus offline protocol twins; no new live native run or quality/latency comparison. |
| `opencode-go/deepseek-v4-pro` | At the exact official Go endpoint, start in schema-validated JSON mode; omit optional log probabilities as a conservative request policy; send no unverified native thinking switch. | Preserved October18 exact-route JSON retry/served proof; gateway forwarding of native thinking controls remains unproved. |
| Go `deepseek-v4.1-flash`, future/legacy identifiers, other gateways, missing/custom/look-alike endpoints | Keep existing payload and reactive compatibility recovery. | No inherited declaration merely from the DeepSeek brand or Go provider label. Case8's separately recorded recovery does not imply every route has the same contract. |

The native change disables thinking for the forced-tool protocol even when a
caller did not request `disable_reasoning`; this follows the documented
restriction on named/required tool choices. It is an explicit behavior change,
not a measured quality improvement. Unknown routes preserve existing behavior.
No native contract is copied onto the gateway; a documented native parameter
is not evidence that a gateway forwards it.

The base URL is read from the actual server-owned SDK client. Matching rejects
userinfo, query, fragment, hostname look-alikes, alternate paths and transport
downgrades. Full ordered message history, schema validation, bounded changed
retries and per-physical-request admission/settlement remain covered. The new
complete regression file is appended to the existing physical-attempt CI
selection without removing older tests.

## Review failures retained and corrected

An earlier draft inferred behavior from family names and later from labels
without binding the actual endpoint. Another sent an unattested native thinking
switch through Go. Neither was published as qualified behavior.

Root's independent real-SDK counter then returned a synthetic HTTP502 whose
message mentioned an unsupported thinking option. The draft stripped that
option and saved a permanent unsupported fact despite the transient status.
The final correction requires an actual provider HTTP400/422 rejection,
including an explicit Instructor exception cause; local validation dumps,
auth/rate limits and temporary server failures do not establish that fact.
The repeated counter retained the native option on every request and saved no
unsupported memo. The failed and corrected counter evidence is retained.

The shared status helper also serves account-quota handling. Its explicit-cause
unwrapping is a cross-caller change; the 11 existing quota-routing controls
passed independently in addition to the 97 focused controls. New tests cover
wrapped400/422 positives and502/503/429/401/403/local-schema negatives. The
broader legacy test comparison from the worker retained the same13 failures
on its baseline and earlier candidate, not a broad-suite green claim.

## Sources and limits

- [DeepSeek Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/): current model identifiers, thinking toggle/effort, forced-tool restrictions and log probabilities; checked November17,2026.
- [DeepSeek thinking mode](https://api-docs.deepseek.com/guides/thinking_mode/): native thinking defaults and controls.
- [Preserved exact Go v4-pro served record](../../backend/scripts/orchestration_acceptance/journey_matrix/l1_s6_successor_served_20261018/README.md): forced-tool rejection followed by a served JSON retry. This is not evidence about every gateway model.

Offline twins validate the request construction and deterministic recovery;
they do not show that current upstream behavior, generated answer quality or
model capability meets the app's goals. Case7 remains failed with unknown
original error cause; case8 separately demonstrated reactive logprob recovery
but still failed to delegate. Original143 claims/18 goals remain incomplete.

Publication code head: `f937efcc7bd39a433e838f7cc59f02d507763700` on documentation main `1453f2cf4`.
Root checked that rebasing changed only the nine already-reviewed documentation
files: runtime, harness/test and CI bytes remain identical to the executed
source. All 642 CI-preservation controls passed independently on this release.
