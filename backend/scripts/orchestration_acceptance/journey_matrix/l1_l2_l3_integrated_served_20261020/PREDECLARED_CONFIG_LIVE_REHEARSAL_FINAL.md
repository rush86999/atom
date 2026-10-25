# Predeclared configuration — full configured profile (policy automatic)

**Declared before execution, 2026-10-24.**

This run tests the final S7 degraded-continuation repair on the full
configured profile. The policy is `automatic` (every configured provider is
eligible). The historical intended-route observations (Ollama/DeepSeek) are
recorded as evidence but are **not** pass/fail criteria; the gate is the
declared policy itself.

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

- Approved profile is the configured set derived from the isolated BYOK
  copy plus local Ollama: DeepSeek, Ollama, OpenCode Go, OpenRouter.
- `automatic` authorizes every approved provider. A `selected` policy
  authorizes only its non-empty allowed subset, and that subset must be
  inside the approved set; an invalid policy authorizes nothing.
- Any POST outside the authorized set is a failure. This is the real
  restriction. It is policy-derived, not the historical two-provider
  list: under `automatic` it authorizes the configured OpenRouter and
  OpenCode Go routes as well, and the declaration says so explicitly.

## Checks

- All 62 checks must pass.
- `provider_policy_declared` — the recorded policy is valid and its
  authorized set is well-formed.
- `provider_policy_respected` — every provider POST is inside the
  authorized set (fail-closed on an empty set).
- `provider_reply_authorized` / `provider_structured_authorized` — every
  reply and structured route is inside the same authorized set.
- `l3_interpretation_authorized`, `comparison_interpretation_authorized`,
  `continuation_interpretation_authorized` — a model origin’s dispatch
  routes must be authorized; `deterministic:continuation` is authorized
  because it dispatches no model.
- Historical intended-route results remain recorded under
  `provider_routes.historical_intended_route_checks` but do not decide
  the pass.
- The S7 date-only follow-up may take at most a 5s optional model
  refinement. If that does not resolve, the explicit
  `deterministic:continuation` record is used: source bound to the
  observed approved record, exactly `expiration_date`,
  `broader_comparison` false, zero writes. Any refinement attempt must
  still use an authorized route.
- A genuinely broad follow-up stays broad (whole-document obligation
  open), and an ambiguous source clarifies without selecting one.
- The cutover request, if any, must explicitly accept the actual
  authorized routes.
