from datetime import datetime
from enum import Enum
import json
import logging
import os
from typing import Any, Dict, List, Optional, Union
import uuid
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Import advanced workflow system
from .advanced_workflow_system import (
    AdvancedWorkflowDefinition,
    InputParameter,
    ParameterType,
    WorkflowStep,
)
from .industry_workflow_templates import Industry, IndustryWorkflowTemplate


class TemplateType(str, Enum):
    LEGACY = "legacy"  # Original node-based templates
    ADVANCED = "advanced"  # New multi-step workflow templates
    INDUSTRY = "industry"  # Industry-specific templates

class WorkflowTemplate(BaseModel):
    id: str
    name: str
    description: str
    category: str
    author: str
    version: str
    integrations: List[str]
    complexity: str  # "Beginner", "Intermediate", "Advanced"
    workflow_data: Dict[str, Any]
    created_at: str
    downloads: int = 0
    rating: float = 0.0
    template_type: TemplateType = TemplateType.LEGACY
    tags: List[str] = []
    estimated_duration: Optional[int] = None  # seconds
    multi_input_support: bool = False
    multi_step_support: bool = False
    multi_output_support: bool = False
    pause_resume_support: bool = False
    prerequisites: List[str] = []
    industry: Optional[str] = None

class AdvancedWorkflowTemplate(BaseModel):
    """Enhanced template for advanced multi-step workflows"""
    id: str
    name: str
    description: str
    category: str
    author: str
    version: str
    integrations: List[str]
    complexity: str
    tags: List[str] = []

    # Advanced workflow specific fields
    input_schema: List[Dict[str, Any]]
    steps: List[Dict[str, Any]]
    output_config: Optional[Dict[str, Any]] = None
    estimated_duration: int = 0
    prerequisites: List[str] = []
    pause_resume_support: bool = True
    multi_input_support: bool = True
    multi_step_support: bool = True
    multi_output_support: bool = True

    # Metadata
    created_at: str
    updated_at: str
    downloads: int = 0
    rating: float = 0.0
    use_cases: List[str] = []
    benefits: List[str] = []

class MarketplaceEngine:
    def __init__(self):
        self.templates_dir = os.path.join(os.path.dirname(__file__), "..", "marketplace_templates")
        os.makedirs(self.templates_dir, exist_ok=True)
        self.advanced_templates_dir = os.path.join(self.templates_dir, "advanced")
        os.makedirs(self.advanced_templates_dir, exist_ok=True)
        self.industry_templates_dir = os.path.join(self.templates_dir, "industry")
        os.makedirs(self.industry_templates_dir, exist_ok=True)

        self._initialize_default_templates()
        self._initialize_advanced_templates()
        self._initialize_industry_templates()

    def _initialize_default_templates(self):
        """Create default templates if they don't exist"""
        defaults = [
            {
                "id": "tmpl_email_summarizer",
                "name": "Daily Email Summarizer",
                "description": "Summarize unread emails from Gmail and send a digest to Slack.",
                "category": "Productivity",
                "author": "ATOM Team",
                "version": "1.0.0",
                "integrations": ["gmail", "slack", "openai"],
                "complexity": "Beginner",
                "workflow_data": {
                    "nodes": [
                        {"id": "1", "type": "trigger", "label": "Every Morning", "config": {"cron": "0 9 * * *"}},
                        {"id": "2", "type": "action", "label": "Fetch Unread Emails", "config": {"integration": "gmail", "action": "list_messages", "query": "is:unread"}},
                        {"id": "3", "type": "action", "label": "Summarize with AI", "config": {"integration": "openai", "action": "summarize"}},
                        {"id": "4", "type": "action", "label": "Send to Slack", "config": {"integration": "slack", "action": "send_message"}}
                    ],
                    "edges": [
                        {"source": "1", "target": "2"},
                        {"source": "2", "target": "3"},
                        {"source": "3", "target": "4"}
                    ]
                }
            },
            {
                "id": "tmpl_lead_enrichment",
                "name": "Sales Lead Enrichment",
                "description": "When a new lead is added to Salesforce, enrich with LinkedIn data and notify team.",
                "category": "Sales",
                "author": "ATOM Team",
                "version": "1.0.0",
                "integrations": ["salesforce", "linkedin", "slack"],
                "complexity": "Intermediate",
                "workflow_data": {
                    "nodes": [
                        {"id": "1", "type": "trigger", "label": "New Salesforce Lead", "config": {"integration": "salesforce", "event": "new_record", "object": "Lead"}},
                        {"id": "2", "type": "action", "label": "Enrich from LinkedIn", "config": {"integration": "linkedin", "action": "get_profile"}},
                        {"id": "3", "type": "action", "label": "Update Salesforce", "config": {"integration": "salesforce", "action": "update_record"}},
                        {"id": "4", "type": "action", "label": "Notify Sales Channel", "config": {"integration": "slack", "action": "send_message"}}
                    ],
                    "edges": [
                        {"source": "1", "target": "2"},
                        {"source": "2", "target": "3"},
                        {"source": "3", "target": "4"}
                    ]
                }
            },
            {
                "id": "tmpl_followup_tasks",
                "name": "Automated Follow-up Tasks",
                "description": "Fetch unread emails from Gmail, extract tasks using AI, and save them to Notion.",
                "category": "Productivity",
                "author": "ATOM Team",
                "version": "1.0.0",
                "integrations": ["gmail", "openai", "notion"],
                "complexity": "Intermediate",
                "workflow_data": {
                    "nodes": [
                        {"id": "1", "type": "trigger", "label": "Fetch Emails", "config": {"integration": "gmail", "action": "list_messages", "query": "is:unread label:followup"}},
                        {"id": "2", "type": "action", "label": "Extract Tasks with AI", "config": {"integration": "openai", "action": "extract_tasks"}},
                        {"id": "3", "type": "action", "label": "Create Notion Tasks", "config": {"integration": "notion", "action": "create_page"}}
                    ],
                    "edges": [
                        {"source": "1", "target": "2"},
                        {"source": "2", "target": "3"}
                    ]
                }
            }
        ]

        for tmpl in defaults:
            path = os.path.join(self.templates_dir, f"{tmpl['id']}.json")
            if not os.path.exists(path):
                # Add metadata fields
                tmpl["created_at"] = datetime.now().isoformat()
                tmpl["downloads"] = 0
                tmpl["rating"] = 5.0
                with open(path, "w") as f:
                    json.dump(tmpl, f, indent=2)

    def list_templates(self, category: Optional[str] = None) -> List[WorkflowTemplate]:
        """List available workflow templates"""
        templates = []
        for filename in os.listdir(self.templates_dir):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(self.templates_dir, filename), "r") as f:
                        data = json.load(f)
                        if category and data.get("category") != category:
                            continue
                        templates.append(WorkflowTemplate(**data))
                except Exception as e:
                    logger.error(f"Error loading template {filename}: {e}")
        return templates

    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """Get a specific template by ID"""
        path = os.path.join(self.templates_dir, f"{template_id}.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
                # Increment download count
                data["downloads"] += 1
                with open(path, "w") as fw:
                    json.dump(data, fw, indent=2)
                return WorkflowTemplate(**data)
        return None

    def import_workflow(self, workflow_json: Dict[str, Any]) -> Dict[str, Any]:
        """Import a workflow into the user's workspace"""
        # Validate workflow structure
        if "nodes" not in workflow_json or "edges" not in workflow_json:
            raise ValueError("Invalid workflow structure: missing nodes or edges")
        
        # In a real app, we would save this to the user's DB
        # For now, we just return the validated data to be used by the frontend
        return {
            "id": str(uuid.uuid4()),
            "name": f"Imported: {workflow_json.get('name', 'Untitled Workflow')}",
            "nodes": workflow_json["nodes"],
            "edges": workflow_json["edges"],
            "imported_at": datetime.now().isoformat()
        }
    
    def export_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Export a workflow to JSON format"""
        # Validate workflow structure
        if "nodes" not in workflow_data or "edges" not in workflow_data:
            raise ValueError("Invalid workflow structure: missing nodes or edges")
        
        # Create exportable format
        export_data = {
            "name": workflow_data.get("name", "Untitled Workflow"),
            "description": workflow_data.get("description", ""),
            "nodes": workflow_data["nodes"],
            "edges": workflow_data["edges"],
            "metadata": {
                "exported_at": datetime.now().isoformat(),
                "version": "1.0.0"
            }
        }
        
        return export_data

    def _initialize_advanced_templates(self):
        """Create advanced workflow templates if they don't exist"""
        advanced_defaults = [
            {
                "id": "advanced_etl_pipeline",
                "name": "Advanced ETL Pipeline",
                "description": "Multi-step data processing pipeline with conditional logic and pause/resume support",
                "category": "Data Processing",
                "author": "ATOM Team",
                "version": "2.0.0",
                "integrations": ["database", "api", "openai"],
                "complexity": "Advanced",
                "tags": ["etl", "pipeline", "data", "multi-step"],
                "input_schema": [
                    {
                        "name": "data_source_type",
                        "type": "select",
                        "label": "Data Source Type",
                        "description": "Select the type of data source",
                        "required": True,
                        "options": ["database", "file", "api", "stream"]
                    },
                    {
                        "name": "transformation_rules",
                        "type": "object",
                        "label": "Transformation Rules",
                        "description": "JSON configuration for data transformations",
                        "required": False,
                        "show_when": {"data_source_type": ["database", "api"]}
                    }
                ],
                "steps": [
                    {
                        "step_id": "validate_inputs",
                        "name": "Validate Input Configuration",
                        "description": "Validate and prepare input parameters",
                        "step_type": "validation",
                        "estimated_duration": 30
                    },
                    {
                        "step_id": "extract_data",
                        "name": "Extract Data",
                        "description": "Extract data from the specified source",
                        "step_type": "data_extraction",
                        "estimated_duration": 120,
                        "depends_on": ["validate_inputs"]
                    },
                    {
                        "step_id": "transform_data",
                        "name": "Transform Data",
                        "description": "Apply transformation rules and clean data",
                        "step_type": "data_transformation",
                        "estimated_duration": 300,
                        "depends_on": ["extract_data"],
                        "can_pause": True
                    },
                    {
                        "step_id": "load_data",
                        "name": "Load Processed Data",
                        "description": "Load transformed data to destination",
                        "step_type": "data_loading",
                        "estimated_duration": 180,
                        "depends_on": ["transform_data"]
                    },
                    {
                        "step_id": "generate_report",
                        "name": "Generate Processing Report",
                        "description": "Create summary report of the ETL process",
                        "step_type": "report_generation",
                        "estimated_duration": 60,
                        "depends_on": ["load_data"]
                    }
                ],
                "output_config": {
                    "type": "multi_output",
                    "outputs": [
                        "processed_data",
                        "transformation_log",
                        "processing_report"
                    ]
                },
                "estimated_duration": 690,
                "prerequisites": ["database_access", "file_permissions"],
                "use_cases": ["Data migration", "Data warehousing", "Real-time processing"],
                "benefits": ["Conditional processing", "Error recovery", "Progress tracking", "Pause/resume support"]
            },
            {
                "id": "advanced_approval_workflow",
                "name": "Multi-Stage Approval Workflow",
                "description": "Advanced approval system with conditional routing and notifications",
                "category": "Business Process",
                "author": "ATOM Team",
                "version": "2.0.0",
                "integrations": ["slack", "email", "crm", "document_management"],
                "complexity": "Intermediate",
                "tags": ["approval", "workflow", "business", "multi-stage"],
                "input_schema": [
                    {
                        "name": "request_type",
                        "type": "select",
                        "label": "Request Type",
                        "description": "Type of approval request",
                        "required": True,
                        "options": ["expense", "purchase", "leave", "project"]
                    },
                    {
                        "name": "amount",
                        "type": "number",
                        "label": "Amount",
                        "description": "Request amount",
                        "required": True,
                        "show_when": {"request_type": ["expense", "purchase"]},
                        "validation_rules": {"min_value": 0}
                    },
                    {
                        "name": "urgency_level",
                        "type": "select",
                        "label": "Urgency Level",
                        "description": "How urgent is this request",
                        "required": True,
                        "options": ["low", "medium", "high", "critical"]
                    }
                ],
                "steps": [
                    {
                        "step_id": "submit_request",
                        "name": "Submit Request",
                        "description": "Initial request submission and validation",
                        "step_type": "request_submission",
                        "estimated_duration": 15
                    },
                    {
                        "step_id": "initial_review",
                        "name": "Initial Review",
                        "description": "Manager initial review and routing",
                        "step_type": "manager_review",
                        "estimated_duration": 60,
                        "depends_on": ["submit_request"]
                    },
                    {
                        "step_id": "conditional_approval",
                        "name": "Conditional Approval",
                        "description": "Route based on amount and request type",
                        "step_type": "conditional_routing",
                        "estimated_duration": 30,
                        "depends_on": ["initial_review"]
                    },
                    {
                        "step_id": "final_approval",
                        "name": "Final Approval",
                        "description": "Final approval stage for high-value requests",
                        "step_type": "final_approval",
                        "estimated_duration": 120,
                        "depends_on": ["conditional_approval"]
                    },
                    {
                        "step_id": "notify_stakeholders",
                        "name": "Notify Stakeholders",
                        "description": "Send notifications to all relevant parties",
                        "step_type": "notification",
                        "estimated_duration": 30,
                        "depends_on": ["final_approval"]
                    }
                ],
                "estimated_duration": 255,
                "use_cases": ["Expense approval", "Purchase requests", "Leave requests", "Project approvals"],
                "benefits": ["Conditional routing", "Multi-stage approval", "Automatic notifications", "Audit trail"]
            }
        ]

        for tmpl in advanced_defaults:
            path = os.path.join(self.advanced_templates_dir, f"{tmpl['id']}.json")
            if not os.path.exists(path):
                tmpl["created_at"] = datetime.now().isoformat()
                tmpl["updated_at"] = datetime.now().isoformat()
                tmpl["downloads"] = 0
                tmpl["rating"] = 5.0
                tmpl["template_type"] = TemplateType.ADVANCED
                tmpl["multi_input_support"] = True
                tmpl["multi_step_support"] = True
                tmpl["multi_output_support"] = True
                tmpl["pause_resume_support"] = True
                with open(path, "w") as f:
                    json.dump(tmpl, f, indent=2)

    def _initialize_industry_templates(self):
        """Create industry-specific templates"""
        industry_templates = [
            {
                "id": "healthcare_patient_onboarding",
                "name": "Healthcare Patient Onboarding",
                "description": "Complete patient onboarding workflow with HIPAA compliance",
                "category": "Healthcare",
                "author": "ATOM Team",
                "version": "1.0.0",
                "integrations": ["ehr", "email", "sms", "document_management"],
                "complexity": "Advanced",
                "industry": "healthcare",
                "compliance_requirements": ["HIPAA", "HITECH"],
                "input_schema": [
                    {
                        "name": "patient_id",
                        "type": "string",
                        "label": "Patient ID",
                        "description": "Patient identifier from EHR system",
                        "required": True
                    },
                    {
                        "name": "insurance_type",
                        "type": "select",
                        "label": "Insurance Type",
                        "description": "Patient's insurance coverage type",
                        "required": True,
                        "options": ["private", "medicare", "medicaid", "self_pay"]
                    }
                ],
                "steps": [
                    {
                        "step_id": "verify_patient_info",
                        "name": "Verify Patient Information",
                        "description": "Validate patient data from EHR",
                        "step_type": "data_validation",
                        "estimated_duration": 120
                    },
                    {
                        "step_id": "check_insurance",
                        "name": "Verify Insurance Coverage",
                        "description": "Check insurance eligibility and coverage",
                        "step_type": "insurance_verification",
                        "estimated_duration": 300,
                        "depends_on": ["verify_patient_info"]
                    },
                    {
                        "step_id": "collect_documents",
                        "name": "Collect Required Documents",
                        "description": "Gather necessary medical and consent forms",
                        "step_type": "document_collection",
                        "estimated_duration": 600,
                        "depends_on": ["check_insurance"],
                        "can_pause": True
                    },
                    {
                        "step_id": "schedule_appointments",
                        "name": "Schedule Initial Appointments",
                        "description": "Schedule initial consultations and assessments",
                        "step_type": "appointment_scheduling",
                        "estimated_duration": 180,
                        "depends_on": ["collect_documents"]
                    },
                    {
                        "step_id": "send_welcome_kit",
                        "name": "Send Welcome Information",
                        "description": "Send patient welcome kit and instructions",
                        "step_type": "patient_communication",
                        "estimated_duration": 60,
                        "depends_on": ["schedule_appointments"]
                    }
                ],
                "estimated_duration": 1260,
                "use_cases": ["New patient registration", "Insurance verification", "Appointment scheduling"],
                "benefits": ["HIPAA compliance", "Automated verification", "Document management", "Patient communication"]
            }
        ]

        for tmpl in industry_templates:
            path = os.path.join(self.industry_templates_dir, f"{tmpl['id']}.json")
            if not os.path.exists(path):
                tmpl["created_at"] = datetime.now().isoformat()
                tmpl["updated_at"] = datetime.now().isoformat()
                tmpl["downloads"] = 0
                tmpl["rating"] = 5.0
                tmpl["template_type"] = TemplateType.INDUSTRY
                tmpl["multi_input_support"] = True
                tmpl["multi_step_support"] = True
                tmpl["multi_output_support"] = True
                tmpl["pause_resume_support"] = True
                with open(path, "w") as f:
                    json.dump(tmpl, f, indent=2)

    def list_templates(self,
                      category: Optional[str] = None,
                      template_type: Optional[TemplateType] = None,
                      industry: Optional[str] = None,
                      tags: Optional[List[str]] = None) -> List[WorkflowTemplate]:
        """List available workflow templates with enhanced filtering"""
        templates = []

        # Load all template types
        templates.extend(self._load_legacy_templates(category))
        templates.extend(self._load_advanced_templates(category))
        templates.extend(self._load_industry_templates(category, industry))

        # Apply filters
        if template_type:
            templates = [t for t in templates if t.template_type == template_type]

        if tags:
            templates = [t for t in templates if any(tag in t.tags for tag in tags)]

        return templates

    def _load_legacy_templates(self, category: Optional[str] = None) -> List[WorkflowTemplate]:
        """Load legacy node-based templates"""
        templates = []
        for filename in os.listdir(self.templates_dir):
            if filename.endswith(".json") and not filename.startswith(("advanced_", "industry_")):
                try:
                    with open(os.path.join(self.templates_dir, filename), "r") as f:
                        data = json.load(f)
                        if category and data.get("category") != category:
                            continue
                        data["template_type"] = TemplateType.LEGACY
                        templates.append(WorkflowTemplate(**data))
                except Exception as e:
                    logger.error(f"Error loading legacy template {filename}: {e}")
        return templates

    def _load_advanced_templates(self, category: Optional[str] = None) -> List[WorkflowTemplate]:
        """Load advanced workflow templates"""
        templates = []
        for filename in os.listdir(self.advanced_templates_dir):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(self.advanced_templates_dir, filename), "r") as f:
                        data = json.load(f)
                        if category and data.get("category") != category:
                            continue

                        # Handle advanced template format
                        if "input_schema" in data and "steps" in data:
                            # Convert to standard WorkflowTemplate format
                            workflow_data = {
                                "id": data.get("id"),
                                "name": data.get("name"),
                                "description": data.get("description"),
                                "category": data.get("category"),
                                "author": data.get("author"),
                                "version": data.get("version"),
                                "integrations": data.get("integrations", []),
                                "complexity": data.get("complexity"),
                                "workflow_data": {
                                    "nodes": [{"id": step["step_id"], "type": "step", "config": step} for step in data.get("steps", [])],
                                    "edges": [{"source": step["depends_on"][0], "target": step["step_id"]}
                                            for step in data.get("steps", []) if step.get("depends_on")]
                                },
                                "created_at": data.get("created_at"),
                                "downloads": data.get("downloads", 0),
                                "rating": data.get("rating", 0.0),
                                "template_type": TemplateType.ADVANCED,
                                "tags": data.get("tags", []),
                                "estimated_duration": data.get("estimated_duration"),
                                "multi_input_support": data.get("multi_input_support", True),
                                "multi_step_support": data.get("multi_step_support", True),
                                "multi_output_support": data.get("multi_output_support", True),
                                "pause_resume_support": data.get("pause_resume_support", True),
                                "prerequisites": data.get("prerequisites", [])
                            }
                            templates.append(WorkflowTemplate(**workflow_data))
                        else:
                            # Fallback to direct loading
                            data["template_type"] = TemplateType.ADVANCED
                            templates.append(WorkflowTemplate(**data))

                except Exception as e:
                    logger.error(f"Error loading advanced template {filename}: {e}")
        return templates

    def _load_industry_templates(self, category: Optional[str] = None, industry: Optional[str] = None) -> List[WorkflowTemplate]:
        """Load industry-specific templates"""
        templates = []
        for filename in os.listdir(self.industry_templates_dir):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(self.industry_templates_dir, filename), "r") as f:
                        data = json.load(f)
                        if category and data.get("category") != category:
                            continue
                        if industry and data.get("industry") != industry:
                            continue

                        # Handle industry template format
                        if "input_schema" in data and "steps" in data:
                            # Convert to standard WorkflowTemplate format
                            workflow_data = {
                                "id": data.get("id"),
                                "name": data.get("name"),
                                "description": data.get("description"),
                                "category": data.get("category"),
                                "author": data.get("author"),
                                "version": data.get("version"),
                                "integrations": data.get("integrations", []),
                                "complexity": data.get("complexity"),
                                "workflow_data": {
                                    "nodes": [{"id": step["step_id"], "type": "step", "config": step} for step in data.get("steps", [])],
                                    "edges": [{"source": step["depends_on"][0], "target": step["step_id"]}
                                            for step in data.get("steps", []) if step.get("depends_on")]
                                },
                                "created_at": data.get("created_at"),
                                "downloads": data.get("downloads", 0),
                                "rating": data.get("rating", 0.0),
                                "template_type": TemplateType.INDUSTRY,
                                "tags": data.get("tags", []),
                                "estimated_duration": data.get("estimated_duration"),
                                "multi_input_support": data.get("multi_input_support", True),
                                "multi_step_support": data.get("multi_step_support", True),
                                "multi_output_support": data.get("multi_output_support", True),
                                "pause_resume_support": data.get("pause_resume_support", True),
                                "prerequisites": data.get("prerequisites", []),
                                "industry": data.get("industry")
                            }
                            templates.append(WorkflowTemplate(**workflow_data))
                        else:
                            # Fallback to direct loading
                            data["template_type"] = TemplateType.INDUSTRY
                            templates.append(WorkflowTemplate(**data))

                except Exception as e:
                    logger.error(f"Error loading industry template {filename}: {e}")
        return templates

    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """Get a specific template by ID"""
        # Try legacy templates first
        path = os.path.join(self.templates_dir, f"{template_id}.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
                data["downloads"] += 1
                with open(path, "w") as fw:
                    json.dump(data, fw, indent=2)
                data["template_type"] = TemplateType.LEGACY
                return WorkflowTemplate(**data)

        # Try advanced templates
        path = os.path.join(self.advanced_templates_dir, f"{template_id}.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
                data["downloads"] += 1
                with open(path, "w") as fw:
                    json.dump(data, fw, indent=2)
                data["template_type"] = TemplateType.ADVANCED
                return WorkflowTemplate(**data)

        # Try industry templates
        path = os.path.join(self.industry_templates_dir, f"{template_id}.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
                data["downloads"] += 1
                with open(path, "w") as fw:
                    json.dump(data, fw, indent=2)
                data["template_type"] = TemplateType.INDUSTRY
                return WorkflowTemplate(**data)

        return None

    def create_advanced_template(self, template_data: Dict[str, Any]) -> AdvancedWorkflowTemplate:
        """Create a new advanced workflow template"""
        template_id = template_data.get("id", f"advanced_{uuid.uuid4().hex[:12]}")
        template_data["id"] = template_id
        template_data["created_at"] = datetime.now().isoformat()
        template_data["updated_at"] = datetime.now().isoformat()

        # Calculate estimated duration
        if "steps" in template_data:
            total_duration = sum(step.get("estimated_duration", 60) for step in template_data["steps"])
            template_data["estimated_duration"] = total_duration

        # Set default values for advanced features
        template_data.setdefault("multi_input_support", True)
        template_data.setdefault("multi_step_support", True)
        template_data.setdefault("multi_output_support", True)
        template_data.setdefault("pause_resume_support", True)
        template_data.setdefault("downloads", 0)
        template_data.setdefault("rating", 5.0)

        # Save to advanced templates directory
        path = os.path.join(self.advanced_templates_dir, f"{template_id}.json")
        with open(path, "w") as f:
            json.dump(template_data, f, indent=2)

        return AdvancedWorkflowTemplate(**template_data)

    def create_workflow_from_advanced_template(self,
                                             template_id: str,
                                             workflow_name: str,
                                             parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Create a workflow from an advanced template"""
        template_path = os.path.join(self.advanced_templates_dir, f"{template_id}.json")
        if not os.path.exists(template_path):
            raise ValueError(f"Advanced template {template_id} not found")

        with open(template_path, "r") as f:
            template_data = json.load(f)

        # Create advanced workflow definition
        workflow_def = {
            "workflow_id": f"workflow_{uuid.uuid4().hex[:12]}",
            "name": workflow_name,
            "description": f"Created from advanced template: {template_data.get('name', 'Unknown')}",
            "category": template_data.get("category", "general"),
            "tags": template_data.get("tags", []),
            "version": "1.0",
            "created_from_template": template_id,
            "created_from_advanced_template": True,

            # Advanced workflow configuration
            "input_schema": template_data.get("input_schema", []),
            "steps": template_data.get("steps", []),
            "output_config": template_data.get("output_config"),
            "estimated_duration": template_data.get("estimated_duration", 0),
            "pause_resume_support": template_data.get("pause_resume_support", True),
            "multi_input_support": template_data.get("multi_input_support", True),
            "multi_step_support": template_data.get("multi_step_support", True),
            "multi_output_support": template_data.get("multi_output_support", True),

            # User inputs
            "user_inputs": parameters,
            "prerequisites": template_data.get("prerequisites", []),
            "integrations": template_data.get("integrations", [])
        }

        # Increment template download count
        template_data["downloads"] += 1
        with open(template_path, "w") as f:
            json.dump(template_data, f, indent=2)

        return workflow_def

# API Router
router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])
marketplace = MarketplaceEngine()

@router.get("/templates", response_model=List[WorkflowTemplate])
async def get_templates(
    category: Optional[str] = None,
    template_type: Optional[TemplateType] = None,
    industry: Optional[str] = None,
    tags: Optional[List[str]] = Query(None)
):
    """Get templates with enhanced filtering"""
    return marketplace.list_templates(
        category=category,
        template_type=template_type,
        industry=industry,
        tags=tags
    )

@router.get("/templates/types")
async def get_template_types():
    """Get available template types"""
    return {
        "template_types": [
            {
                "value": t.value,
                "label": t.value.title(),
                "description": f"{t.value.title()} workflow templates"
            }
            for t in TemplateType
        ]
    }

@router.get("/templates/featured")
async def get_featured_templates(limit: int = Query(10, ge=1, le=50)):
    """Get featured templates"""
    all_templates = marketplace.list_templates()
    featured = [t for t in all_templates if hasattr(t, 'is_featured') and t.is_featured]

    # Sort by rating and downloads
    featured.sort(key=lambda t: (t.rating, t.downloads), reverse=True)
    return featured[:limit]

@router.get("/templates/{template_id}", response_model=WorkflowTemplate)
async def get_template_details(template_id: str):
    template = marketplace.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

@router.post("/templates/{template_id}/import")
async def import_template_by_id(template_id: str):
    """Import a specific template from the marketplace into the user's workspace"""
    try:
        template = marketplace.get_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Call the engine's import logic (simulated for now)
        return marketplace.import_workflow(template.workflow_data)
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Advanced Template Endpoints
@router.post("/templates/advanced", response_model=AdvancedWorkflowTemplate)
async def create_advanced_template(template_data: Dict[str, Any]):
    """Create a new advanced workflow template"""
    try:
        template = marketplace.create_advanced_template(template_data)
        return template
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/templates/{template_id}/create-workflow")
async def create_workflow_from_advanced_template(
    template_id: str,
    workflow_name: str,
    parameters: Dict[str, Any] = {}
):
    """Create a workflow from an advanced template"""
    try:
        workflow_def = marketplace.create_workflow_from_advanced_template(
            template_id=template_id,
            workflow_name=workflow_name,
            parameters=parameters
        )
        return {
            "status": "success",
            "workflow_definition": workflow_def,
            "message": f"Workflow '{workflow_name}' created successfully from template {template_id}"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Legacy Import/Export Endpoints
@router.post("/import")
async def import_workflow(file: UploadFile = File(...)):
    try:
        content = await file.read()
        workflow_data = json.loads(content)
        return marketplace.import_workflow(workflow_data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/export")
async def export_workflow(workflow_data: Dict[str, Any]):
    """Export a workflow as downloadable JSON"""
    try:
        export_data = marketplace.export_workflow(workflow_data)
        return export_data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Template Statistics
@router.get("/templates/statistics")
async def get_template_statistics():
    """Get marketplace statistics"""
    all_templates = marketplace.list_templates()

    stats = {
        "total_templates": len(all_templates),
        "total_downloads": sum(t.downloads for t in all_templates),
        "average_rating": sum(t.rating for t in all_templates) / max(len(all_templates), 1),
        "categories": {},
        "template_types": {},
        "complexity_levels": {}
    }

    for template in all_templates:
        # Category stats
        cat = template.category
        if cat not in stats["categories"]:
            stats["categories"][cat] = {"count": 0, "downloads": 0}
        stats["categories"][cat]["count"] += 1
        stats["categories"][cat]["downloads"] += template.downloads

        # Template type stats
        ttype = getattr(template, 'template_type', TemplateType.LEGACY)
        if ttype not in stats["template_types"]:
            stats["template_types"][ttype] = {"count": 0, "downloads": 0}
        stats["template_types"][ttype]["count"] += 1
        stats["template_types"][ttype]["downloads"] += template.downloads

        # Complexity stats
        comp = template.complexity
        if comp not in stats["complexity_levels"]:
            stats["complexity_levels"][comp] = {"count": 0, "downloads": 0}
        stats["complexity_levels"][comp]["count"] += 1
        stats["complexity_levels"][comp]["downloads"] += template.downloads

    return stats
