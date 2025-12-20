
import asyncio
import os
import sys
from datetime import datetime, timedelta
import uuid

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.database import SessionLocal, engine
from core.models import User, Team, team_members, Base
from sqlalchemy import or_, delete, select
from core.stakeholder_engine import get_stakeholder_engine
from integrations.atom_communication_ingestion_pipeline import memory_manager, CommunicationData

async def verify_stakeholder_detection():
    print("🚀 Starting Silent Stakeholder Detection Verification...")
    
    # 1. Setup Database
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    test_user_id = str(uuid.uuid4())
    stakeholder_email = "silent.bob@example.com"
    
    try:
        # Cleanup existing test data if any
        db.execute(team_members.delete().where(team_members.c.user_id.in_(
            select(User.id).where(User.email.in_(["test_agent@example.com", stakeholder_email]))
        )))
        db.execute(delete(User).where(User.email.in_(["test_agent@example.com", stakeholder_email])))
        db.commit()

        # Create test user
        user = User(id=test_user_id, email="test_agent@example.com", first_name="Test", last_name="Agent")
        db.add(user)
        
        # Create stakeholder user
        stakeholder = User(id=str(uuid.uuid4()), email=stakeholder_email, first_name="Silent", last_name="Bob")
        db.add(stakeholder)
        
        # Create team
        team = Team(id=str(uuid.uuid4()), name="Test Team", workspace_id="test_ws")
        db.add(team)
        db.commit()
        
        # Add both to team
        db.execute(team_members.insert().values(user_id=test_user_id, team_id=team.id, role="member"))
        db.execute(team_members.insert().values(user_id=stakeholder.id, team_id=team.id, role="member"))
        db.commit()
        
        print(f"✅ Created test user {test_user_id} and stakeholder {stakeholder_email} in a team.")
        
        # 2. Setup Communication History
        memory_manager.initialize()
        
        # Clear existing for safety in test
        try:
            memory_manager.connections_table.delete(f"sender = '{stakeholder_email}' OR recipient = '{stakeholder_email}'")
        except:
            pass
            
        # Add an old interaction (5 days ago)
        five_days_ago = datetime.utcnow() - timedelta(days=5)
        comm = CommunicationData(
            id=f"test_{uuid.uuid4()}",
            app_type="slack",
            timestamp=five_days_ago,
            direction="inbound",
            sender=stakeholder_email,
            recipient="user",
            subject="Old Project Update",
            content="Hey, just wanted to let you know the design is ready.",
            attachments=[],
            metadata={},
            status="completed",
            priority="normal",
            tags=["design"]
        )
        
        memory_manager.ingest_communication(comm)
        print(f"✅ Ingested old communication from {stakeholder_email} (5 days ago).")
        
        # 3. Run Detection
        engine_inst = get_stakeholder_engine()
        silent_list = await engine_inst.identify_silent_stakeholders(test_user_id)
        
        print(f"🔍 Detection Results: Found {len(silent_list)} silent stakeholders.")
        for s in silent_list:
            print(f"   - {s['name']} ({s['email']}): {s['days_since']} days silent. Outreach: {s['suggested_outreach']}")
            
        # 4. Assertions
        assert any(s["email"] == stakeholder_email for s in silent_list), "Stakeholder should be detected as silent"
        
        # 5. Add a recent interaction and verify they are NO LONGER silent
        recent_comm = CommunicationData(
            id=f"test_{uuid.uuid4()}",
            app_type="slack",
            timestamp=datetime.utcnow(),
            direction="inbound",
            sender=stakeholder_email,
            recipient="user",
            subject="Recent Ping",
            content="Actually, I have one more update!",
            attachments=[],
            metadata={},
            status="completed",
            priority="normal",
            tags=["design"]
        )
        memory_manager.ingest_communication(recent_comm)
        print(f"✅ Ingested recent communication from {stakeholder_email} (Just now).")
        
        silent_list_updated = await engine_inst.identify_silent_stakeholders(test_user_id)
        assert not any(s["email"] == stakeholder_email for s in silent_list_updated), "Stakeholder should NOT be detected as silent after recent interaction"
        
        print("✅ VERIFICATION SUCCESSFUL: Silent stakeholder detection is working correctly!")
        
    finally:
        # Cleanup
        db.execute(team_members.delete().where(or_(team_members.c.user_id == test_user_id, team_members.c.user_id == stakeholder.id)))
        db.delete(user)
        db.delete(stakeholder)
        db.delete(team)
        db.commit()
        db.close()
        try:
            memory_manager.connections_table.delete(f"sender = '{stakeholder_email}' OR recipient = '{stakeholder_email}'")
        except:
            pass

if __name__ == "__main__":
    asyncio.run(verify_stakeholder_detection())
