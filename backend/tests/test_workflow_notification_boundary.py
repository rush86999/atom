"""Tests for the reusable in-app workflow-step delivery boundary.

These use the real SQLAlchemy models/tables rather than a hand-rolled row
writer. The in-memory database is a synthetic fixture for this packet; in a
full checkout the same assertions run against the existing DB fixture by
constructing ``NotificationService`` with that session.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.append(os.getcwd())

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core import notification_service as notification_service_module
from core.models import (
    Base,
    Notification,
    Tenant,
    User,
    UserStatus,
    Workspace,
    user_workspaces,
)
from core.notification_service import NotificationService


class WorkflowNotificationBoundaryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(
            bind=self.engine,
            tables=[
                Tenant.__table__,
                Workspace.__table__,
                User.__table__,
                user_workspaces,
                Notification.__table__,
            ],
        )
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self._seed_scope()
        self.service = NotificationService(self.db)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _seed_scope(self):
        tenant = Tenant(
            id="tenant-1",
            name="Tenant One",
            subdomain="tenant-one",
            edition="personal",
            is_active=True,
        )
        other_tenant = Tenant(
            id="tenant-2",
            name="Tenant Two",
            subdomain="tenant-two",
            edition="personal",
            is_active=True,
        )
        workspace = Workspace(
            id="workspace-1",
            name="Workspace One",
            tenant_id="tenant-1",
            status="active",
        )
        # Same tenant, but not the user's workspace.
        sibling_workspace = Workspace(
            id="workspace-sibling",
            name="Sibling Workspace",
            tenant_id="tenant-1",
            status="active",
        )
        # A real workspace, but in another tenant.
        other_workspace = Workspace(
            id="workspace-2",
            name="Workspace Two",
            tenant_id="tenant-2",
            status="active",
        )
        user = User(
            id="user-1",
            tenant_id="tenant-1",
            workspace_id="workspace-1",
            email="user1@example.com",
            first_name="Test",
            last_name="User",
            role="member",
            status=UserStatus.ACTIVE.value,
            is_active=True,
        )
        # Authorised only through user_workspaces (no direct User.workspace_id).
        membership_user = User(
            id="user-2",
            tenant_id="tenant-1",
            workspace_id=None,
            email="user2@example.com",
            first_name="Member",
            last_name="User",
            role="member",
            status=UserStatus.ACTIVE.value,
            is_active=True,
        )
        self.db.add_all([
            tenant,
            other_tenant,
            workspace,
            sibling_workspace,
            other_workspace,
            user,
            membership_user,
        ])
        self.db.flush()
        self.db.execute(
            user_workspaces.insert().values(
                user_id="user-2",
                workspace_id="workspace-1",
            )
        )
        self.db.commit()

    async def _send(self, **overrides):
        values = {
            "user_id": "user-1",
            "workspace_id": "workspace-1",
            "tenant_id": "tenant-1",
            "operation_id": "exec-100:step-1",
            "title": "Workflow step complete",
            "message": "Step 1 completed successfully.",
        }
        values.update(overrides)
        return await self.service.send_workflow_notification(**values)

    async def test_insert_persists_in_app_row(self):
        result = await self._send()

        self.assertTrue(result["success"])
        self.assertEqual(result["notification_id"], "exec-100:step-1")
        self.assertTrue(result["created"])
        self.assertFalse(result["emailed"])

        row = (
            self.db.query(Notification)
            .filter(Notification.id == "exec-100:step-1")
            .one()
        )
        self.assertEqual(row.user_id, "user-1")
        self.assertEqual(row.workspace_id, "workspace-1")
        self.assertEqual(row.tenant_id, "tenant-1")
        self.assertEqual(row.title, "Workflow step complete")
        self.assertEqual(row.message, "Step 1 completed successfully.")
        self.assertEqual(row.metadata_json["operation_id"], "exec-100:step-1")
        self.assertFalse(row.read)

    async def test_matching_replay_returns_same_notification_id(self):
        first = await self._send()
        second = await self._send()

        self.assertTrue(first["success"])
        self.assertTrue(second["success"])
        self.assertEqual(first["notification_id"], second["notification_id"])
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(
            self.db.query(Notification)
            .filter(Notification.id == "exec-100:step-1")
            .count(),
            1,
        )

    async def test_conflicting_operation_material_is_refused(self):
        first = await self._send()
        conflict = await self._send(title="Different title")

        self.assertTrue(first["success"])
        self.assertFalse(conflict["success"])
        self.assertIsNone(conflict["notification_id"])
        self.assertEqual(conflict["error"], "operation_conflict")

        rows = self.db.query(Notification).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].title, "Workflow step complete")

    async def test_wrong_workspace_scope_is_refused(self):
        result = await self._send(workspace_id="workspace-sibling")

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "workspace_scope_mismatch")
        self.assertEqual(self.db.query(Notification).count(), 0)

    async def test_wrong_tenant_scope_is_refused(self):
        result = await self._send(
            workspace_id="workspace-2",
            tenant_id="tenant-2",
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "tenant_scope_mismatch")
        self.assertEqual(self.db.query(Notification).count(), 0)

    async def test_inactive_recipient_is_refused(self):
        user = self.db.query(User).filter(User.id == "user-1").one()
        user.status = UserStatus.SUSPENDED.value
        self.db.commit()

        result = await self._send()

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "recipient_inactive")
        self.assertEqual(self.db.query(Notification).count(), 0)

    def _stale_then_real_scope_check(self):
        """Patch the advisory pre-check to observe pre-revocation authority.

        The first call (the explicit pre-check) reports the old, authorised
        state. Later calls (the post-denial diagnostic) use the real check.
        This models the check-then-act window the conditional INSERT must
        close, without relying on timing.
        """
        real_check = notification_service_module._workflow_scope_error
        calls = {"count": 0}

        def check(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                return None
            return real_check(*args, **kwargs)

        return mock.patch.object(
            notification_service_module,
            "_workflow_scope_error",
            side_effect=check,
        )

    async def test_membership_recipient_without_direct_workspace_is_allowed(self):
        result = await self._send(
            user_id="user-2",
            operation_id="exec-membership:step-1",
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["created"])
        row = (
            self.db.query(Notification)
            .filter(Notification.id == "exec-membership:step-1")
            .one()
        )
        self.assertEqual(row.user_id, "user-2")
        self.assertEqual(row.workspace_id, "workspace-1")

    async def test_membership_revoked_after_precheck_cannot_insert(self):
        # The pre-check passes, then a separate committed transaction removes
        # the only proof of workspace membership before the INSERT runs. The
        # insert itself must re-evaluate authority and write nothing.
        with self._stale_then_real_scope_check():
            self.db.execute(
                user_workspaces.delete().where(
                    user_workspaces.c.user_id == "user-2",
                    user_workspaces.c.workspace_id == "workspace-1",
                )
            )
            self.db.commit()
            result = await self._send(
                user_id="user-2",
                operation_id="exec-revoked:step-1",
            )

        self.assertFalse(result["success"])
        self.assertIsNone(result["notification_id"])
        self.assertEqual(result["error"], "workspace_scope_mismatch")
        self.assertEqual(self.db.query(Notification).count(), 0)

    async def test_recipient_deactivated_after_precheck_cannot_insert(self):
        with self._stale_then_real_scope_check():
            user = self.db.query(User).filter(User.id == "user-1").one()
            user.status = UserStatus.SUSPENDED.value
            self.db.commit()
            result = await self._send(
                operation_id="exec-suspended:step-1",
            )

        self.assertFalse(result["success"])
        self.assertIsNone(result["notification_id"])
        self.assertEqual(result["error"], "recipient_inactive")
        self.assertEqual(self.db.query(Notification).count(), 0)

    async def test_blank_scope_is_not_defaulted(self):
        result = await self._send(tenant_id="")

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "invalid_arguments")
        self.assertEqual(self.db.query(Notification).count(), 0)

    async def test_replay_from_another_session_reads_committed_row(self):
        first = await self._send()
        self.db.commit()

        other_db = self.Session()
        try:
            replay_service = NotificationService(other_db)
            replay = await replay_service.send_workflow_notification(
                user_id="user-1",
                workspace_id="workspace-1",
                tenant_id="tenant-1",
                operation_id="exec-100:step-1",
                title="Workflow step complete",
                message="Step 1 completed successfully.",
            )
        finally:
            other_db.close()

        self.assertTrue(replay["success"])
        self.assertFalse(replay["created"])
        self.assertEqual(replay["notification_id"], first["notification_id"])


if __name__ == "__main__":
    unittest.main()
