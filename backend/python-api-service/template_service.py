import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class TemplateType(Enum):
    """Types of templates available"""

    EMAIL = "email"
    DOCUMENT = "document"
    PRESENTATION = "presentation"
    MEETING_AGENDA = "meeting_agenda"
    PROJECT_PLAN = "project_plan"
    BUSINESS_PROPOSAL = "business_proposal"
    REPORT = "report"
    SOCIAL_MEDIA = "social_media"
    CODE = "code"
    CUSTOM = "custom"


class Template:
    """Template representation"""

    def __init__(
        self,
        id: str,
        name: str,
        template_type: TemplateType,
        content: str,
        description: Optional[str] = None,
        variables: Optional[List[str]] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        is_public: bool = False,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id
        self.name = name
        self.template_type = template_type
        self.content = content
        self.description = description
        self.variables = variables or []
        self.category = category
        self.tags = tags or []
        self.user_id = user_id
        self.is_public = is_public
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert template to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "template_type": self.template_type.value,
            "content": self.content,
            "description": self.description,
            "variables": self.variables,
            "category": self.category,
            "tags": self.tags,
            "user_id": self.user_id,
            "is_public": self.is_public,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Template":
        """Create template from dictionary"""
        return cls(
            id=data["id"],
            name=data["name"],
            template_type=TemplateType(data["template_type"]),
            content=data["content"],
            description=data.get("description"),
            variables=data.get("variables", []),
            category=data.get("category"),
            tags=data.get("tags", []),
            user_id=data.get("user_id"),
            is_public=data.get("is_public", False),
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else None,
            updated_at=datetime.fromisoformat(data["updated_at"])
            if data.get("updated_at")
            else None,
        )

    def render(self, variables: Dict[str, str]) -> str:
        """Render template with provided variables"""
        rendered_content = self.content

        for var_name, var_value in variables.items():
            placeholder = f"{{{{ {var_name} }}}}"
            rendered_content = rendered_content.replace(placeholder, str(var_value))

        return rendered_content


class TemplateService:
    """Service for template management and generation"""

    def __init__(self):
        self.templates = {}  # In-memory storage for demo purposes
        self._initialize_default_templates()

    def _initialize_default_templates(self):
        """Initialize with default templates"""
        default_templates = [
            Template(
                id="email_follow_up",
                name="Follow-up Email",
                template_type=TemplateType.EMAIL,
                content="""Dear {{ recipient_name }},

I hope this email finds you well. I wanted to follow up on our recent {{ discussion_topic }}.

{{ follow_up_content }}

Please let me know if you have any questions or need additional information.

Best regards,
{{ sender_name }}""",
                description="Professional follow-up email template",
                variables=[
                    "recipient_name",
                    "discussion_topic",
                    "follow_up_content",
                    "sender_name",
                ],
                category="business",
                tags=["email", "follow-up", "professional"],
                is_public=True,
            ),
            Template(
                id="meeting_agenda_standard",
                name="Standard Meeting Agenda",
                template_type=TemplateType.MEETING_AGENDA,
                content="""Meeting: {{ meeting_title }}
Date: {{ meeting_date }}
Time: {{ meeting_time }}
Location: {{ meeting_location }}

Agenda:
1. Welcome and introductions (5 minutes)
2. Review of previous meeting minutes (10 minutes)
3. {{ agenda_item_1 }} ({{ duration_1 }} minutes)
4. {{ agenda_item_2 }} ({{ duration_2 }} minutes)
5. {{ agenda_item_3 }} ({{ duration_3 }} minutes)
6. Action items and next steps (10 minutes)
7. Any other business (5 minutes)

Attendees: {{ attendees }}""",
                description="Standard meeting agenda template",
                variables=[
                    "meeting_title",
                    "meeting_date",
                    "meeting_time",
                    "meeting_location",
                    "agenda_item_1",
                    "duration_1",
                    "agenda_item_2",
                    "duration_2",
                    "agenda_item_3",
                    "duration_3",
                    "attendees",
                ],
                category="meetings",
                tags=["agenda", "meeting", "professional"],
                is_public=True,
            ),
            Template(
                id="project_plan_basic",
                name="Basic Project Plan",
                template_type=TemplateType.PROJECT_PLAN,
                content="""# Project Plan: {{ project_name }}

## Overview
- **Project Name**: {{ project_name }}
- **Project Manager**: {{ project_manager }}
- **Start Date**: {{ start_date }}
- **End Date**: {{ end_date }}
- **Budget**: {{ budget }}

## Objectives
{{ project_objectives }}

## Key Deliverables
{{ deliverables }}

## Timeline
{{ timeline }}

## Resources
{{ resources }}

## Risks and Mitigations
{{ risks }}""",
                description="Basic project plan template",
                variables=[
                    "project_name",
                    "project_manager",
                    "start_date",
                    "end_date",
                    "budget",
                    "project_objectives",
                    "deliverables",
                    "timeline",
                    "resources",
                    "risks",
                ],
                category="project_management",
                tags=["project", "plan", "management"],
                is_public=True,
            ),
            Template(
                id="business_proposal_executive",
                name="Executive Business Proposal",
                template_type=TemplateType.BUSINESS_PROPOSAL,
                content="""# Executive Business Proposal: {{ proposal_title }}

## Executive Summary
{{ executive_summary }}

## Problem Statement
{{ problem_statement }}

## Proposed Solution
{{ proposed_solution }}

## Market Opportunity
{{ market_opportunity }}

## Financial Projections
{{ financial_projections }}

## Implementation Timeline
{{ implementation_timeline }}

## Conclusion
{{ conclusion }}""",
                description="Executive business proposal template",
                variables=[
                    "proposal_title",
                    "executive_summary",
                    "problem_statement",
                    "proposed_solution",
                    "market_opportunity",
                    "financial_projections",
                    "implementation_timeline",
                    "conclusion",
                ],
                category="business",
                tags=["proposal", "business", "executive"],
                is_public=True,
            ),
            Template(
                id="social_media_linkedin",
                name="LinkedIn Post Template",
                template_type=TemplateType.SOCIAL_MEDIA,
                content="""{{ post_title }}

{{ post_content }}

{{ call_to_action }}

#{{ hashtag_1 }} #{{ hashtag_2 }} #{{ hashtag_3 }}""",
                description="Professional LinkedIn post template",
                variables=[
                    "post_title",
                    "post_content",
                    "call_to_action",
                    "hashtag_1",
                    "hashtag_2",
                    "hashtag_3",
                ],
                category="social_media",
                tags=["linkedin", "social", "professional"],
                is_public=True,
            ),
        ]

        for template in default_templates:
            self.templates[template.id] = template

    async def get_templates(
        self,
        template_type: Optional[TemplateType] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        include_public: bool = True,
    ) -> List[Template]:
        """Get templates based on filters"""
        try:
            filtered_templates = list(self.templates.values())

            # Filter by template type
            if template_type:
                filtered_templates = [
                    t for t in filtered_templates if t.template_type == template_type
                ]

            # Filter by category
            if category:
                filtered_templates = [
                    t for t in filtered_templates if t.category == category
                ]

            # Filter by tags
            if tags:
                filtered_templates = [
                    t for t in filtered_templates if any(tag in t.tags for tag in tags)
                ]

            # Filter by user and public status
            if user_id:
                filtered_templates = [
                    t
                    for t in filtered_templates
                    if t.user_id == user_id or (include_public and t.is_public)
                ]
            elif not include_public:
                filtered_templates = [t for t in filtered_templates if not t.is_public]

            return filtered_templates

        except Exception as e:
            logger.error(f"Error getting templates: {e}")
            return []

    async def get_template(self, template_id: str) -> Optional[Template]:
        """Get a specific template by ID"""
        return self.templates.get(template_id)

    async def create_template(
        self,
        name: str,
        template_type: TemplateType,
        content: str,
        description: Optional[str] = None,
        variables: Optional[List[str]] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        is_public: bool = False,
    ) -> Optional[Template]:
        """Create a new template"""
        try:
            template_id = str(uuid.uuid4())
            template = Template(
                id=template_id,
                name=name,
                template_type=template_type,
                content=content,
                description=description,
                variables=variables or [],
                category=category,
                tags=tags or [],
                user_id=user_id,
                is_public=is_public,
            )

            self.templates[template_id] = template
            logger.info(f"Created template {template_id}: {name}")
            return template

        except Exception as e:
            logger.error(f"Error creating template: {e}")
            return None

    async def update_template(
        self,
        template_id: str,
        updates: Dict[str, Any],
    ) -> Optional[Template]:
        """Update an existing template"""
        try:
            if template_id not in self.templates:
                logger.warning(f"Template {template_id} not found")
                return None

            template = self.templates[template_id]

            # Update fields
            if "name" in updates:
                template.name = updates["name"]
            if "content" in updates:
                template.content = updates["content"]
            if "description" in updates:
                template.description = updates["description"]
            if "variables" in updates:
                template.variables = updates["variables"]
            if "category" in updates:
                template.category = updates["category"]
            if "tags" in updates:
                template.tags = updates["tags"]
            if "is_public" in updates:
                template.is_public = updates["is_public"]

            template.updated_at = datetime.now()

            logger.info(f"Updated template {template_id}")
            return template

        except Exception as e:
            logger.error(f"Error updating template {template_id}: {e}")
            return None

    async def delete_template(self, template_id: str) -> bool:
        """Delete a template"""
        try:
            if template_id in self.templates:
                del self.templates[template_id]
                logger.info(f"Deleted template {template_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error deleting template {template_id}: {e}")
            return False

    async def render_template(
        self,
        template_id: str,
        variables: Dict[str, str],
    ) -> Optional[str]:
        """Render a template with provided variables"""
        try:
            template = await self.get_template(template_id)
            if not template:
                return None

            return template.render(variables)

        except Exception as e:
            logger.error(f"Error rendering template {template_id}: {e}")
            return None

    async def search_templates(
        self,
        query: str,
        template_type: Optional[TemplateType] = None,
        user_id: Optional[str] = None,
    ) -> List[Template]:
        """Search templates by name, description, or content"""
        try:
            all_templates = await self.get_templates(
                template_type=template_type,
                user_id=user_id,
                include_public=True,
            )

            query_lower = query.lower()
            filtered_templates = [
                t
                for t in all_templates
                if (
                    query_lower in t.name.lower()
                    or (t.description and query_lower in t.description.lower())
                    or query_lower in t.content.lower()
                )
            ]

            return filtered_templates

        except Exception as e:
            logger.error(f"Error searching templates: {e}")
            return []

    async def get_template_statistics(self) -> Dict[str, Any]:
        """Get statistics about templates"""
        try:
            total_templates = len(self.templates)
            template_types = {}
            categories = {}

            for template in self.templates.values():
                # Count by template type
                type_name = template.template_type.value
                template_types[type_name] = template_types.get(type_name, 0) + 1

                # Count by category
                if template.category:
                    categories[template.category] = (
                        categories.get(template.category, 0) + 1
                    )

            return {
                "total_templates": total_templates,
                "template_types": template_types,
                "categories": categories,
                "public_templates": len(
                    [t for t in self.templates.values() if t.is_public]
                ),
                "user_templates": len(
                    [t for t in self.templates.values() if t.user_id]
                ),
            }

        except Exception as e:
            logger.error(f"Error getting template statistics: {e}")
            return {}


# Global template service instance
template_service = TemplateService()
