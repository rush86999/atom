"""
Chat Orchestrator - Central coordinator for all ATOM features through chat interface

This module provides a unified chat interface that connects all ATOM capabilities:
- 33+ platform integrations
- AI-powered NLP, data intelligence, and automation
- Specialized UIs (Search, Communication, Tasks, Workflows, Scheduling)
- Multi-agent coordination
- Cross-platform workflow execution
"""
import asyncio
import time
import json
import logging
import os
import re
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from services.agent_service import agent_service

from core.evidence_grounding import (
    EVIDENCE_GROUNDING_RULE,
    asserts_unverified_confirmation,
)
from core.outbound_identity import (
    identity_rule_block,
    signature_signer_status,
)

logger = logging.getLogger(__name__)


def resolve_user_workspace(user_id: Optional[str], fallback: str = "default") -> str:
    """Map a user id to their workspace — the store integration syncs write
    into (the ingestion routes use get_workspace_id(user)). Turn-time memory
    lookup must land in that SAME workspace or ingested data (Zoho, Shopify,
    Salesforce, …) is invisible to the AI employee's recall."""
    if not user_id:
        return fallback
    try:
        db = SessionLocal()
        try:
            from core.models import User

            user_row = db.query(User).filter(User.id == user_id).first()
            if user_row and user_row.workspace_id:
                return user_row.workspace_id
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"workspace resolution failed for {user_id}: {e}")
    return fallback

# LLM Service Integration
try:
    from core.llm_service import LLMService
    LLM_SERVICE_AVAILABLE = True
except ImportError:
    LLM_SERVICE_AVAILABLE = False

# Legacy Agent Definitions for Chat Mapping
AGENTS = {
    "competitive_intel": {
        "name": "Competitive Intelligence Agent",
        "description": "Tracks competitor pricing and product changes",
        "category": "Market Intelligence"
    },
    "inventory_reconcile": {
        "name": "Inventory Reconciliation Agent",
        "description": "Reconciles inventory counts across systems",
        "category": "Operations"
    },
    "payroll_guardian": {
        "name": "Payroll Guardian Agent",
        "description": "Verifies payroll accuracy and compliance",
        "category": "Finance"
    }
}

from core.workflow_endpoints import load_workflows
from ai.automation_engine import AutomationEngine
from ai.workflow_scheduler import workflow_scheduler
import asyncio
import uuid

# BUG-122/123: Missing imports for automation agent execution and finance/CRM handlers.
# These were referenced but never imported → NameError on every chat automation/finance request.
try:
    from api.agent_routes import execute_agent_task
except Exception:
    execute_agent_task = None
    logger.warning("execute_agent_task not importable — chat automation agent trigger disabled")

try:
    from core.automation_settings import get_automation_settings
except Exception:
    get_automation_settings = None
    logger.warning("get_automation_settings not importable — finance/CRM chat handlers degraded")

# Finance/accounting handler dependencies. These were referenced inside
# _handle_finance_request but never imported — every finance chat request
# crashed with NameError before reaching the accounting services.
try:
    from accounting.assistant import AccountingAssistant
    from accounting.workflows import CollectionAgent
    from accounting.close_agent import CloseChecklistAgent
    from accounting.tax_service import TaxService
    from accounting.fpa_service import FPAService
    from accounting.multi_entity import IntercompanyManager
except Exception:
    AccountingAssistant = None  # type: ignore[assignment,misc]
    CollectionAgent = None  # type: ignore[assignment,misc]
    CloseChecklistAgent = None  # type: ignore[assignment,misc]
    TaxService = None  # type: ignore[assignment,misc]
    FPAService = None  # type: ignore[assignment,misc]
    IntercompanyManager = None  # type: ignore[assignment,misc]
    logger.warning("Accounting service modules not importable — finance chat handlers degraded")

from core.database import SessionLocal

REGULATORY_DISCLAIMER = "\n\n---\n*Disclaimer: ATOM's financial features are powered by AI and intended for strategic guidance. This system is not a licensed CPA or tax advisor. All automated records should be reviewed by a qualified professional before filing.*"


class FeatureType(Enum):
    """Types of ATOM features that can be accessed through chat"""
    SEARCH = "search"
    COMMUNICATION = "communication"
    TASKS = "tasks"
    WORKFLOWS = "workflows"
    SCHEDULING = "scheduling"
    INTEGRATIONS = "integrations"
    AI_ANALYTICS = "ai_analytics"
    AUTOMATION = "automation"
    DOCUMENTS = "documents"
    FINANCE = "finance"
    CRM = "crm"
    SOCIAL_MEDIA = "social_media"
    HR = "hr"
    ECOMMERCE = "ecommerce"
    BUSINESS_HEALTH = "business_health"
    AGENT = "agent"  # Phase 30: Atom Meta-Agent

class PlatformType(Enum):
    """Supported platform integrations"""
    # Communication
    SLACK = "slack"
    TEAMS = "teams"
    GMAIL = "gmail"
    WHATSAPP = "whatsapp"
    OUTLOOK = "outlook"
    ZOOM = "zoom"

    # Task Management
    ASANA = "asana"
    NOTION = "notion"
    TRELLO = "trello"
    LINEAR = "linear"
    JIRA = "jira"

    # File Storage
    GOOGLE_DRIVE = "google_drive"
    ONEDRIVE = "onedrive"
    DROPBOX = "dropbox"
    BOX = "box"

    # Finance
    PLAID = "plaid"
    QUICKBOOKS = "quickbooks"
    XERO = "xero"
    STRIPE = "stripe"

    # CRM & Business
    SALESFORCE = "salesforce"
    HUBSPOT = "hubspot"

    # Social Media
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"

    # Marketing
    MAILCHIMP = "mailchimp"
    CANVA = "canva"
    FIGMA = "figma"

    # HR
    GREENHOUSE = "greenhouse"
    BAMBOOHR = "bamboohr"

    # E-commerce
    SHOPIFY = "shopify"

    # Other
    ZAPIER = "zapier"
    ZOHO = "zoho"
    DOCUSIGN = "docusign"


class ChatIntent(Enum):
    """Chat intent classification"""
    SEARCH_REQUEST = "search_request"
    MESSAGE_SEND = "message_send"
    TASK_MANAGEMENT = "task_management"
    WORKFLOW_CREATION = "workflow_creation"
    SCHEDULING = "scheduling"
    DATA_ANALYSIS = "data_analysis"
    AUTOMATION_TRIGGER = "automation_trigger"
    INTEGRATION_SETUP = "integration_setup"
    STATUS_CHECK = "status_check"
    HELP_REQUEST = "help_request"
    MULTI_STEP_PROCESS = "multi_step_process"
    BUSINESS_HEALTH = "business_health"
    CRM = "crm"
    AGENT_REQUEST = "agent_request"  # Phase 30: Request that needs Atom Meta-Agent




_CONVERSATION_REF_RE = re.compile(
    r"\b(earlier|previously|previous|last time|just now|"
    r"you (found|mentioned|said|showed|gave|told|told me)|"
    r"we (discussed|talked about|found)|"
    r"that (email|lead|one|message|result|answer|person|company)|"
    r"the (one you|same)|again|follow[- ]?up)\b",
    re.IGNORECASE,
)


def _references_conversation(message: str) -> bool:
    """True when the user's message points back at this conversation
    ('the email you found earlier', 'try again') rather than at the world —
    the transcript, not retrieved memory, should then drive the answer."""
    return bool(message) and bool(_CONVERSATION_REF_RE.search(message))


# Approval phrases ("go ahead", "proceed", "yes do it") mean DELIVER the
# announced artifact now — without this, reply models loop on proposing
# instead of producing (observed live 2026-09-01: three consecutive
# "Ready to send once you confirm!" turns on an explicit "go ahead").
_APPROVAL_EXECUTION_RULE = (
    "APPROVAL MEANS EXECUTE: when the user says \"go ahead\", \"proceed\", "
    "\"yes\", \"do it\", or otherwise approves something you proposed or "
    "announced — deliver the COMPLETE artifact in this reply: the full email "
    "draft (To/Subject/Body), the complete text, or the concrete result. "
    "Do NOT ask \"should I proceed?\", do NOT restate that you will do it, "
    "and do NOT request another confirmation — the user's approval was the "
    "confirmation. The concise-response limit does not apply to "
    "user-requested artifacts."
)


# Phrases that indicate the reply DENIES having data/ability while a fresh
# tool result was actually injected — the model-quality wobble class (weak
# models anchor on their own earlier refusals and contradict the context).
_INABILITY_RE = re.compile(
    r"\b(i\s+(?:don't|do not|can't|cannot|can not|won't|will not|am unable|'m unable)"
    r"\s+(?:have|see|find|access|research|browse|check|reach|view)|"
    r"unable\s+to\s+(?:research|access|find|browse|check|view|reach)|"
    r"no\s+(?:access|ability|visibility)\s+to|"
    r"i\s+don't\s+have\s+(?:the\s+)?(?:ability|access|capability|tools?))",
    re.IGNORECASE,
)


def _strip_protocol_tags(text: str, captured: Optional[List[str]] = None) -> str:
    """Strip reasoning/protocol fragments weak models leak into content
    (minimax "</mm:think>", raw tool-call XML) — shared by the streaming
    and non-streaming reply paths.

    When ``captured`` is a list, the inner text of paired ``<think>…</think>``
    blocks is APPENDED to it before stripping: the model's chain-of-thought is
    training/audit signal (feedback flows judge ``thought`` text), not junk to
    silently discard."""
    t = str(text or "").strip()
    if captured is not None:
        for _m in re.finditer(r"<think>(.*?)</think>", t, flags=re.DOTALL):
            _block = (_m.group(1) or "").strip()
            if _block:
                captured.append(_block)
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.DOTALL)
    t = re.sub(r"<tool_call>.*?</tool_call>", "", t, flags=re.DOTALL)
    t = re.sub(r"</?(?:mm:)?think>", "", t)
    t = re.sub(r"\]?<\]?minimax\[>?", "", t)
    return t.strip()


def _reply_claims_inability(text: str) -> bool:
    """True when a reply denies having data/ability — detectable wobble that
    contradicts an injected LIVE TOOL RESULT. Cheap string check, so the
    guard costs nothing on healthy replies."""
    if not text:
        return False
    return bool(_INABILITY_RE.search(text))


def _tool_failure_block(planned: str) -> str:
    """Prompt block injected when a PLANNED live lookup failed or timed out.

    Silently dropping the block (the old behavior) reads to the model as
    "no tool ran, therefore no tool exists": it told the user it had no
    Outlook search tool (live 2026-09-06, right after the same lookup had
    succeeded the turn before). An explicit failure block keeps the reply
    truthful about what happened instead."""
    return (
        f"LIVE TOOL RESULTS ({planned}): the live lookup FAILED (timed out or "
        "errored) — you DID attempt it. Tell the user the live lookup could not "
        "complete right now and suggest trying again in a moment. Do NOT claim "
        "you lack tools or integrations, and do NOT claim the data does not "
        "exist — those are both false."
    )


class ChatOrchestrator:
    """
    Main orchestrator that connects chat interface with all ATOM features
    """

    def __init__(self, tenant_id: str = "default"):
        self.conversation_sessions = {}
        self.feature_handlers = {}
        self.platform_connectors = {}
        self.ai_engines = {}
        self.tenant_id = tenant_id
        # Cancellation registry: session_ids that have been cancelled by the user.
        # Checked between processing steps so a long generation can be halted.
        self._cancelled_sessions: set = set()
        
        # Initialize LLMService (Unified interface replaces direct clients)
        self.llm_service = None
        if LLM_SERVICE_AVAILABLE:
            self.llm_service = LLMService(tenant_id=tenant_id)
            logger.info(f"ChatOrchestrator initialized with LLMService for tenant: {tenant_id}")

        # Initialize session manager for persistence
        try:
            from core.chat_session_manager import get_chat_session_manager
            self.session_manager = get_chat_session_manager()
        except ImportError:
            logger.warning("Chat session manager not available, using in-memory sessions only")
            self.session_manager = None

        # Initialize feature handlers
        self._initialize_feature_handlers()
        self._initialize_platform_connectors()
        self._initialize_ai_engines()
        
        # Load persisted sessions
        self._load_persisted_sessions()

    def get_user_sessions(self, user_id: str, limit: int = 20) -> Dict[str, Any]:
        """
        Get all sessions for a user, delegating to the session manager (DB/File).
        Ported from upstream for session persistence.
        """
        if not self.session_manager:
            # Fallback: return in-memory sessions for this user
            return {
                sid: sess for sid, sess in self.conversation_sessions.items()
                if sess.get("user_id") == user_id
            }
        
        # Fetch from manager (which handles DB/File abstraction)
        sessions_list = self.session_manager.list_user_sessions(user_id, limit)
        
        # Convert list to dict format expected by frontend
        sessions_dict = {}
        for s in sessions_list:
            sessions_dict[s["session_id"]] = {
                "id": s["session_id"],
                "user_id": s["user_id"],
                "title": s.get("title"),
                "created_at": s.get("created_at"),
                "last_updated": s.get("last_active"), 
                "history": s.get("history", []),
                "metadata": s.get("metadata", {})
            }
            
            # Opportunistically cache in memory if missing
            if s["session_id"] not in self.conversation_sessions:
                self.conversation_sessions[s["session_id"]] = sessions_dict[s["session_id"]]
                
        return sessions_dict

    def _load_persisted_sessions(self):
        """Load sessions from disk into memory (Legacy File Support)"""
        if not self.session_manager:
            return
            
        try:
            # NOTE: This only loads from file. DB sessions are loaded lazily via get_user_sessions.
            if hasattr(self.session_manager, '_load_sessions_file'):
                persisted = self.session_manager._load_sessions_file()
                for s in persisted:
                    # Convert flat session structure to orchestrator structure
                    self.conversation_sessions[s["session_id"]] = {
                        "id": s["session_id"],
                        "user_id": s["user_id"],
                        "created_at": s.get("created_at"),
                        "last_updated": s.get("last_active"), 
                        "history": s.get("history", [])
                    }
                logger.info(f"Loaded {len(persisted)} persisted sessions from file.")
        except Exception as e:
            logger.error(f"Failed to load persisted sessions: {e}")

    def _workspace_channels(self) -> list:
        """Channels agent workspace events are broadcast to.

        `workspace:default` is what the chat UI subscribes to; the
        tenant-scoped channel keeps workspace-filtered listeners working.
        """
        channels = ["workspace:default"]
        if self.tenant_id and self.tenant_id != "default":
            channels.append(f"workspace:{self.tenant_id}")
        return channels

    @staticmethod
    def _normalize_step_record(step_record: Dict) -> Dict:
        """Normalize a ReAct step record to the shape the Agent Workspace renders.

        The live emitters disagree on keys (AtomMetaAgent/GenericAgent use
        `output`, the UI reads `observation`), so emit both and always stamp
        execution/session identity for run grouping and session filtering.
        Callers occasionally hand over a bare string/None instead of a dict —
        coerce instead of raising: this runs inside the never-break-the-turn
        emit path, and dict(non-dict) would kill the broadcast entirely.
        """
        if not isinstance(step_record, dict):
            step_record = {"observation": str(step_record)} if step_record else {}
        step = dict(step_record or {})
        observation = step.get("observation") or step.get("output") or ""
        step.setdefault("action_input", "")
        step["observation"] = observation
        if not step.get("timestamp"):
            step["timestamp"] = datetime.now().isoformat()
        return step

    async def _emit_agent_step(
        self,
        session_id: Optional[str],
        agent_id: str,
        execution_id: Optional[str],
        step_record: Dict,
    ):
        """Stream one agent execution step to the workspace UI via WebSockets."""
        try:
            from core.websockets import get_connection_manager
            manager = get_connection_manager()
            step = self._normalize_step_record(step_record)
            step["execution_id"] = execution_id or step.get("execution_id")
            step["session_id"] = session_id
            payload = {
                "step": step,
                "agent_id": agent_id,
                "execution_id": step["execution_id"],
                "session_id": session_id,
            }
            for channel in self._workspace_channels():
                await manager.broadcast_event(channel, "agent_step_update", payload)
        except Exception as e:
            logger.warning(f"Failed to emit agent step: {e}")

    async def _emit_agent_status(
        self,
        session_id: Optional[str],
        agent_id: str,
        execution_id: Optional[str],
        status: str,
    ):
        """Broadcast a run lifecycle event (running/success/failed) to the workspace UI."""
        try:
            from core.websockets import get_connection_manager
            manager = get_connection_manager()
            payload = {
                "status": status,
                "agent_id": agent_id,
                "execution_id": execution_id,
                "session_id": session_id,
            }
            for channel in self._workspace_channels():
                await manager.broadcast_event(channel, "agent_status_change", payload)
        except Exception as e:
            logger.warning(f"Failed to emit agent status: {e}")

    # ------------------------------------------------------------------ #
    # Chat-path execution traces (Agent Workspace "Tasks" tab)
    # ------------------------------------------------------------------ #

    def _start_chat_execution(
        self, session_id: str, agent_id: Optional[str], message: str
    ) -> Optional[str]:
        """Create an AgentExecution row for a chat turn so the workspace
        panel has a run to group steps under — and so the trace survives
        reloads (the trace route joins executions via
        metadata_json.session_id). Never raises; None means no trace."""
        try:
            import uuid as _uuid
            from core.database import get_db_session
            from core.models import AgentExecution

            execution_id = str(_uuid.uuid4())
            with get_db_session() as db:
                db.add(AgentExecution(
                    id=execution_id,
                    agent_id=agent_id,
                    status="running",
                    input_summary=(message or "")[:300],
                    triggered_by="chat",
                    metadata_json={"session_id": session_id, "surface": "chat"},
                ))
            return execution_id
        except Exception as e:
            logger.warning(f"chat execution row skipped: {e}")
            return None

    def _finish_chat_execution(
        self, execution_id: Optional[str], status: str, result_summary: str = ""
    ) -> None:
        if not execution_id:
            return
        try:
            from datetime import datetime as _dt
            from core.database import get_db_session
            from core.models import AgentExecution

            with get_db_session() as db:
                row = db.query(AgentExecution).filter(
                    AgentExecution.id == execution_id
                ).first()
                if row:
                    row.status = status
                    row.completed_at = _dt.utcnow()
                    row.result_summary = result_summary[:500]
        except Exception as e:
            logger.warning(f"chat execution finish skipped: {e}")

    async def _record_chat_step(
        self,
        session_id: Optional[str],
        agent_id: Optional[str],
        execution_id: Optional[str],
        step_number: int,
        step_type: str,
        action: Optional[Dict[str, Any]],
        observation: str,
        thought: Optional[str] = None,
    ) -> None:
        """Persist + broadcast one chat-turn step for the workspace panel.
        Best-effort on both legs: a DB failure still broadcasts, a broadcast
        failure still persists. ``thought`` (the ReAct reasoning OR the
        model's chain-of-thought for this turn) is persisted AND broadcast —
        dropping it left every chat surface's "Reasoning Process" collapsible
        expanding to nothing, and step-feedback training payloads judging an
        empty thought."""
        try:
            from core.models import AgentReasoningStep
            from core.database import get_db_session

            with get_db_session() as db:
                db.add(AgentReasoningStep(
                    execution_id=execution_id,
                    step_number=step_number,
                    step_type=step_type,
                    thought=(thought or "")[:20000] or None,
                    action=action,
                    observation=(observation or "")[:2000],
                ))
        except Exception as e:
            logger.warning(f"chat step persist skipped: {e}")
        await self._emit_agent_step(
            session_id,
            agent_id or "chat",
            execution_id,
            {
                "step_number": step_number,
                "type": step_type,
                "thought": thought or "",
                "action": action,
                "action_input": (action or {}).get("params") or "",
                "observation": observation,
            },
        )

    def _initialize_feature_handlers(self):
        """Initialize handlers for all ATOM features"""
        self.feature_handlers = {
            FeatureType.SEARCH: self._handle_search_request,
            FeatureType.COMMUNICATION: self._handle_communication_request,
            FeatureType.TASKS: self._handle_task_request,
            FeatureType.WORKFLOWS: self._handle_workflow_request,
            FeatureType.SCHEDULING: self._handle_scheduling_request,
            FeatureType.INTEGRATIONS: self._handle_integration_request,
            FeatureType.AI_ANALYTICS: self._handle_ai_analytics_request,
            FeatureType.AUTOMATION: self._handle_automation_request,
            FeatureType.DOCUMENTS: self._handle_document_request,
            FeatureType.FINANCE: self._handle_finance_request,
            FeatureType.CRM: self._handle_crm_request,
            FeatureType.SOCIAL_MEDIA: self._handle_social_media_request,
            FeatureType.HR: self._handle_hr_request,
            FeatureType.ECOMMERCE: self._handle_ecommerce_request,
            FeatureType.BUSINESS_HEALTH: self._handle_business_health_request,
            FeatureType.AGENT: self._handle_agent_request,  # Phase 30: Atom Meta-Agent
        }

    def _initialize_platform_connectors(self):
        """Initialize platform connectors for all integrations"""
        # This would connect to actual platform APIs
        self.platform_connectors = {
            platform: self._create_platform_connector(platform)
            for platform in PlatformType
        }

    def _initialize_ai_engines(self):
        """Initialize AI engines for NLP, data intelligence, and automation"""
        try:
            from ai.nlp_engine import NaturalLanguageEngine
            from ai.data_intelligence import DataIntelligenceEngine
            from ai.automation_engine import AutomationEngine

            self.ai_engines = {
                "nlp": NaturalLanguageEngine(tenant_id=self.tenant_id),
                "data_intelligence": DataIntelligenceEngine(),
                "automation": AutomationEngine(),
            }
        except ImportError as e:
            logger.warning(f"AI engines not available: {e}")
            self.ai_engines = {}

    def _create_platform_connector(self, platform: PlatformType):
        """Create a mock platform connector (would connect to real APIs in production)"""
        return {
            "connected": True,
            "capabilities": ["search", "create", "update", "delete"],
            "metadata": {"platform": platform.value}
        }

    async def process_chat_message(
        self,
        user_id: str,
        message: str,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        routing_overrides: Optional[Dict[str, str]] = None,
        images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Process a chat message and coordinate across all ATOM features.

        Args:
            routing_overrides: Optional per-request routing overrides (parsed
                from x-atom-* headers). May contain ``model``, ``tier``,
                ``intent`` keys. Threaded through to the LLM call.
        """
        try:
            # Create or get session
            session_id = session_id or str(uuid.uuid4())
            _execution_id: Optional[str] = None  # chat-trace run (set below)
            session = self._get_or_create_session(user_id, session_id, context)

            # Auto-title from the first user turn — untitled sessions flooded
            # the chat sidebar as "Untitled" clones. Never overrides a title.
            try:
                _current = self.session_manager.get_session(session_id) if self.session_manager else None
                if _current and not (_current.get("title") or "").strip():
                    _title = " ".join((message or "").split())[:60]
                    if _title:
                        self.session_manager.rename_session(session_id, _title)
            except Exception:
                pass  # titling is cosmetic; never block the chat path

            # Build conversation history for context.
            # Session-dedup REMOVED from the read path (Aug 2026): it replaced
            # each prior turn's own text with "[previously sent: <hash>]" in
            # the session records — the write side indexes every turn, so the
            # read side marker-ized the FIRST occurrence too. Follow-up
            # questions ("the lead email you found earlier") then hit a
            # transcript where the found details were an unresolvable
            # placeholder, and the model answered "I don't have access".
            # The [-6:] slice already bounds prompt size; recall beats the
            # marginal token savings. Write-side indexing is harmless and
            # stays, but nothing consumes it on the chat path anymore.
            history = session.get("history", [])[-6:]  # Last 3 turns
            if not history:
                # Belt-and-suspenders for restart survival: if DB hydration
                # found nothing (fresh DB row, or the store failed), fall back
                # to the conversation history the frontend sends with every
                # turn (last 5 messages) instead of answering context-free.
                # Only used for THIS turn's LLM context — not persisted, so it
                # can never duplicate what _update_session already stores.
                conv = (context or {}).get("conversation_history") or []
                rebuilt: List[Dict[str, Any]] = []
                for c in conv[-6:]:
                    if not isinstance(c, dict) or not str(c.get("content") or "").strip():
                        continue
                    if c.get("role") == "user":
                        rebuilt.append({"message": c["content"], "response": {"message": ""}, "intent": {}})
                    else:
                        rebuilt.append({"message": "", "response": {"message": c["content"]}, "intent": {}})
                if rebuilt:
                    history = rebuilt
                    logger.info(
                        f"In-memory history empty — using {len(rebuilt)} frontend-provided "
                        f"message(s) as LLM context for session {session_id}"
                    )
            # 1. Try Qwen AI conversational response first (real AI reply).
            # LKGP: pass the session's last-known-good provider/model as a
            # sticky hint so multi-turn conversations stay on the same model.
            # Chat-path execution trace: one AgentExecution per turn so the
            # Agent Workspace "Tasks" tab shows what this turn actually did
            # (planner decision, tool calls, answer) — and survives reloads.
            _trace_agent_id = (context or {}).get("agent_id") or "chat"
            _execution_id = self._start_chat_execution(
                session_id, (context or {}).get("agent_id"), message
            )
            await self._emit_agent_status(
                session_id, _trace_agent_id, _execution_id, "running"
            )

            # Canvas co-editor turns (/canvas/{id} side panel): the request
            # carries the open canvas in context. Before anything else, give
            # the turn a chance to BE an edit of that canvas — the plain LLM
            # path is canvas-blind and the read-only tool planner can never
            # write, so without this step "remove the sign-off from the
            # draft" produced a generic acknowledgment while the draft sat
            # unchanged (and the intent router side-effect created junk
            # tasks from edit requests). Handled edits return early.
            _canvas_ctx: Optional[Dict[str, Any]] = None
            if context and context.get("canvas_id") and context.get("canvas_content") is not None:
                _canvas_ctx = {
                    "canvas_id": str(context["canvas_id"]),
                    "canvas_type": context.get("canvas_type") or "generic",
                    "title": context.get("canvas_title"),
                    "content": context.get("canvas_content"),
                }
            # Tool planning OVERLAPS the canvas-edit plan: both are
            # structured LLM calls over the same message, neither needs the
            # other's output, and serialized they cost the turn ~4s of dead
            # air before the search even starts (measured 2026-09-01). The
            # task is consumed inside _get_qwen_response and cancelled if an
            # earlier leg (edit/action) already answered.
            _tool_plan_task = None
            try:
                from core.chat_tool_planner import plan_tool_use

                _tool_plan_task = asyncio.create_task(plan_tool_use(
                    message, session.get("history", []) or history,
                    user_id, self.llm_service,
                ))
            except Exception as plan_task_err:
                logger.debug(f"tool plan task not started: {plan_task_err}")
            sticky_hint = None
            try:
                import os as _os
                if _os.getenv("ATOM_LKGP_ENABLED", "true").lower() == "true":
                    _m = session.get("last_known_good_model")
                    _p = session.get("last_known_good_provider")
                    if _m and _p:
                        sticky_hint = (_p, _m)
            except Exception:
                pass

            # Mini-app authoring leg ("build me a mini-app inventory tracker",
            # "publish it", "install it"): runs BEFORE the canvas-edit leg so a
            # ship request on a mini-app canvas isn't mangled into a content
            # edit. The module's keyword gate makes this a no-op (and free)
            # for turns that never say "mini app"; anything else it can't
            # handle returns None and the normal legs proceed. Fault-isolated:
            # never raises into the chat flow.
            _mini_app_response = None
            try:
                from core.chat_mini_app_authoring import try_handle as _mini_app_try_handle
                _mini_app_response = await _mini_app_try_handle(
                    message, session.get("history", []) or history, user_id,
                    self.llm_service, canvas=_canvas_ctx, session_id=session_id,
                )
            except Exception as mini_app_err:
                logger.debug(f"mini-app authoring leg skipped: {mini_app_err}")
            if _mini_app_response:
                self._update_session(
                    session, message, _mini_app_response,
                    {"primary_intent": "mini_app_authoring", "confidence": 0.9},
                )
                await self._emit_agent_status(
                    session_id, _trace_agent_id, _execution_id, "success"
                )
                self._finish_chat_execution(_execution_id, "success", _mini_app_response.get("message", ""))
                if _tool_plan_task is not None and not _tool_plan_task.done():
                    _tool_plan_task.cancel()
                return _mini_app_response
            _turn_t0 = time.monotonic()
            try:
                if _canvas_ctx:
                    _edit_response = await self._try_canvas_edit(
                        message, history, _canvas_ctx, user_id, session_id,
                        _execution_id, (context or {}).get("agent_id"),
                        provenance=(context or {}).get("canvas_provenance"),
                    )
                    logger.info(
                        f"[stage-timing] canvas-edit plan: {time.monotonic() - _turn_t0:.1f}s")
                    if _edit_response:
                        # Persist the turn so follow-ups ("now make it shorter")
                        # have the request in session history, then return —
                        # skipping feature routing means edit requests can no
                        # longer be misfiled into TASKS/AUTOMATION side effects.
                        self._update_session(
                            session, message, _edit_response,
                            {"primary_intent": "canvas_edit", "confidence": 0.9},
                        )
                        await self._emit_agent_status(
                            session_id, _trace_agent_id, _execution_id, "success"
                        )
                        self._finish_chat_execution(_execution_id, "success", _edit_response.get("message", ""))
                        return _edit_response

                    # Not an edit — is it an ACTION on the canvas ("send this")?
                    # Gated by the owner's autonomy policy + hire maturity.
                    _action_response = await self._try_canvas_action(
                        message, history, _canvas_ctx, user_id, session_id,
                        _execution_id, (context or {}).get("agent_id"),
                    )
                    if _action_response:
                        self._update_session(
                            session, message, _action_response,
                            {"primary_intent": "canvas_action", "confidence": 0.9},
                        )
                        await self._emit_agent_status(
                            session_id, _trace_agent_id, _execution_id, "success"
                        )
                        self._finish_chat_execution(_execution_id, "success", _action_response.get("message", ""))
                        return _action_response

                ai_response = await self._get_qwen_response(
                    message, history, routing_overrides,
                    sticky_hint=sticky_hint, user_id=user_id,
                    agent_id=(context or {}).get('agent_id'),
                    planner_history=session.get("history", []),
                    session_id=session_id,
                    execution_id=_execution_id,
                    canvas_context=_canvas_ctx,
                    tool_plan_task=_tool_plan_task,
                    mission_critical=bool((context or {}).get("mission_critical")),
                    canvas_provenance=(context or {}).get("canvas_provenance"),
                    images=images,
                )
            finally:
                if _tool_plan_task is not None:
                    if not _tool_plan_task.done():
                        _tool_plan_task.cancel()
                    elif not _tool_plan_task.cancelled():
                        # retrieve so an unconsumed planner failure doesn't
                        # log "Task exception was never retrieved"
                        _tool_plan_task.exception()

            # Check for cancellation between steps.
            if self._is_cancelled(session_id):
                return {"success": False, "message": "Request cancelled by user.",
                        "session_id": session_id, "cancelled": True}

            # CRM write dispatch: when chatting AS a domain agent and the
            # message is a CRM mutation, execute it directly through the
            # Zoho adapter instead of hoping the LLM does it.
            _agent_id = (context or {}).get("agent_id")
            if _agent_id:
                _crm_result = await self._try_zoho_crm_write(message, context, user_id)
                if _crm_result is not None:
                    return {
                        "success": True,
                        "message": _crm_result,
                        "session_id": session_id,
                    }

            # 2. Analyze intent using AI NLP (for routing)
            intent_analysis = await self._analyze_intent(message, session)

            # Check for cancellation between steps.
            if self._is_cancelled(session_id):
                return {"success": False, "message": "Request cancelled by user.",
                        "session_id": session_id, "cancelled": True}

            # 3. Route to appropriate feature handlers (for data lookups)
            feature_responses = await self._route_to_features(
                message, intent_analysis, session, context
            )

            # 4. If AI gave a real response, use it; otherwise use template
            #    Carry model/provider through so the UI can surface which model
            #    answered and feedback can be tied to a routing decision.
            used_model = None
            used_provider = None
            if ai_response:
                main_message = ai_response["content"]
                used_model = ai_response.get("model")
                used_provider = ai_response.get("provider")
                # LKGP: remember which provider/model served this turn so the
                # next turn in the same session prefers it (sticky routing).
                # Evidence: vLLM #1439, Vercel, LLM Gateway all recommend
                # session stickiness for multi-turn consistency.
                if used_model and used_provider and used_model not in ("template", "auto"):
                    session["last_known_good_model"] = used_model
                    session["last_known_good_provider"] = used_provider
            else:
                main_message = self._generate_main_message(message, intent_analysis, feature_responses)
                # The response came from a template, not an LLM. Label it
                # honestly so the badge renders ("template") rather than
                # silently absent, and feedback records a real model id.
                used_model = "template"
                used_provider = "template"

            # Mentioned-file mini canvas: when the user refers to a specific
            # file and data from it was actually ingested, open a canvas with
            # the data preview for visual reference / editing / discussion.
            try:
                from core.agent_file_context import detect_file_mentions, lookup_file_records

                for _filename in detect_file_mentions(message)[:1]:
                    _lookup = lookup_file_records(
                        resolve_user_workspace(user_id), _filename
                    )
                    if _lookup and _lookup.get("found"):
                        _canvas_id = await self._create_file_mention_canvas(
                            session["id"],
                            user_id,
                            (context or {}).get("agent_id"),
                            _filename,
                            _lookup,
                        )
                        if _canvas_id:
                            main_message += (
                                f"\n\n📋 I've opened a mini canvas — "
                                f"'{_filename} — data preview' — with what I have "
                                "from that file. Open it in the workspace panel "
                                "and we can review or edit it together."
                            )
                    else:
                        main_message += (
                            f"\n\n(I couldn't find ingested data from "
                            f"'{_filename}' — ingest the file first and then "
                            "I can discuss its contents.)"
                        )
            except Exception as _file_err:
                logger.debug(f"file-mention canvas hook failed: {_file_err}")

            # Build combined data from feature responses
            combined_data = {}
            suggested_actions = []
            for feature_type, response in feature_responses.items():
                if response and "data" in response:
                    combined_data[feature_type.value] = response["data"]
                if response and "suggested_actions" in response:
                    suggested_actions.extend(response.get("suggested_actions", []))

            # Budget-failure precedence: if any feature (agent) reported a
            # budget_exceeded error, surface it at the top level — overriding
            # the generic LLM/template message. The user must see their run was
            # halted, with a machine-readable error_code so the frontend renders
            # a distinct budget UI (mirrors the no_llm_provider convention).
            budget_failure = None
            for resp in feature_responses.values():
                if resp and resp.get("error_code") == "budget_exceeded":
                    budget_failure = resp
                    break

            response = {
                "success": not budget_failure,
                "message": budget_failure["message"] if budget_failure else main_message,
                "session_id": session["id"],
                "intent": intent_analysis["primary_intent"].value,
                "confidence": intent_analysis["confidence"],
                "data": combined_data,
                "suggested_actions": suggested_actions[:5],
                "requires_confirmation": False,
                "next_steps": self._generate_next_steps(intent_analysis, feature_responses),
                "timestamp": datetime.now().isoformat(),
                "model": used_model,
                "provider": used_provider,
                "memory_context": (ai_response or {}).get("memory_context") if ai_response else None,
                # The model's chain-of-thought for this turn (what the agent
                # was thinking) — rendered by the "Reasoning Process" drawer
                # and persisted with the assistant message for feedback
                # training (ExchangeExample.reasoning).
                "reasoning": (ai_response or {}).get("reasoning") if ai_response else None,
            }
            if budget_failure:
                response["error_code"] = "budget_exceeded"
                response["failure_reason"] = budget_failure.get("failure_reason")
                response["recovery_url"] = "/settings/billing"

            # Durable fact extraction on the chat path (P0, memory unification
            # plan): fire-and-forget, same extractor the meta agent uses. Chat
            # must not be a memory black hole; a slow write never blocks the
            # user-facing turn.
            if not budget_failure and main_message:
                self._dispatch_turn_fact_extraction(
                    message, main_message, session_id, user_id
                )

            # Update session with new context
            self._update_session(session, message, response, intent_analysis)

            await self._emit_agent_status(
                session_id, _trace_agent_id, _execution_id,
                "success" if response.get("success", True) else "failed",
            )
            self._finish_chat_execution(
                _execution_id,
                "success" if response.get("success", True) else "failed",
                response.get("message", ""),
            )
            return response

        except Exception as e:
            logger.error(f"Error processing chat message: {e}")
            try:
                await self._emit_agent_status(
                    session_id, (context or {}).get("agent_id") or "chat",
                    _execution_id, "failed",
                )
            except Exception:
                pass
            self._finish_chat_execution(_execution_id, "failed", str(e)[:300])
            # BUG-125: Persist the user's message even on error so it's not
            # lost from chat history. Previously _update_session was only
            # called on the success path.
            try:
                error_response = self._generate_error_response(
                    "I encountered an error processing your message. Please try again.", session_id
                )
                self._update_session(session, message, error_response, intent_analysis)
            except Exception:
                pass  # Don't let the persistence attempt mask the original error
            return self._generate_error_response("I encountered an error processing your message. Please try again.", session_id)

    def _dispatch_turn_fact_extraction(
        self, user_request: str, final_answer: str, session_id: Optional[str], user_id: Optional[str]
    ) -> None:
        """Fire-and-forget durable-fact extraction for a completed chat turn."""
        try:
            from core.turn_fact_extractor import get_turn_fact_extractor
            from core.turn_fact_extractor import TURN_FACT_EXTRACTION_ENABLED

            if not TURN_FACT_EXTRACTION_ENABLED:
                return
            extractor = get_turn_fact_extractor(
                workspace_id="default", tenant_id=self.tenant_id
            )
            task = asyncio.create_task(
                extractor.extract_from_turn(
                    user_request=user_request,
                    final_answer=final_answer,
                    session_id=session_id,
                    user_id=user_id,
                )
            )
            task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
        except Exception as e:
            logger.debug(f"turn-fact extraction dispatch failed: {e}")

    def _lookup_agent(self, agent_id: str):
        """Fetch an AgentRegistry row for chat persona building. Best-effort:
        any failure just means the caller falls back to the platform persona."""
        try:
            from core.models import AgentRegistry

            db = SessionLocal()
            try:
                return (
                    db.query(AgentRegistry)
                    .filter(AgentRegistry.id == agent_id)
                    .first()
                )
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"agent lookup failed for {agent_id!r}: {e}")
            return None

    def _is_platform_agent(self, agent) -> bool:
        """Platform-built agents keep the generic ATOM persona — they ARE the
        platform (atom_main, system/Meta category), not domain hires."""
        return (
            (agent.id or "") in {"atom_main"}
            or (agent.category or "").lower() in {"system", "meta"}
            or agent.module_path == "core.atom_meta_agent"
        )

    async def _create_file_mention_canvas(
        self,
        session_id: str,
        user_id: Optional[str],
        agent_id: Optional[str],
        filename: str,
        lookup: Dict[str, Any],
    ) -> Optional[str]:
        """Mini canvas with the mentioned file's ingested data — the visual
        reference/editing surface for training and discussion. Same Canvas +
        CanvasAudit pattern as the chat_draft_to_canvas route, broadcast to
        the session's workspace pane, and expandable to /canvas/{id}."""
        try:
            import uuid as _uuid

            from core.agent_file_context import build_file_canvas_content
            from core.models import Canvas, CanvasAudit
            from core.websockets import manager as ws_manager

            canvas_id = str(_uuid.uuid4())
            created_by = user_id or "system"
            content_text = build_file_canvas_content(filename, lookup)
            db = SessionLocal()
            try:
                canvas = Canvas(
                    id=canvas_id,
                    tenant_id=self.tenant_id or "default",
                    workspace_id=resolve_user_workspace(user_id),
                    created_by=created_by,
                    name=f"{filename} — data preview"[:200],
                    canvas_type="document",
                    content={
                        "type": "doc",
                        "content": content_text,
                    },
                    status="active",
                )
                db.add(canvas)
                db.add(
                    CanvasAudit(
                        canvas_id=canvas_id,
                        tenant_id=canvas.tenant_id,
                        session_id=session_id,
                        agent_id=agent_id,
                        canvas_type="document",
                        action_type="create",
                        user_id=created_by,
                        details_json={"source": "file_mention", "file": filename},
                    )
                )
                db.commit()
            finally:
                db.close()

            # Present it live in the chat's workspace pane (same channel the
            # canvas tool uses), where it can be expanded to the full page.
            # Fan out to BOTH the user channel and the session channel: the
            # chat pane and the expanded /canvas/{id} page subscribe to
            # different channels, and both must see the present event.
            try:
                channels = [f"user:{user_id or 'default'}"]
                if session_id and user_id:
                    channels.append(f"user:{user_id}:session:{session_id}")
                for channel in channels:
                    await ws_manager.broadcast(
                        channel,
                        {
                            "type": "canvas:update",
                            "data": {
                                "action": "present",
                                "component": "document",
                                "canvas_id": canvas_id,
                                "session_id": session_id,
                                "title": f"{filename} — data preview",
                                "data": {
                                    "title": f"{filename} — data preview",
                                    "content": content_text,
                                },
                            },
                        },
                    )
            except Exception as broadcast_err:
                logger.debug(f"file-mention canvas broadcast skipped: {broadcast_err}")

            return canvas_id
        except Exception as e:
            logger.warning(f"file-mention canvas creation failed: {e}")
            return None

    async def _get_qwen_response(
        self,
        message: str,
        history: list,
        routing_overrides: Optional[Dict[str, Any]] = None,
        tool_plan_task: Optional[asyncio.Task] = None,
        sticky_hint: Optional[tuple] = None,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        planner_history: Optional[list] = None,
        session_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        canvas_context: Optional[Dict[str, Any]] = None,
        mission_critical: bool = False,
        canvas_provenance: Optional[Dict[str, Any]] = None,
        images: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get a real conversational AI response using unified LLMService.

        ``images``: user-submitted image data URLs for this turn — routed to
        vision-capable models via the handler's image_payload path (streaming
        is bypassed on image turns: the stream request has no vision
        coordination).

        Returns ``{"content": str, "model": str, "provider": str}`` on success
        (so model identity can be surfaced to the UI and tied to feedback), or
        ``None`` on failure.

        ``sticky_hint`` (when present) is a ``(provider, model)`` tuple from
        the session's last-known-good path — forwarded to the routing layer
        as a boost hint for multi-turn consistency (LKGP).

        ``routing_overrides`` (when present) is unpacked into the
        ``generate_completion`` call: ``model`` overrides auto-routing,
        ``tier``/``intent`` are forwarded as kwargs to BYOKHandler.
        """
        if not self.llm_service:
            return None

        try:
            # Build messages from history
            _connected_line = "unknown"
            try:
                from core.chat_tool_planner import get_connected_services

                _connected = get_connected_services(user_id)
                _connected_line = ", ".join(_connected) if _connected else "none yet"
            except Exception:
                pass
            _TOOL_CAPABILITY = (
                f"Connected integrations: {_connected_line}. When a question "
                "needs fresh data from one of them, the harness runs the "
                "search/read automatically and matched results arrive to you "
                "as system context. Never claim you cannot access a "
                "connected service."
            )
            system_prompt = f"""You are ATOM, an AI-powered business automation assistant. You help users:
- Manage leads and CRM (Zoho, Salesforce, HubSpot)
- Automate workflows and processes
- Schedule meetings and interviews
- Send and draft emails
- Analyze business data and priorities
- Coordinate tasks across Slack, Notion, Google Drive, Gmail

{_TOOL_CAPABILITY}

When users ask to fetch live data (like CRM leads), acknowledge that the integration needs to be connected first and guide them on setup. Be helpful, specific, and actionable. Keep responses concise (2-4 sentences) unless detail is needed.

""" + _APPROVAL_EXECUTION_RULE + "\n\n" + EVIDENCE_GROUNDING_RULE

            # OUTBOUND IDENTITY: resolved per-install data — the agent's
            # OWNER (agents are owned by, and trained by, one user) falling
            # back to the session user, plus the tenant team set from users
            # + installation profile people (role/domain classified).
            # Appended AFTER the persona branch below, which reassigns the
            # prompt — both the platform and hire voices carry the rule.
            _identity_rule = ""
            _outbound_signers: Optional[Dict[str, Any]] = None
            if user_id or agent_id:
                try:
                    _outbound_signers = await asyncio.wait_for(
                        asyncio.to_thread(
                            collect_team_signers, user_id, self.tenant_id, agent_id
                        ),
                        timeout=5,
                    )
                except Exception as id_err:
                    logger.debug(f"outbound identity resolution skipped: {id_err}")
            _primary = (_outbound_signers or {}).get("primary")
            _team = (_outbound_signers or {}).get("team") or []
            # Composer signature only matters for email artifacts; mined for
            # the SIGNING identity (the owner), not the session user.
            if _primary and _primary.get("user_id") and (
                (canvas_context or {}).get("canvas_type") == "email"
            ):
                try:
                    _sig_ident = await asyncio.wait_for(
                        self._sender_identity(_primary["user_id"], "email"),
                        timeout=5,
                    )
                    if (_sig_ident or {}).get("signature"):
                        _primary = {**_primary, "signature": _sig_ident["signature"]}
                except Exception as sig_err:
                    logger.debug(f"composer signature lookup skipped: {sig_err}")
            _identity_rule = identity_rule_block(_primary, _team)

            # Chatting WITH a hire: the employee speaks as themselves, not as
            # the platform. Persona and tier behavior come from the registry,
            # so "chat with my SDR" answers as the SDR within its maturity
            # limits instead of as a generic assistant.
            if agent_id:
                persona_agent = self._lookup_agent(agent_id)
                if persona_agent and not self._is_platform_agent(persona_agent):
                    tier = persona_agent.status or "student"
                    tier_behavior = (
                        "You are still learning: be honest about what you don't know yet, "
                        "propose drafts rather than final actions, and flag anything that "
                        "needs supervisor approval."
                        if tier in ("student", "intern")
                        else "Work autonomously within your declared capabilities."
                    )
                    role_line = (
                        f"Your role: {persona_agent.description}"
                        if persona_agent.description
                        else f"Your role: {persona_agent.category or 'business'} employee."
                    )
                    system_prompt = (
                        f"You are {persona_agent.display_name or persona_agent.name}, "
                        f"a {persona_agent.category or 'business'} employee hired on the "
                        f"ATOM platform. {role_line} "
                        "Always speak in first person as this employee — never as 'Atom' "
                        "or as an AI assistant. "
                        f"Maturity tier: {tier}. {tier_behavior} "
                        f"{_TOOL_CAPABILITY} "
                        "Be helpful, specific, and actionable. Keep responses concise "
                        "(2-4 sentences) unless detail is needed. "
                        + _APPROVAL_EXECUTION_RULE
                        + "\n\n" + EVIDENCE_GROUNDING_RULE
                    )

            if _identity_rule:
                system_prompt += "\n\n" + _identity_rule

            messages = [
                {
                    "role": "system",
                    "content": system_prompt,
                }
            ]

            memory_block = None
            # Unified turn-time memory retrieval (P0, memory unification plan):
            # comms memory + GraphRAG + episodes + turn facts, bounded block.
            # Fault-isolated and flag-gated — never blocks or breaks the turn.
            try:
                from core.memory_context_assembler import (
                    assemble_memory_context,
                    assembly_enabled,
                )

                # Resolve agent identity for role-scoped recall
                _agent_id = agent_id

                if assembly_enabled():
                    # The integral AI-employee contract: memory must be
                    # retrieved from the USER's workspace, the same workspace
                    # integration syncs write into (get_workspace_id in the
                    # ingestion routes). Hardcoding "default" made ingested
                    # Zoho/Shopify/Salesforce/etc. data invisible to the
                    # employee at chat time — "0 relevant entities" despite
                    # synced records (RED→GREEN journey fix).
                    user_workspace = resolve_user_workspace(user_id)

                    logger.info(f"[MEMCTX] agent_id={_agent_id!r}")
                    memory_block = await assemble_memory_context(
                        message=message,
                        workspace_id=user_workspace,
                        tenant_id=self.tenant_id,
                        # the hire's identity → role-aware recall: records
                        # synced FOR this employee surface first
                        agent_id=_agent_id,
                        # mailbox-ownership boundary: comms recall only
                        # surfaces this account's own ingested mail
                        user_id=user_id,
                    )
                    if memory_block:
                        messages.append({"role": "system", "content": memory_block})

            except Exception as e:
                # A silent failure here makes ALL ingested integration data
                # invisible at chat time (no error, empty memory) — warn, don't debug.
                logger.warning(f"memory context assembly skipped: {e}")

            # Canvas co-editor context (non-edit turns): the user is chatting
            # beside an open canvas — "the draft", "the email" refer to it.
            # Without this block the model answered generically about drafts
            # in the abstract while the actual canvas sat in another tab.
            if canvas_context and canvas_context.get("content") is not None:
                try:
                    import json as _json

                    _cc = canvas_context.get("content")
                    _cc_text = _cc if isinstance(_cc, str) else _json.dumps(_cc, default=str)
                    messages.append({"role": "system", "content": (
                        "CANVAS CONTEXT — the user is chatting in a panel beside an "
                        f"open canvas (type: {canvas_context.get('canvas_type') or 'generic'}, "
                        f"id: {canvas_context.get('canvas_id')}). When they refer to "
                        "\"the draft\", \"the email\", \"this canvas\" etc., they mean "
                        "THIS canvas. Its current content is the authoritative and "
                        f"most recent version:\n{_cc_text[:4000]}"
                    )})
                except Exception as canvas_ctx_err:
                    logger.debug(f"canvas context block skipped: {canvas_ctx_err}")

            # Canvas ORIGIN (provenance): the conversation this canvas was
            # created from, hydrated by chat_routes from the create-audit
            # row. The panel session starts empty, so "why was the draft
            # written this way / who wrote this" used to be unanswerable —
            # the model honestly said "I don't know who wrote that language"
            # (observed live 2026-09-02) even though the origin thread sat
            # one DB query away. Background only: origin statements are NOT
            # evidence (see EVIDENCE_GROUNDING_RULE in the system prompt).
            if canvas_provenance and (canvas_provenance.get("messages") or []):
                try:
                    _origin_lines = []
                    for _m in canvas_provenance["messages"][-6:]:
                        if not isinstance(_m, dict) or not str(_m.get("content") or "").strip():
                            continue
                        _role = "User" if _m.get("role") == "user" else "Agent"
                        _origin_lines.append(f"{_role}: {str(_m['content'])[:600]}")
                    if _origin_lines:
                        messages.append({"role": "system", "content": (
                            "CANVAS ORIGIN — this canvas was created from the "
                            "conversation below (before this panel existed). Use it "
                            "to explain the draft's provenance (what was asked, what "
                            "the agent based it on). These statements are background, "
                            "NOT verified evidence — do not treat a claim found here "
                            "as true:\n" + "\n".join(_origin_lines)
                        )})
                except Exception as prov_err:
                    logger.debug(f"canvas provenance block skipped: {prov_err}")

            # Tool planning (LLM-based, ALL connected integrations): a cheap
            # structured-output call reads the conversation and decides
            # whether answering needs fresh data from one of the user's
            # connected services — then the harness executes it read-only.
            # This replaces the earlier Outlook-only regex gates (email-search
            # detector, retry detector, stopword term extraction): the planner
            # understands "find this email in outlook", "try again", "search
            # slack for X", and every other integration, without per-service
            # pattern hacks. The planner seeing the history is what makes
            # retries work — "try again" means re-run the previous action,
            # which an LLM infers naturally.
            # The results block is injected AFTER the transcript (below), not
            # here: weak models anchor on the most recent messages, and the
            # transcript of a long-running session often contains earlier
            # failed attempts — results placed before them lost to recency.
            _tool_block: Optional[str] = None
            _planned: Optional[str] = None
            _step_n = 0

            async def _trace(step_type: str, action: Optional[Dict[str, Any]], observation: str,
                             thought: Optional[str] = None) -> None:
                nonlocal _step_n
                _step_n += 1
                await self._record_chat_step(
                    session_id, agent_id, execution_id,
                    _step_n, step_type, action, observation, thought=thought,
                )

            try:
                from core.chat_tool_planner import execute_tool_plan, plan_tool_use
                from core.hallucination_config import get_verify_panel_mode
                from core.verify_panel import verify_reply

                # Full hydrated history for the planner (not the [-6:] main-
                # model window): in retry-heavy sessions the original request
                # sits several turns back, and user-only lines are tiny.
                # A pre-started plan task means the caller overlapped this
                # plan with the canvas-edit plan — just await it.
                _plan_t0 = time.monotonic()
                if tool_plan_task is not None:
                    _plan = await asyncio.wait_for(tool_plan_task, timeout=25)
                else:
                    _plan = await asyncio.wait_for(
                        plan_tool_use(message, planner_history or history, user_id, self.llm_service),
                        timeout=25,
                    )
                logger.info(
                    f"[stage-timing] tool plan (overlapped={tool_plan_task is not None}): "
                    f"{time.monotonic() - _plan_t0:.1f}s")
                if _plan and _plan.use_tool:
                    _planned = f"{_plan.service}.{_plan.intent}:{(_plan.query or '')[:80]}"
                    await _trace("thought", {"tool": "tool_planner", "params": {"service": _plan.service, "intent": _plan.intent, "query": _plan.query or ""}},
                                 f"Planned live lookup: {_planned}")
                    _exec_t0 = time.monotonic()
                    _tool_block = await asyncio.wait_for(
                        execute_tool_plan(
                            _plan, user_id, self.tenant_id,
                            context={
                                "agent_id": agent_id,
                                "history": (planner_history or history or [])[-6:],
                                "canvas": {
                                    "title": canvas_context.get("title"),
                                    **((canvas_context.get("content") or {})
                                       if isinstance(canvas_context, dict) else {}),
                                } if isinstance(canvas_context, dict) else None,
                            },
                            llm_service=self.llm_service,
                        ),
                        timeout=45,
                    )
                    _first_line = (_tool_block or "").split("\n", 1)[1 if _tool_block and _tool_block.startswith("LIVE TOOL") else 0][:200]
                    await _trace("observation", {"tool": _plan.service, "params": {"query": _plan.query or ""}},
                                 _first_line or "no results")
                    logger.info(
                        f"[stage-timing] tool exec: {time.monotonic() - _exec_t0:.1f}s")
                elif _plan is not None:
                    await _trace("thought", {"tool": "tool_planner", "params": {}},
                                 f"No live lookup needed: {(_plan.reason or 'conversation suffices')[:160]}")
            except Exception as tool_err:
                # !r, not str: a bare asyncio.TimeoutError() stringifies to
                # "" — the old warning printed "tool planning skipped: " and
                # hid the 45s exec timeout entirely (live 2026-09-06).
                logger.warning(f"tool planning skipped: {tool_err!r}")
                if _planned and not _tool_block:
                    _tool_block = _tool_failure_block(_planned)

            # Add conversation history. When fresh tool results exist for
            # this turn, include ONLY the user turns as context: measured
            # (Aug 30), a transcript full of earlier failed attempts anchors
            # weak models into refusing again even with a fresh result
            # injected last — but dropping context ENTIRELY made them emit
            # raw tool-call syntax instead of answering. User turns alone
            # give grounding without the refusal wall. They remain fully in
            # the DB/UI; only this turn's prompt changes.
            if _tool_block:
                for h in history[-3:]:
                    if h.get("message"):
                        messages.append({"role": "user", "content": h["message"]})
            else:
                for h in history:
                    if h.get("message"):
                        messages.append({"role": "user", "content": h["message"]})
                    # Error turns (failed attempts) are skipped: they anchor
                    # weak models into refusals and carry no answer content.
                    if h.get("error"):
                        continue
                    resp_msg = h.get("response", {}).get("message", "")
                    if resp_msg:
                        messages.append({"role": "assistant", "content": resp_msg})

                # Recency precedence: when the user refers to something from
                # THIS conversation ("the email you found earlier"), the
                # transcript is the authoritative source. Without this nudge
                # the model answered "who was in that lead email?" from an
                # older ingested lead in the RELEVANT MEMORY block instead of
                # the record it had just found.
                if history and _references_conversation(message):
                    messages.append({
                        "role": "system",
                        "content": (
                            "PRIORITY: The user is referring to something from THIS "
                            "conversation. Answer from the transcript above — it is the "
                            "authoritative and most recent source. Treat any RELEVANT "
                            "MEMORY block as background only, and use it solely to fill "
                            "gaps the transcript does not already cover."
                        ),
                    })

            # Fresh tool results go LAST — closest to the question they answer.
            # (Earlier failures in the transcript stay where they belong: in
            # the past. The newest data wins.) The block also explicitly
            # overrides stale refusals: long sessions of earlier failed
            # attempts otherwise anchor weak models into repeating "I can't
            # do that" even when a fresh result is in front of them.
            if _tool_block:
                messages.append({"role": "system", "content": (
                    "TOOL EXECUTION RESULT — the harness ran this JUST NOW, "
                    "successfully, on your behalf. Any earlier statement about "
                    "lacking access or tools is OUTDATED: ignore it. Do NOT emit "
                    "tool-call, XML, or protocol syntax, and do not attempt to call "
                    "tools yourself — the harness handles tools. Answer the user's "
                    "current message in plain language using this fresh result:\n"
                    + _tool_block
                )})
                logger.info(f"tool plan executed: {_planned}")

            messages.append({"role": "user", "content": message})

            # Unpack routing overrides. ``model`` overrides the auto default;
            # ``tier``/``intent`` are forwarded as kwargs to the BYOK handler.
            overrides = routing_overrides or {}
            forced_model = overrides.get("model", "auto")
            extra_kwargs: Dict[str, Any] = {}
            if "tier" in overrides:
                extra_kwargs["cognitive_tier"] = overrides["tier"]
            if "intent" in overrides:
                extra_kwargs["intent_override"] = overrides["intent"]
            # LKGP: forward the session's last-known-good (provider, model)
            # as a sticky hint to the routing layer.
            if sticky_hint:
                extra_kwargs["sticky_hint"] = sticky_hint

            # Use LLMService for completion (delegates Qwen/OpenAI/Anthropic routing internally)
            # STREAMING REPLY (ATOM_CHAT_STREAMING, default on): tokens are
            # broadcast over the co-editor's WebSocket as they generate, so
            # time-to-first-content is ~2-5s instead of the full generation
            # (~20s+). Accuracy is unchanged — same routed model, same prompt;
            # the full text is still returned below for persistence, LKGP,
            # and protocol-tag hygiene. ANY failure falls back to the
            # non-streaming completion: streaming is pure UX sugar.
            _streamed: Optional[str] = None
            _turn_reasoning: Optional[str] = None
            if (
                os.getenv("ATOM_CHAT_STREAMING", "true").lower() == "true"
                and user_id and session_id
                # routing_overrides is None on the common path — must not crash
                and not (routing_overrides or {}).get("model")
                # image turns use the non-streaming vision path (image_payload
                # → vision-capable model routing); the stream request has no
                # vision coordination
                and not images
            ):
                try:
                    import time as _time

                    from core.llm.byok_handler import _DEFAULT_COMPLETION_MAX_TOKENS
                    from core.websockets import manager as _ws_manager

                    _prompt_for_cx = " ".join(
                        str(m.get("content") or "") for m in messages
                    )
                    _cx = self.llm_service.handler.analyze_query_complexity(_prompt_for_cx)
                    _s_prov, _s_model = await self.llm_service.handler.get_optimal_provider(_cx)

                    _buf: List[str] = []
                    _t0 = _time.monotonic()
                    # Model chain-of-thought capture: reasoning deltas arrive
                    # on a separate field (delta.reasoning / reasoning_content
                    # / thinking) which the stream loop previously dropped on
                    # the floor. Collected here, persisted + broadcast as the
                    # turn's "thought" step, and returned with the reply so
                    # feedback training captures WHAT the model was thinking.
                    _reasoning_parts: List[str] = []
                    _reasoning_sink: Dict[str, Any] = {"deltas": _reasoning_parts}
                    async for _tok in self.llm_service.stream_completion(
                        messages=messages,
                        model=_s_model,
                        provider_id=_s_prov,
                        temperature=0.7,
                        max_tokens=_DEFAULT_COMPLETION_MAX_TOKENS,
                        reasoning_sink=_reasoning_sink,
                    ):
                        if not _tok:
                            continue
                        _buf.append(_tok)
                        await _ws_manager.broadcast(f"user:{user_id}", {
                            "type": "chat_token",
                            "data": {
                                "session_id": session_id,
                                "delta": _tok,
                            },
                        })
                    _full = "".join(_buf).strip()
                    if _full:
                        _streamed = _strip_protocol_tags(_full, captured=_reasoning_parts)
                        # GROUNDING GUARD: a streamed reply that denies having
                        # data contradicts the LIVE TOOL RESULT injected above
                        # (model-quality wobble, observed live). One grounded
                        # regeneration — the correction replaces the stream.
                        if _tool_block and _reply_claims_inability(_streamed):
                            logger.warning(
                                "streamed reply claims inability despite tool "
                                "results — grounded regeneration")
                            messages.append({"role": "system", "content": (
                                "Your previous reply wrongly claimed you lack data "
                                "or ability. A LIVE TOOL RESULT block IS present "
                                "above — answer the user's current message from it "
                                "now, in plain language, with no capability "
                                "disclaimers."
                            )})
                            _fix = await self.llm_service.generate_completion(
                                messages=messages,
                                model=forced_model,
                                tenant_id=self.tenant_id,
                                **extra_kwargs,
                            )
                            _fixed = _strip_protocol_tags((_fix or {}).get("content"))
                            if _fixed and not _reply_claims_inability(_fixed):
                                _streamed = _fixed
                                _turn_reasoning = (_fix or {}).get("reasoning") or _turn_reasoning
                        # EVIDENCE GUARD: the request asked to confirm/verify
                        # something and the reply ASSERTS it as established
                        # fact (observed live 2026-09-02: "confirm 480V
                        # 3-phase specs" became "the machines are available
                        # in 480V 3-phase configuration"). Conversation is
                        # not evidence — one regeneration offering the
                        # negative or middle path (claim nothing either way).
                        elif asserts_unverified_confirmation(message, _streamed):
                            logger.warning(
                                "streamed reply asserts an unverified "
                                "confirm/verify request as fact — grounded "
                                "regeneration")
                            messages.append({"role": "system", "content": (
                                "Your previous reply stated a claim as fact that "
                                "the request only asked to CONFIRM, and no evidence "
                                "in this context establishes it. Regenerate: keep "
                                "the reply's useful structure, but for that claim "
                                "either (a) say plainly it is not yet verified, or "
                                "(b) make no claim in either direction — word it "
                                "as confirmation in progress (\"We are "
                                "confirming X and will follow up with details\") "
                                "or ask for the missing information (\"Could you "
                                "share the spec sheets so we can confirm?\"). "
                                "Do not assert it as true."
                            )})
                            _fix = await self.llm_service.generate_completion(
                                messages=messages,
                                model=forced_model,
                                tenant_id=self.tenant_id,
                                **extra_kwargs,
                            )
                            _fixed = _strip_protocol_tags((_fix or {}).get("content"))
                            if _fixed and not asserts_unverified_confirmation(message, _fixed):
                                _streamed = _fixed
                                _turn_reasoning = (_fix or {}).get("reasoning") or _turn_reasoning
                        # IDENTITY GUARD (streaming): two tiers — a signer
                        # who is not on the tenant's team is the hard
                        # confabulation class (observed live 2026-09-02: a
                        # draft to one lead was signed with ANOTHER lead's
                        # name); a teammate-but-not-owner signature is an
                        # attribution miss. One regeneration each; if it
                        # still violates, ship anyway — the supervisor sees
                        # the draft (HITL), the violation is logged.
                        elif signature_signer_status(_streamed, _primary, _team):
                            _wrong, _wrong_kind = signature_signer_status(_streamed, _primary, _team)
                            _owner = (_primary or {}).get("name")
                            if _wrong_kind == "external":
                                logger.warning(
                                    f"streamed reply signs as {_wrong!r} — NOT on the "
                                    f"tenant team; identity regeneration")
                                messages.append({"role": "system", "content": (
                                    f"Your previous reply signed the message as "
                                    f"{_wrong!r}, who is not on this business's team. "
                                    f"The sender is {_owner}. Regenerate the reply "
                                    "with the SAME content but signed with the "
                                    "sender's own name/signature only. Never name "
                                    "a lead, customer, or any external contact as sender."
                                )})
                            else:
                                logger.warning(
                                    f"streamed reply signs as teammate {_wrong!r} "
                                    f"instead of the owner; attribution regeneration")
                                messages.append({"role": "system", "content": (
                                    f"Your previous reply signed the message as "
                                    f"{_wrong!r}. You work on behalf of {_owner}; "
                                    "sign with THEIR name/signature. Regenerate "
                                    "the reply with the SAME content, signed as "
                                    f"{_owner}."
                                )})
                            _fix = await self.llm_service.generate_completion(
                                messages=messages,
                                model=forced_model,
                                tenant_id=self.tenant_id,
                                **extra_kwargs,
                            )
                            _fixed = _strip_protocol_tags((_fix or {}).get("content"))
                            if _fixed and not signature_signer_status(_fixed, _primary, _team):
                                _streamed = _fixed
                                _turn_reasoning = (_fix or {}).get("reasoning") or _turn_reasoning
                        # Chain-of-thought → a real "thought" step: persisted
                        # (trace/history) + broadcast (live reasoningTrace in
                        # every chat surface) + returned for feedback capture.
                        if _reasoning_parts:
                            _turn_reasoning = "\n\n".join(
                                p.strip() for p in _reasoning_parts if p and p.strip()
                            ).strip() or None
                        if _turn_reasoning:
                            try:
                                await _trace(
                                    "thought",
                                    {"tool": "llm", "params": {"model": _s_model, "provider": _s_prov}},
                                    "model chain-of-thought (expand for training/audit)",
                                    thought=_turn_reasoning,
                                )
                            except Exception:
                                pass
                        await _ws_manager.broadcast(f"user:{user_id}", {
                            "type": "chat_token_done",
                            "data": {
                                "session_id": session_id,
                                "content": _streamed,
                                "elapsed_s": round(_time.monotonic() - _t0, 1),
                            },
                        })
                        logger.info(
                            f"[stage-timing] reply STREAMED: "
                            f"{_time.monotonic() - _t0:.1f}s to full text "
                            f"({_s_prov}/{_s_model}, {len(_buf)} chunks)")
                        response_data = {
                            "success": True,
                            "content": _streamed,
                            "model": _s_model,
                            "provider": _s_prov,
                        }
                    else:
                        logger.warning("chat streaming produced no tokens — falling back")
                except Exception as stream_err:
                    logger.warning(f"chat streaming failed — non-streaming fallback: {stream_err}")

            if _streamed is None:
                response_data = await self.llm_service.generate_completion(
                    messages=messages,
                    model=forced_model,  # "auto" unless overridden
                    tenant_id=self.tenant_id,
                    **extra_kwargs,
                )
                # Non-streaming path: same chain-of-thought capture as the
                # streaming leg — the response's separate reasoning field
                # (if any) plus inline <think> blocks (captured by the strip
                # call on the next line via the shared _reasoning_parts list).
                _reasoning_parts: List[str] = []
                _strip_protocol_tags(response_data.get("content"), captured=_reasoning_parts)
                _turn_reasoning = (
                    (response_data or {}).get("reasoning")
                    or ("\n\n".join(p.strip() for p in _reasoning_parts if p and p.strip()).strip() or None)
                )
            
            logger.info(
                f"[stage-timing] reply generation: {time.monotonic() - _plan_t0:.1f}s "
                f"(incl. tool plan + exec above)")
            if response_data.get("success"):
                # Reasoning/protocol-tag hygiene: some models (minimax m3 via
                # OpenRouter) leak chain-of-thought fragments ("</mm:think>")
                # or raw tool-call XML ("<tool_call>…</tool_call>") into
                # content. Strip paired blocks and stray tags before the
                # reply is stored or displayed — otherwise they persist into
                # the transcript and the next turn's context.
                _content = _strip_protocol_tags(response_data.get("content"))
                # GROUNDING GUARD (non-streaming path): same wobble guard as
                # the streaming path — one grounded regeneration when the
                # reply denies having data that a LIVE TOOL RESULT provided.
                if _tool_block and _reply_claims_inability(_content):
                    logger.warning(
                        "reply claims inability despite tool results — grounded "
                        "regeneration")
                    messages.append({"role": "system", "content": (
                        "Your previous reply wrongly claimed you lack data or "
                        "ability. A LIVE TOOL RESULT block IS present above — "
                        "answer the user's current message from it now, in plain "
                        "language, with no capability disclaimers."
                    )})
                    response_data = await self.llm_service.generate_completion(
                        messages=messages,
                        model=forced_model,
                        tenant_id=self.tenant_id,
                        **extra_kwargs,
                    )
                    _content = _strip_protocol_tags(
                        (response_data or {}).get("content"))
                # EVIDENCE GUARD (non-streaming path): same confirm→assert
                # guard as the streaming path — the request asked to
                # confirm/verify and the reply asserts it as fact.
                elif asserts_unverified_confirmation(message, _content):
                    logger.warning(
                        "reply asserts an unverified confirm/verify request "
                        "as fact — grounded regeneration")
                    messages.append({"role": "system", "content": (
                        "Your previous reply stated a claim as fact that "
                        "the request only asked to CONFIRM, and no evidence "
                        "in this context establishes it. Regenerate: keep "
                        "the reply's useful structure, but for that claim "
                        "either (a) say plainly it is not yet verified, or "
                        "(b) make no claim in either direction — word it "
                        "as confirmation in progress (\"We are "
                        "confirming X and will follow up with details\") "
                        "or ask for the missing information (\"Could you "
                        "share the spec sheets so we can confirm?\"). "
                        "Do not assert it as true."
                    )})
                    response_data = await self.llm_service.generate_completion(
                        messages=messages,
                        model=forced_model,
                        tenant_id=self.tenant_id,
                        **extra_kwargs,
                    )
                    _fixed = _strip_protocol_tags(
                        (response_data or {}).get("content"))
                    if _fixed and not asserts_unverified_confirmation(message, _fixed):
                        _content = _fixed
                        response_data = {**response_data, "content": _fixed}
                # IDENTITY GUARD (non-streaming): same two-tier wrong-signer
                # backstop as the streaming path.
                elif signature_signer_status(_content, _primary, _team):
                    _wrong, _wrong_kind = signature_signer_status(_content, _primary, _team)
                    _owner = (_primary or {}).get("name")
                    if _wrong_kind == "external":
                        logger.warning(
                            f"reply signs as {_wrong!r} — NOT on the tenant "
                            f"team; identity regeneration")
                        messages.append({"role": "system", "content": (
                            f"Your previous reply signed the message as "
                            f"{_wrong!r}, who is not on this business's team. "
                            f"The sender is {_owner}. Regenerate the reply "
                            "with the SAME content but signed with the "
                            "sender's own name/signature only. Never name a "
                            "lead, customer, or any external contact as sender."
                        )})
                    else:
                        logger.warning(
                            f"reply signs as teammate {_wrong!r} instead of "
                            f"the owner; attribution regeneration")
                        messages.append({"role": "system", "content": (
                            f"Your previous reply signed the message as "
                            f"{_wrong!r}. You work on behalf of {_owner}; "
                            "sign with THEIR name/signature. Regenerate the "
                            f"reply with the SAME content, signed as {_owner}."
                        )})
                    response_data = await self.llm_service.generate_completion(
                        messages=messages,
                        model=forced_model,
                        tenant_id=self.tenant_id,
                        **extra_kwargs,
                    )
                    _fixed = _strip_protocol_tags(
                        (response_data or {}).get("content"))
                    if _fixed and not signature_signer_status(_fixed, _primary, _team):
                        _content = _fixed
                        response_data = {**response_data, "content": _fixed}
                if _tool_block and len(_content) < 20:
                    # The model emitted protocol syntax instead of an answer
                    # (sanitized away). One firm retry; if it still fails,
                    # fall through to the template path — never store junk.
                    logger.info("tool-turn reply was protocol syntax; retrying firmly")
                    _retry = await self.llm_service.generate_completion(
                        messages=messages + [{
                            "role": "system",
                            "content": (
                                "IMPORTANT: You have already received the tool result. "
                                "Reply with a plain-language answer to the user now. "
                                "No tool calls, no XML, no tags."
                            ),
                        }],
                        model=forced_model,
                        tenant_id=self.tenant_id,
                        **extra_kwargs,
                    )
                    if _retry.get("success"):
                        _rc = str(_retry.get("content") or "").strip()
                        _rc = re.sub(r"<tool_call>.*?</tool_call>", "", _rc, flags=re.DOTALL)
                        _rc = re.sub(r"</?(?:mm:)?think>|\]?<\]?minimax\[>?", "", _rc).strip()
                        if len(_rc) >= 20:
                            _content = _rc
                if not _content:
                    return None
                # VERIFICATION PANEL — mission-critical / high-complexity turns only
                # (PoLL pattern: diverse-provider judge VOTE via the R83 voter).
                _vpm = get_verify_panel_mode()
                logger.info(
                    f"[verify-panel] state: mode={_vpm} tool_block={bool(_tool_block)} "
                    f"content={bool(_content)} mission={mission_critical}")
                if _vpm != "off" and _tool_block and _content:
                    _vp_t0 = time.monotonic()
                    _verdict = await verify_reply(
                        _content, _tool_block,
                        handler=self.llm_service.handler,
                        tenant_id=self.tenant_id,
                        agent_id=agent_id,
                    )
                    if _verdict.get("ran"):
                        logger.info(
                            "[verify-panel] " + _vpm + ": grounded=" + str(_verdict.get("grounded"))
                            + " agreement=" + str(_verdict.get("agreement"))
                            + " (" + str(_verdict.get("level")) + ", "
                            + str(_verdict.get("samples")) + " samples, "
                            + "%.1fs)" % (time.monotonic() - _vp_t0))
                        # Enforce only on an AGREED ungrounded verdict — an
                        # ambiguous split (judges disagreed) is logged, never
                        # acted on.
                        if (_vpm == "enforce" and not _verdict.get("grounded")
                                and _verdict.get("level") in ("high", "partial")):
                            logger.warning(
                                "[verify-panel] ungrounded claims: "
                                + "; ".join(_verdict.get("claims") or ["unspecified"])
                                + " — grounded regeneration")
                            messages.append({"role": "system", "content": (
                                "VERIFICATION FAILURE: your reply contains claims the retrieved "
                                "evidence does not support: "
                                + "; ".join(_verdict.get("claims") or ["unspecified"])
                                + ". Rewrite the answer using ONLY the LIVE TOOL RESULT evidence "
                                "above. Keep what is supported; drop what is not."
                            )})
                            response_data = await self.llm_service.generate_completion(
                                messages=messages,
                                model=forced_model,
                                tenant_id=self.tenant_id,
                                **extra_kwargs,
                            )
                            _content = _strip_protocol_tags((response_data or {}).get("content"))
                            _verdict2 = await verify_reply(
                                _content, _tool_block,
                                handler=self.llm_service.handler,
                                tenant_id=self.tenant_id,
                                agent_id=agent_id,
                            )
                            if not _verdict2.get("ran") or not _verdict2.get("grounded"):
                                _content += (
                                    "\n\n⚠️ *Verification note: automated checks could not confirm "
                                    "every claim in this reply against the retrieved sources.*")
                    try:
                        await _trace("final_answer",
                                     {"tool": "llm", "params": {"model": response_data.get("model")}},
                                     _content[:300])
                    except Exception:
                        pass
                # Non-streaming leg: the chain-of-thought step is emitted here
                # (the streaming leg emits its own right after the stream).
                if _turn_reasoning and _streamed is None:
                    try:
                        await _trace(
                            "thought",
                            {"tool": "llm", "params": {"model": response_data.get("model")}},
                            "model chain-of-thought (expand for training/audit)",
                            thought=_turn_reasoning,
                        )
                    except Exception:
                        pass
                return {
                    "content": _content,
                    "model": response_data.get("model"),
                    "provider": response_data.get("provider"),
                    "memory_context": memory_block,
                    "reasoning": _turn_reasoning,
                }

            return None
        except Exception as e:
            logger.warning(f"Unified conversational response failed: {e}")
            return None

    async def _try_zoho_crm_write(self, message: str, context: Dict[str, Any], user_id: str) -> Optional[str]:
        """Detect CRM mutations in a chat message and execute them via Zoho.

        Returns a human-readable confirmation string, or None if the message
        doesn't contain a recognisable CRM operation.
        """
        import re as _re
        from core.integrations.adapters.zoho import ZohoAdapter
        from core.models import IntegrationToken

        lower = message.lower()
        is_create = "create" in lower or "add" in lower or "new lead" in lower
        is_update = "update" in lower or "change" in lower
        if not (is_create or is_update):
            return None

        if not any(k in lower for k in ("lead", "deal", "contact")):
            return None

        # extract name
        name_match = _re.search(
            r"(?:for|named|called)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", message
        )
        person = name_match.group(1) if name_match else None

        # extract email
        email_match = _re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", message)
        email = email_match.group(0) if email_match else None

        # extract company
        company_match = _re.search(r"at\s+([A-Z][\w !&]+?)(?:,|\.|$|\s+email|\s+phone)", message)
        company = company_match.group(1).strip() if company_match else None

        if not person and not email:
            return None

        db = SessionLocal()
        try:
            token = db.query(IntegrationToken).filter(
                IntegrationToken.user_id == user_id,
                IntegrationToken.provider == "zoho",
                IntegrationToken.status == "active",
            ).first()
            if not token:
                return None
            instance_url = token.instance_url or None
            db.close()

            adapter = ZohoAdapter(workspace_id="default", instance_url=instance_url)
            await adapter.ensure_token()

            if "create" in lower or "new lead" in lower or "add" in lower:
                lead_data = {}
                if email:
                    lead_data["Email"] = email
                if person:
                    parts = person.split(" ", 1)
                    lead_data["First_Name"] = parts[0]
                    if len(parts) > 1:
                        lead_data["Last_Name"] = parts[1]
                    else:
                        lead_data["Last_Name"] = parts[0]
                if company:
                    lead_data["Company"] = company
                result = await adapter.create_lead(lead_data)
                if result:
                    return f"Created Zoho CRM lead: {person or 'New lead'} ({email or 'no email'}) — ID: {result.get('id', 'new')}"

            return None
        except Exception as e:
            logger.warning(f"Zoho CRM write failed: {e}")
            return None

    async def _refresh_canvas_from_store(
        self, user_id: str, canvas: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Latest CanvasAudit row over the client-sent content. The panel can
        send stale canvas_content (missed WS broadcast, the autosave debounce
        window); planning an edit against it and writing the result back
        silently reverted the user's saved on-canvas edits — the durable
        store is authoritative, the context only identifies WHICH canvas.
        Fault-isolated: an unreadable store falls back to the client content
        rather than blocking the turn."""
        try:
            from tools.canvas_crud_tool import read_canvas

            fresh = await read_canvas(user_id, str(canvas.get("canvas_id") or ""))
            if fresh.get("success") and fresh.get("content") is not None:
                return {
                    **canvas,
                    "content": fresh["content"],
                    "canvas_type": fresh.get("canvas_type") or canvas.get("canvas_type"),
                    "title": fresh.get("title") or canvas.get("title"),
                }
        except Exception as e:
            logger.debug(f"canvas store refresh skipped: {e}")
        return canvas

    def _recent_canvas_corrections(
        self, user_id: str, canvas_id: Any, limit: int = 3
    ) -> List[Dict[str, Any]]:
        """The supervisor's hand-edits of the agent's drafts are the co-editor's
        promised training signal ("fix it here and I'll learn"). Recording them
        (AgentFeedback → maturity) changes a score; passing the recent ones
        into the edit PLAN is what changes the next draft. Fault-isolated:
        no context or DB trouble → empty list, never blocks the edit."""
        if not canvas_id:
            return []
        try:
            from core.database import get_db_session
            from core.service_factory import ServiceFactory

            with get_db_session() as db:
                service = ServiceFactory.get_canvas_context_service(
                    db, tenant_id=self.tenant_id
                )
                context = service.get_context(str(canvas_id), user_id)
                if context is None or not context.user_corrections:
                    return []
                return list(context.user_corrections)[-limit:]
        except Exception as e:
            logger.debug(f"canvas corrections lookup skipped: {e}")
            return []

    def _agent_lessons(self, agent_id: Optional[str], query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """The operating hire's PERMANENT taught lessons (TrainingPanel /teach,
        mentor lessons, observed human corrections) for the edit plan. Teaching
        stored the lesson but nothing fed it back at work time — this is the
        retrieval half, applied to the canvas co-editor for every agent and
        every canvas app. Fault-isolated like the corrections lookup: [] on
        any failure, never blocks the edit."""
        if not agent_id:
            return []
        try:
            from core.database import get_db_session
            from core.student_learning_service import get_agent_lessons

            with get_db_session() as db:
                return get_agent_lessons(db, agent_id, query=query, limit=limit)
        except Exception as e:
            logger.debug(f"agent lessons lookup skipped: {e}")
            return []

    async def _cross_canvas_learnings(
        self,
        user_id: str,
        canvas: Dict[str, Any],
        agent_id: Optional[str],
    ) -> tuple:
        """The cross-canvas learning channels for the edit plan — the parts
        of a hire's experience beyond the canvas in front of them:

        - EPISODIC: corrections the supervisor made on OTHER similar canvases
          of the same kind, ranked SEMANTICALLY (FastEmbed — the LanceDB
          vector ecosystem — cosine) with a lexical overlap fallback when
          embeddings are unavailable on the deployment;
        - DISTILLED: recurring patterns across ALL corrections (e.g. the
          supervisor consistently fills To/Cc or strips meta-commentary).

        Fault-isolated like every learning lookup: ([], []) on any failure,
        never blocks the edit."""
        try:
            from core.database import get_db_session
            from core.service_factory import ServiceFactory
            from core.chat_canvas_editor import _canvas_profile_text
            from core.canvas_app_schema import normalize_app_type
            from core.models import Canvas as CanvasModel
            from services.canvas_context_service import rank_similar_canvas_candidates

            canvas_id = str(canvas.get("canvas_id") or "")
            if not canvas_id:
                return [], []
            canvas_type = normalize_app_type(canvas.get("canvas_type"))
            profile = _canvas_profile_text(canvas)

            with get_db_session() as db:
                service = ServiceFactory.get_canvas_context_service(
                    db, tenant_id=self.tenant_id
                )
                candidates = service.get_similar_canvas_candidates(
                    canvas_id, user_id, canvas_type
                )
                similar = await rank_similar_canvas_candidates(
                    profile, candidates,
                    now=datetime.now(timezone.utc),
                )
                patterns = service.get_correction_patterns(
                    user_id, agent_id=agent_id, current_canvas_id=canvas_id
                )
                # Stamp similar-canvas entries with their titles (the prompt
                # names them so the model can reason about WHICH past job a
                # correction came from).
                if similar:
                    ids = [e.get("canvas_id") for e in similar if e.get("canvas_id")]
                    rows = (
                        db.query(CanvasModel.id, CanvasModel.name)
                        .filter(CanvasModel.id.in_(ids))
                        .all()
                        if ids else []
                    )
                    titles = {str(r.id): r.name for r in rows}
                    for e in similar:
                        e["title"] = titles.get(str(e.get("canvas_id")))
            return similar, patterns
        except Exception as e:
            logger.debug(f"cross-canvas learning recall skipped: {e}")
            return [], []

    def _recent_canvas_versions(
        self, user_id: str, canvas_id: Any, limit: int = 4, scan: int = 15
    ) -> List[Dict[str, Any]]:
        """Earlier versions of this canvas from the append-only audit trail —
        bounded snapshots the co-editor can diff against, or copy VERBATIM when
        the user asks to go back ("restore my previous draft"). Newest first;
        the caller trims the list and drops the entry equal to the current
        content. Fault-isolated like the corrections lookup: [] on any failure,
        never blocks the edit."""
        if not canvas_id:
            return []
        try:
            from core.database import get_db_session
            from core.models import CanvasAudit
            from sqlalchemy import desc

            with get_db_session() as db:
                rows = (
                    db.query(CanvasAudit)
                    .filter(
                        CanvasAudit.canvas_id == str(canvas_id),
                        CanvasAudit.action_type != "delete",
                    )
                    .order_by(desc(CanvasAudit.created_at))
                    .limit(scan)
                    .all()
                )
            versions: List[Dict[str, Any]] = []
            for r in rows:
                details = r.details_json or {}
                content = details.get("content", details.get("data"))
                if content is None:
                    continue
                versions.append({
                    "audit_id": r.id,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "actor": "agent" if r.agent_id else "supervisor",
                    "title": details.get("title"),
                    "content": content,
                })
            return versions[:limit]
        except Exception as e:
            logger.debug(f"canvas versions lookup skipped: {e}")
            return []

    async def _heal_degenerate_canvas(
        self, user_id: str, canvas: Dict[str, Any]
    ) -> Dict[str, Any]:
        """One-time deterministic healing of legacy canvases seeded before
        narration-tolerant draft extraction existed (live case: an email
        canvas with to=""/cc="" whose body holds the draft with **To:**
        headers, and a truncated narration sentence as the Subject). Only
        EMPTY fields are ever filled. Persisted through update_canvas_content
        so the heal is audit-trailed and broadcast like any other edit, and
        the edit planner then sees the clean fields. Best-effort: any failure
        returns the canvas unchanged — never blocks the edit turn."""
        try:
            from core.chat_canvas_editor import normalize_degenerate_content
            from tools.canvas_crud_tool import update_canvas_content

            healed = normalize_degenerate_content(
                canvas.get("canvas_type"), canvas.get("content")
            )
            if healed is None or healed == canvas.get("content"):
                return canvas
            result = await update_canvas_content(
                user_id,
                str(canvas.get("canvas_id")),
                healed,
                str(canvas.get("canvas_type") or "generic"),
            )
            if (result or {}).get("success"):
                logger.info(
                    f"canvas {canvas.get('canvas_id')} healed: empty fields "
                    "filled from its own draft text (legacy seed)"
                )
                canvas = dict(canvas)
                canvas["content"] = healed
            return canvas
        except Exception as e:
            logger.debug(f"canvas heal skipped: {e}")
            return canvas

    def _relevant_playbooks(
        self, user_id: str, message: str, canvas_type: Any
    ) -> List[Dict[str, Any]]:
        """Approved playbooks matching this turn (Plan Phase 3, shadow by
        default via ATOM_PLAYBOOKS). Sync + to_thread-wrapped by the caller;
        fault-isolated — a playbook-store failure degrades to no playbooks,
        never blocks the edit turn."""
        try:
            from core.database import get_db_session
            from core.playbook_service import PlaybookService

            with get_db_session() as db:
                tenant = "default"
                try:
                    from core.models import User
                    u = db.query(User).filter(User.id == str(user_id)).first()
                    if u is not None and getattr(u, "tenant_id", None):
                        tenant = u.tenant_id
                except Exception:
                    pass
                svc = PlaybookService(db, tenant_id=tenant)
                return svc.get_relevant(message, canvas_type=canvas_type)
        except Exception as e:
            logger.debug(f"playbook retrieval skipped: {e}")
            return []

    async def _sender_identity(
        self, user_id: str, canvas_type: Any
    ) -> Optional[Dict[str, str]]:
        """Who the draft is sent BY: the account name/email, plus (email
        canvases) the composer's default signature from its own store —
        the same source the UI's signature button uses. Live incident
        (2026-09-02, canvas da27bb76…): no identity reached the editor, so
        "i added my signature, adjust" made it GUESS the sender's name from
        the Cc line and sign the draft "Chandrakant". Identity is resolved
        data, never a model guess. Fault-isolated + time-boxed: a slow
        signature lookup (integration mining on cache miss) degrades to
        name/email only — never blocks the edit turn."""
        identity: Dict[str, str] = {}
        try:
            from core.database import get_db_session
            from core.models import User

            with get_db_session() as db:
                u = db.query(User).filter(User.id == str(user_id)).first()
                if u is not None:
                    name = " ".join(
                        p for p in (u.first_name, u.last_name) if p
                    ).strip()
                    if name:
                        identity["name"] = name
                    if u.email:
                        identity["email"] = u.email

                # Installation profile (Plan Phase 1): the wizard-entered
                # identity outranks nothing — it fills the fields the bare
                # account record lacks (company name, tone notes).
                try:
                    from core.installation_profile_service import (
                        InstallationProfileService,
                    )

                    tenant = getattr(u, "tenant_id", None) if u else None
                    ident = InstallationProfileService(db).identity_for_prompts(
                        tenant or "default")
                    for key in ("sender_name", "company_name"):
                        if ident.get(key) and not identity.get("name" if key == "sender_name" else key):
                            if key == "sender_name":
                                identity.setdefault("name", ident[key])
                            else:
                                identity[key] = ident[key]
                except Exception as prof_err:
                    logger.debug(f"installation profile identity skipped: {prof_err}")

                if str(canvas_type or "").lower() == "email" and user_id:
                    try:
                        from core.canvas_email_service import EmailCanvasService

                        sig = await asyncio.wait_for(
                            EmailCanvasService(db).get_signature(str(user_id)),
                            timeout=5,
                        )
                        value = str((sig or {}).get("signature") or "").strip()
                        if value:
                            identity["signature"] = value
                        # The STYLED variant (raw HTML — fonts, layout
                        # tables, links) rides to the drafting prompt so the
                        # agent reproduces the user's real signature markup
                        # in the canvas body, not a plain-text shadow.
                        sig_html = str((sig or {}).get("signature_html") or "").strip()
                        if sig_html:
                            identity["signature_html"] = sig_html
                    except Exception as sig_err:
                        logger.debug(f"canvas editor signature lookup skipped: {sig_err}")
        except Exception as e:
            logger.debug(f"canvas editor identity lookup skipped: {e}")
        return identity or None

    async def _try_canvas_edit(
        self,
        message: str,
        history: list,
        canvas: Dict[str, Any],
        user_id: str,
        session_id: Optional[str],
        execution_id: Optional[str],
        agent_id: Optional[str],
        provenance: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Canvas co-editor edit step: plan the edit via the canvas editor
        module, persist it through canvas_crud_tool, and return the chat
        response. Returns None when the turn is NOT a canvas edit (or
        anything fails) — the normal conversational path then runs."""
        from core.chat_canvas_editor import (
            CanvasPlanUnavailable,
            apply_canvas_edit,
            describe_apply_failure,
            plan_canvas_edit,
        )

        canvas = await self._refresh_canvas_from_store(user_id, canvas)
        canvas = await self._heal_degenerate_canvas(user_id, canvas)

        # PDF canvases are byte-backed: their pages/forms/signatures change
        # only through the maturity-gated pdf_canvas tools — a text patch on
        # the content JSON would corrupt the document state. Steer the turn
        # to the tools instead (reads still flow through the planner).
        if (canvas.get("canvas_type") or "").lower() == "pdf":
            return {
                "success": True,
                "message": (
                    "This is a PDF canvas — its content is edited through the "
                    "pdf_canvas tools (page ops, form fill, redact, sign), which "
                    "follow your approval policy. Tell me what to change and I'll "
                    "propose it through those tools."
                ),
                "data": {
                    "canvas_action": {
                        "action": "pdf_tool_redirect",
                        "canvas_id": canvas.get("canvas_id"),
                    }
                },
            }

        corrections = self._recent_canvas_corrections(user_id, canvas.get("canvas_id"))
        versions = self._recent_canvas_versions(user_id, canvas.get("canvas_id"))
        lessons = self._agent_lessons(agent_id, message)
        similar_corrections, correction_patterns = await self._cross_canvas_learnings(
            user_id, canvas, agent_id
        )
        user_identity = await self._sender_identity(user_id, canvas.get("canvas_type"))
        playbooks = await asyncio.to_thread(
            self._relevant_playbooks, user_id, message, canvas.get("canvas_type"))

        # Live evidence when the edit hinges on data the editor cannot see
        # (a price "from the consolidated price list"). Same read-only tool
        # planner the chat path uses. When a live-data need EXISTS but the
        # lookup failed, DECLINE the edit (None → the tool/conversational
        # path answers the lookup): applying a data-dependent edit without
        # its evidence fabricated values on the user's real draft (live
        # 2026-09-04: 'In Stock' + placeholder price invented on timeout).
        # step_recorder: the co-editor lane used to run real provider calls
        # with NOTHING recorded in the reasoning-step trail — the applied
        # "In Stock" edit's search existed only in gatekeeper logs. Recorded
        # through the same trail the chat lane writes so the audit and the
        # training payloads see the lookup, its query AND its result.
        _step_counter = {"n": 0}

        async def _record_fresh_data_step(step_type: str,
                                          action: Dict[str, Any],
                                          observation: str) -> None:
            _step_counter["n"] += 1
            await self._record_chat_step(
                session_id, agent_id, execution_id,
                step_number=_step_counter["n"],
                step_type=step_type, action=action, observation=observation)

        from core.chat_canvas_editor import fetch_fresh_data_section
        fresh = await fetch_fresh_data_section(
            message, history, self.llm_service, user_id,
            canvas_id=canvas.get("canvas_id"),
            step_recorder=_record_fresh_data_step,
        )
        if fresh.needed and not fresh.ok:
            logger.info(
                "canvas edit declined: the turn needs live data and the "
                "lookup failed — falling through to the tool path instead "
                "of editing without evidence")
            return None
        fresh_data = fresh.section

        try:
            plan = await asyncio.wait_for(
                plan_canvas_edit(
                    message, history, canvas, self.llm_service,
                    corrections=corrections,
                    versions=versions,
                    lessons=lessons,
                    similar_corrections=similar_corrections,
                    correction_patterns=correction_patterns,
                    provenance=provenance,
                    user_identity=user_identity,
                    playbooks=playbooks,
                    fresh_data=fresh_data,
                ),
                timeout=30,
            )
        except (CanvasPlanUnavailable, asyncio.TimeoutError) as e:
            # Planning infrastructure failed (LLM provider down / timeout).
            # Fall-through here is what produced the worst observed failure:
            # the intent router misfiled edit-shaped requests into
            # TASK_MANAGEMENT ("Handled: True") and the reply claimed a
            # change the canvas never received. Answer honestly instead —
            # the canvas is untouched and the user can just retry.
            logger.warning(
                f"canvas edit planning unavailable for {canvas.get('canvas_id')}: {e} — "
                f"replying honestly instead of falling through to conversation"
            )
            return {
                "success": True,
                "message": (
                    "I couldn't reach the model I use to plan canvas edits "
                    "just now, so nothing was changed. Please try again in a "
                    "moment."
                ),
                "session_id": session_id,
                "intent": "canvas_edit",
                "confidence": 0.9,
                "data": {
                    "canvas_edit": {
                        "canvas_id": canvas.get("canvas_id"),
                        "updated": False,
                        "plan_unavailable": True,
                    }
                },
                "suggested_actions": [],
                "requires_confirmation": False,
                "next_steps": [],
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.warning(f"canvas edit planning skipped: {e}")
            return None
        if plan is None or not plan.wants_edit:
            return None
        # P3 transparency: WHICH company playbooks guided this edit — the
        # chat response carries them (chat_routes maps `data`→`metadata`)
        # so the co-editor transcript can show "Following playbook: X".
        matched_playbooks = [
            {"id": pb.get("id"), "name": pb.get("name")}
            for pb in (playbooks or [])[:2]
            if isinstance(pb, dict) and pb.get("id")
        ]

        # Maturity gate — canvas edits are INTERN+ (governance action
        # "update_canvas"). A hire that isn't mature enough is NOT refused:
        # the canvas IS the training surface (chat_draft_to_canvas contract —
        # "the supervisor trains the hire by editing the draft ON the
        # canvas"). The student PROPOSES the edit by applying it as a draft,
        # and the supervisor's on-canvas correction becomes the learning
        # signal (captured at PUT /api/canvas/{id} → record_user_correction →
        # AgentFeedback/RLHF → maturity growth → graduation).
        await self._record_chat_step(
            session_id, agent_id, execution_id, 1, "thought",
            {"tool": "canvas_editor", "params": {"canvas_id": canvas.get("canvas_id")}},
            f"Planned canvas edit: {(plan.reply or '')[:160]}",
        )

        # Maturity gate — canvas edits are INTERN+ (governance action
        # "update_canvas"). A hire that isn't mature enough is NOT refused:
        # the canvas IS the training surface (chat_draft_to_canvas contract —
        # "the supervisor trains the hire by editing the draft ON the
        # canvas"). The student PROPOSES the edit by applying it as a draft,
        # and the supervisor's on-canvas correction becomes the learning
        # signal (captured at PUT /api/canvas/{id} → record_user_correction →
        # AgentFeedback/RLHF → maturity growth → graduation).
        learning_mode = False
        hitl_policy = False
        if agent_id:
            try:
                from core.autonomy_policy import (
                    MODE_AUTO_UNTIL_CORRECTED,
                    autonomy_cycle,
                    get_effective_mode,
                    mode_allows_autonomy,
                    trust_check,
                )
                from core.database import get_db_session
                from core.service_factory import ServiceFactory

                with get_db_session() as db:
                    governance = ServiceFactory.get_governance_service(db)
                    check = governance.can_perform_action(
                        agent_id=agent_id, action_type="update_canvas"
                    )
                    # The owner's canvas_edit choice now bites on THIS path
                    # (previously only the send path consulted the policy):
                    # human_always forces proposal semantics even for a
                    # mature hire, and (flag-on) unproven trust demotes the
                    # edit to a proposal — the same gate_for_topic outcome
                    # the Autonomy tab displays. auto_until_corrected also
                    # allows execution, but its correction cycle is checked
                    # explicitly here (this path predates gate_for_topic).
                    mode = get_effective_mode(db, user_id, "canvas_edit")
                    hitl_policy = not mode_allows_autonomy(mode)
                    trust_ok = trust_check(db, agent_id, "canvas_edit")["ok"]
                    cycle_ok = True
                    if mode == MODE_AUTO_UNTIL_CORRECTED:
                        cycle_ok = autonomy_cycle(
                            db, agent_id, "canvas_edit")["ok"]
                learning_mode = (
                    not check.get("allowed", True)
                    or hitl_policy
                    or not trust_ok
                    or not cycle_ok
                )
                await self._record_chat_step(
                    session_id, agent_id, execution_id, 2, "thought",
                    {"tool": "canvas_governance", "params": {"action": "update_canvas"}},
                    f"gate: {'PROPOSAL' if learning_mode else 'allowed'}"
                    f" (maturity={'fail' if not check.get('allowed', True) else 'ok'},"
                    f" policy={mode},"
                    f" trust={'fail' if not trust_ok else 'ok'},"
                    f" cycle={'reset' if not cycle_ok else 'ok'})"
                    f" — {str(check.get('reason', ''))[:120]}",
                )
            except Exception as gov_err:
                logger.debug(f"canvas edit governance check skipped: {gov_err}")

        applied = await apply_canvas_edit(
            plan, user_id, canvas, return_reason=True
        )
        # Tolerant unpack: tests (and any caller using the default
        # return_reason=False) may hand back the bare result instead of the
        # (result, reason) pair.
        if isinstance(applied, tuple) and len(applied) == 2:
            result, apply_reason = applied
        else:
            result, apply_reason = applied, None
        if result is None and apply_reason == "no_change":
            # The planned edit reproduced the current content byte-for-byte.
            # Writing it anyway (audit row + "updated!" reply) was the live
            # "nothing changed" incident: the user repeated the same feedback
            # three turns in a row while the canvas never moved. Answer
            # honestly — nothing was written, nothing to learn from.
            logger.info(
                f"canvas edit was a no-op for {canvas.get('canvas_id')} — "
                f"replying honestly instead of claiming an update"
            )
            return {
                "success": True,
                "message": (
                    "I read the canvas and it already reflects that — "
                    "nothing needed changing. If you expected a difference, "
                    "point me at the specific wording to change."
                ),
                "session_id": session_id,
                "intent": "canvas_edit",
                "confidence": 0.9,
                "data": {
                    "canvas_edit": {
                        "canvas_id": canvas.get("canvas_id"),
                        "updated": False,
                        "no_change": True,
                        **({"matched_playbooks": matched_playbooks}
                           if matched_playbooks else {}),
                    }
                },
                "suggested_actions": [],
                "requires_confirmation": False,
                "next_steps": [],
                "timestamp": datetime.now().isoformat(),
            }
        if result is None:
            # The editor classified this as an edit but the write failed
            # (mismatched patch target, undecodable replace payload, store
            # rejection). Falling through to the conversational path here was
            # the worst of both worlds, observed live: it chained the full
            # planner+response pipeline (minutes) and then answered from
            # conversation history with a FALSE success claim ("I've appended
            # … the canvas is now updated") while the canvas never changed.
            # Say what happened instead — immediately, honestly, and with the
            # failure reason so the user can act on it.
            logger.warning(
                f"canvas edit apply failed for {canvas.get('canvas_id')} "
                f"({apply_reason}) — replying honestly instead of falling "
                f"through to conversation"
            )
            return {
                "success": True,
                "message": describe_apply_failure(
                    apply_reason, canvas.get("canvas_type"), canvas
                ),
                "session_id": session_id,
                "intent": "canvas_edit",
                "confidence": 0.9,
                "data": {
                    "canvas_edit": {
                        "canvas_id": canvas.get("canvas_id"),
                        "updated": False,
                        "reason": apply_reason,
                    }
                },
                "suggested_actions": [],
                "requires_confirmation": False,
                "next_steps": [],
                "timestamp": datetime.now().isoformat(),
            }

        # Learning mode: file the proposal into the canvas's training
        # context so the correction diff (human edits the draft afterwards)
        # has a documented "original attempt" to learn from.
        if learning_mode and agent_id:
            try:
                from core.database import get_db_session
                from core.service_factory import ServiceFactory

                with get_db_session() as db:
                    service = ServiceFactory.get_canvas_context_service(
                        db, tenant_id=self.tenant_id
                    )
                    service.add_action_to_history(
                        canvas_id=str(canvas.get("canvas_id")),
                        user_id=user_id,
                        action={
                            "type": "canvas_edit_proposal",
                            "agent_id": agent_id,
                            "instruction": message[:200],
                            "learning_mode": not hitl_policy,
                            **({"human_always": True} if hitl_policy else {}),
                        },
                    )
            except Exception as learn_err:
                logger.debug(f"canvas learning-mode record skipped: {learn_err}")

        await self._record_chat_step(
            session_id, agent_id, execution_id, 3, "observation",
            {"tool": "canvas_update", "params": {"canvas_id": canvas.get("canvas_id")}},
            f"Canvas {canvas.get('canvas_id')} "
            f"{'draft proposal applied (learning mode)' if learning_mode else 'updated'} "
            f"({canvas.get('canvas_type') or 'generic'}); broadcast sent.",
        )

        reply = (plan.reply or "").strip() or (
            "Updated the canvas — it should refresh beside this panel (and "
            "the new version is saved to its history)."
        )
        if learning_mode:
            if hitl_policy:
                # Mature hire, but the owner demanded a human for canvas
                # edits — proposal voice, not student voice.
                reply = (
                    f"{reply}\n\n🔒 Per your autonomy setting I don't apply edits "
                    "on my own — this is my draft proposal for you to review and "
                    "correct right here on the canvas."
                )
            else:
                # Student voice: propose, invite correction — never claim authority.
                reply = (
                    f"{reply}\n\n📝 I'm still learning canvas edits, so treat this as "
                    "my draft attempt — fix it right here on the canvas and I'll "
                    "learn from your changes."
                )
        logger.info(
            f"canvas co-editor edit applied: canvas={canvas.get('canvas_id')} "
            f"type={canvas.get('canvas_type')}"
            + (" (learning mode: proposal by immature hire)" if learning_mode else "")
        )
        return {
            "success": True,
            "message": reply,
            "session_id": session_id,
            "intent": "canvas_edit",
            "confidence": 0.9,
            "data": {
                "canvas_edit": {
                    "canvas_id": canvas.get("canvas_id"),
                    "updated": True,
                    **({"learning_mode": True} if learning_mode else {}),
                    **({"matched_playbooks": matched_playbooks}
                       if matched_playbooks else {}),
                }
            },
            "suggested_actions": [],
            "requires_confirmation": False,
            "next_steps": [],
            "timestamp": datetime.now().isoformat(),
        }

    async def _try_canvas_action(
        self,
        message: str,
        history: list,
        canvas: Dict[str, Any],
        user_id: str,
        session_id: Optional[str],
        execution_id: Optional[str],
        agent_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """DOING something with the canvas (send the draft as email) — the
        counterpart of the edit step. Two gates, in order:

        1. AUTONOMY POLICY (the owner's choice, per topic): ``human_always``
           means the agent may only PROPOSE — approval happens in the Journey
           panel / proposals endpoints, never here.
        2. MATURITY (governance): ``auto_if_mature`` topics execute directly
           only when the hire's tier allows it; an immature hire proposes
           (the same learning loop as edits).

        Returns the chat response for a handled action, None to fall through
        (including on every failure — the turn degrades to conversation).
        """
        from core.chat_canvas_editor import plan_canvas_action

        # Same durable-store rule as edits: a send planned from the panel's
        # (possibly stale) content would dispatch an out-of-date draft.
        canvas = await self._refresh_canvas_from_store(user_id, canvas)

        # Same evidence rule as edits: a send that amends the draft with
        # external facts ("send it with the current price") gets the live
        # FRESH DATA section; when that need exists but the lookup failed,
        # DECLINE (None → the conversational/tool path answers) — a send
        # composed from guessed values is fabrication, not assistance.
        from core.chat_canvas_editor import fetch_fresh_data_section
        fresh = await fetch_fresh_data_section(
            message, history, self.llm_service, user_id,
        )
        if fresh.needed and not fresh.ok:
            logger.info(
                "canvas action declined: the turn needs live data and the "
                "lookup failed — falling through to the tool path")
            return None
        fresh_data = fresh.section

        try:
            plan = await asyncio.wait_for(
                plan_canvas_action(message, history, canvas, self.llm_service, fresh_data=fresh_data),
                timeout=25,
            )
        except Exception as e:
            logger.warning(f"canvas action planning skipped: {e}")
            return None
        if plan is None or not plan.wants_action:
            return None

        await self._record_chat_step(
            session_id, agent_id, execution_id, 1, "thought",
            {"tool": "canvas_action_planner", "params": {"action": plan.action}},
            f"Planned canvas action: {plan.action} to={plan.to or '(unspecified)'}",
        )

        from core.autonomy_policy import (
            MODE_AUTO_IF_MATURE,
            MODE_HUMAN_ALWAYS,
            MODE_AUTO_UNTIL_CORRECTED,
            autonomy_cycle,
            get_effective_mode,
            mode_allows_autonomy,
            trust_check,
        )
        from core.database import get_db_session
        from core.email_policy import APPROVE as EMAIL_APPROVE, evaluate_email_action

        mode = MODE_AUTO_IF_MATURE
        governance_allows = True
        trust_allows = True
        cycle_allows = True
        policy_decision = None
        try:
            with get_db_session() as db:
                mode = get_effective_mode(db, user_id, "send_email")
                if agent_id and mode_allows_autonomy(mode):
                    from core.service_factory import ServiceFactory

                    governance = ServiceFactory.get_governance_service(db)
                    check = governance.can_perform_action(
                        agent_id=agent_id, action_type="send_email"
                    )
                    governance_allows = bool(check.get("allowed", True))
                    # Skill-scoped trust (R8): an unproven hire proposes even
                    # when policy + maturity would allow the send. Neutral-pass
                    # while the trust flag is off — legacy behavior unchanged.
                    trust_allows = trust_check(db, agent_id, "send_email")["ok"]
                    # Correction cycle (auto_until_corrected): a human
                    # correction reset the hire's EARNED send autonomy —
                    # propose until verified work re-graduates it.
                    if mode == MODE_AUTO_UNTIL_CORRECTED:
                        cycle_allows = autonomy_cycle(
                            db, agent_id, "send_email")["ok"]

                # The email policy's APPROVE (e.g. external recipient on the
                # egress allowlist) ALWAYS requires a human — for agent-initiated
                # sends that means the HITL proposal flow, not transport.
                # Previously this gate ran only inside EmailCanvasService AFTER
                # the decision, so an agent send to an external recipient went
                # straight to transport and would have DISPATCHED unapproved
                # whenever the transport happened to work (observed 2026-08-31:
                # only the missing Outlook Mail.Send consent prevented it).
                # Deterministic + pure: safe to evaluate here, pre-execution.
                if agent_id:
                    body = (canvas.get("content") or {})
                    if not isinstance(body, dict):
                        body = {"body": str(body)}
                    recipients = [
                        r.strip()
                        for r in (plan.to or "").replace(";", ",").split(",")
                        if r.strip()
                    ]
                    policy_decision = evaluate_email_action(
                        {
                            "to": recipients,
                            "cc": [],
                            "subject": plan.subject or "",
                            "body": plan.body or body.get("body", ""),
                        },
                        {"user_id": user_id, "agent_id": agent_id},
                    )
        except Exception as e:
            logger.warning(f"canvas action gates skipped: {e}")

        # Gate outcomes → direct execution ONLY when policy allows autonomy
        # AND the hire is mature enough AND trust clears the bar AND no
        # correction reset the cycle (until_corrected) AND the email policy
        # doesn't demand a human. Everything else proposes (HITL).
        needs_approval = (
            (not mode_allows_autonomy(mode))
            or not governance_allows
            or not trust_allows
            or not cycle_allows
            or (agent_id is not None and policy_decision is not None
                and policy_decision.get("decision") == EMAIL_APPROVE)
        )
        if not needs_approval:
            result = await self._execute_send_email(
                plan, canvas, user_id, agent_id,
            )
            if result is None:
                return None  # execution failure → fall through to conversation
            reply = result.get("message") or "Email sent."
            return {
                "success": True,
                "message": reply,
                "session_id": session_id,
                "intent": "canvas_action",
                "confidence": 0.9,
                "data": {"canvas_action": result},
                "suggested_actions": [],
                "requires_confirmation": False,
                "next_steps": [],
                "timestamp": datetime.now().isoformat(),
            }

        # HITL: file the proposal; approval executes it (and feeds learning).
        proposal_id = self._create_send_email_proposal(
            plan, canvas, user_id, session_id, agent_id,
        )
        if proposal_id is None:
            return None

        await self._record_chat_step(
            session_id, agent_id, execution_id, 2, "observation",
            {"tool": "action_proposal", "params": {"action": "send_email"}},
            f"HITL: send_email proposed ({plan.to or 'no recipient'}); "
            "awaiting human approval in the Journey panel.",
        )
        reply = (
            (plan.reply or "Ready to send that email.").strip()
            + f"\n\n🔐 This needs your approval first"
            + (" (you've set email sends to always require a human)" if mode == MODE_HUMAN_ALWAYS
               else " (a correction reset this hire's send autonomy — it re-earns it through verified work)" if not cycle_allows
               else " (the hire isn't mature enough to send autonomously yet)"
               if not governance_allows
               else " (the hire's verified trust hasn't earned autonomous sends yet)")
            + " — open the **Journey** tab to approve or reject it."
        )
        return {
            "success": True,
            "message": reply,
            "session_id": session_id,
            "intent": "canvas_action",
            "confidence": 0.9,
            "data": {
                "canvas_action": {
                    "action": "send_email",
                    "proposal_id": proposal_id,
                    "needs_approval": True,
                    "to": plan.to or "",
                    "subject": plan.subject or "",
                }
            },
            "suggested_actions": [],
            "requires_confirmation": False,
            "next_steps": [],
            "timestamp": datetime.now().isoformat(),
        }

    async def _execute_send_email(
        self, plan, canvas: Dict[str, Any], user_id: str, agent_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Direct send via the deterministic email policy (audits + policy
        checks inside). Returns a result dict, None on failure."""
        try:
            from core.canvas_email_service import EmailCanvasService
            from core.database import get_db_session

            recipients = [
                r.strip() for r in (plan.to or "").replace(";", ",").split(",") if r.strip()
            ]
            if not recipients:
                logger.info("canvas action: no recipient in plan — falling through")
                return None
            # cc recipients named by the plan (extracted from the message or
            # the canvas content) — previously hardcoded [] and dropped.
            cc_emails = [
                r.strip() for r in (plan.cc or "").replace(";", ",").split(",") if r.strip()
            ]
            body = (plan.body or "").strip()
            if not body and isinstance(canvas.get("content"), dict):
                body = str(canvas["content"].get("content") or "")
            elif not body and isinstance(canvas.get("content"), str):
                body = canvas["content"]

            with get_db_session() as db:
                service = EmailCanvasService(db)
                result = await service.send_email(
                    canvas_id=str(canvas.get("canvas_id")),
                    user_id=user_id,
                    to_emails=recipients,
                    cc_emails=cc_emails,
                    subject=plan.subject or (canvas.get("title") or ""),
                    body=body,
                    agent_id=agent_id,
                    thread_id=(plan.thread_id or "").strip() or None,
                    reply_all=bool(plan.reply_all),
                )
            if not (result or {}).get("success"):
                logger.info(f"canvas action send_email rejected: {(result or {}).get('error')}")
                return {"message": f"Send blocked by email policy: {(result or {}).get('error', 'unknown')}"}
            status = result.get("status", "sent")
            return {
                "action": "send_email",
                "status": status,
                "message": (f"Email {status} to {', '.join(recipients)}."
                            if status != "sent" else f"Email sent to {', '.join(recipients)}."),
                "result": {k: v for k, v in result.items() if k != "message"},
            }
        except Exception as e:
            logger.warning(f"canvas action send_email failed: {e}")
            return None

    def _create_send_email_proposal(
        self, plan, canvas: Dict[str, Any], user_id: str,
        session_id: Optional[str], agent_id: Optional[str],
    ) -> Optional[str]:
        """File a pending send_email proposal (the existing HITL machinery —
        /api/maturity/proposals + approve executes it and feeds learning)."""
        try:
            from core.database import get_db_session
            from core.models import AgentProposal, AgentRegistry

            with get_db_session() as db:
                agent = (
                    db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
                    if agent_id else None
                )
                # cc recipients: what the plan extracted, falling back to the
                # cc maintained on the canvas draft itself
                canvas_content = canvas.get("content")
                cc_line = (plan.cc or "").strip() or (
                    str(canvas_content.get("cc") or "").strip()
                    if isinstance(canvas_content, dict) else ""
                )
                proposal = AgentProposal(
                    tenant_id=(getattr(agent, "tenant_id", None) or "default"),
                    user_id=user_id,
                    agent_id=agent_id or "atom_main",
                    agent_name=(agent.name if agent else "Assistant"),
                    canvas_id=str(canvas.get("canvas_id")),
                    session_id=session_id,
                    proposal_type="action",
                    title=f"Send email: {plan.subject or (canvas.get('title') or 'draft')}",
                    description=(
                        f"Send the canvas draft by email.\n\nTo: {plan.to or '(not specified)'}\n"
                        + (f"Cc: {cc_line}\n" if cc_line else "")
                        + f"Subject: {plan.subject or '(canvas title)'}"
                    ),
                    proposal_data={
                        "action_type": "send_email",
                        "canvas_id": str(canvas.get("canvas_id")),
                        "to": plan.to or "",
                        "cc": cc_line,
                        "subject": plan.subject or "",
                        "body": plan.body or "",
                        # Threading survives the HITL round-trip: the approved
                        # proposal must replay as the same threaded reply.
                        "thread_id": (plan.thread_id or "").strip(),
                        "reply_all": bool(plan.reply_all),
                    },
                    status="pending_approval",
                )
                db.add(proposal)
                db.commit()
                db.refresh(proposal)
                logger.info(
                    f"canvas action proposal filed: {proposal.id} "
                    f"(send_email, canvas={canvas.get('canvas_id')})"
                )
                return proposal.id
        except Exception as e:
            logger.warning(f"canvas action proposal creation failed: {e}")
            return None

    async def _analyze_intent(self, message: str, session: Dict) -> Dict[str, Any]:
        """Analyze user intent using AI NLP engine"""
        try:
            if "nlp" in self.ai_engines:
                nlp_result = await self.ai_engines["nlp"].parse_command(message)
                return {
                    "primary_intent": self._classify_intent(nlp_result),
                    "confidence": nlp_result.confidence,
                    "entities": nlp_result.entities,
                    "platforms": nlp_result.platforms,
                    "command_type": nlp_result.command_type,
                    "raw_nlp": nlp_result
                }
        except Exception as e:
            logger.warning(f"NLP analysis failed: {e}")

        # Fallback intent classification
        return self._fallback_intent_analysis(message)

    def _classify_intent(self, nlp_result) -> ChatIntent:
        """Classify intent from NLP results"""
        from ai.nlp_engine import CommandType
        command_type = nlp_result.command_type
        
        # Map command types to intents
        intent_mapping = {
            CommandType.SEARCH: ChatIntent.SEARCH_REQUEST,
            CommandType.CREATE: ChatIntent.TASK_MANAGEMENT,
            CommandType.UPDATE: ChatIntent.TASK_MANAGEMENT,
            CommandType.SCHEDULE: ChatIntent.SCHEDULING,
            CommandType.ANALYZE: ChatIntent.DATA_ANALYSIS,
            CommandType.BUSINESS_HEALTH: ChatIntent.BUSINESS_HEALTH,
            CommandType.TRIGGER: ChatIntent.AUTOMATION_TRIGGER,
            CommandType.WORKFLOW_CREATION: ChatIntent.WORKFLOW_CREATION,
        }

        return intent_mapping.get(command_type, ChatIntent.SEARCH_REQUEST)

    def _fallback_intent_analysis(self, message: str) -> Dict[str, Any]:
        """Fallback intent analysis when NLP is unavailable"""
        message_lower = message.lower()

        # Simple keyword-based intent detection
        if any(word in message_lower for word in ["find", "search", "look for", "where is"]):
            intent = ChatIntent.SEARCH_REQUEST
        elif any(word in message_lower for word in ["message", "email", "send", "notify"]):
            intent = ChatIntent.MESSAGE_SEND
        elif any(word in message_lower for word in ["task", "todo", "reminder", "due"]):
            intent = ChatIntent.TASK_MANAGEMENT
        elif any(word in message_lower for word in ["workflow", "automate", "automation"]):
            intent = ChatIntent.WORKFLOW_CREATION
        elif any(word in message_lower for word in ["schedule", "meeting", "calendar", "appointment"]):
            intent = ChatIntent.SCHEDULING
        # Business Health Detection
        elif any(word in message_lower for word in ["priority", "priorities", "what should i do", "what to do today"]):
            intent = ChatIntent.BUSINESS_HEALTH
        elif any(word in message_lower for word in ["simulate", "simulation", "what if i", "impact of"]):
            intent = ChatIntent.BUSINESS_HEALTH
        # CRM & Sales Intelligence intents
        elif any(word in message_lower for word in ["deal", "lead", "pipeline", "sales", "prospect", "forecast"]):
            intent = ChatIntent.CRM
        else:
            intent = ChatIntent.SEARCH_REQUEST

        return {
            "primary_intent": intent,
            "confidence": 0.6,
            "entities": [],
            "platforms": [],
            "command_type": "search"
        }

    async def _route_to_features(
        self,
        message: str,
        intent_analysis: Dict[str, Any],
        session: Dict,
        context: Optional[Dict]
    ) -> Dict[FeatureType, Any]:
        """Route message to appropriate feature handlers"""
        feature_responses = {}
        primary_intent = intent_analysis["primary_intent"]

        # Map intents to features
        intent_to_features = {
            ChatIntent.SEARCH_REQUEST: [FeatureType.SEARCH, FeatureType.AI_ANALYTICS],
            ChatIntent.MESSAGE_SEND: [FeatureType.COMMUNICATION],
            ChatIntent.TASK_MANAGEMENT: [FeatureType.TASKS, FeatureType.AUTOMATION],
            ChatIntent.WORKFLOW_CREATION: [FeatureType.WORKFLOWS, FeatureType.AUTOMATION],
            ChatIntent.SCHEDULING: [FeatureType.SCHEDULING],
            ChatIntent.DATA_ANALYSIS: [FeatureType.AI_ANALYTICS, FeatureType.SEARCH],
            ChatIntent.AUTOMATION_TRIGGER: [FeatureType.AUTOMATION, FeatureType.WORKFLOWS],
            ChatIntent.INTEGRATION_SETUP: [FeatureType.INTEGRATIONS],
            ChatIntent.STATUS_CHECK: [FeatureType.SEARCH, FeatureType.AI_ANALYTICS],
            ChatIntent.HELP_REQUEST: [FeatureType.SEARCH],
            ChatIntent.BUSINESS_HEALTH: [FeatureType.BUSINESS_HEALTH],
            ChatIntent.CRM: [FeatureType.CRM], # Added CRM intent mapping
            ChatIntent.AGENT_REQUEST: [FeatureType.AGENT],  # Phase 30: Route to Atom
            ChatIntent.MULTI_STEP_PROCESS: list(FeatureType),  # All features for complex requests
        }

        target_features = intent_to_features.get(primary_intent, [FeatureType.SEARCH])

        # Execute feature handlers
        feature_responses = {}
        handled = False
        
        logger.info(f"Routing to features: {target_features}")
        
        for feature_type in target_features:
            if feature_type in self.feature_handlers:
                try:
                    logger.info(f"Executing handler for {feature_type}")
                    response = await self.feature_handlers[feature_type](
                        message, intent_analysis, session, context
                    )
                    if response and response.get("success"):
                        feature_responses[feature_type] = response
                        handled = True
                        logger.info(f"Handler {feature_type} succeeded")
                    else:
                        logger.info(f"Handler {feature_type} returned failure/empty")
                except Exception as e:
                    logger.error(f"Feature handler {feature_type} failed: {e}")
                    feature_responses[feature_type] = {"error": "internal_error"}

        logger.info(f"Feature handling complete. Handled: {handled}, Intent: {primary_intent}")

        # Fallback to ComputerUseAgent if no specific feature handled it successfully
        # OR if the intention was explicitly AGENT_REQUEST
        if not handled or primary_intent == ChatIntent.AGENT_REQUEST:
             try:
                # Use the General Agent (ComputerUseAgent) for unhandled queries
                logger.info(f"Fallback to ComputerUseAgent for: {message}")
                
                # Determine mode based on intent
                mode = "thinker" # Default
                if primary_intent in [ChatIntent.TASK_MANAGEMENT, ChatIntent.WORKFLOW_CREATION]:
                    mode = "tasker"
                
                logger.info(f"Calling agent_service.execute_task with goal: {message}")
                
                # Execute agent task (short-lived)
                task = await agent_service.execute_task(
                    goal=message,
                    mode=mode,
                )
                logger.info(f"Agent task started: {task}")
                
                feature_responses[FeatureType.AGENT] = {
                    "success": True,
                    "data": {"task_id": task["id"], "status": task["status"]},
                    "message": f"I'm working on that. Task ID: {task['id']}",
                    "suggested_actions": ["Check Status"]
                }
             except Exception as e:
                logger.error(f"Agent fallback failed: {e}")
                
        return feature_responses

    def _generate_coordinated_response(
        self,
        message: str,
        intent_analysis: Dict[str, Any],
        feature_responses: Dict[FeatureType, Any],
        session: Dict
    ) -> Dict[str, Any]:
        """Generate coordinated response from all feature responses"""
        # Combine results from all features
        combined_data = {}
        suggested_actions = []
        ui_updates = []

        for feature_type, response in feature_responses.items():
            if response and "data" in response:
                combined_data[feature_type.value] = response["data"]

            if response and "suggested_actions" in response:
                suggested_actions.extend(response["suggested_actions"])

            if response and "ui_updates" in response:
                ui_updates.extend(response["ui_updates"])

        # Generate main response message
        main_message = self._generate_main_message(message, intent_analysis, feature_responses)

        return {
            "success": True,
            "message": main_message,
            "session_id": session["id"],
            "intent": intent_analysis["primary_intent"].value,
            "confidence": intent_analysis["confidence"],
            "data": combined_data,
            "suggested_actions": suggested_actions[:5],  # Limit to top 5
            "ui_updates": ui_updates,
            "requires_confirmation": any(
                resp.get("requires_confirmation", False)
                for resp in feature_responses.values()
            ),
            "next_steps": self._generate_next_steps(intent_analysis, feature_responses),
            "timestamp": datetime.now().isoformat()
        }

    def _generate_main_message(
        self,
        message: str,
        intent_analysis: Dict[str, Any],
        feature_responses: Dict[FeatureType, Any]
    ) -> str:
        """Generate main response message based on feature responses"""
        
        # Check if Agent handled the request (e.g. fallback or direct request)
        if FeatureType.AGENT in feature_responses:
            agent_resp = feature_responses[FeatureType.AGENT]
            if agent_resp.get("success") and agent_resp.get("message"):
                return agent_resp["message"]
                
        intent = intent_analysis["primary_intent"]

        if intent == ChatIntent.SEARCH_REQUEST:
            search_data = feature_responses.get(FeatureType.SEARCH, {})
            if search_data.get("data"):
                count = len(search_data["data"].get("results", []))
                return f"I found {count} results for your search."
            return "I've searched across your connected platforms."

        elif intent == ChatIntent.MESSAGE_SEND:
            comm_data = feature_responses.get(FeatureType.COMMUNICATION, {})
            if comm_data.get("success"):
                return "Message sent successfully."
            return "I'll help you send that message."

        elif intent == ChatIntent.TASK_MANAGEMENT:
            task_data = feature_responses.get(FeatureType.TASKS, {})
            if task_data.get("success"):
                return task_data.get("data", {}).get("message", "I've processed your task request.")
            return "I'll manage those tasks for you."

        elif intent == ChatIntent.WORKFLOW_CREATION:
            workflow_data = feature_responses.get(FeatureType.WORKFLOWS, {})
            if workflow_data.get("data"):
                return "Workflow created successfully. Ready to execute?"
            return "I'll create that automation workflow for you."

        elif intent == ChatIntent.SCHEDULING:
            schedule_data = feature_responses.get(FeatureType.SCHEDULING, {})
            if schedule_data.get("data"):
                return "Schedule updated successfully."
            return "I'll handle the scheduling for you."

        elif intent == ChatIntent.CRM:
            crm_data = feature_responses.get(FeatureType.CRM, {})
            if crm_data.get("success"):
                return crm_data.get("data", {}).get("answer", "I've processed your CRM request.")
            return "I'll help you with your CRM request."

        elif intent == ChatIntent.BUSINESS_HEALTH:
            health_data = feature_responses.get(FeatureType.BUSINESS_HEALTH, {})
            if health_data.get("success"):
                return health_data.get("message", "I've analyzed your business health.")
            return "I'll help you with your business health query."

        return "I've processed your request across all connected platforms."

    def _generate_next_steps(
        self,
        intent_analysis: Dict[str, Any],
        feature_responses: Dict[FeatureType, Any]
    ) -> List[str]:
        """Generate suggested next steps"""
        intent = intent_analysis["primary_intent"]
        next_steps = []

        if intent == ChatIntent.SEARCH_REQUEST:
            next_steps.extend([
                "Refine your search with more specific terms",
                "Check the search results in the Search UI",
                "Save important results for quick access"
            ])

        elif intent == ChatIntent.WORKFLOW_CREATION:
            next_steps.extend([
                "Review the workflow steps",
                "Test the workflow execution",
                "Schedule the workflow for automatic runs"
            ])

        elif intent == ChatIntent.TASK_MANAGEMENT:
            next_steps.extend([
                "Set up automatic task creation",
                "Create task templates for recurring work",
                "Coordinate tasks with your team"
            ])
        
        elif intent == ChatIntent.CRM:
            next_steps.extend([
                "View sales pipeline",
                "Create a new lead",
                "Update a deal status"
            ])

        # Add general next steps
        next_steps.extend([
            "Ask me to connect more services",
            "Explore automation opportunities",
            "Check your dashboard for insights"
        ])

        return next_steps[:3]  # Limit to 3 next steps

    # Feature handler implementations
    async def _handle_search_request(
        self,
        message: str,
        intent_analysis: Dict[str, Any],
        session: Dict,
        context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Handle search requests across all platforms"""
        try:
            # Use AI data intelligence for unified search
            if "data_intelligence" in self.ai_engines:
                search_results = self.ai_engines["data_intelligence"].search_unified_entities(
                    message
                )
            else:
                search_results = []

            return {
                "success": True,
                "data": {
                    "results": search_results,
                    "query": message,
                    "platforms_searched": intent_analysis.get("platforms", [])
                },
                "suggested_actions": [
                    "Open Search UI for detailed results",
                    "Save this search for later",
                    "Set up alert for similar content"
                ],
                "ui_updates": [
                    {"type": "search_results", "data": search_results}
                ]
            }
        except Exception as e:
            logger.error(f"Search handler failed: {e}")
            return {"success": False, "error": "search_failed"}

    async def _handle_communication_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        return {"success": True, "data": {"message": "Communication logic here"}}

    async def _handle_task_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Handle task creation and management requests via unified endpoints."""
        try:
            from core.unified_task_endpoints import create_task, CreateTaskRequest, get_current_user
            import asyncio
            from datetime import datetime, timedelta, timezone
            from unittest.mock import MagicMock
            
            # 1. Use NLP to extract title and description
            title = message
            description = ""
            if "data_intelligence" in self.ai_engines and hasattr(self.ai_engines["data_intelligence"], "extract_task_details"):
                # Hypothetical method if it exists, otherwise fallback
                extracted = self.ai_engines["data_intelligence"].extract_task_details(message)
                title = extracted.get("title", message)
                description = extracted.get("description", "")
            else:
                import re
                # Clean up natural language prefixes
                clean_msg = re.sub(r'^(?:please\s+)?(?:create|make|add|schedule)\s+(?:a\s+)?(?:task|todo|reminder)(?:\s+to|\s+that|\s+for|:|-)?\s*', '', message, flags=re.IGNORECASE).strip()
                
                if not clean_msg:
                    clean_msg = message.strip()
                    
                parts = clean_msg.split(":", 1)
                if len(parts) > 1 and len(parts[0]) < 30:
                    title = parts[0].strip()
                    description = parts[1].strip()
                else:
                    title = clean_msg
                    description = ""
            
            # Shorten title if it's too long
            if len(title) > 50:
                description = title
                title = title[:47] + "..."
            
            # Capitalize
            if title:
                title = title[0].upper() + title[1:]
                
            # 2. Construct unified task request
            task_req = CreateTaskRequest(
                title=title or "New Task",
                description=description,
                dueDate=datetime.now() + timedelta(days=1), # Default to tomorrow
                priority="medium",
                platform="local", # Use local mock backend for chat orchestrator tests
                status="todo"
            )
            
            # Mock the FastAPI current_user dependency for internal calls
            mock_user = MagicMock()
            mock_user.id = session.get("user_id", "system")
            
            # 3. Call the unified API endpoint directly
            result = await create_task(task_data=task_req, current_user=mock_user)
            
            if result.get("success"):
                task_id = result.get("task").id if hasattr(result.get("task"), "id") else "unknown"
                return {
                    "success": True, 
                    "data": {
                        "task": task_req.dict(),
                        "message": f"I've added '{task_req.title}' to your Tasks.",
                        "task_id": task_id
                    },
                    "suggested_actions": [
                        # URL action: a real navigation, not a prompt.
                        # Text actions prefill the chat input on click
                        # (frontend) — never auto-send in the user's voice.
                        {"label": "View My Tasks", "url": "/tasks"},
                        {"label": "Add a deadline"},
                        {"label": "Assign to team"},
                    ]
                }
            else:
                return {"success": False, "error": "Internal task creation failed."}
                
        except Exception as e:
            logger.error(f"Task handler failed: {e}")
            return {"success": False, "error": "task_creation_failed", "data": {"message": "Failed to create task"}}

    async def _handle_workflow_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Handle workflow requests (List, Run)"""
        message_lower = message.lower()
        
        # 1. LIST WORKFLOWS
        if "list" in message_lower or "show" in message_lower:
            workflows = load_workflows()
            if not workflows:
                return {"success": True, "message": "No workflows found."}
            
            workflow_list = "\n".join([f"• {wf['name']}" for wf in workflows[:10]])
            return {
                "success": True,
                "message": f"Available Workflows:\n{workflow_list}",
                "data": {"results": workflows},
                "suggested_actions": [f"Run {wf['name']}" for wf in workflows[:3]]
            }

        # 2. RUN WORKFLOW
        if "run" in message_lower or "execute" in message_lower:
            workflows = load_workflows()
            # Extract workflow name (simple heuristic)
            target = message_lower.replace("run", "").replace("execute", "").replace("workflow", "").strip()
            
            workflow = next((w for w in workflows if target in w.get('name', '').lower() or target == w.get('workflow_id') or target == w.get('id')), None)
            
            if workflow:
                # Execute it
                try:
                    engine = AutomationEngine()
                    execution_id = str(uuid.uuid4())
                    # Fire and forget or await? Await for now.
                    await engine.execute_workflow_definition(workflow, {}, execution_id=execution_id)
                    return {
                        "success": True, 
                        "message": f"✅ Workflow '{workflow['name']}' started! (ID: {execution_id})"
                    }
                except Exception as e:
                    return {"success": False, "message": f"Failed to run workflow: {e}"}
            else:
                return {
                    "success": False, 
                    "message": f"Workflow '{target}' not found. Try 'list workflows' to see available options."
                }

        return {"success": True, "message": "I can help you list or run workflows. Just ask!"}

    async def _handle_scheduling_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Handle scheduling requests"""
        # Simple extraction for now
        message_lower = message.lower()
        if "schedule" in message_lower:
            # Try to parse "schedule [workflow] [time]"
            # This requires robust NLP which we are porting partially
            return {
                "success": True, 
                "message": "I can help schedule workflows. Please specify the workflow and time, e.g., 'Schedule Daily Report for every Monday at 9am'.",
                "suggested_actions": ["List Workflows"]
            }
        
        return {"success": True, "data": {"message": "Scheduling logic is being enabled."}}

    async def _handle_integration_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        return {"success": True, "data": {"message": "Integration logic here"}}

    async def _handle_ai_analytics_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        return {"success": True, "data": {"message": "AI Analytics logic here"}}

    async def _handle_automation_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Handle requests to trigger automation agents"""
        message_lower = message.lower()
        
        # Identify which agent to run based on keywords
        target_agent_id = None
        
        if "competitor" in message_lower or "price" in message_lower:
            target_agent_id = "competitive_intel"
        elif "inventory" in message_lower or "stock" in message_lower:
            target_agent_id = "inventory_reconcile"
        elif "payroll" in message_lower:
            target_agent_id = "payroll_guardian"
            
        if not target_agent_id:
            return {
                "success": False, 
                "message": "I understood you want to run an automation, but I'm not sure which one. Try 'Run inventory check' or 'Check competitor prices'."
            }
            
        if target_agent_id not in AGENTS:
             return {
                "success": False, 
                "message": f"Agent configuration for '{target_agent_id}' not found."
            }

        # Trigger the agent using unified execution
        try:
             # In a real app we might pass specific parameters extracted from NLP
            run_params = {"trigger": "chat_user", "session_id": session.get("id"), "request": message}

            # BUG-122: execute_agent_task was referenced but never imported → NameError.
            if execute_agent_task is None:
                return {"success": False, "message": "Agent execution is not available."}

            await execute_agent_task(target_agent_id, run_params)
            
            agent_name = AGENTS[target_agent_id]["name"]
            return {
                "success": True,
                "data": {
                    "agent_id": target_agent_id,
                    "status": "started"
                },
                "message": f"🚀 I've started the **{agent_name}** for you. You'll receive a notification when it completes.",
                "suggested_actions": ["Check Agent Status", "View Live Logs"]
            }
        except Exception as e:
            logger.error(f"Failed to trigger agent {target_agent_id}: {e}")
            return {
                "success": False,
                "error": "agent_start_failed",
                "message": "I tried to start the agent but encountered an error. Please try again."
            }

    async def _handle_document_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        return {"success": True, "data": {"message": "Document logic here"}}

    async def _handle_finance_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Handle financial and accounting queries"""
        # BUG-123: get_automation_settings was never imported → NameError.
        if get_automation_settings is None or not get_automation_settings().is_accounting_enabled():
            return {
                "success": False,
                "message": "AI Accounting Automations are currently disabled in settings.",
                "suggested_actions": ["Enable Accounting in Settings"]
            }
        try:
            if AccountingAssistant is None:
                return {
                    "success": False,
                    "message": "Accounting services are not available in this deployment.",
                    "suggested_actions": ["Enable Accounting in Settings"]
                }
            # Generate a DB session
            db = SessionLocal()
            try:
                # In a real app, workspace_id comes from context or session
                workspace_id: str = (context or {}).get("workspace_id") or "default"
                assistant = AccountingAssistant(db)
                result = await assistant.process_query(workspace_id, message)
                
                # Check for specific AP/AR follow-up actions
                if "intent" in result:
                    if result["intent"] == "check_overdue":
                        collection_agent = CollectionAgent(db)
                        reminders = await collection_agent.check_overdue_invoices(workspace_id)
                        result["answer"] = f"I've identified {len(reminders)} overdue invoices and triggered reminders."
                        result["reminders"] = reminders
                    elif result["intent"] == "get_aging":
                        collection_agent = CollectionAgent(db)
                        result["aging_report"] = collection_agent.generate_aging_report(workspace_id)
                        result["answer"] = "Here is your current AR aging report summary."
                    elif result["intent"] == "check_close_readiness":
                        close_agent = CloseChecklistAgent(db)
                        period = result.get("params", {}).get("period", datetime.now(timezone.utc).strftime("%Y-%m"))
                        result["close_check"] = await close_agent.run_close_check(workspace_id, period)
                        result["answer"] = f"Here is the close readiness report for {period}."
                    elif result["intent"] == "get_tax_estimate":
                        tax_service = TaxService(db)
                        result["tax_estimate"] = tax_service.estimate_tax_liability(workspace_id)
                        result["answer"] = "I've calculated your estimated tax liability based on current sales."
                    elif result["intent"] == "get_cash_forecast":
                        fpa_service = FPAService(db)
                        result["forecast"] = fpa_service.get_13_week_forecast(workspace_id)
                        result["answer"] = "Here is your 13-week cash flow forecast."
                    elif result["intent"] == "run_scenario":
                        fpa_service = FPAService(db)
                        # Assume params contains scenario definitions
                        scenarios = result.get("params", {}).get("scenarios", [])
                        result["scenario_results"] = fpa_service.run_scenario(workspace_id, scenarios)
                        result["answer"] = "I've modeled the requested scenario and updated the forecast."
                    elif result["intent"] == "get_intercompany_report":
                        intercompany_manager = IntercompanyManager(db)
                        result["intercompany_report"] = intercompany_manager.generate_elimination_report(workspace_id)
                        result["answer"] = "Here is the intercompany activity and elimination report."
                    
                    # Append Regulatory Disclaimer to all financial answers
                    if "answer" in result:
                        result["answer"] += REGULATORY_DISCLAIMER

                return {
                    "success": True,
                    "data": result,
                    "message": result.get("answer", "I've processed your financial request."),
                    "suggested_actions": ["Run P&L Report", "Check AR Aging", "View Unpaid Bills"]
                }
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Finance handler failed: {e}")
            return {"success": False, "error": "finance_handler_failed"}

    async def _handle_crm_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Handle sales and CRM queries via SalesAssistant"""
        if get_automation_settings is None or not get_automation_settings().is_sales_enabled():
            return {
                "success": False,
                "message": "AI Sales Automations are currently disabled in settings.",
                "suggested_actions": ["Enable Sales in Settings"]
            }
        
        try:
            db = SessionLocal()
            try:
                from sales.assistant import SalesAssistant
                workspace_id: str = (context or {}).get("workspace_id") or "default"
                assistant = SalesAssistant(db)
                answer = await assistant.answer_sales_query(workspace_id, message)
                
                return {
                    "success": True,
                    "data": {"answer": answer},
                    "message": answer[:100] + "...",
                    "suggested_actions": ["View Pipeline", "Check Top Leads", "List My Tasks"]
                }
            finally:
                db.close()
        except Exception as e:
            logger.error(f"CRM handler failed: {e}")
            return {"success": False, "error": "crm_handler_failed"}

    async def _handle_business_health_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Handle business health queries (priorities and simulations)"""
        from core.business_health_service import business_health_service
        
        message_lower = message.lower()
        workspace_id: str = (context or {}).get("workspace_id") or "default"
        
        try:
            if any(word in message_lower for word in ["simulate", "simulation", "impact", "what if"]):
                # Run Simulation
                # Simple extraction for demo purposes, in production use AI extraction
                decision_type = "GENERAL"
                if "hire" in message_lower or "hiring" in message_lower:
                    decision_type = "HIRING"
                elif "spend" in message_lower or "spent" in message_lower or "buy" in message_lower:
                    decision_type = "CAPEX"
                
                result = await business_health_service.simulate_decision(workspace_id, decision_type, {"query": message})
                answer = result.get("prediction", "I've analyzed the potential impact of this decision.")
                if "roi" in result:
                    answer += f"\n\n**Predicted ROI:** {result['roi']}"
                if "breakeven" in result:
                    answer += f"\n**Breakeven:** {result['breakeven']}"
                
                return {
                    "success": True,
                    "data": result,
                    "message": answer,
                    "suggested_actions": ["Run another simulation", "View cash flow"]
                }
            else:
                # Get Priorities
                result = await business_health_service.get_daily_priorities(workspace_id)
                priorities = result.get("priorities", [])
                advice = result.get("owner_advice", "")
                
                answer = f"**Daily Strategy Insight:**\n{advice}\n\n"
                if priorities:
                    answer += "**Top Priorities:**\n"
                    for p in priorities:
                        answer += f"- [{p['priority']}] **{p['title']}**: {p['description']}\n"
                else:
                    answer += "Your business vitals look great! No urgent actions identified."
                
                return {
                    "success": True,
                    "data": result,
                    "message": answer,
                    "suggested_actions": ["Review Lead Pipeline", "Check Failed Tasks"]
                }
        except Exception as e:
            logger.error(f"Business Health handler failed: {e}")
            return {"success": False, "error": "business_health_failed"}

    async def _handle_social_media_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        return {"success": True, "data": {"message": "Social Media logic here"}}

    async def _handle_hr_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        return {"success": True, "data": {"message": "HR logic here"}}

    async def _handle_ecommerce_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        return {"success": True, "data": {"message": "Ecommerce logic here"}}

    def _hydrate_session_history(self, session_id: str, session: Dict) -> None:
        """Reload persisted turns from the ChatMessage store into an in-memory
        session after a restart. Without this, a returning session's LLM
        context is empty — `_update_session` writes every turn to the DB, but
        nothing ever read them back, so after an app restart the agent saw no
        prior conversation ("this looks like the start of our chat") even
        though the sidebar still listed the messages. Best-effort: a DB
        failure leaves the existing in-memory session and the chat works.

        The DB is AUTHORITATIVE: a session restored from the legacy file
        cache may hold stale-but-non-empty history (the file lags the DB by
        a restart), so a non-empty in-memory history does NOT skip the
        reload — otherwise turns newer than the last file flush vanish from
        the model's context. The DB result replaces the in-memory history
        whenever it holds at least as many turns.
        """
        try:
            from core.database import get_db_session
            from core.models import ChatMessage as ChatMessageModel

            with get_db_session() as db:
                rows = (
                    db.query(ChatMessageModel)
                    .filter(ChatMessageModel.conversation_id == session_id)
                    # Same-second user+assistant rows sort user-first because
                    # "user" > "assistant" descending.
                    .order_by(ChatMessageModel.created_at.asc(), ChatMessageModel.role.desc())
                    .all()
                )

            turns: List[Dict[str, Any]] = []
            pending_user: Optional[str] = None
            for row in rows:
                content = (row.content or "").strip()
                if not content:
                    continue
                if row.role == "user":
                    if pending_user is not None:
                        turns.append({
                            "message": pending_user,
                            "response": {"message": ""},
                            "intent": {},
                            "timestamp": str(row.created_at or ""),
                            "error": False,
                        })
                    pending_user = content
                else:
                    _row_error = False
                    try:
                        _meta = json.loads(row.metadata_json or "{}")
                        _row_error = _meta.get("quality") == "error"
                    except Exception:
                        pass
                    turns.append({
                        "message": pending_user or "",
                        "response": {"message": "" if _row_error else content},
                        "intent": {},
                        "timestamp": str(row.created_at or ""),
                        "error": _row_error,
                    })
                    pending_user = None
            if pending_user is not None:
                turns.append({
                    "message": pending_user,
                    "response": {"message": ""},
                    "intent": {},
                    "timestamp": "",
                    "error": False,
                })

            existing = session.get("history") or []
            if len(turns) >= len(existing) and len(turns) > 0:
                session["history"] = turns[-12:]
                if len(turns) != len(existing):
                    logger.info(
                        f"Hydrated {len(turns)} persisted turn(s) into session "
                        f"{session_id} after restart"
                    )
        except Exception as e:
            logger.warning(f"Could not hydrate session history from DB (non-fatal): {e}")


    def _get_or_create_session(
        self, user_id: str, session_id: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        # R72 Workstream I — bind the session to the source channel/thread.
        # The universal webhook bridge passes channel_id/thread_id in context so
        # a session created from an external platform is verifiably locked to
        # one channel, preventing cross-channel context leaks for one sender.
        context = context or {}
        channel_id = context.get("channel_id") or context.get("recipient_id")
        thread_id = context.get("thread_id")

        # Security: verify ownership — if the session exists but belongs to a
        # different user, reject (prevents cross-user session IDOR).
        if session_id in self.conversation_sessions:
            existing = self.conversation_sessions[session_id]
            if existing.get("user_id") and str(existing["user_id"]) != str(user_id):
                # Don't reveal the session exists — just create a fresh one.
                session_id = str(uuid.uuid4())
                self.conversation_sessions[session_id] = {
                    "id": session_id,
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "thread_id": thread_id,
                    "created_at": datetime.now().isoformat(),
                    "history": []
                }
            else:
                # Sessions preloaded from the legacy file store at boot arrive
                # with empty history — hydrate from the DB so a returning
                # conversation isn't amnesiac after a restart. No-ops when
                # history is already populated.
                self._hydrate_session_history(session_id, existing)
                self._ensure_session_row(session_id, existing, channel_id, thread_id)
            return self.conversation_sessions[session_id]

        # New session — create in-memory AND persist the ChatSession row.
        self.conversation_sessions[session_id] = {
            "id": session_id,
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_id": thread_id,
            "created_at": datetime.now().isoformat(),
            "history": []
        }
        # Restart survival: the ChatMessage rows for this session may already
        # exist from a previous app run — load them back so the LLM sees the
        # full conversation, not just the turns after this restart.
        self._hydrate_session_history(session_id, self.conversation_sessions[session_id])
        # Persist the session row so it survives restarts and appears in the
        # session list sidebar.
        try:
            if self.session_manager:
                self.session_manager.create_session(
                    user_id=str(user_id),
                    session_id=session_id,
                    channel_id=channel_id,
                    thread_id=thread_id,
                )
        except Exception as e:
            logger.debug(f"Could not persist ChatSession row (non-fatal): {e}")
        return self.conversation_sessions[session_id]

    def _ensure_session_row(
        self, session_id: str, session: Dict[str, Any],
        channel_id: Optional[str], thread_id: Optional[str],
    ) -> None:
        """Backfill the durable ChatSession row for a session that exists only
        in memory. Legacy conversation ids (created before session-row
        persistence, or where the insert failed) otherwise never appear in the
        chat_sessions table — every episode-creation pass then logs
        "Session … not found" and that conversation builds no episodic memory
        (observed live 2026-08-31 on every turn of session aca15165…).
        Idempotent: exits silently when the row already exists."""
        if not self.session_manager:
            return
        try:
            from core.database import get_db_session
            from core.models import ChatSession as ChatSessionModel

            with get_db_session() as db:
                exists = db.query(ChatSessionModel.id).filter(
                    ChatSessionModel.id == session_id
                ).first()
                if exists:
                    return
                self.session_manager.create_session(
                    user_id=str(session.get("user_id") or "unknown"),
                    session_id=session_id,
                    channel_id=channel_id,
                    thread_id=thread_id,
                )
                logger.info(f"Backfilled missing ChatSession row for {session_id}")
        except Exception as e:
            logger.debug(f"ChatSession row backfill skipped for {session_id}: {e}")

    def _update_session(self, session: Dict, message: str, response, intent: Dict):
        # Error-turn detection: a reply that is a known failure artifact (no
        # provider, cancelled, budget-halted, protocol residue) must never
        # enter the model's context later — in a long session they stack into
        # a refusal wall that anchors weak models into failing again even
        # when a fresh, successful answer is available. Flagged turns stay in
        # the DB and UI (history is history) but are skipped at prompt-build.
        # ``response`` may be a plain string (legacy callers) — stored
        # verbatim; the dict-only error checks simply don't apply to it.
        _resp_dict = response if isinstance(response, dict) else {}
        _resp_msg = _resp_dict.get("message", "") or ("" if isinstance(response, dict) else str(response or ""))
        _is_error_turn = bool(
            not _resp_dict.get("success", True)
            or _resp_dict.get("cancelled")
            or _resp_dict.get("error_code") in ("no_llm_provider", "budget_exceeded")
            or "<tool_call>" in _resp_msg
            or "</mm:think>" in _resp_msg
        )
        session["history"].append({
            "message": message,
            "response": response,
            "intent": intent,
            "timestamp": datetime.now().isoformat(),
            "error": _is_error_turn,
        })

        # Session-dedup write-side: index this turn's content so future turns
        # can reference-match byte-identical repeated text. Exact-match only.
        # The stored history itself is NEVER marker-ized here — replacing
        # prior turns' text with placeholders is what corrupted recall before
        # the read-path removal (nothing consumes the markers on the chat
        # path anymore; indexing alone is harmless).
        try:
            from core.llm.compression import SESSION_DEDUP_ENABLED
            if SESSION_DEDUP_ENABLED:
                from core.llm.compression.session_dedup import get_or_create_dedup_index
                dedup_idx = get_or_create_dedup_index(session)
                if message:
                    dedup_idx.index_text(message)
                resp_msg = _resp_msg
                if resp_msg:
                    dedup_idx.index_text(resp_msg)
        except Exception:
            pass  # dedup indexing must never break session updates

        # Persist to DB so chat history survives restarts. Previously this was
        # in-memory only — every server restart silently deleted all conversations.
        # Uses the ChatMessage model: conversation_id (not session_id), tenant_id
        # (required), created_at (server-default, no timestamp kwarg).
        try:
            from core.database import get_db_session
            from core.models import ChatMessage as ChatMessageModel
            session_id = session.get("id")
            tenant_id = self.tenant_id or "default"
            if session_id:
                with get_db_session() as db:
                    # R72 Workstream I — backfill channel/thread binding on the
                    # session row (covers legacy sessions created pre-fix).
                    try:
                        from core.models import ChatSession as ChatSessionModel
                        session_row = db.query(ChatSessionModel).filter(
                            ChatSessionModel.id == session_id
                        ).first()
                        if session_row:
                            if session.get("channel_id") and not session_row.channel_id:
                                session_row.channel_id = session["channel_id"]
                            if session.get("thread_id") and not session_row.thread_id:
                                session_row.thread_id = session["thread_id"]
                    except Exception:
                        # Non-fatal: session-row backfill is best-effort.
                        pass

                    # Store the user message.
                    db.add(ChatMessageModel(
                        conversation_id=session_id,
                        tenant_id=tenant_id,
                        role="user",
                        content=message,
                    ))
                    # Store the assistant response; error turns carry a
                    # metadata flag so hydration can exclude them from the
                    # model's context (they remain visible in the UI).
                    # The model's chain-of-thought rides metadata_json so
                    # history hydration re-renders it and ExchangeExample
                    # capture (feedback training) can pick it up.
                    resp_content = response.get("message", "") if isinstance(response, dict) else str(response)
                    if resp_content:
                        _msg_meta: Dict[str, Any] = {}
                        if _is_error_turn:
                            _msg_meta["quality"] = "error"
                        _turn_reasoning = response.get("reasoning") if isinstance(response, dict) else None
                        if _turn_reasoning:
                            _msg_meta["reasoning"] = str(_turn_reasoning)[:20000]
                        db.add(ChatMessageModel(
                            conversation_id=session_id,
                            tenant_id=tenant_id,
                            role="assistant",
                            content=resp_content,
                            metadata_json=json.dumps(_msg_meta) if _msg_meta else None,
                        ))
        except Exception as e:
            logger.warning(f"Could not persist chat history to DB (non-fatal): {e}")

    def _generate_error_response(self, error: str, session_id: str) -> Dict[str, Any]:
        return {
            "success": False,
            "error": error,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }

    # ==================== PHASE 30: ATOM META-AGENT HANDLER ====================
    
    async def _handle_agent_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """
        Route request to Atom Meta-Agent for complex/agent-based processing.
        Atom will analyze the request, spawn specialty agents if needed, and coordinate response.
        """
        try:
            from core.atom_meta_agent import get_atom_agent, AgentTriggerMode
            
            # Get user from session if available
            user_id = session.get("user_id", "default_user")
            session_id = session.get("id")
            
            # Get or create Atom instance
            atom = get_atom_agent()

            # Stream live ReAct steps to the Agent Workspace panel while the
            # run executes. Emission is failure-isolated (the emitter swallows
            # socket errors) so a dead WebSocket can never break the chat reply.
            # The execution id rides on the first step record; it is unknown
            # until the meta-agent creates its run.
            seen_execution = {"id": None}

            async def step_callback(step_record):
                step_exec_id = (step_record or {}).get("execution_id") or seen_execution["id"]
                seen_execution["id"] = step_exec_id
                await self._emit_agent_step(session_id, "atom_main", step_exec_id, step_record)

            await self._emit_agent_status(session_id, "atom_main", None, "running")

            # Execute through Atom
            result = await atom.execute(
                request=message,
                context={
                    "intent_analysis": intent_analysis,
                    "session_id": session_id,
                    "user_id": user_id,
                    **(context or {})
                },
                trigger_mode=AgentTriggerMode.MANUAL,
                step_callback=step_callback,
            )
            execution_id = result.get("execution_id") or seen_execution["id"]
            
            # Propagate the machine-readable budget-failure signal instead of
            # hardcoding "success". Previously the meta-agent's budget_exceeded
            # status was silently swallowed here, so no structured signal could
            # reach the HTTP layer (the user saw a normal assistant bubble).
            failure_reason = result.get("failure_reason")
            await self._emit_agent_status(
                session_id,
                "atom_main",
                execution_id,
                "failed" if failure_reason else "success",
            )
            return {
                "status": "budget_exceeded" if failure_reason else "success",
                "success": not failure_reason,
                "error_code": "budget_exceeded" if failure_reason else None,
                "failure_reason": failure_reason,
                "message": result.get("final_output"),
                "actions_taken": result.get("actions_executed", []),
                "spawned_agent": result.get("spawned_agent"),
                "feature": "agent",
            }
            
        except Exception as e:
            logger.error(f"Agent request handler failed: {e}")
            try:
                await self._emit_agent_status(
                    session.get("id") if session else None, "atom_main", None, "failed"
                )
            except Exception:
                pass
            return {
                "status": "error",
                "error": "agent_request_failed",
                "feature": "agent"
            }

    def request_cancellation(self, session_id: str) -> None:
        """Mark a session's in-flight processing as cancelled.

        Called by the POST /api/chat/cancel/{session_id} endpoint. The
        orchestrator checks _is_cancelled between processing steps and
        returns early if set. Best-effort: if the LLM call is already
        in-flight, the cancel takes effect after it returns.
        """
        self._cancelled_sessions.add(session_id)

    def _is_cancelled(self, session_id: str) -> bool:
        """Check if a session has been cancelled and clear the flag."""
        if session_id in self._cancelled_sessions:
            self._cancelled_sessions.discard(session_id)
            return True
        return False


# Global Chat Orchestrator Instance
chat_orchestrator = ChatOrchestrator()
