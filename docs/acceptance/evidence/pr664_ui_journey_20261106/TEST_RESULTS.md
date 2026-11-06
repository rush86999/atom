# PR #664 non-gating UI journey — test results

Executed source: `83dc39c458a9fe4cb60d8e24cfd3f5fbe4ba25f8`  
Prior fixture commit: `437302cff25594d640d3feedf5d8b4c698113ee3`  
Accepted PR #664 head: `d17acd1d58ed0f743322314ef08e6888cb12c83a`

## Original capture

`before-pr664-ui-block.log` — run `42161362480`, job `127707566246`, head
`d17acd1d5`:

```
test_journey_ui_features.py .FF.FFFFF
test_journey_page_smoke.py F ... .......FF......F.
test_user_journey.py F
============ 12 failed, 16 passed, 57 warnings in 225.73s ============
```

Failing node IDs:

- `TestChatUI::test_chat_composer_loaded`
- `TestChatUI::test_chat_send_message_persists_in_input`
- `TestMarketplaceUI::test_marketplace_renders_and_searches`
- `TestWorkflowBuilderUI::test_builder_renders_and_accepts_name`
- `TestProjectsUI::test_project_command_center_renders`
- `TestIntegrationsHubUI::test_integrations_hub_renders`
- `TestSettingsUI::test_theme_persists_across_reload`
- page smoke `/dashboard`, `/marketplace`, `/dashboards/projects`, `/integrations`
- `TestCanonicalUserJourney::test_full_journey_login_to_logout`

The affected page-object/test files are unchanged between PR base
`71f9e22b4` and PR #664 head; these are pre-existing expectation drifts
against earlier product changes.

## Final hosted run

`after-pr664-ui-block.log` — run `42209447032`, job `127864183212`, head
`83dc39c45`:

```
tests/test_journey_ui_features.py .........   [ 32%]
tests/test_journey_page_smoke.py ................. [100%]
tests/test_user_journey.py .
================= 28 passed, 57 warnings in 206.37s ==================

tests/test_journey_role_ui.py ........................................
================= 40 passed, 81 warnings in 132.81s ==================
```

Gating API journey: `211 passed, 1 skipped, 1 xfailed`.

## Required checks

`final-checks.log` records run `42209447032`:

| Check | Result |
|---|---|
| backend-tests | pass 5m29s |
| e2e-journey | pass 13m5s |
| syntax-gate | pass |
| frontend-typecheck | pass |
| full-app-boots | pass |
| quickstart | pass |
| docker-build | pass |
| GitGuardian Security Checks | pass |

## Local static check

`py-compile.log` — affected page objects, fixtures and UI journey test files
compile with Python 3.11; exit 0.

## Scope

Test/page-object only. No runtime product, provider, role, onboarding or
product-profile behavior changed. No live model/provider/browser account,
credential, spend, send, download or deployment operation. No merge or
deploy.
