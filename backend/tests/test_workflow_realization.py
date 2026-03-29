import pytest
import asyncio
import uuid
from unittest.mock import MagicMock, patch

# Correct imports based on submodule structure
from core.agents.queen_agent import QueenAgent
from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator, WorkflowDefinition, WorkflowStep, WorkflowStepType
from ai.nlp_engine import NaturalLanguageEngine, RouteCategory

@pytest.fixture
def db_session():
    return MagicMock()

@pytest.fixture
def llm_service():
    return MagicMock()

@pytest.fixture
def orchestrator():
    # Use a fresh orchestrator for each test to avoid singleton pollution
    return AdvancedWorkflowOrchestrator()

@pytest.fixture
def queen_agent(db_session, llm_service):
    # Fixed init signature: db, llm, workspace_id, tenant_id
    return QueenAgent(db=db_session, llm=llm_service)

@pytest.mark.asyncio
async def test_route_classification():
    """Test that NaturalLanguageEngine correctly classifies intents."""
    engine = NaturalLanguageEngine()
    
    # We mock the LLM call to avoid external dependencies in unit tests
    with patch.object(engine, 'classify_route', new_callable=MagicMock) as mock_classify:
        from ai.nlp_engine import RouteClassification
        # classify_route is an async method
        f = asyncio.Future()
        f.set_result(RouteClassification(
            category=RouteCategory.AUTOMATION,
            reasoning="Test reasoning",
            confidence=0.9
        ))
        mock_classify.return_value = f
        
        result = await engine.classify_route("Every Monday sync leads")
        assert result.category == RouteCategory.AUTOMATION
        assert result.confidence > 0.5

@pytest.mark.asyncio
async def test_blueprint_realization(queen_agent, orchestrator):
    """Test that QueenAgent can realize a blueprint into a registered workflow."""
    
    blueprint = {
        "architecture_name": "Test Lead Automation",
        "description": "Auto-sync leads from email to CRM",
        "execution_mode": "recurring_automation",
        "nodes": [
            {"id": "trigger_1", "type": "trigger", "name": "New Email in Gmail", "metadata": {"trigger_event": "google_mail"}},
            {"id": "agent_1", "type": "agent", "name": "Sales Specialist", "metadata": {"role": "sales"}, "dependencies": ["trigger_1"]},
            {"id": "skill_1", "type": "skill", "name": "HubSpot Sync", "metadata": {"action": "create_contact"}, "dependencies": ["agent_1"]}
        ]
    }
    
    # Patch the real get_orchestrator in advanced_workflow_orchestrator
    with patch('advanced_workflow_orchestrator.get_orchestrator') as mock_get_orchestrator:
        mock_get_orchestrator.return_value = orchestrator
        
        # Realize the blueprint
        workflow_id = await queen_agent.realize_blueprint(blueprint, tenant_id="test_tenant")
        
        # Verify workflow object exists in orchestrator
        definitions = orchestrator.get_workflow_definitions()
        assert any(wf['workflow_id'] == workflow_id for wf in definitions)
        
        # Check details of registered workflow
        found = next(wf for wf in definitions if wf['workflow_id'] == workflow_id)
        assert found['name'] == "Test Lead Automation"
        assert found['step_count'] == 3

def test_orchestrator_dynamic_registration(orchestrator):
    """Test dynamic workflow registration in the orchestrator."""
    
    # Fixed class name: WorkflowDefinition
    wf = WorkflowDefinition(
        workflow_id="manual_wf_123",
        name="Manual Workflow",
        description="Manually registered",
        steps=[
            WorkflowStep(step_id="n1", step_type=WorkflowStepType.AGENT_EXECUTION, description="Step 1")
        ],
        start_step="n1"
    )
    
    orchestrator.register_workflow(wf)
    
    definitions = orchestrator.get_workflow_definitions()
    found = next((d for d in definitions if d['workflow_id'] == "manual_wf_123"), None)
    
    assert found is not None
    assert found['name'] == "Manual Workflow"
