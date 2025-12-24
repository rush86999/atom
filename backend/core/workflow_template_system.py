"""
Workflow Template System
Advanced template management for reusable workflow components and patterns
"""

import json
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
from enum import Enum
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

class TemplateCategory(str, Enum):
    AUTOMATION = "automation"
    DATA_PROCESSING = "data_processing"
    AI_ML = "ai_ml"
    BUSINESS = "business"
    INTEGRATION = "integration"
    MONITORING = "monitoring"
    REPORTING = "reporting"
    SECURITY = "security"
    GENERAL = "general"

class TemplateComplexity(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

class TemplateParameter(BaseModel):
    """Template parameter definition"""
    name: str
    label: str
    description: str
    type: str = "string"
    required: bool = True
    default_value: Any = None
    options: List[str] = []
    validation_rules: Dict[str, Any] = {}
    help_text: Optional[str] = None
    example_value: Optional[Any] = None

class TemplateStep(BaseModel):
    """Template step definition"""
    step_id: str
    name: str
    description: str
    step_type: str
    parameters: List[TemplateParameter] = []
    condition: Optional[str] = None
    depends_on: List[str] = []
    estimated_duration: int = 60  # seconds
    is_optional: bool = False
    retry_config: Dict[str, Any] = {}

    @validator('depends_on')
    def validate_dependencies(cls, v):
        """Ensure dependency chains don't create cycles"""
        # Basic validation - more complex cycle detection would be done at template level
        return v

class WorkflowTemplate(BaseModel):
    """Comprehensive workflow template definition"""
    template_id: str = Field(default_factory=lambda: f"template_{uuid.uuid4().hex[:12]}")
    name: str
    description: str
    category: TemplateCategory
    complexity: TemplateComplexity
    tags: List[str] = []

    # Template configuration
    version: str = "1.0.0"
    author: str = "System"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Template content
    inputs: List[TemplateParameter] = []
    steps: List[TemplateStep] = []
    output_schema: Dict[str, Any] = {}

    # Usage tracking
    usage_count: int = 0
    rating: float = 0.0
    review_count: int = 0

    # Metadata
    estimated_total_duration: int = 0  # seconds
    prerequisites: List[str] = []
    dependencies: List[str] = []  # External services/APIs required
    permissions: List[str] = []  # Required permissions

    # Template customization
    is_public: bool = False
    is_featured: bool = False
    license: str = "MIT"

    @validator('steps')
    def validate_step_connections(cls, v):
        """Validate that step dependencies are valid"""
        step_ids = {step.step_id for step in v}

        for step in v:
            for dependency in step.depends_on:
                if dependency not in step_ids:
                    raise ValueError(f"Step {step.step_id} depends on non-existent step {dependency}")

        return v

    def calculate_estimated_duration(self):
        """Calculate total estimated duration"""
        self.estimated_total_duration = sum(step.estimated_duration for step in self.steps)
        return self.estimated_total_duration

    def add_usage(self):
        """Increment usage count"""
        self.usage_count += 1
        self.updated_at = datetime.now()

    def update_rating(self, new_rating: float):
        """Update template rating"""
        if self.review_count == 0:
            self.rating = new_rating
        else:
            self.rating = ((self.rating * self.review_count) + new_rating) / (self.review_count + 1)
        self.review_count += 1
        self.updated_at = datetime.now()

class TemplateMarketplace(BaseModel):
    """Template marketplace for sharing and discovering templates"""
    templates: Dict[str, WorkflowTemplate] = {}
    categories: Dict[str, List[str]] = {cat.value: [] for cat in TemplateCategory}
    tags_index: Dict[str, List[str]] = {}
    search_index: Dict[str, List[str]] = {}

    class Config:
        arbitrary_types_allowed = True

class WorkflowTemplateManager:
    """Manages workflow templates, marketplace, and template operations"""

    def __init__(self, template_dir: str = "workflow_templates"):
        self.template_dir = Path(template_dir)
        self.template_dir.mkdir(exist_ok=True)

        self.templates: Dict[str, WorkflowTemplate] = {}
        self.marketplace = TemplateMarketplace()
        self.template_files: Dict[str, Path] = {}

        # Load existing templates
        self.load_templates()
        self.load_built_in_templates()

        logger.info(f"Template manager initialized with {len(self.templates)} templates")

    def create_template(self, template_data: Dict[str, Any]) -> WorkflowTemplate:
        """Create a new workflow template"""
        try:
            # Validate template data
            template = WorkflowTemplate(**template_data)

            # Calculate estimated duration
            template.calculate_estimated_duration()

            # Store template
            self.templates[template.template_id] = template
            self.marketplace.templates[template.template_id] = template

            # Update category and tag indexes
            self._update_indexes(template)

            # Save to file
            self._save_template(template)

            logger.info(f"Created template: {template.name} ({template.template_id})")
            return template

        except Exception as e:
            logger.error(f"Failed to create template: {e}")
            raise

    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """Get template by ID"""
        return self.templates.get(template_id)

    def list_templates(self,
                      category: Optional[TemplateCategory] = None,
                      complexity: Optional[TemplateComplexity] = None,
                      tags: Optional[List[str]] = None,
                      author: Optional[str] = None,
                      is_public: Optional[bool] = None,
                      limit: int = 50) -> List[WorkflowTemplate]:
        """List templates with filtering options"""
        templates = list(self.templates.values())

        # Apply filters
        if category:
            templates = [t for t in templates if t.category == category]

        if complexity:
            templates = [t for t in templates if t.complexity == complexity]

        if tags:
            templates = [t for t in templates if any(tag in t.tags for tag in tags)]

        if author:
            templates = [t for t in templates if t.author == author]

        if is_public is not None:
            templates = [t for t in templates if t.is_public == is_public]

        # Sort by usage count and rating
        templates.sort(key=lambda t: (t.usage_count, t.rating), reverse=True)

        return templates[:limit]

    def search_templates(self, query: str, limit: int = 20) -> List[WorkflowTemplate]:
        """Search templates by text query"""
        query = query.lower()
        matches = []

        for template in self.templates.values():
            # Search in name, description, tags
            searchable_text = f"{template.name} {template.description} {' '.join(template.tags)}"
            if query in searchable_text.lower():
                matches.append(template)

        # Sort by relevance (exact matches first, then by usage)
        exact_matches = [t for t in matches if query in t.name.lower() or query in t.description.lower()]
        partial_matches = [t for t in matches if t not in exact_matches]

        return (exact_matches + partial_matches)[:limit]

    def create_workflow_from_template(self,
                                    template_id: str,
                                    workflow_name: str,
                                    template_parameters: Dict[str, Any],
                                    customizations: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new workflow from a template with parameters"""
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        try:
            # Validate template parameters
            validated_params = self._validate_template_parameters(template, template_parameters)

            # Generate workflow definition
            workflow_def = self._generate_workflow_definition(
                template, workflow_name, validated_params, customizations or {}
            )

            # Track template usage
            template.add_usage()
            self._save_template(template)

            logger.info(f"Created workflow from template: {workflow_name} from {template.name}")

            return {
                "workflow_id": f"workflow_{uuid.uuid4().hex[:12]}",
                "workflow_definition": workflow_def,
                "template_used": template.template_id,
                "template_name": template.name,
                "parameters_applied": validated_params
            }

        except Exception as e:
            logger.error(f"Failed to create workflow from template {template_id}: {e}")
            raise

    def update_template(self, template_id: str, updates: Dict[str, Any]) -> WorkflowTemplate:
        """Update an existing template"""
        if template_id not in self.templates:
            raise ValueError(f"Template {template_id} not found")

        template = self.templates[template_id]

        # Update fields
        for field, value in updates.items():
            if hasattr(template, field) and field not in ['template_id', 'created_at']:
                setattr(template, field, value)

        # Recalculate dependencies
        template.calculate_estimated_duration()
        template.updated_at = datetime.now()

        # Save updates
        self._save_template(template)

        logger.info(f"Updated template: {template.name}")
        return template

    def delete_template(self, template_id: str) -> bool:
        """Delete a template"""
        if template_id not in self.templates:
            return False

        template = self.templates[template_id]

        # Remove from memory
        del self.templates[template_id]
        if template_id in self.marketplace.templates:
            del self.marketplace.templates[template_id]

        # Remove from indexes
        self._update_indexes(template, remove=True)

        # Delete file
        template_file = self.template_files.get(template_id)
        if template_file and template_file.exists():
            template_file.unlink()
            del self.template_files[template_id]

        logger.info(f"Deleted template: {template.name}")
        return True

    def rate_template(self, template_id: str, rating: float) -> bool:
        """Rate a template"""
        if template_id not in self.templates:
            return False

        if not (1.0 <= rating <= 5.0):
            raise ValueError("Rating must be between 1.0 and 5.0")

        template = self.templates[template_id]
        template.update_rating(rating)
        self._save_template(template)

        logger.info(f"Rated template {template.name}: {rating}")
        return True

    def export_template(self, template_id: str) -> Dict[str, Any]:
        """Export template as shareable JSON"""
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        return template.dict()

    def import_template(self, template_data: Dict[str, Any], overwrite: bool = False) -> WorkflowTemplate:
        """Import template from JSON"""
        template_id = template_data.get('template_id')

        if template_id in self.templates and not overwrite:
            raise ValueError(f"Template {template_id} already exists. Use overwrite=True to replace.")

        # Create new template ID if overwriting or conflicting
        if template_id in self.templates and overwrite:
            template_data = template_data.copy()
            template_data['template_id'] = f"template_{uuid.uuid4().hex[:12]}"

        return self.create_template(template_data)

    def get_template_statistics(self) -> Dict[str, Any]:
        """Get template usage statistics"""
        total_templates = len(self.templates)
        total_usage = sum(t.usage_count for t in self.templates.values())
        avg_rating = sum(t.rating * t.review_count for t in self.templates.values()) / max(sum(t.review_count for t in self.templates.values()), 1)

        category_stats = {}
        for category in TemplateCategory:
            category_templates = [t for t in self.templates.values() if t.category == category]
            category_stats[category.value] = {
                "count": len(category_templates),
                "usage": sum(t.usage_count for t in category_templates),
                "avg_rating": sum(t.rating * t.review_count for t in category_templates) / max(sum(t.review_count for t in category_templates), 1)
            }

        return {
            "total_templates": total_templates,
            "total_usage": total_usage,
            "average_rating": round(avg_rating, 2),
            "category_breakdown": category_stats,
            "most_used_templates": sorted(self.templates.values(), key=lambda t: t.usage_count, reverse=True)[:5],
            "highest_rated_templates": sorted([t for t in self.templates.values() if t.review_count > 0], key=lambda t: t.rating, reverse=True)[:5]
        }

    def _validate_template_parameters(self, template: WorkflowTemplate, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate parameters against template requirements"""
        validated = {}

        for param in template.inputs:
            param_name = param.name
            param_value = parameters.get(param_name)

            # Check required parameters
            if param.required and param_value is None:
                if param.default_value is not None:
                    param_value = param.default_value
                else:
                    raise ValueError(f"Required parameter '{param_name}' is missing")

            # Use default value if not provided
            if param_value is None and param.default_value is not None:
                param_value = param.default_value

            # Type validation and transformation
            if param_value is not None:
                try:
                    if param.type == "number":
                        param_value = float(param_value)
                    elif param.type == "boolean":
                        if isinstance(param_value, str):
                            param_value = param_value.lower() in ["true", "1", "yes", "on"]
                        else:
                            param_value = bool(param_value)
                    elif param.type == "array":
                        if isinstance(param_value, str):
                            param_value = json.loads(param_value)
                    elif param.type == "object":
                        if isinstance(param_value, str):
                            param_value = json.loads(param_value)
                except (ValueError, TypeError, json.JSONDecodeError) as e:
                    raise ValueError(f"Invalid value for parameter '{param_name}': {e}")

            validated[param_name] = param_value

        return validated

    def _generate_workflow_definition(self,
                                    template: WorkflowTemplate,
                                    workflow_name: str,
                                    parameters: Dict[str, Any],
                                    customizations: Dict[str, Any]) -> Dict[str, Any]:
        """Generate workflow definition from template"""
        workflow_def = {
            "workflow_id": f"workflow_{uuid.uuid4().hex[:12]}",
            "name": workflow_name,
            "description": f"Created from template: {template.name}",
            "category": template.category.value,
            "tags": template.tags.copy(),
            "version": "1.0",
            "created_from_template": template.template_id,

            # Convert template inputs to workflow inputs
            "input_schema": [
                {
                    "name": param.name,
                    "type": param.type,
                    "label": param.label,
                    "description": param.description,
                    "required": param.required,
                    "default_value": param.default_value,
                    "options": param.options,
                    "validation_rules": param.validation_rules
                }
                for param in template.inputs
            ],

            # Convert template steps to workflow steps
            "steps": [
                {
                    "step_id": step.step_id,
                    "name": step.name,
                    "description": step.description,
                    "step_type": step.step_type,
                    "input_parameters": [
                        {
                            "name": param.name,
                            "type": param.type,
                            "label": param.label,
                            "description": param.description,
                            "required": param.required,
                            "default_value": param.default_value,
                            "options": param.options,
                            "validation_rules": param.validation_rules
                        }
                        for param in step.parameters
                    ],
                    "depends_on": step.depends_on,
                    "condition": step.condition,
                    "retry_config": step.retry_config,
                    "timeout_seconds": step.estimated_duration,
                    "can_pause": True,
                    "is_parallel": False
                }
                for step in template.steps
            ],

            "output_config": template.output_schema,
            "user_inputs": parameters,
            "customizations": customizations
        }

        return workflow_def

    def _update_indexes(self, template: WorkflowTemplate, remove: bool = False):
        """Update category and tag indexes"""
        if remove:
            # Remove from indexes
            if template.template_id in self.marketplace.categories[template.category.value]:
                self.marketplace.categories[template.category.value].remove(template.template_id)

            for tag in template.tags:
                if tag in self.marketplace.tags_index:
                    if template.template_id in self.marketplace.tags_index[tag]:
                        self.marketplace.tags_index[tag].remove(template.template_id)
        else:
            # Add to indexes
            self.marketplace.categories[template.category.value].append(template.template_id)

            for tag in template.tags:
                if tag not in self.marketplace.tags_index:
                    self.marketplace.tags_index[tag] = []
                self.marketplace.tags_index[tag].append(template.template_id)

    def _save_template(self, template: WorkflowTemplate):
        """Save template to file"""
        filename = self.template_dir / f"{template.template_id}.json"

        with open(filename, 'w') as f:
            json.dump(template.dict(), f, indent=2, default=str)

        self.template_files[template.template_id] = filename

    def load_templates(self):
        """Load templates from files"""
        if not self.template_dir.exists():
            return

        for template_file in self.template_dir.glob("*.json"):
            try:
                with open(template_file, 'r') as f:
                    template_data = json.load(f)

                template = WorkflowTemplate(**template_data)
                self.templates[template.template_id] = template
                self.marketplace.templates[template.template_id] = template
                self.template_files[template.template_id] = template_file
                self._update_indexes(template)

            except Exception as e:
                logger.error(f"Failed to load template {template_file}: {e}")

    def load_built_in_templates(self):
        """Load built-in templates"""
        # This would be expanded with comprehensive built-in templates
        built_in_templates = [
            self._create_data_processing_template(),
            self._create_automation_template(),
            self._create_monitoring_template(),
            self._create_integration_template(),
            self._create_content_management_template(),
            self._create_burnout_protection_template(),
            self._create_deadline_mitigation_template(),
            self._create_email_followup_template(),
            self._create_goal_driven_automation_template(),
            self._create_agent_pipeline_template(),  # Phase 28
            # Phase 38: Financial Ops & Background Agent Templates
            self._create_cost_optimization_template(),
            self._create_budget_approval_template(),
            self._create_invoice_reconciliation_template(),
            self._create_periodic_portal_check_template()
        ]

        for template_data in built_in_templates:
            try:
                template = WorkflowTemplate(**template_data)
                if template.template_id not in self.templates:
                    self.templates[template.template_id] = template
                    self.marketplace.templates[template.template_id] = template
                    self._update_indexes(template)
            except Exception as e:
                logger.error(f"Failed to load built-in template: {e}")

    def _create_data_processing_template(self) -> Dict[str, Any]:
        """Create built-in data processing template"""
        return {
            "template_id": "data_processing_etl",
            "name": "ETL Data Processing Pipeline",
            "description": "Extract, Transform, Load pipeline for processing large datasets",
            "category": "data_processing",
            "complexity": "intermediate",
            "tags": ["etl", "data", "processing", "pipeline"],
            "author": "System",
            "version": "1.0.0",
            "inputs": [
                {
                    "name": "data_source",
                    "label": "Data Source",
                    "description": "Source of data to process",
                    "type": "select",
                    "required": True,
                    "options": ["database", "file", "api", "stream"],
                    "help_text": "Select where your input data comes from"
                },
                {
                    "name": "connection_string",
                    "label": "Connection String",
                    "description": "Database connection or file path",
                    "type": "string",
                    "required": True,
                    "show_when": {"data_source": ["database", "api"]},
                    "example_value": "postgresql://user:pass@localhost/db"
                },
                {
                    "name": "transformation_rules",
                    "label": "Transformation Rules",
                    "description": "JSON configuration for data transformations",
                    "type": "object",
                    "required": False,
                    "default_value": {"operations": []}
                },
                {
                    "name": "output_format",
                    "label": "Output Format",
                    "description": "Format for processed data",
                    "type": "select",
                    "required": True,
                    "options": ["json", "csv", "parquet", "database"]
                }
            ],
            "steps": [
                {
                    "step_id": "extract_data",
                    "name": "Extract Data",
                    "description": "Extract data from source",
                    "step_type": "data_extraction",
                    "estimated_duration": 120,
                    "parameters": []
                },
                {
                    "step_id": "transform_data",
                    "name": "Transform Data",
                    "description": "Apply transformation rules",
                    "step_type": "data_transformation",
                    "estimated_duration": 300,
                    "depends_on": ["extract_data"]
                },
                {
                    "step_id": "load_data",
                    "name": "Load Data",
                    "description": "Load processed data to destination",
                    "step_type": "data_loading",
                    "estimated_duration": 180,
                    "depends_on": ["transform_data"]
                }
            ],
            "dependencies": ["database_driver", "pandas"],
            "estimated_total_duration": 600,
            "is_public": True,
            "is_featured": True
        }

    def _create_automation_template(self) -> Dict[str, Any]:
        """Create built-in automation template"""
        return {
            "template_id": "workflow_automation",
            "name": "Automated Workflow Executor",
            "description": "Execute automated workflows with conditional logic",
            "category": "automation",
            "complexity": "advanced",
            "tags": ["automation", "workflow", "conditional", "triggers"],
            "author": "System",
            "version": "1.0.0",
            "inputs": [
                {
                    "name": "trigger_type",
                    "label": "Trigger Type",
                    "description": "What triggers the workflow",
                    "type": "select",
                    "required": True,
                    "options": ["schedule", "webhook", "event", "manual"]
                },
                {
                    "name": "schedule",
                    "label": "Schedule",
                    "description": "Cron expression for scheduled execution",
                    "type": "string",
                    "required": True,
                    "show_when": {"trigger_type": "schedule"},
                    "example_value": "0 9 * * 1-5"
                },
                {
                    "name": "actions",
                    "label": "Actions",
                    "description": "List of actions to execute",
                    "type": "array",
                    "required": True
                }
            ],
            "steps": [
                {
                    "step_id": "validate_trigger",
                    "name": "Validate Trigger",
                    "description": "Check if trigger conditions are met",
                    "step_type": "validation",
                    "estimated_duration": 10
                },
                {
                    "step_id": "execute_actions",
                    "name": "Execute Actions",
                    "description": "Execute the configured actions",
                    "step_type": "automation_execution",
                    "estimated_duration": 300,
                    "depends_on": ["validate_trigger"]
                }
            ],
            "estimated_total_duration": 310,
            "is_public": True
        }

    def _create_monitoring_template(self) -> Dict[str, Any]:
        """Create built-in monitoring template"""
        return {
            "template_id": "system_monitoring",
            "name": "System Health Monitoring",
            "description": "Monitor system health and send alerts",
            "category": "monitoring",
            "complexity": "beginner",
            "tags": ["monitoring", "health", "alerts", "metrics"],
            "author": "System",
            "version": "1.0.0",
            "inputs": [
                {
                    "name": "target_systems",
                    "label": "Target Systems",
                    "description": "Systems to monitor",
                    "type": "array",
                    "required": True
                },
                {
                    "name": "check_interval",
                    "label": "Check Interval",
                    "description": "How often to check system health (seconds)",
                    "type": "number",
                    "required": True,
                    "default_value": 60,
                    "validation_rules": {"min_value": 10, "max_value": 3600}
                },
                {
                    "name": "alert_threshold",
                    "label": "Alert Threshold",
                    "description": "Failure count before alerting",
                    "type": "number",
                    "required": True,
                    "default_value": 3
                }
            ],
            "steps": [
                {
                    "step_id": "collect_metrics",
                    "name": "Collect Metrics",
                    "description": "Gather system metrics",
                    "step_type": "metrics_collection",
                    "estimated_duration": 30
                },
                {
                    "step_id": "analyze_health",
                    "name": "Analyze Health",
                    "description": "Analyze system health status",
                    "step_type": "health_analysis",
                    "estimated_duration": 15,
                    "depends_on": ["collect_metrics"]
                },
                {
                    "step_id": "send_alerts",
                    "name": "Send Alerts",
                    "description": "Send alerts if needed",
                    "step_type": "alert_notification",
                    "estimated_duration": 10,
                    "depends_on": ["analyze_health"]
                }
            ],
            "estimated_total_duration": 55,
            "is_public": True
        }

    def _create_integration_template(self) -> Dict[str, Any]:
        """Create built-in integration template"""
        return {
            "template_id": "api_integration",
            "name": "API Integration Workflow",
            "description": "Integrate with external APIs and process responses",
            "category": "integration",
            "complexity": "intermediate",
            "tags": ["api", "integration", "webhook", "rest"],
            "author": "System",
            "version": "1.0.0",
            "inputs": [
                {
                    "name": "api_endpoint",
                    "label": "API Endpoint",
                    "description": "Target API endpoint URL",
                    "type": "string",
                    "required": True,
                    "validation_rules": {"type": "url"}
                },
                {
                    "name": "auth_method",
                    "label": "Authentication Method",
                    "description": "How to authenticate with the API",
                    "type": "select",
                    "required": True,
                    "options": ["none", "bearer_token", "api_key", "oauth2"]
                },
                {
                    "name": "api_key",
                    "label": "API Key",
                    "description": "API key or token for authentication",
                    "type": "string",
                    "required": True,
                    "show_when": {"auth_method": ["bearer_token", "api_key"]}
                }
            ],
            "steps": [
                {
                    "step_id": "authenticate",
                    "name": "Authenticate",
                    "description": "Authenticate with the API",
                    "step_type": "api_auth",
                    "estimated_duration": 5
                },
                {
                    "step_id": "make_request",
                    "name": "Make API Request",
                    "description": "Send request to API endpoint",
                    "step_type": "api_request",
                    "estimated_duration": 30,
                    "depends_on": ["authenticate"]
                },
                {
                    "step_id": "process_response",
                    "name": "Process Response",
                    "description": "Process and transform API response",
                    "step_type": "response_processing",
                    "estimated_duration": 15,
                    "depends_on": ["make_request"]
                }
            ],
            "dependencies": ["requests"],
            "estimated_total_duration": 50,
            "is_public": True
        }

    def _create_content_management_template(self) -> Dict[str, Any]:
        """Create built-in content and file management template"""
        return {
            "template_id": "content_file_management",
            "name": "Auto-Archive & Task Linker",
            "description": "Automatically archive, tag, and link new files from cloud storage (Drive/Dropbox) to related tasks",
            "category": "data_processing",
            "complexity": "intermediate",
            "tags": ["cloud_storage", "files", "archiving", "task_management"],
            "author": "System",
            "version": "1.0.0",
            "inputs": [
                {
                    "name": "source_platform",
                    "label": "Source Platform",
                    "description": "Platform to monitor for new files",
                    "type": "select",
                    "required": True,
                    "options": ["google_drive", "dropbox", "box"]
                },
                {
                    "name": "target_task_platform",
                    "label": "Target Task Platform",
                    "description": "Platform to link files to",
                    "type": "select",
                    "required": True,
                    "options": ["asana", "trello", "jira", "github"]
                },
                {
                    "name": "archive_root",
                    "label": "Archive Root Folder",
                    "description": "Root folder for archiving files",
                    "type": "string",
                    "required": True,
                    "default_value": "/Archive"
                },
                {
                    "name": "slack_channel",
                    "label": "Slack Channel",
                    "description": "Channel for notifications",
                    "type": "string",
                    "required": False
                }
            ],
            "steps": [
                {
                    "step_id": "monitor_files",
                    "name": "Monitor New Files",
                    "description": "Detect new file uploads in source platform",
                    "step_type": "event_monitor",
                    "estimated_duration": 10
                },
                {
                    "step_id": "analyze_context",
                    "name": "Analyze Context",
                    "description": "Extract project and task context from file",
                    "step_type": "ai_analysis",
                    "estimated_duration": 45,
                    "depends_on": ["monitor_files"]
                },
                {
                    "step_id": "link_to_task",
                    "name": "Link to Task",
                    "description": "Create link between file and related task",
                    "step_type": "integration_link",
                    "estimated_duration": 20,
                    "depends_on": ["analyze_context"]
                },
                {
                    "step_id": "archive_file",
                    "name": "Archive & Organize",
                    "description": "Move and tag file in cloud storage",
                    "step_type": "storage_operation",
                    "estimated_duration": 15,
                    "depends_on": ["link_to_task"]
                },
                {
                    "step_id": "notify_team",
                    "name": "Notify Team",
                    "description": "Send notification to Slack",
                    "step_type": "notification",
                    "estimated_duration": 5,
                    "depends_on": ["archive_file"],
                    "is_optional": True
                }
            ],
            "estimated_total_duration": 95,
            "is_public": True,
            "is_featured": True
        }

    def _create_burnout_protection_template(self) -> Dict[str, Any]:
        """Create built-in burnout protection template"""
        return {
            "template_id": "burnout_protection",
            "name": "Burnout & Overload Protection",
            "description": "Proactively monitor workload and suggest focus blocks, meeting rescheduling, and delegation.",
            "category": "monitoring",
            "complexity": "intermediate",
            "tags": ["wellness", "productivity", "burnout"],
            "author": "System",
            "version": "1.0.0",
            "inputs": [
                {
                    "name": "risk_score",
                    "label": "Risk Score",
                    "description": "Detected burnout risk score",
                    "type": "number",
                    "required": True
                }
            ],
            "steps": [
                {
                    "step_id": "notify_user",
                    "name": "Send Wellness Alert",
                    "description": "Notify user about high burnout risk",
                    "step_type": "action",
                    "parameters": [
                        {
                            "name": "service",
                            "label": "Service",
                            "description": "Service to use",
                            "type": "string",
                            "default_value": "slack"
                        },
                        {
                            "name": "message",
                            "label": "Message",
                            "description": "Message to send",
                            "type": "string",
                            "default_value": "⚠️ High burnout risk detected. Time to consider some focus blocks!"
                        }
                    ]
                }
            ]
        }

    def _create_deadline_mitigation_template(self) -> Dict[str, Any]:
        """Create built-in deadline mitigation template"""
        return {
            "template_id": "deadline_mitigation",
            "name": "Deadline Risk Mitigation",
            "description": "Automatically handle tasks at risk of missing deadlines",
            "category": "automation",
            "complexity": "beginner",
            "tags": ["productivity", "deadlines", "tasks"],
            "author": "System",
            "version": "1.0.0",
            "inputs": [
                {
                    "name": "at_risk_count",
                    "label": "At-Risk Count",
                    "description": "Number of tasks at risk",
                    "type": "number",
                    "required": True
                }
            ],
            "steps": [
                {
                    "step_id": "escalate",
                    "name": "Escalate Priority",
                    "description": "Notify collaborators about at-risk deadlines",
                    "step_type": "action",
                    "parameters": [
                        {
                            "name": "service",
                            "label": "Service",
                            "description": "Service to use",
                            "type": "string",
                            "default_value": "slack"
                        }
                    ]
                }
            ]
        }

    def _create_email_followup_template(self) -> Dict[str, Any]:
        """Create built-in email follow-up automation template"""
        return {
            "template_id": "email_followup",
            "name": "AI Email Follow-up Automation",
            "description": "Automatically detect sent emails with no replies and draft polite follow-up nudges.",
            "category": "automation",
            "complexity": "intermediate",
            "tags": ["email", "productivity", "follow-up"],
            "author": "System",
            "version": "1.0.0",
            "inputs": [
                {
                    "name": "days_threshold",
                    "label": "Wait Threshold (Days)",
                    "description": "Number of days to wait before suggesting a follow-up",
                    "type": "number",
                    "default_value": 3
                }
            ],
            "steps": [
                {
                    "step_id": "detect_candidates",
                    "name": "Detect Cold Threads",
                    "description": "Identify sent emails needing follow-up",
                    "step_type": "action",
                    "parameters": [
                        {"name": "service", "label": "Service", "description": "Service to use", "type": "string", "default_value": "email_automation"},
                        {"name": "action", "label": "Action", "description": "Action to perform", "type": "string", "default_value": "detect_followups"},
                        {"name": "days_threshold", "label": "Threshold", "description": "Days to wait", "type": "number", "default_value": 3}
                    ]
                },
                {
                    "step_id": "draft_followups",
                    "name": "Draft Follow-ups",
                    "description": "Use AI to draft polite follow-up messages",
                    "step_type": "action",
                    "parameters": [
                        {"name": "service", "label": "Service", "description": "Service to use", "type": "string", "default_value": "email_automation"},
                        {"name": "action", "label": "Action", "description": "Action to perform", "type": "string", "default_value": "draft_nudge"}
                    ],
                    "depends_on": ["detect_candidates"]
                }
            ]
        }

    def _create_goal_driven_automation_template(self) -> Dict[str, Any]:
        """Create built-in goal-driven automation template"""
        return {
            "template_id": "goal_driven_automation",
            "name": "Goal-Driven Automation",
            "description": "High-level goal decomposition and progress monitoring",
            "category": "productivity",
            "complexity": "advanced",
            "tags": ["goal", "planning", "automation", "tracking"],
            "author": "System",
            "version": "1.0.0",
            "inputs": [
                {
                    "name": "goal_text",
                    "label": "Goal Description",
                    "description": "The high-level goal you want to achieve",
                    "type": "string",
                    "required": True,
                    "example_value": "Close the Q4 sales deal with Acme Corp"
                },
                {
                    "name": "target_date",
                    "label": "Target Date",
                    "description": "Deadline for achieving this goal",
                    "type": "string",
                    "required": True,
                    "example_value": "2023-12-31T23:59:59Z"
                }
            ],
            "outputs": [
                {
                    "name": "goal_id",
                    "label": "Goal ID",
                    "description": "Identifier for the newly created goal",
                    "type": "string"
                },
                {
                    "name": "sub_tasks",
                    "label": "Generated Sub-tasks",
                    "description": "List of tasks generated to achieve the goal",
                    "type": "array"
                }
            ],
            "steps": [
                {
                    "id": "init_goal",
                    "name": "Initialize and Decompose Goal",
                    "service": "goal_management",
                    "action": "create_goal",
                    "parameters": {
                        "title": "${input.goal_text}",
                        "target_date": "${input.target_date}"
                    }
                },
                {
                    "id": "notify_user",
                    "name": "Notify Goal Creation",
                    "service": "main_agent",
                    "action": "send_notification",
                    "parameters": {
                        "message": "Goal '${input.goal_text}' has been initialized with ${init_goal.result.sub_tasks.length} sub-tasks.",
                        "type": "success"
                    }
                }
            ],
            "is_public": True,
            "cost_estimate": 0.05
        }

    def _create_agent_pipeline_template(self) -> Dict[str, Any]:
        """Create built-in agent pipeline template (Phase 28)"""
        return {
            "template_id": "agent_pipeline_sales",
            "name": "Sales Prospecting Pipeline",
            "description": "Multi-step agent workflow: Research prospects, update CRM, and check for pricing discrepancies.",
            "category": "automation",
            "complexity": "advanced",
            "tags": ["agents", "sales", "crm", "computer-use", "pipeline"],
            "author": "System",
            "version": "1.0.0",
            "inputs": [
                {
                    "name": "target_company",
                    "label": "Target Company",
                    "description": "Company name to research",
                    "type": "string",
                    "required": True,
                    "example_value": "Acme Corp"
                },
                {
                    "name": "competitor_url",
                    "label": "Competitor URL",
                    "description": "URL of competitor pricing page",
                    "type": "string",
                    "required": False,
                    "example_value": "https://competitor.com/pricing"
                }
            ],
            "steps": [
                {
                    "step_id": "research_prospect",
                    "name": "Research Prospect",
                    "description": "Use Prospect Researcher agent to find decision makers",
                    "step_type": "agent_execution",
                    "estimated_duration": 60,
                    "parameters": [
                        {"name": "agent_id", "type": "string", "default_value": "prospect_researcher", "required": True},
                        {"name": "agent_params", "type": "object", "default_value": {"company_name": "{{target_company}}"}}
                    ]
                },
                {
                    "step_id": "update_crm",
                    "name": "Update CRM",
                    "description": "Use CRM Wolf agent to update Salesforce with findings",
                    "step_type": "agent_execution",
                    "estimated_duration": 45,
                    "depends_on": ["research_prospect"],
                    "parameters": [
                        {"name": "agent_id", "type": "string", "default_value": "crm_wolf", "required": True}
                    ]
                },
                {
                    "step_id": "check_competitor_pricing",
                    "name": "Check Competitor Pricing",
                    "description": "Use Competitive Intel agent to monitor pricing changes",
                    "step_type": "agent_execution",
                    "estimated_duration": 30,
                    "depends_on": ["research_prospect"],
                    "is_optional": True,
                    "condition": "{{competitor_url}}",
                    "parameters": [
                        {"name": "agent_id", "type": "string", "default_value": "competitive_intel", "required": True},
                        {"name": "agent_params", "type": "object", "default_value": {"target_url": "{{competitor_url}}"}}
                    ]
                }
            ],
            "dependencies": ["browser_engine", "lancedb"],
            "estimated_total_duration": 135,
            "is_public": True,
            "is_featured": True
        }

    # ==================== PHASE 38: FINANCIAL OPS TEMPLATES ====================
    
    def _create_cost_optimization_template(self) -> Dict[str, Any]:
        """Create cost optimization workflow template"""
        return {
            "template_id": "cost_optimization_workflow",
            "name": "Cost Optimization Workflow",
            "description": "Detect unused SaaS subscriptions, redundant tools, and generate savings report",
            "category": "financial_ops",
            "complexity": "intermediate",
            "tags": ["cost", "optimization", "saas", "savings"],
            "author": "System",
            "version": "1.0.0",
            "inputs": [
                {"name": "threshold_days", "label": "Unused Threshold (Days)", "type": "number", "required": False, "default_value": 30}
            ],
            "steps": [
                {"step_id": "detect_leaks", "name": "Detect Cost Leaks", "step_type": "cost_leak_detection", "estimated_duration": 10},
                {"step_id": "notify_finance", "name": "Notify Finance Team", "step_type": "slack_notification", "depends_on": ["detect_leaks"],
                 "parameters": [{"name": "channel", "default_value": "#finance"}, {"name": "message", "default_value": "Cost Report: {{cost_report}}"}]}
            ],
            "is_public": True
        }

    def _create_budget_approval_template(self) -> Dict[str, Any]:
        """Create budget check and approval workflow template"""
        return {
            "template_id": "budget_approval_workflow",
            "name": "Budget Check & Approval",
            "description": "Check spending against budget limits tied to deal stages and milestones",
            "category": "financial_ops",
            "complexity": "simple",
            "tags": ["budget", "approval", "spending", "guardrails"],
            "author": "System",
            "version": "1.0.0",
            "inputs": [
                {"name": "category", "label": "Budget Category", "type": "string", "required": True},
                {"name": "amount", "label": "Spend Amount", "type": "number", "required": True},
                {"name": "deal_stage", "label": "Deal Stage", "type": "string", "required": False}
            ],
            "steps": [
                {"step_id": "check_budget", "name": "Check Budget", "step_type": "budget_check", "estimated_duration": 5,
                 "parameters": [{"name": "category", "default_value": "{{category}}"}, {"name": "amount", "default_value": "{{amount}}"}]},
                {"step_id": "conditional_approval", "name": "Route Based on Result", "step_type": "conditional_logic", "depends_on": ["check_budget"],
                 "parameters": [{"name": "conditions", "default_value": [{"if": "budget_check_result.status == 'approved'", "then": ["notify_approved"]}, {"if": "budget_check_result.status == 'paused'", "then": ["notify_paused"]}]}]},
                {"step_id": "notify_approved", "name": "Notify Approved", "step_type": "slack_notification", "is_optional": True},
                {"step_id": "notify_paused", "name": "Notify Paused", "step_type": "slack_notification", "is_optional": True}
            ],
            "is_public": True
        }

    def _create_invoice_reconciliation_template(self) -> Dict[str, Any]:
        """Create invoice reconciliation pipeline template"""
        return {
            "template_id": "invoice_reconciliation_pipeline",
            "name": "Invoice Reconciliation Pipeline",
            "description": "Match invoices to contracts, flag discrepancies, and alert on mismatches",
            "category": "financial_ops",
            "complexity": "intermediate",
            "tags": ["invoice", "reconciliation", "contracts", "discrepancies"],
            "author": "System",
            "version": "1.0.0",
            "inputs": [],
            "steps": [
                {"step_id": "reconcile", "name": "Reconcile Invoices", "step_type": "invoice_reconciliation", "estimated_duration": 15},
                {"step_id": "check_discrepancies", "name": "Check for Discrepancies", "step_type": "conditional_logic", "depends_on": ["reconcile"],
                 "parameters": [{"name": "conditions", "default_value": [{"if": "reconciliation_result.summary.discrepancy_count > 0", "then": ["alert_discrepancies"]}]}]},
                {"step_id": "alert_discrepancies", "name": "Alert on Discrepancies", "step_type": "slack_notification", "is_optional": True,
                 "parameters": [{"name": "channel", "default_value": "#finance-alerts"}, {"name": "message", "default_value": "⚠️ Invoice discrepancies detected: {{reconciliation_result.summary.discrepancy_count}}"}]}
            ],
            "is_public": True
        }

    def _create_periodic_portal_check_template(self) -> Dict[str, Any]:
        """Create periodic portal check background agent template"""
        return {
            "template_id": "periodic_portal_check",
            "name": "Periodic Portal Check",
            "description": "Start a background agent for periodic portal monitoring with status updates",
            "category": "automation",
            "complexity": "simple",
            "tags": ["background", "periodic", "monitoring", "agent"],
            "author": "System",
            "version": "1.0.0",
            "inputs": [
                {"name": "agent_id", "label": "Agent ID", "type": "string", "required": True},
                {"name": "interval_seconds", "label": "Check Interval (seconds)", "type": "number", "required": False, "default_value": 3600}
            ],
            "steps": [
                {"step_id": "start_agent", "name": "Start Background Agent", "step_type": "background_agent_start", "estimated_duration": 5,
                 "parameters": [{"name": "agent_id", "default_value": "{{agent_id}}"}, {"name": "interval_seconds", "default_value": "{{interval_seconds}}"}]},
                {"step_id": "confirm_started", "name": "Confirm Started", "step_type": "slack_notification",
                 "parameters": [{"name": "message", "default_value": "🤖 Background agent {{agent_id}} started with {{interval_seconds}}s interval"}]}
            ],
            "is_public": True
        }
