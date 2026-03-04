import asyncio
import uuid
from sqlalchemy.orm import Session
from core.database import SessionLocal
from core.models import AgentRegistry, Skill, Tenant, User
from core.agent_evolution_loop import AgentEvolutionLoop
from unittest.mock import MagicMock, patch

async def run_integration_test():
    """
    Integration test for GEA skill writing using standard asyncio/mock.
    Simulates a GEA cycle where a "CREATE_SKILL:" directive is generated.
    Verifies that a new Skill record is created and linked to the agent's evolved config.
    """
    db: Session = SessionLocal()
    
    try:
        print("--- Starting GEA Skill Creation Integration Test ---")
        # 1. Setup Mock Tenant and Agent
        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(id=str(uuid.uuid4()), name="Test Tenant")
            db.add(tenant)
            db.commit()
            
        user = db.query(User).filter(User.tenant_id == tenant.id).first()
        if not user:
            user = User(id=str(uuid.uuid4()), email="test@example.com", tenant_id=tenant.id)
            db.add(user)
            db.commit()

        agent_id = str(uuid.uuid4())
        agent = AgentRegistry(
            id=agent_id,
            tenant_id=tenant.id,
            name="Test Evolving Agent",
            category="engineering",
            configuration={"system_prompt": "You are a test agent."},
            enabled=True,
            confidence_score=0.8
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        print(f"✓ Mock agent created: {agent_id}")

        # 2. Mock Reflection Service to return a CREATE_SKILL directive
        with patch("core.group_reflection_service.GroupReflectionService.reflect_and_generate_directives") as mock_reflect:
            mock_reflect.return_value = ["CREATE_SKILL: Fetch product inventory from Shopify API"]
            
            # Mock Guardrails and Evaluation to always pass
            with patch("core.agent_evolution_loop.AgentEvolutionLoop._validate_via_guardrails") as mock_guard:
                mock_guard.return_value = True
                with patch("core.agent_evolution_loop.AgentEvolutionLoop._evaluate_evolved_config") as mock_eval:
                    mock_eval.return_value = (0.9, True)
                    
                    # 3. Run Evolution Cycle
                    print("Running evolution cycle...")
                    loop = AgentEvolutionLoop(db)
                    result = await loop.run_evolution_cycle(
                        tenant_id=tenant.id,
                        target_agent_id=agent.id
                    )
                    
                    # 4. Assertions
                    assert result.evolved_agent_id is not None
                    print(f"✓ Evolved agent ID: {result.evolved_agent_id}")
                    
                    # Verify Evolved Agent Config
                    evolved_agent = db.query(AgentRegistry).filter(
                        AgentRegistry.id == result.evolved_agent_id
                    ).first()
                    
                    assert "evolution_history" in evolved_agent.configuration
                    last_history = evolved_agent.configuration["evolution_history"][-1]
                    assert "skill_created" in last_history
                    print(f"✓ Skill creation logged in history: {last_history['skill_created']}")
                    
                    # Verify Skill Record in DB
                    skill_id = evolved_agent.configuration["active_skills"][-1]
                    skill = db.query(Skill).filter(Skill.id == skill_id).first()
                    assert skill is not None
                    assert "Shopify" in skill.name or "evolved_skill" in skill.name
                    assert skill.tenant_id == tenant.id
                    print(f"✓ Skill record verified in DB: {skill.name} ({skill.id})")
                    
                    print(f"\n✅ SUCCESS: Successfully verified GEA skill creation.")

    except Exception as e:
        print(f"\n❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        raise e
    finally:
        # Cleanup
        try:
            print("Cleaning up...")
            db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).delete()
            # Potential skills created (we search by name or prefix if we didn't store IDs perfectly)
            db.query(Skill).filter(Skill.tenant_id == tenant.id).delete()
            db.commit()
        except:
            pass
        db.close()

if __name__ == "__main__":
    asyncio.run(run_integration_test())
