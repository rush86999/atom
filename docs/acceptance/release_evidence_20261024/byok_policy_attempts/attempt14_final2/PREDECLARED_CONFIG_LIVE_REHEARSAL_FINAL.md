# Predeclared configuration — full configured profile (policy automatic)

**Declared before execution, 2026-10-24.**

This run tests the final edit/no-op repair on the full configured profile. The policy is `automatic` (all
configured providers eligible). The two historical intended-route checks
remain declared as failed; a separate `approved_profile_allowlist_clean`
check records whether every POST is one of the configured providers.

## Candidate

- Product `8912eba5dac56e3c6a29d18e380b1b1cf5adb3ea`
- Launch `8912eba5dac5`
- Frontend `P5jHbHKTzj_38xHIMFoe9`
- World: 09:19 876 MB snapshot; scratch
  `…/l1-l2-l3-live-rehearsal-20261024-final2`
- Full 13-key / 37-provider BYOK copy in isolation.

## Policy

```
ATOM_LLM_PROVIDER_POLICY={"mode":"automatic","allowed_providers":[]}
```

- Intended profile remains Ollama reply / DeepSeek structured; it is
  expected to fail parity if OpenCode Go/OpenRouter are selected.
- Approved profile is the configured set: DeepSeek, Ollama, OpenCode Go,
  OpenRouter.
- Any POST outside that configured set is a failure.

## Checks

- Functional checks must be 59/59.
- `provider_reply_parity` and `provider_allowlist_clean` are expected to
  fail under the historical Ollama/DeepSeek allowlist and are not relabeled.
- `approved_profile_allowlist_clean` must pass.
- A new edit must apply exactly once through the deterministic compiler;
  the identical re-ask must complete before planning with zero writes.
- The cutover request, if any, must explicitly accept the actual routes.
