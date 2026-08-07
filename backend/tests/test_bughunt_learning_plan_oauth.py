"""TDD bug-hunt: learning-plan Notion token lookup (R80 follow-up).

``api/learning_plan_routes`` queried ``OAuthToken`` (the OAuth-server model —
no ``provider`` column) for the user's Notion token. Notion credentials live
in ``IntegrationToken`` (encrypted), so every learning-plan creation with a
``notion_database_id`` raised AttributeError and Notion export never worked.
"""
from __future__ import annotations

import inspect


def test_learning_plan_notion_lookup_uses_integration_token():
    import api.learning_plan_routes as mod

    src = inspect.getsource(mod)
    assert "IntegrationToken" in src, (
        "learning_plan_routes must query IntegrationToken for Notion tokens"
    )
    assert "OAuthToken.provider" not in src, (
        "OAuthToken has no provider column — stale query crashes every export"
    )
