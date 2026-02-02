
from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, DateTime, Text, Table, JSON, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
import uuid
import enum
from core.database import Base
from core.data_visibility import DataVisibility

# Enums
class UserRole(str, enum.Enum):
    """
    Consolidated user roles for access control.

    Combines both workspace and enterprise roles into a single enum.
    Roles are hierarchical in terms of permissions:
    - SUPER_ADMIN: Full system access
    - SECURITY_ADMIN: Security settings and user management
    - WORKSPACE_ADMIN: Workspace management and billing
    - WORKFLOW_ADMIN: Workflow creation and management
    - AUTOMATION_ADMIN: Automation rule management
    - INTEGRATION_ADMIN: Third-party integrations
    - COMPLIANCE_ADMIN: Compliance and audit logs
    - TEAM_LEAD: Team management and reporting
    - MEMBER: Standard user with execution permissions
    - GUEST: Read-only access
    """
    # System-wide roles
    SUPER_ADMIN = "super_admin"

    # Enterprise admin roles
    SECURITY_ADMIN = "security_admin"
    WORKSPACE_ADMIN = "workspace_admin"
    WORKFLOW_ADMIN = "workflow_admin"
    AUTOMATION_ADMIN = "automation_admin"
    INTEGRATION_ADMIN = "integration_admin"
    COMPLIANCE_ADMIN = "compliance_admin"

    # Workspace roles
    TEAM_LEAD = "team_lead"
    MEMBER = "member"
    GUEST = "guest"

    # Legacy alias for backwards compatibility
    ADMIN = "workspace_admin"  # Maps to WORKSPACE_ADMIN

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
    satellite_api_key = Column(String, nullable=True, unique=True, index=True)
    
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
    graph_nodes = relationship("GraphNode", back_populates="workspace", cascade="all, delete-orphan")
    graph_communities = relationship("GraphCommunity", back_populates="workspace", cascade="all, delete-orphan")

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

    # Email Verification
    email_verified = Column(Boolean, default=False)

    # Tenant/Multi-tenancy
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True, index=True)

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


class WorkflowExecutionLog(Base):
    """Execution logs for workflow runs"""
    __tablename__ = "workflow_execution_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(String, ForeignKey("workflow_executions.execution_id"), nullable=False, index=True)

    level = Column(String, default="INFO")  # DEBUG, INFO, WARNING, ERROR
    message = Column(Text, nullable=False)
    step_id = Column(String, nullable=True)
    context = Column(JSON, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    execution = relationship("WorkflowExecution", backref="logs")

    __table_args__ = (
        Index('ix_workflow_execution_logs_execution', 'execution_id'),
    )


class WorkflowStepExecution(Base):
    """Step-level execution tracking for workflows"""
    __tablename__ = "workflow_step_executions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(String, ForeignKey("workflow_executions.execution_id"), nullable=False, index=True)
    workflow_id = Column(String, nullable=False, index=True)

    step_id = Column(String, nullable=False, index=True)
    step_name = Column(String, nullable=False)
    step_type = Column(String, nullable=False)  # trigger, action, condition
    sequence_order = Column(Integer, nullable=False)

    status = Column(String, default="pending")  # pending, running, completed, failed, skipped

    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)

    retry_count = Column(Integer, default=0)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    execution = relationship("WorkflowExecution", backref="step_executions")

    __table_args__ = (
        Index('ix_workflow_step_executions_execution', 'execution_id'),
        Index('ix_workflow_step_executions_step', 'step_id'),
    )

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

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", backref="password_reset_tokens")

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
    agent_execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # The Interaction
    input_context = Column(Text, nullable=True) # What triggered the agent
    original_output = Column(Text, nullable=False) # What the agent did/said
    user_correction = Column(Text, nullable=False) # What the user said it should be

    # Enhanced Feedback (NEW)
    feedback_type = Column(String, nullable=True, index=True) # correction, rating, approval, comment
    thumbs_up_down = Column(Boolean, nullable=True) # Quick feedback (true=up, false=down)
    rating = Column(Integer, nullable=True, index=True) # 1-5 stars

    # Adjudication
    status = Column(String, default=FeedbackStatus.PENDING.value)
    ai_reasoning = Column(Text, nullable=True) # AI judge's explanation

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    adjudicated_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    agent = relationship("AgentRegistry", backref="feedback_history")
    execution = relationship("AgentExecution", backref="feedback")
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
    workspace_id = Column(String, nullable=False, index=True) # Standardized for Upstream
    role = Column(String, nullable=False)  # 'user', 'assistant', etc.
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
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
    """
    Represents an entity in the Knowledge Graph (Person, Project, Document).
    """
    __tablename__ = "graph_nodes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False) # e.g., 'person', 'task', 'document'
    description = Column(Text, nullable=True)
    properties = Column(JSON, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    workspace = relationship("Workspace", back_populates="graph_nodes")

class GraphEdge(Base):
    """
    Represents a relationship between two entities.
    """
    __tablename__ = "graph_edges"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    source_node_id = Column(String, ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_node_id = Column(String, ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = Column(String, nullable=False)
    weight = Column(Float, default=1.0)
    properties = Column(JSON, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    source_node = relationship("GraphNode", foreign_keys=[source_node_id], backref="out_edges")
    target_node = relationship("GraphNode", foreign_keys=[target_node_id], backref="in_edges")

class GraphCommunity(Base):
    """
    Hierarchical clusters detected by Leiden algorithm.
    Used for Global Search (Map-Reduce).
    """
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
    workspace = relationship("Workspace", back_populates="graph_communities")

class CommunityMembership(Base):
    """Mapping of Nodes to Communities"""
    __tablename__ = "community_memberships"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    community_id = Column(String, ForeignKey("graph_communities.id", ondelete="CASCADE"), nullable=False)
    node_id = Column(String, ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False)
    rank = Column(Integer, default=0)

    # Relationships
    community = relationship("GraphCommunity", backref="members")
    node = relationship("GraphNode", backref="communities")


class SkillExecution(Base):
    """
    Execution record for skill runs with ACU billing tracking.

    Container skills (cloud execution) track compute usage in ACUs.
    Docker skills (local only) do NOT incur ACU charges.
    """
    __tablename__ = "skill_executions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
    skill_id = Column(String, nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True) # Standardized for Upstream

    status = Column(String, default="pending")
    input_params = Column(JSON, nullable=True)
    output_result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    # ACU Billing (1 ACU = 1 second of compute)
    execution_seconds = Column(Float, default=0.0)
    cpu_count = Column(Integer, nullable=True)
    memory_mb = Column(Integer, nullable=True)
    compute_billed = Column(Boolean, default=False)

    # Infrastructure metadata
    machine_id = Column(String, nullable=True)

    # Legacy timing (ms for non-compute skills)
    execution_time_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    agent = relationship("AgentRegistry", backref="skill_executions")
    workspace = relationship("Workspace", backref="skill_executions")

class AgentExecution(Base):
    """
    Detailed execution record for an Agent run (Phase 30).
    Replaces simpler AgentJob for detailed tracing.
    """
    __tablename__ = "agent_executions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
    workspace_id = Column(String, nullable=True, index=True)

    status = Column(String, default="running")
    input_summary = Column(Text, nullable=True)
    output_summary = Column(Text, nullable=True)
    triggered_by = Column(String, default="manual") # manual, schedule, websocket, event

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, default=0.0)

    result_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    agent = relationship("AgentRegistry")
    # Note: workspace relationship removed - workspace_id is a string reference without FK constraint


class CanvasAudit(Base):
    """
    Audit trail for canvas actions with governance tracking.
    Records all presentations (charts, markdown, forms) and submissions.

    Extended with session_id for session isolation (February 2026).
    Extended with canvas_type for specialized canvas support (February 2026).
    """
    __tablename__ = "canvas_audit"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, nullable=True, index=True)
    agent_id = Column(String, nullable=True, index=True)
    agent_execution_id = Column(String, nullable=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    canvas_id = Column(String, nullable=True, index=True)
    session_id = Column(String, nullable=True, index=True)  # Session isolation (NEW)
    canvas_type = Column(String, default="generic", nullable=False, index=True)  # 'generic', 'docs', 'email', 'sheets', 'orchestration', 'terminal', 'coding' (NEW)
    component_type = Column(String, nullable=False)  # 'chart', 'markdown', 'form', etc.
    component_name = Column(String, nullable=True)  # 'line_chart', 'bar_chart', etc.
    action = Column(String, nullable=False)  # 'present', 'close', 'submit', 'update'
    audit_metadata = Column(JSON, default={})  # Renamed from 'metadata' (reserved)
    governance_check_passed = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

class AgentOperationTracker(Base):
    """
    Real-time tracking of agent operations for canvas visibility.

    Provides transparency into what agents are doing with step-by-step progress,
    context explanations, and operation logs.
    """
    __tablename__ = "agent_operation_tracker"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)

    # Operation details
    operation_type = Column(String, nullable=False, index=True)  # integration_connect, browser_automate, workflow_execute
    operation_id = Column(String, nullable=False, unique=True, index=True)
    current_step = Column(String, nullable=True)
    total_steps = Column(Integer, nullable=True)
    current_step_index = Column(Integer, default=0)
    status = Column(String, default="running", index=True)  # running, waiting, completed, failed
    progress = Column(Integer, default=0)  # 0-100

    # Agent guidance context
    what_explanation = Column(Text, nullable=True)  # Plain English: what agent is doing
    why_explanation = Column(Text, nullable=True)   # Why agent is doing this
    next_steps = Column(Text, nullable=True)        # What happens next

    # Operation metadata
    operation_metadata = Column(JSON, default=dict)
    logs = Column(JSON, default=list)  # [{timestamp, level, message}]

    # Timing
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    agent = relationship("AgentRegistry", backref="tracked_operations")


class AgentRequestLog(Base):
    """
    Log of agent requests for user input/decisions.

    Records all instances where agents ask users for permissions, decisions,
    or input with full audit trail for governance.
    """
    __tablename__ = "agent_request_log"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    request_id = Column(String, nullable=False, unique=True, index=True)

    # Request details
    request_type = Column(String, nullable=False, index=True)  # permission, input, decision, confirmation
    request_data = Column(JSON, nullable=False)  # Full request with title, options, context
    user_response = Column(JSON, nullable=True)  # User's choice
    response_time_seconds = Column(Float, nullable=True)

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    responded_at = Column(DateTime(timezone=True), nullable=True)

    # Governance
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked = Column(Boolean, default=False)

    # Relationships
    agent = relationship("AgentRegistry", backref="user_requests")


class ViewOrchestrationState(Base):
    """
    State for multi-view coordination (browser, terminal, canvas).

    Manages which views are active, their layout, and which agent is controlling them.
    """
    __tablename__ = "view_orchestration_state"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(String, nullable=False, unique=True, index=True)

    # Active views
    active_views = Column(JSON, default=list)  # [{view_id, view_type, status, position, size}]
    layout = Column(String, default="canvas")  # canvas, split_horizontal, split_vertical, tabs, grid
    controlling_agent = Column(String, ForeignKey("agent_registry.id"), nullable=True)

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    agent = relationship("AgentRegistry", backref="orchestrated_views")


class OperationErrorResolution(Base):
    """
    Track error resolutions for learning and improvement.

    Records which resolutions work for which error types to improve
    future suggestions and enable agent auto-fix capabilities.
    """
    __tablename__ = "operation_error_resolutions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    error_type = Column(String, nullable=False, index=True)
    error_code = Column(String, nullable=True, index=True)

    # Resolution details
    resolution_attempted = Column(String, nullable=False)  # Which resolution option was used
    success = Column(Boolean, nullable=False, index=True)
    user_feedback = Column(Text, nullable=True)  # Did it work? Any issues?

    # Metadata
    agent_suggested = Column(Boolean, default=True)  # Was agent suggestion used?
    alternative_used = Column(Text, nullable=True)  # If user used different solution

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AgentTraceStep(Base):
    """
    Persisted reasoning step for an agent execution (ReAct thought/action).
    """
    __tablename__ = "agent_trace_steps"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(String, ForeignKey("agent_executions.id", ondelete="CASCADE"), nullable=False, index=True)

    step_number = Column(Integer, nullable=False)

    thought = Column(Text, nullable=True)
    action = Column(JSON, nullable=True) # {tool: str, params: dict}
    observation = Column(Text, nullable=True)
    final_answer = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    execution = relationship("AgentExecution", backref="trace_steps")


class BrowserSession(Base):
    """
    Browser session tracking for browser automation.

    Records all browser sessions created by agents with full audit trail.
    """
    __tablename__ = "browser_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, nullable=False, unique=True, index=True)  # External session ID
    workspace_id = Column(String, nullable=True, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)
    agent_execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=True, index=True)
    # ... rest of BrowserSession if exists in file ...

class Artifact(Base):
    """
    Persistent AI-generated artifacts (code, markdown, etc.) that can be edited by users.
    """
    __tablename__ = "artifacts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)
    session_id = Column(String, nullable=True, index=True) # Logical link to chat session
    
    name = Column(String, nullable=False)
    type = Column(String, nullable=False) # 'code', 'markdown', etc.
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, default={})
    
    version = Column(Integer, default=1)
    is_locked = Column(Boolean, default=False)
    locked_by_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    author_id = Column(String, ForeignKey("users.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Relationships
    author = relationship("User", foreign_keys=[author_id])
    locked_by = relationship("User", foreign_keys=[locked_by_user_id])
    workspace = relationship("Workspace")

class ArtifactVersion(Base):
    """
    Immutable snapshots of artifact states for time-travel/versioning.
    """
    __tablename__ = "artifact_versions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    artifact_id = Column(String, ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, default={})
    
    author_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    artifact = relationship("Artifact", backref="versions")
    author = relationship("User")
    
    # Session Details
    url = Column(String, nullable=True)
    title = Column(String, nullable=True)
    status = Column(String, default="active") # active, closed, error
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)

class DeviceNode(Base):
    """
    Registry of compute nodes (Desktop, Mobile, Cloud) available for orchestration.
    Backported from Atom SaaS for standard device targeting.
    """
    __tablename__ = "device_nodes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)

    # Node Identity
    name = Column(String, nullable=False)
    device_id = Column(String, nullable=False, index=True) # Unique hardware/client ID
    node_type = Column(String, nullable=False) # desktop_windows, desktop_mac, mobile_ios, etc.

    # Connectivity
    status = Column(String, default="offline") # online, offline, busy
    last_seen = Column(DateTime(timezone=True), server_default=func.now())

    # Capabilities (JSON list of strings)
    capabilities = Column(JSON, default=[]) # e.g. ["browser", "terminal", "file_system"]
    capabilities_detailed = Column(JSON, nullable=True)  # Detailed capability info

    # Platform information
    platform = Column(String, nullable=True)  # darwin, windows, linux
    platform_version = Column(String, nullable=True)
    architecture = Column(String, nullable=True)  # x86_64, arm64, etc.

    # Version information
    tauri_version = Column(String, nullable=True)
    app_version = Column(String, nullable=True)
    version = Column(String, nullable=True)  # Legacy, keep for compatibility

    # Hardware information
    hardware_info = Column(JSON, nullable=True)  # CPU, RAM, GPU, etc.

    # Metadata
    metadata_json = Column(JSON, default={})

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    workspace = relationship("Workspace", backref="device_nodes")
    user_id = Column(String, nullable=False, index=True)

class DeviceSession(Base):
    """
    Device session tracking for device operations.

    Records ongoing device sessions (camera, screen recording, command execution)
    with full audit trail and governance tracking.
    """
    __tablename__ = "device_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, nullable=False, unique=True, index=True)  # External session ID
    workspace_id = Column(String, nullable=True, index=True)
    device_node_id = Column(String, nullable=False, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)
    agent_execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=True, index=True)
    user_id = Column(String, nullable=False, index=True)

    # Session details
    session_type = Column(String, nullable=False)  # camera, screen_record, command, location, notification
    status = Column(String, default="active")  # active, closed, error
    configuration = Column(JSON, nullable=True)  # Session-specific configuration

    # Metadata
    metadata_json = Column(JSON, nullable=True)
    governance_check_passed = Column(Boolean, nullable=True)

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    agent = relationship("AgentRegistry")
    execution = relationship("AgentExecution")

class DeviceAudit(Base):
    """
    Audit trail for device automation actions.

    Records all device operations (camera, screen recording, location, notifications,
    command execution) with full governance tracking and attribution.
    """
    __tablename__ = "device_audit"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, nullable=True, index=True)
    agent_id = Column(String, nullable=True, index=True)
    agent_execution_id = Column(String, nullable=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    device_node_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=True, index=True)

    # Action details
    action_type = Column(String, nullable=False)  # camera_snap, screen_record_start, location, etc.
    action_params = Column(JSON, nullable=True)  # Full parameters for reproducibility

    # Results
    success = Column(Boolean, nullable=False)
    result_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    result_data = Column(JSON, nullable=True)  # Structured result data
    file_path = Column(Text, nullable=True)  # For camera/screen recordings

    # Metadata
    duration_ms = Column(Integer, nullable=True)
    governance_check_passed = Column(Boolean, nullable=True)

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class BrowserAudit(Base):
    """
    Audit trail for browser automation actions.

    Records all browser operations (navigate, click, fill, screenshot, etc.)
    with full governance tracking and attribution.
    """
    __tablename__ = "browser_audit"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, nullable=True, index=True)
    agent_id = Column(String, nullable=True, index=True)
    agent_execution_id = Column(String, nullable=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    session_id = Column(String, ForeignKey("browser_sessions.session_id"), nullable=False, index=True)

    # Action details
    action_type = Column(String, nullable=False)  # navigate, click, fill, screenshot, extract, execute
    action_target = Column(Text, nullable=True)  # URL, selector, script, etc.
    action_params = Column(JSON, default={})  # Full parameters for reproducibility

    # Results
    success = Column(Boolean, nullable=False)
    result_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    result_data = Column(JSON, default={})  # Structured result data

    # Metadata
    duration_ms = Column(Integer, nullable=True)
    governance_check_passed = Column(Boolean, nullable=True)

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    session = relationship("BrowserSession", backref="actions")


class DeepLinkAudit(Base):
    """
    Audit trail for deep link invocations.

    Records all deep link executions (agent, workflow, canvas, tool)
    with full governance tracking and attribution.
    """
    __tablename__ = "deep_link_audit"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, nullable=True, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)
    agent_execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=True, index=True)
    user_id = Column(String, nullable=False, index=True)

    # Deep link details
    resource_type = Column(String, nullable=False)  # 'agent', 'workflow', 'canvas', 'tool'
    resource_id = Column(String, nullable=False)
    action = Column(String, nullable=False)
    source = Column(String, default="external")  # external_app, browser, etc.

    # Full context
    deeplink_url = Column(Text, nullable=False)
    parameters = Column(JSON, nullable=True)

    # Results
    status = Column(String, default="success")  # success, failed, error
    error_message = Column(Text, nullable=True)
    governance_check_passed = Column(Boolean, nullable=True)

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    agent = relationship("AgentRegistry")
    execution = relationship("AgentExecution")


class ABTest(Base):
    """
    A/B Test for comparing agent configurations, prompts, or strategies.

    Enables controlled experiments to measure the impact of changes
    on agent performance, user satisfaction, and key metrics.
    """
    __tablename__ = "ab_tests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Test configuration
    status = Column(String, default="draft")  # draft, running, paused, completed
    test_type = Column(String, nullable=False)  # agent_config, prompt, strategy, tool
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)

    # Traffic allocation
    traffic_percentage = Column(Float, default=0.5)  # 0.0 to 1.0 (e.g., 0.5 = 50% to variant B)
    variant_a_name = Column(String, default="Control")
    variant_b_name = Column(String, default="Treatment")

    # Configuration for each variant
    variant_a_config = Column(JSON, nullable=True)  # Control configuration
    variant_b_config = Column(JSON, nullable=True)  # Treatment configuration

    # Success metrics
    primary_metric = Column(String, nullable=False)  # satisfaction_rate, success_rate, response_time, etc.
    secondary_metrics = Column(JSON, nullable=True)  # List of additional metrics to track

    # Statistical parameters
    min_sample_size = Column(Integer, default=100)
    confidence_level = Column(Float, default=0.95)  # 95% confidence
    statistical_significance_threshold = Column(Float, default=0.05)  # p-value threshold

    # Results
    variant_a_metrics = Column(JSON, nullable=True)  # Aggregated metrics for variant A
    variant_b_metrics = Column(JSON, nullable=True)  # Aggregated metrics for variant B
    statistical_significance = Column(Float, nullable=True)  # p-value
    winner = Column(String, nullable=True)  # 'A', 'B', or 'inconclusive'

    # Timestamps
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    agent = relationship("AgentRegistry", backref="ab_tests")
    test_participants = relationship("ABTestParticipant", backref="test", cascade="all, delete-orphan")


class ABTestParticipant(Base):
    """
    Individual participants in an A/B test.

    Tracks which variant each user was assigned to and their outcomes.
    """
    __tablename__ = "ab_test_participants"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    test_id = Column(String, ForeignKey("ab_tests.id"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=True, index=True)

    # Assignment
    assigned_variant = Column(String, nullable=False)  # 'A' or 'B'
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())

    # Outcomes (tracked based on primary_metric)
    success = Column(Boolean, nullable=True)
    metric_value = Column(Float, nullable=True)  # Numerical value (e.g., satisfaction score, response time)
    recorded_at = Column(DateTime(timezone=True), nullable=True)

    # Additional metadata
    meta_data = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Index for querying active participants
    __table_args__ = (
        Index('ix_ab_test_participants_test_variant', 'test_id', 'assigned_variant'),
    )


class CanvasCollaborationSession(Base):
    """
    Multi-agent collaboration session for shared canvases.

    Enables multiple agents to work together on a single canvas with
    defined roles, permissions, and conflict resolution.
    """
    __tablename__ = "canvas_collaboration_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    canvas_id = Column(String, nullable=False, index=True)  # Links to canvas
    session_id = Column(String, nullable=False, index=True)  # Links to canvas session
    user_id = Column(String, nullable=False, index=True)  # Owner user

    # Session configuration
    status = Column(String, default="active")  # active, paused, completed
    collaboration_mode = Column(String, default="sequential")  # sequential, parallel, locked
    max_agents = Column(Integer, default=5)  # Maximum agents in session

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    participants = relationship("CanvasAgentParticipant", back_populates="collaboration_session", cascade="all, delete-orphan")


class CanvasAgentParticipant(Base):
    """
    Individual agent participant in a canvas collaboration session.

    Tracks agent role, permissions, and activity within the session.
    """
    __tablename__ = "canvas_agent_participants"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    collaboration_session_id = Column(String, ForeignKey("canvas_collaboration_sessions.id"), nullable=False, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)  # User who initiated this agent

    # Agent role and permissions
    role = Column(String, default="contributor")  # owner, contributor, reviewer, viewer
    permissions = Column(JSON, default={})  # Can read, write, delete specific components

    # Activity tracking
    status = Column(String, default="active")  # active, idle, completed
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now())
    actions_count = Column(Integer, default=0)  # Number of actions performed

    # Lock management for parallel mode
    held_locks = Column(JSON, default=list)  # List of component_ids locked by this agent

    # Timing
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    left_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    collaboration_session = relationship("CanvasCollaborationSession", back_populates="participants")
    agent = relationship("AgentRegistry")

    # Index for querying active agents in a session
    __table_args__ = (
        Index('ix_canvas_agent_participants_session_agent', 'collaboration_session_id', 'agent_id'),
        Index('ix_canvas_agent_participants_session_status', 'collaboration_session_id', 'status'),
    )


class CanvasConflict(Base):
    """
    Conflict resolution log for multi-agent canvas updates.

    Tracks when multiple agents try to modify the same canvas element
    simultaneously and how the conflict was resolved.
    """
    __tablename__ = "canvas_conflicts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    collaboration_session_id = Column(String, ForeignKey("canvas_collaboration_sessions.id"), nullable=False, index=True)
    canvas_id = Column(String, nullable=False, index=True)
    component_id = Column(String, nullable=False)  # ID of the contested component

    # Conflicting agents
    agent_a_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
    agent_b_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)

    # Actions
    agent_a_action = Column(JSON, nullable=True)  # What agent A tried to do
    agent_b_action = Column(JSON, nullable=True)  # What agent B tried to do

    # Resolution
    resolution = Column(String, nullable=False)  # agent_a_wins, agent_b_wins, merged, queued
    resolved_by = Column(String, nullable=True)  # 'system' or agent_id if manual resolution
    resolved_action = Column(JSON, nullable=True)  # Final action taken

    # Timing
    conflict_time = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    collaboration_session = relationship("CanvasCollaborationSession")
    agent_a = relationship("AgentRegistry", foreign_keys=[agent_a_id])
    agent_b = relationship("AgentRegistry", foreign_keys=[agent_b_id])


class CustomComponent(Base):
    """
    Custom HTML/CSS/JS components for canvas presentations.

    Allows users to create reusable custom components with:
    - HTML structure
    - CSS styling
    - JavaScript behavior
    - Version tracking
    - Governance requirements
    """
    __tablename__ = "custom_components"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    # Component identification
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True, index=True)  # URL-friendly identifier
    description = Column(Text, nullable=True)
    category = Column(String, default="custom")  # 'chart', 'form', 'widget', 'custom'

    # Component code
    html_content = Column(Text, nullable=True)
    css_content = Column(Text, nullable=True)
    js_content = Column(Text, nullable=True)

    # Component metadata
    props_schema = Column(JSON, nullable=True)  # JSON schema for component properties
    default_props = Column(JSON, nullable=True)  # Default property values
    dependencies = Column(JSON, nullable=True)  # External dependencies (libraries, etc.)

    # Governance
    requires_governance = Column(Boolean, default=True)
    min_maturity_level = Column(String, default="AUTONOMOUS")  # Only AUTONOMOUS agents can create JS components
    is_public = Column(Boolean, default=False)  # Share with other users
    is_active = Column(Boolean, default=True)

    # Usage tracking
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Version control
    current_version = Column(Integer, default=1)
    parent_component_id = Column(String, ForeignKey("custom_components.id"), nullable=True)

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User")
    versions = relationship("ComponentVersion", back_populates="component", cascade="all, delete-orphan")
    usage_logs = relationship("ComponentUsage", back_populates="component", cascade="all, delete-orphan")
    parent = relationship("CustomComponent", remote_side=[id])

    # Indexes
    __table_args__ = (
        Index('ix_custom_components_workspace_user', 'workspace_id', 'user_id'),
        Index('ix_custom_components_category', 'category'),
        Index('ix_custom_components_is_active', 'is_active'),
        Index('ix_custom_components_is_public', 'is_public'),
    )


class ComponentVersion(Base):
    """
    Version history for custom components.

    Tracks all changes to components with ability to rollback.
    """
    __tablename__ = "component_versions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    component_id = Column(String, ForeignKey("custom_components.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)

    # Version code snapshot
    html_content = Column(Text, nullable=True)
    css_content = Column(Text, nullable=True)
    js_content = Column(Text, nullable=True)
    props_schema = Column(JSON, nullable=True)
    default_props = Column(JSON, nullable=True)
    dependencies = Column(JSON, nullable=True)

    # Change metadata
    change_description = Column(Text, nullable=True)
    changed_by = Column(String, ForeignKey("users.id"), nullable=True)
    change_type = Column(String, default="update")  # 'create', 'update', 'rollback'

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    component = relationship("CustomComponent", back_populates="versions")
    changer = relationship("User")

    # Unique constraint
    __table_args__ = (
        Index('ix_component_versions_component_version', 'component_id', 'version_number', unique=True),
    )


class ComponentUsage(Base):
    """
    Usage audit log for custom components.

    Tracks when and where components are used on canvases.
    """
    __tablename__ = "component_usage"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    component_id = Column(String, ForeignKey("custom_components.id"), nullable=False, index=True)
    canvas_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)

    # Usage context
    props_passed = Column(JSON, nullable=True)  # Properties passed to component
    rendering_time_ms = Column(Integer, nullable=True)  # Performance tracking
    error_message = Column(Text, nullable=True)  # Any rendering errors

    # Governance
    governance_check_passed = Column(Boolean, nullable=True)
    agent_maturity_level = Column(String, nullable=True)

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    component = relationship("CustomComponent", back_populates="usage_logs")
    agent = relationship("AgentRegistry")

    # Indexes
    __table_args__ = (
        Index('ix_component_usage_component_canvas', 'component_id', 'canvas_id'),
        Index('ix_component_usage_session', 'session_id'),
    )


class WorkflowTemplate(Base):
    """
    User-created workflow templates for reusable workflow patterns.

    Templates allow users to save workflows as reusable patterns with
    parameterization for customization.
    """
    __tablename__ = "workflow_templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id = Column(String, unique=True, nullable=False, index=True)

    # Metadata
    name = Column(String, nullable=False)
    description = Column(Text)
    category = Column(String, nullable=False)  # automation, data_processing, ai_ml, etc.
    complexity = Column(String, nullable=False)  # beginner, intermediate, advanced, expert
    tags = Column(JSON, default=list)

    # Authorship and visibility
    author_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    is_public = Column(Boolean, default=False, index=True)
    is_featured = Column(Boolean, default=False, index=True)

    # Template content (full workflow definition)
    template_json = Column(JSON, nullable=False)
    inputs_schema = Column(JSON, default=list)  # Input parameters with validation
    steps_schema = Column(JSON, default=list)  # Workflow steps with dependencies
    output_schema = Column(JSON, default=dict)  # Expected output structure

    # Usage tracking
    usage_count = Column(Integer, default=0)
    rating_sum = Column(Integer, default=0)
    rating_count = Column(Integer, default=0)

    # Calculated rating (0-5)
    @property
    def rating(self) -> float:
        if self.rating_count == 0:
            return 0.0
        return round(self.rating_sum / self.rating_count, 2)

    # Version control
    version = Column(String, default="1.0.0")
    parent_template_id = Column(String, ForeignKey("workflow_templates.template_id"), nullable=True)

    # Metadata
    estimated_duration_seconds = Column(Integer, default=0)
    prerequisites = Column(JSON, default=list)
    dependencies = Column(JSON, default=list)  # External services/APIs required
    permissions = Column(JSON, default=list)  # Required permissions
    license = Column(String, default="MIT")

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    author = relationship("User", backref="templates")
    children = relationship("WorkflowTemplate",
                           remote_side=[template_id],
                           foreign_keys=[parent_template_id],
                           back_populates="parent")
    parent = relationship("WorkflowTemplate",
                         foreign_keys=[parent_template_id],
                         back_populates="children")
    executions = relationship("TemplateExecution", back_populates="template")
    versions = relationship("TemplateVersion", back_populates="template")

    # Indexes
    __table_args__ = (
        Index('ix_workflow_templates_category_complexity', 'category', 'complexity'),
        Index('ix_workflow_templates_public_featured', 'is_public', 'is_featured'),
        Index('ix_workflow_templates_author_public', 'author_id', 'is_public'),
    )


class TemplateVersion(Base):
    """
    Version history for workflow templates.

    Tracks all changes to templates with ability to rollback.
    """
    __tablename__ = "template_versions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id = Column(String, ForeignKey("workflow_templates.template_id"), nullable=False, index=True)
    version = Column(String, nullable=False)  # Semantic version (1.0.0, 1.1.0, etc.)

    # Snapshot of template at this version
    template_snapshot = Column(JSON, nullable=False)
    change_description = Column(Text)
    changed_by_id = Column(String, ForeignKey("users.id"), nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    template = relationship("WorkflowTemplate", back_populates="versions")
    changed_by = relationship("User")

    # Unique constraint
    __table_args__ = (
        Index('ix_template_versions_template_version', 'template_id', 'version', unique=True),
    )


class TemplateExecution(Base):
    """
    Execution log for template instantiations.

    Tracks when templates are used to create workflows and their results.
    """
    __tablename__ = "template_executions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id = Column(String, ForeignKey("workflow_templates.template_id"), nullable=False, index=True)
    workflow_id = Column(String, nullable=False, index=True)  # Created workflow ID
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    # Execution parameters
    parameters_used = Column(JSON, nullable=False)  # Input values provided
    template_version = Column(String, nullable=False)  # Template version used

    # Execution results
    status = Column(String, nullable=False)  # started, completed, failed
    error_message = Column(Text, nullable=True)

    # Timing
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    template = relationship("WorkflowTemplate", back_populates="executions")
    user = relationship("User")

    # Indexes
    __table_args__ = (
        Index('ix_template_executions_template_status', 'template_id', 'status'),
        Index('ix_template_executions_user_status', 'user_id', 'status'),
    )


class WorkflowCollaborationSession(Base):
    """
    Real-time collaboration session for workflow editing.

    Tracks multiple users editing the same workflow simultaneously.
    """
    __tablename__ = "workflow_collaboration_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, unique=True, nullable=False, index=True)
    workflow_id = Column(String, nullable=False, index=True)

    # Session metadata
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Active users tracking
    active_users = Column(JSON, default=list)  # List of user_ids currently in session
    last_activity = Column(DateTime(timezone=True), server_default=func.now())

    # Session settings
    collaboration_mode = Column(String, default="parallel")  # "parallel", "sequential", "locked"
    max_users = Column(Integer, default=10)

    # Relationships
    participants = relationship("CollaborationSessionParticipant", back_populates="session", cascade="all, delete-orphan")
    locks = relationship("EditLock", back_populates="session", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('ix_workflow_collaboration_sessions_workflow', 'workflow_id'),
        Index('ix_workflow_collaboration_sessions_created_by', 'created_by'),
        Index('ix_workflow_collaboration_sessions_active', 'last_activity'),
    )


class CollaborationSessionParticipant(Base):
    """
    Participant in a collaboration session.

    Tracks individual user presence and cursor position.
    """
    __tablename__ = "collaboration_session_participants"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("workflow_collaboration_sessions.session_id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    # Presence tracking
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    last_heartbeat = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Cursor position (for canvas)
    cursor_position = Column(JSON)  # {x, y, node_id, viewport}
    selected_node = Column(String)  # Currently selected node ID

    # User info snapshot
    user_name = Column(String)  # Denormalized for performance
    user_color = Column(String, default="#2196F3")  # Unique color for cursor

    # Permissions
    role = Column(String, default="editor")  # "owner", "editor", "viewer", "commenter"
    can_edit = Column(Boolean, default=True)

    # Relationships
    session = relationship("WorkflowCollaborationSession", back_populates="participants")
    user = relationship("User")

    # Unique constraint
    __table_args__ = (
        Index('ix_collaboration_participants_session_user', 'session_id', 'user_id', unique=True),
        Index('ix_collaboration_participants_heartbeat', 'last_heartbeat'),
    )


class EditLock(Base):
    """
    Edit lock for workflow nodes or sections.

    Prevents conflicting edits when multiple users are editing.
    """
    __tablename__ = "edit_locks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("workflow_collaboration_sessions.session_id"), nullable=False, index=True)

    # Lock target
    workflow_id = Column(String, nullable=False, index=True)
    resource_type = Column(String, nullable=False)  # "node", "edge", "workflow"
    resource_id = Column(String, nullable=False, index=True)  # node_id, edge_id, or "workflow"

    # Lock owner
    locked_by = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    locked_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Lock metadata
    lock_reason = Column(String)  # Optional reason for lock
    is_active = Column(Boolean, default=True, index=True)

    # Relationships
    session = relationship("WorkflowCollaborationSession", back_populates="locks")
    locker = relationship("User")

    # Indexes
    __table_args__ = (
        Index('ix_edit_locks_workflow', 'workflow_id', 'is_active'),
        Index('ix_edit_locks_resource', 'resource_type', 'resource_id', 'is_active'),
        Index('ix_edit_locks_expiry', 'expires_at', 'is_active'),
    )


class WorkflowShare(Base):
    """
    Workflow sharing records.

    Manages workflow access via share links or direct invitations.
    """
    __tablename__ = "workflow_shares"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    share_id = Column(String, unique=True, nullable=False, index=True)
    workflow_id = Column(String, nullable=False, index=True)

    # Share metadata
    created_by = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    share_link = Column(String, unique=True, nullable=False)  # Public share URL

    # Access control
    share_type = Column(String, default="link")  # "link", "email", "workspace"
    permissions = Column(JSON)  # {can_view: true, can_edit: false, can_comment: true}
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    max_uses = Column(Integer, nullable=True)  # Null for unlimited
    use_count = Column(Integer, default=0)

    # Active status
    is_active = Column(Boolean, default=True, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(String, ForeignKey("users.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_accessed = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    revoker = relationship("User", foreign_keys=[revoked_by])

    # Indexes
    __table_args__ = (
        Index('ix_workflow_shares_workflow', 'workflow_id', 'is_active'),
        Index('ix_workflow_shares_expires', 'expires_at', 'is_active'),
    )


class CollaborationComment(Base):
    """
    Comments and discussions on workflows.

    Enables threaded conversations about workflows.
    """
    __tablename__ = "collaboration_comments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String, nullable=False, index=True)

    # Comment content
    author_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)

    # Thread support
    parent_comment_id = Column(String, ForeignKey("collaboration_comments.id"), nullable=True, index=True)

    # Context
    context_type = Column(String)  # "workflow", "node", "edge"
    context_id = Column(String)  # node_id or edge_id for targeted comments

    # Status
    is_resolved = Column(Boolean, default=False, index=True)
    resolved_by = Column(String, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    author = relationship("User", foreign_keys=[author_id])
    resolver = relationship("User", foreign_keys=[resolved_by])
    parent = relationship("CollaborationComment", remote_side=[id], backref="replies")

    # Indexes
    __table_args__ = (
        Index('ix_collaboration_comments_workflow', 'workflow_id'),
        Index('ix_collaboration_comments_context', 'context_type', 'context_id'),
        Index('ix_collaboration_comments_thread', 'parent_comment_id'),
        Index('ix_collaboration_comments_resolved', 'is_resolved'),
    )


class CollaborationAudit(Base):
    """
    Audit log for collaboration activities.

    Tracks all collaborative actions for accountability.
    """
    __tablename__ = "collaboration_audit"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String, nullable=False, index=True)

    # Action details
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    action_type = Column(String, nullable=False, index=True)  # "share", "comment", "lock", "unlock", "join_session"
    action_details = Column(JSON)  # Additional context about the action

    # Target resource
    resource_type = Column(String)  # "workflow", "node", "comment", "share"
    resource_id = Column(String)

    # Session tracking
    session_id = Column(String, ForeignKey("workflow_collaboration_sessions.session_id"), nullable=True, index=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship("User")
    session = relationship("WorkflowCollaborationSession")

    # Indexes
    __table_args__ = (
        Index('ix_collaboration_audit_workflow', 'workflow_id'),
        Index('ix_collaboration_audit_user', 'user_id', 'created_at'),
        Index('ix_collaboration_audit_action', 'action_type', 'created_at'),
    )


# ============================================================================
# WORKFLOW DEBUGGING MODELS
# ============================================================================

class WorkflowDebugSession(Base):
    """
    Debug session for workflow step-through debugging.
    
    Manages active debugging sessions with breakpoints and execution state.
    """
    __tablename__ = "workflow_debug_sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String, nullable=False, index=True)
    execution_id = Column(String, ForeignKey("workflow_executions.execution_id"), nullable=True, index=True)
    
    # Session management
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    session_name = Column(String, nullable=True)
    status = Column(String, default="active")  # active, paused, completed, cancelled
    current_step = Column(Integer, default=0)
    current_node_id = Column(String, nullable=True)
    
    # Debug state
    breakpoints = Column(JSON)  # List of breakpoint configurations
    variables = Column(JSON)  # Current variable state at each step
    call_stack = Column(JSON)  # Execution call stack
    
    # Settings
    stop_on_entry = Column(Boolean, default=False)
    stop_on_exceptions = Column(Boolean, default=True)
    stop_on_error = Column(Boolean, default=True)
    
    # Conditional breakpoints
    conditional_breakpoints = Column(JSON)  # {node_id: condition_expression}

    # Collaborative debugging (NEW - Phase 6 Enhanced)
    collaborators = Column(JSON)  # {user_id: {permission, added_at}}

    # Performance profiling (NEW - Phase 6 Enhanced)
    performance_metrics = Column(JSON)  # {enabled, started_at, step_times, node_times, total_duration_ms}

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User")
    execution = relationship("WorkflowExecution")
    
    # Indexes
    __table_args__ = (
        Index('ix_debug_sessions_workflow', 'workflow_id'),
        Index('ix_debug_sessions_user', 'user_id', 'created_at'),
        Index('ix_debug_sessions_status', 'status'),
    )


class WorkflowBreakpoint(Base):
    """
    Breakpoint configuration for workflow debugging.
    
    Defines where execution should pause during debugging.
    """
    __tablename__ = "workflow_breakpoints"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String, nullable=False, index=True)
    debug_session_id = Column(String, ForeignKey("workflow_debug_sessions.id"), nullable=True, index=True)
    
    # Breakpoint target
    node_id = Column(String, nullable=False, index=True)  # ID of the node to break at
    edge_id = Column(String, nullable=True, index=True)  # ID of the edge (for connection breakpoints)
    
    # Breakpoint configuration
    breakpoint_type = Column(String, default="node")  # node, edge, conditional, exception
    condition = Column(Text, nullable=True)  # Conditional expression
    hit_count = Column(Integer, default=0)  # Number of times breakpoint was hit
    hit_limit = Column(Integer, nullable=True)  # Stop after N hits (null = unlimited)
    
    # State
    is_active = Column(Boolean, default=True, index=True)
    is_disabled = Column(Boolean, default=False)
    log_message = Column(Text, nullable=True)  # Optional log message instead of stopping
    
    # Metadata
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    debug_session = relationship("WorkflowDebugSession")
    creator = relationship("User", foreign_keys=[created_by])
    
    # Indexes
    __table_args__ = (
        Index('ix_breakpoints_workflow', 'workflow_id', 'is_active'),
        Index('ix_breakpoints_session', 'debug_session_id'),
        Index('ix_breakpoints_node', 'node_id'),
    )


class ExecutionTrace(Base):
    """
    Detailed execution trace for workflow debugging.
    
    Records each step of workflow execution for inspection.
    """
    __tablename__ = "execution_traces"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String, nullable=False, index=True)
    execution_id = Column(String, ForeignKey("workflow_executions.execution_id"), nullable=False, index=True)
    debug_session_id = Column(String, ForeignKey("workflow_debug_sessions.id"), nullable=True, index=True)
    
    # Step information
    step_number = Column(Integer, nullable=False, index=True)
    node_id = Column(String, nullable=False, index=True)
    node_type = Column(String, nullable=False)  # trigger, action, condition, loop, etc.
    
    # Execution details
    status = Column(String, nullable=False)  # started, completed, failed, paused
    input_data = Column(JSON)  # Input data for this step
    output_data = Column(JSON)  # Output data from this step
    error_message = Column(Text, nullable=True)
    
    # Variable state
    variables_before = Column(JSON)  # Variable snapshot before execution
    variables_after = Column(JSON)  # Variable snapshot after execution
    variable_changes = Column(JSON)  # List of changed variables
    
    # Timing
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    # Metadata
    parent_step_id = Column(String, nullable=True)  # For nested workflows
    thread_id = Column(String, nullable=True)  # For parallel executions
    
    # Relationships
    execution = relationship("WorkflowExecution")
    debug_session = relationship("WorkflowDebugSession")
    
    # Indexes
    __table_args__ = (
        Index('ix_traces_execution', 'execution_id', 'step_number'),
        Index('ix_traces_workflow', 'workflow_id'),
        Index('ix_traces_debug_session', 'debug_session_id'),
        Index('ix_traces_node', 'node_id'),
    )


class DebugVariable(Base):
    """
    Variable inspection data for workflow debugging.
    
    Stores variable values and metadata at specific execution points.
    """
    __tablename__ = "debug_variables"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    trace_id = Column(String, ForeignKey("execution_traces.id"), nullable=False, index=True)
    debug_session_id = Column(String, ForeignKey("workflow_debug_sessions.id"), nullable=True, index=True)
    
    # Variable identification
    variable_name = Column(String, nullable=False, index=True)
    variable_path = Column(String, nullable=False)  # Dot-notation path for nested variables (e.g., "user.profile.name")
    variable_type = Column(String, nullable=False)  # string, number, boolean, object, array, null
    
    # Variable value and metadata
    value = Column(JSON, nullable=True)
    value_preview = Column(Text, nullable=True)  # String preview for complex objects
    is_mutable = Column(Boolean, default=True)
    scope = Column(String, default="local")  # local, global, workflow, context
    
    # Change tracking
    is_changed = Column(Boolean, default=False)
    previous_value = Column(JSON, nullable=True)
    
    # Watch expressions
    is_watch = Column(Boolean, default=False)  # True if this is a watch expression
    watch_expression = Column(Text, nullable=True)  # The expression being watched
    
    # Relationships
    trace = relationship("ExecutionTrace")
    debug_session = relationship("WorkflowDebugSession")
    
    # Indexes
    __table_args__ = (
        Index('ix_debug_variables_trace', 'trace_id'),
        Index('ix_debug_variables_session', 'debug_session_id'),
        Index('ix_debug_variables_name', 'variable_name'),
    )

# ============================================================================
# USER MANAGEMENT MODELS (Phase 1: Frontend to Backend Migration)
# ============================================================================

class EmailVerificationToken(Base):
    """Email verification tokens for user registration"""
    __tablename__ = "email_verification_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", backref="email_verification_tokens")

    # Indexes
    __table_args__ = (
        Index('ix_email_verification_user_token', 'user_id', 'token'),
    )


class Tenant(Base):
    """Tenant/Multi-tenancy support for enterprise deployments"""
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    subdomain = Column(String, unique=True, nullable=False, index=True)
    plan_type = Column(String, default="standard")  # standard, premium, enterprise
    status = Column(String, default="active")  # active, suspended, cancelled
    settings = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    users = relationship("User", backref="tenant")


class AdminRole(Base):
    """Admin roles with specific permissions"""
    __tablename__ = "admin_roles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False)  # super_admin, security_admin, etc.
    permissions = Column(JSON, default={})  # Dict of permission_name: bool
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    users = relationship("AdminUser", backref="role")


class AdminUser(Base):
    """Administrative users with elevated privileges"""
    __tablename__ = "admin_users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role_id = Column(String, ForeignKey("admin_roles.id"), nullable=False)
    status = Column(String, default="active")  # active, inactive
    last_login = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Indexes
    __table_args__ = (
        Index('ix_admin_users_status', 'status'),
    )


class MeetingAttendanceStatus(Base):
    """Meeting attendance tracking for automated monitoring"""
    __tablename__ = "meeting_attendance_status"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    platform = Column(String, nullable=True)  # zoom, teams, meet, etc.
    meeting_identifier = Column(String, nullable=True)  # Meeting ID or URL
    status_timestamp = Column(DateTime(timezone=True), nullable=False)
    current_status_message = Column(Text, nullable=True)
    final_notion_page_url = Column(String, nullable=True)
    error_details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", backref="meeting_attendances")

    # Indexes
    __table_args__ = (
        Index('ix_meeting_attendance_task', 'task_id', 'user_id'),
        Index('ix_meeting_attendance_timestamp', 'status_timestamp'),
    )


class FinancialAccount(Base):
    """User financial accounts (banking, investment, credit cards)"""
    __tablename__ = "financial_accounts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    account_type = Column(String, nullable=False)  # checking, savings, investment, credit_card
    provider = Column(String, nullable=True)  # Bank or institution name
    provider_account_id = Column(String, nullable=True)  # External ID
    balance = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    name = Column(String, nullable=True)  # User-defined account name
    account_metadata = Column(JSON, default={})  # Additional account details (renamed from metadata)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="financial_accounts")

    # Indexes
    __table_args__ = (
        Index('ix_financial_accounts_user_type', 'user_id', 'account_type'),
    )


class NetWorthSnapshot(Base):
    """Net worth tracking over time"""
    __tablename__ = "net_worth_snapshots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    snapshot_date = Column(DateTime(timezone=True), nullable=False, index=True)
    net_worth = Column(Float, nullable=False)
    assets = Column(Float, default=0.0)
    liabilities = Column(Float, default=0.0)
    breakdown = Column(JSON, default={})  # Detailed breakdown by category
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", backref="net_worth_snapshots")

    # Indexes
    __table_args__ = (
        Index('ix_net_worth_user_date', 'user_id', 'snapshot_date'),
    )


class CanvasRecording(Base):
    """Canvas session recording for governance and audit"""
    __tablename__ = "canvas_recordings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    recording_id = Column(String, unique=True, nullable=False, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id"))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    canvas_id = Column(String, nullable=True)
    session_id = Column(String, nullable=True, index=True)

    # Recording metadata
    reason = Column(String, nullable=False)  # Why was this recorded?
    status = Column(String, default="recording")  # recording, completed, failed
    tags = Column(JSON, default=list)  # ["autonomous", "governance", "integration_connect"]

    # Events and timeline
    events = Column(JSON, default=list)  # [{timestamp, event_type, data}]
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    stopped_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Summary and review
    summary = Column(Text, nullable=True)
    event_count = Column(Integer, default=0)
    recording_metadata = Column(JSON, default=dict)  # Renamed from 'metadata' (reserved in SQLAlchemy)

    # Governance
    flagged_for_review = Column(Boolean, default=False)
    flag_reason = Column(Text, nullable=True)
    flagged_by = Column(String, nullable=True)
    flagged_at = Column(DateTime(timezone=True), nullable=True)

    # Retention
    expires_at = Column(DateTime(timezone=True), nullable=True)
    storage_url = Column(String, nullable=True)  # S3/blob storage if needed

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    agent = relationship("AgentRegistry", backref="canvas_recordings")
    user = relationship("User", backref="canvas_recordings")

    # Indexes
    __table_args__ = (
        Index('ix_canvas_recordings_agent_user', 'agent_id', 'user_id'),
        Index('ix_canvas_recordings_session', 'session_id', 'status'),
        Index('ix_canvas_recordings_started', 'started_at'),
    )


class CanvasRecordingReview(Base):
    """Recording review linking canvas recordings to governance and learning outcomes"""
    __tablename__ = "canvas_recording_reviews"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    recording_id = Column(String, ForeignKey("canvas_recordings.recording_id"), nullable=False, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    # Review outcomes
    review_status = Column(String, nullable=False)  # approved, rejected, needs_changes, pending
    overall_rating = Column(Integer, nullable=True)  # 1-5 stars
    performance_rating = Column(Integer, nullable=True)  # 1-5 stars
    safety_rating = Column(Integer, nullable=True)  # 1-5 stars (governance compliance)

    # Feedback and learning
    feedback = Column(Text, nullable=True)
    identified_issues = Column(JSON, default=list)  # ["unsafe_action", "error_recovery", "user_intervention"]
    positive_patterns = Column(JSON, default=list)  # ["efficient_workflow", "good_error_handling"]
    lessons_learned = Column(Text, nullable=True)

    # Governance impact
    confidence_delta = Column(Float, default=0.0)  # Change to agent confidence score
    promoted = Column(Boolean, default=False)  # Did this contribute to promotion?
    demoted = Column(Boolean, default=False)  # Did this contribute to demotion?
    governance_notes = Column(Text, nullable=True)

    # Review metadata
    reviewed_by = Column(String, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    auto_reviewed = Column(Boolean, default=False)  # True if AI-reviewed
    auto_review_confidence = Column(Float, nullable=True)  # AI's confidence in its review

    # Learning integration
    used_for_training = Column(Boolean, default=False)
    training_value = Column(String, nullable=True)  # high, medium, low
    world_model_updated = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    recording = relationship("CanvasRecording", backref="reviews")
    agent = relationship("AgentRegistry", backref="recording_reviews")
    user = relationship("User", foreign_keys=[user_id], backref="submitted_reviews")
    reviewer = relationship("User", foreign_keys=[reviewed_by], backref="conducted_reviews")

    # Indexes
    __table_args__ = (
        Index('ix_recording_reviews_recording', 'recording_id'),
        Index('ix_recording_reviews_agent', 'agent_id'),
        Index('ix_recording_reviews_status', 'review_status'),
        Index('ix_recording_reviews_reviewed', 'reviewed_at'),
    )


class MobileDevice(Base):
    """Mobile device registration for push notifications and mobile access"""
    __tablename__ = "mobile_devices"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    device_token = Column(String, nullable=False, unique=True, index=True)
    platform = Column(String, nullable=False)  # ios, android, web
    status = Column(String, default="active")  # active, inactive, disabled

    # Device information
    device_info = Column(JSON, default=dict)  # {model, os_version, app_version, etc.}

    # Notification preferences
    notification_enabled = Column(Boolean, default=True)
    notification_preferences = Column(JSON, default=dict)  # {agent_alerts, system_alerts, etc.}

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="mobile_devices")
    offline_actions = relationship("OfflineAction", backref="device", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('ix_mobile_devices_user', 'user_id'),
        Index('ix_mobile_devices_token', 'device_token'),
        Index('ix_mobile_devices_platform', 'platform'),
        Index('ix_mobile_devices_status', 'status'),
    )


class OfflineAction(Base):
    """Actions queued while device is offline for later sync"""
    __tablename__ = "offline_actions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String, ForeignKey("mobile_devices.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    # Action details
    action_type = Column(String, nullable=False)  # agent_message, workflow_trigger, form_submit, etc.
    action_data = Column(JSON, nullable=False)  # Full action payload
    priority = Column(Integer, default=0)  # Higher = more important

    # Sync status
    status = Column(String, default="pending")  # pending, syncing, completed, failed
    sync_attempts = Column(Integer, default=0)
    last_sync_error = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    synced_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", backref="offline_actions")

    # Indexes
    __table_args__ = (
        Index('ix_offline_actions_device', 'device_id'),
        Index('ix_offline_actions_user', 'user_id'),
        Index('ix_offline_actions_status', 'status'),
        Index('ix_offline_actions_priority', 'priority'),
        Index('ix_offline_actions_created', 'created_at'),
    )


class SyncState(Base):
    """Track synchronization state for mobile devices"""
    __tablename__ = "sync_states"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String, ForeignKey("mobile_devices.id"), nullable=False, unique=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    # Last sync timestamps
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_successful_sync_at = Column(DateTime(timezone=True), nullable=True)

    # Sync statistics
    total_syncs = Column(Integer, default=0)
    successful_syncs = Column(Integer, default=0)
    failed_syncs = Column(Integer, default=0)

    # Pending actions count
    pending_actions_count = Column(Integer, default=0)

    # Sync configuration
    auto_sync_enabled = Column(Boolean, default=True)
    sync_interval_seconds = Column(Integer, default=300)  # 5 minutes default

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    device = relationship("MobileDevice", backref=backref("sync_state", uselist=False))
    user = relationship("User", backref="sync_states")

    # Indexes
    __table_args__ = (
        Index('ix_sync_states_device', 'device_id'),
        Index('ix_sync_states_user', 'user_id'),
        Index('ix_sync_states_last_sync', 'last_sync_at'),
    )