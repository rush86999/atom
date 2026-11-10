# Supervisor directory route restoration — evidence packet

Packet: `docs/acceptance/evidence/web_presence_supervisor_route_repair_31bd7f607/`

## Regression

PR820 presence patch at `a90e77bf8` accidentally deleted the baseline
`GET /api/users/available-supervisors` endpoint from
`backend/api/user_activity_routes.py`, while retaining
`AvailableSupervisorsResponse` and the unchanged
`UserActivityService.get_available_supervisors` method.

Root independent public-API controls at `a90`:

- guest → expected 403, actual 404
- member → expected 200, actual 404
- `actual_exit 1`, `same_source true`

The CI guest failure and root negative are preserved in
`root_controls/root_supervisors_route_negative_*`.

## Repair

Restored the exact baseline endpoint block from `750f` lines 295–335, before
the dynamic `/{user_id}/activity/sessions` route:

- path `/available-supervisors` under the existing `/api/users` router;
- `USER_VIEW` dependency (`require_permission(Permission.USER_VIEW)`);
- existing body with optional `category`, service call and
  `AvailableSupervisorsResponse(supervisors, total_count)`;
- existing 500 internal-error behavior.

No permission broadening, new engine, alternate contract, router or store.

## Deletion trace

Compared every baseline/current `@router` decorator path in the file:

- baseline 7 routes, current 7 routes after restore;
- no other missing route;
- service method and all callers unchanged;
- original presence override/CAS/replay tests untouched.

## Gates

| Gate | Result | Log |
|---|---|---|
| Root supervisor route controls locally | 2 passed (guest 403/member 200) | `gates/root_supervisor_route_probe_2.proof` |
| Original activity/public-API selection + new route twins | 64 passed | `gates/activity_public_api_64.proof` |
| Stale old mock route suite | 19 failed / 16 passed, pre-existing mock mismatch | `gates/old_route_mock_suite_stale_failures.proof` |

The old `tests/api/test_user_activity_routes.py` uses a Mock DB with no User row
and a FakeUser lacking scope, while the presence repair’s verified actor
resolution requires the actual actor row. Those failures are independent of
the restored supervisor endpoint (all four supervisor tests in that file pass)
and are reported, not weakened or skipped. The original 62-control selection
(which uses the real scratch world) plus the two new route twins passes at 64.

## Boundaries

- No CI YAML/ledger edits; root owns PR820 integration/final merge.
- No live DB, provider/model, browser, credential, spend or deployment.
- Original `docs/acceptance/evidence/web_presence_override_20261110/` packet
  (29 artifacts) remains unchanged.
- This is a bounded route restoration, not whole-app ORACLE acceptance.
