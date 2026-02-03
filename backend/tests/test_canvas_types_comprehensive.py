"""
Comprehensive Tests for Specialized Canvas Types

Tests all canvas type services, API routes, and tools.
"""
from datetime import datetime
import pytest
from sqlalchemy.orm import Session

from core.canvas_coding_service import CodingCanvasService
from core.canvas_docs_service import DocumentationCanvasService
from core.canvas_email_service import EmailCanvasService
from core.canvas_orchestration_service import OrchestrationCanvasService
from core.canvas_sheets_service import SpreadsheetCanvasService
from core.canvas_terminal_service import TerminalCanvasService
from core.canvas_type_registry import CanvasType, MaturityLevel, canvas_type_registry


class TestCanvasTypeRegistry:
    """Tests for CanvasTypeRegistry."""

    def test_all_canvas_types_registered(self):
        """Test that all canvas types are registered."""
        all_types = canvas_type_registry.get_all_types()
        assert len(all_types) == 7
        assert "generic" in all_types
        assert "docs" in all_types
        assert "email" in all_types
        assert "sheets" in all_types
        assert "orchestration" in all_types
        assert "terminal" in all_types
        assert "coding" in all_types

    def test_validate_canvas_type(self):
        """Test canvas type validation."""
        assert canvas_type_registry.validate_canvas_type("docs") is True
        assert canvas_type_registry.validate_canvas_type("invalid") is False

    def test_validate_component(self):
        """Test component validation."""
        assert canvas_type_registry.validate_component("docs", "rich_editor") is True
        assert canvas_type_registry.validate_component("docs", "invalid") is False

    def test_validate_layout(self):
        """Test layout validation."""
        assert canvas_type_registry.validate_layout("docs", "document") is True
        assert canvas_type_registry.validate_layout("docs", "invalid") is False

    def test_governance_permissions(self):
        """Test governance permission checks."""
        # Docs: INTERN+ can create
        assert canvas_type_registry.check_governance_permission("docs", "intern", "create") is True
        assert canvas_type_registry.check_governance_permission("docs", "student", "create") is False

        # Email: SUPERVISED+ can send
        assert canvas_type_registry.check_governance_permission("email", "autonomous", "send") is True
        assert canvas_type_registry.check_governance_permission("email", "supervised", "send") is False

    def test_min_maturity_levels(self):
        """Test minimum maturity levels."""
        assert canvas_type_registry.get_min_maturity("generic") == MaturityLevel.STUDENT
        assert canvas_type_registry.get_min_maturity("docs") == MaturityLevel.INTERN
        assert canvas_type_registry.get_min_maturity("email") == MaturityLevel.SUPERVISED
        assert canvas_type_registry.get_min_maturity("orchestration") == MaturityLevel.SUPERVISED


class TestDocumentationCanvas:
    """Tests for Documentation Canvas."""

    def test_create_document_canvas(self, db_session: Session):
        """Test creating a documentation canvas."""
        service = DocumentationCanvasService(db_session)
        result = service.create_document_canvas(
            user_id="test-user",
            title="Test Doc",
            content="# Test Content",
            enable_comments=True,
            enable_versioning=True
        )

        assert result["success"] is True
        assert "canvas_id" in result
        assert result["title"] == "Test Doc"
        assert result["enable_comments"] is True
        assert result["enable_versioning"] is True

    def test_update_document_content(self, db_session: Session):
        """Test updating document content."""
        service = DocumentationCanvasService(db_session)

        # Create first
        create_result = service.create_document_canvas(
            user_id="test-user",
            title="Test Doc",
            content="# Original"
        )
        canvas_id = create_result["canvas_id"]

        # Update
        update_result = service.update_document_content(
            canvas_id=canvas_id,
            user_id="test-user",
            content="# Updated",
            changes="Updated content"
        )

        assert update_result["success"] is True
        assert update_result["content"] == "# Updated"

    def test_add_comment(self, db_session: Session):
        """Test adding a comment."""
        service = DocumentationCanvasService(db_session)

        create_result = service.create_document_canvas(
            user_id="test-user",
            title="Test Doc",
            content="# Test"
        )
        canvas_id = create_result["canvas_id"]

        comment_result = service.add_comment(
            canvas_id=canvas_id,
            user_id="test-user",
            content="This is a comment"
        )

        assert comment_result["success"] is True
        assert "comment_id" in comment_result

    def test_version_history(self, db_session: Session):
        """Test version history."""
        service = DocumentationCanvasService(db_session)

        create_result = service.create_document_canvas(
            user_id="test-user",
            title="Test Doc",
            content="# Version 1"
        )
        canvas_id = create_result["canvas_id"]

        # Update to create version 2
        service.update_document_content(
            canvas_id=canvas_id,
            user_id="test-user",
            content="# Version 2"
        )

        # Get versions
        versions_result = service.get_document_versions(canvas_id)

        assert versions_result["success"] is True
        assert versions_result["total"] >= 2

    def test_table_of_contents(self, db_session: Session):
        """Test table of contents generation."""
        service = DocumentationCanvasService(db_session)

        create_result = service.create_document_canvas(
            user_id="test-user",
            title="Test Doc",
            content="# Heading 1\n\n## Heading 2\n\n### Heading 3"
        )
        canvas_id = create_result["canvas_id"]

        toc_result = service.get_table_of_contents(canvas_id)

        assert toc_result["success"] is True
        assert toc_result["total"] == 3
        assert toc_result["headings"][0]["level"] == 1


class TestEmailCanvas:
    """Tests for Email Canvas."""

    def test_create_email_canvas(self, db_session: Session):
        """Test creating an email canvas."""
        service = EmailCanvasService(db_session)
        result = service.create_email_canvas(
            user_id="test-user",
            subject="Test Subject",
            recipients=["test@example.com"]
        )

        assert result["success"] is True
        assert "canvas_id" in result
        assert "thread_id" in result
        assert result["subject"] == "Test Subject"

    def test_add_message_to_thread(self, db_session: Session):
        """Test adding a message to a thread."""
        service = EmailCanvasService(db_session)

        create_result = service.create_email_canvas(
            user_id="test-user",
            subject="Test",
            recipients=["test@example.com"]
        )
        canvas_id = create_result["canvas_id"]

        message_result = service.add_message_to_thread(
            canvas_id=canvas_id,
            user_id="test-user",
            from_email="sender@example.com",
            to_emails=["test@example.com"],
            subject="Test",
            body="Test body"
        )

        assert message_result["success"] is True
        assert "message_id" in message_result

    def test_save_draft(self, db_session: Session):
        """Test saving a draft."""
        service = EmailCanvasService(db_session)

        create_result = service.create_email_canvas(
            user_id="test-user",
            subject="Test",
            recipients=["test@example.com"]
        )
        canvas_id = create_result["canvas_id"]

        draft_result = service.save_draft(
            canvas_id=canvas_id,
            user_id="test-user",
            to_emails=["recipient@example.com"],
            subject="Draft Subject",
            body="Draft body"
        )

        assert draft_result["success"] is True
        assert "draft_id" in draft_result


class TestSpreadsheetCanvas:
    """Tests for Spreadsheet Canvas."""

    def test_create_spreadsheet_canvas(self, db_session: Session):
        """Test creating a spreadsheet canvas."""
        service = SpreadsheetCanvasService(db_session)
        result = service.create_spreadsheet_canvas(
            user_id="test-user",
            title="Test Sheet",
            data={"A1": "Value", "B1": 100}
        )

        assert result["success"] is True
        assert "canvas_id" in result
        assert result["title"] == "Test Sheet"
        assert "A1" in result["cells"]

    def test_update_cell(self, db_session: Session):
        """Test updating a cell."""
        service = SpreadsheetCanvasService(db_session)

        create_result = service.create_spreadsheet_canvas(
            user_id="test-user",
            title="Test Sheet",
            data={"A1": "Original"}
        )
        canvas_id = create_result["canvas_id"]

        update_result = service.update_cell(
            canvas_id=canvas_id,
            user_id="test-user",
            cell_ref="A1",
            value="Updated"
        )

        assert update_result["success"] is True
        assert update_result["value"] == "Updated"

    def test_add_chart(self, db_session: Session):
        """Test adding a chart."""
        service = SpreadsheetCanvasService(db_session)

        create_result = service.create_spreadsheet_canvas(
            user_id="test-user",
            title="Test Sheet",
            data={"A1": "Label", "B1": 100}
        )
        canvas_id = create_result["canvas_id"]

        chart_result = service.add_chart(
            canvas_id=canvas_id,
            user_id="test-user",
            chart_type="bar",
            data_range="A1:B1",
            title="Test Chart"
        )

        assert chart_result["success"] is True
        assert "chart_id" in chart_result


class TestOrchestrationCanvas:
    """Tests for Orchestration Canvas."""

    def test_create_orchestration_canvas(self, db_session: Session):
        """Test creating an orchestration canvas."""
        service = OrchestrationCanvasService(db_session)
        result = service.create_orchestration_canvas(
            user_id="test-user",
            title="Test Workflow",
            tasks=[
                {"title": "Task 1", "status": "todo"},
                {"title": "Task 2", "status": "in_progress"}
            ]
        )

        assert result["success"] is True
        assert "canvas_id" in result
        assert len(result["tasks"]) == 2

    def test_add_integration_node(self, db_session: Session):
        """Test adding a workflow node."""
        service = OrchestrationCanvasService(db_session)

        create_result = service.create_orchestration_canvas(
            user_id="test-user",
            title="Test Workflow"
        )
        canvas_id = create_result["canvas_id"]

        node_result = service.add_workflow_node(
            canvas_id=canvas_id,
            user_id="test-user",
            node_name="slack",
            node_type="action",
            config={},
            position={"x": 100, "y": 200}
        )

        assert node_result["success"] is True
        assert "node_id" in node_result
        assert node_result["node_name"] == "slack"

    def test_connect_nodes(self, db_session: Session):
        """Test connecting nodes."""
        service = OrchestrationCanvasService(db_session)

        create_result = service.create_orchestration_canvas(
            user_id="test-user",
            title="Test Workflow"
        )
        canvas_id = create_result["canvas_id"]

        # Add two nodes
        node1 = service.add_workflow_node(
            canvas_id=canvas_id,
            user_id="test-user",
            node_name="gmail",
            node_type="trigger"
        )

        node2 = service.add_workflow_node(
            canvas_id=canvas_id,
            user_id="test-user",
            node_name="slack",
            node_type="action"
        )

        # Connect them
        connect_result = service.connect_nodes(
            canvas_id=canvas_id,
            user_id="test-user",
            from_node=node1["node_id"],
            to_node=node2["node_id"]
        )

        assert connect_result["success"] is True
        assert "connection_id" in connect_result


class TestTerminalCanvas:
    """Tests for Terminal Canvas."""

    def test_create_terminal_canvas(self, db_session: Session):
        """Test creating a terminal canvas."""
        service = TerminalCanvasService(db_session)
        result = service.create_terminal_canvas(
            user_id="test-user",
            command="ls -la",
            working_dir="/home/user"
        )

        assert result["success"] is True
        assert "canvas_id" in result
        assert result["command"] == "ls -la"

    def test_add_output(self, db_session: Session):
        """Test adding command output."""
        service = TerminalCanvasService(db_session)

        create_result = service.create_terminal_canvas(
            user_id="test-user",
            command="echo hello"
        )
        canvas_id = create_result["canvas_id"]

        output_result = service.add_output(
            canvas_id=canvas_id,
            user_id="test-user",
            command="echo hello",
            output="hello\n",
            exit_code=0
        )

        assert output_result["success"] is True
        assert "output_id" in output_result


class TestCodingCanvas:
    """Tests for Coding Canvas."""

    def test_create_coding_canvas(self, db_session: Session):
        """Test creating a coding canvas."""
        service = CodingCanvasService(db_session)
        result = service.create_coding_canvas(
            user_id="test-user",
            repo="github.com/user/repo",
            branch="main"
        )

        assert result["success"] is True
        assert "canvas_id" in result
        assert result["repo"] == "github.com/user/repo"
        assert result["branch"] == "main"

    def test_add_file(self, db_session: Session):
        """Test adding a file."""
        service = CodingCanvasService(db_session)

        create_result = service.create_coding_canvas(
            user_id="test-user",
            repo="test/repo",
            branch="main"
        )
        canvas_id = create_result["canvas_id"]

        file_result = service.add_file(
            canvas_id=canvas_id,
            user_id="test-user",
            path="src/main.py",
            content="print('hello')",
            language="python"
        )

        assert file_result["success"] is True
        assert "file_id" in file_result
        assert file_result["path"] == "src/main.py"

    def test_add_diff(self, db_session: Session):
        """Test adding a diff."""
        service = CodingCanvasService(db_session)

        create_result = service.create_coding_canvas(
            user_id="test-user",
            repo="test/repo",
            branch="main"
        )
        canvas_id = create_result["canvas_id"]

        diff_result = service.add_diff(
            canvas_id=canvas_id,
            user_id="test-user",
            file_path="src/main.py",
            old_content="print('old')",
            new_content="print('new')"
        )

        assert diff_result["success"] is True
        assert "diff_id" in diff_result


# Note: db_session fixture is imported from conftest.py
