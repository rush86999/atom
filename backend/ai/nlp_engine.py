"""
AI Natural Language Processing Engine for ATOM Platform
Enhanced with LLM-powered intent parsing via BYOK
Pattern-based fallback for reliability
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
logger = logging.getLogger(__name__)

# ==================== IMPORTS FOR LLM ENHANCEMENT ====================

# BYOK Integration
try:
    from core.byok_endpoints import get_byok_manager
    BYOK_AVAILABLE = True
except ImportError:
    get_byok_manager = None
    BYOK_AVAILABLE = False

# OpenAI for LLM parsing
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI not available for NLU LLM parsing")

# ==================== CONFIGURATION ====================

NLU_LLM_ENABLED = os.getenv("NLU_LLM_ENABLED", "true").lower() == "true"
NLU_LLM_PROVIDER = os.getenv("NLU_LLM_PROVIDER", "openai")
NLU_LLM_MODEL = os.getenv("NLU_LLM_MODEL", "gpt-4o-mini")

# ==================== ENUMS AND DATA CLASSES ====================

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
    TRIGGER = "trigger"
    BUSINESS_HEALTH = "business_health"
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
    llm_parsed: bool = False


@dataclass
class PlatformEntity:
    """Entity mapping across platforms"""
    entity_type: str
    platform_mappings: Dict[str, str]
    attributes: Dict[str, Any]


class NaturalLanguageEngine:
    """
    AI Natural Language Processing Engine for ATOM Platform
    Enhanced with LLM-powered intent parsing via BYOK
    """

    def __init__(self):
        self.platform_patterns = self._initialize_platform_patterns()
        self.command_patterns = self._initialize_command_patterns()
        self.entity_extractors = self._initialize_entity_extractors()
        
        # Initialize LLM client via BYOK
        self._llm_client = None
        self._byok_manager = None
        self._initialize_llm_client()

    def _initialize_llm_client(self):
        """Initialize LLM client using BYOK system"""
        if not NLU_LLM_ENABLED:
            logger.info("NLU LLM parsing disabled via config")
            return
        
        if not OPENAI_AVAILABLE:
            logger.warning("OpenAI not available, falling back to pattern-based parsing")
            return
        
        try:
            # Get API key from BYOK manager
            api_key = None
            base_url = None
            if BYOK_AVAILABLE and get_byok_manager:
                self._byok_manager = get_byok_manager()
                api_key = self._byok_manager.get_api_key(NLU_LLM_PROVIDER)
                provider_config = self._byok_manager.providers.get(NLU_LLM_PROVIDER)
                if provider_config:
                    base_url = provider_config.base_url
            
            if not api_key:
                api_key = os.getenv("OPENAI_API_KEY")
            
            if api_key:
                client_kwargs = {"api_key": api_key}
                if base_url:
                    client_kwargs["base_url"] = base_url
                
                self._llm_client = OpenAI(**client_kwargs)
                logger.info(f"NLU LLM client initialized with BYOK ({NLU_LLM_PROVIDER}) at {base_url or 'default'}")
            else:
                logger.warning(f"No API key available for NLU LLM parsing (Provider: {NLU_LLM_PROVIDER})")
        except Exception as e:
            logger.error(f"Failed to initialize NLU LLM client: {e}")

    def _is_llm_available(self) -> bool:
        """Check if LLM parsing is available"""
        return NLU_LLM_ENABLED and self._llm_client is not None

    # ==================== LLM-POWERED PARSING ====================

    def _llm_parse_command(self, command: str) -> Optional[CommandIntent]:
        """Parse command using LLM for high-quality intent extraction"""
        
        prompt = f"""Analyze this natural language command and extract the user's intent.

Command: "{command}"

Respond with valid JSON only:
{{
  "command_type": "search|create|update|delete|schedule|analyze|report|notify|trigger|business_health|unknown",
  "platforms": ["communication|storage|productivity|crm|financial|marketing|analytics"],
  "entities": ["extracted entity names like project names, people, files"],
  "parameters": {{
    "dates": ["any dates mentioned"],
    "times": ["any times mentioned"],
    "people": ["people names"],
    "priority": "high|medium|low|null"
  }},
  "confidence": 0.0-1.0
}}

Guidelines:
- command_type: The primary action the user wants to perform
- platforms: Which platform categories are relevant (can be empty if general)
- entities: Specific named things mentioned (projects, files, people)
- parameters: Additional details like dates, times, priority
- confidence: How confident you are in this interpretation (0.0-1.0)"""

        try:
            response = self._llm_client.chat.completions.create(
                model=NLU_LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert NLU parser for a productivity platform. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            content = response.choices[0].message.content.strip()
            # Handle markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            
            data = json.loads(content)
            
            # Parse command type
            cmd_type_str = data.get("command_type", "unknown").lower()
            try:
                command_type = CommandType(cmd_type_str)
            except ValueError:
                command_type = CommandType.UNKNOWN
            
            # Parse platforms
            platforms = []
            for p_str in data.get("platforms", []):
                try:
                    platforms.append(PlatformType(p_str.lower()))
                except ValueError:
                    pass
            
            # Build intent
            intent = CommandIntent(
                command_type=command_type,
                platforms=platforms,
                entities=data.get("entities", []),
                parameters=data.get("parameters", {}),
                confidence=min(1.0, max(0.0, data.get("confidence", 0.8))),
                raw_command=command,
                llm_parsed=True
            )
            
            logger.info(f"LLM parsed command: type={command_type.value}, confidence={intent.confidence}")
            return intent
            
        except Exception as e:
            logger.warning(f"LLM parsing failed: {e}, falling back to pattern-based")
            return None

    # ==================== MAIN PARSE METHOD ====================

    def parse_command(self, command: str) -> CommandIntent:
        """
        Parse natural language command and extract intent
        Tries LLM first for best quality, falls back to pattern-based
        """
        logger.info(f"Parsing command: {command}")
        
        # Try LLM parsing first
        if self._is_llm_available():
            result = self._llm_parse_command(command)
            if result and result.confidence > 0.3:
                return result
        
        # Fallback to pattern-based parsing
        return self._pattern_parse_command(command)

    def _pattern_parse_command(self, command: str) -> CommandIntent:
        """Pattern-based fallback parsing"""
        normalized_command = command.lower().strip()

        command_type = self._extract_command_type(normalized_command)
        platforms = self._extract_platforms(normalized_command)
        entities = self._extract_entities(normalized_command)
        parameters = self._extract_parameters(normalized_command)
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
            llm_parsed=False
        )

    # ==================== PATTERN INITIALIZATION ====================

    def _initialize_platform_patterns(self) -> Dict[PlatformType, List[str]]:
        """Initialize platform recognition patterns"""
        return {
            PlatformType.COMMUNICATION: [
                "slack", "teams", "discord", "zoom", "whatsapp", "telegram",
                "google chat", "message", "chat", "call", "meeting", "conversation",
            ],
            PlatformType.STORAGE: [
                "google drive", "dropbox", "box", "onedrive", "github",
                "file", "document", "folder", "storage", "share",
            ],
            PlatformType.PRODUCTIVITY: [
                "asana", "notion", "linear", "monday", "trello", "jira", "gitlab",
                "task", "project", "issue", "board", "card", "todo",
            ],
            PlatformType.CRM: [
                "salesforce", "hubspot", "intercom", "freshdesk", "zendesk",
                "contact", "customer", "deal", "ticket", "lead", "pipeline",
            ],
            PlatformType.FINANCIAL: [
                "stripe", "quickbooks", "xero",
                "payment", "invoice", "customer", "transaction", "accounting",
            ],
            PlatformType.MARKETING: [
                "mailchimp", "hubspot marketing", "shopify",
                "campaign", "email", "audience", "product", "order",
            ],
            PlatformType.ANALYTICS: [
                "tableau", "google analytics", "figma",
                "report", "dashboard", "analytics", "data", "metric",
            ],
        }

    def _initialize_command_patterns(self) -> Dict[CommandType, List[str]]:
        """Initialize command recognition patterns"""
        return {
            CommandType.BUSINESS_HEALTH: [
                r"priority", r"priorities", r"what.*should.*i.*do",
                r"what.*to.*do.*today", r"simulate", r"simulation",
                r"impact.*of", r"what.*if.*i",
            ],
            CommandType.SEARCH: [
                r"find.*", r"search.*", r"look.*for", r"show.*me",
                r"get.*", r"what.*are.*my", r"list.*my", r"display.*",
            ],
            CommandType.CREATE: [
                r"create.*", r"add.*", r"make.*new", r"start.*new",
                r"set up.*", r"schedule.*meeting", r"book.*", r"plan.*",
            ],
            CommandType.UPDATE: [
                r"update.*", r"edit.*", r"change.*", r"modify.*",
                r"adjust.*", r"move.*", r"reschedule.*", r"reassign.*",
            ],
            CommandType.DELETE: [
                r"delete.*", r"remove.*", r"cancel.*", r"archive.*", r"clear.*",
            ],
            CommandType.SCHEDULE: [
                r"schedule.*", r"plan.*meeting", r"book.*time",
                r"set.*reminder", r"calendar.*", r"arrange.*",
            ],
            CommandType.ANALYZE: [
                r"analyze.*", r"review.*", r"check.*performance",
                r"evaluate.*", r"how.*are.*we.*doing", r"what.*is.*the.*status",
                r"impact.*of", r"what.*if.*i",
            ],
            CommandType.REPORT: [
                r"generate.*report", r"create.*report", r"show.*report",
                r"what.*are.*the.*numbers", r"give.*me.*stats",
            ],
            CommandType.NOTIFY: [
                r"notify.*", r"alert.*", r"tell.*team",
                r"inform.*", r"send.*message.*to", r"share.*with",
            ],
            CommandType.TRIGGER: [
                r"run.*", r"start.*", r"trigger.*", r"execute.*",
                r"kick.*off", r"launch.*", r"begin.*",
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

    # ==================== PATTERN EXTRACTION METHODS ====================

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
                    break
        return platforms

    def _extract_entities(self, command: str) -> List[str]:
        """Extract entities from command"""
        entities = []

        # Extract project names (capitalized words)
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

        dates = self._extract_dates(command)
        if dates:
            parameters["dates"] = dates

        times = self._extract_times(command)
        if times:
            parameters["times"] = times

        people = self._extract_people(command)
        if people:
            parameters["people"] = people

        priority = self._extract_priority(command)
        if priority:
            parameters["priority"] = priority

        amount = self._extract_amounts(command)
        if amount:
            parameters["amount"] = amount

        return parameters

    def _extract_dates(self, command: str) -> List[str]:
        """Extract dates from command"""
        date_patterns = [
            r"\b\d{1,2}/\d{1,2}/\d{4}\b",
            r"\b\d{4}-\d{1,2}-\d{1,2}\b",
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
        people_patterns = [
            r"\b(?:team|team members|everyone|all)\b",
            r"\b(?:john|jane|smith|doe)\b",
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
        project_pattern = r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b"
        return re.findall(project_pattern, command)

    def _extract_files(self, command: str) -> List[str]:
        """Extract file names from command"""
        file_pattern = r"\b\w+\.(doc|docx|pdf|txt|xls|xlsx|ppt|pptx|jpg|png)\b"
        return re.findall(file_pattern, command, re.IGNORECASE)

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

        if command_type != CommandType.UNKNOWN:
            confidence += 0.3

        if platforms:
            confidence += 0.3

        if entities:
            confidence += 0.2

        word_count = len(command.split())
        if word_count >= 5:
            confidence += 0.2

        return min(confidence, 1.0)

    # ==================== RESPONSE GENERATION ====================

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
            "llm_parsed": intent.llm_parsed,
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
            actions.append("Create new item in relevant platforms")
            if "dates" in intent.parameters:
                actions.append(f"Schedule for: {intent.parameters['dates']}")

        elif intent.command_type == CommandType.SCHEDULE:
            actions.append("Check calendar availability")
            actions.append("Send meeting invitations")

        elif intent.command_type == CommandType.ANALYZE:
            actions.append("Gather data from connected platforms")
            actions.append("Generate insights and recommendations")

        elif intent.command_type == CommandType.REPORT:
            actions.append("Compile data from relevant sources")
            actions.append("Generate visual report")

        return actions

    def _generate_message(self, intent: CommandIntent) -> str:
        """Generate human-readable message based on intent"""
        if intent.confidence < 0.3:
            return "I'm not sure what you want me to do. Could you rephrase your request?"

        base_messages = {
            CommandType.SEARCH: "I'll search for that information across your platforms.",
            CommandType.CREATE: "I'll create that for you in the relevant systems.",
            CommandType.UPDATE: "I'll update that information across platforms.",
            CommandType.DELETE: "I'll remove that from the relevant systems.",
            CommandType.SCHEDULE: "I'll schedule that for you.",
            CommandType.ANALYZE: "I'll analyze the data and provide insights.",
            CommandType.REPORT: "I'll generate a report with the requested information.",
            CommandType.NOTIFY: "I'll send notifications to the relevant people.",
            CommandType.TRIGGER: "I'll execute that action for you.",
            CommandType.BUSINESS_HEALTH: "I'll analyze your business priorities.",
            CommandType.UNKNOWN: "I'll try to help with your request.",
        }

        message = base_messages.get(intent.command_type, "I'll help with your request.")

        if intent.platforms:
            platform_names = [platform.value for platform in intent.platforms]
            message += f" This involves your {', '.join(platform_names)} platforms."

        if intent.llm_parsed:
            message += " (AI-powered parsing)"

        return message


# Example usage and testing
if __name__ == "__main__":
    nlp_engine = NaturalLanguageEngine()

    test_commands = [
        "Find all overdue tasks in Asana and Jira",
        "Schedule a team meeting for tomorrow at 2pm",
        "Create a new contact in Salesforce for John Doe",
        "Show me the Q3 sales report from HubSpot",
        "What are my upcoming deadlines across all platforms?",
        "What should I prioritize today?",
    ]

    print("Testing Enhanced Natural Language Processing Engine:")
    print("=" * 60)
    print(f"LLM Available: {nlp_engine._is_llm_available()}")
    print("=" * 60)

    for command in test_commands:
        print(f"\nCommand: '{command}'")
        intent = nlp_engine.parse_command(command)
        response = nlp_engine.generate_response(intent)

        print(f"  Type: {intent.command_type.value}")
        print(f"  Platforms: {[p.value for p in intent.platforms]}")
        print(f"  Entities: {intent.entities}")
        print(f"  Parameters: {intent.parameters}")
        print(f"  Confidence: {intent.confidence:.2f}")
        print(f"  LLM Parsed: {intent.llm_parsed}")
        print(f"  Message: {response['message']}")
