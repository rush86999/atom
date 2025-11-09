import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CommandType(Enum):
    """Types of natural language commands"""

    SEARCH = "search"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    SCHEDULE = "schedule"
    ANALYZE = "analyze"
    REPORT = "report"
    NOTIFY = "notify"
    UNKNOWN = "unknown"


class PlatformType(Enum):
    """Supported platform types"""

    COMMUNICATION = "communication"
    STORAGE = "storage"
    PRODUCTIVITY = "productivity"
    CRM = "crm"
    FINANCIAL = "financial"
    MARKETING = "marketing"
    ANALYTICS = "analytics"


@dataclass
class CommandIntent:
    """Parsed intent from natural language command"""

    command_type: CommandType
    platforms: List[PlatformType]
    entities: List[str]
    parameters: Dict[str, Any]
    confidence: float
    raw_command: str


@dataclass
class PlatformEntity:
    """Entity mapping across platforms"""

    entity_type: str
    platform_mappings: Dict[str, str]  # platform_name -> entity_id
    attributes: Dict[str, Any]


class NaturalLanguageEngine:
    """AI Natural Language Processing Engine for ATOM Platform"""

    def __init__(self):
        self.platform_patterns = self._initialize_platform_patterns()
        self.command_patterns = self._initialize_command_patterns()
        self.entity_extractors = self._initialize_entity_extractors()

    def _initialize_platform_patterns(self) -> Dict[PlatformType, List[str]]:
        """Initialize platform recognition patterns"""
        return {
            PlatformType.COMMUNICATION: [
                "slack",
                "teams",
                "discord",
                "zoom",
                "whatsapp",
                "telegram",
                "google chat",
                "message",
                "chat",
                "call",
                "meeting",
                "conversation",
            ],
            PlatformType.STORAGE: [
                "google drive",
                "dropbox",
                "box",
                "onedrive",
                "github",
                "file",
                "document",
                "folder",
                "storage",
                "share",
            ],
            PlatformType.PRODUCTIVITY: [
                "asana",
                "notion",
                "linear",
                "monday",
                "trello",
                "jira",
                "gitlab",
                "task",
                "project",
                "issue",
                "board",
                "card",
                "todo",
            ],
            PlatformType.CRM: [
                "salesforce",
                "hubspot",
                "intercom",
                "freshdesk",
                "zendesk",
                "contact",
                "customer",
                "deal",
                "ticket",
                "lead",
                "pipeline",
            ],
            PlatformType.FINANCIAL: [
                "stripe",
                "quickbooks",
                "xero",
                "payment",
                "invoice",
                "customer",
                "transaction",
                "accounting",
            ],
            PlatformType.MARKETING: [
                "mailchimp",
                "hubspot marketing",
                "shopify",
                "campaign",
                "email",
                "audience",
                "product",
                "order",
            ],
            PlatformType.ANALYTICS: [
                "tableau",
                "google analytics",
                "figma",
                "report",
                "dashboard",
                "analytics",
                "data",
                "metric",
            ],
        }

    def _initialize_command_patterns(self) -> Dict[CommandType, List[str]]:
        """Initialize command recognition patterns"""
        return {
            CommandType.SEARCH: [
                r"find.*",
                r"search.*",
                r"look.*for",
                r"show.*me",
                r"get.*",
                r"what.*are.*my",
                r"list.*my",
                r"display.*",
            ],
            CommandType.CREATE: [
                r"create.*",
                r"add.*",
                r"make.*new",
                r"start.*new",
                r"set up.*",
                r"schedule.*meeting",
                r"book.*",
                r"plan.*",
            ],
            CommandType.UPDATE: [
                r"update.*",
                r"edit.*",
                r"change.*",
                r"modify.*",
                r"adjust.*",
                r"move.*",
                r"reschedule.*",
                r"reassign.*",
            ],
            CommandType.DELETE: [
                r"delete.*",
                r"remove.*",
                r"cancel.*",
                r"archive.*",
                r"clear.*",
            ],
            CommandType.SCHEDULE: [
                r"schedule.*",
                r"plan.*meeting",
                r"book.*time",
                r"set.*reminder",
                r"calendar.*",
                r"arrange.*",
            ],
            CommandType.ANALYZE: [
                r"analyze.*",
                r"review.*",
                r"check.*performance",
                r"evaluate.*",
                r"how.*are.*we.*doing",
                r"what.*is.*the.*status",
            ],
            CommandType.REPORT: [
                r"generate.*report",
                r"create.*report",
                r"show.*report",
                r"what.*are.*the.*numbers",
                r"give.*me.*stats",
            ],
            CommandType.NOTIFY: [
                r"notify.*",
                r"alert.*",
                r"tell.*team",
                r"inform.*",
                r"send.*message.*to",
                r"share.*with",
            ],
        }

    def _initialize_entity_extractors(self) -> Dict[str, callable]:
        """Initialize entity extraction functions"""
        return {
            "date": self._extract_dates,
            "time": self._extract_times,
            "person": self._extract_people,
            "project": self._extract_projects,
            "file": self._extract_files,
            "amount": self._extract_amounts,
            "priority": self._extract_priority,
        }

    def parse_command(self, command: str) -> CommandIntent:
        """
        Parse natural language command and extract intent

        Args:
            command: Natural language command from user

        Returns:
            CommandIntent with parsed information
        """
        logger.info(f"Parsing command: {command}")

        # Normalize command
        normalized_command = command.lower().strip()

        # Extract command type
        command_type = self._extract_command_type(normalized_command)

        # Extract platforms
        platforms = self._extract_platforms(normalized_command)

        # Extract entities
        entities = self._extract_entities(normalized_command)

        # Extract parameters
        parameters = self._extract_parameters(normalized_command)

        # Calculate confidence
        confidence = self._calculate_confidence(
            command_type, platforms, entities, normalized_command
        )

        return CommandIntent(
            command_type=command_type,
            platforms=platforms,
            entities=entities,
            parameters=parameters,
            confidence=confidence,
            raw_command=command,
        )

    def _extract_command_type(self, command: str) -> CommandType:
        """Extract the type of command from natural language"""
        for cmd_type, patterns in self.command_patterns.items():
            for pattern in patterns:
                if re.search(pattern, command, re.IGNORECASE):
                    return cmd_type
        return CommandType.UNKNOWN

    def _extract_platforms(self, command: str) -> List[PlatformType]:
        """Extract relevant platforms from command"""
        platforms = []
        for platform_type, keywords in self.platform_patterns.items():
            for keyword in keywords:
                if keyword in command:
                    platforms.append(platform_type)
                    break  # Only add each platform once
        return platforms

    def _extract_entities(self, command: str) -> List[str]:
        """Extract entities from command"""
        entities = []

        # Extract project names (capitalized words that might be projects)
        project_pattern = r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b"
        projects = re.findall(project_pattern, command)
        entities.extend(projects)

        # Extract file names (words with extensions)
        file_pattern = r"\b\w+\.(doc|docx|pdf|txt|xls|xlsx|ppt|pptx|jpg|png)\b"
        files = re.findall(file_pattern, command, re.IGNORECASE)
        entities.extend(files)

        # Extract amounts
        amount_pattern = r"\$\d+(?:\.\d{2})?|\d+\s*(?:dollars|USD)"
        amounts = re.findall(amount_pattern, command, re.IGNORECASE)
        entities.extend(amounts)

        return entities

    def _extract_parameters(self, command: str) -> Dict[str, Any]:
        """Extract parameters from command"""
        parameters = {}

        # Extract dates
        dates = self._extract_dates(command)
        if dates:
            parameters["dates"] = dates

        # Extract times
        times = self._extract_times(command)
        if times:
            parameters["times"] = times

        # Extract people (simplified - in real implementation, use NER)
        people = self._extract_people(command)
        if people:
            parameters["people"] = people

        # Extract priority
        priority = self._extract_priority(command)
        if priority:
            parameters["priority"] = priority

        # Extract amount
        amount = self._extract_amounts(command)
        if amount:
            parameters["amount"] = amount

        return parameters

    def _extract_dates(self, command: str) -> List[str]:
        """Extract dates from command"""
        # Simple date patterns - in production, use proper date parsing
        date_patterns = [
            r"\b\d{1,2}/\d{1,2}/\d{4}\b",  # MM/DD/YYYY
            r"\b\d{4}-\d{1,2}-\d{1,2}\b",  # YYYY-MM-DD
            r"\b(?:today|tomorrow|yesterday)\b",
            r"\b(?:next|last)\s+(?:week|month|year)\b",
            r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        ]

        dates = []
        for pattern in date_patterns:
            dates.extend(re.findall(pattern, command, re.IGNORECASE))
        return dates

    def _extract_times(self, command: str) -> List[str]:
        """Extract times from command"""
        time_patterns = [
            r"\b\d{1,2}:\d{2}\s*(?:am|pm)\b",
            r"\b\d{1,2}\s*(?:am|pm)\b",
            r"\b(?:morning|afternoon|evening|noon|midnight)\b",
        ]

        times = []
        for pattern in time_patterns:
            times.extend(re.findall(pattern, command, re.IGNORECASE))
        return times

    def _extract_people(self, command: str) -> List[str]:
        """Extract people names from command"""
        # Simple pattern - in production, use proper NER
        people_patterns = [
            r"\b(?:team|team members|everyone|all)\b",
            r"\b(?:john|jane|smith|doe)\b",  # Example names - expand in production
        ]

        people = []
        for pattern in people_patterns:
            people.extend(re.findall(pattern, command, re.IGNORECASE))
        return people

    def _extract_priority(self, command: str) -> Optional[str]:
        """Extract priority from command"""
        priority_keywords = {
            "high": ["urgent", "important", "critical", "asap", "high priority"],
            "medium": ["normal", "medium", "standard"],
            "low": ["low", "whenever", "no rush"],
        }

        for priority_level, keywords in priority_keywords.items():
            for keyword in keywords:
                if keyword in command:
                    return priority_level
        return None

    def _extract_projects(self, command: str) -> List[str]:
        """Extract project names from command"""
        # Simple project name extraction - in production, use more sophisticated methods
        project_pattern = r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b"
        projects = re.findall(project_pattern, command)
        return projects

    def _extract_files(self, command: str) -> List[str]:
        """Extract file names from command"""
        file_pattern = r"\b\w+\.(doc|docx|pdf|txt|xls|xlsx|ppt|pptx|jpg|png)\b"
        files = re.findall(file_pattern, command, re.IGNORECASE)
        return files

    def _extract_amounts(self, command: str) -> Optional[float]:
        """Extract monetary amounts from command"""
        amount_pattern = r"\$(\d+(?:\.\d{2})?)"
        matches = re.findall(amount_pattern, command)
        if matches:
            try:
                return float(matches[0])
            except ValueError:
                pass
        return None

    def _calculate_confidence(
        self,
        command_type: CommandType,
        platforms: List[PlatformType],
        entities: List[str],
        command: str,
    ) -> float:
        """Calculate confidence score for the parsed intent"""
        confidence = 0.0

        # Base confidence for command type
        if command_type != CommandType.UNKNOWN:
            confidence += 0.3

        # Confidence for platforms detected
        if platforms:
            confidence += 0.3

        # Confidence for entities detected
        if entities:
            confidence += 0.2

        # Confidence based on command complexity
        word_count = len(command.split())
        if word_count >= 5:  # More complex commands are more likely to be valid
            confidence += 0.2

        return min(confidence, 1.0)  # Cap at 1.0

    def generate_response(self, intent: CommandIntent) -> Dict[str, Any]:
        """Generate response based on parsed intent"""
        response = {
            "success": intent.confidence > 0.5,
            "confidence": intent.confidence,
            "command_type": intent.command_type.value,
            "platforms": [platform.value for platform in intent.platforms],
            "entities": intent.entities,
            "parameters": intent.parameters,
            "suggested_actions": self._generate_suggested_actions(intent),
            "message": self._generate_message(intent),
        }

        return response

    def _generate_suggested_actions(self, intent: CommandIntent) -> List[str]:
        """Generate suggested actions based on intent"""
        actions = []

        if intent.command_type == CommandType.SEARCH:
            actions.append(f"Search across {len(intent.platforms)} platforms")
            if intent.entities:
                actions.append(f"Look for: {', '.join(intent.entities)}")

        elif intent.command_type == CommandType.CREATE:
            actions.append(f"Create new item in relevant platforms")
            if "dates" in intent.parameters:
                actions.append(f"Schedule for: {intent.parameters['dates']}")

        elif intent.command_type == CommandType.SCHEDULE:
            actions.append("Check calendar availability")
            actions.append("Send meeting invitations")

        return actions

    def _generate_message(self, intent: CommandIntent) -> str:
        """Generate human-readable message based on intent"""
        if intent.confidence < 0.3:
            return (
                "I'm not sure what you want me to do. Could you rephrase your request?"
            )

        base_messages = {
            CommandType.SEARCH: "I'll search for that information across your platforms.",
            CommandType.CREATE: "I'll create that for you in the relevant systems.",
            CommandType.UPDATE: "I'll update that information across platforms.",
            CommandType.DELETE: "I'll remove that from the relevant systems.",
            CommandType.SCHEDULE: "I'll schedule that for you.",
            CommandType.ANALYZE: "I'll analyze the data and provide insights.",
            CommandType.REPORT: "I'll generate a report with the requested information.",
            CommandType.NOTIFY: "I'll send notifications to the relevant people.",
            CommandType.UNKNOWN: "I'll try to help with your request.",
        }

        message = base_messages.get(intent.command_type, "I'll help with your request.")

        # Add platform-specific information
        if intent.platforms:
            platform_names = [platform.value for platform in intent.platforms]
            message += f" This involves your {', '.join(platform_names)} platforms."

        return message


# Example usage and testing
if __name__ == "__main__":
    # Initialize the NLP engine
    nlp_engine = NaturalLanguageEngine()

    # Test commands
    test_commands = [
        "Find all overdue tasks in Asana and Jira",
        "Schedule a team meeting for tomorrow at 2pm",
        "Create a new contact in Salesforce for John Doe",
        "Show me the Q3 sales report from HubSpot",
        "What are my upcoming deadlines across all platforms?",
    ]

    print("Testing Natural Language Processing Engine:")
    print("=" * 50)

    for command in test_commands:
        print(f"\nCommand: '{command}'")
        intent = nlp_engine.parse_command(command)
        response = nlp_engine.generate_response(intent)

        print(f"Type: {intent.command_type.value}")
        print(f"Platforms: {[p.value for p in intent.platforms]}")
        print(f"Entities: {intent.entities}")
        print(f"Parameters: {intent.parameters}")
        print(f"Confidence: {intent.confidence:.2f}")
        print(f"Message: {response['message']}")
        print(f"Suggested Actions: {response['suggested_actions']}")
