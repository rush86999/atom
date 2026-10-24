# BYOK routing and settings: bounded release work order

Date: 2026-10-24, America/Toronto. Companion to `AUTONOMOUS_COMPLETION_GUIDE_2026-10-23.md`.

## Outcome

Include BYOK correctness and its user experience in the release candidate. A saved credential must not be confused with permission to use that provider for every request. Users must be able to understand and control which services may receive their content, choose a preferred route, and understand an actual fallback. Preserve all existing credentials and provider definitions.

This is one bounded settings-to-dispatch slice, not a BYOK redesign, credential migration, new router, or provider-account-management project. Keep the passing functional workflow and all prior evidence. Live cutover remains held.

## Verified starting evidence

- Attempt 9 on product `09cccb5b0` passed all 59 functional checks with the full copied provider store. It failed the two declared route-policy checks: replies and plans used configured OpenCode Go/OpenRouter routes outside the intended Ollama/DeepSeek profile.
- `byok_handler.py` describes `ATOM_PREFERRED_LLM_PROVIDER` / `ATOM_PREFERRED_LLM_MODEL` as ranking preferences. They do not establish an allowlist.
- `pinned_planning.py::pinned_structured_call` intentionally performs an unpinned fallback after the preferred pin yields no result. That fallback must preserve a separate hard route policy.
- `frontend-nextjs/src/components/AIProviders/AIProviderSettings.tsx` maps provider `status === "active"` to a `test_result` labelled “Connection successful.” Its Test Connection action reloads status. Inspect what the backend actually probes before asserting a fresh successful test; active/configured is not itself evidence that the selected model can answer now.
- `runtime_settings.py` supports environment override, persisted settings, defaults, and cache invalidation. Reuse the established settings/auth surface, but do not let its generic invalid-value fallback accidentally turn a malformed restrictive policy into unrestricted routing.

Revalidate the current owner branch, symbols, and active file ownership before editing. Shared main and the pilot are not the implementation workspace.

## 1. User flow in Settings → AI

Keep a simple primary flow; model-level details belong under Advanced.

1. **Connections:** show provider name, key saved/not saved, enabled state, recent verified check, and an appropriate account-management link. A key remains masked; never return it to the browser after save. Provider API base URL is not automatically its key-management page. Avoid assuming all keys start with `sk-`.
2. **Where Atom may send requests:** offer “Automatic among enabled providers” and “Only selected providers.” Show the effective provider names and explain that enabled cloud providers may receive request content. Saving or retaining a key is separate from the routing selection. Do not silently opt an existing installation into new providers or delete stored keys to implement restrictions.
3. **Preferred provider:** choose the first eligible option inside the allowed set. Explain that preferred is an order, not a guarantee. Preserve capability, access, local-only, and billing constraints.
4. **Fallback:** show permitted alternatives. In selected-provider mode, fallback cannot escape the selected set. If no allowed route is usable, show an actionable unavailable-provider result rather than silently sending elsewhere.
5. **Save and check:** save policy through the authenticated settings API, show validation failures, and retain the prior effective policy on failed save. A bounded actual check reports the tested provider/model and time. If checks can incur usage, say so before initiating one; do not repeatedly probe every configured provider on page load.

Use clear status labels: “Key saved,” “Not checked,” “Ready — checked at …,” “Authentication failed,” “Usage limit reached,” “Unavailable,” and “Enabled, excluded by routing policy.” Distinguish quota and rate limits from invalid credentials. Do not label missing model capability as a bad key.

On normal chat responses, expose the actual answering provider/model in the existing metadata/details UI and a short fallback indication when relevant. Do not ask the user to approve every normal fallback already permitted by their saved policy. Never show an internal error placeholder as successful content.

Environment-enforced configuration remains authoritative. Show its effective value and “Managed by this installation” with disabled conflicting controls; never present a UI save as effective when an environment override wins. Preserve existing local-only semantics: this work must not make cloud dispatch legal under local-only.

## 2. Backend policy contract

Audit the settings catalogue/API, scoped handler construction, ranked/default routes, pin handling, streaming and non-streaming paths before choosing the smallest implementation. Reuse existing general policy machinery if it already supplies this contract.

An illustrative internal record (not a required new API) is:

```json
{
  "mode": "selected",
  "allowed_providers": ["ollama", "deepseek"],
  "preferred": {"provider": "ollama", "model": "llama3.1:8b"}
}
```

Required semantics:

- Policy belongs to the authenticated installation/workspace scope used for dispatch. Never borrow another workspace's settings or constructor handler.
- Unset policy preserves the explicitly documented legacy behavior; explicitly empty selected-provider policy means no routes, not unrestricted fallback. Reject unknown IDs and malformed saves. An unreadable restrictive policy must fail closed with a configuration error.
- UI permissions follow the existing settings/admin authorization. A chat message or untrusted client context cannot expand the allowed set. No secret values enter policy telemetry.
- Request admission resolves one effective immutable policy snapshot. Ordinary changes apply to new requests; document any separate emergency revocation behavior instead of promising immediate cancellation of in-flight network requests.
- Intersect eligible candidates with allowed providers before ranking. Recheck every provider/model immediately before transport dispatch so defaults, direct pins, retries, streaming fallback, capability fail-open, and absolute fallback cannot escape.
- Apply the constraint to all AI calls owned by the request, including interpretation, tool/edit planning, replies, guard regeneration, and any invoked embedding/auxiliary paths. Preserve any narrower existing policies. Do not claim global enforcement until direct clients/background callers are audited; a caller without request context must resolve an appropriate installation policy or fail closed where required.
- Pins and preferences may choose only allowed eligible routes. A denied or failed pin may fall back only within the policy; it cannot widen the provider pool. Keep deadline, quality, entitlement, capability, and local-only checks.
- Do not bypass the observed-latency gate blindly to make an edit pin hold. Trace pin admission → forwarded kwargs → actual attempt → failure/fallback. If a slow route is unsuitable, the policy permits an honest failure or a declared allowed alternative, not an unauthorized provider.
- An API response should expose effective policy, configuration source, and non-secret reason codes. Actual route evidence must be request-bound, not mutable “last used” globals shared across users.

Pattern only; use existing APIs:

```python
policy = resolve_authorized_effective_policy(scope)
eligible = policy.filter(capability_eligible_routes)
ranked = rank_with_preference(eligible)

for route in bounded_attempts(ranked):
    policy.require_allowed(route)  # immediately before the actual transport
    result = await dispatch(route, deadline=deadline)
    if result.usable:
        return result
return honest_allowed_routes_unavailable()
```

Filtering just one ranker is insufficient: trace every escape/default path. Do not duplicate a different allowlist in each caller or mutate shared handler state per request.

## 3. Repo work map

- `backend/core/settings_catalog.py`, `runtime_settings.py`, and the existing settings API: persistence, effective overrides, validation and invalidation.
- `backend/api/byok_routes.py`: provider/key status and actual check behavior; retain vault ownership and no-secret response contracts.
- `backend/core/llm_service.py`: request-scoped forwarding.
- `backend/core/llm/byok_handler.py`: candidate selection, defaults, structured/non-streaming/streaming dispatch and fallback.
- `backend/core/llm/pinned_planning.py`: pin preference, scope and fallback.
- `backend/core/request_scope.py`: authenticated scope propagation.
- `frontend-nextjs/pages/settings/ai.tsx` and `src/components/AIProviders/AIProviderSettings.tsx`: existing user surface. Inspect routing/settings pages for established components before adding another panel.
- `frontend-nextjs/tests/components/AIProviderSettings.test.tsx` and relevant backend scope/pin/routing tests: test neighborhoods. Find additional current tests rather than assuming all historical filenames still apply.

Use the current integrated owner worktree. Coordinate edits to shared routing/orchestration files; the pilot remains unchanged.

## 4. Acceptance tests that must discriminate

Backend/transport:

- Full 13-key/37-provider scratch store remains byte-preserved; selected Ollama/DeepSeek policy produces zero POSTs to OpenRouter/OpenCode Go.
- Allowed primary and allowed fallback work in streaming, non-streaming, structured interpretation and planning.
- A forbidden explicit pin, exhausted allowed pool, no local client, capability fail-open, and default/absolute fallback cannot escape the policy.
- Empty/malformed selected policy fails closed; unset legacy behavior is explicitly tested. UI cannot expand an operator-enforced restriction.
- Two scopes overlap at a real event barrier without policy leakage; settings/credential changes do not mutate another scope's active handler.
- Per-request telemetry reports actual attempts, answering route, fallback reason, and effective policy revision/source without credentials.
- A failed preference does not bypass the same policy; a failed check does not delete or rotate the key.

Browser:

- Save provider selection; reload and sign in again; effective selection persists.
- “Test connection” displays an actual bounded check result and timestamp, or honestly says no recent check exists.
- “Preferred” and “allowed” are visibly different. Disabling routing does not delete a key.
- Environment override is visible and conflicting controls cannot pretend to change it.
- Simulated allowed-primary failure uses only a permitted fallback and shows the actual answering route. Exhaustion gives a useful next action, not an endless spinner or bad-key claim for a quota error.
- Failed saves preserve the prior effective settings; controls are labelled and keyboard-accessible.

Use mock transports to prove forbidden destinations receive zero attempts, then a bounded real scoped smoke on already authorized routes. A catalogue lookup alone is not a successful inference test; one inference success is not a latency guarantee.

## 5. Completion sequence and limits

One implementation owner implements backend and UX together; independent review examines policy escape paths and UI truthfulness. Keep the passing functional workflow unchanged. Do not start another model campaign while local transport controls still fail.

1. Audit existing policy/settings paths and publish a compact owned-file plan in coordination notes; then implement without asking for a new brief.
2. Run policy, scope, pin, streaming, settings, provider-status and UI tests plus meaningful persistence controls.
3. Freeze runtime/frontend/configuration and independently review it.
4. Run one unfiltered-BYOK isolated live-world rehearsal under the saved selected-provider policy, with actual HTTP attribution and all existing functional gates. Preserve earlier outcomes.
5. Refresh cutover package only after the declared functional and routing/UI gates pass. Obtain the still-required final live-cutover approval; do not infer it from this work order.

No credential removal, funding, key rotation, broad endpoint migration, per-turn user model selection, or live deployment is implied. Nonessential model analytics, onboarding redesign, all-provider account-link acquisition, and a new routing dashboard are out of scope. Prior successful evidence remains candidate-bound. This work is complete when saved user policy controls real dispatch, the UI describes its effective behavior truthfully, and the integrated job passes under that policy.
