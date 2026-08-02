"""
Round 70 — B1 regression: budget enforcement notification never delivered.

budget_enforcement_service._send_enforcement_notification called
NotificationService.send_notification with 7 kwargs vs the real 3-arg signature
(user_id, notification_type, data) -> TypeError swallowed by the outer except,
so NO enforcement notification ever reached admins. This test pins the fix.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from core.budget_enforcement_service import (
    BudgetEnforcementMode,
    BudgetEnforcementService,
)


def test_send_enforcement_notification_uses_3arg_signature():
    db = MagicMock()
    service = BudgetEnforcementService.__new__(BudgetEnforcementService)
    service.db = db
    service.notification_service = MagicMock()
    service.notification_service.send_notification = AsyncMock(return_value=None)

    admin = MagicMock()
    admin.id = "u-admin"
    admin.tenant_id = "t-1"
    workspace = MagicMock()
    workspace.id = "ws-1"

    def query_side_effect(model, *a, **k):
        q = MagicMock()
        name = getattr(model, "__name__", str(model))
        if name == "User":
            # Role-based admin query + tenant-owner fallback.
            q.filter.return_value.all.return_value = [admin]
            q.filter.return_value.limit.return_value.all.return_value = [admin]
        elif name == "Workspace":
            q.filter.return_value.first.return_value = workspace
        else:
            q.all.return_value = []
        return q

    db.query.side_effect = query_side_effect

    result = asyncio.run(
        service._send_enforcement_notification(
            tenant_id="t-1",
            mode=BudgetEnforcementMode.HARD_STOP,
            current_spend=120.0,
            budget_limit=100.0,
            utilization_percent=120.0,
            details="Hard stop triggered",
        )
    )

    assert result is True
    # Exactly one call; positional user_id + notification_type + data dict.
    service.notification_service.send_notification.assert_awaited_once()
    call = service.notification_service.send_notification.await_args
    args, kwargs = call.args, call.kwargs
    assert kwargs == {}  # no leftover 7-kwarg style
    assert args[0] == "u-admin"
    assert args[1] == "budget_enforcement"
    assert isinstance(args[2], dict)
    assert args[2]["metadata"]["enforcement_mode"] == BudgetEnforcementMode.HARD_STOP
    assert args[2]["title"] == "Budget Enforcement: Hard Stop Active"
