# Goal 9 — PR832 c3 backend-core CI repair

Date: 2026-11-10. Branch: `codex/goal9-ci-repair-c3-20261110`, based on
`c3c540f720f7497e8443a6d30299c3525e2ed8d9` (PR832 frozen; not edited).
This is a focused CI repair, not Goal 9 acceptance. The atomic reservation
WIP remains separately checkpointed on `codex/goal9-atomic-cap-20261110` at
`bc8d7c10a03903779e02bb8564cb948b9c3f8a31`.

## Root cause (runtime evidence, not fixture hypothesis)

The root-private c3 backend-core log is retained as an excerpt with its
byte count and SHA-256 in `retained_negative/`; the full log remains
root-private. The actual evidence is **17 pre-dispatch intent `NameError`s**
and **13 failing CI tests**:

- `backend/core/llm/byok_handler.py::generate_response` had `agent_id` and
  `chain_id` but no `execution_id` parameter/local. The new durable
  pre-dispatch call and both ordinary settlement branches passed
  `execution_id=execution_id`, so every ordinary completion raised
  `NameError` before any provider call. The test doubles never reached the
  provider and returned the generic "every provider failed" text.
- The earlier fixture-gap hypothesis is **superseded** by this runtime
  evidence: the failure was a real consumer-contract defect, not a missing
  test binding.

The exact 13 CI failures are preserved in the excerpt: 6
`TestFreeToPaidRetry`, 3 `TestStageSteeringRealBPC`, and 4
`TestGenerateResponseModelTypeSteering`.

## Fixes

### 1. Real optional execution attribution

`generate_response` now accepts the legitimate optional
`execution_id: Optional[str] = None` contract and uses that same value in
the pre-dispatch intent and both ordinary settlement/error paths. Callers
without an execution context deliberately pass `None` (no invented
identity, no global); callers that own a server execution can pass the
exact id. `LLMService.generate` already forwards kwargs, so the option is
available without changing routing or eligibility.

### 2. Per-call stream identity (real production defect found in review)

`_stash_decision_features` returns `None` when the learning router is off.
The stream settlement used `f"{stream_decision_id}:stream:request"`, so every
stream in that mode shared `"None:stream:request"` and collided on the
ledger's unique `attempt_id`. `stream_completion` now mints a per-call
server-owned `stream-<uuid>` identity when the decision id is absent; the
request/attempt ids and feedback decision id remain separate concerns.

### 3. No hidden provider fallback on ledger/scope failure

Ordinary `generate_response` and `generate_chat_completion` previously
`continue`d to the next provider when the durable intent could not persist.
That is a hidden fallback after an accounting/scope failure. Both now
`break` the provider loop; no provider is dispatched and the caller sees
the truthful failure. The pre-dispatch ledger gate and credit liability are
preserved (no provider call, no fake charged usage).

## Verification (scratch SQLite, doubled transport only)

Exact failing classes: **15 passed** (includes the 13 CI failures).
New `tests/test_goal9_ci_execution_contract.py`: **3 passed**
- ordinary doubled response with no execution context -> success and ledger
  `execution_id is None`;
- exact provided `execution_id="exec-ci-123"` -> ledger attribution exact;
- intent store failure -> zero provider calls on both ranked providers, no
  hidden fallback, no intent row.

Gates:

- focused (two failing files + new contract): **59 passed**
- stream/route regression (opencode provider, retry state, deepseek, BYOK
  stream): **132 passed**
- bounded backend-core BYOK/route subset (CI-listed files + new contract):
  **225 passed**
- PR832 durable/upgrade regression: **29 passed**

Logs: `gates/focused.log`, `gates/stream.log`, `gates/bounded.log`,
`gates/durable.log`. The broad out-of-CI unit-double selection was not used
as a gate; those doubles do not bind the scratch ledger and are not part of
the backend-core CI selection.

## Honest limits

- Scratch SQLite only; no hosted CI run, live DB, provider/model, credential,
  send, spend, deploy, download, or new dependency. Root will run hosted CI
  and integrate verified source.
- Atomic concurrent reservation remains open on its separate branch; this
  repair does not mix reservation runtime into the c3 CI lane.
- PR832 c3 is frozen; no merge/approval/self-accept. Root review owns
  integration and the final CI gate.
