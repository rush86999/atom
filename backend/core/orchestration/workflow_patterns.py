"""
Enterprise Workflow Patterns Module

Provides:
- Standard workflow templates
- Workflow composition primitives
- Workflow versioning and migration

Based on 2025-2026 research:
- Enterprise Agent Workflows (Medium.com)
- AgentOrchestra Case Study (arXiv:2506.12508v4)
"""

from core.orchestration.workflow_templates import (
    WorkflowTemplate,
    TemplateCategory,
    TemplateParameter,
    get_template_library,
)

from core.orchestration.workflow_composer import (
    WorkflowComposer,
    CompositionPrimitive,
    CompositionStrategy,
    ComposedWorkflow,
    get_workflow_composer,
)

from core.orchestration.workflow_versioning import (
    WorkflowVersion,
    VersionSchema,
    MigrationStrategy,
    VersionedWorkflow,
    get_workflow_versioning,
)

__all__ = [
    # Templates
    "WorkflowTemplate",
    "TemplateCategory",
    "TemplateParameter",
    "get_template_library",

    # Composition
    "WorkflowComposer",
    "CompositionPrimitive",
    "CompositionStrategy",
    "ComposedWorkflow",
    "get_workflow_composer",

    # Versioning
    "WorkflowVersion",
    "VersionSchema",
    "MigrationStrategy",
    "VersionedWorkflow",
    "get_workflow_versioning",
]
