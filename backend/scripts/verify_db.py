"""
Database Persistence Verification Script
Tests that database operations work correctly and data persists across sessions
"""

import asyncio
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from sqlalchemy import select

from core.database_manager import db_manager
from core.enterprise_security import (
    AuditEvent,
    EventType,
    SecurityLevel,
    ThreatLevel,
    enterprise_security,
)
from core.enterprise_user_management import (
    TeamCreate,
    UserCreate,
    WorkspaceCreate,
    enterprise_user_mgmt,
)
from core.models import AuditLog as AuditLogModel, User as UserModel, Workspace as WorkspaceModel


async def test_database_persistence():
    """Test database persistence"""
    print("=" * 60)
    print("DATABASE PERSISTENCE VERIFICATION")
    print("=" * 60)
    
    # Initialize database
    print("\n1. Initializing database connection...")
    try:
        await db_manager.initialize()
        print(f"   ✓ Database connected: {db_manager.check_connection()}")
    except Exception as e:
        print(f"   ✗ Failed to connect: {str(e)}")
        return False

    try:
        # Create a session
        async for session in db_manager.get_session():
            print("\n2. Testing Workspace creation...")
            workspace_data = WorkspaceCreate(
                name="Test Corporation",
                description="Verification test workspace",
                plan_tier="enterprise"
            )
            workspace = await enterprise_user_mgmt.create_workspace(session, workspace_data)
            print(f"   ✓ Created workspace: {workspace.name} (ID: {workspace.id})")
            workspace_id = workspace.id

            print("\n3. Testing User creation...")
            # Use timestamp to ensure unique email
            test_email = f"test+{int(datetime.now().timestamp())}@example.com"
            user_data = UserCreate(
                email=test_email,
                first_name="Test",
                last_name="User",
                workspace_id=workspace_id
            )
            user = await enterprise_user_mgmt.create_user(session, user_data)
            print(f"   ✓ Created user: {user.email} (ID: {user.id})")
            user_id = user.id

            print("\n4. Testing Team creation...")
            team_data = TeamCreate(
                name="Engineering",
                description="Test team",
                workspace_id=workspace_id
            )
            team = await enterprise_user_mgmt.create_team(session, team_data)
            print(f"   ✓ Created team: {team.name} (ID: {team.id})")
            team_id = team.id

            print("\n5. Testing User-Team association...")
            result = await enterprise_user_mgmt.add_user_to_team(session, user_id, team_id)
            print(f"   ✓ Added user to team: {result}")

            print("\n6. Testing Audit Log creation...")
            audit_event = AuditEvent(
                event_type=EventType.USER_CREATED,
                security_level=SecurityLevel.LOW,
                threat_level=ThreatLevel.NORMAL,
                user_id=user_id,
                user_email=user.email,
                workspace_id=workspace_id,
                action="create_user",
                description="Test user created for verification",
                success=True
            )
            event_id = await enterprise_security.log_audit_event(session, audit_event)
            print(f"   ✓ Created audit log: {event_id}")

            print("\n7. Verifying data persistence...")
            
            # Check workspace
            db_workspace = await enterprise_user_mgmt.get_workspace(session, workspace_id)
            assert db_workspace is not None, "Workspace not found"
            print(f"   ✓ Workspace persisted: {db_workspace.name}")

            # Check user
            db_user = await enterprise_user_mgmt.get_user(session, user_id)
            assert db_user is not None, "User not found"
            print(f"   ✓ User persisted: {db_user.email}")

            # Check team
            db_team = await enterprise_user_mgmt.get_team(session, team_id)
            assert db_team is not None, "Team not found"
            print(f"   ✓ Team persisted: {db_team.name}")

            # Check team members
            team_users = await enterprise_user_mgmt.get_users_in_team(session, team_id)
            assert len(team_users) == 1, "Team member not found"
            print(f"   ✓ Team membership persisted: {len(team_users)} members")

            # Check audit log
            result = await session.execute(select(AuditLogModel).where(AuditLogModel.id == event_id))
            db_audit = result.scalar_one_or_none()
            assert db_audit is not None, "Audit log not found"
            print(f"   ✓ Audit log persisted: {db_audit.description}")

            print("\n8. Testing statistics...")
            stats = await enterprise_user_mgmt.get_enterprise_stats(session)
            print(f"   ✓ Total users: {stats['total_users']}")
            print(f"   ✓ Total workspaces: {stats['total_workspaces']}")
            print(f"   ✓ Total teams: {stats['total_teams']}")

            security_stats = await enterprise_security.get_security_stats(session)
            print(f"   ✓ Total audit events: {security_stats['total_audit_events']}")

            print("\n" + "=" * 60)
            print("✓ ALL TESTS PASSED - DATABASE PERSISTENCE VERIFIED")
            print("=" * 60)
            return True

    except Exception as e:
        print(f"\n✗ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await db_manager.close()
        print("\nDatabase connection closed.")


if __name__ == "__main__":
    result = asyncio.run(test_database_persistence())
    sys.exit(0 if result else 1)
