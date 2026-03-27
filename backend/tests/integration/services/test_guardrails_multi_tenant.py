import pytest
from sqlalchemy.orm import Session
from core.autonomous_guardrails import AutonomousGuardrailService
from core.models import AgentRegistry, TokenUsage, AgentStatus
from datetime import datetime, timezone, timedelta

def test_guardrails_tenant_isolation(db_session: Session):
    # 1. Setup two agents in different tenants
    agent1 = AgentRegistry(
        id="agent-t1",
        name="Agent T1",
        workspace_id="ws-1",
        tenant_id="tenant-1",
        status=AgentStatus.AUTONOMOUS.value,
        category="Test",
        module_path="test.path",
        class_name="TestAgent",
        configuration={"guardrails": {"max_actions_per_hour": 5}}
    )
    agent2 = AgentRegistry(
        id="agent-t2",
        name="Agent T2",
        workspace_id="ws-2",
        tenant_id="tenant-2",
        status=AgentStatus.AUTONOMOUS.value,
        category="Test",
        module_path="test.path",
        class_name="TestAgent",
        configuration={"guardrails": {"max_actions_per_hour": 5}}
    )
    db_session.add(agent1)
    db_session.add(agent2)
    db_session.commit()

    # 2. Add some usage for tenant 1
    for _ in range(3):
        usage = TokenUsage(
            agent_id="agent-t1",
            workspace_id="ws-1",
            tenant_id="tenant-1",
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.01,
            timestamp=datetime.now(timezone.utc)
        )
        db_session.add(usage)
    db_session.commit()

    # 3. Check guardrails for tenant 1 (should pass: 3 < 5)
    gs1 = AutonomousGuardrailService(db_session, workspace_id="ws-1", tenant_id="tenant-1")
    res1 = gs1.check_guardrails("agent-t1", "test_action", {})
    assert res1["proceed"] is True

    # 4. Add more usage for tenant 1 to hit limit
    for _ in range(3):
        usage = TokenUsage(
            agent_id="agent-t1",
            workspace_id="ws-1",
            tenant_id="tenant-1",
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.01,
            timestamp=datetime.now(timezone.utc)
        )
        db_session.add(usage)
    db_session.commit()

    res1_hit = gs1.check_guardrails("agent-t1", "test_action", {})
    assert res1_hit["proceed"] is False
    assert "Rate limit exceeded" in res1_hit["reason"]

    # 5. Check guardrails for tenant 2 (should still pass: 0 usage)
    gs2 = AutonomousGuardrailService(db_session, workspace_id="ws-2", tenant_id="tenant-2")
    res2 = gs2.check_guardrails("agent-t2", "test_action", {})
    assert res2["proceed"] is True
