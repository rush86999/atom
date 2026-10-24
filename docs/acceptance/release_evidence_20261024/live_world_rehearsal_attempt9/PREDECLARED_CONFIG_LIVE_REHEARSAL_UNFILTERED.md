# Predeclared configuration — unfiltered-BYOK live-world rehearsal

**Declared before execution, 2026-10-24.**

This is the successor configuration after the `[ingested]` paragraph-deletion
fix. It does not transfer attempt 8's pass to changed code; attempt 8 remains
historical evidence for `cc813aeeb`.

## Candidate

| Item | Value |
|---|---|
| Product commit | `09cccb5b0b977f86c0a39d59af5b922c83143e7f` |
| Product tree | `4c7ec787c8ff1f81baa89f1cdc3c40496ef44b1f` |
| Launch commit | `09cccb5b0b977f86c0a39d59af5b922c83143e7f` (clean) |
| Branch | `fix/l3-required-read-timeout` |
| Interpreter | `/Users/rushiparikh/projects/atom/backend/venv314/bin/python` 3.14.7 |
| Live gate | `successor_gates_live.py` `6d66d0b8b3b2c9a24efbe111a750c477f623a207d34692dcd4fa07cfceb88dd2` |

Frozen source hashes:

```
answer_boundary        3a36a5dd99cd11e1767c036461f84342fbf41e4f20d6644e147f5047a6b49db3
chat_tool_planner      807dd65eb83fe7676ac29fba475ef188cac6ad82146c02321d66564a023414c5
chat_orchestrator      7736adbf3bbf9e007087201f4e72b212a1667f7384ec44426efc915b3802d91c
workbook_read_artifact db23d66749eb79ed37f0011b96b0096ad0e746cc0c981fd5f5f6edb89889da67
chat_canvas_editor     5f724ceb645cff36718c13a5c6a3cb3de2417f63f9b2e04cc5be84c55170dece
chat_routes            d86d0be9334e8927c6811b998a5cc8c28a3b535d03cace57e8f9529679ffa0e0
turn_decision          f5342f1d8deac03a917142d5931efec190fe58a52889e8acf9cc551963508065
```

## Isolation and world

- World: the verified 876 MB 09:19 snapshot
  `atom-cutover-final-20261024/atom-pre-cutover-final-20261024-091936.db.gz`
  (`quick_check=ok`; 48 users / 1022 sessions / 5426 messages).
- Scratch root: `…/opencode/l2-fix/scratch/l1-l2-l3-live-rehearsal-20261024-unfiltered`.
- Auxiliary stores (SQLite/LanceDB/BYOK) are fresh under the scratch root.
- Scheduler and ingestion sync are disabled; no background writer runs.
- The live pilot on `:8001`/`:3000` and the live DB are not modified.
- The rehearsal backend listens on `:8121`.

## Unfiltered BYOK

This is the configuration-parity check that attempt 8 did not perform.

- `byok_config.json`, `byok_keys.json`, and `byok_encryption_key` are copied
  from `/Users/rushiparikh/projects/atom/backend/data` into the scratch world
  **before launch**. The live files are read-only.
- All 13 existing keys and 37 provider definitions are present in the
  isolated copy. No provider is filtered out.
- The scratch copy is what the product reads; the pilot's provider settings
  remain intact.
- DeepSeek is still registered through the product API inside the scratch
  world (the same authorized operator credential) so the structured route
  can be exercised through the real product path.
- Intended reply: `ollama/llama3.1:8b`.
- Intended structured interpretation and edit planning:
  `deepseek/deepseek-v4-pro`.
- Allowed fallback: DeepSeek.
- Any outbound provider POST other than `api.deepseek.com` or local Ollama
  (`localhost:11434` / `127.0.0.1:11434`) is an unexpected-provider failure.
  The runner scans both server logs and records every POST destination.

## Flags

```
CHAT_FINALIZATION_M1=1
CHAT_FINALIZATION_M2=1
ATOM_TASK_LIFECYCLE_ENABLED=1
ATOM_TURN_DECISION_ROUTING=1
ATOM_TURN_INTERPRETATION=1
ATOM_TURN_INTERPRET_PIN=deepseek:deepseek-v4-pro
ATOM_TURN_INTERPRET_CAPTURE=1
ATOM_ASYNC_EDIT_PLAN_MODEL=deepseek/deepseek-v4-pro
ATOM_PROVIDER=ollama
ATOM_DEFAULT_MODEL=llama3.1:8b
PREFERRED_PROVIDER=ollama
ATOM_PREFERRED_LLM_PROVIDER=ollama
ATOM_PREFERRED_LLM_MODEL=llama3.1:8b
```

## Workflow and fixtures

Same composed workflow as attempt 8:

1. Upload `approved_records_q2026_114.txt` and `l3_zephyr9_fixture.txt`
   through `POST /api/documents/upload`.
2. L3 sourced ask: search for the Zephyr-9 launch code; expect `QUARTZ-77`,
   verified `documents.search` receipt, no `BASALT-13`.
3. Edit: `Please update the payment terms in the draft to Net 30.`
   (one write).
4. Identical re-ask: no-op, zero additional writes.
5. S3: compare the draft quotation with the approved record; honest partial,
   broader obligation OPEN, truthful date, zero writes.
6. S7: date-only continuation; settlement basis; restart agreement.
7. Restart the same scratch process/stores; reload both sessions.

## Checks

The attempt-9 result adds `provider_allowlist_clean` to the attempt-8 checks.
A pass requires all of:

- runtime identity and product/source pins;
- L3 answer, receipt, history agreement;
- edit exactly one write and field preservation;
- re-ask no-op and zero writes;
- S3/S7 truthful behavior and zero writes;
- restart identity/history/zero-write agreement;
- structured DeepSeek and reply Ollama/DeepSeek parity;
- **no unexpected provider POST destination**;
- live DB isolated and pilot untouched.

A failure is classified by the first failing check; no gate is relaxed.
