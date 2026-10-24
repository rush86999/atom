# Predeclared configuration — selected-provider policy (Ollama/DeepSeek/OpenCode Go)

**Declared before execution, 2026-10-24.**

Attempt 10 proved the strict Ollama/DeepSeek boundary blocks every forbidden
POST, but the identical re-ask failed because the allowed edit planner could
not produce a no-op plan. This run keeps the policy boundary and admits the
one additional configured provider needed for the verified edit-planning
shape, while excluding OpenRouter.

## Candidate

| Item | Value |
|---|---|
| Product commit | `a729df5f572ac254eac0ae0d4180818c67916eba` |
| Product tree | `481f3a4f338fdd50fc9f2870019f0be89e3fff5f` |
| Launch commit | `0f012af51d41…` (clean) |
| Frontend build | `P5jHbHKTzj_38xHIMFoe9` |
| Live gate | `successor_gates_live.py` `6d66d0b8…` |

## Policy

```
ATOM_LLM_PROVIDER_POLICY={"mode":"selected","allowed_providers":["ollama","deepseek","opencode-go"],"preferred":{"provider":"ollama","model":"llama3.1:8b"}}
```

- All 13 keys / 37 provider definitions remain in the isolated copy.
- OpenRouter remains configured but **forbidden**; it must receive zero POSTs.
- Replies/planning may use Ollama, DeepSeek, or OpenCode Go only.
- Intent: keep the provider that was actually needed for edit planning while
  excluding the other previously observed fallback (OpenRouter).

## Isolation

- World: 09:19 876 MB snapshot (`quick_check=ok`).
- Scratch: `…/l2-fix/scratch/l1-l2-l3-live-rehearsal-20261024-policy3`.
- Live pilot/DB/BYOK untouched; backend on `:8121`.

## Pass conditions

All 61 checks, including `provider_reply_parity` and
`provider_allowlist_clean` with OpenCode Go allowed and OpenRouter denied.
Any OpenRouter POST is a failure.
