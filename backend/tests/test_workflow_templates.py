#!/usr/bin/env python3
"""
Tests for Workflow Template Manager
Tests the workflow template system for reusability
"""

import shutil
import tempfile
from pathlib import Path
import pytest

from core.workflow_template_manager import WorkflowTemplate, WorkflowTemplateManager

# Sample template data
SAMPLE_TEMPLATE = {
    "template_id": "test_email_campaign",
    "name": "Email Campaign Workflow",
    "description": "Automated email campaign setup and execution",
    "category": "marketing",
    "input_schema": [
        {
            "name": "recipient_list",
            "type": "array",
            "required": True,
            "description": "List of email recipients"
        },
        {
            "name": "subject",
            "type": "string",
            "required": True,
            "description": "Email subject line"
        }
    ],
    "steps": [
        {
            "step_id": "validate_recipients",
            "name": "Validate Recipients",
            "action": "validate_emails",
            "inputs": {"recipient_list": "{{input.recipient_list}}"}
        },
        {
            "step_id": "send_emails",
            "name": "Send Emails",
            "action": "send_bulk_emails",
            "inputs": {
                "recipients": "{{steps.validate_recipients.valid_emails}}",
                "subject": "{{input.subject}}"
            }
        }
    ],
    "tags": ["marketing", "email", "automation"],
    "version": "1.0.0"
}


@pytest.fixture
def temp_templates_dir():
    """Create temporary directory for templates"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def template_manager(temp_templates_dir):
    """Create template manager with temporary directory"""
    return WorkflowTemplateManager(templates_dir=temp_templates_dir)


class TestTemplateCreation:
    """Tests for template creation"""

    def test_create_template(self, template_manager):
        """Test creating a new template"""
        template = template_manager.create_template(SAMPLE_TEMPLATE)

        assert template is not None
        assert template.template_id == "test_email_campaign"
        assert template.name == "Email Campaign Workflow"
        assert template.category == "marketing"
        assert len(template.tags) == 3
        assert template.is_active is True

    def test_create_template_auto_generates_id(self, template_manager):
        """Test that template_id is auto-generated if not provided"""
        template_data = SAMPLE_TEMPLATE.copy()
        del template_data["template_id"]

        template = template_manager.create_template(template_data)

        assert template is not None
        assert template.template_id.startswith("template_")
        assert len(template.template_id) == len("template_") + 8

    def test_create_duplicate_template_raises_error(self, template_manager):
        """Test that creating duplicate template raises error"""
        template_manager.create_template(SAMPLE_TEMPLATE)

        with pytest.raises(ValueError, match="already exists"):
            template_manager.create_template(SAMPLE_TEMPLATE)

    def test_create_invalid_template_raises_error(self, template_manager):
        """Test that invalid template data raises error"""
        invalid_data = {
            "template_id": "invalid",
            "name": "",  # Empty name should fail validation
            "steps": []
        }

        with pytest.raises(ValueError):
            template_manager.create_template(invalid_data)


class TestTemplateRetrieval:
    """Tests for template retrieval"""

    def test_get_existing_template(self, template_manager):
        """Test retrieving an existing template"""
        created = template_manager.create_template(SAMPLE_TEMPLATE)
        retrieved = template_manager.get_template(created.template_id)

        assert retrieved is not None
        assert retrieved.template_id == created.template_id
        assert retrieved.name == created.name
        assert retrieved.category == created.category

    def test_get_nonexistent_template(self, template_manager):
        """Test retrieving a non-existent template"""
        template = template_manager.get_template("nonexistent")
        assert template is None


class TestTemplateListing:
    """Tests for template listing"""

    def test_list_all_templates(self, template_manager):
        """Test listing all templates"""
        # Create multiple templates
        for i in range(3):
            data = SAMPLE_TEMPLATE.copy()
            data["template_id"] = f"template_{i}"
            data["name"] = f"Template {i}"
            data["category"] = "test"
            template_manager.create_template(data)

        templates = template_manager.list_templates()
        assert len(templates) == 3

    def test_list_templates_by_category(self, template_manager):
        """Test filtering templates by category"""
        # Create templates in different categories
        marketing_data = SAMPLE_TEMPLATE.copy()
        marketing_data["template_id"] = "marketing_template"
        marketing_data["category"] = "marketing"
        template_manager.create_template(marketing_data)

        sales_data = SAMPLE_TEMPLATE.copy()
        sales_data["template_id"] = "sales_template"
        sales_data["category"] = "sales"
        template_manager.create_template(sales_data)

        # Filter by marketing category
        marketing_templates = template_manager.list_templates(category="marketing")
        assert len(marketing_templates) == 1
        assert marketing_templates[0].category == "marketing"

    def test_list_templates_by_tags(self, template_manager):
        """Test filtering templates by tags"""
        data1 = SAMPLE_TEMPLATE.copy()
        data1["template_id"] = "template1"
        data1["tags"] = ["marketing", "email"]
        template_manager.create_template(data1)

        data2 = SAMPLE_TEMPLATE.copy()
        data2["template_id"] = "template2"
        data2["tags"] = ["sales", "automation"]
        template_manager.create_template(data2)

        # Filter by email tag
        email_templates = template_manager.list_templates(tags=["email"])
        assert len(email_templates) == 1
        assert "email" in email_templates[0].tags

    def test_list_active_only(self, template_manager):
        """Test filtering by active status"""
        # Create active and inactive templates
        active_data = SAMPLE_TEMPLATE.copy()
        active_data["template_id"] = "active_template"
        active_data["is_active"] = True
        template_manager.create_template(active_data)

        inactive_data = SAMPLE_TEMPLATE.copy()
        inactive_data["template_id"] = "inactive_template"
        inactive_data["is_active"] = False
        template_manager.create_template(inactive_data)

        # List only active templates
        active_only = template_manager.list_templates(active_only=True)
        assert len(active_only) == 1
        assert active_only[0].template_id == "active_template"

        # List all templates
        all_templates = template_manager.list_templates(active_only=False)
        assert len(all_templates) == 2


class TestTemplateUpdate:
    """Tests for template updates"""

    def test_update_template_name(self, template_manager):
        """Test updating template name"""
        created = template_manager.create_template(SAMPLE_TEMPLATE)

        updated = template_manager.update_template(
            created.template_id,
            {"name": "Updated Email Campaign"}
        )

        assert updated is not None
        assert updated.name == "Updated Email Campaign"
        assert updated.updated_at != created.updated_at

    def test_update_nonexistent_template(self, template_manager):
        """Test updating non-existent template"""
        result = template_manager.update_template(
            "nonexistent",
            {"name": "New Name"}
        )
        assert result is None

    def test_update_with_invalid_data(self, template_manager):
        """Test updating with invalid data"""
        created = template_manager.create_template(SAMPLE_TEMPLATE)

        with pytest.raises(ValueError):
            template_manager.update_template(
                created.template_id,
                {"name": ""}  # Empty name
            )


class TestTemplateDeletion:
    """Tests for template deletion"""

    def test_delete_template(self, template_manager):
        """Test deleting a template"""
        created = template_manager.create_template(SAMPLE_TEMPLATE)

        # Verify it exists
        assert template_manager.get_template(created.template_id) is not None

        # Delete it
        result = template_manager.delete_template(created.template_id)
        assert result is True

        # Verify it's gone
        assert template_manager.get_template(created.template_id) is None

    def test_delete_nonexistent_template(self, template_manager):
        """Test deleting non-existent template"""
        result = template_manager.delete_template("nonexistent")
        assert result is False


class TestWorkflowFromTemplate:
    """Tests for creating workflows from templates"""

    def test_create_workflow_from_template(self, template_manager):
        """Test creating a workflow definition from a template"""
        template = template_manager.create_template(SAMPLE_TEMPLATE)

        workflow_data = {
            "name": "My Email Campaign",
            "description": "Custom email campaign",
            "created_by": "user123"
        }

        workflow_def = template_manager.create_workflow_from_template(
            template_id=template.template_id,
            workflow_data=workflow_data
        )

        assert workflow_def is not None
        assert workflow_def["name"] == "My Email Campaign"
        assert workflow_def["description"] == "Custom email campaign"
        assert workflow_def["category"] == "marketing"
        assert workflow_def["template_id"] == template.template_id
        assert workflow_def["template_version"] == "1.0.0"
        assert "workflow_id" in workflow_def
        assert len(workflow_def["input_schema"]) == 2
        assert len(workflow_def["steps"]) == 2

    def test_create_workflow_from_inactive_template_fails(self, template_manager):
        """Test that creating workflow from inactive template fails"""
        template_data = SAMPLE_TEMPLATE.copy()
        template_data["is_active"] = False
        template = template_manager.create_template(template_data)

        with pytest.raises(ValueError, match="not active"):
            template_manager.create_workflow_from_template(
                template_id=template.template_id,
                workflow_data={}
            )

    def test_create_workflow_from_nonexistent_template_fails(self, template_manager):
        """Test that creating workflow from non-existent template fails"""
        with pytest.raises(ValueError, match="not found"):
            template_manager.create_workflow_from_template(
                template_id="nonexistent",
                workflow_data={}
            )


class TestIndexManagement:
    """Tests for template index management"""

    def test_index_created_on_template_creation(self, template_manager, temp_templates_dir):
        """Test that index file is created"""
        template_manager.create_template(SAMPLE_TEMPLATE)

        index_file = Path(temp_templates_dir) / "template_index.json"
        assert index_file.exists()

    def test_index_updated_on_template_deletion(self, template_manager):
        """Test that index is updated when template is deleted"""
        template = template_manager.create_template(SAMPLE_TEMPLATE)
        template_manager.delete_template(template.template_id)

        index = template_manager._load_index()
        assert template.template_id not in index.get("templates", {})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
