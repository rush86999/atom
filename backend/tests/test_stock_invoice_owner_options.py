"""Focused synthetic tests for the stock invoice account-owner options read.

The endpoint is exercised directly with an in-memory SQLAlchemy database so the
tests pin scope derivation, active exact-workspace eligibility, output shape and
deterministic ordering without running the wider workflow stack.
"""
import os
import sys
import types
import unittest

sys.path.append(os.getcwd())

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import (
    Base,
    Notification,
    Tenant,
    User,
    UserStatus,
    Workspace,
    user_workspaces,
)
from core.workflow_endpoints import (
    get_stock_invoice_account_owner_options,
    router,
)

OPTIONS_PATH = "/workflows/htn_invoice_followup/account-owner-options"


class StockInvoiceOwnerOptionsTests(unittest.IsolatedAsyncioTestCase):
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

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _user(
        self,
        user_id,
        *,
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        first_name="",
        last_name="",
        status=UserStatus.ACTIVE.value,
        is_active=True,
    ):
        return User(
            id=user_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            email=f"{user_id}@example.com",
            first_name=first_name,
            last_name=last_name,
            role="member",
            status=status,
            is_active=is_active,
        )

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
        sibling_workspace = Workspace(
            id="workspace-sibling",
            name="Sibling Workspace",
            tenant_id="tenant-1",
            status="active",
        )
        other_workspace = Workspace(
            id="workspace-2",
            name="Workspace Two",
            tenant_id="tenant-2",
            status="active",
        )
        self.principal = self._user(
            "user-owner", first_name="Maya", last_name="Owner")
        direct_member = self._user(
            "user-z", first_name="Zoe", last_name="Zulu")
        membership_member = self._user(
            "user-a",
            workspace_id=None,
            first_name="Alice",
            last_name="Able",
        )
        nameless_member = self._user("user-3")
        inactive_member = self._user(
            "user-inactive",
            first_name="Ina",
            last_name="Inactive",
            status=UserStatus.SUSPENDED.value,
        )
        sibling_member = self._user(
            "user-sibling",
            workspace_id="workspace-sibling",
            first_name="Sam",
            last_name="Sibling",
        )
        cross_tenant_member = self._user(
            "user-cross-tenant",
            tenant_id="tenant-2",
            workspace_id="workspace-1",
            first_name="Cara",
            last_name="Cross",
        )
        self.db.add_all([
            tenant,
            other_tenant,
            workspace,
            sibling_workspace,
            other_workspace,
            self.principal,
            direct_member,
            membership_member,
            nameless_member,
            inactive_member,
            sibling_member,
            cross_tenant_member,
        ])
        self.db.flush()
        self.db.execute(
            user_workspaces.insert().values(
                user_id="user-a",
                workspace_id="workspace-1",
            )
        )
        self.db.commit()

    async def _options(self, user=None):
        return await get_stock_invoice_account_owner_options(
            user=user or self.principal,
            db=self.db,
        )

    async def test_returns_only_active_exact_workspace_recipients(self):
        options = await self._options()

        self.assertEqual(
            [option["user_id"] for option in options],
            ["user-a", "user-owner", "user-3", "user-z"],
        )
        self.assertEqual(
            [option["display_label"] for option in options],
            ["Alice Able", "Maya Owner", "user-3", "Zoe Zulu"],
        )
        for option in options:
            self.assertEqual(
                set(option), {"user_id", "display_label"})
        self.assertNotIn(
            "user-inactive", [option["user_id"] for option in options])
        self.assertNotIn(
            "user-sibling", [option["user_id"] for option in options])
        self.assertNotIn(
            "user-cross-tenant", [option["user_id"] for option in options])
        self.assertEqual(self.db.query(Notification).count(), 0)

    async def test_missing_principal_scope_fails_closed_without_defaults(self):
        cases = [
            (None, "workspace-1"),
            ("tenant-1", None),
            ("", "workspace-1"),
            ("tenant-1", ""),
        ]
        for tenant_id, workspace_id in cases:
            with self.subTest(tenant_id=tenant_id, workspace_id=workspace_id):
                principal = types.SimpleNamespace(
                    id="user-owner",
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                )
                with self.assertRaises(HTTPException) as raised:
                    await self._options(user=principal)
                self.assertEqual(raised.exception.status_code, 403)

    async def test_principal_outside_exact_workspace_fails_closed(self):
        # The DB row keeps its own workspace (workspace-sibling); the trusted
        # principal claims workspace-1 without an explicit membership there.
        # Scope comes from the principal, while the DB independently proves
        # the claimed workspace membership is absent.
        sibling_principal = types.SimpleNamespace(
            id="user-sibling",
            tenant_id="tenant-1",
            workspace_id="workspace-1",
        )

        with self.assertRaises(HTTPException) as raised:
            await self._options(user=sibling_principal)

        self.assertEqual(raised.exception.status_code, 403)

    async def test_sibling_own_workspace_returns_its_roster(self):
        sibling_principal = types.SimpleNamespace(
            id="user-sibling",
            tenant_id="tenant-1",
            workspace_id="workspace-sibling",
        )

        options = await self._options(user=sibling_principal)

        self.assertEqual(
            [option["user_id"] for option in options],
            ["user-sibling"],
        )
        self.assertEqual(
            [option["display_label"] for option in options],
            ["Sam Sibling"],
        )
        self.assertEqual(self.db.query(Notification).count(), 0)

    async def test_inactive_principal_fails_closed(self):
        inactive = (
            self.db.query(User)
            .filter(User.id == "user-inactive")
            .one()
        )

        with self.assertRaises(HTTPException) as raised:
            await self._options(user=inactive)

        self.assertEqual(raised.exception.status_code, 403)

    async def test_membership_only_principal_is_eligible_until_revoked(self):
        # The DB row intentionally has no direct workspace_id; only the
        # explicit membership row proves workspace-1. The trusted fixture
        # principal supplies the authenticated tenant/workspace scope.
        membership_principal = types.SimpleNamespace(
            id="user-a",
            tenant_id="tenant-1",
            workspace_id="workspace-1",
        )

        allowed = await self._options(user=membership_principal)
        self.assertIn(
            "user-a", [option["user_id"] for option in allowed])

        self.db.execute(
            user_workspaces.delete().where(
                user_workspaces.c.user_id == "user-a",
                user_workspaces.c.workspace_id == "workspace-1",
            )
        )
        self.db.commit()

        with self.assertRaises(HTTPException) as raised:
            await self._options(user=membership_principal)
        self.assertEqual(raised.exception.status_code, 403)

        roster = await self._options()
        self.assertNotIn("user-a", [option["user_id"] for option in roster])

    def test_route_is_registered_as_a_get_on_the_workflows_router(self):
        matches = [
            route for route in router.routes
            if getattr(route, "path", None) == OPTIONS_PATH
        ]

        self.assertEqual(len(matches), 1)
        self.assertIn("GET", matches[0].methods)


if __name__ == "__main__":
    unittest.main()
