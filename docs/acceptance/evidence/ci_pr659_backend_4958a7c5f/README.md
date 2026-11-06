# PR #659 backend CI diagnosis and repair

Status: **submitted for independent verification.** PR #663 restores the
backend test job that was red on merged PR #659. No production policy was
weakened.

## Observed failure

| Item | Value |
|---|---|
| PR | #659, merged at `baa695775c30686e21ca9d30fa0a1fb32c2175d3` (head `5ede9bf67`) |
| Run / job | `42149250267` / `127668163932` |
| Hosted result | **39 failed, 522 passed, 1 skipped** in 80.76s on Python 3.11.18 |
| Follow-up branch | `codex/ci659-backend-repair-20261105` from main `71f9e22b4` |
| Fix commit | `4958a7c5fa80c276f53c13b5fb33ee295f4bc5f5` |
| Follow-up PR | https://github.com/rush86999/atom/pull/663 |
| E2E fixture fix | `b472ef80cd05fd6727a0dd3cfc88bd99dfbf26dd` |

## Reproduction

The exact CI command and declared environment reproduced **39 failed, 522
passed, 1 skipped** on current main before the fix
(`ci659-repro-311.log`).

The same seven affected files on the recorded PR base `60a1171b8` produce the
**same 39 failures and 173 passes** (`ci659-base-seven.log`). This is
pre-existing fixture/consumer drift, not a fleet regression introduced by the
merged repair.

## Failure classes and fixes

| Class | Tests | Cause | Fix |
|---|---|---|---|
| Feedback observation | 4 | router stub rejected `observe_only=True`; handler Mock lacked `workspace_id`; completion handler double rejected `tenant_id` | stubs accept the current keyword contract; handler supplies workspace scope; test asserts `workspace_id`/`tenant_id` propagation |
| Oracle task-id proof | 1 | mock `BoardTask` omitted the title the current verifier checks | mock carries `title="do it"`; negative/refuted controls unchanged |
| OpenCode streaming | 7 | injected explicit provider route hit the unknown-catalog gate | `explicit_route=True` for the deliberately selected doubled route |
| OpenCode free→paid retry | 6 | injected routes lacked a discovered eligible catalog | local `ProviderModelCatalog` records the models exercised by the tests |
| BYOK provider serving | 2 | constructor-bypassed handler lacked `_local_routes`; stale hardcoded absolute-fallback expectation | complete handler state (`credential_signature`, `_local_routes={}`); assert the configured provider's tier default |
| BYOK chat/stream | 3 | constructor bypass caused credential refresh to replace doubles; catalog unknown | complete handler state plus explicit isolated catalog |
| DeepSeek taint/steering/retry | 16 | MagicMock completion payloads counted as empty; unknown catalog; sweep obscured isolated retry contract | real `SimpleNamespace` completion payloads; explicit catalog; disable the ladder sweep only inside the isolated retry tests |

No test was deleted, skipped, xfailed, or made permissive. Production
eligibility, oracle proof, strict pins, tenant scope and capability floors are
unchanged.

## Verification

| Gate | Result |
|---|---|
| Exact CI backend selection, Python 3.11 | **561 passed, 1 skipped, 0 failed** |
| Exact CI backend selection, Python 3.14 | **561 passed, 1 skipped, 0 failed** |
| Seven previously failing files together | **212 passed** |
| PR base `60a1171b8`, seven files | **39 failed, 173 passed** (same failure classes) |
| Memory eval gate | **recall 1.0**, no misses |
| PR #663 backend-tests | **pass** (4m42s) |
| PR #663 syntax/frontend/boot/quickstart/docker/GitGuardian | **pass** |
| PR #663 e2e-journey | **pass** after the privileged journey fixture fix (12m23s) |

## E2E check repair

The original `e2e-journey` failure was `TestSkillsJourney::test_skill_lifecycle`
getting `403` on skill delete: the journey fixture registers an ordinary member,
while the accepted community-skill contract requires TEAM_LEAD+.

The fixture now adds an isolated `journey_team_lead_headers` user registered
through the live backend with its role set in the backend's own DB. The test
asserts both directions: the ordinary member delete is refused with `403`, and
the privileged journey user deletes with `200/204`. The community-skill
authority guard is unchanged. Local API journey run: **6 passed**; hosted
`e2e-journey`: **pass 12m23s**.

## Boundaries

- No live model/provider/sandbox/browser/credential/spend/send/download/
  deployment operation.
- No dependency download, merge, force-push, or branch-protection change.
- Accepted fleet/ORCH-01/employee/feedback/admin/memory lanes remain unchanged.
- PostgreSQL runtime/soak, multi-worker and whole-app ORACLE remain open.
