
from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, DateTime, Text, Table, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from core.database import Base
from core.data_visibility import DataVisibility

# Enums
class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    WORKSPACE_ADMIN = "workspace_admin"
    TEAM_LEAD = "team_lead"
    MEMBER = "member"
    GUEST = "guest"

class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"
    DELETED = "deleted"

class WorkspaceStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    EXPIRED = "expired"

# Association Tables
team_members = Table(
    'team_members',
    Base.metadata,
    Column('user_id', String, ForeignKey('users.id'), primary_key=True),
    Column('team_id', String, ForeignKey('teams.id'), primary_key=True),
    Column('role', String, default="member"),
    Column('joined_at', DateTime(timezone=True), server_default=func.now())
)

user_workspaces = Table(
    'user_workspaces',
    Base.metadata,
    Column('user_id', String, ForeignKey('users.id'), primary_key=True),
    Column('workspace_id', String, ForeignKey('workspaces.id'), primary_key=True),
    Column('role', String, default="member"),
    Column('joined_at', DateTime(timezone=True), server_default=func.now())
)

class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default=WorkspaceStatus.ACTIVE.value)
    plan_tier = Column(String, default="standard")
    
    # Autonomous Agent Guardrails
    is_startup = Column(Boolean, default=False)
    learning_phase_completed = Column(Boolean, default=False)
    metadata_json = Column(JSON, default={}) # Governance & Config
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    users = relationship("User", secondary=user_workspaces, back_populates="workspaces")
    teams = relationship("Team", back_populates="workspace")
    products_services = relationship("BusinessProductService", back_populates="workspace")

class Team(Base):
    __tablename__ = "teams"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    workspace = relationship("Workspace", back_populates="teams")
    members = relationship("User", secondary=team_members, back_populates="teams")
    messages = relationship("TeamMessage", back_populates="team")

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=True) # Nullable for SSO users
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    role = Column(String, default=UserRole.MEMBER.value)
    
    # Domain Specialty (e.g. "Accountant", "Marketer", "Sales")
    specialty = Column(String, nullable=True) 
    
    status = Column(String, default=UserStatus.ACTIVE.value)
    
    # Resource Management
    skills = Column(Text, nullable=True) # JSON string of skills
    
    # Onboarding
    onboarding_completed = Column(Boolean, default=False)
    onboarding_step = Column(String, default="welcome")
    capacity_hours = Column(Float, default=40.0) # Weekly capacity
    hourly_cost_rate = Column(Float, default=0.0) # Internal labor cost
    metadata_json = Column(JSON, nullable=True)
    preferences = Column(JSON, default={}) # User Preferences (Phase 45)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    # 2FA Fields
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String, nullable=True) # Should be encrypted in a real production app
    two_factor_backup_codes = Column(JSON, nullable=True)

    # Relationships
    workspaces = relationship("Workspace", secondary=user_workspaces, back_populates="users")
    teams = relationship("Team", secondary=team_members, back_populates="members")
    messages = relationship("TeamMessage", back_populates="sender")

class TeamMessage(Base):
    __tablename__ = "team_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    team_id = Column(String, ForeignKey("teams.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    
    # Context (e.g., 'task', 'workflow')
    context_type = Column(String, nullable=True) 
    context_id = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    team = relationship("Team", back_populates="messages")
    sender = relationship("User", back_populates="messages")

# Additional enums
class WorkflowExecutionStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"

class AuditEventType(str, enum.Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ACCESS = "access"
    EXECUTE = "execute"
    ERROR = "error"

class SecurityLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ThreatLevel(str, enum.Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

# Additional models
class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"

    execution_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String, nullable=False, index=True)
    status = Column(String, default=WorkflowExecutionStatus.PENDING.value, index=True)
    input_data = Column(Text, nullable=True)
    steps = Column(Text, nullable=True)
    outputs = Column(Text, nullable=True)
    context = Column(Text, nullable=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    error = Column(Text, nullable=True)
    # Add user_id foreign key for user binding
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    
    # Visibility scoping
    visibility = Column(String, default=DataVisibility.WORKSPACE.value, nullable=False, index=True)
    owner_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    team_id = Column(String, ForeignKey("teams.id"), nullable=True, index=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="workflow_executions")
    owner = relationship("User", foreign_keys=[owner_id])
    team = relationship("Team")

class ChatProcess(Base):
    __tablename__ = "chat_processes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    current_step = Column(Integer, default=0)
    total_steps = Column(Integer, nullable=False)
    steps = Column(Text, nullable=True)  # JSON array of step definitions
    context = Column(Text, nullable=True)  # JSON context data
    inputs = Column(Text, nullable=True)  # JSON collected inputs
    outputs = Column(Text, nullable=True)  # JSON aggregated outputs
    status = Column(String, default="active")  # active, paused, completed, cancelled
    missing_parameters = Column(Text, nullable=True)  # JSON array of missing param names
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Visibility scoping
    visibility = Column(String, default=DataVisibility.PRIVATE.value, nullable=False, index=True)
    owner_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    team_id = Column(String, ForeignKey("teams.id"), nullable=True, index=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="chat_processes")
    owner = relationship("User", foreign_keys=[owner_id])
    team = relationship("Team")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String, nullable=False)
    security_level = Column(String, nullable=False)
    threat_level = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    user_email = Column(String, nullable=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    resource = Column(String, nullable=True)
    action = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=True)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", backref="audit_logs")
    workspace = relationship("Workspace", backref="audit_logs")

class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    session_token = Column(String, nullable=False, unique=True)
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    device_type = Column(String, nullable=True)
    browser = Column(String, nullable=True)
    os = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active_at = Column(DateTime(timezone=True), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    user = relationship("User", backref="sessions")

class AgentJobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"

class HITLActionStatus(str, enum.Enum):
    """Status for Human-in-the-loop actions requiring user approval"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"

class AgentJob(Base):
    __tablename__ = "agent_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, nullable=False)
    status = Column(String, default=AgentJobStatus.PENDING.value)
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True)
    logs = Column(Text, nullable=True) # JSON Logs
    result_summary = Column(Text, nullable=True) # JSON Result

class BusinessProductService(Base):
    """Catalog of products or services provided by a business"""
    __tablename__ = "business_product_services"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    external_id = Column(String, nullable=True, index=True) # ID from legacy system
    name = Column(String, nullable=False)
    type = Column(String, default="service") # product, service
    description = Column(Text, nullable=True)
    base_price = Column(Float, default=0.0)
    unit_cost = Column(Float, default=0.0) # COGS for tangible products
    currency = Column(String, default="USD")
    stock_quantity = Column(Integer, default=0) # For tangible products
    
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    workspace = relationship("Workspace", back_populates="products_services")

class BusinessRule(Base):
    """Logical rules or calculation patterns extracted from business docs"""
    __tablename__ = "business_rules"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    description = Column(String, nullable=False)
    rule_type = Column(String, nullable=False) # pricing, discount, tax, workflow
    formula = Column(Text, nullable=True) # e.g., "base_price * 1.2"
    value = Column(Float, nullable=True) # Fixed value if applicable
    applies_to = Column(String, nullable=True) # Entity or category this applies to
    is_active = Column(Boolean, default=True)
    
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class HITLAction(Base):
    """Actions paused for manual review (Phase 70)"""
    __tablename__ = "hitl_actions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    agent_id = Column(String, nullable=True) # ID of the agent that initiated the action
    action_type = Column(String, nullable=False) # e.g., "send_message"
    platform = Column(String, nullable=False) # e.g., "whatsapp", "meta"
    params = Column(JSON, nullable=False) # Serialized action parameters
    
    status = Column(String, default=HITLActionStatus.PENDING.value)
    reason = Column(String, nullable=True) # e.g., "Learning Phase: External Contact"
    
    # Ownership
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    
    confidence_score = Column(Float, default=0.0)
    user_feedback = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(String, ForeignKey("users.id"), nullable=True)

    # Relationships
    workspace = relationship("Workspace", backref="hitl_actions")
    reviewer = relationship("User", foreign_keys=[reviewed_by], backref="reviewed_hitl_actions")

class AgentStatus(str, enum.Enum):
    STUDENT = "student"       # Initial phase, high supervision
    INTERN = "intern"         # Learning, needs approval
    SUPERVISED = "supervised" # Operational but monitored
    AUTONOMOUS = "autonomous" # Fully trusted
    PAUSED = "paused"
    DEPRECATED = "deprecated"

class FeedbackStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

class AgentRegistry(Base):
    """Registry for AI Agents and their governance state"""
    __tablename__ = "agent_registry"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=False) # e.g., "Operations", "Finance"
    
    # Technical Config
    module_path = Column(String, nullable=False) # e.g., "operations.automations.inventory"
    class_name = Column(String, nullable=False)
    
    # Ownership
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)

    
    # Governance
    status = Column(String, default=AgentStatus.STUDENT.value)
    confidence_score = Column(Float, default=0.5) # 0.0 to 1.0
    required_role_for_autonomy = Column(String, default=UserRole.TEAM_LEAD.value)
    
    version = Column(String, default="1.0.0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Flexible Configuration
    configuration = Column(JSON, default={}) # System prompts, tools, constraints
    schedule_config = Column(JSON, default={}) # Cron expression, active status

class AgentFeedback(Base):
    """User feedback on agent actions for RLHF"""
    __tablename__ = "agent_feedback"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # The Interaction
    input_context = Column(Text, nullable=True) # What triggered the agent
    original_output = Column(Text, nullable=False) # What the agent did/said
    user_correction = Column(Text, nullable=False) # What the user said it should be
    
    # Adjudication
    status = Column(String, default=FeedbackStatus.PENDING.value)
    ai_reasoning = Column(Text, nullable=True) # AI judge's explanation
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    adjudicated_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    agent = relationship("AgentRegistry", backref="feedback_history")
    user = relationship("User", backref="submitted_feedback")

class IntegrationCatalog(Base):
    """Native catalog of integration pieces available in the platform"""
    __tablename__ = "integration_catalog"

    id = Column(String, primary_key=True) # Usually the piece name/slug
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=False)
    icon = Column(String, nullable=True)
    color = Column(String, default="#6366F1")
    auth_type = Column(String, default="none")
    
    # Link to native implementation if exists (e.g., "slack", "gmail")
    native_id = Column(String, nullable=True)
    
    # Store actions/triggers as JSON for flexibility
    triggers = Column(JSON, default=list)
    actions = Column(JSON, default=list)
    
    popular = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class UserConnection(Base):
    """Securely stores OAuth credentials and other auth data for users"""
    __tablename__ = "user_connections"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=True, index=True)
    
    # integration_id matches piece name, e.g., "@activepieces/piece-slack" or native "slack"
    integration_id = Column(String, nullable=False, index=True)
    connection_name = Column(String, nullable=False) # User-defined name
    
    # Encrypted credentials JSON
    credentials = Column(JSON, nullable=False)
    
    status = Column(String, default="active") # active, expired, revoked
    last_used = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="connections")
    workspace = relationship("Workspace", backref="connections")

class WorkflowSnapshot(Base):
    """
    Time-Travel Debugging: Immutable snapshot of execution state at a specific step.
    This acts as a 'Save Point' allowing users to fork/replay from this exact moment.
    """
    __tablename__ = "workflow_snapshots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(String, ForeignKey("workflow_executions.execution_id"), nullable=False, index=True)
    step_id = Column(String, nullable=False) # The step that just finished/is current
    step_order = Column(Integer, nullable=False) # Sequence number (0, 1, 2...)
    
    # State Capture
    context_snapshot = Column(Text, nullable=False) # Full JSON dump of WorkflowContext (vars, results)
    
    # Metadata
    status = Column(String, nullable=False) # Status at this snapshot (e.g. COMPLETED, FAILED)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    execution = relationship("WorkflowExecution", backref="snapshots")
class IngestedDocument(Base):
    """Record of an ingested document from a service like Google Drive"""
    __tablename__ = "ingested_documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    tenant_id = Column(String, nullable=True, index=True) # Upstream might use tenant parity later
    
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    integration_id = Column(String, nullable=False, index=True)
    
    file_size_bytes = Column(Integer, default=0)
    content_preview = Column(Text, nullable=True)
    
    external_id = Column(String, nullable=False, index=True) # ID in source system
    external_modified_at = Column(DateTime(timezone=True), nullable=True)
    
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class IngestionSettings(Base):
    """Settings for document ingestion per integration"""
    __tablename__ = "ingestion_settings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    integration_id = Column(String, nullable=False, index=True)
    
    enabled = Column(Boolean, default=False)
    auto_sync_new_files = Column(Boolean, default=True)
    file_types = Column(JSON, default=list) # ["pdf", "docx"]
    sync_folders = Column(JSON, default=list)
    exclude_folders = Column(JSON, default=list)
    max_file_size_mb = Column(Integer, default=50)
    sync_frequency_minutes = Column(Integer, default=60)
    
    last_sync = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class IntegrationMetric(Base):
    """
    Stores cached analytics data for dashboards (Sync Strategy).
    Avoids real-time API rate limits and high latency.
    """
    __tablename__ = "integration_metrics"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    
    integration_type = Column(String, nullable=False) # "salesforce", "hubspot", "stripe"
    metric_key = Column(String, nullable=False) # "total_revenue", "pipeline_count", "lead_conversion_rate"
    
    # Store value as JSON to handle scalars (10.5) or time-series ([{date: v}, ...])
    value = Column(JSON, nullable=False) 
    
    unit = Column(String, default="count") # "usd", "percent", "count"
    timeframe = Column(String, default="current") # "30d", "current"
    
    last_synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, nullable=False, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)  # 'user', 'assistant', etc.
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    tenant_id = Column(String, default="default", index=True)
    title = Column(String, nullable=True) # First message summary or custom title
    metadata_json = Column(JSON, default={}) # For storing 'source', 'context', etc.
    
    # Tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    message_count = Column(Integer, default=0)

    # Relationships (Optional explicit link, or logical via conversation_id)
    # messages = relationship("ChatMessage", backref="session", cascade="all, delete-orphan")

# ==================== GRAPHRAG MODELS ====================

class GraphNode(Base):
    __tablename__ = "graph_nodes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    properties = Column(JSON, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    workspace = relationship("Workspace", backref="graph_nodes")

class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    source_node_id = Column(String, ForeignKey("graph_nodes.id"), nullable=False, index=True)
    target_node_id = Column(String, ForeignKey("graph_nodes.id"), nullable=False, index=True)
    relationship_type = Column(String, nullable=False)
    properties = Column(JSON, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    source_node = relationship("GraphNode", foreign_keys=[source_node_id], backref="out_edges")
    target_node = relationship("GraphNode", foreign_keys=[target_node_id], backref="in_edges")

class GraphCommunity(Base):
    __tablename__ = "graph_communities"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    name = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    keywords = Column(JSON, default=list) # List[str]
    level = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    workspace = relationship("Workspace", backref="graph_communities")

class CommunityMembership(Base):
    __tablename__ = "community_memberships"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    community_id = Column(String, ForeignKey("graph_communities.id"), nullable=False)
    node_id = Column(String, ForeignKey("graph_nodes.id"), nullable=False)
    rank = Column(Integer, default=0)

    # Relationships
    community = relationship("GraphCommunity", backref="members")
    node = relationship("GraphNode", backref="communities")
