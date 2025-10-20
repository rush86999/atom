"""
Trigger Configuration Service for Atom Workflow Automation

This service manages trigger configurations stored in the database,
allowing dynamic trigger creation and management for workflow automation.
"""

import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, JSON, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class TriggerConfiguration(Base):
    """Database model for trigger configurations"""

    __tablename__ = "trigger_configurations"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    service = Column(String(50), nullable=False)
    description = Column(Text)
    icon = Column(String(10))
    color = Column(String(7))  # Hex color code
    enabled = Column(Boolean, default=True)
    fields_schema = Column(JSON)  # Field definitions for the trigger
    outputs_schema = Column(JSON)  # Output definitions
    handler_function = Column(String(100))  # Backend function to handle this trigger
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TriggerConfigurationService:
    """Service for managing trigger configurations in the database"""

    def __init__(self, database_url: str = None):
        """Initialize the service with database connection"""
        if database_url is None:
            database_url = "sqlite:///triggers.db"  # Default for development

        self.engine = create_engine(database_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        # Initialize with default triggers if empty
        self._initialize_default_triggers()

    def _initialize_default_triggers(self):
        """Initialize the database with default trigger configurations"""
        if self.session.query(TriggerConfiguration).count() == 0:
            default_triggers = self._get_default_trigger_configurations()
            for trigger in default_triggers:
                self.create_trigger(trigger)

    def _get_default_trigger_configurations(self) -> List[Dict[str, Any]]:
        """Return default trigger configurations for all supported services"""
        return [
            # Gmail Triggers
            {
                "id": "gmail_new_email",
                "name": "Gmail - New Email",
                "service": "gmail",
                "description": "Trigger when new emails arrive matching specified criteria",
                "icon": "G",
                "color": "#EA4335",
                "fields_schema": [
                    {
                        "id": "query",
                        "label": "Email Query",
                        "type": "text",
                        "placeholder": "is:unread label:important",
                        "defaultValue": "is:unread",
                        "required": True,
                    },
                    {
                        "id": "maxResults",
                        "label": "Max Results",
                        "type": "number",
                        "min": 1,
                        "max": 50,
                        "defaultValue": 10,
                        "required": True,
                    },
                    {
                        "id": "schedule",
                        "label": "Check Schedule",
                        "type": "text",
                        "placeholder": "*/5 * * * * (every 5 minutes)",
                        "defaultValue": "*/5 * * * *",
                    },
                ],
                "outputs_schema": [
                    {"id": "emails", "label": "Emails List", "type": "array"},
                    {"id": "email_count", "label": "Email Count", "type": "number"},
                    {"id": "latest_email", "label": "Latest Email", "type": "object"},
                ],
                "handler_function": "_handle_gmail_trigger",
            },
            # Google Calendar Triggers
            {
                "id": "google_calendar_new_event",
                "name": "Google Calendar - New Event",
                "service": "google_calendar",
                "description": "Trigger when new calendar events are created",
                "icon": "G",
                "color": "#4285F4",
                "fields_schema": [
                    {
                        "id": "calendarId",
                        "label": "Calendar ID",
                        "type": "text",
                        "placeholder": "primary",
                        "defaultValue": "primary",
                        "required": True,
                    },
                    {
                        "id": "eventType",
                        "label": "Event Type",
                        "type": "select",
                        "options": [
                            {"value": "created", "label": "New Events"},
                            {"value": "updated", "label": "Updated Events"},
                            {"value": "cancelled", "label": "Cancelled Events"},
                        ],
                        "defaultValue": "created",
                        "required": True,
                    },
                    {
                        "id": "timeRange",
                        "label": "Time Range",
                        "type": "select",
                        "options": [
                            {"value": "upcoming", "label": "Upcoming Events"},
                            {"value": "today", "label": "Today's Events"},
                            {"value": "tomorrow", "label": "Tomorrow's Events"},
                        ],
                        "defaultValue": "upcoming",
                        "required": True,
                    },
                ],
                "outputs_schema": [
                    {"id": "events", "label": "Events List", "type": "array"},
                    {"id": "event_count", "label": "Event Count", "type": "number"},
                    {"id": "next_event", "label": "Next Event", "type": "object"},
                ],
                "handler_function": "_handle_google_calendar_trigger",
            },
            # Slack Triggers
            {
                "id": "slack_new_message",
                "name": "Slack - New Message",
                "service": "slack",
                "description": "Trigger when new messages arrive in specified channels",
                "icon": "S",
                "color": "#4A154B",
                "fields_schema": [
                    {
                        "id": "channelId",
                        "label": "Channel ID",
                        "type": "text",
                        "placeholder": "C1234567890 or #general",
                        "required": True,
                    },
                    {
                        "id": "triggerType",
                        "label": "Trigger Type",
                        "type": "select",
                        "options": [
                            {"value": "new_message", "label": "New Message"},
                            {"value": "message_reaction", "label": "Message Reaction"},
                            {"value": "thread_reply", "label": "Thread Reply"},
                        ],
                        "defaultValue": "new_message",
                        "required": True,
                    },
                    {
                        "id": "keywordFilter",
                        "label": "Keyword Filter",
                        "type": "text",
                        "placeholder": "urgent, help, question",
                    },
                ],
                "outputs_schema": [
                    {"id": "messages", "label": "Messages List", "type": "array"},
                    {"id": "message_count", "label": "Message Count", "type": "number"},
                    {
                        "id": "latest_message",
                        "label": "Latest Message",
                        "type": "object",
                    },
                ],
                "handler_function": "_handle_slack_trigger",
            },
            # Notion Triggers
            {
                "id": "notion_page_created",
                "name": "Notion - Page Created",
                "service": "notion",
                "description": "Trigger when new pages are created in specified databases",
                "icon": "N",
                "color": "#000000",
                "fields_schema": [
                    {
                        "id": "databaseId",
                        "label": "Database ID",
                        "type": "text",
                        "placeholder": "Database ID or URL",
                        "required": True,
                    },
                    {
                        "id": "filterProperty",
                        "label": "Filter Property",
                        "type": "text",
                        "placeholder": "Status, Priority, Type",
                    },
                    {
                        "id": "filterValue",
                        "label": "Filter Value",
                        "type": "text",
                        "placeholder": "Done, High, Bug",
                    },
                ],
                "outputs_schema": [
                    {"id": "pages", "label": "Pages List", "type": "array"},
                    {"id": "page_count", "label": "Page Count", "type": "number"},
                    {"id": "latest_page", "label": "Latest Page", "type": "object"},
                ],
                "handler_function": "_handle_notion_trigger",
            },
            # GitHub Triggers
            {
                "id": "github_new_issue",
                "name": "GitHub - New Issue",
                "service": "github",
                "description": "Trigger when new issues are created in repositories",
                "icon": "GH",
                "color": "#181717",
                "fields_schema": [
                    {
                        "id": "repository",
                        "label": "Repository",
                        "type": "text",
                        "placeholder": "owner/repo-name",
                        "required": True,
                    },
                    {
                        "id": "issueType",
                        "label": "Issue Type",
                        "type": "select",
                        "options": [
                            {"value": "all", "label": "All Issues"},
                            {"value": "opened", "label": "Opened Issues"},
                            {"value": "closed", "label": "Closed Issues"},
                        ],
                        "defaultValue": "opened",
                        "required": True,
                    },
                ],
                "outputs_schema": [
                    {"id": "issues", "label": "Issues List", "type": "array"},
                    {"id": "issue_count", "label": "Issue Count", "type": "number"},
                    {"id": "latest_issue", "label": "Latest Issue", "type": "object"},
                ],
                "handler_function": "_handle_github_trigger",
            },
            # Trello Triggers
            {
                "id": "trello_new_card",
                "name": "Trello - New Card",
                "service": "trello",
                "description": "Trigger when new cards are created on boards",
                "icon": "T",
                "color": "#0079BF",
                "fields_schema": [
                    {
                        "id": "boardId",
                        "label": "Board ID",
                        "type": "text",
                        "required": True,
                    },
                    {
                        "id": "listName",
                        "label": "List Name",
                        "type": "text",
                        "placeholder": "To Do, In Progress, Done",
                    },
                ],
                "outputs_schema": [
                    {"id": "cards", "label": "Cards List", "type": "array"},
                    {"id": "card_count", "label": "Card Count", "type": "number"},
                    {"id": "latest_card", "label": "Latest Card", "type": "object"},
                ],
                "handler_function": "_handle_trello_trigger",
            },
            # Asana Triggers
            {
                "id": "asana_new_task",
                "name": "Asana - New Task",
                "service": "asana",
                "description": "Trigger when new tasks are created in projects",
                "icon": "A",
                "color": "#273347",
                "fields_schema": [
                    {
                        "id": "projectId",
                        "label": "Project ID",
                        "type": "text",
                        "required": True,
                    },
                    {
                        "id": "assignee",
                        "label": "Assignee Filter",
                        "type": "text",
                        "placeholder": "User ID or email",
                    },
                ],
                "outputs_schema": [
                    {"id": "tasks", "label": "Tasks List", "type": "array"},
                    {"id": "task_count", "label": "Task Count", "type": "number"},
                    {"id": "latest_task", "label": "Latest Task", "type": "object"},
                ],
                "handler_function": "_handle_asana_trigger",
            },
        ]

    def create_trigger(self, trigger_data: Dict[str, Any]) -> TriggerConfiguration:
        """Create a new trigger configuration"""
        trigger = TriggerConfiguration(
            id=trigger_data["id"],
            name=trigger_data["name"],
            service=trigger_data["service"],
            description=trigger_data.get("description", ""),
            icon=trigger_data.get("icon", ""),
            color=trigger_data.get("color", "#666666"),
            fields_schema=trigger_data.get("fields_schema", []),
            outputs_schema=trigger_data.get("outputs_schema", []),
            handler_function=trigger_data.get("handler_function", ""),
        )

        self.session.add(trigger)
        self.session.commit()
        return trigger

    def get_trigger(self, trigger_id: str) -> Optional[TriggerConfiguration]:
        """Get a trigger configuration by ID"""
        return self.session.query(TriggerConfiguration).filter_by(id=trigger_id).first()

    def get_all_triggers(self) -> List[TriggerConfiguration]:
        """Get all trigger configurations"""
        return self.session.query(TriggerConfiguration).filter_by(enabled=True).all()

    def get_triggers_by_service(self, service: str) -> List[TriggerConfiguration]:
        """Get all triggers for a specific service"""
        return (
            self.session.query(TriggerConfiguration)
            .filter_by(service=service, enabled=True)
            .all()
        )

    def update_trigger(
        self, trigger_id: str, update_data: Dict[str, Any]
    ) -> Optional[TriggerConfiguration]:
        """Update a trigger configuration"""
        trigger = self.get_trigger(trigger_id)
        if not trigger:
            return None

        for key, value in update_data.items():
            if hasattr(trigger, key):
                setattr(trigger, key, value)

        trigger.updated_at = datetime.utcnow()
        self.session.commit()
        return trigger

    def delete_trigger(self, trigger_id: str) -> bool:
        """Delete a trigger configuration"""
        trigger = self.get_trigger(trigger_id)
        if not trigger:
            return False

        self.session.delete(trigger)
        self.session.commit()
        return True

    def disable_trigger(self, trigger_id: str) -> bool:
        """Disable a trigger (soft delete)"""
        trigger = self.get_trigger(trigger_id)
        if not trigger:
            return False

        trigger.enabled = False
        trigger.updated_at = datetime.utcnow()
        self.session.commit()
        return True

    def get_trigger_schema(self, trigger_id: str) -> Optional[Dict[str, Any]]:
        """Get the complete schema for a trigger including fields and outputs"""
        trigger = self.get_trigger(trigger_id)
        if not trigger:
            return None

        return {
            "id": trigger.id,
            "name": trigger.name,
            "service": trigger.service,
            "description": trigger.description,
            "icon": trigger.icon,
            "color": trigger.color,
            "fields": trigger.fields_schema,
            "outputs": trigger.outputs_schema,
            "handler_function": trigger.handler_function,
        }

    def get_all_trigger_schemas(self) -> List[Dict[str, Any]]:
        """Get schemas for all enabled triggers"""
        triggers = self.get_all_triggers()
        return [self.get_trigger_schema(trigger.id) for trigger in triggers]

    def validate_trigger_config(
        self, trigger_id: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate trigger configuration against its schema"""
        trigger = self.get_trigger(trigger_id)
        if not trigger:
            return {"valid": False, "errors": ["Trigger not found"]}

        errors = []

        # Check required fields
        for field in trigger.fields_schema:
            if field.get("required") and field["id"] not in config:
                errors.append(f"Missing required field: {field['label']}")

        # Validate field types
        for field_id, value in config.items():
            field_def = next(
                (f for f in trigger.fields_schema if f["id"] == field_id), None
            )
            if field_def:
                if field_def["type"] == "number" and not isinstance(
                    value, (int, float)
                ):
                    try:
                        float(value)
                    except (ValueError, TypeError):
                        errors.append(f"Field {field_def['label']} must be a number")

                # Add more type validations as needed

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "trigger": self.get_trigger_schema(trigger_id),
        }


# Singleton instance for easy access
trigger_service = TriggerConfigurationService()

if __name__ == "__main__":
    # Test the service
    service = TriggerConfigurationService()
    triggers = service.get_all_triggers()
    print(f"Loaded {len(triggers)} triggers:")
    for trigger in triggers:
        print(f"- {trigger.name} ({trigger.service})")
