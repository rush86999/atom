"""
Workflow-specific fixtures for E2E testing.

This module provides fixtures for testing critical user workflows end-to-end:
- Agent execution workflow (creation, execution, monitoring, results)
- Skill loading workflow (import, scan, install, execute)
- Package installation workflow (request, governance, install, execute)
- Multi-provider LLM workflow (provider selection, fallback, streaming)
- Canvas presentation workflow (creation, LLM content, present, feedback)
"""

import pytest
import tempfile
from pathlib import Path
from typing import Dict, Any, Generator, Optional
from datetime import datetime

from sqlalchemy.orm import Session

from core.models import (
    AgentRegistry,
    AgentExecution,
    CommunitySkill,
    SkillSecurityScan,
    PackageRegistry,
    CanvasAudit,
    AgentFeedback
)
from core.agent_governance_service import AgentGovernanceService
from core.skill_adapter import SkillAdapter
from core.package_governance_service import PackageGovernanceService
from core.package_installer import PackageInstaller
from core.llm.byok_handler import BYOKHandler


@pytest.fixture(scope="function")
def agent_workflow(e2e_postgres_session: Session) -> Generator[Dict[str, Any], None, None]:
    """
    Set up agent execution workflow.

    Provides:
    - agent: Test agent with AUTONOMOUS maturity
    - governance: AgentGovernanceService instance
    - session: Database session

    Usage:
        def test_agent_execution_workflow(agent_workflow):
            agent = agent_workflow["agent"]
            governance = agent_workflow["governance"]
            # Test agent execution
    """
    # Create test agent
    agent = AgentRegistry(
        id="workflow-test-agent",
        name="Workflow Test Agent",
        description="Agent for workflow E2E testing",
        category="Testing",
        module_path="test",
        class_name="WorkflowTestAgent",
        status="AUTONOMOUS",
        confidence_score=0.95,
        capabilities=["read", "write", "execute"],
        governance_level=4
    )
    e2e_postgres_session.add(agent)
    e2e_postgres_session.commit()

    governance = AgentGovernanceService(e2e_postgres_session)

    yield {
        "agent": agent,
        "governance": governance,
        "session": e2e_postgres_session
    }

    # Cleanup
    e2e_postgres_session.query(AgentExecution).filter(
        AgentExecution.agent_id == "workflow-test-agent"
    ).delete()
    e2e_postgres_session.query(AgentRegistry).filter(
        AgentRegistry.id == "workflow-test-agent"
    ).delete()
    e2e_postgres_session.commit()


@pytest.fixture(scope="function")
def skill_workflow(
    e2e_postgres_session: Session,
    tmp_path: Path
) -> Generator[Dict[str, Any], None, None]:
    """
    Set up skill loading workflow.

    Provides:
    - adapter: SkillAdapter instance
    - skill_dir: Temporary directory with test skill
    - session: Database session

    Usage:
        def test_skill_loading_workflow(skill_workflow):
            adapter = skill_workflow["adapter"]
            skill_dir = skill_workflow["skill_dir"]
            # Test skill import
    """
    # Create test skill directory structure
    skill_dir = tmp_path / "test_workflow_skill"
    skill_dir.mkdir()

    # Create SKILL.md with YAML frontmatter
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("""---
name: test_workflow_skill
version: 1.0.0
description: Test skill for E2E workflow testing
type: prompt
maturity: autonomous
author: Test Suite
tags: [e2e, testing, workflow]
packages: []
---

# Test Workflow Skill

This is a test skill for E2E workflow validation.

## Usage

Use this skill for testing workflow integration.
""")

    # Create skill Python file (if needed for code-based skills)
    skill_py = skill_dir / "skill.py"
    skill_py.write_text("""
def test_function():
    '''Test function for skill execution.'''
    return {'success': True, 'data': 'test'}
""")

    adapter = SkillAdapter(e2e_postgres_session)

    yield {
        "adapter": adapter,
        "skill_dir": skill_dir,
        "skill_id": "test_workflow_skill",
        "session": e2e_postgres_session
    }

    # Cleanup
    e2e_postgres_session.query(CommunitySkill).filter(
        CommunitySkill.skill_id == "test_workflow_skill"
    ).delete()
    e2e_postgres_session.query(SkillSecurityScan).filter(
        SkillSecurityScan.skill_id == "test_workflow_skill"
    ).delete()
    e2e_postgres_session.commit()


@pytest.fixture(scope="function")
def package_workflow(e2e_postgres_session: Session) -> Generator[Dict[str, Any], None, None]:
    """
    Set up package installation workflow.

    Provides:
    - governance: PackageGovernanceService instance
    - installer: PackageInstaller instance
    - session: Database session

    Usage:
        def test_python_package_installation(package_workflow):
            governance = package_workflow["governance"]
            installer = package_workflow["installer"]
            # Test package installation
    """
    governance = PackageGovernanceService(e2e_postgres_session)

    try:
        installer = PackageInstaller()
    except Exception as e:
        # PackageInstaller may fail if Docker not available
        # Create mock installer for testing
        installer = None

    yield {
        "governance": governance,
        "installer": installer,
        "session": e2e_postgres_session,
        "docker_available": installer is not None
    }

    # Cleanup
    e2e_postgres_session.query(PackageRegistry).filter(
        PackageRegistry.package_name.like("test-%")
    ).delete()
    e2e_postgres_session.commit()


@pytest.fixture(scope="function")
def llm_workflow(llm_api_keys: Dict[str, str]) -> Dict[str, Any]:
    """
    Set up multi-provider LLM workflow.

    Provides:
    - handler: BYOKHandler instance
    - api_keys: Dictionary of available API keys
    - available_providers: List of providers with keys

    Usage:
        def test_multi_provider_fallback(llm_workflow):
            handler = llm_workflow["handler"]
            # Test LLM provider fallback
    """
    handler = BYOKHandler(workspace_id="e2e_test_workflow")

    # Determine which providers are available
    available_providers = []
    for provider in ["openai", "anthropic", "deepseek", "gemini"]:
        if llm_api_keys.get(provider):
            available_providers.append(provider)

    return {
        "handler": handler,
        "api_keys": llm_api_keys,
        "available_providers": available_providers,
        "has_openai": "openai" in llm_api_keys,
        "has_anthropic": "anthropic" in llm_api_keys,
        "has_deepseek": "deepseek" in llm_api_keys,
        "has_gemini": "gemini" in llm_api_keys,
        "has_any_provider": len(available_providers) > 0
    }


@pytest.fixture(scope="function")
def canvas_workflow(e2e_postgres_session: Session) -> Generator[Dict[str, Any], None, None]:
    """
    Set up canvas presentation workflow.

    Provides:
    - session: Database session
    - user_id: Test user ID
    - canvas_id: Test canvas ID

    Usage:
        def test_canvas_presentation_workflow(canvas_workflow):
            user_id = canvas_workflow["user_id"]
            # Test canvas presentation
    """
    test_user_id = "e2e-test-user"
    test_canvas_id = "workflow-test-canvas"

    yield {
        "session": e2e_postgres_session,
        "user_id": test_user_id,
        "canvas_id": test_canvas_id
    }

    # Cleanup
    e2e_postgres_session.query(CanvasAudit).filter(
        CanvasAudit.canvas_id == test_canvas_id
    ).delete()
    e2e_postgres_session.query(AgentFeedback).filter(
        AgentFeedback.canvas_id == test_canvas_id
    ).delete()
    e2e_postgres_session.commit()


@pytest.fixture(scope="function")
def composite_workflow(
    agent_workflow: Dict[str, Any],
    skill_workflow: Dict[str, Any],
    package_workflow: Dict[str, Any],
    llm_workflow: Dict[str, Any],
    canvas_workflow: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Composite fixture providing all workflow fixtures.

    Useful for end-to-end smoke tests that span multiple workflows.

    Provides:
    - agent: From agent_workflow
    - skill: From skill_workflow
    - package: From package_workflow
    - llm: From llm_workflow
    - canvas: From canvas_workflow

    Usage:
        def test_complete_user_journey(composite_workflow):
            agent = composite_workflow["agent"]
            skill = composite_workflow["skill"]
            # Test complete workflow
    """
    return {
        "agent": agent_workflow,
        "skill": skill_workflow,
        "package": package_workflow,
        "llm": llm_workflow,
        "canvas": canvas_workflow
    }


@pytest.fixture(scope="function")
def workflow_test_data(e2e_postgres_session: Session) -> Dict[str, Any]:
    """
    Provide test data for workflow execution.

    Provides pre-configured test data:
    - test_prompts: Dictionary of test prompts by category
    - test_queries: Sample queries for workflows
    - test_contexts: Sample context data
    - expected_results: Expected outcomes

    Usage:
        def test_workflow_with_data(workflow_test_data):
            prompt = workflow_test_data["test_prompts"]["analysis"]
            # Test with pre-configured data
    """
    return {
        "test_prompts": {
            "analysis": "Analyze this data and provide insights",
            "generation": "Generate a summary of the workflow",
            "decision": "Should we proceed with this action?",
            "extraction": "Extract key information from this text"
        },
        "test_queries": [
            "What is the status of the current workflow?",
            "Execute the following task",
            "Provide a summary of recent activity"
        ],
        "test_contexts": {
            "user_id": "test-user-001",
            "workspace_id": "test-workspace-001",
            "session_id": "test-session-001"
        },
        "expected_results": {
            "success": True,
            "execution_time_seconds": 5.0,
            "has_output": True,
            "has_audit_trail": True
        }
    }


@pytest.fixture(scope="function")
def workflow_performance_thresholds() -> Dict[str, float]:
    """
    Provide performance thresholds for workflow validation.

    Usage:
        def test_workflow_performance(workflow_performance_thresholds):
            threshold = workflow_performance_thresholds["agent_creation"]
            # Assert performance meets threshold
    """
    return {
        "agent_creation_seconds": 1.0,
        "agent_execution_seconds": 10.0,
        "skill_import_seconds": 5.0,
        "skill_execution_seconds": 30.0,
        "package_install_seconds": 60.0,
        "package_execute_seconds": 10.0,
        "llm_streaming_seconds": 5.0,
        "llm_fallback_seconds": 3.0,
        "canvas_creation_seconds": 2.0,
        "canvas_presentation_seconds": 1.0,
        "total_workflow_seconds": 120.0  # 2 minutes for complete workflow
    }


@pytest.fixture(scope="function")
def workflow_audit_trail(e2e_postgres_session: Session) -> Dict[str, Any]:
    """
    Fixture to capture and validate audit trails for workflows.

    Provides helper methods to:
    - Get audit records for a workflow
    - Validate audit trail completeness
    - Check audit record ordering

    Usage:
        def test_workflow_audit_trail(workflow_audit_trail):
            audit_trail.get_audit_records("workflow-id")
            # Validate audit trail
    """
    def get_audit_records(entity_id: str, entity_type: str = "agent"):
        """Get audit records for an entity."""
        if entity_type == "agent":
            return e2e_postgres_session.query(AgentExecution).filter(
                AgentExecution.agent_id == entity_id
            ).all()
        elif entity_type == "skill":
            return e2e_postgres_session.query(CommunitySkill).filter(
                CommunitySkill.skill_id == entity_id
            ).all()
        elif entity_type == "canvas":
            return e2e_postgres_session.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == entity_id
            ).all()
        return []

    def validate_audit_trail(records: list) -> Dict[str, Any]:
        """Validate audit trail completeness."""
        return {
            "has_records": len(records) > 0,
            "record_count": len(records),
            "has_timestamps": all(
                hasattr(r, 'created_at') or hasattr(r, 'timestamp')
                for r in records
            ),
            "chronological_order": all(
                records[i].created_at <= records[i+1].created_at
                for i in range(len(records)-1)
                if hasattr(records[i], 'created_at')
            ) if len(records) > 1 else True
        }

    return {
        "get_audit_records": get_audit_records,
        "validate_audit_trail": validate_audit_trail,
        "session": e2e_postgres_session
    }
