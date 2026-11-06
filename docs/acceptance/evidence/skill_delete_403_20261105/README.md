# Skill-delete 403 journey investigation — evidence

Date: 2026-11-05
Base: `71f9e22b4`
Code checkpoint: `c7e1530a1`

This is the separate finite investigation requested after the PR #664
streaming gate. It does not change skill authority or community-skill
production code.

## Observed failure

Hosted `e2e-journey` on PR #664 (and on current main) failed only:

```
TestSkillsJourney::test_skill_lifecycle
AssertionError: delete failed: 403
1 failed, 210 passed, 1 skipped, 1 xfailed
```

The journey registered a normal user via `/api/auth/register` and then
expected `DELETE /api/skills/{skill_id}` to succeed.

## Real policy trace

`backend/api/skill_routes.py`:

```python
def _require_community_skill_reviewer(db, current_user):
    """Community-skill promote/delete is a TEAM_LEAD+ platform decision."""
    user = db.query(UserModel).filter(UserModel.id == current_user.id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not user_meets_role(user, UserRole.TEAM_LEAD):
        raise HTTPException(
            status_code=403,
            detail="Community skill review requires team_lead or higher",
        )
```

`backend/core/auth_endpoints.py` self-registration:

```python
new_user = User(
    ...
    # SECURITY: ignore the client-supplied role entirely. Self-registration
    # must always create a plain "member"; elevated roles ... only grantable
    # by an existing admin via the admin API.
    role="member",
    status=UserStatus.ACTIVE
)
```

`backend/tests/e2e_ui/fixtures/journey_fixtures.py` creates the journey user
through `/api/auth/register` and returns its JWT. The JWT carries only the
user id; `get_current_user` reads the current role from the DB.

**Conclusion:** the route's 403 is the intended team_lead+ review boundary.
The journey fixture was missing the now-required review authority. This is
not a product regression and does not justify granting every journey user a
broad role.

## Repair

`backend/tests/e2e_ui/tests/test_journey_api_features.py` now exercises both
sides of the contract with the SAME owner and tenant:

1. member delete → **403**, and the skill remains;
2. elevate that owner to `team_lead` in the DB (the existing JWT now carries
   the review authority because the backend reads the role per request);
3. delete → **200/204**, and the skill leaves the owner's list.

No new login, no broad role grant, no production authority change.

The fast contract `backend/tests/test_community_skill_write_contract.py`
gets the same unauthorized member / authorized team-lead twin, and is added
to the backend CI selection.

## Verification

Local scratch full app on `127.0.0.1:18001` with a scratch SQLite DB and
`BYPASS_RATE_LIMIT=1` (no live provider/browser):

| Gate | Result |
| --- | --- |
| `TestSkillsJourney::test_skill_lifecycle` | **1 passed** (`journey-skill-lifecycle-311.log`) |
| Whole `test_journey_api_features.py` | **6 passed** (`journey-api-features-311.log`) |
| `test_community_skill_write_contract.py` | **22 passed** (`skill-contract-311.log`) |
| Updated CI backend selection, Python 3.11 | **606 passed, 1 skipped, 0 failed** (`ci-selection-311.log`) |
| Updated CI backend selection, Python 3.14 | **606 passed, 1 skipped, 0 failed** (`ci-selection-314.log`) |

The local e2e run used `-p no:randomly` only to avoid a local
pytest-randomly/numpy teardown seed conflict; the test itself is the same
gating API journey test.

## Source / artifact hashes

| File | Git blob | SHA-256 |
| --- | --- | --- |
| `backend/tests/e2e_ui/tests/test_journey_api_features.py` | `c344f14657b26cd32533ee102587cda7a1d7042d` | `7de77ff836d3bdbf590ee84a2b112b016d9cdedcf5cd8fecc5d05dd2f55a582b` |
| `backend/tests/test_community_skill_write_contract.py` | `c9b04a20dc6d037b38da5ba927f5c1eb9cee24d5` | `8680d4a322357a20d96fd546923d2b852637967b4bb135d17222d3628a8c4eb1` |
| `.github/workflows/ci.yml` | `c67282f3705b6b6c8d426d615cc66b5f3ac12347` | `14c6056e8367c1564bdbcc89da9cf2118e4a7c263f41f70742f7ab118ff117c0` |
| `backend/api/skill_routes.py` (policy source, unchanged) | `88c669a20ad7f64df46e133fff6ad70f79a6500c` | `527325f2be61dc000aacd5a584e048f4ce9764929b6ca32129d3b777e913a612` |
| `backend/core/security/rbac.py` (policy helper, unchanged) | `671ee154e4f62827a506007e8010c4648cdc5dcb` | `48a7ecdb609f7e32267212e85b1993a0045eb84aca903f0152a8a498bcbd405e` |
| `backend/core/auth_endpoints.py` (member default, unchanged) | `79463ad11e17892eff4c5a12aded1cbbd2ebc618` | `bf7c344519f519a39d68656c7fe687dd8d8befbabb5c2b39959a416231e66105` |

Evidence artifact hashes are in `verification.json`.

## Boundaries

- No broad role grant, no skill-authority relaxation, no production route
  change.
- The existing cross-tenant/global community-skill read behavior is not
  changed here; the authorized positive uses the same owner and tenant.
- No live model/provider/browser/sandbox/credential/spend/send/download or
  deployment operation was used.
