# Release approval request — Atom `55b13cd2f`

**Requested decision:** approve **one reversible live cutover** of the local
Atom pilot (`:8001` / `:3000`) to product
`55b13cd2fcab67ba8436618f7032339649cbdffc`, using the prepared release
tree, verified frontend build, fresh backup, smoke checks, and rollback
below.

**No cutover has been executed.** The live-deployment hold remains in
force until this exact package is approved. A rollback ends the attempt;
there is no second attempt in the same window.

## Current environment

- The pilot backend `:8001` and frontend `:3000` were **absent before**
  attempt 16. The disappearance is **unexplained**; this work did not
  intentionally stop or restore the pilot.
- No live-DB/WAL/SHM holder was present at backup capture.
- Attempt 16 was a **declared no-pilot isolated rehearsal** on `:8121`.
  It establishes a `no_pilot_isolation_asserted` claim, **not** pilot
  preservation.
- Attempt 15 remains **functional verification passed; original
  pilot-preservation assertion not established**. It is not 62/62.

## Candidate

| Item | Value |
|---|---|
| Product | `55b13cd2fcab67ba8436618f7032339649cbdffc` |
| Backend tree | `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-release-55b13cd2f-20261024` (clean) |
| Frontend tree | `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-release-a729df5f5-20261024/frontend-nextjs` |
| Frontend build | `P5jHbHKTzj_38xHIMFoe9` (source identical to `55b13cd2f`) |
| Python | `/Users/rushiparikh/projects/atom/backend/venv314/bin/python` |
| Actual provider profile | `automatic`; DeepSeek, Ollama, OpenCode Go, OpenRouter authorized |

## Evidence

- **Attempt 16** (declared no-pilot): `no_pilot_isolation_asserted=true`.
  **Original result: 61/62**, only `l3_answer_correct` failed under the
  original predeclared gate (expected code, **no decoy mention**). The
  gate remains failed; this is **not** an automated 62/62.
- **Independent manual answer assessment:** the captured L3 answer is
  semantically correct — QUARTZ-77 for Zephyr-9; BASALT-13 correctly
  attributed to Halcyon-2 as its archive key; no swapped or contradictory
  assignment; source named. This is a manual semantic assessment, not the
  original gate passing.
- **Answer-scope contract:** no change is requested in this package. The
  earlier lenient predicate (`f40d2a881`) was withdrawn because it could
  accept swapped/contradictory assignments; the original strict gate is
  restored.
- **517 focused tests passed** on the final local batch. Two
  `test_fallback_honesty` receipt fixtures fail identically on parent
  `73bcae400` (pre-existing).
- **S7 date-only:** `deterministic:continuation`; 5s DeepSeek refinement
  cancelled (`wait_timeout`); source
  `approved_records_q2026_114.txt`; fields exactly `["expiration_date"]`;
  `broader_comparison=false`; context `completed`; zero writes; outcome
  `partial` for the captured prior outlook obligation; `success=true`;
  38.64s.
- **Edit/no-op:** applied exactly once; identical re-ask completed with
  zero writes.
- **Provider policy:** all policy gates passed; actual reply routes were
  within the declared four providers.

## Backup and rollback source

```
/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/
atom-cutover-55b13cd2f-20261024/pre_cutover/
atom-pre-cutover-55b13cd2f-20261025T034740Z.db
sha256 de62922c9d826d133e6813bd0455a6668a5576c175d2a3486a97310e58a82f6b
quick_check ok
users 49; chat_sessions 1025; chat_messages 5430; agent_executions 4257;
canvases 197; canvas_audit 1116; ingested_documents 3747; task_operation_records 269
```

Source live DB sha256
`4b25241ef0754e33424bdaac74f5ee063e5b750eeaedf0f7c596429eb13aca7e`,
WAL size 0. Immediately before cutover, re-verify the live DB is
unchanged; if any writer touched it, take a new fresh WAL-safe snapshot.
The 09:19 rehearsal backup is not the cutover rollback source.

Private config/secret backup (outside committed evidence, mode 700):
`/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-cutover-55b13cd2f-20261024/private_config_backup`.
Copy `byok_config.json`, `byok_keys.json`, `byok_encryption_key`, `.env`
there with `cp -p` and mode 600 at cutover. Archive only the redacted
manifest; never commit those file contents.

## Smoke gate (must pass before declaring success)

1. `/api/health` 200, `identity.revision=55b13cd2f`, clean, live DB/BYOK
   paths.
2. `/login` 200 and a real browser sign-in.
3. Sourced answer: upload `release_smoke_record_55b13cd2f.txt` and ask for
   its `CEDAR-55` code; answer names the source, no provider/error text,
   persisted history.
4. Edit: `Payment terms: Net 45` → `Net 30`; exactly one audit/write;
   other fields preserved.
5. Identical re-ask: byte-identical body, zero additional writes, honest
   no-op.
6. S7 date-only: source-bound `expiration_date` comparison; zero writes;
   response/settlement/history agree.
7. Reload/restart: same identity, history, canvas, no new write.
8. Provider POSTs only to DeepSeek, local Ollama, OpenCode Go, or
   OpenRouter. Any other destination is a rollback condition.

## Rollback

Stop candidate PIDs; free `:8001`/`:3000`; remove WAL/SHM; restore the
fresh backup; verify `quick_check`/row counts; restore the four pre-cutover
config/secret files from the private backup directory; restart the old
backend from
`/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-rollback-8c593e/backend`
on `:8001` and the old frontend from
`/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-release-910bf85a6/frontend-nextjs`
on `:3000`; verify health `8c593e57031e` and `/login` 200. Keep all
evidence; the attempt is over.

## What approval covers — and does not

**Covers:** one reversible live start of this exact backend/frontend build
against the intended live DB; the declared `automatic` provider profile
(DeepSeek/Ollama/OpenCode Go/OpenRouter); the no-pilot environment claim;
the backup, smoke, and rollback above.

**Does not cover:** a second attempt after rollback; a different product
or provider profile; a deadline change; a claim that attempt 15 was
62/62; a pilot-preservation claim; a change to the answer-scope contract;
or treating the manual L3 assessment as the automated gate passing.

## Known limitations

- The pilot was absent before the rehearsal; its disappearance is
  unexplained. The live start would start the candidate, not restore the
  old pilot first.
- Attempt 16 is **61/62** under the original predeclared gate. The
  captured L3 answer is semantically correct by independent manual
  assessment, but it is not an automated gate pass. No new campaign was
  run to change that.
- The S7 date-only settlement is `partial` because the captured prior
  outlook obligation remains open; this is truthful, not a failure.
- The direct harness does not always persist the detailed
  context-fulfillment gap; `objective_met=false` and response/history
  agree on non-completion.
- The additional-action extractor records a primary edit as an
  `additional_action`; the primary edit/no-op receipt path is unaffected.

## Evidence

- `docs/acceptance/RELEASE_PACKAGE_55b13cd2f_2026-10-24.md`
- `docs/acceptance/release_evidence_20261024/release_55b13cd2f/`
  (`release_config.json`, `no_pilot_preflight.json`,
  `manual_answer_semantic_assessment.json`,
  `pre_cutover_config_manifest.redacted.json`, `backup_verification.json`,
  attempt-16 config/summary/result/console, checksums). Secret/config
  files go only to the private backup directory, never committed
  evidence.
- `docs/acceptance/S7_CONTINUATION_REPAIR_2026-10-24.md`

**Requested: Approve / Do not approve this one reversible cutover.**
