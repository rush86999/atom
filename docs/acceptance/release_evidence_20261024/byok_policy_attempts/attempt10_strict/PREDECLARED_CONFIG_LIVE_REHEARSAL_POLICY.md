# Predeclared configuration — selected-provider policy rehearsal

**Declared before execution, 2026-10-24.**

This verifies the BYOK policy boundary with the full pilot BYOK store.
Attempt 9's functional pass remains historical; this is the first run under
an enforced selected-provider policy.

## Candidate

| Item | Value |
|---|---|
| Product commit | `a729df5f572ac254eac0ae0d4180818c67916eba` |
| Product tree | `481f3a4f338fdd50fc9f2870019f0be89e3fff5f` |
| Launch commit | `a729df5f572ac254eac0ae0d4180818c67916eba` (clean) |
| Branch | `fix/l3-required-read-timeout` |
| Frontend build | `P5jHbHKTzj_38xHIMFoe9` |
| Live gate | `successor_gates_live.py` `6d66d0b8…` |

## Policy under test

```
ATOM_LLM_PROVIDER_POLICY={"mode":"selected","allowed_providers":["ollama","deepseek"],"preferred":{"provider":"ollama","model":"llama3.1:8b"}}
```

- All 13 keys / 37 provider definitions are copied into the isolated world.
- OpenCode Go and OpenRouter keys remain present but are forbidden by policy.
- Any outbound POST to OpenCode Go/OpenRouter (or any provider other than
  `api.deepseek.com` / local Ollama) is a hard failure.
- Replies and planning must use only Ollama/DeepSeek. Preferred is an order,
  not a guarantee; capability/local-only/rate checks still apply.

## Isolation

- World: 09:19 876 MB snapshot (`quick_check=ok`).
- Scratch: `…/opencode/l2-fix/scratch/l1-l2-l3-live-rehearsal-20261024-policy`.
- Live DB/BYOK/pilot untouched; backend on `:8121`.
- Scheduler/ingestion disabled.

## Workflow

Same composed fixture and asks as attempt 9: upload → L3 sourced answer →
edit → identical no-op → S3 partial → S7 date-only → restart agreement.

## Pass conditions

All 61 checks, including `provider_reply_parity` and
`provider_allowlist_clean` under the Ollama/DeepSeek-only allowlist. A
forbidden POST is a failure regardless of answer correctness.
