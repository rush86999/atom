"""
Standard Workflow Templates for Enterprise Use

Based on 2025-2026 research:
- Enterprise Agent Workflows (Medium.com)

Implements:
- Pre-built workflow templates
- Parameterized templates
- Template validation
- Category-based organization
"""

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from jsonschema import validate, ValidationError

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================

class TemplateCategory(Enum):
    """Categories of workflow templates"""
    AUTOMATION = "automation"  # Recurring automations
    INTEGRATION = "integration"  # Third-party integrations
    DATA_PIPELINE = "data_pipeline"  # Data processing
    REPORTING = "reporting"  # Report generation
    APPROVAL = "approval"  # Approval workflows
    NOTIFICATION = "notification"  # Notification workflows
    ANALYSIS = "analysis"  # Data analysis workflows
    MONITORING = "monitoring"  # System monitoring


class ParameterType(Enum):
    """Types of template parameters"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    ENUM = "enum"
    DATE = "date"
    DATETIME = "datetime"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class TemplateParameter:
    """A parameter in a workflow template"""
    name: str = ""
    type: ParameterType = ParameterType.STRING
    description: str = ""

    # Validation
    required: bool = True
    default: Any = None
    allowed_values: Optional[List[Any]] = None  # For enum type

    # Constraints
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    pattern: Optional[str] = None  # Regex pattern

    def validate(self, value: Any) -> bool:
        """Validate a value against this parameter"""
        if value is None:
            return not self.required

        # Type check
        if self.type == ParameterType.STRING:
            if not isinstance(value, str):
                return False
            if self.pattern:
                import re
                if not re.match(self.pattern, value):
                    return False

        elif self.type == ParameterType.INTEGER:
            if not isinstance(value, int):
                return False
            if self.min_value is not None and value < self.min_value:
                return False
            if self.max_value is not None and value > self.max_value:
                return False

        elif self.type == ParameterType.FLOAT:
            if not isinstance(value, (int, float)):
                return False
            if self.min_value is not None and value < self.min_value:
                return False
            if self.max_value is not None and value > self.max_value:
                return False

        elif self.type == ParameterType.BOOLEAN:
            if not isinstance(value, bool):
                return False

        elif self.type == ParameterType.ARRAY:
            if not isinstance(value, list):
                return False

        elif self.type == ParameterType.ENUM:
            if self.allowed_values and value not in self.allowed_values:
                return False

        return True


@dataclass
class WorkflowStepTemplate:
    """A step template within a workflow"""
    step_id: str = ""
    name: str = ""
    description: str = ""
    step_type: str = "agent"  # agent, integration, condition

    # Configuration
    agent_type: Optional[str] = None  # Required if agent step
    capability: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Dependencies
    depends_on: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)

    # Conditions
    condition: Optional[str] = None
    parallel_group: Optional[str] = None

    # Metadata
    timeout_seconds: int = 300
    retry_count: int = 3


@dataclass
class WorkflowTemplate:
    """A reusable workflow template"""
    template_id: str = ""
    name: str = ""
    category: TemplateCategory = TemplateCategory.AUTOMATION
    description: str = ""
    version: str = "1.0.0"

    # Structure
    steps: List[WorkflowStepTemplate] = field(default_factory=list)
    start_step: str = ""

    # Parameters
    parameters: List[TemplateParameter] = field(default_factory=list)

    # Triggers
    trigger_type: str = "manual"  # manual, schedule, event, condition
    trigger_config: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    author: str = "system"
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

    # Schema validation
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None

    def validate_parameters(self, params: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate parameters against template definition"""
        errors = []

        for param in self.parameters:
            value = params.get(param.name)

            # Check required
            if param.required and value is None:
                errors.append(f"Required parameter '{param.name}' is missing")

            # Validate value
            if value is not None and not param.validate(value):
                errors.append(f"Parameter '{param.name}' validation failed")

        # Validate against schema
        if self.input_schema:
            try:
                validate(instance=params, schema=self.input_schema)
            except ValidationError as e:
                errors.append(f"Schema validation failed: {e.message}")

        return len(errors) == 0, errors

    def instantiate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Instantiate template with parameters"""
        valid, errors = self.validate_parameters(params)

        if not valid:
            raise ValueError(f"Invalid parameters: {errors}")

        # Create workflow definition
        workflow = {
            "workflow_id": f"wf_{uuid.uuid4().hex[:16]}",
            "name": self.name,
            "description": self.description,
            "template_id": self.template_id,
            "template_version": self.version,
            "parameters": params,
            "steps": [],
            "start_step": self.start_step
        }

        # Instantiate steps
        for step_template in self.steps:
            step = {
                "step_id": step_template.step_id,
                "name": step_template.name,
                "step_type": step_template.step_type,
                "agent_type": step_template.agent_type,
                "capability": step_template.capability,
                "parameters": step_template.parameters.copy(),
                "depends_on": step_template.depends_on.copy(),
                "next_steps": step_template.next_steps.copy(),
                "condition": step_template.condition,
                "parallel_group": step_template.parallel_group,
                "timeout_seconds": step_template.timeout_seconds
            }

            # Substitute parameters in step
            for key, value in step.get("parameters", {}).items():
                if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                    param_name = value[2:-2]
                    if param_name in params:
                        step["parameters"][key] = params[param_name]

            workflow["steps"].append(step)

        return workflow


# ============================================================================
# Template Library
# ============================================================================

class TemplateLibrary:
    """Library of workflow templates"""

    def __init__(self):
        self._templates: Dict[str, WorkflowTemplate] = {}
        self._category_index: Dict[TemplateCategory, List[str]] = defaultdict(list)

        # Load standard templates
        self._load_standard_templates()

    def register_template(self, template: WorkflowTemplate) -> None:
        """Register a workflow template"""
        self._templates[template.template_id] = template
        self._category_index[template.category].append(template.template_id)

        logger.info(f"Registered template: {template.template_id}")

    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """Get template by ID"""
        return self._templates.get(template_id)

    def get_templates_by_category(self, category: TemplateCategory) -> List[WorkflowTemplate]:
        """Get all templates in a category"""
        template_ids = self._category_index.get(category, [])
        return [self._templates[tid] for tid in template_ids if tid in self._templates]

    def list_templates(self) -> List[WorkflowTemplate]:
        """List all templates"""
        return list(self._templates.values())

    def search_templates(self, query: str) -> List[WorkflowTemplate]:
        """Search templates by name or description"""
        query_lower = query.lower()
        results = []

        for template in self._templates.values():
            if (query_lower in template.name.lower() or
                query_lower in template.description.lower() or
                any(query_lower in tag.lower() for tag in template.tags)):
                results.append(template)

        return results

    def _load_standard_templates(self) -> None:
        """Load standard enterprise workflow templates"""
        # Data Sync Automation Template
        data_sync = WorkflowTemplate(
            template_id="data_sync_automation",
            name="Data Sync Automation",
            category=TemplateCategory.AUTOMATION,
            description="Automated data synchronization between systems",
            version="1.0.0",
            trigger_type="schedule",
            trigger_config={"cron": "0 */6 * * *"},  # Every 6 hours
            parameters=[
                TemplateParameter(
                    name="source_system",
                    type=ParameterType.STRING,
                    description="Source system identifier",
                    required=True
                ),
                TemplateParameter(
                    name="target_system",
                    type=ParameterType.STRING,
                    description="Target system identifier",
                    required=True
                ),
                TemplateParameter(
                    name="sync_mode",
                    type=ParameterType.ENUM,
                    description="Synchronization mode",
                    allowed_values=["full", "incremental"],
                    default="incremental"
                )
            ],
            steps=[
                WorkflowStepTemplate(
                    step_id="validate_connection",
                    name="Validate Connections",
                    step_type="condition",
                    capability="system_check",
                    next_steps=["extract_data"]
                ),
                WorkflowStepTemplate(
                    step_id="extract_data",
                    name="Extract Data",
                    step_type="integration",
                    capability="data_extraction",
                    depends_on=["validate_connection"],
                    next_steps=["transform_data"]
                ),
                WorkflowStepTemplate(
                    step_id="transform_data",
                    name="Transform Data",
                    step_type="agent",
                    capability="data_transformation",
                    depends_on=["extract_data"],
                    next_steps=["load_data"]
                ),
                WorkflowStepTemplate(
                    step_id="load_data",
                    name="Load Data",
                    step_type="integration",
                    capability="data_loading",
                    depends_on=["transform_data"]
                )
            ],
            start_step="validate_connection",
            tags=["data", "automation", "integration"]
        )

        self.register_template(data_sync)

        # Report Generation Template
        report_gen = WorkflowTemplate(
            template_id="report_generation",
            name="Report Generation",
            category=TemplateCategory.REPORTING,
            description="Generate periodic business reports",
            version="1.0.0",
            trigger_type="schedule",
            trigger_config={"cron": "0 9 * * MON"},  # Monday 9am
            parameters=[
                TemplateParameter(
                    name="report_type",
                    type=ParameterType.ENUM,
                    description="Type of report",
                    allowed_values=["sales", "inventory", "financial", "operations"],
                    required=True
                ),
                TemplateParameter(
                    name="date_range",
                    type=ParameterType.STRING,
                    description="Date range for report",
                    default="last_7_days"
                ),
                TemplateParameter(
                    name="format",
                    type=ParameterType.ENUM,
                    description="Output format",
                    allowed_values=["pdf", "excel", "email"],
                    default="pdf"
                ),
                TemplateParameter(
                    name="recipients",
                    type=ParameterType.ARRAY,
                    description="Email recipients",
                    default=[]
                )
            ],
            steps=[
                WorkflowStepTemplate(
                    step_id="gather_data",
                    name="Gather Data",
                    step_type="agent",
                    capability="data_aggregation",
                    next_steps=["generate_report"]
                ),
                WorkflowStepTemplate(
                    step_id="generate_report",
                    name="Generate Report",
                    step_type="agent",
                    capability="report_generation",
                    depends_on=["gather_data"],
                    next_steps=["distribute_report"]
                ),
                WorkflowStepTemplate(
                    step_id="distribute_report",
                    name="Distribute Report",
                    step_type="integration",
                    capability="email_delivery",
                    depends_on=["generate_report"]
                )
            ],
            start_step="gather_data",
            tags=["reporting", "business"]
        )

        self.register_template(report_gen)

        # Approval Workflow Template
        approval = WorkflowTemplate(
            template_id="approval_workflow",
            name="Approval Workflow",
            category=TemplateCategory.APPROVAL,
            description="Multi-level approval workflow for requests",
            version="1.0.0",
            trigger_type="manual",
            parameters=[
                TemplateParameter(
                    name="request_type",
                    type=ParameterType.STRING,
                    description="Type of request",
                    required=True
                ),
                TemplateParameter(
                    name="approval_levels",
                    type=ParameterType.INTEGER,
                    description="Number of approval levels",
                    default=3,
                    min_value=1,
                    max_value=5
                ),
                TemplateParameter(
                    name="auto_approve_threshold",
                    type=ParameterType.FLOAT,
                    description="Amount under which auto-approval applies",
                    default=1000.0
                )
            ],
            steps=[
                WorkflowStepTemplate(
                    step_id="validate_request",
                    name="Validate Request",
                    step_type="condition",
                    capability="request_validation",
                    next_steps=["check_auto_approve"]
                ),
                WorkflowStepTemplate(
                    step_id="check_auto_approve",
                    name="Check Auto-Approve",
                    step_type="condition",
                    capability="threshold_check",
                    depends_on=["validate_request"],
                    next_steps=["level1_approval", "manual_approval"]
                ),
                WorkflowStepTemplate(
                    step_id="level1_approval",
                    name="Level 1 Approval",
                    step_type="agent",
                    capability="approval",
                    depends_on=["check_auto_approve"],
                    next_steps=["level2_approval"]
                ),
                WorkflowStepTemplate(
                    step_id="level2_approval",
                    name="Level 2 Approval",
                    step_type="agent",
                    capability="approval",
                    depends_on=["level1_approval"],
                    next_steps=["level3_approval"]
                ),
                WorkflowStepTemplate(
                    step_id="level3_approval",
                    name="Level 3 Approval",
                    step_type="agent",
                    capability="approval",
                    depends_on=["level2_approval"],
                    next_steps=["complete_approval"]
                ),
                WorkflowStepTemplate(
                    step_id="manual_approval",
                    name="Manual Approval",
                    step_type="agent",
                    capability="manual_review",
                    depends_on=["check_auto_approve"],
                    next_steps=["complete_approval"]
                ),
                WorkflowStepTemplate(
                    step_id="complete_approval",
                    name="Complete Approval",
                    step_type="integration",
                    capability="approval_notification"
                )
            ],
            start_step="validate_request",
            tags=["approval", "business"]
        )

        self.register_template(approval)

        # Monitoring Alert Template
        monitoring = WorkflowTemplate(
            template_id="monitoring_alert",
            name="Monitoring Alert",
            category=TemplateCategory.MONITORING,
            description="System monitoring and alerting workflow",
            version="1.0.0",
            trigger_type="event",
            trigger_config={"event_type": "system.alert"},
            parameters=[
                TemplateParameter(
                    name="alert_threshold",
                    type=ParameterType.FLOAT,
                    description="Alert threshold",
                    required=True
                ),
                TemplateParameter(
                    name="notification_channels",
                    type=ParameterType.ARRAY,
                    description="Notification channels",
                    allowed_values=["email", "slack", "pagerduty"],
                    default=["email"]
                )
            ],
            steps=[
                WorkflowStepTemplate(
                    step_id="check_metrics",
                    name="Check Metrics",
                    step_type="agent",
                    capability="metrics_check",
                    next_steps=["evaluate_condition"]
                ),
                WorkflowStepTemplate(
                    step_id="evaluate_condition",
                    name="Evaluate Condition",
                    step_type="condition",
                    capability="threshold_check",
                    next_steps=["send_alert", "log_only"]
                ),
                WorkflowStepTemplate(
                    step_id="send_alert",
                    name="Send Alert",
                    step_type="integration",
                    capability="alert_delivery"
                ),
                WorkflowStepTemplate(
                    step_id="log_only",
                    name="Log Only",
                    step_type="agent",
                    capability="logging"
                )
            ],
            start_step="check_metrics",
            tags=["monitoring", "alerting"]
        )

        self.register_template(monitoring)

    def get_statistics(self) -> Dict[str, Any]:
        """Get template library statistics"""
        return {
            "total_templates": len(self._templates),
            "category_distribution": {
                category.value: len(self._category_index.get(category, []))
                for category in TemplateCategory
            },
            "parameter_counts": {
                t.template_id: len(t.parameters)
                for t in self._templates.values()
            }
        }


# ============================================================================
# Factory
# ============================================================================

_template_library_instance: Optional[TemplateLibrary] = None


def get_template_library() -> TemplateLibrary:
    """Get or create template library instance"""
    global _template_library_instance
    if _template_library_instance is None:
        _template_library_instance = TemplateLibrary()
    return _template_library_instance
