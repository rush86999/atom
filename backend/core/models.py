
import base64
import datetime
import enum
import hashlib
import json
from typing import Optional
import uuid
from cryptography.fernet import Fernet
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import backref, relationship
from sqlalchemy.sql import func

from core.data_visibility import DataVisibility
from core.database import Base

# ============================================================================
# Token Encryption Helpers
# ============================================================================

_fernet_instances = {}

def _get_fernet_for_token():
    """
    Get or create a Fernet instance for token encryption.
    Uses the same encryption key pattern as connection_service.py.
    """
    global _fernet_instances
    if 'token' not in _fernet_instances:
        # Lazy import to avoid circular dependency
        from core.config import get_config
        key = get_config().security.encryption_key or get_config().security.secret_key
        # Fernet key must be 32 url-safe base64-encoded bytes
        key_bytes = key.encode()
        key_hash = hashlib.sha256(key_bytes).digest()
        fernet_key = base64.urlsafe_b64encode(key_hash)
        _fernet_instances['token'] = Fernet(fernet_key)
    return _fernet_instances['token']

def _encrypt_token(token: str) -> str:
    """Encrypt a token string for storage."""
    if not token:
        return ""
    f = _get_fernet_for_token()
    return f.encrypt(token.encode()).decode()

def _decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt a token string from storage.
    Supports backwards compatibility with plaintext tokens.
    """
    if not encrypted_token:
        return ""

    # If it's already a plaintext token (doesn't look like Fernet output)
    # Fernet output is base64-encoded and typically 44+ chars starting with 'gAAAA'
    if not encrypted_token.startswith('gAAAA') and len(encrypted_token) < 40:
        # Assume plaintext (backwards compatibility)
        return encrypted_token

    try:
        f = _get_fernet_for_token()
        decrypted = f.decrypt(encrypted_token.encode()).decode()
        return decrypted
    except Exception:
        # If decryption fails, return as-is (might be legacy plaintext)
        return encrypted_token


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

    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id}, name={self.name}, status={self.status})>"

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
    activity = relationship("UserActivity", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id}, email={self.email}, role={self.role})>"

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
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class HITLActionStatus(str, enum.Enum):
    """Status for Human-in-the-loop actions requiring user approval"""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "expired"

class AgentJob(Base):
    __tablename__ = "agent_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, nullable=False)
    status = Column(SQLEnum(AgentJobStatus), default=AgentJobStatus.PENDING, nullable=False)
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

    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id}, name={self.name}, status={self.status}, confidence={self.confidence_score})>"

class AgentFeedback(Base):
    """User feedback on agent actions for RLHF"""
    __tablename__ = "agent_feedback"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False)
    agent_execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    episode_id = Column(String, ForeignKey("episodes.id"), nullable=True, index=True)  # NEW - Episode backlink

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
    status = Column(String, default="active")  # active, inactive, deprecated
    last_successful_connection = Column(DateTime(timezone=True), nullable=True)
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

class StripeToken(Base):
    """Stores Stripe OAuth tokens for secure API access"""
    __tablename__ = "stripe_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=True, index=True)

    # OAuth tokens (encrypted in production)
    access_token = Column(String, nullable=False)  # Stripe access token
    refresh_token = Column(String, nullable=True)  # For token refresh
    stripe_user_id = Column(String, nullable=False, index=True)  # Stripe account ID

    # Token metadata
    livemode = Column(Boolean, default=False)  # True for production, False for test mode
    token_type = Column(String, default="bearer")  # Usually "bearer"

    # Expiration tracking
    expires_at = Column(DateTime(timezone=True), nullable=True)
    scope = Column(String, nullable=True)  # OAuth scope granted

    # Status
    status = Column(String, default="active")  # active, expired, revoked
    last_used = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="stripe_tokens")
    workspace = relationship("Workspace", backref="stripe_tokens")

class NotionToken(Base):
    """Stores Notion OAuth tokens for secure API access"""
    __tablename__ = "notion_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=True, index=True)

    # OAuth tokens (encrypted in production)
    access_token = Column(String, nullable=False)  # Notion access token
    refresh_token = Column(String, nullable=True)  # Notion doesn't use refresh tokens currently, but reserved for future
    notion_user_id = Column(String, nullable=True, index=True)  # Notion user/bot ID

    # Token metadata
    workspace_name = Column(String, nullable=True)  # Notion workspace name
    workspace_icon = Column(String, nullable=True)  # Notion workspace icon URL
    notion_workspace_id = Column(String, nullable=True)  # Notion workspace ID (external)

    # Token type
    token_type = Column(String, default="bearer")  # Usually "bearer"
    owner_type = Column(String, nullable=True)  # "user" or "workspace"

    # Expiration tracking (Notion access tokens don't expire, but we track for safety)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    scope = Column(String, nullable=True)  # OAuth scope granted

    # Status
    status = Column(String, default="active")  # active, expired, revoked
    last_used = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="notion_tokens")
    workspace = relationship("Workspace", backref="notion_tokens")

class IntegrationHealthMetrics(Base):
    """
    Health metrics for integrations to track latency, error rates, and trends.
    Used by the health monitoring system to calculate integration health.
    """
    __tablename__ = "integration_health_metrics"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    integration_id = Column(String, ForeignKey("integration_catalog.id"), nullable=False, index=True)
    connection_id = Column(String, ForeignKey("user_connections.id"), nullable=False, index=True)

    # Health metrics
    latency_ms = Column(Float, default=0.0)
    success_rate = Column(Float, default=1.0)
    error_count = Column(Integer, default=0)
    request_count = Column(Integer, default=0)

    # Trend tracking
    health_trend = Column(String, default="stable")  # improving, stable, declining
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    integration = relationship("IntegrationCatalog", backref="health_metrics")
    connection = relationship("UserConnection", backref="health_metrics")

class OAuthState(Base):
    """
    OAuth state parameter storage for CSRF protection.

    Stores temporary state tokens used during OAuth flows to prevent CSRF attacks.
    States are single-use and expire after a short time (typically 10 minutes).
    """
    __tablename__ = "oauth_states"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String, nullable=False, index=True)  # google, github, notion, etc.
    state = Column(String, unique=True, nullable=False, index=True)  # Random state token

    # OAuth flow parameters
    scopes = Column(JSON, nullable=True)  # List of requested scopes
    redirect_uri = Column(String, nullable=True)  # Where to redirect after auth

    # Expiration and cleanup
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    used = Column(Boolean, default=False, index=True)  # Mark as used after callback

    # Relationships
    user = relationship("User", backref="oauth_states")

    def __repr__(self):
        return f"<OAuthState(id={self.id}, user_id={self.user_id}, provider={self.provider}, used={self.used})>"

class OAuthToken(Base):
    """
    Unified OAuth token storage for all OAuth providers.

    Stores access tokens, refresh tokens, and metadata for OAuth integrations.
    Supports multiple providers (Google, GitHub, Notion, etc.) with automatic
    token refresh capabilities.

    Security: Access tokens are automatically encrypted at rest using Fernet.
    Refresh tokens are also encrypted for additional security.
    """
    __tablename__ = "oauth_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String, nullable=False, index=True)  # google, github, notion, etc.

    # Encrypted token storage (actual database columns)
    _encrypted_access_token = Column("encrypted_access_token", Text, nullable=True)
    _encrypted_refresh_token = Column("encrypted_refresh_token", Text, nullable=True)

    # Properties for automatic encryption/decryption
    @property
    def access_token(self) -> str:
        """Get decrypted access token."""
        return _decrypt_token(self._encrypted_access_token or "")

    @access_token.setter
    def access_token(self, value: str):
        """Set encrypted access token."""
        self._encrypted_access_token = _encrypt_token(value) if value else ""

    @property
    def refresh_token(self) -> str:
        """Get decrypted refresh token."""
        return _decrypt_token(self._encrypted_refresh_token or "")

    @refresh_token.setter
    def refresh_token(self, value: str):
        """Set encrypted refresh token."""
        self._encrypted_refresh_token = _encrypt_token(value) if value else None

    token_type = Column(String, default="Bearer")  # Typically "Bearer"

    # Token metadata
    scopes = Column(JSON, nullable=True)  # List of granted scopes
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Some tokens don't expire (Notion)

    # Status tracking
    status = Column(String, default="active", index=True)  # active, expired, revoked
    last_used = Column(DateTime(timezone=True), nullable=True)  # Track when token was last used

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="oauth_tokens")

    def __repr__(self):
        return f"<OAuthToken(id={self.id}, user_id={self.user_id}, provider={self.provider}, status={self.status})>"

    def is_expired(self) -> bool:
        """Check if the token is expired"""
        if self.expires_at is None:
            return False  # Tokens without expiration (like Notion) don't expire
        return datetime.datetime.now(self.expires_at.tzinfo) > self.expires_at

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
    agent = relationship("AgentRegistry", backref="executions")
    # Note: workspace relationship removed - workspace_id is a string reference without FK constraint

    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id}, agent_id={self.agent_id}, status={self.status})>"


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
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)
    agent_execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    canvas_id = Column(String, nullable=True, index=True)
    session_id = Column(String, nullable=True, index=True)  # Session isolation (NEW)
    canvas_type = Column(String, default="generic", nullable=False, index=True)  # 'generic', 'docs', 'email', 'sheets', 'orchestration', 'terminal', 'coding' (NEW)
    component_type = Column(String, nullable=False)  # 'chart', 'markdown', 'form', etc.
    component_name = Column(String, nullable=True)  # 'line_chart', 'bar_chart', etc.
    action = Column(String, nullable=False)  # 'present', 'close', 'submit', 'update'
    audit_metadata = Column(JSON, default={})  # Renamed from 'metadata' (reserved)
    governance_check_passed = Column(Boolean, nullable=True)
    episode_id = Column(String, ForeignKey("episodes.id"), nullable=True, index=True)  # NEW - Episode backlink
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    agent = relationship("AgentRegistry", backref="canvas_audits")
    execution = relationship("AgentExecution", backref="canvas_audits")
    user = relationship("User", backref="canvas_audits")
    episode = relationship("Episode", backref="canvas_references")

    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id}, action={self.action}, component_type={self.component_type})>"

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
    
    # Traceability
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)
    agent_execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=True, index=True)

    # Relationships
    agent = relationship("AgentRegistry")
    execution = relationship("AgentExecution", foreign_keys=[agent_execution_id])

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

    # App type (desktop, mobile, menubar)
    app_type = Column(String, default="desktop")

    # Last command execution timestamp (for menu bar)
    last_command_at = Column(DateTime(timezone=True), nullable=True)

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
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)
    agent_execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    device_node_id = Column(String, ForeignKey("device_nodes.device_id"), nullable=False, index=True)
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

    # Relationships
    agent = relationship("AgentRegistry", backref="device_audits")
    execution = relationship("AgentExecution", backref="device_audits")
    user = relationship("User", backref="device_audits")
    device = relationship("DeviceNode", backref="audit_logs")


class BrowserAudit(Base):
    """
    Audit trail for browser automation actions.

    Records all browser operations (navigate, click, fill, screenshot, etc.)
    with full governance tracking and attribution.
    """
    __tablename__ = "browser_audit"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, nullable=True, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)
    agent_execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
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
    agent = relationship("AgentRegistry", backref="browser_audits")
    execution = relationship("AgentExecution", backref="browser_audits")
    user = relationship("User", backref="browser_audits")
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
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

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
    agent = relationship("AgentRegistry", backref="deep_link_audits")
    execution = relationship("AgentExecution", backref="deep_link_audits")
    user = relationship("User", backref="deep_link_audits")


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

    # Biometric authentication support
    biometric_public_key = Column(Text, nullable=True)  # Public key for signature verification
    biometric_enabled = Column(Boolean, default=False)  # Whether biometric auth is enabled
    last_biometric_auth = Column(DateTime(timezone=True), nullable=True)  # Last successful biometric auth

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
        Index('ix_mobile_devices_user_status', 'user_id', 'status'),  # Composite index for faster lookups
        Index('ix_mobile_devices_biometric_enabled', 'biometric_enabled'),
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
        # Composite indexes for better performance
        Index('ix_offline_actions_priority_status', 'priority', 'status'),
        Index('ix_offline_actions_user_pending', 'user_id', 'status'),
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

    # Conflict resolution
    conflict_resolution = Column(String, default="last_write_wins")  # last_write_wins, manual, server_wins
    last_conflict_at = Column(DateTime(timezone=True), nullable=True)

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


# ============================================================================
# Student Agent Training & Maturity-Based Routing Models
# ============================================================================

class TriggerSource(str, enum.Enum):
    """Sources of agent triggers"""
    MANUAL = "manual"                # User directly triggered
    DATA_SYNC = "data_sync"          # Offline sync operations
    WORKFLOW_ENGINE = "workflow_engine"  # Workflow automation
    AI_COORDINATOR = "ai_coordinator"    # AI-driven data ingestion


class ProposalStatus(str, enum.Enum):
    """Status of proposals (training or action)"""
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    CANCELLED = "cancelled"


class ProposalType(str, enum.Enum):
    """Type of proposal"""
    TRAINING = "training"        # Training proposal for STUDENT agents
    ACTION = "action"            # Action proposal from INTERN agents
    ANALYSIS = "analysis"        # Analysis/review proposal


class SupervisionStatus(str, enum.Enum):
    """Status of supervision sessions"""
    RUNNING = "running"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


class BlockedTriggerContext(Base):
    """
    Record of automated triggers intercepted by maturity guard.

    Tracks when agents are blocked from executing due to maturity level,
    providing audit trail and routing information for training/proposals.
    """
    __tablename__ = "blocked_triggers"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Agent Information
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
    agent_name = Column(String, nullable=False)  # Denormalized for quick queries

    # Maturity State at Time of Block
    agent_maturity_at_block = Column(String, nullable=False, index=True)  # student, intern, supervised, autonomous
    confidence_score_at_block = Column(Float, nullable=False)

    # Trigger Source
    trigger_source = Column(String, nullable=False, index=True)  # MANUAL, DATA_SYNC, WORKFLOW_ENGINE, AI_COORDINATOR
    trigger_type = Column(String, nullable=False)  # agent_message, workflow_trigger, etc.
    trigger_context = Column(JSON, nullable=False)  # Full trigger payload

    # Routing Decision
    routing_decision = Column(String, nullable=False)  # training, proposal, supervision, execution
    block_reason = Column(Text, nullable=False)  # Human-readable explanation

    # Resolution
    proposal_id = Column(String, ForeignKey("agent_proposals.id"), nullable=True, index=True)
    resolved = Column(Boolean, default=False, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_outcome = Column(Text, nullable=True)  # What happened after blocking

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    agent = relationship("AgentRegistry", backref="blocked_triggers")
    proposal = relationship("AgentProposal", backref="blocked_triggers")

    # Indexes
    __table_args__ = (
        Index('ix_blocked_triggers_agent', 'agent_id'),
        Index('ix_blocked_triggers_source', 'trigger_source'),
        Index('ix_blocked_triggers_maturity', 'agent_maturity_at_block'),
        Index('ix_blocked_triggers_resolved', 'resolved'),
        Index('ix_blocked_triggers_created', 'created_at'),
    )


class AgentProposal(Base):
    """
    Proposals generated by INTERN agents or Meta Agent for STUDENT training.

    INTERN agents generate proposals for human review instead of executing directly.
    Meta Agent generates training proposals for STUDENT agents who were blocked.
    """
    __tablename__ = "agent_proposals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Agent Information
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
    agent_name = Column(String, nullable=False)  # Denormalized

    # Proposal Details
    proposal_type = Column(String, nullable=False, index=True)  # training, action, analysis
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)

    # Proposed Action / Training
    proposed_action = Column(JSON, nullable=True)  # For action proposals: what agent wants to do
    reasoning = Column(Text, nullable=True)  # Why this action/training is needed

    # Training-Specific Fields (for STUDENT agents)
    learning_objectives = Column(JSON, nullable=True)  # List of learning objectives
    capability_gaps = Column(JSON, nullable=True)  # List of capabilities to develop
    training_scenario_template = Column(String, nullable=True)  # Finance, Sales, Operations, etc.

    # Duration Estimation (AI-based with user override)
    estimated_duration_hours = Column(Float, nullable=True)  # AI estimate
    duration_estimation_confidence = Column(Float, nullable=True)  # AI's confidence (0-1)
    duration_estimation_reasoning = Column(Text, nullable=True)  # Why AI chose this duration
    user_override_duration_hours = Column(Float, nullable=True)  # User's custom duration
    hours_per_day_limit = Column(Float, nullable=True)  # Daily availability constraint

    # Training Schedule (for approved training proposals)
    training_start_date = Column(DateTime(timezone=True), nullable=True)
    training_end_date = Column(DateTime(timezone=True), nullable=True)

    # Approval Workflow
    status = Column(String, default=ProposalStatus.PROPOSED.value, index=True)
    proposed_by = Column(String, nullable=False)  # agent_id or "atom_meta_agent"
    approved_by = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    modifications = Column(JSON, nullable=True)  # Changes made during approval

    # Execution Results
    execution_result = Column(JSON, nullable=True)  # Result of executed action or training
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    agent = relationship("AgentRegistry", backref="proposals")
    approver = relationship("User", backref="approved_proposals", foreign_keys=[approved_by])

    # Indexes
    __table_args__ = (
        Index('ix_agent_proposals_agent', 'agent_id'),
        Index('ix_agent_proposals_type', 'proposal_type'),
        Index('ix_agent_proposals_status', 'status'),
        Index('ix_agent_proposals_proposed_by', 'proposed_by'),
        Index('ix_agent_proposals_approved_by', 'approved_by'),
        Index('ix_agent_proposals_created', 'created_at'),
    )


class SupervisionSession(Base):
    """
    Real-time supervision sessions for SUPERVISED agents (0.7-0.9 confidence).

    SUPERVISED agents execute with real-time monitoring where humans can intervene.
    Tracks all interventions and outcomes for learning and audit purposes.
    """
    __tablename__ = "supervision_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Agent Information
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
    agent_name = Column(String, nullable=False)  # Denormalized

    # Trigger Context
    trigger_id = Column(String, ForeignKey("blocked_triggers.id"), nullable=True, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    trigger_context = Column(JSON, nullable=False)  # Original trigger context

    # Session Status
    status = Column(String, default=SupervisionStatus.RUNNING.value, index=True)

    # Timing
    started_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)  # Calculated on completion

    # Supervision
    supervisor_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    intervention_count = Column(Integer, default=0)  # Number of interventions

    # Interventions (JSON array of intervention records)
    # Each intervention: {timestamp, type, guidance, agent_state, outcome}
    interventions = Column(JSON, default=list)

    # Agent Actions (JSON array of action records)
    # Each action: {timestamp, action_type, description, result}
    agent_actions = Column(JSON, default=list)

    # Outcomes
    outcomes = Column(JSON, nullable=True)  # Summary of what was accomplished
    supervisor_rating = Column(Integer, nullable=True)  # 1-5 stars
    supervisor_feedback = Column(Text, nullable=True)

    # Maturity Impact
    confidence_boost = Column(Float, nullable=True)  # Confidence increase from successful execution

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    agent = relationship("AgentRegistry", backref="supervision_sessions")
    trigger = relationship("BlockedTriggerContext", backref="supervision_sessions")
    workspace = relationship("Workspace", backref="supervision_sessions")
    supervisor = relationship("User", backref="supervised_sessions")

    # Indexes
    __table_args__ = (
        Index('ix_supervision_sessions_agent', 'agent_id'),
        Index('ix_supervision_sessions_workspace', 'workspace_id'),
        Index('ix_supervision_sessions_supervisor', 'supervisor_id'),
        Index('ix_supervision_sessions_status', 'status'),
        Index('ix_supervision_sessions_started', 'started_at'),
    )


# ============================================================================
# TWO-WAY LEARNING SYSTEM: Supervisor Performance & Feedback
# ============================================================================

class SupervisorRating(Base):
    """
    5-star ratings for supervisors on supervision sessions.

    Agents and other supervisors can rate supervisor performance.
    Enables supervisor learning and improvement.
    """
    __tablename__ = "supervisor_ratings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Links
    supervision_session_id = Column(String, ForeignKey("supervision_sessions.id"), nullable=False, index=True)
    supervisor_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    rater_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)  # Who rated
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)  # Optional agent context

    # Rating (1-5 stars)
    rating = Column(Integer, nullable=False)  # 1-5 scale
    rating_category = Column(String, nullable=True)  # "intervention_quality", "guidance_clarity", "outcome_quality"

    # Context
    reason = Column(Text, nullable=True)  # Optional explanation for rating
    was_helpful = Column(Boolean, default=True)  # Did this supervision help the agent?

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    supervision_session = relationship("SupervisionSession", backref="ratings")
    supervisor = relationship("User", foreign_keys=[supervisor_id], backref="received_ratings")
    rater = relationship("User", foreign_keys=[rater_id], backref="given_ratings")
    agent = relationship("AgentRegistry", backref="supervisor_ratings")

    # Indexes
    __table_args__ = (
        Index('ix_supervisor_ratings_session', 'supervision_session_id'),
        Index('ix_supervisor_ratings_supervisor', 'supervisor_id'),
        Index('ix_supervisor_ratings_rater', 'rater_id'),
        Index('ix_supervisor_ratings_created', 'created_at'),
    )


class SupervisorComment(Base):
    """
    Threaded comments on supervision sessions.

    Enables rich discussion and learning from supervision experiences.
    Supports hierarchical comment threads for organized discussions.
    """
    __tablename__ = "supervisor_comments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Links
    supervision_session_id = Column(String, ForeignKey("supervision_sessions.id"), nullable=False, index=True)
    author_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    parent_comment_id = Column(String, ForeignKey("supervisor_comments.id"), nullable=True, index=True)  # For threading

    # Content
    content = Column(Text, nullable=False)
    content_type = Column(String, default="text")  # "text", "code", "suggestion"

    # Metadata
    comment_type = Column(String, nullable=True)  # "guidance", "question", "observation", "resolution"
    intervention_reference = Column(JSON, nullable=True)  # Reference to specific intervention

    # Threading support
    thread_path = Column(String, nullable=True)  # e.g., "root.parent.child" for efficient querying
    depth = Column(Integer, default=0)  # Thread depth (0 for root comments)

    # Engagement
    reply_count = Column(Integer, default=0)  # Number of direct replies
    upvote_count = Column(Integer, default=0)  # Sum of upvotes
    downvote_count = Column(Integer, default=0)  # Sum of downvotes

    # Status
    is_edited = Column(Boolean, default=False)
    is_resolved = Column(Boolean, default=False)  # For questions/issues
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)  # Soft delete

    # Relationships
    supervision_session = relationship("SupervisionSession", backref="comments")
    author = relationship("User", backref="supervisor_comments")
    parent_comment = relationship("SupervisorComment", remote_side=[id], backref="replies")

    # Indexes
    __table_args__ = (
        Index('ix_supervisor_comments_session', 'supervision_session_id'),
        Index('ix_supervisor_comments_author', 'author_id'),
        Index('ix_supervisor_comments_parent', 'parent_comment_id'),
        Index('ix_supervisor_comments_thread', 'thread_path'),
        Index('ix_supervisor_comments_created', 'created_at'),
    )


class FeedbackVote(Base):
    """
    Thumbs up/down votes for supervision sessions and comments.

    Enables quick feedback on supervision quality and comment helpfulness.
    """
    __tablename__ = "feedback_votes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Links
    supervision_session_id = Column(String, ForeignKey("supervision_sessions.id"), nullable=True, index=True)
    comment_id = Column(String, ForeignKey("supervisor_comments.id"), nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    # Vote (thumbs up/down)
    vote_type = Column(String, nullable=False)  # "up", "down"

    # Context
    vote_reason = Column(String, nullable=True)  # Optional: "helpful", "incorrect", "unclear"

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    supervision_session = relationship("SupervisionSession", backref="votes")
    comment = relationship("SupervisorComment", backref="votes")
    user = relationship("User", backref="feedback_votes")

    # Indexes
    __table_args__ = (
        Index('ix_feedback_votes_session', 'supervision_session_id'),
        Index('ix_feedback_votes_comment', 'comment_id'),
        Index('ix_feedback_votes_user', 'user_id'),
        Index('ix_feedback_votes_created', 'created_at'),

        # Ensure one vote per user per target
        Index('ix_feedback_votes_unique_session', 'supervision_session_id', 'user_id', unique=True),
        Index('ix_feedback_votes_unique_comment', 'comment_id', 'user_id', unique=True),
    )


class SupervisorPerformance(Base):
    """
    Aggregated performance metrics for supervisors.

    Tracks supervisor effectiveness over time to enable learning and
    identify areas for improvement.
    """
    __tablename__ = "supervisor_performance"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Supervisor
    supervisor_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # Overall Metrics
    total_sessions_supervised = Column(Integer, default=0)
    total_interventions = Column(Integer, default=0)

    # Rating Metrics (from ratings received)
    average_rating = Column(Float, default=0.0)  # 1-5 scale
    total_ratings = Column(Integer, default=0)

    # 5-star distribution
    rating_1_count = Column(Integer, default=0)
    rating_2_count = Column(Integer, default=0)
    rating_3_count = Column(Integer, default=0)
    rating_4_count = Column(Integer, default=0)
    rating_5_count = Column(Integer, default=0)

    # Intervention Success Metrics
    successful_interventions = Column(Integer, default=0)  # Interventions that led to success
    failed_interventions = Column(Integer, default=0)  # Interventions that didn't help

    # Agent Improvement Metrics
    agents_promoted = Column(Integer, default=0)  # Agents that graduated under this supervisor
    agent_confidence_boosted = Column(Float, default=0.0)  # Total confidence increase given

    # Feedback Metrics
    total_comments_given = Column(Integer, default=0)
    total_upvotes_received = Column(Integer, default=0)
    total_downvotes_received = Column(Integer, default=0)

    # Supervisor Confidence (self-assessment and community-rated)
    confidence_score = Column(Float, default=0.5)  # 0.0 to 1.0
    competence_level = Column(String, default="novice")  # "novice", "intermediate", "advanced", "expert"

    # Learning & Trend
    learning_rate = Column(Float, default=0.0)  # How fast supervisor is improving
    performance_trend = Column(String, default="stable")  # "improving", "stable", "declining"

    # Timestamps
    last_updated = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    supervisor = relationship("User", backref="performance_metrics")

    # Indexes
    __table_args__ = (
        Index('ix_supervisor_performance_supervisor', 'supervisor_id'),
        Index('ix_supervisor_performance_rating', 'average_rating'),
        Index('ix_supervisor_performance_confidence', 'confidence_score'),
    )


class InterventionOutcome(Base):
    """
    Tracks outcomes of supervisor interventions for learning.

    Links interventions to agent behavior changes and success metrics.
    """
    __tablename__ = "intervention_outcomes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Links
    supervision_session_id = Column(String, ForeignKey("supervision_sessions.id"), nullable=False, index=True)
    supervisor_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)

    # Intervention Details
    intervention_type = Column(String, nullable=False)  # "pause", "correct", "terminate"
    intervention_timestamp = Column(DateTime(timezone=True), nullable=False)

    # Outcome
    outcome = Column(String, nullable=False)  # "success", "partial", "failure"
    agent_behavior_change = Column(String, nullable=True)  # "improved", "unchanged", "degraded"
    task_completion = Column(String, nullable=True)  # "completed", "abandoned", "failed"

    # Time to Recovery
    seconds_to_recovery = Column(Integer, nullable=True)  # How long until agent was back on track

    # Assessment
    was_necessary = Column(Boolean, default=True)  # Was this intervention needed?
    was_effective = Column(Boolean, default=True)  # Did it help?
    would_recommend = Column(Boolean, nullable=True)  # Would supervisor do this again?

    # Learning
    lesson_learned = Column(Text, nullable=True)  # What the supervisor learned
    confidence_change = Column(Float, default=0.0)  # Supervisor confidence change (-1.0 to 1.0)

    # Timestamps
    assessed_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    supervision_session = relationship("SupervisionSession", backref="intervention_outcomes")
    supervisor = relationship("User", backref="intervention_assessments")
    agent = relationship("AgentRegistry", backref="intervention_outcomes")

    # Indexes
    __table_args__ = (
        Index('ix_intervention_outcomes_session', 'supervision_session_id'),
        Index('ix_intervention_outcomes_supervisor', 'supervisor_id'),
        Index('ix_intervention_outcomes_agent', 'agent_id'),
        Index('ix_intervention_outcomes_type', 'intervention_type'),
        Index('ix_intervention_outcomes_outcome', 'outcome'),
        Index('ix_intervention_outcomes_assessed', 'assessed_at'),
    )


class TrainingSession(Base):
    """
    Human-in-the-loop training sessions for STUDENT agents.

    Conducted when STUDENT agents are blocked from automated triggers.
    Provides guided learning experiences to build capabilities before autonomy.
    """
    __tablename__ = "training_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Proposal Reference
    proposal_id = Column(String, ForeignKey("agent_proposals.id"), nullable=False, index=True, unique=True)

    # Agent Information
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
    agent_name = Column(String, nullable=False)  # Denormalized

    # Session Status
    status = Column(String, index=True)  # scheduled, in_progress, completed, cancelled, failed

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)  # Actual training duration

    # Supervision
    supervisor_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    supervisor_guidance = Column(JSON, nullable=True)  # Guidance provided during training

    # Training Progress
    tasks_completed = Column(Integer, default=0)  # Number of training tasks completed
    total_tasks = Column(Integer, nullable=True)  # Total tasks in training plan

    # Outcomes
    outcomes = Column(JSON, nullable=True)  # Summary of what was accomplished
    performance_score = Column(Float, nullable=True)  # 0.0 to 1.0
    errors_count = Column(Integer, default=0)  # Number of errors during training
    supervisor_feedback = Column(Text, nullable=True)

    # Maturity Impact
    confidence_boost = Column(Float, nullable=True)  # Confidence increase from training
    promoted_to_intern = Column(Boolean, default=False)  # Whether training led to promotion

    # Capability Development
    capabilities_developed = Column(JSON, nullable=True)  # List of capabilities gained
    capability_gaps_remaining = Column(JSON, nullable=True)  # Gaps still remaining

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    proposal = relationship("AgentProposal", backref=backref("training_session", uselist=False))
    agent = relationship("AgentRegistry", backref="training_sessions")
    supervisor = relationship("User", backref="training_sessions_supervised")

    # Indexes
    __table_args__ = (
        Index('ix_training_sessions_proposal', 'proposal_id'),
        Index('ix_training_sessions_agent', 'agent_id'),
        Index('ix_training_sessions_supervisor', 'supervisor_id'),
        Index('ix_training_sessions_status', 'status'),
        Index('ix_training_sessions_created', 'created_at'),
    )


class Dashboard(Base):
    """
    Analytics dashboard for visualizing workflow and agent performance metrics.
    Supports multiple widget types with customizable configurations.
    """
    __tablename__ = "dashboards"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    # Dashboard configuration (layout, theme, refresh interval, etc.)
    configuration = Column(JSON, default={})

    # Visibility settings
    is_public = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", backref="dashboards")
    widgets = relationship("DashboardWidget", back_populates="dashboard", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('ix_dashboards_owner', 'owner_id'),
        Index('ix_dashboards_public', 'is_public'),
        Index('ix_dashboards_active', 'is_active'),
    )


class DashboardWidget(Base):
    """
    Individual widget within a dashboard.
    Supports various types: charts, metrics, tables, etc.
    """
    __tablename__ = "dashboard_widgets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    dashboard_id = Column(String, ForeignKey("dashboards.id"), nullable=False, index=True)

    # Widget configuration
    widget_type = Column(String(50), nullable=False)  # 'line_chart', 'bar_chart', 'metric', 'table', etc.
    widget_name = Column(String(255), nullable=False)

    # Data source configuration
    data_source = Column(JSON, default={})  # Query type, filters, aggregation, etc.

    # Display configuration
    position = Column(JSON, default={})  # {x, y, width, height, etc.}
    display_config = Column(JSON, default={})  # Colors, labels, axis settings, etc.

    # Refresh settings
    refresh_interval_seconds = Column(Integer, default=300)  # 5 minutes default

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    dashboard = relationship("Dashboard", back_populates="widgets")

    # Indexes
    __table_args__ = (
        Index('ix_dashboard_widgets_dashboard', 'dashboard_id'),
        Index('ix_dashboard_widgets_type', 'widget_type'),
    )


# ============================================================================
# AUTHENTICATION AND SECURITY MODELS
# ============================================================================

class ActiveToken(Base):
    """
    Active JWT Token Tracker

    Tracks issued JWT tokens for proper revocation management.
    When a user logs in or receives a new token, it's tracked here.
    This enables revocation of all user tokens (e.g., on password change).

    Cleanup: Expired entries should be periodically removed via maintenance job.
    """
    __tablename__ = "active_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    jti = Column(String(255), unique=True, nullable=False, index=True)
    issued_at = Column(DateTime, server_default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)  # For cleanup

    # Track which user owns the token
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    # Optional: Track token context (IP, user agent)
    issued_ip = Column(String(50), nullable=True)
    issued_user_agent = Column(String(500), nullable=True)

    # Relationships
    user = relationship("User")

    # Indexes for efficient lookups and cleanup
    __table_args__ = (
        Index('ix_active_tokens_jti', 'jti'),
        Index('ix_active_tokens_expires', 'expires_at'),
        Index('ix_active_tokens_user', 'user_id', 'issued_at'),
    )

class RevokedToken(Base):
    """
    JWT Token Revocation Store

    Tracks revoked JWT tokens for security enforcement.
    When a user logs out, changes password, or has tokens invalidated,
    the JTI (JWT ID) is stored here to prevent further use.

    Cleanup: Expired entries should be periodically removed via maintenance job.
    """
    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    jti = Column(String(255), unique=True, nullable=False, index=True)
    revoked_at = Column(DateTime, server_default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)  # For cleanup

    # Optional: Track which user revoked the token
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)

    # Optional: Track revocation reason (logout, password_change, security_breach, admin_action)
    revocation_reason = Column(String(50), nullable=True)

    # Relationships
    user = relationship("User")

    # Indexes for efficient lookups and cleanup
    __table_args__ = (
        Index('ix_revoked_tokens_jti', 'jti'),
        Index('ix_revoked_tokens_expires', 'expires_at'),
        Index('ix_revoked_tokens_user', 'user_id', 'revoked_at'),
    )

# ============================================================================
# EPISODIC MEMORY MODELS
# ============================================================================

class Episode(Base):
    """
    Episodic memory container for agent interactions.

    Stores coherent segments of agent activity (episodes) with metadata
    for retrieval, governance, and graduation validation.
    """
    __tablename__ = "episodes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Core identity
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)

    # Attribution
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)

    # Relationships
    session_id = Column(String, nullable=True, index=True)  # Links to ChatSession
    execution_ids = Column(JSON, default=list)  # List of AgentExecution IDs

    # Canvas linkage (NEW - Feb 2026)
    canvas_ids = Column(JSON, default=list)  # List of CanvasAudit IDs
    canvas_action_count = Column(Integer, default=0)  # Total canvas actions in episode

    # Feedback linkage (NEW - Feb 2026)
    feedback_ids = Column(JSON, default=list)  # List of AgentFeedback IDs
    aggregate_feedback_score = Column(Float, nullable=True)  # -1.0 to 1.0 aggregate score

    # Supervision linkage (NEW - Feb 2026)
    supervisor_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    supervisor_rating = Column(Integer, nullable=True)  # 1-5 scale
    supervision_feedback = Column(Text, nullable=True)
    intervention_count = Column(Integer, default=0)
    intervention_types = Column(JSON, nullable=True)  # ["pause", "correct", "terminate"]

    # Proposal linkage (NEW - Feb 2026)
    proposal_id = Column(String, ForeignKey("agent_proposals.id"), nullable=True, index=True)
    proposal_outcome = Column(String, nullable=True)  # "approved", "rejected", "modified"
    rejection_reason = Column(Text, nullable=True)

    # Boundaries
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # State
    status = Column(String, default="active", nullable=False, index=True)  # active, completed, archived, consolidated

    # Content
    topics = Column(JSON, default=list)  # Extracted topics
    entities = Column(JSON, default=list)  # Named entities
    importance_score = Column(Float, default=0.5, index=True)  # 0.0 to 1.0

    # Graduation tracking fields
    maturity_at_time = Column(String, nullable=False, index=True)  # STUDENT, INTERN, SUPERVISED, AUTONOMOUS
    human_intervention_count = Column(Integer, default=0, nullable=False)
    human_edits = Column(JSON, default=list)  # List of corrections made
    constitutional_score = Column(Float, nullable=True)  # 0.0 to 1.0
    world_model_state = Column(String, nullable=True)  # Version identifier

    # Lifecycle
    decay_score = Column(Float, default=1.0)  # 0.0 to 1.0, decays over time
    access_count = Column(Integer, default=0, nullable=False)
    consolidated_into = Column(String, ForeignKey("episodes.id"), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    agent = relationship("AgentRegistry", backref="episodes")
    segments = relationship("EpisodeSegment", backref="episode", cascade="all, delete-orphan")
    access_logs = relationship("EpisodeAccessLog", backref="episode", cascade="all, delete-orphan")
    consolidated_episodes = relationship("Episode", remote_side=[id], backref="consolidated_children")
    supervisor = relationship("User", foreign_keys=[supervisor_id], backref="supervised_episodes")
    proposal = relationship("AgentProposal", foreign_keys=[proposal_id], backref="episodes")

    # Indexes
    __table_args__ = (
        Index('ix_episodes_agent', 'agent_id'),
        Index('ix_episodes_user', 'user_id'),
        Index('ix_episodes_workspace', 'workspace_id'),
        Index('ix_episodes_session', 'session_id'),
        Index('ix_episodes_status', 'status'),
        Index('ix_episodes_started_at', 'started_at'),
        Index('ix_episodes_maturity', 'maturity_at_time'),
        Index('ix_episodes_importance', 'importance_score'),
        Index('ix_episodes_agent_canvas', 'agent_id', 'canvas_action_count'),  # NEW - Canvas queries
        Index('ix_episodes_supervisor_id', 'supervisor_id'),  # NEW - Supervision queries
        Index('ix_episodes_supervisor_rating', 'supervisor_rating'),  # NEW - Quality filtering
        Index('ix_episodes_proposal_id', 'proposal_id'),  # NEW - Proposal linkage
    )


class EpisodeSegment(Base):
    """
    Individual segments within an episode.

    Episodes are composed of multiple segments (conversations, executions, reflections)
    that are ordered sequentially to reconstruct the full episode context.
    """
    __tablename__ = "episode_segments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    episode_id = Column(String, ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False, index=True)

    # Segment details
    segment_type = Column(String, nullable=False, index=True)  # conversation, execution, reflection
    sequence_order = Column(Integer, nullable=False)  # For ordering within episode

    # Content
    content = Column(Text, nullable=False)
    content_summary = Column(Text, nullable=True)  # Shortened version for display

    # Source tracking
    source_type = Column(String, nullable=False)  # chat_message, agent_execution, manual
    source_id = Column(String, nullable=True, index=True)  # ID of source object

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Indexes
    __table_args__ = (
        Index('ix_episode_segments_episode', 'episode_id'),
        Index('ix_episode_segments_sequence', 'sequence_order'),
    )


class EpisodeAccessLog(Base):
    """
    Audit trail for episode access.

    Records all episode access operations for governance compliance
    and audit trail requirements.
    """
    __tablename__ = "episode_access_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    episode_id = Column(String, ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False, index=True)

    # Access details
    accessed_by = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    accessed_by_agent = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)

    access_type = Column(String, nullable=False, index=True)  # temporal, semantic, sequential, contextual
    retrieval_query = Column(Text, nullable=True)
    retrieval_mode = Column(String, nullable=True)  # Specific mode used

    # Governance
    governance_check_passed = Column(Boolean, default=True, nullable=False)
    agent_maturity_at_access = Column(String, nullable=True)

    # Results
    results_count = Column(Integer, default=0, nullable=False)
    access_duration_ms = Column(Integer, nullable=True)

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship("User", foreign_keys=[accessed_by])
    agent = relationship("AgentRegistry", foreign_keys=[accessed_by_agent])

    # Indexes
    __table_args__ = (
        Index('ix_episode_access_logs_episode', 'episode_id'),
        Index('ix_episode_access_logs_created_at', 'created_at'),
        Index('ix_episode_access_logs_access_type', 'access_type'),
    )


# ============================================================================
# Messaging Feature Parity Models
# ============================================================================

class ProactiveMessageStatus(str, enum.Enum):
    """Status for proactive messages"""
    PENDING = "pending"
    APPROVED = "approved"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProactiveMessage(Base):
    """
    Proactive messages initiated by agents (not responses).

    Agents can initiate conversations based on business logic, alerts, or automation.
    All proactive messages are governed by agent maturity levels:
    - STUDENT: Blocked from proactive messaging
    - INTERN: Requires human approval before sending
    - SUPERVISED: Sent with real-time monitoring
    - AUTONOMOUS: Full access with audit trail
    """
    __tablename__ = "proactive_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Agent Information
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
    agent_name = Column(String, nullable=False)  # Denormalized for quick queries
    agent_maturity_level = Column(String, nullable=False, index=True)  # STUDENT, INTERN, SUPERVISED, AUTONOMOUS

    # Message Details
    platform = Column(String, nullable=False, index=True)  # slack, discord, whatsapp, etc.
    recipient_id = Column(String, nullable=False, index=True)  # User ID, channel ID, phone number
    content = Column(Text, nullable=False)

    # Scheduling
    scheduled_for = Column(DateTime(timezone=True), nullable=True, index=True)  # Send at specific time
    send_now = Column(Boolean, default=False)  # If True, send immediately (if approved)

    # Status & Approval
    status = Column(String, default=ProactiveMessageStatus.PENDING.value, index=True)
    approved_by = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Governance
    governance_metadata = Column(JSON, default={})  # Governance check results, risk level, etc.

    # Execution
    sent_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    platform_message_id = Column(String, nullable=True)  # ID returned by platform

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    agent = relationship("AgentRegistry", backref="proactive_messages")
    approver = relationship("User", foreign_keys=[approved_by])

    # Indexes
    __table_args__ = (
        Index('ix_proactive_messages_agent_status', 'agent_id', 'status'),
        Index('ix_proactive_messages_platform_status', 'platform', 'status'),
        Index('ix_proactive_messages_scheduled', 'scheduled_for', 'status'),
        Index('ix_proactive_messages_created', 'created_at'),
    )


class ScheduledMessageStatus(str, enum.Enum):
    """Status for scheduled messages"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduledMessage(Base):
    """
    Scheduled and recurring messages.

    Supports one-time and recurring messages with cron expressions.
    Messages can include templates with variable substitution.
    """
    __tablename__ = "scheduled_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Agent Information
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
    agent_name = Column(String, nullable=False)  # Denormalized

    # Schedule Details
    platform = Column(String, nullable=False, index=True)
    recipient_id = Column(String, nullable=False, index=True)

    # Message Content (Template)
    template = Column(Text, nullable=False)  # Can include variables like {{customer_name}}
    template_variables = Column(JSON, default={})  # Variable definitions for substitution

    # Schedule Configuration
    schedule_type = Column(String, nullable=False, index=True)  # one_time, recurring
    cron_expression = Column(String, nullable=True)  # For recurring: "0 9 * * *" (daily at 9am)
    natural_language_schedule = Column(String, nullable=True)  # "every day at 9am"

    # Execution Tracking
    next_run = Column(DateTime(timezone=True), nullable=False, index=True)
    last_run = Column(DateTime(timezone=True), nullable=True)
    run_count = Column(Integer, default=0, nullable=False)

    # Recurring Settings
    max_runs = Column(Integer, nullable=True)  # Limit number of executions (None = infinite)
    end_date = Column(DateTime(timezone=True), nullable=True)  # Stop after this date

    # Status
    status = Column(String, default=ScheduledMessageStatus.ACTIVE.value, index=True)
    timezone = Column(String, default="UTC")  # Timezone for schedule

    # Governance
    governance_metadata = Column(JSON, default={})

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    agent = relationship("AgentRegistry", backref="scheduled_messages")

    # Indexes
    __table_args__ = (
        Index('ix_scheduled_messages_next_run', 'next_run', 'status'),
        Index('ix_scheduled_messages_agent_status', 'agent_id', 'status'),
        Index('ix_scheduled_messages_platform', 'platform', 'status'),
        Index('ix_scheduled_messages_created', 'created_at'),
    )


class ConditionMonitorType(str, enum.Enum):
    """Types of conditions to monitor"""
    INBOX_VOLUME = "inbox_volume"
    TASK_BACKLOG = "task_backlog"
    API_METRICS = "api_metrics"
    DATABASE_QUERY = "database_query"
    COMPOSITE = "composite"


class ConditionAlertStatus(str, enum.Enum):
    """Status for condition alerts"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    ACKNOWLEDGED = "acknowledged"


class ConditionMonitor(Base):
    """
    Real-time business condition monitors.

    Monitors business conditions (inbox volume, task backlog, API metrics, etc.)
    and sends alerts when thresholds are exceeded.
    """
    __tablename__ = "condition_monitors"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Agent Information
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
    agent_name = Column(String, nullable=False)  # Denormalized

    # Monitor Details
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Condition Configuration
    condition_type = Column(String, nullable=False, index=True)  # inbox_volume, task_backlog, api_metrics, etc.
    threshold_config = Column(JSON, nullable=False)  # Threshold configuration
    # Examples:
    # {"metric": "unread_count", "operator": ">", "value": 100}
    # {"metric": "error_rate", "operator": ">", "value": 0.05, "window": "5m"}

    # Composite Conditions (AND/OR logic)
    composite_logic = Column(String, nullable=True)  # "AND", "OR"
    composite_conditions = Column(JSON, nullable=True)  # List of sub-conditions

    # Monitoring Schedule
    check_interval_seconds = Column(Integer, default=300, nullable=False)  # Default: 5 minutes

    # Alert Configuration
    platforms = Column(JSON, nullable=False)  # [{"platform": "slack", "recipient_id": "C12345"}]
    alert_template = Column(Text, nullable=True)  # Alert message template

    # Throttling (prevent alert spam)
    throttle_minutes = Column(Integer, default=60)  # Wait X minutes between alerts
    last_alert_sent_at = Column(DateTime(timezone=True), nullable=True)

    # Status
    status = Column(String, default="active", index=True)  # active, paused, disabled

    # Governance
    governance_metadata = Column(JSON, default={})

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    agent = relationship("AgentRegistry", backref="condition_monitors")
    alerts = relationship("ConditionAlert", backref="monitor", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('ix_condition_monitors_agent_status', 'agent_id', 'status'),
        Index('ix_condition_monitors_type', 'condition_type', 'status'),
        Index('ix_condition_monitors_created', 'created_at'),
    )


class ConditionAlert(Base):
    """
    Alert history for condition monitors.

    Records every time a condition threshold is triggered.
    """
    __tablename__ = "condition_alerts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Monitor Reference
    monitor_id = Column(String, ForeignKey("condition_monitors.id"), nullable=False, index=True)

    # Condition Details
    condition_value = Column(JSON, nullable=False)  # Actual value that triggered alert
    threshold_value = Column(JSON, nullable=False)  # Threshold that was exceeded

    # Alert Content
    alert_message = Column(Text, nullable=False)
    platforms_sent = Column(JSON, default=[])  # [{"platform": "slack", "status": "sent", "message_id": "..."}]

    # Status
    status = Column(String, default=ConditionAlertStatus.PENDING.value, index=True)

    # Timestamps
    triggered_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)

    # Error Handling
    error_message = Column(Text, nullable=True)

    # Indexes
    __table_args__ = (
        Index('ix_condition_alerts_monitor', 'monitor_id', 'triggered_at'),
        Index('ix_condition_alerts_status', 'status'),
        Index('ix_condition_alerts_triggered', 'triggered_at'),
    )


class UnifiedWorkspace(Base):
    """
    Unified workspace model for cross-platform synchronization.

    Supports synchronization across multiple communication platforms:
    - Slack
    - Discord
    - Google Chat
    - Microsoft Teams

    Features:
    - Platform-specific workspace IDs mapping
    - Change detection and propagation
    - Conflict resolution
    - Member synchronization
    """
    __tablename__ = "unified_workspaces"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    # Workspace identification
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Platform-specific IDs (nullable for partial sync)
    slack_workspace_id = Column(String, nullable=True, index=True)
    discord_guild_id = Column(String, nullable=True, index=True)
    google_chat_space_id = Column(String, nullable=True, index=True)
    teams_team_id = Column(String, nullable=True, index=True)

    # Synchronization status
    sync_status = Column(String, default="active", index=True)  # active, paused, error
    last_sync_at = Column(DateTime(timezone=True), default=func.now())
    last_sync_error = Column(Text, nullable=True)

    # Statistics
    platform_count = Column(Integer, default=0)  # Number of connected platforms
    member_count = Column(Integer, default=0)  # Total members across all platforms

    # Sync configuration
    sync_config = Column(JSON, nullable=True)  # {"auto_sync": true, "conflict_resolution": "latest"}

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="unified_workspaces")

    # Indexes
    __table_args__ = (
        Index("ix_unified_workspaces_user", "user_id"),
        Index("ix_unified_workspaces_slack", "slack_workspace_id"),
        Index("ix_unified_workspaces_discord", "discord_guild_id"),
        Index("ix_unified_workspaces_google_chat", "google_chat_space_id"),
        Index("ix_unified_workspaces_teams", "teams_team_id"),
        Index("ix_unified_workspaces_sync_status", "sync_status"),
    )

    def add_platform(self, platform: str, platform_id: str):
        """Add or update a platform mapping"""
        if platform == "slack":
            self.slack_workspace_id = platform_id
        elif platform == "discord":
            self.discord_guild_id = platform_id
        elif platform == "google_chat":
            self.google_chat_space_id = platform_id
        elif platform == "teams":
            self.teams_team_id = platform_id
        else:
            raise ValueError(f"Unknown platform: {platform}")

        # Update platform count
        self.platform_count = sum([
            bool(self.slack_workspace_id),
            bool(self.discord_guild_id),
            bool(self.google_chat_space_id),
            bool(self.teams_team_id)
        ])

    def get_platform_id(self, platform: str) -> Optional[str]:
        """Get platform-specific ID"""
        platform_map = {
            "slack": self.slack_workspace_id,
            "discord": self.discord_guild_id,
            "google_chat": self.google_chat_space_id,
            "teams": self.teams_team_id
        }
        return platform_map.get(platform)


class WorkspaceSyncLog(Base):
    """
    Audit log for workspace synchronization events.

    Tracks all sync operations across platforms for debugging and auditing.
    """
    __tablename__ = "workspace_sync_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Workspace reference
    unified_workspace_id = Column(String, ForeignKey("unified_workspaces.id"), nullable=False, index=True)

    # Sync operation details
    operation = Column(String, nullable=False)  # create, update, delete, propagate
    source_platform = Column(String, nullable=False)  # slack, discord, google_chat, teams
    target_platforms = Column(JSON, nullable=False)  # ["discord", "teams"]

    # Change details
    change_type = Column(String, nullable=False)  # name_change, member_add, member_remove, etc.
    change_data = Column(JSON, nullable=True)  # {"old_name": "...", "new_name": "..."}

    # Status
    status = Column(String, nullable=False)  # success, partial_failure, failure
    error_message = Column(Text, nullable=True)

    # Timing
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Relationships
    unified_workspace = relationship("UnifiedWorkspace", backref="sync_logs")

    # Indexes
    __table_args__ = (
        Index("ix_workspace_sync_logs_workspace", "unified_workspace_id", "started_at"),
        Index("ix_workspace_sync_logs_status", "status"),
        Index("ix_workspace_sync_logs_operation", "operation"),
    )



class GovernanceAuditLog(Base):
    """
    Audit log for governance checks.

    Tracks all governance decisions for compliance, debugging, and analytics.
    """
    __tablename__ = "governance_audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Agent information
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)

    # Action details
    action_type = Column(String, nullable=False, index=True)  # accounting_transaction_create, etc.
    resource_type = Column(String, nullable=True)  # transaction, message, canvas, etc.

    # Governance decision
    allowed = Column(Boolean, nullable=False, index=True)
    agent_maturity = Column(String, nullable=False, index=True)  # STUDENT, INTERN, SUPERVISED, AUTONOMOUS
    required_maturity = Column(String, nullable=False)  # Required maturity for this action
    reason = Column(Text, nullable=True)  # Reason for denial (if not allowed)

    # Context
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    request_id = Column(String, nullable=True, index=True)  # For tracing

    # Timestamps
    checked_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    agent = relationship("AgentRegistry", backref="governance_audit_logs")

    # Indexes
    __table_args__ = (
        Index("ix_governance_audit_logs_agent", "agent_id", "checked_at"),
        Index("ix_governance_audit_logs_action", "action_type", "checked_at"),
        Index("ix_governance_audit_logs_allowed", "allowed", "checked_at"),
        Index("ix_governance_audit_logs_maturity", "agent_maturity", "allowed"),
    )


class SocialPostHistory(Base):
    """
    Social Media Post History

    Tracks all social media posts made through the platform.
    Supports rate limiting and audit trail.
    """
    __tablename__ = "social_post_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    # Post content
    content = Column(Text, nullable=False)
    platforms = Column(JSON, nullable=False)  # ["twitter", "linkedin"]
    media_urls = Column(JSON, nullable=True)  # List of image/video URLs
    link_url = Column(String, nullable=True)  # Attached link

    # Post results
    platform_results = Column(JSON, nullable=True)  # Results from each platform
    post_ids = Column(JSON, nullable=True)  # Platform-specific post IDs

    # Scheduling
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)

    # Background task tracking
    job_id = Column(String, nullable=True, index=True)  # RQ job ID for scheduled posts

    # Status tracking
    status = Column(String, default="pending", index=True)  # pending, posted, failed, scheduled, posting, partial, cancelled
    error_message = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="social_posts")

    # Indexes
    __table_args__ = (
        Index("ix_social_post_history_user_created", "user_id", "created_at"),
        Index("ix_social_post_history_status_created", "status", "created_at"),
        Index("ix_social_post_history_scheduled", "scheduled_for"),
        Index("ix_social_post_history_job_id", "job_id"),
    )


class SecurityAuditLog(Base):
    """
    Security Audit Log

    Tracks security-related events for compliance and monitoring.
    """
    __tablename__ = "security_audit_log"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Event information
    event_type = Column(String(100), nullable=False, index=True)  # webhook_signature_invalid, default_secret_key, etc.
    severity = Column(String(20), nullable=False, index=True)  # critical, warning, info

    # User context
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)

    # Event details
    details = Column(JSON, nullable=False, default=dict)

    # Request context
    request_id = Column(String, nullable=True, index=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)

    # Relationships
    user = relationship("User", backref="security_events")

    # Indexes
    __table_args__ = (
        Index("ix_security_audit_log_timestamp", "timestamp"),
        Index("ix_security_audit_log_event_type", "event_type"),
        Index("ix_security_audit_log_severity", "severity"),
        Index("ix_security_audit_log_user", "user_id", "timestamp"),
        Index("ix_security_audit_log_severity_timestamp", "severity", "timestamp"),
    )


class SocialMediaAudit(Base):
    """
    Social Media Audit Log

    Tracks all social media operations for governance and compliance.
    Ensures all posting actions are attributable and governable.
    """
    __tablename__ = "social_media_audit"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Agent context
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)
    agent_execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    # Action details
    platform = Column(String(50), nullable=False, index=True)  # twitter, linkedin, facebook
    action_type = Column(String(50), nullable=False, index=True)  # post, schedule, delete
    post_id = Column(String, nullable=True, index=True)  # Platform-specific post ID

    # Content tracking
    content = Column(Text, nullable=False)  # Post content
    media_urls = Column(JSON, nullable=True)  # Attached media
    link_url = Column(String, nullable=True)  # Attached link

    # Results
    success = Column(Boolean, nullable=False, default=False, index=True)
    error_message = Column(Text, nullable=True)
    platform_response = Column(JSON, nullable=True)  # Full API response

    # Maturity at time of action
    agent_maturity = Column(String(50), nullable=False, index=True)  # STUDENT, INTERN, SUPERVISED, AUTONOMOUS
    governance_check_passed = Column(Boolean, nullable=False, default=True, index=True)
    required_approval = Column(Boolean, nullable=False, default=False)
    approval_granted = Column(Boolean, nullable=True)

    # Request context
    request_id = Column(String, nullable=True, index=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)

    # Relationships
    agent = relationship("AgentRegistry", backref="social_media_audits")
    execution = relationship("AgentExecution", backref="social_media_audits")
    user = relationship("User", backref="social_media_audits")

    # Indexes
    __table_args__ = (
        Index("ix_social_media_audit_timestamp", "timestamp"),
        Index("ix_social_media_audit_platform", "platform", "timestamp"),
        Index("ix_social_media_audit_action", "action_type", "timestamp"),
        Index("ix_social_media_audit_agent", "agent_id", "timestamp"),
        Index("ix_social_media_audit_user", "user_id", "timestamp"),
        Index("ix_social_media_audit_maturity", "agent_maturity", "governance_check_passed"),
    )


class FinancialAudit(Base):
    """
    Financial Account Audit Log

    Tracks all financial account operations for governance and compliance.
    Ensures all financial actions are attributable and governable.
    """
    __tablename__ = "financial_audit"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Agent context
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)
    agent_execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    # Action details
    account_id = Column(String, ForeignKey("financial_accounts.id"), nullable=False, index=True)
    action_type = Column(String(50), nullable=False, index=True)  # create, update, delete

    # Change tracking
    changes = Column(JSON, nullable=False, default=dict)  # {"field": {"old": "value", "new": "value"}}
    old_values = Column(JSON, nullable=True)  # Full old state
    new_values = Column(JSON, nullable=True)  # Full new state

    # Results
    success = Column(Boolean, nullable=False, default=False, index=True)
    error_message = Column(Text, nullable=True)

    # Maturity at time of action
    agent_maturity = Column(String(50), nullable=False, index=True)
    governance_check_passed = Column(Boolean, nullable=False, default=True, index=True)
    required_approval = Column(Boolean, nullable=False, default=False)
    approval_granted = Column(Boolean, nullable=True)

    # Request context
    request_id = Column(String, nullable=True, index=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)

    # Relationships
    agent = relationship("AgentRegistry", backref="financial_audits")
    execution = relationship("AgentExecution", backref="financial_audits")
    user = relationship("User", backref="financial_audits")
    account = relationship("FinancialAccount", backref="audit_logs")

    # Indexes
    __table_args__ = (
        Index("ix_financial_audit_timestamp", "timestamp"),
        Index("ix_financial_audit_account", "account_id", "timestamp"),
        Index("ix_financial_audit_action", "action_type", "timestamp"),
        Index("ix_financial_audit_agent", "agent_id", "timestamp"),
        Index("ix_financial_audit_user", "user_id", "timestamp"),
        Index("ix_financial_audit_maturity", "agent_maturity", "governance_check_passed"),
    )


class MenuBarAudit(Base):
    """
    Menu Bar Operations Audit Log

    Tracks all menu bar companion app operations for governance and compliance.
    Ensures all menu bar-triggered actions are attributable and governable.
    """
    __tablename__ = "menu_bar_audit"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Agent context
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)
    agent_execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    device_id = Column(String, ForeignKey("device_nodes.device_id"), nullable=True, index=True)

    # Action details
    action = Column(String(100), nullable=False, index=True)  # login, quick_chat, get_agents, etc.
    endpoint = Column(String(200), nullable=False)

    # Request/Response tracking
    request_params = Column(JSON, nullable=True)  # Input parameters
    response_summary = Column(JSON, nullable=True)  # Output summary

    # Results
    success = Column(Boolean, nullable=False, default=False, index=True)
    error_message = Column(Text, nullable=True)

    # Agent maturity at time of action (if agent involved)
    agent_maturity = Column(String(50), nullable=True, index=True)
    governance_check_passed = Column(Boolean, nullable=True, index=True)

    # Request context
    request_id = Column(String, nullable=True, index=True)
    ip_address = Column(String, nullable=True)
    platform = Column(String(50), nullable=True)  # darwin, windows, linux

    # Relationships
    agent = relationship("AgentRegistry", backref="menu_bar_audits")
    execution = relationship("AgentExecution", backref="menu_bar_audits")
    user = relationship("User", backref="menu_bar_audits")
    device = relationship("DeviceNode", backref="menu_bar_audit_logs")

    # Indexes
    __table_args__ = (
        Index("ix_menu_bar_audit_timestamp", "timestamp"),
        Index("ix_menu_bar_audit_action", "action", "timestamp"),
        Index("ix_menu_bar_audit_agent", "agent_id", "timestamp"),
        Index("ix_menu_bar_audit_user", "user_id", "timestamp"),
        Index("ix_menu_bar_audit_device", "device_id", "timestamp"),
        Index("ix_menu_bar_audit_maturity", "agent_maturity", "governance_check_passed"),
    )


# ============================================================================
# AI Debug System Models
# ============================================================================

class DebugEventType(str, enum.Enum):
    """Debug event types for categorization"""
    LOG = "log"
    STATE_SNAPSHOT = "state_snapshot"
    METRIC = "metric"
    ERROR = "error"
    SYSTEM = "system"


class DebugInsightType(str, enum.Enum):
    """Types of insights generated by the debug system"""
    CONSISTENCY = "consistency"  # Data consistency across components
    FLOW = "flow"  # Execution flow and operations
    PERFORMANCE = "performance"  # Performance bottlenecks
    ERROR = "error"  # Error patterns and causality
    ANOMALY = "anomaly"  # Unexpected behavior


class DebugInsightSeverity(str, enum.Enum):
    """Severity levels for debug insights"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DebugEvent(Base):
    """
    Raw Debug Events

    Stores all debug events including logs, state snapshots, metrics, and errors.
    Indexed for fast querying by component, correlation, and time.
    """
    __tablename__ = "debug_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Event categorization
    event_type = Column(String(50), nullable=False, index=True)  # DebugEventType
    component_type = Column(String(50), nullable=False, index=True)  # agent, browser, workflow, system
    component_id = Column(String, nullable=True, index=True)  # Component identifier

    # Correlation and linking
    correlation_id = Column(String, nullable=False, index=True)  # Links related events
    parent_event_id = Column(String, nullable=True, index=True)  # Event chain for tracing

    # Log metadata
    level = Column(String(20), nullable=True, index=True)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message = Column(Text, nullable=True)

    # Event data
    data = Column(JSON, nullable=True)  # Full event data
    event_metadata = Column(JSON, nullable=True)  # Tags, labels, additional context

    # Timestamp
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    insights = relationship("DebugInsight", backref="event", foreign_keys="DebugInsight.source_event_id")

    # Indexes for efficient querying
    __table_args__ = (
        Index("ix_debug_event_timestamp", "timestamp"),
        Index("ix_debug_event_component", "component_type", "component_id", "timestamp"),
        Index("ix_debug_event_correlation", "correlation_id", "timestamp"),
        Index("ix_debug_event_type_level", "event_type", "level", "timestamp"),
        Index("ix_debug_event_parent", "parent_event_id"),
    )

    def __repr__(self):
        return f"<DebugEvent(id={self.id}, type={self.event_type}, component={self.component_type}/{self.component_id})>"


class DebugInsight(Base):
    """
    Abstracted Debug Insights

    High-level insights generated from raw debug events.
    Provides AI agents with abstracted understanding without processing raw logs.
    """
    __tablename__ = "debug_insights"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Insight categorization
    insight_type = Column(String(50), nullable=False, index=True)  # DebugInsightType
    severity = Column(String(20), nullable=False, index=True)  # DebugInsightSeverity

    # Insight content
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)  # Human-readable explanation
    summary = Column(String(500), nullable=False)  # One-line for AI consumption

    # Evidence and confidence
    evidence = Column(JSON, nullable=True)  # Event IDs and excerpts
    confidence_score = Column(Float, nullable=False, default=0.0)  # 0-1

    # Resolution suggestions
    suggestions = Column(JSON, nullable=True)  # Resolution suggestions
    resolved = Column(Boolean, nullable=False, default=False, index=True)
    resolution_notes = Column(Text, nullable=True)

    # Scope and impact
    scope = Column(String(50), nullable=False, index=True)  # component, distributed, system
    affected_components = Column(JSON, nullable=True)  # List of affected components

    # Provenance
    source_event_id = Column(String, ForeignKey("debug_events.id"), nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Insight expiration

    # Indexes
    __table_args__ = (
        Index("ix_debug_insight_generated", "generated_at"),
        Index("ix_debug_insight_type_severity", "insight_type", "severity", "generated_at"),
        Index("ix_debug_insight_scope", "scope", "generated_at"),
        Index("ix_debug_insight_resolved", "resolved", "generated_at"),
        Index("ix_debug_insight_expires", "expires_at"),
    )

    def __repr__(self):
        return f"<DebugInsight(id={self.id}, type={self.insight_type}, severity={self.severity}, title={self.title})>"


class DebugStateSnapshot(Base):
    """
    Component State Snapshots

    Captures state of distributed components at specific points in time.
    Includes diff detection to identify state changes.
    """
    __tablename__ = "debug_state_snapshots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Component identification
    component_type = Column(String(50), nullable=False, index=True)
    component_id = Column(String, nullable=False, index=True)

    # Correlation
    operation_id = Column(String, nullable=False, index=True)  # Operation correlation
    checkpoint_name = Column(String(100), nullable=True)  # Optional label

    # State data
    state_data = Column(JSON, nullable=False)  # Full state capture
    diff_from_previous = Column(JSON, nullable=True)  # Delta from previous snapshot
    snapshot_type = Column(String(20), nullable=False)  # full, incremental, partial

    # Timestamp
    captured_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Indexes
    __table_args__ = (
        Index("ix_debug_state_component", "component_type", "component_id", "captured_at"),
        Index("ix_debug_state_operation", "operation_id", "captured_at"),
        Index("ix_debug_state_checkpoint", "component_id", "checkpoint_name", "captured_at"),
    )

    def __repr__(self):
        return f"<DebugStateSnapshot(id={self.id}, component={self.component_type}/{self.component_id}, type={self.snapshot_type})>"


class DebugMetric(Base):
    """
    Time-Series Debug Metrics

    Stores performance and operational metrics for monitoring and analytics.
    Enables trend analysis and anomaly detection.
    """
    __tablename__ = "debug_metrics"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Metric identification
    metric_name = Column(String(100), nullable=False, index=True)
    component_type = Column(String(50), nullable=False, index=True)
    component_id = Column(String, nullable=True, index=True)

    # Metric value
    value = Column(Float, nullable=False)
    unit = Column(String(20), nullable=True)  # ms, count, percentage, etc.

    # Dimensions for aggregation
    dimensions = Column(JSON, nullable=True)  # Additional dimensions for filtering

    # Timestamp
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Indexes
    __table_args__ = (
        Index("ix_debug_metric_name_timestamp", "metric_name", "timestamp"),
        Index("ix_debug_metric_component", "component_type", "component_id", "timestamp"),
        Index("ix_debug_metric_dimensions", "metric_name", "timestamp"),
    )

    def __repr__(self):
        return f"<DebugMetric(id={self.id}, name={self.metric_name}, value={self.value}, unit={self.unit})>"


class DebugSession(Base):
    """
    Interactive Debug Sessions

    Manages debugging sessions for interactive troubleshooting.
    Tracks queries, insights, and resolutions.
    """
    __tablename__ = "debug_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Session context
    session_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Filters and scope
    filters = Column(JSON, nullable=True)  # Applied filters
    scope = Column(JSON, nullable=True)  # Component scope

    # Session tracking
    event_count = Column(Integer, nullable=False, default=0)
    insight_count = Column(Integer, nullable=False, default=0)
    query_count = Column(Integer, nullable=False, default=0)

    # Status
    active = Column(Boolean, nullable=False, default=True, index=True)
    resolved = Column(Boolean, nullable=False, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)

    # Indexes
    __table_args__ = (
        Index("ix_debug_session_created", "created_at"),
        Index("ix_debug_session_active", "active", "created_at"),
        Index("ix_debug_session_resolved", "resolved", "created_at"),
    )

    def __repr__(self):
        return f"<DebugSession(id={self.id}, name={self.session_name}, active={self.active})>"


# ============================================================================
# Learning and Analysis Models
# ============================================================================

class LearningPlan(Base):
    """
    AI-Generated Personalized Learning Plans

    Stores structured learning paths with modules, resources, exercises,
    milestones, and assessment criteria. Supports progress tracking and
    adaptive learning based on user feedback.
    """
    __tablename__ = "learning_plans"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    # Plan details
    topic = Column(String, nullable=False)
    current_skill_level = Column(String, nullable=False)  # beginner, intermediate, advanced
    target_skill_level = Column(String, nullable=False)
    duration_weeks = Column(Integer, nullable=False)

    # Learning content
    modules = Column(JSON, nullable=False)  # List of LearningModule objects
    milestones = Column(JSON, nullable=False)  # List of milestone strings
    assessment_criteria = Column(JSON, nullable=False)  # List of criteria

    # Progress tracking
    progress = Column(JSON, default=dict)  # {completed_modules: [], feedback_scores: {}, time_spent: {}, adjustments_made: []}

    # Notion integration
    notion_database_id = Column(String, nullable=True)
    notion_page_id = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="learning_plans")

    # Indexes
    __table_args__ = (
        Index('ix_learning_plans_user_created', 'user_id', 'created_at'),
    )

    def __repr__(self):
        return f"<LearningPlan(id={self.id}, topic={self.topic}, user_id={self.user_id})>"


class CompetitorAnalysis(Base):
    """
    AI-Powered Competitor Analysis Results

    Stores comprehensive competitor analysis with caching support.
    Includes insights, comparison matrix, and recommendations.
    """
    __tablename__ = "competitor_analyses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    # Analysis parameters
    competitors = Column(JSON, nullable=False)  # List of competitor names/URLs
    analysis_depth = Column(String, nullable=False)  # basic, standard, comprehensive
    focus_areas = Column(JSON, nullable=False)  # List of focus areas

    # Analysis results
    insights = Column(JSON, nullable=False)  # CompetitorInsight per competitor
    comparison_matrix = Column(JSON, nullable=False)  # Cross-competitor comparison
    recommendations = Column(JSON, nullable=False)  # Strategic recommendations

    # Notion integration
    notion_database_id = Column(String, nullable=True)
    notion_page_id = Column(String, nullable=True)

    # Caching
    status = Column(String, default="complete")  # complete, cached, expired
    cache_expiry = Column(DateTime(timezone=True), nullable=True, index=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship("User", backref="competitor_analyses")

    # Indexes
    __table_args__ = (
        Index('ix_competitor_analyses_user_created', 'user_id', 'created_at'),
        Index('ix_competitor_analyses_cache_expiry', 'cache_expiry'),
    )

    def __repr__(self):
        return f"<CompetitorAnalysis(id={self.id}, competitors={self.competitors}, user_id={self.user_id})>"


class ProjectHealthHistory(Base):
    """
    Project Health Check History

    Stores snapshots of project health metrics over time.
    Enables trend analysis and alerting.
    """
    __tablename__ = "project_health_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    # Check identification
    check_id = Column(String, nullable=False, index=True)

    # Overall results
    overall_score = Column(Float, nullable=False)
    overall_status = Column(String, nullable=False)  # excellent, good, warning, critical

    # Individual metrics
    metrics = Column(JSON, nullable=False)  # {metric_name: HealthMetric}

    # Time range analyzed
    time_range_days = Column(Integer, nullable=False)

    # Timestamp
    checked_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship("User", backref="project_health_history")

    # Indexes
    __table_args__ = (
        Index('ix_project_health_history_user_checked', 'user_id', 'checked_at'),
        Index('ix_project_health_history_check_id', 'check_id'),
    )

    def __repr__(self):
        return f"<ProjectHealthHistory(id={self.id}, check_id={self.check_id}, score={self.overall_score})>"


class CustomerChurnPrediction(Base):
    """
    Customer Churn Risk Predictions

    Stores AI-generated churn risk predictions with risk factors
    and recommended actions.
    """
    __tablename__ = "customer_churn_predictions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, nullable=False, index=True)

    # Customer info
    customer_id = Column(String, nullable=False)
    customer_name = Column(String, nullable=False)

    # Prediction results
    churn_probability = Column(Float, nullable=False)
    risk_factors = Column(JSON, nullable=False)  # List of risk factors
    mrr_at_risk = Column(Float, nullable=False)
    recommended_action = Column(Text, nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Indexes
    __table_args__ = (
        Index('ix_churn_predictions_workspace_created', 'workspace_id', 'created_at'),
        Index('ix_churn_predictions_probability', 'churn_probability'),
    )

    def __repr__(self):
        return f"<CustomerChurnPrediction(id={self.id}, customer={self.customer_name}, probability={self.churn_probability})>"


class ARDelayPrediction(Base):
    """
    Accounts Receivable Delay Predictions

    Stores predictions for late invoice payments based on
    client payment history.
    """
    __tablename__ = "ar_delay_predictions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, nullable=False, index=True)

    # Invoice info
    invoice_id = Column(String, nullable=False)
    client_name = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False)

    # Prediction results
    likelihood_late = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Indexes
    __table_args__ = (
        Index('ix_ar_predictions_workspace_created', 'workspace_id', 'created_at'),
        Index('ix_ar_predictions_due_date', 'due_date'),
    )

    def __repr__(self):
        return f"<ARDelayPrediction(id={self.id}, invoice={self.invoice_id}, likelihood={self.likelihood_late})>"


# ============================================================================
# Multi-Level Agent Supervision System Models
# ============================================================================

class UserState(str, enum.Enum):
    """User activity state for supervision routing"""
    online = "online"
    away = "away"
    offline = "offline"


class QueueStatus(str, enum.Enum):
    """Status for supervised execution queue"""
    pending = "pending"
    executing = "executing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class UserActivity(Base):
    """
    Track user activity state for supervision availability.

    Records user's current state (online/away/offline) to determine
    if they can supervise INTERN and SUPERVISED agents.
    """
    __tablename__ = "user_activities"

    id = Column(String, primary_key=True, default=lambda: f"ua_{str(uuid.uuid4())}")
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True, unique=True)
    state = Column(SQLEnum(UserState), nullable=False, default=UserState.offline, index=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    manual_override = Column(Boolean, default=False)
    manual_override_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="activity")
    sessions = relationship("UserActivitySession", back_populates="activity", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('ix_user_activity_state_updated', 'state', 'updated_at'),
    )


class UserActivitySession(Base):
    """
    User sessions for activity tracking.

    Each web/desktop session sends heartbeats to track user activity.
    A user is considered online if ANY session is active.
    """
    __tablename__ = "user_activity_sessions"

    id = Column(String, primary_key=True, default=lambda: f"us_{str(uuid.uuid4())}")
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    activity_id = Column(String, ForeignKey("user_activities.id"), nullable=False, index=True)
    session_type = Column(String, nullable=False)  # "web" or "desktop"
    session_token = Column(String, nullable=False, unique=True, index=True)
    last_heartbeat = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    terminated_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", backref="activity_sessions")
    activity = relationship("UserActivity", back_populates="sessions")

    # Indexes
    __table_args__ = (
        Index('ix_user_activity_session_heartbeat', 'last_heartbeat'),
    )


class SupervisedExecutionQueue(Base):
    """
    Queue for SUPERVISED agent executions when users are unavailable.

    When a SUPERVISED agent triggers but the user is offline, the execution
    is queued and auto-executed when the user returns online.
    """
    __tablename__ = "supervised_execution_queue"

    id = Column(String, primary_key=True, default=lambda: f"queue_{str(uuid.uuid4())}")
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    trigger_type = Column(String, nullable=False)  # "automated" or "manual"
    execution_context = Column(JSON, nullable=False)  # Serialized execution context
    status = Column(SQLEnum(QueueStatus), nullable=False, default=QueueStatus.pending, index=True)
    supervisor_type = Column(String, nullable=False)  # "user" or "autonomous_agent"
    priority = Column(Integer, default=0, index=True)  # Higher priority = executed first
    max_attempts = Column(Integer, default=3)
    attempt_count = Column(Integer, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    agent = relationship("AgentRegistry", backref="queued_executions")
    user = relationship("User", backref="queued_executions")
    execution = relationship("AgentExecution", backref="queue_entry")

    # Indexes
    __table_args__ = (
        Index('ix_supervised_queue_user_status', 'user_id', 'status'),
        Index('ix_supervised_queue_priority_created', 'priority', 'created_at'),
        Index('ix_supervised_queue_expires', 'expires_at'),
    )
