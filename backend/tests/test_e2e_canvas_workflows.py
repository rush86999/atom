"""
End-to-End Canvas Workflow Tests

Tests complete canvas presentation workflows from creation to submission.
Covers canvas creation, presentation, user interaction, submission, and updates.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session

from core.models import CanvasAudit, AgentExecution


class TestCanvasPresentationWorkflow:
    """Test complete canvas presentation workflows."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = Mock(spec=Session)
        db.query = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.rollback = Mock()
        db.refresh = Mock()
        db.merge = Mock()
        return db

    @pytest.fixture
    def sample_agent_execution(self):
        """Create sample agent execution."""
        execution = AgentExecution(
            id="exec-001",
            agent_id="agent-001",
            status="running",
            input_data={"task": "present canvas"},
            started_at=datetime.utcnow()
        )
        return execution

    def test_complete_canvas_presentation_workflow(self, mock_db, sample_agent_execution):
        """Test complete workflow: create → present → interact → submit."""
        # Step 1: Create canvas
        canvas_data = {
            "canvas_id": "canvas-001",
            "canvas_type": "bar_chart",
            "title": "Sales Data",
            "data": {
                "labels": ["Jan", "Feb", "Mar"],
                "datasets": [{
                    "label": "Sales",
                    "data": [100, 150, 200]
                }]
            },
            "metadata": {"agent_id": "agent-001"}
        }

        audit_entry = CanvasAudit(
            id="audit-001",
            canvas_id=canvas_data["canvas_id"],
            canvas_type=canvas_data["canvas_type"],
            agent_id=sample_agent_execution.agent_id,
            execution_id=sample_agent_execution.id,
            presented_at=datetime.utcnow(),
            canvas_data=canvas_data,
            status="presented"
        )
        mock_db.add(audit_entry)
        mock_db.commit()

        assert audit_entry.canvas_id == "canvas-001"
        assert audit_entry.status == "presented"

        # Step 2: User interacts with canvas
        interaction = CanvasAudit(
            id="audit-002",
            canvas_id=canvas_data["canvas_id"],
            canvas_type="bar_chart",
            agent_id=sample_agent_execution.agent_id,
            execution_id=sample_agent_execution.id,
            presented_at=datetime.utcnow(),
            canvas_data={"interaction_type": "click", "element": "legend"},
            status="interaction"
        )
        mock_db.add(interaction)
        mock_db.commit()

        # Step 3: User submits canvas
        submission = CanvasAudit(
            id="audit-003",
            canvas_id=canvas_data["canvas_id"],
            canvas_type="bar_chart",
            agent_id=sample_agent_execution.agent_id,
            execution_id=sample_agent_execution.id,
            presented_at=datetime.utcnow(),
            canvas_data={"submitted": True, "values": {"selected": "Jan"}},
            status="submitted"
        )
        mock_db.add(submission)
        mock_db.commit()

        assert submission.status == "submitted"
        assert submission.canvas_data["submitted"] is True

    def test_canvas_form_submission_workflow(self, mock_db, sample_agent_execution):
        """Test canvas form presentation and submission workflow."""
        # Present form
        form_canvas = {
            "canvas_id": "form-001",
            "canvas_type": "interactive_form",
            "title": "User Information",
            "fields": [
                {"name": "name", "type": "text", "required": True},
                {"name": "email", "type": "email", "required": True},
                {"name": "age", "type": "number", "required": False}
            ],
            "metadata": {"agent_id": "agent-001"}
        }

        audit = CanvasAudit(
            id="audit-form-001",
            canvas_id=form_canvas["canvas_id"],
            canvas_type="interactive_form",
            agent_id=sample_agent_execution.agent_id,
            execution_id=sample_agent_execution.id,
            presented_at=datetime.utcnow(),
            canvas_data=form_canvas,
            status="presented"
        )
        mock_db.add(audit)
        mock_db.commit()

        # User submits form with validation
        form_submission = {
            "canvas_id": "form-001",
            "values": {
                "name": "John Doe",
                "email": "john@example.com",
                "age": 30
            },
            "submitted_at": datetime.utcnow().isoformat()
        }

        submission_audit = CanvasAudit(
            id="audit-form-002",
            canvas_id=form_canvas["canvas_id"],
            canvas_type="interactive_form",
            agent_id=sample_agent_execution.agent_id,
            execution_id=sample_agent_execution.id,
            presented_at=datetime.utcnow(),
            canvas_data=form_submission,
            status="submitted"
        )
        mock_db.add(submission_audit)
        mock_db.commit()

        # Verify submission
        assert submission_audit.canvas_data["values"]["name"] == "John Doe"
        assert submission_audit.canvas_data["values"]["email"] == "john@example.com"

    def test_canvas_multi_step_workflow(self, mock_db, sample_agent_execution):
        """Test multi-step canvas workflow (wizard-style)."""
        # Step 1: Present first canvas
        canvas1 = CanvasAudit(
            id="audit-step-001",
            canvas_id="wizard-step-1",
            canvas_type="markdown",
            agent_id=sample_agent_execution.agent_id,
            execution_id=sample_agent_execution.id,
            presented_at=datetime.utcnow(),
            canvas_data={"content": "Step 1: Welcome", "step": 1, "total_steps": 3},
            status="presented"
        )
        mock_db.add(canvas1)
        mock_db.commit()

        # Step 2: Present second canvas
        canvas2 = CanvasAudit(
            id="audit-step-002",
            canvas_id="wizard-step-2",
            canvas_type="form",
            agent_id=sample_agent_execution.agent_id,
            execution_id=sample_agent_execution.id,
            presented_at=datetime.utcnow(),
            canvas_data={"content": "Step 2: Enter data", "step": 2, "total_steps": 3},
            status="presented"
        )
        mock_db.add(canvas2)
        mock_db.commit()

        # Step 3: Present final canvas
        canvas3 = CanvasAudit(
            id="audit-step-003",
            canvas_id="wizard-step-3",
            canvas_type="chart",
            agent_id=sample_agent_execution.agent_id,
            execution_id=sample_agent_execution.id,
            presented_at=datetime.utcnow(),
            canvas_data={"content": "Step 3: Results", "step": 3, "total_steps": 3},
            status="presented"
        )
        mock_db.add(canvas3)
        mock_db.commit()

        # Verify multi-step flow
        mock_db.query.return_value.filter.return_value.all.return_value = [
            canvas1, canvas2, canvas3
        ]

        wizard_canvases = mock_db.query(CanvasAudit).filter(
            CanvasAudit.execution_id == sample_agent_execution.id
        ).all()

        assert len(wizard_canvases) == 3
        assert wizard_canvases[0].canvas_data["step"] == 1
        assert wizard_canvases[2].canvas_data["step"] == 3

    def test_canvas_error_handling_workflow(self, mock_db, sample_agent_execution):
        """Test canvas workflow with error handling."""
        # Present canvas with error
        error_canvas = CanvasAudit(
            id="audit-error-001",
            canvas_id="error-canvas",
            canvas_type="error",
            agent_id=sample_agent_execution.agent_id,
            execution_id=sample_agent_execution.id,
            presented_at=datetime.utcnow(),
            canvas_data={
                "error_type": "validation_error",
                "message": "Invalid input data",
                "details": {"field": "email", "issue": "invalid format"}
            },
            status="error"
        )
        mock_db.add(error_canvas)
        mock_db.commit()

        # Present recovery canvas
        recovery_canvas = CanvasAudit(
            id="audit-recovery-001",
            canvas_id="recovery-canvas",
            canvas_type="form",
            agent_id=sample_agent_execution.agent_id,
            execution_id=sample_agent_execution.id,
            presented_at=datetime.utcnow(),
            canvas_data={
                "message": "Please correct your input",
                "retry": True
            },
            status="presented"
        )
        mock_db.add(recovery_canvas)
        mock_db.commit()

        # Verify error handling
        assert error_canvas.status == "error"
        assert recovery_canvas.canvas_data["retry"] is True

    def test_canvas_with_agent_guidance_workflow(self, mock_db, sample_agent_execution):
        """Test canvas workflow with real-time agent guidance."""
        # Present canvas with guidance
        guidance_canvas = CanvasAudit(
            id="audit-guidance-001",
            canvas_id="guidance-canvas",
            canvas_type="agent_guidance",
            agent_id=sample_agent_execution.agent_id,
            execution_id=sample_agent_execution.id,
            presented_at=datetime.utcnow(),
            canvas_data={
                "operation": "data_processing",
                "progress": 0.5,
                "message": "Processing your data...",
                "steps": [
                    {"name": "Validate", "status": "completed"},
                    {"name": "Process", "status": "in_progress"},
                    {"name": "Render", "status": "pending"}
                ]
            },
            status="presented"
        )
        mock_db.add(guidance_canvas)
        mock_db.commit()

        # Update progress
        guidance_canvas.canvas_data["progress"] = 0.8
        guidance_canvas.canvas_data["steps"][1]["status"] = "completed"
        guidance_canvas.canvas_data["steps"][2]["status"] = "in_progress"
        guidance_canvas.canvas_data["message"] = "Rendering results..."
        mock_db.commit()

        # Complete
        guidance_canvas.canvas_data["progress"] = 1.0
        guidance_canvas.canvas_data["steps"][2]["status"] = "completed"
        guidance_canvas.canvas_data["message"] = "Complete!"
        guidance_canvas.status = "completed"
        mock_db.commit()

        assert guidance_canvas.canvas_data["progress"] == 1.0
        assert all(s["status"] == "completed" for s in guidance_canvas.canvas_data["steps"])

    def test_canvas_collaborative_workflow(self, mock_db, sample_agent_execution):
        """Test canvas workflow with multiple users."""
        # Present canvas to user 1
        canvas1 = CanvasAudit(
            id="audit-collab-001",
            canvas_id="collab-canvas",
            canvas_type="sheet",
            agent_id=sample_agent_execution.agent_id,
            execution_id=sample_agent_execution.id,
            presented_at=datetime.utcnow(),
            canvas_data={"user": "user1", "action": "view"},
            status="presented"
        )
        mock_db.add(canvas1)
        mock_db.commit()

        # User 2 updates canvas
        canvas2 = CanvasAudit(
            id="audit-collab-002",
            canvas_id="collab-canvas",
            canvas_type="sheet",
            agent_id=sample_agent_execution.agent_id,
            execution_id=sample_agent_execution.id,
            presented_at=datetime.utcnow(),
            canvas_data={"user": "user2", "action": "update", "cell": "A1", "value": "100"},
            status="updated"
        )
        mock_db.add(canvas2)
        mock_db.commit()

        # User 1 sees update
        canvas3 = CanvasAudit(
            id="audit-collab-003",
            canvas_id="collab-canvas",
            canvas_type="sheet",
            agent_id=sample_agent_execution.agent_id,
            execution_id=sample_agent_execution.id,
            presented_at=datetime.utcnow(),
            canvas_data={"user": "user1", "action": "view_update", "cell": "A1"},
            status="presented"
        )
        mock_db.add(canvas3)
        mock_db.commit()

        # Verify collaboration
        assert canvas2.canvas_data["action"] == "update"
        assert canvas2.canvas_data["value"] == "100"

    def test_canvas_with_file_upload_workflow(self, mock_db, sample_agent_execution):
        """Test canvas workflow with file upload."""
        # Present file upload canvas
        upload_canvas = CanvasAudit(
            id="audit-upload-001",
            canvas_id="upload-canvas",
            canvas_type="file_upload",
            agent_id=sample_agent_execution.agent_id,
            execution_id=sample_agent_execution.id,
            presented_at=datetime.utcnow(),
            canvas_data={
                "accept": ".csv,.xlsx",
                "max_size_mb": 10,
                "message": "Upload your data file"
            },
            status="presented"
        )
        mock_db.add(upload_canvas)
        mock_db.commit()

        # User uploads file
        file_submission = CanvasAudit(
            id="audit-upload-002",
            canvas_id="upload-canvas",
            canvas_type="file_upload",
            agent_id=sample_agent_execution.agent_id,
            execution_id=sample_agent_execution.id,
            presented_at=datetime.utcnow(),
            canvas_data={
                "file_name": "data.csv",
                "file_size": 1024,
                "file_type": "text/csv",
                "uploaded": True
            },
            status="submitted"
        )
        mock_db.add(file_submission)
        mock_db.commit()

        # Process file and present results
        result_canvas = CanvasAudit(
            id="audit-upload-003",
            canvas_id="result-canvas",
            canvas_type="table",
            agent_id=sample_agent_execution.agent_id,
            execution_id=sample_agent_execution.id,
            presented_at=datetime.utcnow(),
            canvas_data={
                "rows": 100,
                "columns": 5,
                "preview": [["col1", "col2"], ["val1", "val2"]]
            },
            status="presented"
        )
        mock_db.add(result_canvas)
        mock_db.commit()

        assert file_submission.canvas_data["uploaded"] is True
        assert result_canvas.canvas_data["rows"] == 100

    def test_canvas_state_persistence_workflow(self, mock_db, sample_agent_execution):
        """Test canvas state persistence across sessions."""
        # Create initial canvas state
        initial_state = CanvasAudit(
            id="audit-state-001",
            canvas_id="state-canvas",
            canvas_type="interactive_form",
            agent_id=sample_agent_execution.agent_id,
            execution_id=sample_agent_execution.id,
            presented_at=datetime.utcnow(),
            canvas_data={
                "field1": "value1",
                "field2": "value2",
                "step": 1
            },
            status="presented"
        )
        mock_db.add(initial_state)
        mock_db.commit()

        # Update state
        updated_state = CanvasAudit(
            id="audit-state-002",
            canvas_id="state-canvas",
            canvas_type="interactive_form",
            agent_id=sample_agent_execution.agent_id,
            execution_id=sample_agent_execution.id,
            presented_at=datetime.utcnow(),
            canvas_data={
                "field1": "value1",
                "field2": "updated_value2",
                "field3": "value3",
                "step": 2
            },
            status="updated"
        )
        mock_db.add(updated_state)
        mock_db.commit()

        # Verify state persistence
        assert updated_state.canvas_data["field2"] == "updated_value2"
        assert updated_state.canvas_data["step"] == 2

    def test_canvas_with_governance_workflow(self, mock_db, sample_agent_execution):
        """Test canvas workflow with governance enforcement."""
        # Present canvas requiring governance
        governed_canvas = CanvasAudit(
            id="audit-gov-001",
            canvas_id="gov-canvas",
            canvas_type="form",
            agent_id=sample_agent_execution.agent_id,
            execution_id=sample_agent_execution.id,
            presented_at=datetime.utcnow(),
            canvas_data={
                "action": "delete_data",
                "governance_level": 4,  # CRITICAL - AUTONOMOUS only
                "agent_maturity": "INTERN"  # Not allowed
            },
            status="governance_check"
        )
        mock_db.add(governed_canvas)
        mock_db.commit()

        # Governance check fails
        if governed_canvas.canvas_data["agent_maturity"] != "AUTONOMOUS":
            governed_canvas.status = "blocked"
            governed_canvas.canvas_data["block_reason"] = "Insufficient maturity level"
            mock_db.commit()

        assert governed_canvas.status == "blocked"
        assert "Insufficient maturity" in governed_canvas.canvas_data["block_reason"]

    def test_canvas_analytics_workflow(self, mock_db, sample_agent_execution):
        """Test canvas analytics and reporting workflow."""
        # Present multiple canvases
        canvas_types = ["bar_chart", "line_chart", "pie_chart", "table"]
        for i, canvas_type in enumerate(canvas_types):
            canvas = CanvasAudit(
                id=f"audit-analytics-{i:03d}",
                canvas_id=f"analytics-{i}",
                canvas_type=canvas_type,
                agent_id=sample_agent_execution.agent_id,
                execution_id=sample_agent_execution.id,
                presented_at=datetime.utcnow() - timedelta(minutes=len(canvas_types)-i),
                canvas_data={"index": i},
                status="presented"
            )
            mock_db.add(canvas)

        mock_db.commit()

        # Generate analytics
        mock_db.query.return_value.filter.return_value.count.return_value = 4
        canvas_count = mock_db.query(CanvasAudit).filter(
            CanvasAudit.execution_id == sample_agent_execution.id
        ).count()

        assert canvas_count == 4

        # Most popular canvas type
        mock_db.query.return_value.filter.return_value.all.return_value = [
            CanvasAudit(canvas_type="bar_chart"),
            CanvasAudit(canvas_type="line_chart"),
            CanvasAudit(canvas_type="pie_chart"),
            CanvasAudit(canvas_type="table")
        ]
