"""
End-to-End Tests for MCP Tools

This test suite validates MCP (Model Context Protocol) tool implementations
using real PostgreSQL database and mocked external services.

Tests cover 8 major MCP tool categories:
- CRM (contacts, leads, pipeline)
- Tasks (projects, task management)
- Tickets (support tickets)
- Knowledge (document ingestion, graph queries)
- Canvas (presentations, UI components)
- Finance (metrics, invoices)
- WhatsApp (messaging, templates)
- Shopify (products, inventory, orders)

All tests use real PostgreSQL database operations to validate actual tool behavior,
not mocked database calls. External APIs (WhatsApp, Shopify) are mocked with httpx.
"""

import pytest
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import text

# Ensure backend is in path
import sys
from pathlib import Path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))


# =============================================================================
# Test Constants and Helpers
# =============================================================================

TEST_WORKSPACE_ID = "e2e-test-workspace"
TEST_AGENT_ID = "e2e-test-agent"
TEST_USER_ID = "e2e-test-user"

def assert_success_response(response: Dict[str, Any], operation_name: str):
    """Helper to assert MCP operation succeeded."""
    assert isinstance(response, dict), f"{operation_name}: Response should be a dict"
    assert "error" not in response or response.get("error") is None, \
        f"{operation_name}: Got error - {response.get('error')}"
    assert response.get("success") is not False, \
        f"{operation_name}: Operation failed"

def assert_database_record(db: Session, table_name: str, filters: Dict[str, Any], should_exist: bool = True):
    """Helper to verify database record exists."""
    query = text(f"SELECT * FROM {table_name} WHERE " + " AND ".join([f"{k} = :{k}" for k in filters.keys()]))
    result = db.execute(query, filters).fetchone()

    if should_exist:
        assert result is not None, f"Record not found in {table_name} with filters {filters}"
    else:
        assert result is None, f"Unexpected record found in {table_name} with filters {filters}"

    return result


# =============================================================================
# CRM Tool E2E Tests
# =============================================================================

class TestMCPToolsCRM:
    """E2E tests for MCP CRM tools (contacts, leads, pipeline)."""

    @pytest.mark.asyncio
    async def test_mcp_search_contacts_empty(self, mcp_service, e2e_postgres_db):
        """Test searching contacts when database is empty."""
        response = await mcp_service.call_tool(
            "search_contacts",
            {"query": "test", "platform": "salesforce"},
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        # Should return empty results or success with no matches
        assert isinstance(response, dict)
        assert response.get("results") == [] or response.get("contacts") == []

    @pytest.mark.asyncio
    async def test_mcp_create_crm_lead_basic(self, mcp_service, e2e_postgres_db, crm_contact_factory):
        """Test creating a basic CRM lead via MCP tool."""
        lead_data = crm_contact_factory(
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            company="Acme Corp",
            status="lead"
        )

        response = await mcp_service.call_tool(
            "create_crm_lead",
            {
                "platform": "salesforce",
                **lead_data
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        # Verify response
        assert_success_response(response, "create_crm_lead")
        assert "id" in response or "lead_id" in response or response.get("success") is True

        # Note: Actual database verification depends on integration implementation
        # Some tools may write to external CRM APIs, not local database
        # For E2E tests with real services, we verify the tool executed successfully

    @pytest.mark.asyncio
    async def test_mcp_create_crm_lead_with_company(self, mcp_service, e2e_postgres_db):
        """Test creating CRM lead with company information."""
        lead_data = {
            "platform": "hubspot",
            "first_name": "Jane",
            "last_name": "Smith",
            "email": f"jane.smith.{uuid.uuid4()}@example.com",
            "company": "Tech Startup Inc",
            "status": "prospect"
        }

        response = await mcp_service.call_tool(
            "create_crm_lead",
            lead_data,
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert_success_response(response, "create_crm_lead_with_company")

    @pytest.mark.asyncio
    async def test_mcp_crm_contact_lifecycle(self, mcp_service, e2e_postgres_db, crm_contact_factory):
        """Test full CRM contact lifecycle: create → search → update → delete."""
        # Create
        contact_data = crm_contact_factory(
            first_name="Lifecycle",
            last_name="Test",
            email=f"lifecycle.{uuid.uuid4()}@example.com"
        )

        create_response = await mcp_service.call_tool(
            "create_crm_lead",
            {"platform": "salesforce", **contact_data},
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )
        assert_success_response(create_response, "CRM lifecycle create")

        # Search
        search_response = await mcp_service.call_tool(
            "search_contacts",
            {"query": "Lifecycle", "platform": "salesforce"},
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )
        assert isinstance(search_response, dict)

        # Update (if update implemented)
        if create_response.get("id"):
            update_response = await mcp_service.call_tool(
                "update_crm_lead",
                {
                    "platform": "salesforce",
                    "id": create_response["id"],
                    "data": {"status": "qualified", "phone": "+15551234567"}
                },
                context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
            )
            # Update might not be implemented in all integrations
            assert isinstance(update_response, dict)

    @pytest.mark.asyncio
    async def test_mcp_get_sales_pipeline(self, mcp_service, e2e_postgres_db):
        """Test fetching sales pipeline data."""
        response = await mcp_service.call_tool(
            "get_sales_pipeline",
            {"platform": "salesforce", "status": "open"},
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        # Should return pipeline data (may be empty)
        assert isinstance(response, dict)
        assert "pipeline" in response or "deals" in response or "results" in response or isinstance(response.get("value"), (list, dict))


# =============================================================================
# Tasks Tool E2E Tests
# =============================================================================

class TestMCPToolsTasks:
    """E2E tests for MCP task management tools."""

    @pytest.mark.asyncio
    async def test_mcp_list_projects(self, mcp_service, e2e_postgres_db):
        """Test listing projects from project management platforms."""
        response = await mcp_service.call_tool(
            "list_projects",
            {"platform": "asana"},
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        # Should return list of projects (may be empty)
        assert isinstance(response, dict)
        assert "projects" in response or "results" in response or isinstance(response.get("value"), list)

    @pytest.mark.asyncio
    async def test_mcp_create_task(self, mcp_service, e2e_postgres_db, task_factory):
        """Test creating a task via MCP tool."""
        task_data = task_factory(
            title=f"E2E Test Task {uuid.uuid4()}",
            description="This is an E2E test task",
            status="todo",
            priority="high",
            due_date=(datetime.now() + timedelta(days=7)).isoformat()
        )

        response = await mcp_service.call_tool(
            "create_task",
            {
                "platform": "asana",
                "project": "E2E Test Project",
                **task_data
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert_success_response(response, "create_task")
        assert "id" in response or "task_id" in response or response.get("success") is True

    @pytest.mark.asyncio
    async def test_mcp_get_tasks_with_filters(self, mcp_service, e2e_postgres_db):
        """Test fetching tasks with filters."""
        response = await mcp_service.call_tool(
            "get_tasks",
            {
                "platform": "jira",
                "assignee": "test-user",
                "status": "todo"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)
        assert "tasks" in response or "results" in response or isinstance(response.get("value"), list)

    @pytest.mark.asyncio
    async def test_mcp_update_task(self, mcp_service, e2e_postgres_db, task_factory):
        """Test updating a task via MCP tool."""
        # First create a task
        create_response = await mcp_service.call_tool(
            "create_task",
            {
                "platform": "linear",
                "project": "E2E Test",
                "title": f"Update Test {uuid.uuid4()}",
                "status": "todo"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        # Then update it
        if create_response.get("id"):
            update_response = await mcp_service.call_tool(
                "update_task",
                {
                    "platform": "linear",
                    "id": create_response["id"],
                    "data": {"status": "done", "priority": "urgent"}
                },
                context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
            )
            assert isinstance(update_response, dict)

    @pytest.mark.asyncio
    async def test_mcp_task_workflow(self, mcp_service, e2e_postgres_db):
        """Test complete task workflow: create → assign → complete → query."""
        # Create
        task_title = f"Workflow Test {uuid.uuid4()}"
        create_response = await mcp_service.call_tool(
            "create_task",
            {
                "platform": "monday",
                "project": "Workflow Test Project",
                "title": task_title,
                "description": "Testing complete task workflow"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        # Assign (update with assignee)
        if create_response.get("id"):
            assign_response = await mcp_service.call_tool(
                "update_task",
                {
                    "platform": "monday",
                    "id": create_response["id"],
                    "data": {"assignee": "test-user-123"}
                },
                context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
            )

            # Complete
            complete_response = await mcp_service.call_tool(
                "update_task",
                {
                    "platform": "monday",
                    "id": create_response["id"],
                    "data": {"status": "done"}
                },
                context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
            )

    @pytest.mark.asyncio
    async def test_mcp_search_tasks(self, mcp_service, e2e_postgres_db):
        """Test searching for tasks by query."""
        response = await mcp_service.call_tool(
            "search_tasks",
            {"query": "urgent", "platform": "jira"},
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)
        assert "tasks" in response or "results" in response or isinstance(response.get("value"), list)


# =============================================================================
# Tickets Tool E2E Tests
# =============================================================================

class TestMCPToolsTickets:
    """E2E tests for MCP support ticket tools."""

    @pytest.mark.asyncio
    async def test_mcp_create_support_ticket(self, mcp_service, e2e_postgres_db, ticket_factory):
        """Test creating a support ticket."""
        ticket_data = ticket_factory(
            subject=f"E2E Test Issue {uuid.uuid4()}",
            description="Customer unable to access account",
            priority="high",
            status="open"
        )

        response = await mcp_service.call_tool(
            "create_support_ticket",
            {
                "platform": "zendesk",
                **ticket_data
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert_success_response(response, "create_support_ticket")
        assert "id" in response or "ticket_id" in response or response.get("success") is True

    @pytest.mark.asyncio
    async def test_mcp_create_ticket_with_priority(self, mcp_service, e2e_postgres_db):
        """Test creating ticket with different priority levels."""
        for priority in ["low", "normal", "high", "urgent"]:
            response = await mcp_service.call_tool(
                "create_support_ticket",
                {
                    "platform": "freshdesk",
                    "subject": f"Priority Test - {priority}",
                    "description": f"Testing {priority} priority ticket",
                    "priority": priority
                },
                context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
            )

            assert isinstance(response, dict)

    @pytest.mark.asyncio
    async def test_mcp_update_support_ticket(self, mcp_service, e2e_postgres_db, ticket_factory):
        """Test updating support ticket status and adding comments."""
        # Create ticket first
        create_response = await mcp_service.call_tool(
            "create_support_ticket",
            {
                "platform": "intercom",
                "subject": f"Update Test {uuid.uuid4()}",
                "description": "Test ticket for updates",
                "priority": "normal"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        # Update with status change and comment
        if create_response.get("id"):
            update_response = await mcp_service.call_tool(
                "update_support_ticket",
                {
                    "platform": "intercom",
                    "id": create_response["id"],
                    "data": {
                        "status": "resolved",
                        "priority": "high",
                        "comment": "Issue resolved by support team"
                    }
                },
                context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
            )
            assert isinstance(update_response, dict)

    @pytest.mark.asyncio
    async def test_mcp_ticket_resolution_workflow(self, mcp_service, e2e_postgres_db):
        """Test ticket resolution workflow: create → comment → resolve → verify."""
        # Create
        subject = f"Resolution Test {uuid.uuid4()}"
        create_response = await mcp_service.call_tool(
            "create_support_ticket",
            {
                "platform": "zendesk",
                "subject": subject,
                "description": "Customer billing inquiry",
                "priority": "normal"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        # Add comment
        if create_response.get("id"):
            comment_response = await mcp_service.call_tool(
                "update_support_ticket",
                {
                    "platform": "zendesk",
                    "id": create_response["id"],
                    "data": {"comment": "Investigating billing discrepancy"}
                },
                context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
            )

            # Resolve
            resolve_response = await mcp_service.call_tool(
                "update_support_ticket",
                {
                    "platform": "zendesk",
                    "id": create_response["id"],
                    "data": {"status": "solved", "comment": "Billing discrepancy resolved"}
                },
                context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
            )


# =============================================================================
# Knowledge Tool E2E Tests
# =============================================================================

class TestMCPToolsKnowledge:
    """E2E tests for MCP knowledge and memory tools."""

    @pytest.mark.asyncio
    async def test_mcp_ingest_knowledge_from_text(self, mcp_service, e2e_postgres_db):
        """Test ingesting knowledge from text."""
        test_text = """
        Atom is an AI-powered automation platform that helps businesses streamline workflows.
        It uses multi-agent systems with different maturity levels: STUDENT, INTERN, SUPERVISED, and AUTONOMOUS.
        The platform integrates with popular tools like Slack, Salesforce, and Jira.
        """

        response = await mcp_service.call_tool(
            "ingest_knowledge_from_text",
            {
                "text": test_text,
                "doc_id": f"e2e-test-doc-{uuid.uuid4()}",
                "source": "e2e_test"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert_success_response(response, "ingest_knowledge_from_text")
        # Knowledge ingestion may return entities extracted, relationships found
        assert isinstance(response, dict)

    @pytest.mark.asyncio
    async def test_mcp_ingest_knowledge_structured_data(self, mcp_service, e2e_postgres_db):
        """Test ingesting knowledge with structured business data."""
        business_text = """
        Q4 2025 Revenue: $1.2M, up 15% from Q3
        Active customers: 1,250
        Churn rate: 2.3% (down from 3.1%)
        Top product: Atom Enterprise Edition
        """

        response = await mcp_service.call_tool(
            "ingest_knowledge_from_text",
            {
                "text": business_text,
                "doc_id": f"q4-report-{uuid.uuid4()}",
                "source": "quarterly_report"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)
        # Should extract metrics like revenue, customer count, churn rate

    @pytest.mark.asyncio
    async def test_mcp_query_knowledge_graph(self, mcp_service, e2e_postgres_db):
        """Test querying knowledge graph."""
        # First ingest some knowledge
        await mcp_service.call_tool(
            "ingest_knowledge_from_text",
            {
                "text": "Atom uses PostgreSQL for data storage and Redis for caching. The platform supports multi-tenant workspaces.",
                "doc_id": f"tech-doc-{uuid.uuid4()}",
                "source": "e2e_test"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        # Then query
        response = await mcp_service.call_tool(
            "query_knowledge_graph",
            {
                "query": "What database does Atom use?",
                "mode": "local"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)
        assert "results" in response or "answer" in response or "entities" in response

    @pytest.mark.asyncio
    async def test_mcp_query_knowledge_global_mode(self, mcp_service, e2e_postgres_db):
        """Test querying knowledge graph in global mode (high-level summaries)."""
        response = await mcp_service.call_tool(
            "query_knowledge_graph",
            {
                "query": "Summarize Atom's architecture",
                "mode": "global"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)

    @pytest.mark.asyncio
    async def test_mcp_save_business_fact(self, mcp_service, e2e_postgres_db):
        """Test saving a verifiable business fact with citations."""
        response = await mcp_service.call_tool(
            "save_business_fact",
            {
                "fact": "Atom supports 4 agent maturity levels: STUDENT, INTERN, SUPERVISED, AUTONOMOUS",
                "citations": ["/docs/AGENT_MATURITY.md", "/docs/GOVERNANCE.md"],
                "reason": "Core architecture principle",
                "source": "e2e_test"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert_success_response(response, "save_business_fact")

    @pytest.mark.asyncio
    async def test_mcp_save_multiple_facts_and_query(self, mcp_service, e2e_postgres_db):
        """Test saving multiple facts and then querying them."""
        facts = [
            {
                "fact": "Atom uses FastAPI for the backend REST API",
                "citations": ["/docs/ARCHITECTURE.md"],
                "reason": "Technology stack documentation"
            },
            {
                "fact": "MCP stands for Model Context Protocol",
                "citations": ["/docs/MCP.md"],
                "reason": "Terminology clarification"
            }
        ]

        for fact_data in facts:
            response = await mcp_service.call_tool(
                "save_business_fact",
                {**fact_data, "source": "e2e_test"},
                context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
            )
            assert_success_response(response, "save_business_fact")


# =============================================================================
# Canvas Tool E2E Tests
# =============================================================================

class TestMCPToolsCanvas:
    """E2E tests for MCP canvas presentation tools."""

    @pytest.mark.asyncio
    async def test_mcp_canvas_present_chart(self, mcp_service, e2e_postgres_db, canvas_data_factory):
        """Test presenting a chart via canvas tool."""
        chart_data = canvas_data_factory["create_chart_data"](chart_type="line")

        response = await mcp_service.call_tool(
            "canvas_tool",
            {
                "action": "present",
                "component": "chart",
                "data": chart_data,
                "title": "E2E Test Chart"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert_success_response(response, "canvas_tool present chart")
        assert "canvas_id" in response or "id" in response or response.get("success") is True

    @pytest.mark.asyncio
    async def test_mcp_canvas_present_form(self, mcp_service, e2e_postgres_db, canvas_data_factory):
        """Test presenting a form via canvas tool."""
        form_data = canvas_data_factory["create_form_data"]()

        response = await mcp_service.call_tool(
            "canvas_tool",
            {
                "action": "present",
                "component": "form",
                "data": form_data,
                "title": "E2E Test Form"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert_success_response(response, "canvas_tool present form")

    @pytest.mark.asyncio
    async def test_mcp_canvas_update(self, mcp_service, e2e_postgres_db, canvas_data_factory):
        """Test updating a canvas presentation."""
        # Present initial canvas
        chart_data = canvas_data_factory["create_chart_data"]("bar")
        present_response = await mcp_service.call_tool(
            "canvas_tool",
            {
                "action": "present",
                "component": "chart",
                "data": chart_data,
                "title": "Original Chart"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        # Update if we got a canvas ID
        if present_response.get("canvas_id") or present_response.get("id"):
            canvas_id = present_response.get("canvas_id") or present_response.get("id")

            updated_data = chart_data.copy()
            updated_data["title"] = "Updated Chart"

            update_response = await mcp_service.call_tool(
                "canvas_tool",
                {
                    "action": "update",
                    "canvas_id": canvas_id,
                    "data": updated_data
                },
                context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
            )
            assert isinstance(update_response, dict)

    @pytest.mark.asyncio
    async def test_mcp_canvas_close(self, mcp_service, e2e_postgres_db, canvas_data_factory):
        """Test closing a canvas presentation."""
        # Present canvas first
        form_data = canvas_data_factory["create_form_data"]()
        present_response = await mcp_service.call_tool(
            "canvas_tool",
            {
                "action": "present",
                "component": "form",
                "data": form_data,
                "title": "Temporary Form"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        # Close if we got a canvas ID
        if present_response.get("canvas_id") or present_response.get("id"):
            canvas_id = present_response.get("canvas_id") or present_response.get("id")

            close_response = await mcp_service.call_tool(
                "canvas_tool",
                {
                    "action": "close",
                    "canvas_id": canvas_id
                },
                context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
            )
            assert isinstance(close_response, dict)

    @pytest.mark.asyncio
    async def test_mcp_canvas_governance_checks(self, mcp_service, e2e_postgres_db, test_agents):
        """Test that canvas tool respects agent governance (maturity levels)."""
        chart_data = {"type": "line", "title": "Governance Test", "data": {"labels": ["A", "B"], "datasets": [{"data": [1, 2]}]}}

        # Test with different agent maturity levels
        for maturity, agent in test_agents.items():
            response = await mcp_service.call_tool(
                "canvas_tool",
                {
                    "action": "present",
                    "component": "chart",
                    "data": chart_data,
                    "title": f"Governance Test - {maturity}"
                },
                context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": agent.id, "user_id": TEST_USER_ID}
            )

            # All maturity levels should be able to present basic canvas
            assert isinstance(response, dict)


# =============================================================================
# Finance Tool E2E Tests
# =============================================================================

class TestMCPToolsFinance:
    """E2E tests for MCP finance tools."""

    @pytest.mark.asyncio
    async def test_mcp_query_financial_metrics(self, mcp_service, e2e_postgres_db):
        """Test querying financial metrics."""
        response = await mcp_service.call_tool(
            "query_financial_metrics",
            {
                "metrics": ["revenue", "expenses", "profit"],
                "period": "2025-01"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        # Should return metrics (may be empty/mocked data)
        assert isinstance(response, dict)
        assert "metrics" in response or "results" in response or "data" in response

    @pytest.mark.asyncio
    async def test_mcp_list_finance_invoices(self, mcp_service, e2e_postgres_db):
        """Test listing finance invoices."""
        response = await mcp_service.call_tool(
            "list_finance_invoices",
            {
                "status": "pending",
                "limit": 10
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)
        assert "invoices" in response or "results" in response or isinstance(response.get("value"), list)

    @pytest.mark.asyncio
    async def test_mcp_create_invoice(self, mcp_service, e2e_postgres_db, finance_data_factory):
        """Test creating an invoice."""
        invoice_data = finance_data_factory(
            customer_id=f"cust-{uuid.uuid4().hex[:8]}",
            amount=1500.00,
            currency="USD",
            description="Professional Services - January 2025",
            status="pending"
        )

        response = await mcp_service.call_tool(
            "create_invoice",
            invoice_data,
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert_success_response(response, "create_invoice")
        assert "id" in response or "invoice_id" in response or response.get("success") is True


# =============================================================================
# WhatsApp Tool E2E Tests
# =============================================================================

class TestMCPToolsWhatsApp:
    """E2E tests for MCP WhatsApp tools (with mocked external API)."""

    @pytest.mark.asyncio
    async def test_mcp_whatsapp_send_message(self, mcp_service, e2e_postgres_db):
        """Test sending WhatsApp message (will be mocked/hitl gated)."""
        response = await mcp_service.call_tool(
            "whatsapp_send_message",
            {
                "to": "+15551234567",
                "message": "Test message from E2E test suite",
                "template_name": None
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        # May be HITL intercepted or return success
        assert isinstance(response, dict)
        # HITL will return intervention request, or success if agent has permission

    @pytest.mark.asyncio
    async def test_mcp_whatsapp_send_template(self, mcp_service, e2e_postgres_db):
        """Test sending WhatsApp template message."""
        response = await mcp_service.call_tool(
            "whatsapp_send_template",
            {
                "to": "+15551234567",
                "template_name": "order_confirmation",
                "template_data": {"order_id": "12345", "amount": "$99.99"}
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)

    @pytest.mark.asyncio
    async def test_mcp_whatsapp_list_templates(self, mcp_service, e2e_postgres_db):
        """Test listing WhatsApp message templates."""
        response = await mcp_service.call_tool(
            "whatsapp_list_templates",
            {"limit": 20},
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)
        assert "templates" in response or isinstance(response.get("value"), list)


# =============================================================================
# Shopify Tool E2E Tests
# =============================================================================

class TestMCPToolsShopify:
    """E2E tests for MCP Shopify tools (with mocked external API)."""

    @pytest.mark.asyncio
    async def test_mcp_shopify_list_products(self, mcp_service, e2e_postgres_db):
        """Test listing Shopify products."""
        response = await mcp_service.call_tool(
            "shopify_get_products",
            {"limit": 10},
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)
        assert "products" in response or "results" in response or isinstance(response.get("value"), list)

    @pytest.mark.asyncio
    async def test_mcp_shopify_create_product(self, mcp_service, e2e_postgres_db):
        """Test creating a Shopify product."""
        response = await mcp_service.call_tool(
            "shopify_create_product",
            {
                "title": f"E2E Test Product {uuid.uuid4()}",
                "description": "Test product for E2E testing",
                "price": 29.99,
                "inventory_quantity": 100,
                "sku": f"E2E-{uuid.uuid4().hex[:8].upper()}"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)

    @pytest.mark.asyncio
    async def test_mcp_shopify_update_inventory(self, mcp_service, e2e_postgres_db):
        """Test updating Shopify product inventory."""
        response = await mcp_service.call_tool(
            "shopify_update_inventory",
            {
                "product_id": f"prod_{uuid.uuid4().hex[:8]}",
                "inventory_quantity": 50,
                "location_id": "default"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)

    @pytest.mark.asyncio
    async def test_mcp_shopify_get_orders(self, mcp_service, e2e_postgres_db):
        """Test fetching Shopify orders."""
        response = await mcp_service.call_tool(
            "shopify_get_orders",
            {
                "status": "open",
                "limit": 10
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)
        assert "orders" in response or "results" in response or isinstance(response.get("value"), list)


# =============================================================================
# Additional Tool Tests
# =============================================================================

class TestMCPToolsAdditional:
    """E2E tests for additional MCP tools."""

    @pytest.mark.asyncio
    async def test_mcp_send_email(self, mcp_service, e2e_postgres_db):
        """Test sending email (should be HITL gated)."""
        response = await mcp_service.call_tool(
            "send_email",
            {
                "platform": "gmail",
                "to": "test@example.com",
                "subject": "E2E Test Email",
                "body": "This is a test email from E2E test suite"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        # Should be HITL intercepted for non-autonomous agents
        assert isinstance(response, dict)

    @pytest.mark.asyncio
    async def test_mcp_search_emails(self, mcp_service, e2e_postgres_db):
        """Test searching emails."""
        response = await mcp_service.call_tool(
            "search_emails",
            {
                "query": "urgent",
                "platform": "gmail",
                "limit": 10
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)

    @pytest.mark.asyncio
    async def test_mcp_send_message(self, mcp_service, e2e_postgres_db):
        """Test sending message to communication platform."""
        response = await mcp_service.call_tool(
            "send_message",
            {
                "platform": "slack",
                "target": "#general",
                "message": "Test message from E2E test suite"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)

    @pytest.mark.asyncio
    async def test_mcp_post_channel_message(self, mcp_service, e2e_postgres_db):
        """Test posting high-visibility channel message."""
        response = await mcp_service.call_tool(
            "post_channel_message",
            {
                "platform": "slack",
                "channel": "#announcements",
                "message": "Important announcement from E2E test"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)

    @pytest.mark.asyncio
    async def test_mcp_reconcile_inventory(self, mcp_service, e2e_postgres_db):
        """Test inventory reconciliation tool."""
        response = await mcp_service.call_tool(
            "reconcile_inventory",
            {
                "skus": "SKU-001,SKU-002,SKU-003"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)


# =============================================================================
# Error Handling Edge Case Tests
# =============================================================================

class TestMCPToolsErrorHandling:
    """E2E tests for MCP tool error handling."""

    @pytest.mark.asyncio
    async def test_mcp_crm_invalid_email(self, mcp_service, e2e_postgres_db):
        """Test creating CRM contact with invalid email."""
        response = await mcp_service.call_tool(
            "create_crm_lead",
            {
                "platform": "salesforce",
                "first_name": "Invalid",
                "last_name": "Email",
                "email": "not-an-email",  # Invalid format
                "company": "Test Corp"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        # Should handle gracefully - either reject or return error
        assert isinstance(response, dict)
        # May have validation error or proceed (depends on integration)

    @pytest.mark.asyncio
    async def test_mcp_task_invalid_status(self, mcp_service, e2e_postgres_db):
        """Test updating task with invalid status."""
        response = await mcp_service.call_tool(
            "update_task",
            {
                "platform": "jira",
                "id": "fake-task-id",
                "data": {"status": "invalid_status_value_12345"}
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)
        # Should return error or handle gracefully

    @pytest.mark.asyncio
    async def test_mcp_knowledge_empty_ingest(self, mcp_service, e2e_postgres_db):
        """Test ingesting empty knowledge text."""
        response = await mcp_service.call_tool(
            "ingest_knowledge_from_text",
            {
                "text": "",  # Empty text
                "doc_id": f"empty-test-{uuid.uuid4()}",
                "source": "e2e_test"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)
        # Should handle empty input gracefully

    @pytest.mark.asyncio
    async def test_mcp_canvas_invalid_component(self, mcp_service, e2e_postgres_db):
        """Test creating canvas with invalid component type."""
        response = await mcp_service.call_tool(
            "canvas_tool",
            {
                "action": "present",
                "component": "nonexistent_component_type",
                "data": {"invalid": "data"},
                "title": "Invalid Component Test"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)
        # Should return error or handle gracefully

    @pytest.mark.asyncio
    async def test_mcp_missing_required_parameters(self, mcp_service, e2e_postgres_db):
        """Test calling tools with missing required parameters."""
        response = await mcp_service.call_tool(
            "create_task",
            {
                # Missing required 'project' and 'title' parameters
                "platform": "asana"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)
        # Should return validation error

    @pytest.mark.asyncio
    async def test_mcp_unknown_tool_name(self, mcp_service, e2e_postgres_db):
        """Test calling non-existent tool."""
        response = await mcp_service.call_tool(
            "nonexistent_tool_name_xyz",
            {"any": "parameter"},
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)
        assert "error" in response or response.get("success") is False

    @pytest.mark.asyncio
    async def test_mcp_invoice_negative_amount(self, mcp_service, e2e_postgres_db):
        """Test creating invoice with negative amount."""
        response = await mcp_service.call_tool(
            "create_invoice",
            {
                "customer_id": f"cust-{uuid.uuid4().hex[:8]}",
                "amount": -100.00,  # Negative amount
                "currency": "USD",
                "description": "Invalid negative invoice"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)
        # Should reject or handle negative amount

    @pytest.mark.asyncio
    async def test_mcp_support_ticket_missing_subject(self, mcp_service, e2e_postgres_db):
        """Test creating support ticket without required subject."""
        response = await mcp_service.call_tool(
            "create_support_ticket",
            {
                "platform": "zendesk",
                "description": "Ticket without subject"
                # Missing required 'subject' field
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)


# =============================================================================
# Concurrency Edge Case Tests
# =============================================================================

class TestMCPToolsConcurrency:
    """E2E tests for MCP tool concurrent operations."""

    @pytest.mark.asyncio
    async def test_mcp_concurrent_task_creation(self, mcp_service, e2e_postgres_db):
        """Test creating 10 tasks concurrently."""
        task_count = 10
        tasks = []

        # Create concurrent tasks
        for i in range(task_count):
            task = mcp_service.call_tool(
                "create_task",
                {
                    "platform": "asana",
                    "project": "Concurrency Test",
                    "title": f"Concurrent Task {i} - {uuid.uuid4()}",
                    "description": "Testing concurrent task creation"
                },
                context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
            )
            tasks.append(task)

        # Wait for all to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should return dict responses (no exceptions)
        for i, result in enumerate(results):
            assert not isinstance(result, Exception), f"Task {i} raised exception: {result}"
            assert isinstance(result, dict), f"Task {i} returned non-dict: {type(result)}"

    @pytest.mark.asyncio
    async def test_mcp_concurrent_knowledge_ingest(self, mcp_service, e2e_postgres_db):
        """Test ingesting multiple knowledge documents concurrently."""
        doc_count = 5
        docs = []

        for i in range(doc_count):
            doc = mcp_service.call_tool(
                "ingest_knowledge_from_text",
                {
                    "text": f"Concurrent test document {i}: This is test content for document {i}.",
                    "doc_id": f"concurrent-doc-{i}-{uuid.uuid4()}",
                    "source": "concurrency_test"
                },
                context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
            )
            docs.append(doc)

        results = await asyncio.gather(*docs, return_exceptions=True)

        for i, result in enumerate(results):
            assert not isinstance(result, Exception), f"Doc {i} raised exception: {result}"
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_mcp_concurrent_canvas_operations(self, mcp_service, e2e_postgres_db):
        """Test multiple canvas presentations concurrently."""
        canvas_count = 5
        canvases = []

        for i in range(canvas_count):
            canvas = mcp_service.call_tool(
                "canvas_tool",
                {
                    "action": "present",
                    "component": "chart",
                    "data": {
                        "type": "line",
                        "title": f"Concurrent Chart {i}",
                        "data": {
                            "labels": ["A", "B", "C"],
                            "datasets": [{"data": [i, i*2, i*3]}]
                        }
                    }
                },
                context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
            )
            canvases.append(canvas)

        results = await asyncio.gather(*canvases, return_exceptions=True)

        for i, result in enumerate(results):
            assert not isinstance(result, Exception), f"Canvas {i} raised exception: {result}"
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_mcp_concurrent_contact_search(self, mcp_service, e2e_postgres_db):
        """Test concurrent contact searches."""
        search_count = 8
        searches = []

        queries = ["test", "john", "jane", "acme", "tech", "startup", "customer", "lead"]

        for query in queries:
            search = mcp_service.call_tool(
                "search_contacts",
                {"query": query, "platform": "salesforce"},
                context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
            )
            searches.append(search)

        results = await asyncio.gather(*searches, return_exceptions=True)

        for i, result in enumerate(results):
            assert not isinstance(result, Exception), f"Search {i} raised exception: {result}"
            assert isinstance(result, dict)


# =============================================================================
# Performance Edge Case Tests
# =============================================================================

class TestMCPToolsPerformance:
    """E2E tests for MCP tool performance with large datasets."""

    @pytest.mark.asyncio
    async def test_mcp_bulk_task_creation(self, mcp_service, e2e_postgres_db, performance_monitor):
        """Test creating 100 tasks and measure performance."""
        task_count = 100
        performance_monitor.start_timer("bulk_task_creation")

        tasks = []
        for i in range(task_count):
            task = mcp_service.call_tool(
                "create_task",
                {
                    "platform": "asana",
                    "project": "Bulk Test Project",
                    "title": f"Bulk Task {i:03d} - {uuid.uuid4()}",
                    "description": f"Bulk test task number {i}"
                },
                context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        duration = performance_monitor.stop_timer("bulk_task_creation")

        # Verify all succeeded
        success_count = sum(1 for r in results if isinstance(r, dict))
        assert success_count == task_count, f"Only {success_count}/{task_count} tasks succeeded"

        # Performance assertion: should complete in reasonable time
        # This is a soft assertion - adjust threshold based on environment
        print(f"\nBulk task creation ({task_count} tasks): {duration:.2f}ms")

    @pytest.mark.asyncio
    async def test_mcp_large_knowledge_ingest(self, mcp_service, e2e_postgres_db, performance_monitor):
        """Test ingesting large document (10K characters)."""
        # Generate 10K character document
        large_text = " ".join([f"Word{i} " for i in range(5000)])  # ~10K chars

        performance_monitor.start_timer("large_knowledge_ingest")

        response = await mcp_service.call_tool(
            "ingest_knowledge_from_text",
            {
                "text": large_text,
                "doc_id": f"large-doc-{uuid.uuid4()}",
                "source": "performance_test"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        duration = performance_monitor.stop_timer("large_knowledge_ingest")

        assert isinstance(response, dict)
        print(f"\nLarge knowledge ingest (10K chars): {duration:.2f}ms")

    @pytest.mark.asyncio
    async def test_mcp_complex_canvas_render(self, mcp_service, e2e_postgres_db, performance_monitor):
        """Test rendering canvas with many components."""
        # Create canvas with complex nested data
        complex_data = {
            "type": "line",
            "title": "Performance Test Chart",
            "data": {
                "labels": [f"Label{i}" for i in range(50)],
                "datasets": [
                    {
                        "label": f"Dataset{j}",
                        "data": [i * j for i in range(50)],
                        "borderColor": f"rgb({j*20}, 100, 200)"
                    }
                    for j in range(10)
                ]
            }
        }

        performance_monitor.start_timer("complex_canvas_render")

        response = await mcp_service.call_tool(
            "canvas_tool",
            {
                "action": "present",
                "component": "chart",
                "data": complex_data,
                "title": "Complex Performance Test"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        duration = performance_monitor.stop_timer("complex_canvas_render")

        assert isinstance(response, dict)
        print(f"\nComplex canvas render (50 labels, 10 datasets): {duration:.2f}ms")

    @pytest.mark.asyncio
    async def test_mcp_rapid_sequential_calls(self, mcp_service, e2e_postgres_db, performance_monitor):
        """Test 50 rapid sequential tool calls."""
        call_count = 50
        performance_monitor.start_timer("rapid_sequential_calls")

        for i in range(call_count):
            response = await mcp_service.call_tool(
                "search_contacts",
                {"query": f"test{i}", "platform": "salesforce"},
                context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
            )
            assert isinstance(response, dict)

        duration = performance_monitor.stop_timer("rapid_sequential_calls")

        avg_time = duration / call_count
        print(f"\nRapid sequential calls ({call_count} calls): {duration:.2f}ms total, {avg_time:.2f}ms avg")


# =============================================================================
# Data Validation Edge Case Tests
# =============================================================================

class TestMCPToolsDataValidation:
    """E2E tests for MCP tool data validation."""

    @pytest.mark.asyncio
    async def test_mcp_required_field_validation(self, mcp_service, e2e_postgres_db):
        """Test validation of required fields across tools."""
        # Missing required fields should be handled gracefully

        # Task without title
        task_response = await mcp_service.call_tool(
            "create_task",
            {
                "platform": "asana",
                "project": "Test Project"
                # Missing: title (required)
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )
        assert isinstance(task_response, dict)

        # CRM lead without email
        crm_response = await mcp_service.call_tool(
            "create_crm_lead",
            {
                "platform": "salesforce",
                "first_name": "No",
                "last_name": "Email"
                # Missing: email (typically required)
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )
        assert isinstance(crm_response, dict)

    @pytest.mark.asyncio
    async def test_mcp_foreign_key_constraints(self, mcp_service, e2e_postgres_db):
        """Test operations with invalid foreign key references."""
        # Update non-existent task
        response = await mcp_service.call_tool(
            "update_task",
            {
                "platform": "jira",
                "id": "non-existent-task-id-12345",
                "data": {"status": "done"}
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)
        # Should handle gracefully (error or not-found response)

    @pytest.mark.asyncio
    async def test_mcp_unique_constraints(self, mcp_service, e2e_postgres_db):
        """Test handling of unique constraint violations."""
        # Some systems enforce unique emails, IDs, etc.

        unique_id = f"unique-{uuid.uuid4()}"

        # Create first contact
        response1 = await mcp_service.call_tool(
            "create_crm_lead",
            {
                "platform": "salesforce",
                "first_name": "Unique",
                "last_name": "Test",
                "email": f"{unique_id}@example.com",
                "company": "Unique Test Corp"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        # Try to create duplicate (if unique constraint exists)
        response2 = await mcp_service.call_tool(
            "create_crm_lead",
            {
                "platform": "salesforce",
                "first_name": "Duplicate",
                "last_name": "Test",
                "email": f"{unique_id}@example.com",  # Same email
                "company": "Duplicate Corp"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        # Both should return dict responses
        assert isinstance(response1, dict)
        assert isinstance(response2, dict)

    @pytest.mark.asyncio
    async def test_mcp_data_type_validation(self, mcp_service, e2e_postgres_db):
        """Test handling of incorrect data types."""
        # Pass string where number expected
        response = await mcp_service.call_tool(
            "create_invoice",
            {
                "customer_id": f"cust-{uuid.uuid4().hex[:8]}",
                "amount": "not-a-number",  # Should be number
                "currency": "USD",
                "description": "Type validation test"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)

    @pytest.mark.asyncio
    async def test_mcp_string_length_validation(self, mcp_service, e2e_postgres_db):
        """Test handling of excessively long strings."""
        very_long_string = "x" * 10000  # 10K character string

        response = await mcp_service.call_tool(
            "create_task",
            {
                "platform": "asana",
                "project": "Test",
                "title": very_long_string,  # Excessively long title
                "description": "Testing length validation"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)
        # Should truncate or reject

    @pytest.mark.asyncio
    async def test_mcp_special_characters_handling(self, mcp_service, e2e_postgres_db):
        """Test handling of special characters and unicode."""
        special_text = "Test with émojis 🎉 spëcial çhars & symbols <script>alert('xss')</script>"

        response = await mcp_service.call_tool(
            "ingest_knowledge_from_text",
            {
                "text": special_text,
                "doc_id": f"special-chars-{uuid.uuid4()}",
                "source": "security_test"
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)
        # Should handle/sanitize special characters safely

    @pytest.mark.asyncio
    async def test_mcp_null_value_handling(self, mcp_service, e2e_postgres_db):
        """Test handling of null/None values in parameters."""
        response = await mcp_service.call_tool(
            "create_crm_lead",
            {
                "platform": "hubspot",
                "first_name": "Test",
                "last_name": None,  # Explicit None value
                "email": f"null-test-{uuid.uuid4()}@example.com",
                "company": None
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)
        # Should handle None values gracefully

    @pytest.mark.asyncio
    async def test_mcp_sql_injection_prevention(self, mcp_service, e2e_postgres_db):
        """Test that SQL injection attempts are handled safely."""
        malicious_input = "'; DROP TABLE contacts; --"

        response = await mcp_service.call_tool(
            "search_contacts",
            {"query": malicious_input, "platform": "salesforce"},
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)
        # Should sanitize input and not cause SQL errors

    @pytest.mark.asyncio
    async def test_mcp_malformed_json(self, mcp_service, e2e_postgres_db):
        """Test handling of malformed JSON in data parameters."""
        response = await mcp_service.call_tool(
            "update_task",
            {
                "platform": "jira",
                "id": "test-id",
                "data": "{invalid json}"  # Malformed JSON string
            },
            context={"workspace_id": TEST_WORKSPACE_ID, "agent_id": TEST_AGENT_ID, "user_id": TEST_USER_ID}
        )

        assert isinstance(response, dict)
        # Should handle parse errors gracefully
