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
        """Return comprehensive trigger configurations for all supported services"""
        return [
            # ========== EMAIL SERVICES ==========
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
                    },
                ],
                "outputs_schema": [
                    {"id": "emails", "label": "Emails List", "type": "array"},
                    {"id": "email_count", "label": "Email Count", "type": "number"},
                    {"id": "latest_email", "label": "Latest Email", "type": "object"},
                ],
                "handler_function": "_handle_gmail_trigger",
            },
            {
                "id": "gmail_email_labeled",
                "name": "Gmail - Email Labeled",
                "service": "gmail",
                "description": "Trigger when emails are labeled with specific labels",
                "icon": "G",
                "color": "#EA4335",
                "fields_schema": [
                    {
                        "id": "labelName",
                        "label": "Label Name",
                        "type": "text",
                        "placeholder": "Important, Follow-up, Urgent",
                        "required": True,
                    }
                ],
                "outputs_schema": [
                    {"id": "emails", "label": "Emails List", "type": "array"},
                    {"id": "email_count", "label": "Email Count", "type": "number"},
                ],
                "handler_function": "_handle_gmail_trigger",
            },
            {
                "id": "gmail_email_starred",
                "name": "Gmail - Email Starred",
                "service": "gmail",
                "description": "Trigger when emails are starred",
                "icon": "G",
                "color": "#EA4335",
                "fields_schema": [
                    {
                        "id": "maxResults",
                        "label": "Max Results",
                        "type": "number",
                        "min": 1,
                        "max": 50,
                        "defaultValue": 10,
                    }
                ],
                "outputs_schema": [
                    {"id": "emails", "label": "Emails List", "type": "array"},
                    {"id": "email_count", "label": "Email Count", "type": "number"},
                ],
                "handler_function": "_handle_gmail_trigger",
            },
            # Outlook Triggers
            {
                "id": "outlook_new_email",
                "name": "Outlook - New Email",
                "service": "outlook",
                "description": "Trigger when new emails arrive in Outlook",
                "icon": "O",
                "color": "#0078D4",
                "fields_schema": [
                    {
                        "id": "folder",
                        "label": "Folder",
                        "type": "text",
                        "placeholder": "Inbox, Sent Items",
                        "defaultValue": "Inbox",
                    }
                ],
                "outputs_schema": [
                    {"id": "emails", "label": "Emails List", "type": "array"},
                    {"id": "email_count", "label": "Email Count", "type": "number"},
                ],
                "handler_function": "_handle_outlook_trigger",
            },
            {
                "id": "outlook_email_flagged",
                "name": "Outlook - Email Flagged",
                "service": "outlook",
                "description": "Trigger when emails are flagged for follow-up",
                "icon": "O",
                "color": "#0078D4",
                "fields_schema": [
                    {
                        "id": "importance",
                        "label": "Importance",
                        "type": "select",
                        "options": [
                            {"value": "all", "label": "All"},
                            {"value": "high", "label": "High"},
                            {"value": "normal", "label": "Normal"},
                        ],
                        "defaultValue": "all",
                    }
                ],
                "outputs_schema": [
                    {"id": "emails", "label": "Emails List", "type": "array"},
                    {"id": "email_count", "label": "Email Count", "type": "number"},
                ],
                "handler_function": "_handle_outlook_trigger",
            },
            # ========== CALENDAR SERVICES ==========
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
                    },
                ],
                "outputs_schema": [
                    {"id": "events", "label": "Events List", "type": "array"},
                    {"id": "event_count", "label": "Event Count", "type": "number"},
                    {"id": "next_event", "label": "Next Event", "type": "object"},
                ],
                "handler_function": "_handle_google_calendar_trigger",
            },
            {
                "id": "google_calendar_event_starting",
                "name": "Google Calendar - Event Starting",
                "service": "google_calendar",
                "description": "Trigger when events are about to start",
                "icon": "G",
                "color": "#4285F4",
                "fields_schema": [
                    {
                        "id": "minutesBefore",
                        "label": "Minutes Before",
                        "type": "number",
                        "placeholder": "15",
                        "defaultValue": 15,
                    }
                ],
                "outputs_schema": [
                    {"id": "events", "label": "Events List", "type": "array"},
                    {"id": "event_count", "label": "Event Count", "type": "number"},
                ],
                "handler_function": "_handle_google_calendar_trigger",
            },
            # Outlook Calendar Triggers
            {
                "id": "outlook_calendar_new_event",
                "name": "Outlook Calendar - New Event",
                "service": "outlook_calendar",
                "description": "Trigger when new events are created in Outlook Calendar",
                "icon": "O",
                "color": "#0078D4",
                "fields_schema": [
                    {
                        "id": "eventType",
                        "label": "Event Type",
                        "type": "select",
                        "options": [
                            {"value": "created", "label": "New Events"},
                            {"value": "updated", "label": "Updated Events"},
                        ],
                        "defaultValue": "created",
                    }
                ],
                "outputs_schema": [
                    {"id": "events", "label": "Events List", "type": "array"},
                    {"id": "event_count", "label": "Event Count", "type": "number"},
                ],
                "handler_function": "_handle_outlook_calendar_trigger",
            },
            # Calendly Triggers
            {
                "id": "calendly_new_booking",
                "name": "Calendly - New Booking",
                "service": "calendly",
                "description": "Trigger when someone books a meeting through Calendly",
                "icon": "C",
                "color": "#006BFF",
                "fields_schema": [
                    {
                        "id": "eventType",
                        "label": "Event Type",
                        "type": "text",
                        "placeholder": "15 Minute Meeting, 30 Minute Consultation",
                    }
                ],
                "outputs_schema": [
                    {"id": "bookings", "label": "Bookings List", "type": "array"},
                    {"id": "booking_count", "label": "Booking Count", "type": "number"},
                ],
                "handler_function": "_handle_calendly_trigger",
            },
            {
                "id": "calendly_cancellation",
                "name": "Calendly - Booking Cancelled",
                "service": "calendly",
                "description": "Trigger when a Calendly booking is cancelled",
                "icon": "C",
                "color": "#006BFF",
                "fields_schema": [
                    {
                        "id": "eventType",
                        "label": "Event Type",
                        "type": "text",
                        "placeholder": "15 Minute Meeting, 30 Minute Consultation",
                    }
                ],
                "outputs_schema": [
                    {
                        "id": "cancellations",
                        "label": "Cancellations List",
                        "type": "array",
                    },
                    {
                        "id": "cancellation_count",
                        "label": "Cancellation Count",
                        "type": "number",
                    },
                ],
                "handler_function": "_handle_calendly_trigger",
            },
            {
                "id": "zoom_meeting_created",
                "name": "Zoom - Meeting Created",
                "service": "zoom",
                "description": "Trigger when new Zoom meetings are scheduled",
                "icon": "Z",
                "color": "#2D8CFF",
                "fields_schema": [
                    {
                        "id": "meetingType",
                        "label": "Meeting Type",
                        "type": "select",
                        "options": [
                            {"value": "scheduled", "label": "Scheduled"},
                            {"value": "instant", "label": "Instant"},
                            {"value": "recurring", "label": "Recurring"},
                        ],
                        "defaultValue": "scheduled",
                    }
                ],
                "outputs_schema": [
                    {"id": "meetings", "label": "Meetings List", "type": "array"},
                    {"id": "meeting_count", "label": "Meeting Count", "type": "number"},
                ],
                "handler_function": "_handle_zoom_trigger",
            },
            # ========== COMMUNICATION SERVICES ==========
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
            {
                "id": "slack_channel_created",
                "name": "Slack - Channel Created",
                "service": "slack",
                "description": "Trigger when new channels are created",
                "icon": "S",
                "color": "#4A154B",
                "fields_schema": [
                    {
                        "id": "channelType",
                        "label": "Channel Type",
                        "type": "select",
                        "options": [
                            {"value": "public", "label": "Public"},
                            {"value": "private", "label": "Private"},
                            {"value": "all", "label": "All"},
                        ],
                        "defaultValue": "all",
                    }
                ],
                "outputs_schema": [
                    {"id": "channels", "label": "Channels List", "type": "array"},
                    {"id": "channel_count", "label": "Channel Count", "type": "number"},
                ],
                "handler_function": "_handle_slack_trigger",
            },
            {
                "id": "slack_user_joined",
                "name": "Slack - User Joined Channel",
                "service": "slack",
                "description": "Trigger when users join channels",
                "icon": "S",
                "color": "#4A154B",
                "fields_schema": [
                    {
                        "id": "channelId",
                        "label": "Channel ID",
                        "type": "text",
                        "required": True,
                    }
                ],
                "outputs_schema": [
                    {"id": "users", "label": "Users List", "type": "array"},
                    {"id": "user_count", "label": "User Count", "type": "number"},
                ],
                "handler_function": "_handle_slack_trigger",
            },
            {
                "id": "slack_message_reaction",
                "name": "Slack - Message Reaction",
                "service": "slack",
                "description": "Trigger when messages receive reactions",
                "icon": "S",
                "color": "#4A154B",
                "fields_schema": [
                    {
                        "id": "emoji",
                        "label": "Emoji Filter",
                        "type": "text",
                        "placeholder": "👍, ❤️, 🚀",
                    }
                ],
                "outputs_schema": [
                    {"id": "reactions", "label": "Reactions List", "type": "array"},
                    {
                        "id": "reaction_count",
                        "label": "Reaction Count",
                        "type": "number",
                    },
                ],
                "handler_function": "_handle_slack_trigger",
            },
            # Microsoft Teams Triggers
            {
                "id": "teams_new_message",
                "name": "Microsoft Teams - New Message",
                "service": "microsoft_teams",
                "description": "Trigger when new messages arrive in Teams channels",
                "icon": "T",
                "color": "#6264A7",
                "fields_schema": [
                    {
                        "id": "teamId",
                        "label": "Team ID",
                        "type": "text",
                        "required": True,
                    }
                ],
                "outputs_schema": [
                    {"id": "messages", "label": "Messages List", "type": "array"},
                    {"id": "message_count", "label": "Message Count", "type": "number"},
                ],
                "handler_function": "_handle_teams_trigger",
            },
            {
                "id": "teams_meeting_created",
                "name": "Microsoft Teams - Meeting Created",
                "service": "microsoft_teams",
                "description": "Trigger when new Teams meetings are scheduled",
                "icon": "T",
                "color": "#6264A7",
                "fields_schema": [
                    {
                        "id": "meetingType",
                        "label": "Meeting Type",
                        "type": "select",
                        "options": [
                            {"value": "scheduled", "label": "Scheduled"},
                            {"value": "channel", "label": "Channel Meeting"},
                        ],
                        "defaultValue": "scheduled",
                    }
                ],
                "outputs_schema": [
                    {"id": "meetings", "label": "Meetings List", "type": "array"},
                    {"id": "meeting_count", "label": "Meeting Count", "type": "number"},
                ],
                "handler_function": "_handle_teams_trigger",
            },
            # ========== TASK MANAGEMENT SERVICES ==========
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
                ],
                "outputs_schema": [
                    {"id": "pages", "label": "Pages List", "type": "array"},
                    {"id": "page_count", "label": "Page Count", "type": "number"},
                    {"id": "latest_page", "label": "Latest Page", "type": "object"},
                ],
                "handler_function": "_handle_notion_trigger",
            },
            {
                "id": "notion_database_updated",
                "name": "Notion - Database Updated",
                "service": "notion",
                "description": "Trigger when databases are modified",
                "icon": "N",
                "color": "#000000",
                "fields_schema": [
                    {
                        "id": "databaseId",
                        "label": "Database ID",
                        "type": "text",
                        "required": True,
                    }
                ],
                "outputs_schema": [
                    {"id": "changes", "label": "Changes List", "type": "array"},
                    {"id": "change_count", "label": "Change Count", "type": "number"},
                ],
                "handler_function": "_handle_notion_trigger",
            },
            {
                "id": "notion_page_updated",
                "name": "Notion - Page Updated",
                "service": "notion",
                "description": "Trigger when pages are updated in specified databases",
                "icon": "N",
                "color": "#000000",
                "fields_schema": [
                    {
                        "id": "databaseId",
                        "label": "Database ID",
                        "type": "text",
                        "required": True,
                    }
                ],
                "outputs_schema": [
                    {"id": "pages", "label": "Pages List", "type": "array"},
                    {"id": "page_count", "label": "Page Count", "type": "number"},
                ],
                "handler_function": "_handle_notion_trigger",
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
            {
                "id": "trello_card_due",
                "name": "Trello - Card Due Date",
                "service": "trello",
                "description": "Trigger when cards approach their due dates",
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
                        "id": "hoursBefore",
                        "label": "Hours Before Due",
                        "type": "number",
                        "defaultValue": 24,
                    },
                ],
                "outputs_schema": [
                    {"id": "cards", "label": "Cards List", "type": "array"},
                    {"id": "card_count", "label": "Card Count", "type": "number"},
                ],
                "handler_function": "_handle_trello_trigger",
            },
            {
                "id": "trello_card_moved",
                "name": "Trello - Card Moved",
                "service": "trello",
                "description": "Trigger when cards are moved between lists",
                "icon": "T",
                "color": "#0079BF",
                "fields_schema": [
                    {
                        "id": "boardId",
                        "label": "Board ID",
                        "type": "text",
                        "required": True,
                    }
                ],
                "outputs_schema": [
                    {"id": "cards", "label": "Cards List", "type": "array"},
                    {"id": "card_count", "label": "Card Count", "type": "number"},
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
            {
                "id": "asana_task_due",
                "name": "Asana - Task Due Date",
                "service": "asana",
                "description": "Trigger when tasks approach their due dates",
                "icon": "A",
                "color": "#273347",
                "fields_schema": [
                    {
                        "id": "projectId",
                        "label": "Project ID",
                        "type": "text",
                    },
                    {
                        "id": "hoursBefore",
                        "label": "Hours Before Due",
                        "type": "number",
                        "defaultValue": 24,
                    },
                ],
                "outputs_schema": [
                    {"id": "tasks", "label": "Tasks List", "type": "array"},
                    {"id": "task_count", "label": "Task Count", "type": "number"},
                ],
                "handler_function": "_handle_asana_trigger",
            },
            {
                "id": "asana_task_completed",
                "name": "Asana - Task Completed",
                "service": "asana",
                "description": "Trigger when tasks are marked as completed",
                "icon": "A",
                "color": "#273347",
                "fields_schema": [
                    {
                        "id": "projectId",
                        "label": "Project ID",
                        "type": "text",
                    }
                ],
                "outputs_schema": [
                    {"id": "tasks", "label": "Tasks List", "type": "array"},
                    {"id": "task_count", "label": "Task Count", "type": "number"},
                ],
                "handler_function": "_handle_asana_trigger",
            },
            # Jira Triggers
            {
                "id": "jira_new_issue",
                "name": "Jira - New Issue",
                "service": "jira",
                "description": "Trigger when new issues are created in projects",
                "icon": "J",
                "color": "#0052CC",
                "fields_schema": [
                    {
                        "id": "projectKey",
                        "label": "Project Key",
                        "type": "text",
                        "required": True,
                    },
                    {
                        "id": "issueType",
                        "label": "Issue Type",
                        "type": "select",
                        "options": [
                            {"value": "bug", "label": "Bug"},
                            {"value": "story", "label": "Story"},
                            {"value": "task", "label": "Task"},
                            {"value": "epic", "label": "Epic"},
                        ],
                        "defaultValue": "bug",
                    },
                ],
                "outputs_schema": [
                    {"id": "issues", "label": "Issues List", "type": "array"},
                    {"id": "issue_count", "label": "Issue Count", "type": "number"},
                    {"id": "latest_issue", "label": "Latest Issue", "type": "object"},
                ],
                "handler_function": "_handle_jira_trigger",
            },
            {
                "id": "jira_issue_updated",
                "name": "Jira - Issue Updated",
                "service": "jira",
                "description": "Trigger when issues are updated",
                "icon": "J",
                "color": "#0052CC",
                "fields_schema": [
                    {
                        "id": "projectKey",
                        "label": "Project Key",
                        "type": "text",
                        "required": True,
                    },
                    {
                        "id": "status",
                        "label": "Status Filter",
                        "type": "text",
                        "placeholder": "In Progress, Done, To Do",
                    },
                ],
                "outputs_schema": [
                    {"id": "issues", "label": "Issues List", "type": "array"},
                    {"id": "issue_count", "label": "Issue Count", "type": "number"},
                ],
                "handler_function": "_handle_jira_trigger",
            },
            {
                "id": "jira_comment_added",
                "name": "Jira - Comment Added",
                "service": "jira",
                "description": "Trigger when comments are added to issues",
                "icon": "J",
                "color": "#0052CC",
                "fields_schema": [
                    {
                        "id": "projectKey",
                        "label": "Project Key",
                        "type": "text",
                    }
                ],
                "outputs_schema": [
                    {"id": "comments", "label": "Comments List", "type": "array"},
                    {"id": "comment_count", "label": "Comment Count", "type": "number"},
                ],
                "handler_function": "_handle_jira_trigger",
            },
            # ========== FILE STORAGE SERVICES ==========
            # Google Drive Triggers
            {
                "id": "google_drive_file_created",
                "name": "Google Drive - File Created",
                "service": "google_drive",
                "description": "Trigger when new files are created in Google Drive",
                "icon": "G",
                "color": "#4285F4",
                "fields_schema": [
                    {
                        "id": "folderId",
                        "label": "Folder ID",
                        "type": "text",
                        "placeholder": "Folder ID or path",
                    },
                    {
                        "id": "fileType",
                        "label": "File Type",
                        "type": "select",
                        "options": [
                            {"value": "all", "label": "All Files"},
                            {"value": "document", "label": "Documents"},
                            {"value": "spreadsheet", "label": "Spreadsheets"},
                            {"value": "presentation", "label": "Presentations"},
                        ],
                        "defaultValue": "all",
                    },
                ],
                "outputs_schema": [
                    {"id": "files", "label": "Files List", "type": "array"},
                    {"id": "file_count", "label": "File Count", "type": "number"},
                    {"id": "latest_file", "label": "Latest File", "type": "object"},
                ],
                "handler_function": "_handle_google_drive_trigger",
            },
            {
                "id": "google_drive_file_modified",
                "name": "Google Drive - File Modified",
                "service": "google_drive",
                "description": "Trigger when files are modified in Google Drive",
                "icon": "G",
                "color": "#4285F4",
                "fields_schema": [
                    {
                        "id": "folderId",
                        "label": "Folder ID",
                        "type": "text",
                    }
                ],
                "outputs_schema": [
                    {"id": "files", "label": "Files List", "type": "array"},
                    {"id": "file_count", "label": "File Count", "type": "number"},
                ],
                "handler_function": "_handle_google_drive_trigger",
            },
            # Dropbox Triggers
            {
                "id": "dropbox_file_created",
                "name": "Dropbox - File Created",
                "service": "dropbox",
                "description": "Trigger when new files are created in Dropbox",
                "icon": "D",
                "color": "#0061FF",
                "fields_schema": [
                    {
                        "id": "folderPath",
                        "label": "Folder Path",
                        "type": "text",
                        "placeholder": "/Documents/Projects",
                    }
                ],
                "outputs_schema": [
                    {"id": "files", "label": "Files List", "type": "array"},
                    {"id": "file_count", "label": "File Count", "type": "number"},
                ],
                "handler_function": "_handle_dropbox_trigger",
            },
            {
                "id": "dropbox_file_shared",
                "name": "Dropbox - File Shared",
                "service": "dropbox",
                "description": "Trigger when files are shared in Dropbox",
                "icon": "D",
                "color": "#0061FF",
                "fields_schema": [
                    {
                        "id": "folderPath",
                        "label": "Folder Path",
                        "type": "text",
                    }
                ],
                "outputs_schema": [
                    {"id": "files", "label": "Files List", "type": "array"},
                    {"id": "file_count", "label": "File Count", "type": "number"},
                ],
                "handler_function": "_handle_dropbox_trigger",
            },
            # OneDrive Triggers
            {
                "id": "onedrive_file_created",
                "name": "OneDrive - File Created",
                "service": "onedrive",
                "description": "Trigger when new files are created in OneDrive",
                "icon": "O",
                "color": "#0078D4",
                "fields_schema": [
                    {
                        "id": "folderPath",
                        "label": "Folder Path",
                        "type": "text",
                        "placeholder": "/Documents",
                    }
                ],
                "outputs_schema": [
                    {"id": "files", "label": "Files List", "type": "array"},
                    {"id": "file_count", "label": "File Count", "type": "number"},
                ],
                "handler_function": "_handle_onedrive_trigger",
            },
            # Box Triggers
            {
                "id": "box_file_uploaded",
                "name": "Box - File Uploaded",
                "service": "box",
                "description": "Trigger when files are uploaded to Box",
                "icon": "B",
                "color": "#0061D5",
                "fields_schema": [
                    {
                        "id": "folderId",
                        "label": "Folder ID",
                        "type": "text",
                    }
                ],
                "outputs_schema": [
                    {"id": "files", "label": "Files List", "type": "array"},
                    {"id": "file_count", "label": "File Count", "type": "number"},
                ],
                "handler_function": "_handle_box_trigger",
            },
            # ========== FINANCE SERVICES ==========
            # Plaid Triggers
            {
                "id": "plaid_new_transaction",
                "name": "Plaid - New Transaction",
                "service": "plaid",
                "description": "Trigger when new transactions occur in bank accounts",
                "icon": "P",
                "color": "#5ACF9E",
                "fields_schema": [
                    {
                        "id": "accountId",
                        "label": "Account ID",
                        "type": "text",
                    },
                    {
                        "id": "amountThreshold",
                        "label": "Amount Threshold",
                        "type": "number",
                        "placeholder": "100.00",
                    },
                ],
                "outputs_schema": [
                    {
                        "id": "transactions",
                        "label": "Transactions List",
                        "type": "array",
                    },
                    {
                        "id": "transaction_count",
                        "label": "Transaction Count",
                        "type": "number",
                    },
                ],
                "handler_function": "_handle_plaid_trigger",
            },
            {
                "id": "plaid_low_balance",
                "name": "Plaid - Low Balance",
                "service": "plaid",
                "description": "Trigger when account balance falls below threshold",
                "icon": "P",
                "color": "#5ACF9E",
                "fields_schema": [
                    {
                        "id": "accountId",
                        "label": "Account ID",
                        "type": "text",
                    },
                    {
                        "id": "balanceThreshold",
                        "label": "Balance Threshold",
                        "type": "number",
                        "placeholder": "100.00",
                        "required": True,
                    },
                ],
                "outputs_schema": [
                    {"id": "accounts", "label": "Accounts List", "type": "array"},
                    {"id": "account_count", "label": "Account Count", "type": "number"},
                ],
                "handler_function": "_handle_plaid_trigger",
            },
            # QuickBooks Triggers
            {
                "id": "quickbooks_invoice_created",
                "name": "QuickBooks - Invoice Created",
                "service": "quickbooks",
                "description": "Trigger when new invoices are created",
                "icon": "Q",
                "color": "#2CA01C",
                "fields_schema": [
                    {
                        "id": "customerId",
                        "label": "Customer ID",
                        "type": "text",
                    }
                ],
                "outputs_schema": [
                    {"id": "invoices", "label": "Invoices List", "type": "array"},
                    {"id": "invoice_count", "label": "Invoice Count", "type": "number"},
                ],
                "handler_function": "_handle_quickbooks_trigger",
            },
            {
                "id": "quickbooks_payment_received",
                "name": "QuickBooks - Payment Received",
                "service": "quickbooks",
                "description": "Trigger when payments are received",
                "icon": "Q",
                "color": "#2CA01C",
                "fields_schema": [
                    {
                        "id": "amountThreshold",
                        "label": "Amount Threshold",
                        "type": "number",
                        "placeholder": "100.00",
                    }
                ],
                "outputs_schema": [
                    {"id": "payments", "label": "Payments List", "type": "array"},
                    {"id": "payment_count", "label": "Payment Count", "type": "number"},
                ],
                "handler_function": "_handle_quickbooks_trigger",
            },
            # Xero Triggers
            {
                "id": "xero_invoice_created",
                "name": "Xero - Invoice Created",
                "service": "xero",
                "description": "Trigger when new invoices are created in Xero",
                "icon": "X",
                "color": "#13B5EA",
                "fields_schema": [
                    {
                        "id": "contactId",
                        "label": "Contact ID",
                        "type": "text",
                    }
                ],
                "outputs_schema": [
                    {"id": "invoices", "label": "Invoices List", "type": "array"},
                    {"id": "invoice_count", "label": "Invoice Count", "type": "number"},
                ],
                "handler_function": "_handle_xero_trigger",
            },
            # Stripe Triggers
            {
                "id": "stripe_payment_succeeded",
                "name": "Stripe - Payment Succeeded",
                "service": "stripe",
                "description": "Trigger when payments succeed in Stripe",
                "icon": "S",
                "color": "#635BFF",
                "fields_schema": [
                    {
                        "id": "amountThreshold",
                        "label": "Amount Threshold",
                        "type": "number",
                        "placeholder": "100.00",
                    }
                ],
                "outputs_schema": [
                    {"id": "payments", "label": "Payments List", "type": "array"},
                    {"id": "payment_count", "label": "Payment Count", "type": "number"},
                ],
                "handler_function": "_handle_stripe_trigger",
            },
            {
                "id": "stripe_subscription_created",
                "name": "Stripe - Subscription Created",
                "service": "stripe",
                "description": "Trigger when new subscriptions are created",
                "icon": "S",
                "color": "#635BFF",
                "fields_schema": [
                    {
                        "id": "planId",
                        "label": "Plan ID",
                        "type": "text",
                    }
                ],
                "outputs_schema": [
                    {
                        "id": "subscriptions",
                        "label": "Subscriptions List",
                        "type": "array",
                    },
                    {
                        "id": "subscription_count",
                        "label": "Subscription Count",
                        "type": "number",
                    },
                ],
                "handler_function": "_handle_stripe_trigger",
            },
            # ========== CRM & SALES SERVICES ==========
            # Salesforce Triggers
            {
                "id": "salesforce_lead_created",
                "name": "Salesforce - Lead Created",
                "service": "salesforce",
                "description": "Trigger when new leads are created in Salesforce",
                "icon": "SF",
                "color": "#00A1E0",
                "fields_schema": [
                    {
                        "id": "leadSource",
                        "label": "Lead Source",
                        "type": "text",
                        "placeholder": "Web, Referral, Partner",
                    }
                ],
                "outputs_schema": [
                    {"id": "leads", "label": "Leads List", "type": "array"},
                    {"id": "lead_count", "label": "Lead Count", "type": "number"},
                ],
                "handler_function": "_handle_salesforce_trigger",
            },
            {
                "id": "salesforce_opportunity_won",
                "name": "Salesforce - Opportunity Won",
                "service": "salesforce",
                "description": "Trigger when opportunities are marked as won",
                "icon": "SF",
                "color": "#00A1E0",
                "fields_schema": [
                    {
                        "id": "amountThreshold",
                        "label": "Amount Threshold",
                        "type": "number",
                        "placeholder": "1000.00",
                    }
                ],
                "outputs_schema": [
                    {
                        "id": "opportunities",
                        "label": "Opportunities List",
                        "type": "array",
                    },
                    {
                        "id": "opportunity_count",
                        "label": "Opportunity Count",
                        "type": "number",
                    },
                ],
                "handler_function": "_handle_salesforce_trigger",
            },
            # HubSpot Triggers
            {
                "id": "hubspot_contact_created",
                "name": "HubSpot - Contact Created",
                "service": "hubspot",
                "description": "Trigger when new contacts are created in HubSpot",
                "icon": "H",
                "color": "#FF7A59",
                "fields_schema": [
                    {
                        "id": "lifecycleStage",
                        "label": "Lifecycle Stage",
                        "type": "select",
                        "options": [
                            {"value": "subscriber", "label": "Subscriber"},
                            {"value": "lead", "label": "Lead"},
                            {
                                "value": "marketingqualifiedlead",
                                "label": "Marketing Qualified Lead",
                            },
                            {
                                "value": "salesqualifiedlead",
                                "label": "Sales Qualified Lead",
                            },
                            {"value": "opportunity", "label": "Opportunity"},
                            {"value": "customer", "label": "Customer"},
                        ],
                        "defaultValue": "lead",
                    }
                ],
                "outputs_schema": [
                    {"id": "contacts", "label": "Contacts List", "type": "array"},
                    {"id": "contact_count", "label": "Contact Count", "type": "number"},
                ],
                "handler_function": "_handle_hubspot_trigger",
            },
            {
                "id": "hubspot_deal_created",
                "name": "HubSpot - Deal Created",
                "service": "hubspot",
                "description": "Trigger when new deals are created",
                "icon": "H",
                "color": "#FF7A59",
                "fields_schema": [
                    {
                        "id": "pipelineId",
                        "label": "Pipeline ID",
                        "type": "text",
                    }
                ],
                "outputs_schema": [
                    {"id": "deals", "label": "Deals List", "type": "array"},
                    {"id": "deal_count", "label": "Deal Count", "type": "number"},
                ],
                "handler_function": "_handle_hubspot_trigger",
            },
            # ========== SOCIAL MEDIA SERVICES ==========
            # Twitter Triggers
            {
                "id": "twitter_new_tweet",
                "name": "Twitter - New Tweet",
                "service": "twitter",
                "description": "Trigger when new tweets are posted",
                "icon": "T",
                "color": "#1DA1F2",
                "fields_schema": [
                    {
                        "id": "username",
                        "label": "Username",
                        "type": "text",
                        "placeholder": "@username",
                    },
                    {
                        "id": "keywordFilter",
                        "label": "Keyword Filter",
                        "type": "text",
                        "placeholder": "urgent, help, announcement",
                    },
                ],
                "outputs_schema": [
                    {"id": "tweets", "label": "Tweets List", "type": "array"},
                    {"id": "tweet_count", "label": "Tweet Count", "type": "number"},
                ],
                "handler_function": "_handle_twitter_trigger",
            },
            {
                "id": "twitter_mention",
                "name": "Twitter - Mention",
                "service": "twitter",
                "description": "Trigger when your account is mentioned in tweets",
                "icon": "T",
                "color": "#1DA1F2",
                "fields_schema": [
                    {
                        "id": "keywordFilter",
                        "label": "Keyword Filter",
                        "type": "text",
                    }
                ],
                "outputs_schema": [
                    {"id": "mentions", "label": "Mentions List", "type": "array"},
                    {"id": "mention_count", "label": "Mention Count", "type": "number"},
                ],
                "handler_function": "_handle_twitter_trigger",
            },
            # LinkedIn Triggers
            {
                "id": "linkedin_new_post",
                "name": "LinkedIn - New Post",
                "service": "linkedin",
                "description": "Trigger when new posts are published on LinkedIn",
                "icon": "L",
                "color": "#0077B5",
                "fields_schema": [
                    {
                        "id": "companyId",
                        "label": "Company ID",
                        "type": "text",
                    }
                ],
                "outputs_schema": [
                    {"id": "posts", "label": "Posts List", "type": "array"},
                    {"id": "post_count", "label": "Post Count", "type": "number"},
                ],
                "handler_function": "_handle_linkedin_trigger",
            },
            # Instagram Triggers
            {
                "id": "instagram_new_post",
                "name": "Instagram - New Post",
                "service": "instagram",
                "description": "Trigger when new posts are published on Instagram",
                "icon": "I",
                "color": "#E4405F",
                "fields_schema": [
                    {
                        "id": "username",
                        "label": "Username",
                        "type": "text",
                    }
                ],
                "outputs_schema": [
                    {"id": "posts", "label": "Posts List", "type": "array"},
                    {"id": "post_count", "label": "Post Count", "type": "number"},
                ],
                "handler_function": "_handle_instagram_trigger",
            },
            # TikTok Triggers
            {
                "id": "tiktok_new_video",
                "name": "TikTok - New Video",
                "service": "tiktok",
                "description": "Trigger when new videos are posted on TikTok",
                "icon": "TT",
                "color": "#000000",
                "fields_schema": [
                    {
                        "id": "username",
                        "label": "Username",
                        "type": "text",
                    }
                ],
                "outputs_schema": [
                    {"id": "videos", "label": "Videos List", "type": "array"},
                    {"id": "video_count", "label": "Video Count", "type": "number"},
                ],
                "handler_function": "_handle_tiktok_trigger",
            },
            # ========== MARKETING SERVICES ==========
            # Mailchimp Triggers
            {
                "id": "mailchimp_subscriber_added",
                "name": "Mailchimp - Subscriber Added",
                "service": "mailchimp",
                "description": "Trigger when new subscribers are added to lists",
                "icon": "M",
                "color": "#FFE01B",
                "fields_schema": [
                    {
                        "id": "listId",
                        "label": "List ID",
                        "type": "text",
                        "required": True,
                    }
                ],
                "outputs_schema": [
                    {"id": "subscribers", "label": "Subscribers List", "type": "array"},
                    {
                        "id": "subscriber_count",
                        "label": "Subscriber Count",
                        "type": "number",
                    },
                ],
                "handler_function": "_handle_mailchimp_trigger",
            },
            {
                "id": "mailchimp_campaign_sent",
                "name": "Mailchimp - Campaign Sent",
                "service": "mailchimp",
                "description": "Trigger when email campaigns are sent",
                "icon": "M",
                "color": "#FFE01B",
                "fields_schema": [
                    {
                        "id": "campaignType",
                        "label": "Campaign Type",
                        "type": "select",
                        "options": [
                            {"value": "regular", "label": "Regular"},
                            {"value": "plaintext", "label": "Plaintext"},
                            {"value": "absplit", "label": "A/B Split"},
                            {"value": "rss", "label": "RSS"},
                            {"value": "variate", "label": "Variate"},
                        ],
                        "defaultValue": "regular",
                    }
                ],
                "outputs_schema": [
                    {"id": "campaigns", "label": "Campaigns List", "type": "array"},
                    {
                        "id": "campaign_count",
                        "label": "Campaign Count",
                        "type": "number",
                    },
                ],
                "handler_function": "_handle_mailchimp_trigger",
            },
            # Canva Triggers
            {
                "id": "canva_design_created",
                "name": "Canva - Design Created",
                "service": "canva",
                "description": "Trigger when new designs are created in Canva",
                "icon": "C",
                "color": "#00C4CC",
                "fields_schema": [
                    {
                        "id": "templateType",
                        "label": "Template Type",
                        "type": "text",
                        "placeholder": "Social Media, Presentation, Poster",
                    }
                ],
                "outputs_schema": [
                    {"id": "designs", "label": "Designs List", "type": "array"},
                    {"id": "design_count", "label": "Design Count", "type": "number"},
                ],
                "handler_function": "_handle_canva_trigger",
            },
            # Figma Triggers
            {
                "id": "figma_file_updated",
                "name": "Figma - File Updated",
                "service": "figma",
                "description": "Trigger when Figma files are updated",
                "icon": "F",
                "color": "#F24E1E",
                "fields_schema": [
                    {
                        "id": "fileId",
                        "label": "File ID",
                        "type": "text",
                        "required": True,
                    }
                ],
                "outputs_schema": [
                    {"id": "files", "label": "Files List", "type": "array"},
                    {"id": "file_count", "label": "File Count", "type": "number"},
                ],
                "handler_function": "_handle_figma_trigger",
            },
            # ========== HR SERVICES ==========
            # Greenhouse Triggers
            {
                "id": "greenhouse_new_application",
                "name": "Greenhouse - New Application",
                "service": "greenhouse",
                "description": "Trigger when new job applications are submitted",
                "icon": "G",
                "color": "#00A26C",
                "fields_schema": [
                    {
                        "id": "jobId",
                        "label": "Job ID",
                        "type": "text",
                    }
                ],
                "outputs_schema": [
                    {
                        "id": "applications",
                        "label": "Applications List",
                        "type": "array",
                    },
                    {
                        "id": "application_count",
                        "label": "Application Count",
                        "type": "number",
                    },
                ],
                "handler_function": "_handle_greenhouse_trigger",
            },
            # BambooHR Triggers
            {
                "id": "bamboohr_new_employee",
                "name": "BambooHR - New Employee",
                "service": "bamboohr",
                "description": "Trigger when new employees are added to BambooHR",
                "icon": "B",
                "color": "#00A4E4",
                "fields_schema": [
                    {
                        "id": "department",
                        "label": "Department",
                        "type": "text",
                    }
                ],
                "outputs_schema": [
                    {"id": "employees", "label": "Employees List", "type": "array"},
                    {
                        "id": "employee_count",
                        "label": "Employee Count",
                        "type": "number",
                    },
                ],
                "handler_function": "_handle_bamboohr_trigger",
            },
            # ========== E-COMMERCE SERVICES ==========
            # Shopify Triggers
            {
                "id": "shopify_new_order",
                "name": "Shopify - New Order",
                "service": "shopify",
                "description": "Trigger when new orders are placed in Shopify",
                "icon": "S",
                "color": "#7AB55C",
                "fields_schema": [
                    {
                        "id": "amountThreshold",
                        "label": "Amount Threshold",
                        "type": "number",
                        "placeholder": "100.00",
                    }
                ],
                "outputs_schema": [
                    {"id": "orders", "label": "Orders List", "type": "array"},
                    {"id": "order_count", "label": "Order Count", "type": "number"},
                ],
                "handler_function": "_handle_shopify_trigger",
            },
            {
                "id": "shopify_product_low_stock",
                "name": "Shopify - Low Stock",
                "service": "shopify",
                "description": "Trigger when product inventory falls below threshold",
                "icon": "S",
                "color": "#7AB55C",
                "fields_schema": [
                    {
                        "id": "productId",
                        "label": "Product ID",
                        "type": "text",
                    },
                    {
                        "id": "stockThreshold",
                        "label": "Stock Threshold",
                        "type": "number",
                        "defaultValue": 10,
                    },
                ],
                "outputs_schema": [
                    {"id": "products", "label": "Products List", "type": "array"},
                    {"id": "product_count", "label": "Product Count", "type": "number"},
                ],
                "handler_function": "_handle_shopify_trigger",
            },
            # ========== OTHER SERVICES ==========
            # Zapier Triggers
            {
                "id": "zapier_webhook",
                "name": "Zapier - Webhook",
                "service": "zapier",
                "description": "Trigger when Zapier webhooks are received",
                "icon": "Z",
                "color": "#FF4A00",
                "fields_schema": [
                    {
                        "id": "webhookUrl",
                        "label": "Webhook URL",
                        "type": "text",
                        "required": True,
                    }
                ],
                "outputs_schema": [
                    {"id": "webhook_data", "label": "Webhook Data", "type": "object"},
                ],
                "handler_function": "_handle_zapier_trigger",
            },
            # Zoho Triggers
            {
                "id": "zoho_new_lead",
                "name": "Zoho - New Lead",
                "service": "zoho",
                "description": "Trigger when new leads are created in Zoho",
                "icon": "Z",
                "color": "#CC0000",
                "fields_schema": [
                    {
                        "id": "leadSource",
                        "label": "Lead Source",
                        "type": "text",
                    }
                ],
                "outputs_schema": [
                    {"id": "leads", "label": "Leads List", "type": "array"},
                    {"id": "lead_count", "label": "Lead Count", "type": "number"},
                ],
                "handler_function": "_handle_zoho_trigger",
            },
            # DocuSign Triggers
            {
                "id": "docusign_envelope_sent",
                "name": "DocuSign - Envelope Sent",
                "service": "docusign",
                "description": "Trigger when envelopes are sent for signature",
                "icon": "D",
                "color": "#CCCCCC",
                "fields_schema": [
                    {
                        "id": "templateId",
                        "label": "Template ID",
                        "type": "text",
                    }
                ],
                "outputs_schema": [
                    {"id": "envelopes", "label": "Envelopes List", "type": "array"},
                    {
                        "id": "envelope_count",
                        "label": "Envelope Count",
                        "type": "number",
                    },
                ],
                "handler_function": "_handle_docusign_trigger",
            },
            {
                "id": "docusign_envelope_completed",
                "name": "DocuSign - Envelope Completed",
                "service": "docusign",
                "description": "Trigger when envelopes are fully signed",
                "icon": "D",
                "color": "#CCCCCC",
                "fields_schema": [
                    {
                        "id": "templateId",
                        "label": "Template ID",
                        "type": "text",
                    }
                ],
                "outputs_schema": [
                    {"id": "envelopes", "label": "Envelopes List", "type": "array"},
                    {
                        "id": "envelope_count",
                        "label": "Envelope Count",
                        "type": "number",
                    },
                ],
                "handler_function": "_handle_docusign_trigger",
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
                    },
                ],
                "outputs_schema": [
                    {"id": "issues", "label": "Issues List", "type": "array"},
                    {"id": "issue_count", "label": "Issue Count", "type": "number"},
                    {"id": "latest_issue", "label": "Latest Issue", "type": "object"},
                ],
                "handler_function": "_handle_github_trigger",
            },
            {
                "id": "github_new_pull_request",
                "name": "GitHub - New Pull Request",
                "service": "github",
                "description": "Trigger when new pull requests are created",
                "icon": "GH",
                "color": "#181717",
                "fields_schema": [
                    {
                        "id": "repository",
                        "label": "Repository",
                        "type": "text",
                        "required": True,
                    }
                ],
                "outputs_schema": [
                    {
                        "id": "pull_requests",
                        "label": "Pull Requests List",
                        "type": "array",
                    },
                    {"id": "pr_count", "label": "PR Count", "type": "number"},
                ],
                "handler_function": "_handle_github_trigger",
            },
            {
                "id": "github_push",
                "name": "GitHub - Push",
                "service": "github",
                "description": "Trigger when code is pushed to repositories",
                "icon": "GH",
                "color": "#181717",
                "fields_schema": [
                    {
                        "id": "repository",
                        "label": "Repository",
                        "type": "text",
                        "required": True,
                    }
                ],
                "outputs_schema": [
                    {"id": "pushes", "label": "Pushes List", "type": "array"},
                    {"id": "push_count", "label": "Push Count", "type": "number"},
                ],
                "handler_function": "_handle_github_trigger",
            },
            # GitLab Triggers
            {
                "id": "gitlab_new_issue",
                "name": "GitLab - New Issue",
                "service": "gitlab",
                "description": "Trigger when new issues are created in GitLab",
                "icon": "GL",
                "color": "#FC6D26",
                "fields_schema": [
                    {
                        "id": "projectId",
                        "label": "Project ID",
                        "type": "text",
                        "required": True,
                    }
                ],
                "outputs_schema": [
                    {"id": "issues", "label": "Issues List", "type": "array"},
                    {"id": "issue_count", "label": "Issue Count", "type": "number"},
                ],
                "handler_function": "_handle_gitlab_trigger",
            },
            # Manual Triggers
            {
                "id": "manual_trigger",
                "name": "Manual - Start Workflow",
                "service": "atom",
                "description": "Trigger workflow manually from the Atom interface",
                "icon": "A",
                "color": "#3B82F6",
                "fields_schema": [
                    {
                        "id": "triggerName",
                        "label": "Trigger Name",
                        "type": "text",
                        "placeholder": "Daily Report, Weekly Sync, Monthly Review",
                        "required": True,
                    }
                ],
                "outputs_schema": [
                    {"id": "trigger_data", "label": "Trigger Data", "type": "object"},
                ],
                "handler_function": "_handle_manual_trigger",
            },
            {
                "id": "schedule_trigger",
                "name": "Schedule - Cron Job",
                "service": "atom",
                "description": "Trigger workflow on a schedule using cron syntax",
                "icon": "A",
                "color": "#3B82F6",
                "fields_schema": [
                    {
                        "id": "cronExpression",
                        "label": "Cron Expression",
                        "type": "text",
                        "placeholder": "0 9 * * * (9 AM daily)",
                        "required": True,
                    }
                ],
                "outputs_schema": [
                    {"id": "schedule_data", "label": "Schedule Data", "type": "object"},
                ],
                "handler_function": "_handle_schedule_trigger",
            },
        ]
