"""
AI Natural Language Processing Engine for ATOM Platform
Enhanced with LLM-powered intent parsing via BYOK
Pattern-based fallback for reliability
"""

import json
import logging
import os
import re
from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field

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

from core.billing import billing_service
from core.database import get_db

# OpenAI & Instructor for LLM parsing
try:
    import instructor
    from openai import OpenAI, AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI or Instructor not available for NLU LLM parsing")

# Anthropic for fallback
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("Anthropic not available for NLU LLM parsing")

# ==================== CONFIGURATION ====================

NLU_LLM_ENABLED = os.getenv("NLU_LLM_ENABLED", "true").lower() == "true"
NLU_LLM_PROVIDER = os.getenv("NLU_LLM_PROVIDER", "openai")
NLU_LLM_MODEL = os.getenv("NLU_LLM_MODEL", "gpt-4o-mini")

# ==================== ENUMS AND DATA CLASSES ====================

class CommandType(str, Enum):
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
    WORKFLOW_CREATION = "workflow_creation"
    UNKNOWN = "unknown"


class PlatformType(str, Enum):
    """Supported platform types"""
    COMMUNICATION = "communication"
    STORAGE = "storage"
    PRODUCTIVITY = "productivity"
    CRM = "crm"
    FINANCIAL = "financial"
    MARKETING = "marketing"
    ANALYTICS = "analytics"


class CommandIntentResult(BaseModel):
    """
    Structured output for Command Intent.
    Used by Instructor to enforce schema.
    """
    command_type: CommandType = Field(..., description="The primary action the user wants to perform")
    platforms: List[PlatformType] = Field(default_factory=list, description="Relevant platform categories")
    entities: List[str] = Field(default_factory=list, description="Specific named things mentioned (projects, files, people)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Additional details like dates, times, priority")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    reasoning: Optional[str] = Field(None, description="Brief explanation of why this intent was chosen")

@dataclass
class CommandIntent:
    """Internal representation of parsed intent (kept for backward compatibility if needed, but we could switch to just using the Pydantic model)"""
    command_type: CommandType
    platforms: List[PlatformType]
    entities: List[str]
    parameters: Dict[str, Any]
    confidence: float
    raw_command: str
    llm_parsed: bool = False
    reasoning: Optional[str] = None


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
    Uses Instructor for robust structured output
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
        """Initialize LLM client using BYOK system (OpenAI or Anthropic)"""
        if not NLU_LLM_ENABLED:
            logger.info("NLU LLM parsing disabled via config")
            return
        
        self.active_provider = None
        self.api_key = None
        self._llm_client = None

        try:
            if BYOK_AVAILABLE and get_byok_manager:
                self._byok_manager = get_byok_manager()
                
                # Check OpenAI first (preferred for Instructor)
                if OPENAI_AVAILABLE:
                    openai_key = self._byok_manager.get_api_key("openai")
                    # Also check env var if BYOK fails
                    if not openai_key:
                        openai_key = os.getenv("OPENAI_API_KEY")
                        
                    if openai_key:
                        self.active_provider = "openai"
                        self.api_key = openai_key
                        
                        raw_client = AsyncOpenAI(api_key=openai_key)
                        self._llm_client = instructor.from_openai(raw_client)
                        logger.info(f"NLU LLM initialized with OpenAI (Instructor) via BYOK/Env")
                        return

                # Check Anthropic fallback
                if ANTHROPIC_AVAILABLE:
                    anthropic_key = self._byok_manager.get_api_key("anthropic") or self._byok_manager.get_api_key("lux")
                    # Check env var
                    if not anthropic_key:
                        anthropic_key = os.getenv("ANTHROPIC_API_KEY")

                    if anthropic_key:
                        self.active_provider = "anthropic"
                        self.api_key = anthropic_key
                        self._llm_client = anthropic.AsyncAnthropic(api_key=anthropic_key)
                        logger.info(f"NLU LLM initialized with Anthropic (BYOK/Env)")
                        return
            
            logger.warning("No suitable LLM provider found for NLU parsing (OpenAI or Anthropic).")
            
            # Phase 42: Mock Fallback for Testing/Verification
            # If we are in a test environment or explicitly enable mocks
            if os.getenv("ATOM_MOCK_MODE", "false").lower() == "true":
                self.active_provider = "mock"
                self._llm_client = "mock_client"
                logger.warning("NLU initialized with MOCK provider (ATOM_MOCK_MODE=true)")
                
        except Exception as e:
            logger.error(f"Failed to initialize NLU LLM client: {e}")

    def _is_llm_available(self) -> bool:
        """Check if LLM parsing is available"""
        return NLU_LLM_ENABLED and self._llm_client is not None

    # ==================== LLM-POWERED PARSING ====================

    async def _llm_parse_command(self, command: str, tenant_id: str = None, user_id: str = None) -> Optional[CommandIntent]:
        """Parse command using active LLM provider"""
        
        try:
            # Phase 42: Pre-flight budget check
            if tenant_id and self.active_provider != "mock":
                from core.database import SessionLocal
                from core.billing import billing_service
                with SessionLocal() as db:
                    if billing_service.is_budget_exceeded(db, tenant_id):
                        logger.warning(f"Blocking NLU LLM call for tenant {tenant_id} - budget exceeded")
                        return None

            if self.active_provider == "openai" and self._llm_client:
                 return await self._openai_parse_command(command)
                 
            elif self.active_provider == "anthropic" and self._llm_client:
                return await self._anthropic_parse_command(command)
                
            elif self.active_provider == "mock":
                return await self._mock_parse_command(command)
                
            return None
            
        except Exception as e:
            logger.warning(f"LLM parsing failed: {e}, falling back to pattern-based")
            return None
            
    async def _mock_parse_command(self, command: str) -> Optional[CommandIntent]:
        """Mock parsing for verification scripts"""
        # Simulate intelligent parsing based on keywords
        cmd_lower = command.lower()
        intent_type = CommandType.UNKNOWN
        
        if "schedule" in cmd_lower or "meeting" in cmd_lower:
            intent_type = CommandType.SCHEDULING
        elif "list" in cmd_lower and "workflow" in cmd_lower:
             intent_type = CommandType.WORKFLOW_CREATION
        elif "search" in cmd_lower or "find" in cmd_lower:
            intent_type = CommandType.SEARCH_REQUEST
        elif "run" in cmd_lower and "workflow" in cmd_lower:
            intent_type = CommandType.WORKFLOW_CREATION
        elif "strategy" in cmd_lower and "data" in cmd_lower:
            intent_type = CommandType.BUSINESS_HEALTH # Test case specific
            
        return CommandIntent(
            command_type=intent_type,
            platforms=[],
            entities=[],
            parameters={},
            confidence=0.95,
            raw_command=command,
            llm_parsed=True,
            reasoning="Mock parsed"
        )

    async def _openai_parse_command(self, command: str) -> Optional[CommandIntent]:
        """Parse using OpenAI + Instructor (Structured Output)"""
        try:
            response = await self._llm_client.chat.completions.create(
                model=NLU_LLM_MODEL, # Default to gpt-4o-mini
                response_model=CommandIntentResult,
                messages=[
                    {"role": "system", "content": "You are an expert NLU parser for a productivity platform. Analyze the command and extract structured intent."},
                    {"role": "user", "content": f"Command: {command}"}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            intent = CommandIntent(
                command_type=response.command_type,
                platforms=response.platforms,
                entities=response.entities,
                parameters=response.parameters,
                confidence=response.confidence,
                raw_command=command,
                llm_parsed=True,
                reasoning=response.reasoning
            )
            logger.info(f"LLM parsed (OpenAI): {intent.command_type}")
            return intent
        except Exception as e:
            logger.warning(f"OpenAI parsing failed: {e}")
            raise e

    async def _anthropic_parse_command(self, command: str) -> Optional[CommandIntent]:
        """Parse using Anthropic (Manual JSON Extraction)"""
        try:
            prompt = f"""
You are an NLU parser for ATOM. Analyze the user command and return a JSON object with the intent.

Command: "{command}"

Valid Intents (command_type):
- search, create, update, delete, schedule, analyze, report, notify, trigger, business_health, unknown

Valid Platforms:
- communication, storage, productivity, crm, financial, marketing, analytics

Output JSON Format:
{{
    "command_type": "search",
    "platforms": ["communication"],
    "entities": ["entity1"],
    "parameters": {{"key": "value"}},
    "confidence": 0.9,
    "reasoning": "explanation"
}}

Return ONLY JSON. No markdown.
"""
            message = await self._llm_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = message.content[0].text.strip()
            
            # Simple JSON extraction
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "{" not in response_text:
                raise ValueError("No JSON found in response")
                
            data = json.loads(response_text)
            
            # Map string to Enum safely
            try:
                cmd_type = CommandType(data.get("command_type", "unknown"))
            except ValueError:
                cmd_type = CommandType.UNKNOWN
                
            platforms = []
            for p in data.get("platforms", []):
                try:
                    platforms.append(PlatformType(p))
                except ValueError:
                    pass

            intent = CommandIntent(
                command_type=cmd_type,
                platforms=platforms,
                entities=data.get("entities", []),
                parameters=data.get("parameters", {}),
                confidence=float(data.get("confidence", 0.5)),
                raw_command=command,
                llm_parsed=True,
                reasoning=data.get("reasoning")
            )
            logger.info(f"LLM parsed (Anthropic): {intent.command_type}")
            return intent
            
        except Exception as e:
            logger.warning(f"Anthropic parsing failed: {e}")
            raise e

    # ==================== MAIN PARSE METHOD ====================

    async def parse_command(self, command: str, tenant_id: str = None, user_id: str = None) -> CommandIntent:
        """
        Parse natural language command and extract intent
        Tries LLM first for best quality, falls back to pattern-based
        """
        logger.info(f"Parsing command: {command}")
        
        # Try LLM parsing first
        if self._is_llm_available():
            result = await self._llm_parse_command(command, tenant_id=tenant_id, user_id=user_id)
            if result and result.confidence > 0.3:
                return result
        
        # Fallback to pattern-based parsing
        return self._pattern_parse_command(command)

    async def execute_agent_action(self, command: str, user_id: str, tenant_id: str = None) -> Dict[str, Any]:
        """
        Directly execute an action using MCP tools based on user command.
        This bypasses the intent classification and goes straight to tool execution.
        """
        if not self._is_llm_available():
             return {"success": False, "error": "LLM not available for agent execution"}

        try:
            from core.database import SessionLocal
            from core.billing import billing_service
            
            # Phase 42: Pre-flight budget check
            if tenant_id:
                with SessionLocal() as db:
                    if billing_service.is_budget_exceeded(db, tenant_id):
                        return {"success": False, "error": "Budget exceeded. Please upgrade or increase limit."}

            from integrations.mcp_service import mcp_service
            
            # 1. Get available tools
            tools = await mcp_service.get_openai_tools()
            
            # 2. Call LLM with tools
            messages = [
                {"role": "system", "content": "You are a helpful AI agent. Use the available tools to fulfill the user's request. If no tool is relevant, reply with a helpful message."},
                {"role": "user", "content": command}
            ]
            
            # Note: We access the raw async client for native tool calling, bypassing strict response_model
            response = await self._llm_client.client.chat.completions.create(
                model=NLU_LLM_MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            
            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls
            
            if tool_calls:
                results = []
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Execute tool via MCP
                    logger.info(f"Agent executing tool: {function_name} with args: {function_args}")
                    
                    context = {"user_id": user_id, "workspace_id": tenant_id or "default"}
                    result = await mcp_service.call_tool(function_name, function_args, context=context)
                    results.append({"tool": function_name, "result": result})
                
                return {
                    "success": True,
                    "action_type": "tool_execution",
                    "results": results,
                    "message": f"Executed {len(results)} actions."
                }
            else:
                return {
                    "success": True,
                    "action_type": "message",
                    "message": response_message.content
                }

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return {"success": False, "error": str(e)}

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
            "reasoning": intent.reasoning
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
