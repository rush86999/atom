from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Boolean, Float, Text, Index,
    Table, JSON, MetaData, select, update, delete, func, and_, or_, not_,
    UniqueConstraint, Enum as SQLEnum, BigInteger, TypeDecorator, Numeric, Date
)
from sqlalchemy.orm import relationship, sessionmaker, Session, declared_attr, DeclarativeBase
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
import uuid
from decimal import Decimal

# pgvector is optional - graceful degradation if not installed
try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    # Use JSON as fallback for embedding storage
    Vector = None


class UUID(TypeDecorator):
    """
    Platform-independent UUID type.

    Uses PostgreSQL UUID type when available, falls back to String(36) for SQLite.
    This enables tests to use SQLite in-memory databases while production uses PostgreSQL.
    """
    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PGUUID)
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        return uuid.UUID(value) if isinstance(value, str) else value


class JSONColumn(TypeDecorator):
    """
    Platform-independent JSON type.

    Uses PostgreSQL JSONB type when available for better performance,
    falls back to JSON for SQLite and other databases.
    This enables tests to use SQLite in-memory databases while production uses PostgreSQL.
    """
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(JSONB)
        else:
            return dialect.type_descriptor(JSON)


class JSONBColumn(TypeDecorator):
    """
    PostgreSQL-specific JSONB type for fields that require JSONB operators.

    NOTE: GraphRAG functionality will NOT work on SQLite (JSON) as it requires 
    JSONB operators (@>, ?, etc.) which are only available in PostgreSQL.

    WARNING: This type primarily works with PostgreSQL.
    Use this ONLY for fields that need:
    - JSONB query operators (@>, ?, ?, etc.)
    - JSONPath expressions
    - GIN indexes for JSON queries
    """
    impl = JSONB
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(JSONB)
        else:
            # Fallback to JSON for SQLite/etc to support tests and local development
            return dialect.type_descriptor(JSON)

from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
import enum
from datetime import datetime, timezone
import os
from core.database import Base
from core.data_visibility import DataVisibility

# Embedding dimension configuration - OpenAI text-embedding-3-small (1536 dimensions)
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))

# Enums
class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    OWNER = "owner"
    ADMIN = "admin"
    WORKSPACE_ADMIN = "workspace_admin"
    TEAM_LEAD = "team_lead"
    MEMBER = "member"
    VIEWER = "viewer"
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

class ExecutionStatus(str, enum.Enum):
    """Universal execution status for agents, workflows, and jobs"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    TIMEOUT = "timeout"

class AuditEventType(str, enum.Enum):
    """Types of audit events"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    LOGIN = "login"
    LOGOUT = "logout"
    ACCESS = "access"
    GOVERNANCE = "governance"

class SecurityLevel(str, enum.Enum):
    """Security/Severity levels for audit logs"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class DebugEventType(str, enum.Enum):
    """Types of debug events"""
    LOG = "log"
    STATE_SNAPSHOT = "state_snapshot"
    METRIC = "metric"
    ERROR = "error"
    SYSTEM = "system"

class DebugInsightType(str, enum.Enum):
    """Types of debug insights"""
    ERROR = "error"
    PERFORMANCE = "performance"
    ANOMALY = "anomaly"
    CONSISTENCY = "consistency"
    FLOW = "flow"

class DebugInsightSeverity(str, enum.Enum):
    """Severity levels for debug insights"""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"

class PostType(str, enum.Enum):
    """Types of social posts - SOCIAL-01"""
    STATUS = "status"
    INSIGHT = "insight"
    QUESTION = "question"
    ALERT = "alert"
    TASK = "task"

class AuthorType(str, enum.Enum):
    """Author types for social posts"""
    AGENT = "agent"
    HUMAN = "human"

class PackageMaturityLevel(str, enum.Enum):
    """Agent maturity levels for package access control"""
    STUDENT = "student"
    INTERN = "intern"
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"

class PackageType(str, enum.Enum):
    """Package manager types for multi-language support"""
    PYTHON = "python"
    NPM = "npm"
    YARN = "yarn"
    PNPM = "pnpm"

class InstallationStatus(str, enum.Enum):
    """Package installation status"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

# Association Tables
team_members = Table(
    'team_members',
    Base.metadata,
    Column('user_id', String, ForeignKey('users.id'), primary_key=True),
    Column('team_id', String, ForeignKey('teams.id'), primary_key=True),
    Column('role', String, default="member"),
    Column('joined_at', DateTime(timezone=True), server_default=func.now()),
    extend_existing=True  # Allow redefinition during test collection
)

user_workspaces = Table(
    'user_workspaces',
    Base.metadata,
    Column('user_id', String, ForeignKey('users.id'), primary_key=True),
    Column('workspace_id', String, ForeignKey('workspaces.id'), primary_key=True),
    Column('role', String, default="member"),
    Column('joined_at', DateTime(timezone=True), server_default=func.now()),
    extend_existing=True  # Allow redefinition during test collection
)

class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default=WorkspaceStatus.ACTIVE.value)
    plan_tier = Column(String, default="standard")
    
    # Multi-tenant isolation
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)

    # Autonomous Agent Guardrails
    is_startup = Column(Boolean, default=False)
    learning_phase_completed = Column(Boolean, default=False)
    metadata_json = Column(JSONColumn, default={}) # Governance & Config
    internal_domains = Column(Text, nullable=True)  # JSON string: ["atom.ai", "example.com"]

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    users = relationship("User", secondary=user_workspaces, back_populates="workspaces")
    teams = relationship("Team", back_populates="workspace")
    products_services = relationship("BusinessProductService", back_populates="workspace")

class PlanType(str, enum.Enum):
    FREE = "free"
    SOLO = "solo"
    TEAM = "team"
    ENTERPRISE = "enterprise"

class Tenant(Base):
    """Tenant model for SaaS multi-tenancy"""
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    subdomain = Column(String, unique=True, nullable=False, index=True)
    # Custom domain for tenant (column named 'domain' in database for sync compatibility)
    custom_domain = Column("domain", String, nullable=True)
    plan_type = Column(String, default=PlanType.FREE.value)

    # Edition: 'personal' or 'enterprise'
    # Personal: Local agent, limited IM (Telegram only), single user
    # Enterprise: Full platform, all IM, multi-user, all features
    edition = Column(String, nullable=False, default="personal", index=True)

    # Feature flags
    segregated_namespaces = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Additional fields
    computer_use_count = Column(Integer, default=0)
    last_desktop_sync = Column(DateTime(timezone=True), nullable=True)
    api_key = Column(String, unique=True, nullable=True)
    status = Column(String, default="active")
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    api_calls_count = Column(Integer, default=0)
    ai_mode = Column(String, default="byok")  # byok, managed, hybrid

    # Edition helper properties
    @property
    def is_personal(self) -> bool:
        """Check if tenant is on Personal Edition"""
        return self.edition == "personal"

    @property
    def is_enterprise(self) -> bool:
        """Check if tenant is on Enterprise Edition"""
        return self.edition == "enterprise"

    @property
    def edition_display_name(self) -> str:
        """Get human-readable edition name"""
        return {
            "personal": "Personal Edition",
            "enterprise": "Enterprise Edition"
        }.get(self.edition, "Personal Edition")

    def can_upgrade_to_enterprise(self) -> bool:
        """Check if tenant can be upgraded to Enterprise"""
        return self.is_personal

    # Relationships
    # Note: Tenant settings are stored in the tenant_settings table, not as a column
    push_tokens = relationship("PushToken", back_populates="tenant", cascade="all, delete-orphan")
    settings_list = relationship("TenantSetting", back_populates="tenant", cascade="all, delete-orphan")

class TenantSetting(Base):
    """Model for tenant-specific settings and API keys"""
    __tablename__ = "tenant_settings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    setting_key = Column(String(255), nullable=False)
    setting_value = Column(Text, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", back_populates="settings_list")

    __table_args__ = (
        UniqueConstraint('tenant_id', 'setting_key', name='_tenant_setting_uc'),
    )

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


class IntegrationCanvasNode(Base):
    """Represents an integration placed on a canvas for visual management."""
    __tablename__ = "integration_canvas_nodes"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    canvas_id = Column(String, ForeignKey("canvases.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    integration_id = Column(String, nullable=False, index=True)  # e.g., "salesforce", "slack"
    integration_instance_id = Column(String, nullable=True)  # For multi-account support
    
    # Visual Properties
    position = Column(JSONColumn, default={"x": 0, "y": 0})
    size = Column(JSONColumn, default={"width": 300, "height": 200})
    z_index = Column(Integer, default=0)
    
    # Configuration
    config = Column(JSONColumn, default={})  # Integration-specific settings
    display_name = Column(String, nullable=True)
    icon_override = Column(String, nullable=True)
    
    # Status
    status = Column(String, default="active")  # active, error, disconnected
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Agent Assignment
    assigned_agent_ids = Column(JSONColumn, default=[])
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class IntegrationConnection(Base):
    """Represents a workflow connection between integrations on a canvas."""
    __tablename__ = "integration_connections"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    canvas_id = Column(String, ForeignKey("canvases.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    source_node_id = Column(String, ForeignKey("integration_canvas_nodes.id", ondelete="CASCADE"), nullable=False)
    target_node_id = Column(String, ForeignKey("integration_canvas_nodes.id", ondelete="CASCADE"), nullable=False)
    
    # Connection Type
    connection_type = Column(String, default="trigger")  # trigger, sync, transform
    
    # Data Mapping
    data_mapping = Column(JSONColumn, default={})  # Field mapping rules
    transform_script = Column(Text, nullable=True)  # Optional JS/Python transform
    
    # Filtering
    filter_conditions = Column(JSONColumn, default={})
    
    # Status
    status = Column(String, default="active")
    last_execution_at = Column(DateTime(timezone=True), nullable=True)
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=True) # Nullable for SSO users
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    role = Column(String, default=UserRole.MEMBER.value)
    custom_role_id = Column(String, ForeignKey("custom_roles.id"), nullable=True)
    
    # Domain Specialty (e.g. "Accountant", "Marketer", "Sales")
    specialty = Column(String, nullable=True) 
    
    status = Column(String, default=UserStatus.ACTIVE.value)
    
    # Resource Management
    skills = Column(Text, nullable=True) # JSON string of skills
    
    # Onboarding
    onboarding_completed = Column(Boolean, default=False)
    onboarding_step = Column(String, default="welcome")
    metadata_json = Column(JSONColumn, nullable=True)
    preferences = Column(JSONColumn, default={}) # User Preferences (Phase 45)
    
    # Resource Management (SaaS Parity)
    capacity_hours = Column(Float, default=40.0) # Weekly capacity
    hourly_cost_rate = Column(Float, default=0.0) # Internal labor cost
    notification_preferences = Column(JSONBColumn, nullable=True) # Notification preferences (Phase 214)
    
    # Verification (Restored)
    verification_token = Column(String, nullable=True)
    email_verified = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    # 2FA Fields
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String, nullable=True) # Should be encrypted in a real production app
    two_factor_backup_codes = Column(JSONColumn, nullable=True)

    # Relationships
    workspaces = relationship("Workspace", secondary=user_workspaces, back_populates="users")
    teams = relationship("Team", secondary=team_members, back_populates="members")
    messages = relationship("TeamMessage", back_populates="sender")
    push_tokens = relationship("PushToken", back_populates="user", cascade="all, delete-orphan")
    custom_role = relationship("CustomRole")
    im_accounts = relationship("UserAccount", back_populates="user", cascade="all, delete-orphan")

    @property
    def name(self) -> str:
        """Full name combining first and last name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or ""

class AdminRole(Base):
    """
    Admin Role with permissions for admin user management
    Defines what actions admin users can perform
    """
    __tablename__ = "admin_roles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, nullable=False, index=True)
    permissions = Column(JSON, default={}, nullable=False)  # {"users": True, "workflows": False}
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    admin_users = relationship("AdminUser", back_populates="role")

    def __repr__(self):
        return f"<AdminRole(id={self.id}, name={self.name})>"


class AdminUser(Base):
    """
    Admin User for administrative access control
    Separate from regular User model for security isolation
    """
    __tablename__ = "admin_users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    password_hash = Column(String, nullable=False)
    role_id = Column(String, ForeignKey("admin_roles.id"), nullable=False, index=True)
    status = Column(String(50), default="active", nullable=False)  # active, inactive
    last_login = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    role = relationship("AdminRole", back_populates="admin_users")

    def __repr__(self):
        return f"<AdminUser(id={self.id}, email={self.email}, role_id={self.role_id})>"

class UserAccount(Base):
    """
    Links user accounts to IM platform accounts (Telegram, WhatsApp, Signal)
    Maintains tenant isolation for all IM-linked operations
    """
    __tablename__ = "user_accounts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    platform = Column(String, nullable=False)  # telegram, whatsapp, signal
    platform_user_id = Column(String)  # Platform's internal user ID
    chat_id = Column(String, index=True)  # For direct messaging
    username = Column(String)  # Platform username/handle
    linked_at = Column(DateTime(timezone=True), default=lambda: datetime.utcnow(), nullable=False)
    last_used_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    user = relationship("User", back_populates="im_accounts")
    tenant = relationship("Tenant")

    __table_args__ = (
        UniqueConstraint('platform', 'platform_user_id', name='uq_user_accounts_platform_user'),
    )

    def __repr__(self):
        return f"<UserAccount(user_id={self.user_id}, platform={self.platform}, chat_id={self.chat_id})>"

class IMAuditLog(Base):
    """
    Audit log for all IM-linked actions
    Tracks commands sent via IM for compliance and debugging
    """
    __tablename__ = "im_audit_log"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"))
    platform = Column(String, nullable=False)  # telegram, whatsapp, signal
    chat_id = Column(String, nullable=False)
    action = Column(String, nullable=False)  # command_sent, response_received, link_request
    agent_id = Column(String, ForeignKey("agent_registry.id"))
    command = Column(Text)
    response = Column(Text)
    status = Column(String, nullable=False)  # success, error, blocked, rate_limited
    error_message = Column(Text)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.utcnow(), nullable=False, index=True)

    # Relationships
    tenant = relationship("Tenant")
    user = relationship("User")
    agent = relationship("AgentRegistry")

    def __repr__(self):
        return f"<IMAuditLog(platform={self.platform}, action={self.action}, status={self.status})>"

class LinkToken(Base):
    """
    Tokens for secure account linking between IM platforms and Atom
    Generated in dashboard, redeemed in IM app
    """
    __tablename__ = "link_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    token = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    platform = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.utcnow(), nullable=False)

    # Relationships
    user = relationship("User")
    tenant = relationship("Tenant")

    @property
    def is_valid(self) -> bool:
        """Check if token is still valid (not expired and not used)"""
        return self.expires_at > datetime.utcnow() and self.used_at is None

    def __repr__(self):
        return f"<LinkToken(token={self.token[:8]}..., platform={self.platform})>"

class ShellAuditLog(Base):
    """
    Audit log for all shell command executions.
    Tracks agent shell commands for security monitoring and compliance.
    """
    __tablename__ = "shell_audit_log"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"))
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)
    agent_maturity_level = Column(String, nullable=False, index=True)
    command = Column(String, nullable=False)
    args = Column(JSONColumn, nullable=False)  # Stored as JSON array of strings
    working_directory = Column(String)
    exit_code = Column(Integer)
    stdout = Column(Text)
    stderr = Column(Text)
    duration_ms = Column(BigInteger, nullable=False)
    timeout_seconds = Column(Integer)
    success = Column(Boolean, nullable=False, default=False, index=True)
    error_message = Column(Text)
    required_approval = Column(Boolean, nullable=False, default=False)
    approval_granted = Column(Boolean, nullable=True)
    approved_by = Column(String)  # user_id or 'auto' for mature agents
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.utcnow(), nullable=False, index=True)
    source = Column(String, nullable=False, default="tauri")  # tauri, im, api

    # Relationships
    tenant = relationship("Tenant")
    user = relationship("User")
    agent = relationship("AgentRegistry")

    @property
    def full_command(self) -> str:
        """Return full command string with args"""
        import json
        args_list = json.loads(self.args) if isinstance(self.args, str) else self.args
        if args_list:
            return f"{self.command} {' '.join(args_list)}"
        return self.command

    @property
    def was_approved(self) -> bool:
        """Check if execution required and received approval"""
        return not self.required_approval or (self.required_approval and self.approval_granted)

    def __repr__(self):
        return f"<ShellAuditLog(command={self.command}, success={self.success}, maturity={self.agent_maturity_level})>"

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
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
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
    completed_at = Column(DateTime(timezone=True), nullable=True)
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
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
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
    __tablename__ = "saas_audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String, nullable=False)
    security_level = Column(String, nullable=False)
    threat_level = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    user_email = Column(String, nullable=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
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
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
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
    PENDING_2FA = "pending_2fa"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"

class AgentJob(Base):
    __tablename__ = "agent_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    agent_id = Column(String, nullable=False, index=True)
    status = Column(String, default=AgentJobStatus.PENDING.value, index=True)
    start_time = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    logs = Column(Text, nullable=True) # JSON Logs
    result_summary = Column(Text, nullable=True) # JSON Result

    __table_args__ = (
        Index('idx_agent_job_lookup', 'agent_id', 'start_time'),
    )

class AgentOperationTracker(Base):
    """Tracker for agent operations broadcasted to canvas."""
    __tablename__ = "agent_operation_tracker"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True)
    operation_type = Column(String(100), nullable=False)
    operation_id = Column(String(255), nullable=False, index=True, unique=True)
    
    current_step = Column(String(255), nullable=False)
    total_steps = Column(Integer, nullable=True)
    current_step_index = Column(Integer, default=0)
    
    status = Column(String(50), default="running", index=True) # running, completed, failed
    progress = Column(Integer, default=0) # 0-100
    
    what_explanation = Column(Text, nullable=True)
    why_explanation = Column(Text, nullable=True)
    next_steps = Column(Text, nullable=True)
    
    operation_metadata = Column(JSONColumn, default={})
    logs = Column(JSONColumn, default=list) # List of log dictionaries
    
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant")
    agent = relationship("AgentRegistry")
    user = relationship("User")
    workspace = relationship("Workspace")

class AgentRequestLog(Base):
    """Log of requests sent from agents to users for permission/decisions."""
    __tablename__ = "agent_request_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    request_id = Column(String(255), nullable=False, index=True, unique=True)
    request_type = Column(String(50), nullable=False) # permission, decision, etc
    
    request_data = Column(JSONColumn, nullable=False) # Full request context
    user_response = Column(JSONColumn, nullable=True) # User's response
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    responded_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    response_time_seconds = Column(Integer, nullable=True)
    revoked = Column(Boolean, default=False)

    # Relationships
    tenant = relationship("Tenant")
    agent = relationship("AgentRegistry")
    user = relationship("User")

class OperationErrorResolution(Base):
    """
    Track error resolution outcomes for learning and guidance.

    Records which resolutions work for which errors to improve
    automated error guidance suggestions over time.
    """
    __tablename__ = "operation_error_resolutions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Error identification
    error_type = Column(String(100), nullable=False, index=True)
    error_code = Column(String(50), nullable=True, index=True)

    # Resolution details
    resolution_attempted = Column(Text, nullable=False)
    success = Column(Boolean, nullable=False, default=False, index=True)

    # Feedback
    user_feedback = Column(Text, nullable=True)
    agent_suggested = Column(Boolean, default=True, index=True)

    # Timestamps
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Metadata
    operation_id = Column(String, ForeignKey("agent_operation_tracker.operation_id", ondelete="SET NULL"), nullable=True, index=True)
    resolution_metadata = Column(JSONColumn, default={})

    # Relationships
    tenant = relationship("Tenant")
    operation = relationship("AgentOperationTracker")

    def __repr__(self):
        return f"<OperationErrorResolution(id={self.id}, error_type={self.error_type}, success={self.success})>"

class ViewOrchestrationState(Base):
    """
    Track multi-view orchestration state for agent guidance.

    Manages which views (browser, terminal, canvas) are active and their layout.
    """
    __tablename__ = "view_orchestration_state"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id", ondelete="SET NULL"), nullable=True, index=True)

    # Session tracking
    session_id = Column(String(255), nullable=False, unique=True, index=True)

    # View management
    active_views = Column(JSONColumn, nullable=False, default=list)  # List of active view configs
    layout = Column(String(50), nullable=False, default="canvas")  # canvas, split_horizontal, split_vertical, tabs, grid

    # Control
    controlling_agent = Column(String, ForeignKey("agent_registry.id", ondelete="SET NULL"), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now())

    # Metadata
    orchestration_metadata = Column(JSONColumn, default={})

    # Relationships
    tenant = relationship("Tenant")
    user = relationship("User")
    agent = relationship("AgentRegistry", foreign_keys=[agent_id])
    controller = relationship("AgentRegistry", foreign_keys=[controlling_agent])

    def __repr__(self):
        return f"<ViewOrchestrationState(id={self.id}, session_id={self.session_id}, layout={self.layout})>"

class AgentExecution(Base):
    """
    Detailed execution record for an Agent run (Phase 30).
    Replaces simpler AgentJob for detailed tracing.
    """
    __tablename__ = "agent_executions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    chain_id = Column(String, ForeignKey("delegation_chains.id"), nullable=True, index=True) # Phase 10
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=True, index=True)

    status = Column(String, default=ExecutionStatus.RUNNING.value, index=True)
    input_summary = Column(Text, nullable=True)
    triggered_by = Column(String, default="manual") # manual, schedule, websocket, event

    started_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, default=0.0)

    result_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    metadata_json = Column(JSONColumn, default={}) # Phase 110: Extensible tracking for complexity, etc.

    __table_args__ = (
        Index('idx_agent_execution_lookup', 'agent_id', 'started_at'),
    )

    # Episodic Memory Tracking (Phase: Episodic Memory & Graduation)
    human_intervention_count = Column(Integer, default=0)  # Number of human interventions during execution

    # Relationships
    agent = relationship("AgentRegistry")

class AgentReasoningStep(Base):
    """
    Persisted reasoning step for an agent execution (ReAct thought/action).
    """
    __tablename__ = "agent_reasoning_steps"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    execution_id = Column(String, ForeignKey("agent_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    step_number = Column(Integer, nullable=False)
    step_type = Column(String, nullable=False) # thought, action, observation, final_answer
    
    thought = Column(Text, nullable=True)
    action = Column(JSONColumn, nullable=True) # {tool: str, params: dict}
    observation = Column(Text, nullable=True)
    
    confidence = Column(Float, default=1.0)
    duration_ms = Column(Float, default=0.0)
    
    # RLHF Feedback (Phase 6)
    feedback_score = Column(Integer, nullable=True) # 1 (like) or -1 (dislike)
    feedback_text = Column(Text, nullable=True)     # Optional user comment
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    execution = relationship("AgentExecution", backref="reasoning_steps")

class AgentFailureTracking(Base):
    """
    Track consecutive failures for agent stuck detection (Phase 73).

    Stores failure counts and stuck status per tenant-agent pair.
    Enables automatic detection of agents that are stuck in failure loops.
    """
    __tablename__ = "agent_failure_tracking"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)

    consecutive_failure_count = Column(Integer, default=0, nullable=False)
    is_stuck = Column(Boolean, default=False, index=True, nullable=False)

    last_failure_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('idx_agent_failure_lookup', 'tenant_id', 'agent_id'),
        UniqueConstraint('tenant_id', 'agent_id', name='uq_tenant_agent_failure_tracking'),
    )

    # Relationships
    agent = relationship("AgentRegistry", backref="failure_tracking")

class ChatMessage(Base):
    """
    Persistence for chat messages (Phase 55).
    """
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, nullable=False, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False) # user, assistant, system
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Optional metadata
    agent_id = Column(String, nullable=True)
    metadata_json = Column(Text, nullable=True)

class AgentModelMetrics(Base):
    """
    Metrics for tracking Agent Performance (Phase 13).
    """
    __tablename__ = "agent_model_metrics"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    model_id = Column(String, nullable=False) # e.g. "model_agent-123"
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    
    confidence = Column(Float, default=0.5)
    accuracy = Column(Float, default=0.0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    total_experiences = Column(Integer, default=0)
    last_updated = Column(DateTime, default=func.now())

class TokenUsage(Base):
    """
    Track token and cost usage per agent (Phase 4).
    """
    __tablename__ = "token_usage"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=True, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=True)
    chain_id = Column(String, ForeignKey("delegation_chains.id"), nullable=True, index=True) # Phase 10
    
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    billed = Column(Boolean, default=False)
    cost_usd = Column(Float, default=0.0)
    memory_mb = Column(Float, default=0.0)  # Track memory usage for governance metrics
    model_name = Column(String, nullable=False)
    timestamp = Column(DateTime, default=func.now())

class UserIdentity(Base):
    __tablename__ = "user_identities"
    __table_args__ = (
        UniqueConstraint('provider', 'provider_user_id', name='uq_provider_user_id'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    provider = Column(String, nullable=False) # e.g. "slack", "discord"
    provider_user_id = Column(String, nullable=False) # e.g. "U123456"
    provider_username = Column(String, nullable=True) # e.g. "rushiparikh"
    
    metadata_json = Column(JSONColumn, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="identities")

class BusinessProductService(Base):
    """Catalog of products or services provided by a business"""
    __tablename__ = "business_product_services"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    external_id = Column(String, nullable=True, index=True) # ID from legacy system
    name = Column(String, nullable=False)
    type = Column(String, default="service") # product, service
    description = Column(Text, nullable=True)
    base_price = Column(Float, default=0.0)
    unit_cost = Column(Float, default=0.0) # COGS for tangible products
    currency = Column(String, default="USD")
    stock_quantity = Column(Integer, default=0) # For tangible products
    
    metadata_json = Column(JSONColumn, nullable=True)
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
    
    metadata_json = Column(JSONColumn, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class HITLAction(Base):
    """Actions paused for manual review (Phase 70)"""
    __tablename__ = "hitl_actions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    agent_id = Column(String, nullable=True) # ID of the agent that initiated the action
    action_type = Column(String, nullable=False) # e.g., "send_message"
    platform = Column(String, nullable=False) # e.g., "whatsapp", "meta"
    params = Column(JSONColumn, nullable=False) # Serialized action parameters

    # NEW Phase 10: Delegation chain association
    chain_id = Column(String, ForeignKey("delegation_chains.id"), nullable=True, index=True)
    context_snapshot = Column(JSONColumn, nullable=True) # Snapshot of blackboard at time of HITL Request
    
    status = Column(String, default=HITLActionStatus.PENDING.value)
    reason = Column(String, nullable=True) # e.g., "Learning Phase: External Contact"
    
    # Priority & Routing
    priority = Column(String, default="MEDIUM") # LOW, MEDIUM, HIGH, URGENT
    notified_channel_id = Column(String, nullable=True) # Slack/Discord channel ID where notification was sent

    # Ownership
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    
    confidence_score = Column(Float, default=0.0)
    user_feedback = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(String, ForeignKey("users.id"), nullable=True)
    
    # New requirements Phase 110
    required_role = Column(String, nullable=True)
    required_confidence = Column(Float, default=0.7)
    meta_guidance = Column(Text, nullable=True) # Guidance from Meta Agent for Students

    # Relationships
    workspace = relationship("Workspace", backref="hitl_actions")
    reviewer = relationship("User", foreign_keys=[reviewed_by], backref="reviewed_hitl_actions")

class ActionProposal(Base):
    """Represents an agent action proposal awaiting user approval (Canvas Workflow)"""
    __tablename__ = "action_proposals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    canvas_id = Column(String, nullable=False, index=True)
    tenant_id = Column(String, nullable=True, index=True)  # Multi-tenant isolation
    session_id = Column(String, nullable=True)

    action_type = Column(String, nullable=False)
    action_data = Column(JSONColumn, nullable=False)
    description = Column(String, nullable=True)
    reason = Column(String, nullable=True)
    reversible = Column(Boolean, default=True)

    status = Column(String, default="pending")
    modified_data = Column(JSONColumn, nullable=True)
    rejection_reason = Column(String, nullable=True)
    user_guidance = Column(String, nullable=True)
    meta_guidance = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    responded_at = Column(DateTime, nullable=True)

class AgentStatus(str, enum.Enum):
    STUDENT = "student"       # Initial phase, high supervision
    INTERN = "intern"         # Learning, needs approval
    SUPERVISED = "supervised" # Operational but monitored
    AUTONOMOUS = "autonomous" # Fully trusted
    PAUSED = "paused"
    STOPPED = "stopped"
    DEPRECATED = "deprecated"
    DELETED = "deleted"

class AgentTriggerMode(str, enum.Enum):
    """How an agent can be triggered"""
    MANUAL = "manual"           # User-initiated via API/Chat
    DATA_EVENT = "data_event"   # Triggered by new data (webhook, ingestion, etc.)
    SCHEDULED = "scheduled"     # Triggered by cron/scheduler
    WORKFLOW = "workflow"       # Triggered as part of a workflow step

class FeedbackStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

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

class BudgetEnforcementMode(str, enum.Enum):
    """Budget enforcement mode when budget limit is exceeded"""
    ALERT_ONLY = "alert_only"  # Continue all operations, notifications only
    SOFT_STOP = "soft_stop"    # Prevent new episodes, allow active to complete
    HARD_STOP = "hard_stop"    # Halt all operations immediately
    APPROVAL = "approval"      # Require admin approval to continue

class AgentRegistry(Base):
    """Registry for AI Agents and their governance state"""
    __tablename__ = "agent_registry"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    display_name = Column(String, nullable=True) # Personalized name (e.g., Alex, Grace)
    handle = Column(String, nullable=True, index=True) # Unique handle for @mentions (e.g., alex)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=False) # e.g., "Operations", "Finance"
    
    # Legacy/Compatibility fields (SaaS Parity)
    role = Column(String, nullable=False, default='agent')
    type = Column(String, nullable=False, default='personal')
    capabilities = Column(JSONColumn, nullable=False, default=list)
    module_class = Column(String, nullable=True)  # Maps to class_name for compatibility

    # Technical Config
    module_path = Column(String, nullable=False) # e.g., "operations.automations.inventory"
    class_name = Column(String, nullable=False)
    
    # Ownership
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Governance
    status = Column(String, default=AgentStatus.STUDENT.value)
    confidence_score = Column(Float, default=0.5) # 0.0 to 1.0
    required_role_for_autonomy = Column(String, default=UserRole.TEAM_LEAD.value)
    self_healed_count = Column(Integer, default=0)  # Track self-healing recovery
    is_system_agent = Column(Boolean, default=False)  # System agents can use workspace tokens
    enabled = Column(Boolean, default=True)  # Whether agent is available for supervision tasks
    diversity_profile = Column(JSONColumn, default={})  # Strategy traits (e.g., risk_profile, focus)

    @property
    def maturity_level(self):
        return self.status

    @maturity_level.setter
    def maturity_level(self, value):
        self.status = value

    version = Column(String, default="1.0.0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Flexible Configuration
    configuration = Column(JSONColumn, default={}) # System prompts, tools, constraints
    schedule_config = Column(JSONColumn, default={}) # Cron expression, active status
    
    # Training Period Configuration (Phase: AI Training Periods)
    training_period_days = Column(Integer, nullable=True)  # Custom training duration
    training_started_at = Column(DateTime(timezone=True), nullable=True)  # When training began
    training_ends_at = Column(DateTime(timezone=True), nullable=True)  # When training completes
    training_config = Column(JSONColumn, default={})  # Milestones, AI estimates, custom settings

    # Graduation & Promotion Tracking (Phase: Episodic Memory & Graduation)
    last_promotion_at = Column(DateTime(timezone=True), nullable=True)  # Last promotion date
    promotion_count = Column(Integer, default=0)  # Number of promotions received
    last_exam_id = Column(String(255), ForeignKey("graduation_exams.id", ondelete="SET NULL"), nullable=True)  # Most recent exam
    exam_eligible_at = Column(DateTime(timezone=True), nullable=True)  # When agent can take next exam
    
    # Abuse Protection & Rate Limiting
    daily_requests_count = Column(Integer, default=0)
    last_request_date = Column(DateTime(timezone=True), nullable=True)

class BlockedTriggerContext(Base):
    """
    Record of automated triggers intercepted by maturity guard.
    """
    __tablename__ = "blocked_triggers"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)

    # Agent Information
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
    agent_name = Column(String, nullable=False)  # Denormalized for quick queries

    # Maturity State at Time of Block
    agent_maturity_at_block = Column(String, nullable=False, index=True)  # student, intern, supervised, autonomous
    confidence_score_at_block = Column(Float, nullable=False)

    # Trigger Source
    trigger_source = Column(String, nullable=False, index=True)  # MANUAL, DATA_SYNC, WORKFLOW_ENGINE, AI_COORDINATOR
    trigger_type = Column(String, nullable=False)  # agent_message, workflow_trigger, etc.
    trigger_context = Column(JSONColumn, nullable=False)  # Full trigger payload

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
    tenant = relationship("Tenant")
    agent = relationship("AgentRegistry", backref="blocked_triggers", foreign_keys=[agent_id])
    proposal = relationship("AgentProposal", foreign_keys=[proposal_id])

    # Indexes
    __table_args__ = (
        Index('ix_blocked_triggers_agent_tenant', 'agent_id', 'tenant_id'),
    )

class SupervisionSession(Base):
    """
    Real-time supervision sessions for SUPERVISED agents.
    """
    __tablename__ = "supervision_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)

    # Agent Information
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
    agent_name = Column(String, nullable=False)  # Denormalized

    # Trigger Context
    trigger_id = Column(String, ForeignKey("blocked_triggers.id"), nullable=True, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    trigger_context = Column(JSONColumn, nullable=False)  # Original trigger context

    # Session Status
    status = Column(String, default=SupervisionStatus.RUNNING.value, index=True)

    # Timing
    started_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Supervision
    supervisor_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    intervention_count = Column(Integer, default=0)

    # Interventions (JSON array of intervention records)
    interventions = Column(JSONColumn, default=list)
    agent_actions = Column(JSONColumn, default=list)

    # Outcomes
    supervisor_rating = Column(Integer, nullable=True)
    supervisor_feedback = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant")
    agent = relationship("AgentRegistry", backref="supervision_sessions", foreign_keys=[agent_id])
    trigger = relationship("BlockedTriggerContext", foreign_keys=[trigger_id])
    workspace = relationship("Workspace", backref="supervision_sessions")
    supervisor = relationship("User", foreign_keys=[supervisor_id])


class TrainingSession(Base):
    """
    Human-in-the-loop training sessions for STUDENT agents.

    Conducted when STUDENT agents are blocked from automated triggers.
    Provides guided learning experiences to build capabilities before autonomy.
    """
    __tablename__ = "training_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

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
    supervisor_guidance = Column(JSONColumn, nullable=True)  # Guidance provided during training

    # Training Progress
    tasks_completed = Column(Integer, default=0)  # Number of training tasks completed
    total_tasks = Column(Integer, nullable=True)  # Total tasks in training plan

    # Outcomes
    outcomes = Column(JSONColumn, nullable=True)  # Summary of what was accomplished
    performance_score = Column(Float, nullable=True)  # 0.0 to 1.0
    errors_count = Column(Integer, default=0)  # Number of errors during training
    supervisor_feedback = Column(Text, nullable=True)

    # Maturity Impact
    confidence_boost = Column(Float, nullable=True)  # Confidence increase from training
    promoted_to_intern = Column(Boolean, default=False)  # Whether training led to promotion

    # Capability Development
    capabilities_developed = Column(JSONColumn, nullable=True)  # List of capabilities gained
    capability_gaps_remaining = Column(JSONColumn, nullable=True)  # Gaps still remaining

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant")
    proposal = relationship("AgentProposal", backref=backref("training_session", uselist=False))
    agent = relationship("AgentRegistry", backref="training_sessions", foreign_keys=[agent_id])
    supervisor = relationship("User", foreign_keys=[supervisor_id])


class AgentFeedback(Base):
    """User feedback on agent actions for RLHF"""
    __tablename__ = "agent_feedback"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False)
    agent_execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # The Interaction
    input_context = Column(Text, nullable=True) # What triggered the agent
    original_output = Column(Text, nullable=False) # What the agent did/said
    user_correction = Column(Text, nullable=False) # What the user said it should be
    
    # Enhanced Feedback (NEW - from upstream)
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


class AgentLearning(Base):
    """
    Summary model for agent performance and adaptive parameters.
    Updated continuously by ContinuousLearningService.
    """
    __tablename__ = "agent_learning"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)

    # Aggregated Stats
    total_feedback = Column(Integer, default=0)
    positive_feedback = Column(Integer, default=0)
    negative_feedback = Column(Integer, default=0)
    avg_rating = Column(Float, nullable=True)

    # Learning Parameters
    learning_rate = Column(Float, default=0.01)
    parameters_json = Column(JSONColumn, nullable=True)

    last_updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    agent = relationship("AgentRegistry", backref=backref("learning_summary", uselist=False))
    tenant = relationship("Tenant", backref="agent_learning_records")

class AgentHandoff(Base):
    """
    Agent handoff records for multi-agent coordination.
    Tracks handoffs between agents working on the same canvas,
    including context, status, and results.
    """
    __tablename__ = "agent_handoffs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    from_agent_id = Column(String, ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    to_agent_id = Column(String, ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    canvas_id = Column(String, ForeignKey("canvases.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Handoff details
    context = Column(JSONColumn, nullable=True)  # Context passed between agents
    input_schema = Column(JSONColumn, nullable=True)  # Expected input schema
    output_schema = Column(JSONColumn, nullable=True) # Expected output schema
    reason = Column(Text, nullable=True)  # Why the handoff occurred
    status = Column(String(20), nullable=False)  # pending, accepted, rejected, completed
    rejection_reason = Column(Text, nullable=True)

    # Timestamps
    initiated_at = Column(DateTime(timezone=True), server_default=func.now())
    responded_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Result
    result = Column(JSONColumn, nullable=True)  # Final result from handoff

    # Relationships
    from_agent = relationship("AgentRegistry", foreign_keys=[from_agent_id], backref="initiated_handoffs")
    to_agent = relationship("AgentRegistry", foreign_keys=[to_agent_id], backref="received_handoffs")
    canvas = relationship("Canvas", back_populates="handoffs")
    tenant = relationship("Tenant", backref="agent_handoffs")


class DelegationChain(Base):
    """
    Tracks complete delegation chains for audit and debugging.

    A delegation chain represents a complete workflow where agents delegate
    tasks to other agents, forming a tree structure of parent-child relationships.

    Example:
    - Agent A delegates to Agent B (link 1)
    - Agent B delegates to Agent C (link 2)
    - Agent A also delegates to Agent D (link 3, parallel)

    This enables:
    - Complete audit trail of who delegated to whom
    - Debugging complex multi-agent workflows
    - Visualization of delegation flows
    - Performance analysis (timing, success rates)
    """
    __tablename__ = "delegation_chains"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Root delegation (where chain started)
    root_agent_id = Column(String, ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    root_task = Column(Text, nullable=True)
    root_execution_id = Column(String, nullable=True)

    # Chain lifecycle
    status = Column(String(50), nullable=False, default="active")  # active, completed, failed, cancelled
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Statistics
    total_links = Column(Integer, nullable=False, default=0)

    # NEW Phase 10: Aggregate tracking and guardrails
    total_spend_usd = Column(Float, nullable=False, default=0.0)
    max_depth = Column(Integer, nullable=False, default=5) # Limit recursion depth

    # Additional metadata
    metadata_json = Column(JSONColumn, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="delegation_chains")
    root_agent = relationship("AgentRegistry", foreign_keys=[root_agent_id], backref="initiated_chains")
    links = relationship("ChainLink", back_populates="chain", cascade="all, delete-orphan")
    healing_events = relationship("FleetHealingEvent", back_populates="chain", cascade="all, delete-orphan")


class ChainLink(Base):
    """
    Individual link in a delegation chain (parent -> child relationship).

    Each link represents one delegation from a parent agent to a child agent.
    Links form a tree structure representing the complete delegation flow.
    """
    __tablename__ = "chain_links"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    chain_id = Column(String, ForeignKey("delegation_chains.id", ondelete="CASCADE"), nullable=False, index=True)

    # Parent-child relationship
    parent_agent_id = Column(String, ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    child_agent_id = Column(String, ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)

    # Delegation details
    task_description = Column(Text, nullable=False)
    context_json = Column(JSONColumn, nullable=True)
    result_json = Column(JSONColumn, nullable=True)
    error_message = Column(Text, nullable=True)

    # Link lifecycle
    status = Column(String(50), nullable=False, default="pending")  # pending, in_progress, completed, failed
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Order within chain (for sequential flows)
    link_order = Column(Integer, nullable=False)

    # Additional metadata
    metadata_json = Column(JSONColumn, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    chain = relationship("DelegationChain", back_populates="links")
    parent_agent = relationship("AgentRegistry", foreign_keys=[parent_agent_id], backref="delegations_as_parent")
    child_agent = relationship("AgentRegistry", foreign_keys=[child_agent_id], backref="delegations_as_child")


class FleetPerformanceMetric(Base):
    """
    Tracks performance metrics for fleet execution.

    Records metrics like execution time, success rate, throughput
    for fleet scaling and optimization decisions.
    """
    __tablename__ = "fleet_performance_metrics"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    chain_id = Column(String, ForeignKey("delegation_chains.id", ondelete="CASCADE"), nullable=False, index=True)

    # Metric details
    metric_type = Column(String(50), nullable=False, index=True)  # execution_time, success_rate, throughput
    metric_value = Column(Float, nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False, index=True)
    window_end = Column(DateTime(timezone=True), nullable=False)

    # Additional context
    agent_count = Column(Integer, nullable=True)
    metadata_json = Column(JSONColumn, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    chain = relationship("DelegationChain", backref="performance_metrics")


class FleetOverage(Base):
    """
    Tracks temporary fleet expansion overages.

    Allows fleets to temporarily exceed base plan limits
    during scaling proposals or special circumstances.
    """
    __tablename__ = "fleet_overages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    chain_id = Column(String, ForeignKey("delegation_chains.id", ondelete="CASCADE"), nullable=False, index=True)

    # Overage details
    base_limit = Column(Integer, nullable=False)
    temporary_limit = Column(Integer, nullable=False)
    current_size = Column(Integer, nullable=False)

    # Expiry tracking
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    is_active = Column(Boolean, default=True, index=True)

    # Metadata
    reason = Column(Text, nullable=True)
    approved_by = Column(String, ForeignKey("users.id"), nullable=True)
    metadata_json = Column(JSONColumn, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    chain = relationship("DelegationChain", backref="overages")
    approver = relationship("User", backref="approved_overages")


class ScalingAutoApproval(Base):
    """
    Stores auto-approval rules for scaling operations.

    Defines thresholds and conditions under which scaling
    proposals can be automatically approved without human review.
    """
    __tablename__ = "scaling_auto_approvals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Rule configuration
    max_agents = Column(Integer, nullable=False)  # Maximum agents for auto-approval
    max_cost_increase_percent = Column(Float, nullable=False)  # Maximum cost increase percentage
    risk_threshold = Column(Float, default=0.3)  # Maximum risk score for auto-approval

    # Status
    is_active = Column(Boolean, default=True, index=True)

    # Metadata
    description = Column(Text, nullable=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    creator = relationship("User", backref="auto_approval_rules")


class ScalingProposal(Base):
    """
    Tracks scaling proposals for fleet expansion/contraction.

    Records proposals to change fleet size, their approval status,
    and execution history.
    """
    __tablename__ = "scaling_proposals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    chain_id = Column(String, ForeignKey("delegation_chains.id", ondelete="CASCADE"), nullable=True, index=True)

    # Proposal details
    proposal_type = Column(String(50), nullable=False)  # expansion, contraction
    current_agents = Column(Integer, nullable=False)
    proposed_agents = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    risk_score = Column(Float, default=0.5)

    # Approval tracking
    status = Column(String(50), default="pending", index=True)  # pending, approved, rejected, expired, executed
    approved_by = Column(String, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Execution tracking
    executed_at = Column(DateTime(timezone=True), nullable=True)
    execution_result = Column(JSONColumn, nullable=True)

    # Expiry
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    metadata_json = Column(JSONColumn, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    chain = relationship("DelegationChain", backref="scaling_proposals")
    approver = relationship("User", backref="approved_scaling_proposals")


class FleetHealingEvent(Base):
    """
    Tracks automated self-healing operations for fleet resilience.
    
    Records every time the SelfHealService triggers a recovery action
    (e.g., retry with quality override) due to a link failure or 
    performance bottleneck.
    """
    __tablename__ = "fleet_healing_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    chain_id = Column(String, ForeignKey("delegation_chains.id", ondelete="CASCADE"), nullable=False, index=True)
    link_id = Column(String, ForeignKey("chain_links.id", ondelete="CASCADE"), nullable=False, index=True)

    # Healing trigger details
    trigger_type = Column(String(50), nullable=False)  # "failed_link", "critical_bottleneck"
    trigger_reason = Column(Text, nullable=True)  # Error message or bottleneck description

    # Recovery action taken
    recovery_action = Column(String(50), nullable=False)  # "retry_with_quality", "consensus_committee"
    
    # Status of the healing operation
    status = Column(String(50), nullable=False, default="in_progress")  # in_progress, succeeded, failed
    
    # Outcome tracking (links created by this healing event)
    retry_link_id = Column(String, ForeignKey("chain_links.id", ondelete="SET NULL"), nullable=True)

    # Metadata for the healing operation (models used, overrides)
    metadata_json = Column(JSONColumn, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="fleet_healing_events")
    chain = relationship("DelegationChain", back_populates="healing_events")
    link = relationship("ChainLink", foreign_keys=[link_id], backref="healing_triggers")
    retry_link = relationship("ChainLink", foreign_keys=[retry_link_id], backref="healing_source")

    def __repr__(self):
        return f"<FleetHealingEvent(id={self.id}, trigger={self.trigger_type}, status={self.status})>"


class AgentCanvasPresence(Base):
    """
    Agent presence on canvases.
    Tracks which agents are currently active on which canvases,
    including their role and current action.
    """
    __tablename__ = "agent_canvas_presence"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    canvas_id = Column(String, ForeignKey("canvases.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Presence details
    role = Column(String(50), nullable=True)  # collaborator, reviewer, approver
    status = Column(String(20), default="active")  # active, idle, left
    current_action = Column(Text, nullable=True)  # What the agent is currently doing

    # Timestamps
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    left_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    agent = relationship("AgentRegistry", backref="canvas_presence")
    canvas = relationship("Canvas", back_populates="agent_presence")
    tenant = relationship("Tenant")

    def __repr__(self):
        return f"<AgentCanvasPresence(id={self.id}, agent_id={self.agent_id}, canvas_id={self.canvas_id})>"


class CoordinatedStrategy(Base):
    """A strategic plan formed by multiple specialty agents."""
    __tablename__ = "coordinated_strategies"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    objective = Column(Text, nullable=False)
    status = Column(String, default="draft")  # draft, negotiating, approved, executed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    approved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    contributions = relationship("StrategyContribution", back_populates="strategy", cascade="all, delete-orphan")
    tenant = relationship("Tenant", backref="coordinated_strategies")

class StrategyContribution(Base):
    """A specific contribution or critique from a specialty agent in a strategy."""
    __tablename__ = "strategy_contributions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    strategy_id = Column(String, ForeignKey("coordinated_strategies.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    specialty = Column(String, nullable=False)
    content = Column(JSONColumn, nullable=False)  # The actual strategic input
    status = Column(String, default="proposed")  # proposed, debated, final
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    strategy = relationship("CoordinatedStrategy", back_populates="contributions")
    agent = relationship("AgentRegistry")


class GovernanceDocStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"

class GovernanceImpactLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class GovernanceDocument(Base):
    """
    Database model for governance documents (policies, contracts, compliance).
    Tracks R2 metadata and manual fact entry status.
    """
    __tablename__ = "governance_documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Document Metadata
    title = Column(String(512), nullable=False)
    content = Column(Text, nullable=False)
    source_url = Column(String(1024), nullable=True) # e.g. R2 public URL
    source_type = Column(String(50), default="manual") # manual, file_upload, url
    
    # Governance Context
    impact_level = Column(String, default=GovernanceImpactLevel.MEDIUM.value)
    category = Column(String(100), default="general") # security, finance, hr
    
    # Approval Flow
    status = Column(String, default=GovernanceDocStatus.PENDING.value)
    entered_by = Column(String, ForeignKey("users.id"), nullable=False)
    approved_by = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Verification tracking (MODEL-02)
    last_verified = Column(DateTime(timezone=True), nullable=True)
    
    # Document lifecycle (MODEL-03)
    expiration_date = Column(DateTime(timezone=True), nullable=True)
    is_deleted = Column(Boolean, default=False, index=True)
    
    # Vector Embedding for RAG
    if PGVECTOR_AVAILABLE:
        embedding = Column(Vector(EMBEDDING_DIM), nullable=True)
    else:
        embedding = Column(JSONColumn, nullable=True)
        
    # Metadata for filtering
    metadata_json = Column(JSONColumn, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    approved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    author = relationship("User", foreign_keys=[entered_by], backref="entered_governance")
    approver = relationship("User", foreign_keys=[approved_by], backref="approved_governance")


class AgentFeedEvent(Base):
    """
    Agent social feed events for real-time status updates.
    Stores agent activity for timeline display and historical queries.
    """
    __tablename__ = "agent_feed_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    message = Column(Text, nullable=False)
    data = Column(JSONColumn, nullable=True)
    importance = Column(Integer, nullable=False, default=1, index=True)  # 0=low, 1=normal, 2=high
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.utcnow(), nullable=False, index=True)

    # Relationships
    tenant = relationship("Tenant")
    agent = relationship("AgentRegistry", backref="feed_events")

    def __repr__(self):
        return f"<AgentFeedEvent(agent_id={self.agent_id}, type={self.event_type}, importance={self.importance})>"


class SupervisorPerformance(Base):
    """
    Track supervisor performance for confidence adjustment.

    This model tracks how well supervisors (users or autonomous agents) perform
    in their supervision role, enabling the system to:
    - Adjust supervisor confidence based on supervision quality
    - Reward good supervision (approvals that lead to success)
    - Penalize bad supervision (approvals that fail, rejections that block success)
    - Learn which supervisors make the best decisions

    PHASE: Enhanced Rating & Confidence System
    """
    __tablename__ = "supervisor_performance"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    supervisor_id = Column(String(255), nullable=False, index=True)
    supervisor_type = Column(String(50), nullable=False, index=True)  # "user" or "autonomous_agent"
    tenant_id = Column(String(255), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)

    # Supervision statistics
    total_supervisions = Column(Integer, default=0, nullable=False)
    approvals_granted = Column(Integer, default=0, nullable=False)
    rejections_granted = Column(Integer, default=0, nullable=False)

    # Outcomes of approved proposals
    approved_successful = Column(Integer, default=0, nullable=False)  # Led to successful execution
    approved_failed = Column(Integer, default=0, nullable=False)      # Led to failed execution

    # Outcomes of rejected proposals (would have succeeded/failed)
    # This is estimated - we track when a rejected proposal is later executed
    correct_rejections = Column(Integer, default=0, nullable=False)     # Would have failed
    incorrect_rejections = Column(Integer, default=0, nullable=False)  # Would have succeeded

    # Performance metrics
    approval_success_rate = Column(Float, default=0.0)  # approved_successful / total_approvals
    supervision_quality_score = Column(Float, default=0.5)  # Overall quality (0.0 to 1.0)

    # Confidence tracking for the supervisor
    # If supervisor_type = "autonomous_agent", this maps to agent_registry.confidence_score
    # If supervisor_type = "user", this could be stored separately
    supervisor_confidence = Column(Float, default=0.5)  # Confidence in supervision ability

    # Timestamps
    first_supervision_at = Column(DateTime(timezone=True), nullable=True)
    last_supervision_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="supervisor_performances")


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
    triggers = Column(JSONColumn, default=list)
    actions = Column(JSONColumn, default=list)
    
    popular = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class UserConnection(Base):
    """Securely stores OAuth credentials and other auth data for users"""
    __tablename__ = "user_connections"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=True, index=True)
    
    # integration_id matches piece name, e.g., "@activepieces/piece-slack" or native "slack"
    integration_id = Column(String, nullable=False, index=True)
    connection_name = Column(String, nullable=False) # User-defined name
    
    # Encrypted credentials JSON
    credentials = Column(JSONColumn, nullable=False)
    
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
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
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
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    
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

class KnowledgeDocument(Base):
    """General-purpose document for RAG/knowledge base - persisted to DB"""
    __tablename__ = "knowledge_documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=False, default="")
    doc_type = Column(String(50), default="text")  # text, pdf, url
    metadata_json = Column(JSONColumn, default=dict)
    chunk_count = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class IngestionSettings(Base):
    """Settings for document ingestion per integration"""
    __tablename__ = "ingestion_settings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    integration_id = Column(String, nullable=False, index=True)
    
    enabled = Column(Boolean, default=False)
    auto_sync_new_files = Column(Boolean, default=True)
    file_types = Column(JSONColumn, default=list) # ["pdf", "docx"]
    sync_folders = Column(JSONColumn, default=list)
    exclude_folders = Column(JSONColumn, default=list)
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
    value = Column(JSONColumn, nullable=False) 
    
    unit = Column(String, default="count") # "usd", "percent", "count"
    timeframe = Column(String, default="current") # "30d", "current"
    
    last_synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# ==================== GRAPHRAG V2 (PostgreSQL) ====================

class GraphNode(Base):
    """
    Represents an entity in the Knowledge Graph (Person, Project, Document).
    Replaces in-memory NetworkX nodes.
    """
    __tablename__ = "graph_nodes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    workspace_id = Column(String, nullable=False, index=True) # Partition key
    name = Column(String, nullable=False)
    type = Column(String, nullable=False) # e.g., 'person', 'task', 'document'
    description = Column(Text, nullable=True)
    properties = Column(JSONColumn, default={}) # Flexible metadata
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('ix_graph_nodes_properties_gin', 'properties', postgresql_using='gin'),
    )

    # Constraints: (workspace_id, name, type) should be unique to prevent dupes
    # We'll enforce this via unique index in migration or explicit UNIQUE constraint

class GraphEdge(Base):
    """
    Represents a relationship between two entities.
    Replaces in-memory NetworkX edges.
    """
    __tablename__ = "graph_edges"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    workspace_id = Column(String, nullable=False, index=True)
    
    source_node_id = Column(String, ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_node_id = Column(String, ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    
    relationship_type = Column(String, nullable=False) # e.g., 'manages', 'blocks'
    weight = Column(Float, default=1.0)
    properties = Column(JSONColumn, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('ix_graph_edges_properties_gin', 'properties', postgresql_using='gin'),
    )

    # Relationships
    source_node = relationship("GraphNode", foreign_keys=[source_node_id])
    target_node = relationship("GraphNode", foreign_keys=[target_node_id])

class GraphCommunity(Base):
    """
    Hierarchical clusters detected by Leiden algorithm.
    Used for Global Search (Map-Reduce).
    """
    __tablename__ = "graph_communities"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    workspace_id = Column(String, nullable=False, index=True)
    
    level = Column(Integer, default=0) # Hierarchy level
    summary = Column(Text, nullable=False) # LLM-generated summary
    keywords = Column(JSONColumn, default=list) # Top keywords for indexing
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('ix_graph_communities_keywords_gin', 'keywords', postgresql_using='gin'),
    )

class CommunityMembership(Base):
    """Mapping of Nodes to Communities (Many-to-Many but usually One-to-Many per level)"""
    __tablename__ = "community_membership"

    community_id = Column(String, ForeignKey("graph_communities.id", ondelete="CASCADE"), primary_key=True)
    node_id = Column(String, ForeignKey("graph_nodes.id", ondelete="CASCADE"), primary_key=True)


# Models supporting Admin Dashboard & Governance
class SystemSettings(Base):
    __tablename__ = "system_settings"
    id = Column(String, primary_key=True, default="global")
    allow_public_signups = Column(Boolean, default=True)
    maintenance_mode = Column(Boolean, default=False)
    require_admin_mfa = Column(Boolean, default=False)
    global_budget_limit = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Intervention(Base):
    __tablename__ = "interventions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    action_type = Column(String, nullable=False)
    platform = Column(String, nullable=True)
    reason = Column(Text, nullable=True)
    params = Column(JSONColumn, default={})
    status = Column(String, default="pending")
    agent_id = Column(String, nullable=True)
    workspace_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class WorkflowRun(Base):
    """Execution log for legacy workflows, used for usage analytics in admin dashboard."""
    __tablename__ = "workflow_runs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String, nullable=False)
    tenant_id = Column(String, nullable=True)
    status = Column(String, default="completed")
    duration_seconds = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), server_default=func.now())

class WorkflowTemplate(Base):
    """Reusable workflow templates for the workflow UI."""
    __tablename__ = "workflow_templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    author_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Template metadata
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, index=True)
    icon = Column(String(50), nullable=False)

    # Template definition (stored as JSON)
    steps = Column(JSONColumn, nullable=False, default=list)
    input_schema = Column(JSONColumn, nullable=True)

    # Template settings
    is_public = Column(Boolean, default=False, index=True)
    is_approved = Column(Boolean, default=False, index=True)
    version = Column(String(20), default="1.0.0")

    # Usage tracking
    usage_count = Column(Integer, default=0)
    rating = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="workflow_templates")
    author = relationship("User", backref="created_templates")

class DesktopSession(Base):
    __tablename__ = "desktop_sessions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"))
    
    device_id = Column(String, nullable=True, index=True)
    hostname = Column(String(255), nullable=True)
    platform = Column(String(50), nullable=True)
    version = Column(String(20), nullable=True)
    capabilities = Column(JSONColumn, nullable=True)  # List of supported tools/features
    
    status = Column(String, default="active")  # active, inactive, disconnected
    last_active = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="desktop_sessions")
    user = relationship("User", backref="desktop_sessions")

class TicketStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"

class TicketPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class SupportTicket(Base):
    __tablename__ = "support_tickets"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    subject = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default=TicketStatus.OPEN.value)
    priority = Column(String, default=TicketPriority.MEDIUM.value)
    
    metadata_json = Column(JSONColumn, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="tickets")
    messages = relationship("TicketMessage", back_populates="ticket", cascade="all, delete-orphan")

class TicketMessage(Base):
    """Messages within a support ticket"""
    __tablename__ = "ticket_messages"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id = Column(String, ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=False)
    
    metadata_json = Column(JSONColumn, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    ticket = relationship("SupportTicket", back_populates="messages")
    user = relationship("User")

class UnifiedCommunication(Base):
    """Unified representation of messages across communication channels and help desks"""
    __tablename__ = "unified_communications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    ticket_id = Column(String, nullable=False)  # References ticket
    sender_id = Column(String, nullable=False)
    sender_type = Column(String(50))  # 'customer', 'agent', 'system'
    subject = Column(String(255))
    body = Column(Text, nullable=False)
    internal = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata_json = Column(JSONColumn)  # Additional data like attachments, headers, etc.

    tenant = relationship("Tenant")

class DesktopCommand(Base):
    """Commands sent to a desktop session (Satellite) for execution"""
    __tablename__ = "desktop_commands"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("desktop_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    command = Column(String(255), nullable=False)
    payload = Column(JSONColumn, nullable=True)
    
    status = Column(String(50), default="pending")  # pending, sent, completed, failed
    result = Column(JSONColumn, nullable=True)
    error = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    session = relationship("DesktopSession", backref="commands")


class UnifiedCalendarEvent(Base):
    """Unified representation of calendar events across providers"""
    __tablename__ = "unified_calendar_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    external_event_id = Column(String, nullable=False)  # Original event ID
    source = Column(String(50), nullable=False)  # 'google', 'outlook', 'apple', etc.
    title = Column(String(255), nullable=False)
    description = Column(Text)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    location = Column(String(255))
    attendees = Column(JSONColumn)  # List of attendees with emails, names, RSVP status
    status = Column(String(50))  # 'confirmed', 'tentative', 'cancelled'
    recurrence_rule = Column(String(255))  # iCal RRULE if recurring
    conference_url = Column(String(500))  # Meeting link
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    meta_data = Column(JSONColumn)  # Provider-specific data

    tenant = relationship("Tenant")

    def as_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "start": self.start_time,
            "end": self.end_time,
            "location": self.location,
            "status": self.status,
            "platform": self.source,
            "metadata": self.meta_data or {}
        }

class SSOConfiguration(Base):
    """Single Sign-On configuration for enterprise tenants"""
    __tablename__ = "sso_configurations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)  # 'saml', 'oidc', 'azure-ad', 'okta', etc.
    config = Column(JSONColumn, nullable=False)  # Provider-specific config (endpoints, certs, etc.)
    enabled = Column(Boolean, default=True)
    domain_mapping = Column(String(255))  # Optional: domain for auto-provisioning
    role_mapping = Column(JSONColumn)  # Map SSO roles to platform roles
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_sync_at = Column(DateTime)

    tenant = relationship("Tenant")

class SCIMConfiguration(Base):
    """SCIM 2.0 configuration for user provisioning"""
    __tablename__ = "scim_configurations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    scim_endpoint = Column(String(255), nullable=False)  # SCIM base URL
    bearer_token = Column(String(255), nullable=False)  # SCIM bearer token (should be hashed in production!)
    sync_enabled = Column(Boolean, default=False)
    sync_users = Column(Boolean, default=True)
    sync_groups = Column(Boolean, default=True)
    last_sync_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    meta_data = Column(JSONColumn)  # Provider-specific configuration

    tenant = relationship("Tenant")

class CommunicationComment(Base):
    """Comments on communications (emails, messages, etc.)"""
    __tablename__ = "communication_comments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    communication_id = Column(String, nullable=False)  # References external communication
    parent_comment_id = Column(String, ForeignKey("communication_comments.id"))  # For threaded comments
    author_id = Column(String, nullable=False)  # External user ID
    author_name = Column(String(255))
    author_email = Column(String(255))
    content = Column(Text, nullable=False)
    internal = Column(Boolean, default=False)  # Internal-only comment
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    mentions = Column(JSONColumn)  # List of mentioned user IDs
    attachments = Column(JSONColumn)  # Comment attachments

    tenant = relationship("Tenant")
    parent = relationship("CommunicationComment", remote_side=[id], foreign_keys=[parent_comment_id], backref="replies")

class Skill(Base):
    """
    Skill definition for agent capabilities.
    Types:
    - api: HTTP REST API calls
    - function: Native Python function calls (coming soon)
    - script: Local script execution (sandboxed)
    - docker: Local Docker execution (desktop only)
    - container: Cloud container execution (Fly.io Machines)

    Note: extend_existing=True handles duplicate class at line 7305.
    """
    __tablename__ = "skills"
    __table_args__ = {'extend_existing': True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)  # NULL for public marketplace skills
    author_tenant_id = Column(String, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True)  # Original creator

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    long_description = Column(Text, nullable=True)  # Detailed markdown description
    version = Column(String, default="1.0.0")
    type = Column(String, nullable=False)  # api, function, script, docker, container

    # API / Function Schema
    input_schema = Column(JSONColumn, nullable=False, default=dict)
    output_schema = Column(JSONColumn, nullable=True)

    # config: { url, method, headers } or { script } or { image, command }
    config = Column(JSONColumn, nullable=False, default=dict)

    # Marketplace metadata
    is_public = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=False)  # For public marketplace skills
    is_featured = Column(Boolean, default=False)  # Featured in marketplace

    # Categories & tags
    category = Column(String(50), nullable=True)  # productivity, finance, communication, etc.
    tags = Column(JSONColumn, nullable=True)  # List of tags for better discoverability

    # Pricing
    price = Column(Float, default=0.0)  # Price in USD (0 = free)
    currency = Column(String(3), default="USD")
    revenue_share = Column(Float, default=0.7)  # Author revenue share (70%)

    # Usage stats
    installs = Column(Integer, default=0)  # Number of installations
    executions = Column(Integer, default=0)  # Total executions
    success_rate = Column(Float, default=1.0)  # Execution success rate
    avg_execution_time_ms = Column(Float, nullable=True)  # Average execution time

    # Rating & feedback
    rating = Column(Float, default=0.0)  # Average rating (1-5)
    rating_count = Column(Integer, default=0)

    # Licensing
    license = Column(String(50), default="MIT")  # Skill license
    repository_url = Column(String(500), nullable=True)  # Source code repository
    documentation_url = Column(String(500), nullable=True)  # External docs

    # Approval workflow
    submitted_for_approval = Column(Boolean, default=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(String, ForeignKey("users.id"), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Dependencies
    dependencies = Column(JSONColumn, nullable=True)  # List of skill IDs this depends on
    environment_vars = Column(JSONColumn, nullable=True)  # Required environment variables

    # Code/storage
    code = Column(Text, nullable=True)  # Inline code for function/script types
    file_path = Column(String(500), nullable=True)  # For skills stored in S3

    # OpenClaw-specific fields
    openclaw_source_url = Column(String(500), nullable=True)  # GitHub URL to SKILL.md
    openclaw_skill_md = Column(Text, nullable=True)  # Original SKILL.md content
    openclaw_author = Column(String(255), nullable=True)  # Original author from SKILL.md
    openclaw_metadata = Column(JSONColumn, nullable=True)  # Full parsed YAML frontmatter
    openclaw_dependencies = Column(JSONColumn, nullable=True)  # Parsed dependencies from parser

    # Security scanning fields (for Phase 43)
    safety_level = Column(String(20), default="UNKNOWN")  # SAFE, LOW_RISK, MEDIUM_RISK, HIGH_RISK, BLOCKED
    scan_status = Column(String(20), default="PENDING")  # PENDING, SCANNED, APPROVED

    # Package dependencies (for Phase 60)
    python_packages = Column(JSONColumn, nullable=True)  # Python package specs: [{"name": "pandas", "version": ">=2.0.0", "index": "pypi"}]
    npm_packages = Column(JSONColumn, nullable=True)  # npm package specs: [{"name": "axios", "version": "^1.6.0", "registry": "npm"}]
    packages_installed = Column(JSONColumn, nullable=True)  # Tracking installed packages: {"python": ["pandas"], "npm": ["axios"], "installed_at": "2026-02-19T..."}
    installation_error = Column(Text, nullable=True)  # Installation failure diagnostics

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="skills", foreign_keys=[tenant_id])
    author_tenant = relationship("Tenant", backref="published_skills", foreign_keys=[author_tenant_id])
    approver = relationship("User", foreign_keys=[approved_by])


class SkillVersion(Base):
    __table_args__ = {'extend_existing': True}  # Duplicate class
    """
    Version history for skills.
    Enables rollback and version comparison.
    """
    __tablename__ = "skill_versions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    skill_id = Column(String, ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    version = Column(String, nullable=False)  # Semver version
    changelog = Column(Text, nullable=True)  # Version notes

    # Snapshot of skill at this version
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    type = Column(String, nullable=False)
    input_schema = Column(JSONColumn, nullable=False, default=dict)
    output_schema = Column(JSONColumn, nullable=True)
    config = Column(JSONColumn, nullable=False, default=dict)
    code = Column(Text, nullable=True)
    dependencies = Column(JSONColumn, nullable=True)

    # Release info
    is_stable = Column(Boolean, default=False)  # Marked as stable release
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    skill = relationship("Skill", backref="versions")
    tenant = relationship("Tenant", backref="skill_versions")


class SkillInstallation(Base):
    __table_args__ = {'extend_existing': True}  # Duplicate class
    """
    Track skill installations from marketplace.
    Links installed skill to original creator for revenue sharing.
    """
    __tablename__ = "skill_installations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id = Column(String, ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True)
    source_skill_id = Column(String, ForeignKey("skills.id", ondelete="SET NULL"), nullable=True)  # Original marketplace skill

    # Installation details
    installed_version = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)  # Can be disabled without uninstalling
    config_overrides = Column(JSONColumn, nullable=True)  # Tenant-specific config overrides

    # Usage tracking
    executions = Column(Integer, default=0)
    last_executed_at = Column(DateTime(timezone=True), nullable=True)

    # Feedback
    rating = Column(Integer, nullable=True)  # User's rating of this skill
    feedback = Column(Text, nullable=True)  # User feedback text

    installed_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="installed_skills")
    skill = relationship("Skill", backref="installations", foreign_keys=[skill_id])
    source_skill = relationship("Skill", backref="marketplace_installations", foreign_keys=[source_skill_id])


class SkillRating(Base):
    """
    User ratings and reviews for marketplace skills.
    """
    __tablename__ = "skill_ratings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id = Column(String, ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Rating
    rating = Column(Integer, nullable=False)  # 1-5 stars
    review = Column(Text, nullable=True)  # Optional review text

    # Moderation
    is_flagged = Column(Boolean, default=False)
    is_visible = Column(Boolean, default=True)

    # Helpful votes
    helpful_count = Column(Integer, default=0)
    not_helpful_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="skill_ratings")
    skill = relationship("Skill", backref="ratings")
    user = relationship("User", backref="skill_ratings")

    __table_args__ = (
        UniqueConstraint('skill_id', 'user_id', name='uq_skill_user_rating'),
    )


class AgentSkill(Base):
    __table_args__ = {'extend_existing': True}  # Duplicate class
    """Many-to-Many relationship between agents and skills"""
    __tablename__ = "agent_skills"

    agent_id = Column(String, ForeignKey("agent_registry.id", ondelete="CASCADE"), primary_key=True)
    skill_id = Column(String, ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)
    enabled = Column(Boolean, default=True)
    config_overrides = Column(JSONColumn, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    agent = relationship("AgentRegistry", backref="assigned_skills")
    skill = relationship("Skill", backref="assigned_agents")


class SkillExecution(Base):
    """
    Execution record for skill runs with ACU billing tracking.

    Container skills (cloud execution) track compute usage in ACUs.
    Docker skills (local only) do NOT incur ACU charges.

    Billing follows the same pattern as AgentExecution:
    - execution_seconds: Total compute time in seconds
    - compute_billed: Idempotent flag to prevent double-charging
    - tenant_id: Links execution to tenant for billing aggregation
    """
    __tablename__ = "skill_executions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id = Column(String, ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True)

    status = Column(String, default="pending")  # pending, running, completed, failed
    input_params = Column(JSONColumn, nullable=True)
    output_result = Column(JSONColumn, nullable=True)
    error_message = Column(Text, nullable=True)

    # ACU Billing (1 ACU = 1 second of compute)
    execution_seconds = Column(Float, default=0.0)
    cpu_count = Column(Integer, nullable=True)
    memory_mb = Column(Integer, nullable=True)
    compute_billed = Column(Boolean, default=False, nullable=False)

    # Infrastructure metadata (for debugging/audit)
    machine_id = Column(String, nullable=True)  # Cloud container ID

    # Sandbox tracking (Phase 44)
    container_id = Column(String, nullable=True)  # Docker container or Fly.io Machine ID
    safety_level = Column(String, nullable=True)  # Scanner safety level at execution time
    stdout = Column(Text, nullable=True)  # Captured stdout from container
    stderr = Column(Text, nullable=True)  # Captured stderr from container
    exit_code = Column(Integer, nullable=True)  # Container exit code (0=success)

    # Community Skills tracking (Phase 14, Migration: 20260216_community_skills)
    skill_source = Column(String, default='cloud', nullable=True)  # 'cloud' or 'community'
    security_scan_result = Column(JSONColumn, nullable=True)  # LLM security scan results
    sandbox_enabled = Column(Boolean, default=False, nullable=True)  # Docker sandbox flag

    # Audit provenance tracking (Phase 45-02, SKILL-26)
    audit_metadata = Column(JSONColumn, nullable=True)  # ShellSession-style provenance tracking

    # Legacy timing (ms for non-compute skills like API calls)
    execution_time_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    agent = relationship("AgentRegistry", backref="skill_executions")
    tenant = relationship("Tenant", backref="skill_executions")
    skill = relationship("Skill", backref="execution_records")


class SkillComposition(Base):
    """
    Multi-skill workflow definition.

    Composes multiple skills into executable workflows with data passing
    between steps. Enables complex multi-step agent operations.
    """
    __tablename__ = "skill_compositions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    version = Column(String, default="1.0.0")

    # Workflow configuration
    input_schema = Column(JSONColumn, nullable=True)  # Expected workflow input
    output_schema = Column(JSONColumn, nullable=True)  # Workflow output structure

    # Execution tracking
    total_executions = Column(Integer, default=0)
    successful_executions = Column(Integer, default=0)
    failed_executions = Column(Integer, default=0)

    is_public = Column(Boolean, default=False)  # Share with marketplace

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="skill_compositions")
    author = relationship("User", backref="authored_compositions")
    steps = relationship("SkillCompositionStep", backref="composition", cascade="all, delete-orphan")


class SkillCompositionStep(Base):
    """
    Individual step in a skill composition workflow.

    Defines which skill to run and how to map inputs/outputs between steps.
    Supports conditional execution, error handling, and retry logic.
    """
    __tablename__ = "skill_composition_steps"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    composition_id = Column(String, ForeignKey("skill_compositions.id", ondelete="CASCADE"), nullable=False, index=True)

    step_order = Column(Integer, nullable=False)
    skill_id = Column(String, ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True)

    # Input/output mapping
    input_mapping = Column(JSONColumn, nullable=True)  # Map workflow state to skill input
    output_mapping = Column(JSONColumn, nullable=True)  # Map skill output to workflow state

    # Conditional execution
    condition = Column(JSONColumn, nullable=True)  # {"field": "status", "operator": "eq", "value": "success"}
    parallel = Column(Boolean, default=False)  # Execute in parallel with next step

    # Error handling
    continue_on_failure = Column(Boolean, default=False)
    retry_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    skill = relationship("Skill", backref="composition_steps")


class SkillCompositionExecution(Base):
    """
    Execution record for skill composition workflows.

    Tracks individual workflow runs with validation status, execution results,
    and rollback information for debugging and monitoring.
    """
    __tablename__ = "skill_composition_executions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String, nullable=False, index=True)
    agent_id = Column(String, nullable=False, index=True)
    workspace_id = Column(String, default="default")

    # Workflow definition and validation
    workflow_definition = Column(JSONColumn, nullable=False)  # List of steps as dicts
    validation_status = Column(String, default="pending")  # pending, valid, invalid

    # Execution status
    status = Column(String, default="pending")  # pending, running, completed, failed, rolled_back
    current_step = Column(String, nullable=True)
    completed_steps = Column(JSONColumn, nullable=False, default=list)  # List of step_ids

    # Execution results
    execution_results = Column(JSONColumn, nullable=True)  # Step results
    final_output = Column(JSONColumn, nullable=True)  # Final workflow output

    # Error handling
    error_message = Column(Text, nullable=True)

    # Rollback tracking
    rollback_performed = Column(Boolean, default=False)
    rollback_steps = Column(JSONColumn, nullable=True)  # List of step_ids in reverse order

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AgentMessage(Base):
    """
    Messages passed between agents for multi-agent coordination.

    Enables agents to communicate, collaborate, and coordinate on complex tasks.
    """
    __tablename__ = "agent_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Sender/Receiver
    from_agent_id = Column(String, ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    to_agent_id = Column(String, ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)

    # Message content
    message_type = Column(String(50), nullable=False)  # request, response, notification, status, error
    priority = Column(String(20), default="normal")  # low, normal, high, urgent
    subject = Column(String(255), nullable=True)  # Message subject
    content = Column(Text, nullable=False)  # Message body
    metadata_json = Column(JSONColumn, nullable=True)  # Additional context

    # Task context (for coordinated workflows)
    task_id = Column(String, nullable=True, index=True)  # Parent task/workflow ID
    parent_message_id = Column(String, ForeignKey("agent_messages.id", ondelete="SET NULL"), nullable=True)  # For threading
    conversation_id = Column(String, nullable=True, index=True)  # Group related messages

    # Delivery tracking
    status = Column(String(50), default="pending")  # pending, delivered, read, failed
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    # Response tracking
    correlation_id = Column(String, nullable=True, index=True)  # Link request/response
    requires_response = Column(Boolean, default=False)
    response_message_id = Column(String, nullable=True)  # ID of response message

    # TTL for temporary messages
    expires_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="agent_messages")
    from_agent = relationship("AgentRegistry", backref="sent_messages", foreign_keys=[from_agent_id])
    to_agent = relationship("AgentRegistry", backref="received_messages", foreign_keys=[to_agent_id])
    parent_message = relationship("AgentMessage", remote_side=[id], foreign_keys=[parent_message_id], backref="replies")


class SwarmTask(Base):
    """
    Tasks managed by the Swarm Orchestrator.

    Represents complex tasks that are decomposed and distributed across multiple agents.
    """
    __tablename__ = "swarm_tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Task definition
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    task_type = Column(String(50), nullable=False)  # parallel, sequential, dynamic
    priority = Column(String(20), default="normal")  # low, normal, high, urgent

    # Task decomposition
    parent_task_id = Column(String, ForeignKey("swarm_tasks.id"), nullable=True, index=True)  # For nested tasks
    root_task_id = Column(String, nullable=True, index=True)  # Top-level task

    # Status tracking
    status = Column(String(50), default="pending")  # pending, running, completed, failed, cancelled
    progress = Column(Float, default=0.0)  # 0-100
    result = Column(JSONColumn, nullable=True)  # Aggregated result from all agents

    # Agent assignments
    required_capabilities = Column(JSONColumn, nullable=True)  # Required agent capabilities
    assigned_agents = Column(JSONColumn, nullable=True)  # List of agent IDs

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    timeout_seconds = Column(Integer, default=300)  # Task timeout

    # Error handling
    error_message = Column(Text, nullable=True)
    failed_agent_id = Column(String, nullable=True)  # Which agent failed

    # Statistics
    total_subtasks = Column(Integer, default=0)
    completed_subtasks = Column(Integer, default=0)
    failed_subtasks = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="swarm_tasks")
    parent_task = relationship("SwarmTask", remote_side=[id], foreign_keys=[parent_task_id], backref="subtasks")


class DeepLinkAudit(Base):
    """
    Audit trail for deep link invocations.

    Records all deep link executions (agent, workflow, canvas, tool)
    with full governance tracking and attribution.
    """
    __tablename__ = "deep_link_audit"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)
    agent_execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=True, index=True)
    user_id = Column(String, nullable=False, index=True)

    # Deep link details
    resource_type = Column(String, nullable=False)  # 'agent', 'workflow', 'canvas', 'tool'
    resource_id = Column(String, nullable=False)
    action = Column(String, nullable=False)
    source = Column(String, default="external")  # external_app, browser, mobile, etc.

    # Full context
    deeplink_url = Column(Text, nullable=False)
    parameters = Column(JSONColumn, nullable=True)

    # Results
    status = Column(String, default="success")  # success, failed, error
    error_message = Column(Text, nullable=True)
    governance_check_passed = Column(Boolean, nullable=True)

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    agent = relationship("AgentRegistry")
    execution = relationship("AgentExecution")
    tenant = relationship("Tenant")

class PushToken(Base):
    """Push notification tokens for mobile devices"""
    __tablename__ = "push_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    token = Column(String, nullable=False, unique=True, index=True)
    platform = Column(String, nullable=False)  # 'ios' or 'android'
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="push_tokens")
    tenant = relationship("Tenant", back_populates="push_tokens")


class DesktopAction(Base):
    """Auditable actions performed by a desktop session (Satellite)"""
    __tablename__ = "desktop_actions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("desktop_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    action_type = Column(String(50), nullable=False)  # 'tool_execution', 'file_access', 'shell_command', etc.
    action_name = Column(String(255), nullable=False)
    metadata_json = Column(JSONColumn, nullable=True)  # Using JSON for flexibility
    
    success = Column(Boolean, default=True)
    duration_ms = Column(Integer, default=0)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    session = relationship("DesktopSession", backref="actions")
    tenant = relationship("Tenant", backref="desktop_actions")


# ========================================================================
# COLLABORATIVE CANVAS & MULTI-AGENT COORDINATION MODELS
# ========================================================================

class Canvas(Base):
    """
    Canvas for collaborative editing and presentations.

    Supports:
    - Real-time collaboration
    - Multi-user editing
    - Agent coordination
    - Component installations
    """
    __tablename__ = "canvases"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=False)

    # Canvas details
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    canvas_type = Column(String(50), default="document")  # document, spreadsheet, email, presentation, custom

    # Content storage
    content = Column(JSONColumn, nullable=True)  # Canvas content (structure, text, etc.)
    style = Column(JSONColumn, nullable=True)  # Custom CSS/styling

    # Collaboration settings
    is_collaborative = Column(Boolean, default=True)
    is_public = Column(Boolean, default=False)  # Shareable via public link
    share_token = Column(String(255), unique=True, nullable=True)  # For public sharing

    # Status
    status = Column(String(20), default="active")  # active, archived, deleted

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_edited_by = Column(String, ForeignKey("users.id"), nullable=True)
    last_edited_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant", backref="canvases")
    workspace = relationship("Workspace", backref="canvases")
    creator = relationship("User", foreign_keys=[created_by], backref="created_canvases")
    editor = relationship("User", foreign_keys=[last_edited_by])
    installations = relationship("ComponentInstallation", back_populates="canvas", cascade="all, delete-orphan")
    agent_presence = relationship("AgentCanvasPresence", back_populates="canvas", cascade="all, delete-orphan")
    handoffs = relationship("AgentHandoff", back_populates="canvas", cascade="all, delete-orphan")
    audit_records = relationship("CanvasAudit", back_populates="canvas", cascade="all, delete-orphan")


class CanvasAudit(Base):
    """
    Audit trail for canvas actions and interactions.

    Tracks all canvas-related events including:
    - Form submissions
    - Canvas closes
    - User interactions
    - Artifact modifications
    - Agent actions

    Used for episodic memory context retrieval during agent decision-making.
    """
    __tablename__ = 'canvas_audit'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    canvas_id = Column(String(255), ForeignKey("canvases.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(255), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(255), ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True, index=True)  # Link to chat session for episodic memory

    # Action details
    action_type = Column(String(100), nullable=False, index=True)  # "form_submit", "canvas_close", "artifact_modify", etc.
    user_id = Column(String(255), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    agent_id = Column(String(255), ForeignKey("agent_registry.id", ondelete="SET NULL"), nullable=True)

    # Episode linkage for episodic memory context retrieval
    episode_id = Column(String(255), ForeignKey("agent_episodes.id", ondelete="SET NULL"), nullable=True, index=True)

    # Action details (JSON for flexibility)
    details_json = Column(JSONColumn, nullable=True)  # Action-specific data

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    canvas = relationship("Canvas", back_populates="audit_records")
    session = relationship("ChatSession", foreign_keys=[session_id])

    __table_args__ = (
        Index('idx_canvas_audit_canvas_id', 'canvas_id'),
        Index('idx_canvas_audit_action_type', 'action_type'),
        Index('idx_canvas_audit_created_at', 'created_at'),
        Index('idx_canvas_audit_session_id', 'session_id'),
    )

    def __repr__(self):
        return f"<CanvasAudit(id={self.id}, canvas_id={self.canvas_id}, action_type={self.action_type})>"


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
    user_id = Column(String, nullable=False, index=True)
    browser_type = Column(String, server_default="chromium", nullable=True)
    headless = Column(Boolean, server_default="1", nullable=True)
    status = Column(String, server_default="active", nullable=True)
    current_url = Column(Text, nullable=True)
    page_title = Column(Text, nullable=True)
    metadata_json = Column(JSONColumn, nullable=True)
    governance_check_passed = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    agent = relationship("AgentRegistry", foreign_keys=[agent_id])
    agent_execution = relationship("AgentExecution", foreign_keys=[agent_execution_id])

class BrowserAudit(Base):
    """
    Browser Operations Audit Log

    Tracks all browser automation operations (navigate, click, fill form, screenshot, extract text, execute script)
    for governance and compliance. All browser actions by agents create audit entries.
    """
    __tablename__ = "browser_audit"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # Alias for timestamp

    # Agent context
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)
    agent_execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(String, nullable=True, index=True)  # Link to BrowserSession

    # Action details
    action = Column(String(100), nullable=False, index=True)  # navigate, click, fill_form, screenshot, etc.
    action_type = Column(String(100), nullable=True, index=True)  # Alias for action
    endpoint = Column(String(200), nullable=False)

    # Request/Response tracking
    request_params = Column(JSONColumn, nullable=True)  # Input parameters
    action_params = Column(JSONColumn, nullable=True)  # Alias for request_params
    response_summary = Column(JSONColumn, nullable=True)  # Output summary
    result_summary = Column(Text, nullable=True)  # Human-readable result
    result_data = Column(JSONColumn, nullable=True)  # Structured result data

    # Status and governance
    status_code = Column(Integer, nullable=True)  # HTTP-like status code
    success = Column(Boolean, default=True, index=True)
    error_message = Column(Text, nullable=True)

    # Governance metadata
    maturity_level = Column(String(50), nullable=True)  # INTERN, SUPERVISED, AUTONOMOUS
    governance_allowed = Column(Boolean, default=True)
    governance_reason = Column(Text, nullable=True)
    governance_check_passed = Column(Boolean, nullable=True)  # Whether governance check passed

    # Browser-specific metadata
    browser_type = Column(String(50), nullable=True)  # chromium, firefox, webkit
    headless = Column(Boolean, nullable=True)
    current_url = Column(Text, nullable=True)  # URL after action
    page_title = Column(Text, nullable=True)  # Page title after action
    duration_ms = Column(Integer, nullable=True)  # Operation duration in milliseconds

    # Metadata
    metadata_json = Column(JSONColumn, default={})

    # Relationships
    agent = relationship("AgentRegistry", foreign_keys=[agent_id])
    agent_execution = relationship("AgentExecution", foreign_keys=[agent_execution_id])
    user = relationship("User", foreign_keys=[user_id])

#
#     id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
#     workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
#     agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)
#     session_id = Column(String, nullable=True, index=True) # Logical link to chat session
#     
#     name = Column(String, nullable=False)
#     type = Column(String, nullable=False) # 'code', 'markdown', etc.
#     content = Column(Text, nullable=False)
#     metadata_json = Column(JSONColumn, default={})
#     
#     version = Column(Integer, default=1)
#     is_locked = Column(Boolean, default=False)
#     locked_by_user_id = Column(String, ForeignKey("users.id"), nullable=True)
#     author_id = Column(String, ForeignKey("users.id"), nullable=True)
#     
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
#
#     # Relationships
#     author = relationship("User", foreign_keys=[author_id])
#     locked_by = relationship("User", foreign_keys=[locked_by_user_id])
#     workspace = relationship("Workspace")

class ArtifactVersion(Base):
    """
    Immutable snapshots of artifact states for time-travel/versioning.
    """
    __tablename__ = "artifact_versions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    artifact_id = Column(String, ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    
    content = Column(Text, nullable=False)
    metadata_json = Column(JSONColumn, default={})
    
    author_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    artifact = relationship("Artifact", backref="versions")
    author = relationship("User")

class DeviceNode(Base):
    """
    Registry of compute nodes (Desktop, Mobile, Cloud) available for orchestration.
    Backported from Atom SaaS for standard device targeting.
    """
    __tablename__ = "device_nodes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)

    # Node Identity
    name = Column(String, nullable=False)
    device_id = Column(String, nullable=False, index=True) # Unique hardware/client ID
    node_type = Column(String, nullable=False) # desktop_windows, desktop_mac, mobile_ios, etc.

    # Connectivity
    status = Column(String, default="offline") # online, offline, busy
    last_seen = Column(DateTime(timezone=True), server_default=func.now())

    # Capabilities (JSON list of strings)
    capabilities = Column(JSONColumn, default=[]) # e.g. ["browser", "terminal", "file_system"]
    capabilities_detailed = Column(JSONColumn, nullable=True)  # Detailed capability info

    # Platform information
    platform = Column(String, nullable=True)  # darwin, windows, linux
    platform_version = Column(String, nullable=True)
    architecture = Column(String, nullable=True)  # x86_64, arm64, etc.

    # Version information
    tauri_version = Column(String, nullable=True)
    app_version = Column(String, nullable=True)
    version = Column(String, nullable=True)  # Legacy, keep for compatibility

    # Hardware information
    hardware_info = Column(JSONColumn, nullable=True)  # CPU, RAM, GPU, etc.

    # Metadata
    metadata_json = Column(JSONColumn, default={})

    # App type (desktop, mobile, menubar)
    app_type = Column(String, default="desktop")

    # Last command execution timestamp (for menu bar)
    last_command_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    workspace = relationship("Workspace", backref="device_nodes")
    user = relationship("User", backref="devices")


class DeviceAudit(Base):
    """
    Device Operations Audit Log
    Tracks all device operations (camera, screen recording, location, notifications) for governance and compliance.
    """
    __tablename__ = "device_audit"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # Alias for timestamp, used by device_tool.py

    # Agent context
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)
    agent_execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    device_node_id = Column(String, nullable=True, index=True)

    # Action details
    action = Column(String(100), nullable=False, index=True)  # camera_snap, screen_record, get_location, etc.
    action_type = Column(String(100), nullable=True, index=True)  # Alias for action, used by device_tool.py
    endpoint = Column(String(200), nullable=False)

    # Request/Response tracking
    request_params = Column(JSONColumn, nullable=True)  # Input parameters
    action_params = Column(JSONColumn, nullable=True)  # Alias for request_params, used by device_tool.py
    response_summary = Column(JSONColumn, nullable=True)  # Output summary
    result_summary = Column(Text, nullable=True)  # Alias for response_summary text
    result_data = Column(JSONColumn, nullable=True)  # Structured result data

    # Status and governance
    status_code = Column(Integer, nullable=True)  # HTTP-like status code
    success = Column(Boolean, default=True, index=True)
    error_message = Column(Text, nullable=True)

    # Governance metadata
    maturity_level = Column(String(50), nullable=True)  # INTERN, SUPERVISED, AUTONOMOUS
    governance_allowed = Column(Boolean, default=True)
    governance_reason = Column(Text, nullable=True)

    # Device-specific metadata
    session_id = Column(String, nullable=True, index=True)  # Link to DeviceSession
    device_type = Column(String(50), nullable=True)  # mobile, desktop, etc.
    file_path = Column(String(500), nullable=True)  # For camera/screen recording outputs
    duration_ms = Column(Integer, nullable=True)  # Operation duration in milliseconds
    governance_check_passed = Column(Boolean, nullable=True)  # Whether governance check passed

    # Metadata
    metadata_json = Column(JSONColumn, default={})


class DeviceSession(Base):
    """
    Device Operation Session
    Tracks active device operation sessions (screen recording, etc.) for lifecycle management.
    """
    __tablename__ = "device_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)

    # Session identifiers
    session_id = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    device_node_id = Column(String, nullable=False, index=True)

    # Agent context
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)
    agent_execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=True, index=True)

    # Governance tracking
    governance_check_passed = Column(Boolean, nullable=True)  # Whether governance check passed

    # Session details
    session_type = Column(String(50), nullable=False, index=True)  # screen_record, camera_stream, etc.
    status = Column(String(50), default="active", index=True)  # active, stopped, error

    # Configuration
    configuration = Column(JSONColumn, nullable=True)  # Session configuration (resolution, etc.)
    capabilities = Column(JSONColumn, nullable=True)  # Device capabilities for this session

    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    stopped_at = Column(DateTime(timezone=True), nullable=True)
    last_activity = Column(DateTime(timezone=True), server_default=func.now())

    # Output tracking
    output_files = Column(JSONColumn, default=[])  # List of generated file paths
    total_duration_seconds = Column(Integer, nullable=True)

    # Metadata
    metadata_json = Column(JSONColumn, default={})


class MenuBarAudit(Base):
    """
    Menu Bar Operations Audit Log
    Tracks all menu bar companion app operations for governance and compliance.
    """
    __tablename__ = "menu_bar_audit"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Agent context
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)
    agent_execution_id = Column(String, ForeignKey("agent_executions.id"), nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    device_id = Column(String, nullable=True, index=True) # Hardware/client ID

    # Action details
    action = Column(String(100), nullable=False, index=True)  # login, quick_chat, get_agents, etc.
    endpoint = Column(String(200), nullable=False)

    # Request/Response tracking
    request_params = Column(JSONColumn, nullable=True)  # Input parameters
    response_summary = Column(JSONColumn, nullable=True)  # Output summary

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
    agent = relationship("AgentRegistry")
    execution = relationship("AgentExecution")
    user = relationship("User")


class CanvasComponent(Base):
    __table_args__ = {'extend_existing': True}  # Duplicate class
    """
    Reusable components for canvas marketplace.

    Supports:
    - Public marketplace components
    - Tenant-specific components
    - Version tracking
    - Dependency management
    - Pricing and licensing
    """
    __tablename__ = "canvas_components"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)  # NULL = public marketplace
    author_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Component details
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False)  # 'chart', 'table', 'form', 'widget', 'media', 'layout', etc.
    tags = Column(JSONColumn, nullable=True)  # Tags for better discoverability

    # Component definition
    component_type = Column(String(50), nullable=False)  # 'html', 'react', 'vue', 'custom'
    code = Column(Text, nullable=False)  # HTML/CSS/JS or React component code
    config_schema = Column(JSONColumn, nullable=True)  # JSON schema for component props
    preview_url = Column(String(500), nullable=True)  # Screenshot or preview URL
    thumbnail_url = Column(String(500), nullable=True)
    demo_url = Column(String(500), nullable=True)  # Live demo URL

    # Marketplace metadata
    version = Column(String(20), default="1.0.0")
    is_public = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=False)  # For public marketplace components
    is_featured = Column(Boolean, default=False)  # Featured in marketplace
    license = Column(String(50), default="MIT")  # Component license (MIT, Apache-2.0, etc.)

    # Pricing (for paid components)
    price = Column(Float, default=0.0)  # Price in USD (0 = free)
    currency = Column(String(3), default="USD")
    revenue_share = Column(Float, default=0.7)  # Author revenue share (70%)

    # Usage stats
    installs = Column(Integer, default=0)
    downloads = Column(Integer, default=0)  # Download count (includes previews)
    views = Column(Integer, default=0)  # Page views
    rating = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)

    # Dependencies
    dependencies = Column(JSONColumn, nullable=True)  # NPM packages or CDN links
    css_dependencies = Column(JSONColumn, nullable=True)

    # Canvas-Skill Integration
    required_skill_id = Column(String, ForeignKey("skills.id", ondelete="SET NULL"), nullable=True, index=True)  # Skill that component requires
    skill_version = Column(String(50), nullable=True)  # Version of skill component was designed for
    auto_install_skill = Column(Boolean, nullable=False, default=True, server_default="true")  # Auto-install skill on component install

    # Approval workflow
    submitted_for_approval = Column(Boolean, default=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(String, ForeignKey("users.id"), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="canvas_components")
    author = relationship("User", backref="published_components", foreign_keys=[author_id])
    approver = relationship("User", backref="approved_components", foreign_keys=[approved_by])
    installations = relationship("ComponentInstallation", back_populates="component", cascade="all, delete-orphan")
    required_skill = relationship("Skill", foreign_keys=[required_skill_id])


class ComponentInstallation(Base):
    """
    Component installations on canvases.

    Tracks which components are installed on which canvases
    with instance-specific configuration.
    """
    __tablename__ = "component_installations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    canvas_id = Column(String, ForeignKey("canvases.id", ondelete="CASCADE"), nullable=False, index=True)
    component_id = Column(String, ForeignKey("canvas_components.id", ondelete="CASCADE"), nullable=False, index=True)

    # Instance configuration
    config = Column(JSONColumn, nullable=True)  # Component props for this instance
    position = Column(JSONColumn, nullable=True)  # { x, y, width, height }
    z_index = Column(Integer, default=0)

    # Timestamps
    installed_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant")
    canvas = relationship("Canvas", back_populates="installations")
    component = relationship("CanvasComponent", back_populates="installations")


class MarketplaceRating(Base):
    """
    User ratings and reviews for marketplace components.

    Tracks individual ratings with reviews for transparency.
    """
    __tablename__ = "marketplace_ratings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    component_id = Column(String, ForeignKey("canvas_components.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Rating
    rating = Column(Integer, nullable=False)  # 1-5 stars
    review = Column(Text, nullable=True)  # Optional review text

    # Moderation
    is_flagged = Column(Boolean, default=False)  # Flagged for review
    is_visible = Column(Boolean, default=True)  # Hidden if inappropriate

    # Helpful votes
    helpful_count = Column(Integer, default=0)
    not_helpful_count = Column(Integer, default=0)

    # Response from author
    author_response = Column(Text, nullable=True)
    author_response_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="marketplace_ratings")
    component = relationship("CanvasComponent", backref="ratings")
    user = relationship("User", backref="marketplace_ratings")

    __table_args__ = (
        UniqueConstraint('component_id', 'user_id', name='uq_component_user_rating'),
    )


class CanvasTemplate(Base):
    """
    User-generated canvas templates.

    Supports:
    - Template marketplace
    - Template versioning
    - Template categories
    """
    __tablename__ = "canvas_templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)  # NULL = public template
    author_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Template details
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)

    # Template snapshot
    canvas_snapshot = Column(JSONColumn, nullable=False)  # Full canvas state
    component_installations = Column(JSONColumn, nullable=True)  # List of installed components
    styles = Column(JSONColumn, nullable=True)  # Custom CSS

    # Metadata
    is_public = Column(Boolean, default=False)
    thumbnail_url = Column(String(500), nullable=True)

    # Usage stats
    usage_count = Column(Integer, default=0)
    rating = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="canvas_templates")
    author = relationship("User", backref="published_templates")



# REDUNDANT AgentHandoff / Strategy models removed - using definitions at line 1544

class Workflow(Base):
    """Core workflow definition model."""
    __tablename__ = 'workflows'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    tenant_id = Column(String, ForeignKey('tenants.id', ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=True)
    status = Column(String, default="active")
    configuration = Column(JSONColumn, nullable=True)
    usage_count = Column(Integer, default=0)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="workflows")
    user = relationship("User", backref="workflows")
    steps = relationship("WorkflowStep", back_populates="workflow", cascade="all, delete-orphan")

    def as_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "usage_count": self.usage_count,
            "last_run_at": self.last_run_at
        }

class WorkflowStep(Base):
    """Individual step within a workflow."""
    __tablename__ = 'workflow_steps'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String, ForeignKey('workflows.id', ondelete="CASCADE"), nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
    connector_id = Column(String, nullable=True)
    operation_id = Column(String, nullable=True)
    parameters = Column(JSONColumn, nullable=True)
    priority = Column(String, default="MEDIUM") # LOW, MEDIUM, HIGH, URGENT
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    workflow = relationship("Workflow", back_populates="steps")



# REDUNDANT AgentCanvasPresence removed - using definition at line 1581


# ========================================================================
# INTEGRATION OAUTH MODELS
# ========================================================================

class OAuthState(Base):
    """
    OAuth state management for CSRF protection during OAuth flows.

    Stores temporary state tokens during OAuth authorization flows
    to prevent CSRF attacks. States expire after 10 minutes.

    Used by all OAuth2 integrations (Slack, Salesforce, HubSpot, etc.).
    """
    __tablename__ = "oauth_states"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)

    # OAuth state token (unique, indexed for fast lookup)
    state = Column(String, nullable=False, unique=True, index=True)

    # Provider identifier (e.g., 'slack', 'salesforce', 'stripe')
    provider = Column(String, nullable=False)

    # Expiration timestamp (typically 10 minutes from creation)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # Creation timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Where to redirect after successful OAuth
    redirect_uri = Column(String, nullable=True)

    # Additional provider-specific data
    extra_data = Column(JSONColumn, nullable=True)

    # Relationships
    tenant = relationship("Tenant", backref="oauth_states")
    user = relationship("User", backref="oauth_states")

    def __repr__(self):
        return f"<OAuthState(id={self.id}, provider={self.provider}, state={self.state[:8]}...)>"

    def is_valid(self) -> bool:
        """Check if state is still valid (not expired)."""
        from datetime import datetime
        return datetime.now(self.expires_at.tzinfo) < self.expires_at


class IntegrationToken(Base):
    """
    Integration token storage for OAuth access/refresh tokens.

    Stores OAuth credentials for all third-party integrations.
    Supports multi-provider token management with automatic refresh.

    Providers:
    - OAuth2: Slack, Salesforce, HubSpot, Google, Microsoft, Stripe, etc.
    - API Key: Airtable, OpenAI, etc. (store in access_token field)
    - Basic Auth: Store base64 encoded credentials in access_token field
    """
    __tablename__ = "integration_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True)

    # Provider identifier (e.g., 'slack', 'salesforce', 'stripe')
    provider = Column(String, nullable=False, index=True)

    # OAuth credentials
    access_token = Column(Text, nullable=False)  # Encrypted at rest
    refresh_token = Column(Text, nullable=True)  # Encrypted at rest
    token_type = Column(String, default="Bearer")  # Bearer, Basic, etc.

    # Token expiration (for access_token auto-refresh)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Provider-specific metadata (e.g., Salesforce instance URL)
    instance_url = Column(Text, nullable=True)

    # Granted scopes (for OAuth2)
    scope = Column(Text, nullable=True)

    # Token status
    status = Column(String, default="active")  # active, revoked, expired

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="integration_tokens")
    user = relationship("User", backref="integration_tokens")
    workspace = relationship("Workspace", backref="integration_tokens")

    # Unique constraint: one active token per tenant+provider+user combination
    __table_args__ = (
        UniqueConstraint('tenant_id', 'provider', 'user_id', name='uq_integration_token_user'),
    )

    def __repr__(self):
        masked_token = f"{self.access_token[:8]}..." if self.access_token else None
        return f"<IntegrationToken(id={self.id}, provider={self.provider}, status={self.status})>"

    def is_expired(self) -> bool:
        """Check if access token is expired."""
        if not self.expires_at:
            return False
        from datetime import datetime
        return datetime.now(self.expires_at.tzinfo) >= self.expires_at

    def is_valid(self) -> bool:
        """Check if token is valid (active and not expired)."""
        return self.status == "active" and not self.is_expired()


# ============================================================================
# Brain System Models - Agent Memory and Learning
# ============================================================================

class AgentMemory(Base):
    """
    Stores agent memories with embeddings for semantic search.
    Part of the Cognitive Architecture memory system.
    """
    __tablename__ = 'agent_memories'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=True, index=True)
    tenant_id = Column(String(255), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(255), ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Memory content
    content = Column(Text, nullable=False)
    embedding = Column(JSONColumn, nullable=True)  # Vector embedding for similarity search
    memory_type = Column(String, default='semantic')  # semantic, episodic, procedural
    
    # Metadata
    metadata_json = Column(JSONColumn, nullable=True)
    importance_score = Column(Float, default=0.5)  # 0-1, used for forgetting
    access_count = Column(Integer, default=0)  # Used for memory reinforcement
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)

    # Episodic Memory Link (Phase: Episodic Memory & Graduation)
    episode_id = Column(String(255), ForeignKey("agent_episodes.id", ondelete="SET NULL"), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    tenant = relationship("Tenant", backref="agent_memories")
    agent = relationship("AgentRegistry", backref="memories")
    
    def __repr__(self):
        return f"<AgentMemory(id={self.id}, agent_id={self.agent_id}, type={self.memory_type})>"


class CognitiveExperience(Base):
    """
    Stores learning experiences from agent execution.
    Used for RLHF and performance tracking.
    """
    __tablename__ = 'cognitive_experiences'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(255), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(255), ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Experience details
    experience_type = Column(String, nullable=False)  # reasoning, learning, adaptation, etc.
    task_type = Column(String, nullable=True)  # Category of task performed
    input_summary = Column(Text, nullable=True)
    output_summary = Column(Text, nullable=True)
    outcome = Column(String, nullable=False, index=True)  # success, failure, partial
    
    # Learning data
    learnings = Column(JSONColumn, nullable=True)  # Key insights from this experience
    cognitive_metrics = Column(JSONColumn, nullable=True)  # Performance metrics
    effectiveness_score = Column(Float, nullable=True)  # 0-1, how effective was this approach
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    tenant = relationship("Tenant", backref="cognitive_experiences")
    agent = relationship("AgentRegistry", backref="cognitive_experiences")
    
    def __repr__(self):
        return f"<CognitiveExperience(id={self.id}, agent_id={self.agent_id}, outcome={self.outcome})>"


class CommunicationSuggestion(Base):
    """
    Stores AI-generated communication suggestions for user review.
    Used by the Communication Intelligence service.
    """
    __tablename__ = 'communication_suggestions'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(255), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(255), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Communication details
    channel_id = Column(String(255), nullable=True)  # Slack channel, email thread, etc.
    integration_type = Column(String(50), nullable=False)  # slack, email, teams
    suggestion_text = Column(Text, nullable=False)

    # Status tracking
    status = Column(String(20), nullable=False, default='pending', index=True)  # pending, accepted, rejected, modified

    # Original context for reference
    original_content = Column(Text, nullable=True)
    context_data = Column(JSONColumn, nullable=True)  # Related entities, deals, etc.

    # User feedback
    user_feedback = Column(Text, nullable=True)
    rating = Column(Integer, nullable=True)  # 1-5 rating if user provides feedback

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    responded_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant", backref="communication_suggestions")
    user = relationship("User", backref="communication_suggestions")

    def __repr__(self):
        return f"<CommunicationSuggestion(id={self.id}, user_id={self.user_id}, status={self.status})>"


class Notification(Base):
    """
    Stores in-app notifications for users.
    Used by the Notification Service.
    """
    __tablename__ = 'notifications'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(255), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(255), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(255), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Notification details
    title = Column(String(500), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), nullable=False, default='info')  # info, warning, error, success
    metadata_json = Column(JSONColumn, nullable=True)  # Additional context

    # Status
    read = Column(Boolean, nullable=False, default=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)

    # Action links (optional)
    action_url = Column(String(500), nullable=True)
    action_label = Column(String(100), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant", backref="notifications")
    user = relationship("User", backref="notifications")
    workspace = relationship("Workspace", backref="notifications")

    def __repr__(self):
        return f"<Notification(id={self.id}, user_id={self.user_id}, type={self.type}, read={self.read})>"

# RBAC Models
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", String, ForeignKey("custom_roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", String, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    extend_existing=True  # Allow redefinition during test collection
)

class Permission(Base):
    __tablename__ = "permissions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    scope = Column(String, nullable=False) # e.g. "agents", "billing"
    action = Column(String, nullable=False) # e.g. "create", "read"
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CustomRole(Base):
    __tablename__ = "custom_roles"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    permissions = relationship("Permission", secondary=role_permissions, backref="roles")
    tenant = relationship("Tenant", backref="custom_roles")

class Artifact(Base):
    """
    Persistent AI-generated artifacts (code, markdown, etc.) that can be edited by users.
    Multi-tenant version with tenant_id for SaaS isolation.

    Note: extend_existing=True is set to handle the duplicate Artifact class definition
    at line 2577. This is a pre-existing issue in the codebase.
    """
    __tablename__ = "artifacts"
    __table_args__ = {'extend_existing': True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    canvas_id = Column(String, ForeignKey("canvases.id", ondelete="CASCADE"), nullable=True, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)
    session_id = Column(String, nullable=True, index=True)  # Logical link to chat session

    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # 'code', 'markdown', etc.
    content = Column(Text, nullable=False)
    metadata_json = Column(JSONColumn, default={})

    version = Column(Integer, default=1)
    is_locked = Column(Boolean, default=False)
    locked_by_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    author_id = Column(String, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Relationships
    author = relationship("User", foreign_keys=[author_id])
    locked_by = relationship("User", foreign_keys=[locked_by_user_id])
    tenant = relationship("Tenant", backref="artifacts")
    workspace = relationship("Workspace", backref="artifacts")
    canvas = relationship("Canvas", backref="artifacts")
    comments = relationship("ArtifactComment", back_populates="artifact", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Artifact(id={self.id}, name={self.name}, type={self.type})>"


class ArtifactComment(Base):
    """
    Comments and annotations on canvas artifacts.
    Allows users to leave contextual notes and agents to read them for enhanced understanding.
    Multi-tenant version with tenant_id for SaaS isolation.
    """
    __tablename__ = "artifact_comments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_id = Column(String, ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True, index=True)

    content = Column(Text, nullable=False)
    metadata_json = Column(JSONColumn, default={})  # For attachments, formatting, etc.

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="artifact_comments")
    artifact = relationship("Artifact", back_populates="comments")
    user = relationship("User", backref="artifact_comments")
    agent = relationship("AgentRegistry", backref="artifact_comments")

    def __repr__(self):
        return f"<ArtifactComment(id={self.id}, artifact_id={self.artifact_id})>"


# For backward compatibility with legacy Role references in core/rbac.py
Role = CustomRole
RolePermission = role_permissions


# ============================================================================
# Episodic Memory & Graduation Exam Models
# ============================================================================

class EpisodeOutcome(str, enum.Enum):
    """Possible outcomes for an agent episode"""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"

class PromotionType(str, enum.Enum):
    """Types of agent promotion"""
    AUTOMATIC = "automatic"  # Via graduation exam
    MANUAL = "manual"        # Admin override
    DEMOTION = "demotion"    # Level decrease


class AgentEpisode(Base):
    """
    Core episodic memory table for tracking agent execution cycles.

    Each episode represents a discrete task execution with constitutional
    compliance and human intervention tracking. Used for graduation readiness
    calculation and learning analysis.

    Storage: PostgreSQL + pgvector (hot storage for recent episodes)
    """
    __tablename__ = 'agent_episodes'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(255), ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(255), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_id = Column(String(255), ForeignKey("agent_executions.id", ondelete="SET NULL"), nullable=True)

    # Task description
    task_description = Column(Text, nullable=True)
    maturity_at_time = Column(String(50), nullable=False)  # student, intern, supervised, autonomous

    # Constitutional compliance metrics
    constitutional_score = Column(Float, default=1.0)  # 0.0 to 1.0
    human_intervention_count = Column(Integer, default=0)
    confidence_score = Column(Float, default=0.5)  # 0.0 to 1.0

    # Outcome tracking
    outcome = Column(String(20), nullable=False, index=True)  # success, failure, partial
    success = Column(Boolean, default=False)
    step_efficiency = Column(Float, default=1.0)  # TRACE framework efficiency metric

    # Execution status
    status = Column(String(20), nullable=False, default="active", index=True)  # active, completed, failed, cancelled

    # Metadata
    metadata_json = Column(JSONColumn, nullable=True)

    # Vector embedding for semantic search (pgvector)
    # Use dynamic Vector dimension if pgvector is available, otherwise fall back to JSON
    embedding = Column(
        Vector(EMBEDDING_DIM) if (PGVECTOR_AVAILABLE and Vector is not None) else JSON,
        nullable=True
    )

    # Boundaries
    started_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Relationships
    session_id = Column(String(255), nullable=True, index=True) # Links to ChatSession

    # Canvas linkage (NEW - Feb 2026)
    canvas_ids = Column(JSONColumn, default=list) # List of CanvasAudit IDs
    canvas_action_count = Column(Integer, default=0) # Total canvas actions in episode

    # Supervision System Integration (Phase: Supervision-Learning Integration)
    supervisor_type = Column(String(50), nullable=True, comment='Type of supervisor (user or autonomous_agent)')
    supervisor_id = Column(String(255), nullable=True, comment='ID of the supervisor (user_id or agent_id)')
    proposal_id = Column(String(255), nullable=True, index=True, comment='Link to original proposal if episode from supervision flow')
    supervision_decision = Column(String(20), nullable=True, index=True, comment='Supervision decision (approved or rejected)')
    supervision_reasoning = Column(Text, nullable=True, comment='Supervisor rationale for decision')
    execution_followed_proposal = Column(Boolean, nullable=True, comment='Did execution match the approved proposal?')

    # Additional supervision metadata for retrieval service
    supervisor_rating = Column(Integer, nullable=True, comment='Supervisor rating 1-5 for this episode')
    intervention_types = Column(JSONColumn, nullable=True, comment='List of intervention types (human_correction, guidance, termination)')
    supervision_feedback = Column(Text, nullable=True, comment='Detailed feedback from supervisor')

    # Feedback linkage (NEW - Feb 2026)
    feedback_ids = Column(JSONColumn, default=list) # List of AgentFeedback IDs
    aggregate_feedback_score = Column(Float, nullable=True) # -1.0 to 1.0 aggregate score

    # Content
    topics = Column(JSONColumn, default=list) # Extracted topics
    entities = Column(JSONColumn, default=list) # Named entities
    importance_score = Column(Float, default=0.5, index=True) # 0.0 to 1.0

    # Lifecycle
    decay_score = Column(Float, default=1.0) # 0.0 to 1.0, decays over time
    access_count = Column(Integer, default=0, nullable=False)
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Episode consolidation
    consolidated_into = Column(String(255), ForeignKey("agent_episodes.id", ondelete="SET NULL"), nullable=True, index=True)
    consolidated_episodes = relationship("AgentEpisode", remote_side=[id], foreign_keys=[consolidated_into])

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('ix_agent_episodes_metadata_gin', 'metadata_json', postgresql_using='gin'),
    )

    # Relationships
    agent = relationship("AgentRegistry", backref="episodes")
    tenant = relationship("Tenant", backref="agent_episodes")
    execution = relationship("AgentExecution", backref="episode")
    feedback_records = relationship("EpisodeFeedback", back_populates="episode", cascade="all, delete-orphan")
    segments = relationship("EpisodeSegment", backref="episode", cascade="all, delete-orphan")
    access_logs = relationship("EpisodeAccessLog", backref="episode", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AgentEpisode(id={self.id}, agent_id={self.agent_id}, outcome={self.outcome})>"


class EpisodeFeedback(Base):
    """
    Human feedback for agent episodes (RLHF - Reinforcement Learning from Human Feedback).

    Links human feedback to specific episodes for enhanced agent learning.
    Feedback is linked via episode metadata (feedback_id reference) but retrieved
    completely during agent decision-making to provide full feedback context.
    """
    __tablename__ = 'episode_feedback'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    episode_id = Column(String(255), ForeignKey("agent_episodes.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(255), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Feedback score (-1.0 to 1.0)
    feedback_score = Column(Float, nullable=False)

    # Optional detailed feedback
    feedback_notes = Column(Text, nullable=True)
    feedback_category = Column(String(100), nullable=True)  # "accuracy", "helpfulness", "safety", etc.

    # Provider info
    provider_id = Column(String(255), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    provider_type = Column(String(50), default="human")  # "human", "automated", "peer_agent"

    # Timestamps
    provided_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    episode = relationship("AgentEpisode", back_populates="feedback_records")

    __table_args__ = (
        Index('idx_episode_feedback_episode_id', 'episode_id'),
        Index('idx_episode_feedback_tenant_id', 'tenant_id'),
    )

    def __repr__(self):
        return f"<EpisodeFeedback(id={self.id}, episode_id={self.episode_id}, score={self.feedback_score})>"


class EpisodeSegment(Base):
    """
    Individual segments within an episode.
    """
    __tablename__ = 'episode_segments'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    episode_id = Column(String(255), ForeignKey("agent_episodes.id", ondelete="CASCADE"), nullable=False, index=True)
    
    segment_type = Column(String(50), nullable=False) # conversation, execution, reflection, canvas_update
    sequence_order = Column(Integer, nullable=False)
    
    content = Column(Text, nullable=False)
    content_summary = Column(String(255), nullable=True)

    source_type = Column(String(50), nullable=True) # e.g., "slack", "canvas", "terminal"
    source_id = Column(String(255), nullable=True)

    # Canvas presentation context for semantic understanding
    canvas_context = Column(JSONColumn, nullable=True, comment='Canvas presentation context (canvas_type, presentation_summary, critical_data_points, visual_elements)')

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<EpisodeSegment(id={self.id}, episode_id={self.episode_id}, type={self.segment_type})>"


class EpisodeAccessLog(Base):
    """
    Audit log for episode access/recall.
    """
    __tablename__ = 'episode_access_logs'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    episode_id = Column(String(255), ForeignKey("agent_episodes.id", ondelete="CASCADE"), nullable=True, index=True)

    accessed_by_agent = Column(String(255), nullable=False, index=True)
    access_type = Column(String(50), nullable=False) # temporal, semantic, contextual

    governance_check_passed = Column(Boolean, default=True)
    agent_maturity_at_access = Column(String(50), nullable=True)
    results_count = Column(Integer, default=1)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<EpisodeAccessLog(id={self.id}, episode_id={self.episode_id}, agent={self.accessed_by_agent})>"


class GraduationExam(Base):
    """
    Track graduation exam attempts for agent maturity progression.

    Stores exam results including readiness scores, edge case simulation
    results, and constitutional compliance checks.
    """
    __tablename__ = 'graduation_exams'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(255), ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(255), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    target_level = Column(String(50), nullable=False)  # Level being tested for
    current_level = Column(String(50), nullable=False)  # Level at exam time

    # Readiness scores
    readiness_score = Column(Float, nullable=False)  # Overall score 0.0 to 1.0
    zero_intervention_ratio = Column(Float, nullable=False)  # 40% weight
    avg_constitutional_score = Column(Float, nullable=False)  # 30% weight
    avg_confidence_score = Column(Float, nullable=False)  # 20% weight
    success_rate = Column(Float, nullable=False)  # 10% weight
    episodes_analyzed = Column(Integer, default=0)

    # Skill performance scores (Stage 6)
    skill_mastery_score = Column(Float, nullable=True)  # Overall skill mastery
    skill_diversity_score = Column(Float, nullable=True)  # Skill diversity metric
    skills_used = Column(JSONColumn, nullable=True)  # List of skill_id used

    # Edge case simulation results
    edge_case_results = Column(JSONColumn, nullable=True)  # Detailed results per edge case
    edge_cases_passed = Column(Integer, default=0)
    edge_cases_total = Column(Integer, default=5)

    # Constitutional check results
    constitutional_violations = Column(JSONColumn, nullable=True)  # List of violations found
    constitutional_check_passed = Column(Boolean, default=False)

    # Exam outcome
    passed = Column(Boolean, default=False)
    promoted = Column(Boolean, default=False)
    promoted_at = Column(DateTime(timezone=True), nullable=True)
    failure_reason = Column(Text, nullable=True)

    # Metadata
    metadata_json = Column(JSONColumn, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    agent = relationship("AgentRegistry", backref="graduation_exams", foreign_keys=[agent_id])
    tenant = relationship("Tenant", backref="graduation_exams")

    def __repr__(self):
        return f"<GraduationExam(id={self.id}, agent_id={self.agent_id}, passed={self.passed})>"


class PromotionHistory(Base):
    """
    Audit trail for agent promotions and demotions.

    Records all maturity level changes with readiness scores,
    promotion type, and justification for audit purposes.
    """
    __tablename__ = 'promotion_history'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(255), ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(255), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    from_level = Column(String(50), nullable=False)
    to_level = Column(String(50), nullable=False)

    # Promotion details
    promotion_type = Column(String(20), nullable=False)  # automatic, manual, demotion
    readiness_score = Column(Float, nullable=False)  # Score at time of promotion
    exam_id = Column(String(255), ForeignKey("graduation_exams.id", ondelete="SET NULL"), nullable=True)

    # Who and why
    promoted_by = Column(String(255), nullable=True)  # User ID (null for automatic)
    justification = Column(Text, nullable=True)

    # Timestamps
    promoted_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    agent = relationship("AgentRegistry", backref="promotion_history", foreign_keys=[agent_id])
    tenant = relationship("Tenant", backref="promotion_history")
    exam = relationship("GraduationExam", backref="promotion_records")

    def __repr__(self):
        return f"<PromotionHistory(id={self.id}, agent_id={self.agent_id}, {self.from_level} -> {self.to_level})>"


class EdgeCaseLibrary(Base):
    """
    Historical failure patterns for graduation exam simulation.

    Stores edge cases that agents must pass during graduation exams
    to ensure they can handle known failure scenarios.
    """
    __tablename__ = 'edge_case_library'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(255), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)

    # Test case definition
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    test_input = Column(JSONColumn, nullable=False)  # Input that triggers the edge case
    expected_behavior = Column(JSONColumn, nullable=False)  # Expected correct behavior
    violation_type = Column(String(100), nullable=False, index=True)  # Type of violation this tests

    # Test statistics
    times_tested = Column(Integer, default=0)
    times_passed = Column(Integer, default=0)
    last_tested_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    severity = Column(String(20), default="high")  # critical, high, medium, low
    category = Column(String(100), nullable=True)  # Data safety, security, privacy, etc.
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="edge_cases")

    def __repr__(self):
        return f"<EdgeCaseLibrary(id={self.id}, name={self.name}, violation_type={self.violation_type})>"

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate for this edge case"""
        if self.times_tested == 0:
            return 0.0
        return self.times_passed / self.times_tested


class PasswordResetToken(Base):
    """
    Password reset tokens for secure password recovery flow.

    Multi-tenant password reset system with:
    - Secure token generation (32-byte URL-safe tokens)
    - 1-hour expiration
    - Single-use tokens (marked as used after redemption)
    - Rate limiting (3 requests per hour per email)
    - Full audit trail
    """
    __tablename__ = "password_reset_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Secure token (32 bytes URL-safe random)
    token = Column(String(255), nullable=False, unique=True, index=True)

    # Token expiration (1 hour from creation)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Token usage tracking
    used = Column(Boolean, default=False, nullable=False, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True)

    # IP address tracking for security
    created_ip = Column(String(45), nullable=True)  # IPv6 compatible
    used_ip = Column(String(45), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="password_reset_tokens")
    user = relationship("User", backref="password_reset_tokens")

    def __repr__(self):
        return f"<PasswordResetToken(id={self.id}, user_id={self.user_id}, used={self.used})>"

    def is_valid(self) -> bool:
        """Check if token is valid (not used and not expired)"""
        from datetime import datetime
        now = datetime.now(self.expires_at.tzinfo) if self.expires_at.tzinfo else datetime.utcnow()
        return not self.used and now < self.expires_at

    def mark_as_used(self, ip_address: str = None):
        """Mark token as used"""
        from datetime import datetime
        self.used = True
        self.used_at = datetime.now(self.expires_at.tzinfo) if self.expires_at.tzinfo else datetime.utcnow()
        self.used_ip = ip_address

# ========================================================================
# CONSOLIDATED DOMAIN MODELS (Unified Schema)
# ========================================================================



class Formula(Base):
    """
    Stored formulas for spreadsheets and calculations.
    Learned from user behavior and explicitly taught.
    """
    __tablename__ = "formulas"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)

    name = Column(String, nullable=False)
    expression = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    domain = Column(String, default="general")  # finance, sales, marketing, general

    parameters = Column(JSONColumn, default=list)  # List of parameter definitions
    dependencies = Column(JSONColumn, default=list)  # List of formula IDs this depends on

    # Usage tracking
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Quality metrics
    success_rate = Column(Float, default=1.0)  # Track successful applications
    feedback_score = Column(Float, nullable=True)  # Average user feedback (1-5)
    feedback_count = Column(Integer, default=0)

    # Source tracking
    creator_id = Column(String, nullable=True)
    source = Column(String, default="user_taught")  # user_taught, learned, system

    # Sharing
    is_public = Column(Boolean, default=False)  # Share with other tenants

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="formulas")


class FormulaFeedback(Base):
    """
    User feedback on formula suggestions and applications.
    Used to improve formula recommendation quality.
    """
    __tablename__ = "formula_feedback"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    formula_id = Column(String, ForeignKey("formulas.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Feedback
    is_helpful = Column(Boolean, nullable=True)  # True/False/NULL (skipped)
    rating = Column(Integer, nullable=True)  # 1-5 stars
    applied = Column(Boolean, default=False)  # Did user apply the formula?
    custom_expression = Column(Text, nullable=True)  # If user modified it

    # Context
    context = Column(JSONColumn, nullable=True)  # Spreadsheet context, cell range, etc.
    suggested_for = Column(Text, nullable=True)  # What query triggered this suggestion

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="formula_feedback")
    formula = relationship("Formula", backref="feedback")
    user = relationship("User", backref="formula_feedback")

class EcommerceStore(Base):
    __tablename__ = "ecommerce_stores"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(String, default="shopify")
    shop_domain = Column(String, nullable=False, unique=True, index=True)
    access_token = Column(String, nullable=True)
    
    is_active = Column(Boolean, default=True)
    metadata_json = Column(JSONColumn, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class EcommerceCustomer(Base):
    __tablename__ = "ecommerce_customers"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    external_id = Column(String, nullable=True, index=True)
    email = Column(String, nullable=False, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    
    crm_contact_id = Column(String, nullable=True)
    accounting_entity_id = Column(String, nullable=True)
    
    risk_score = Column(Float, default=0.0)
    risk_level = Column(String, default="low")
    
    metadata_json = Column(JSONColumn, nullable=True)
    is_b2b = Column(Boolean, default=False)
    pricing_config = Column(JSONColumn, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    orders = relationship("EcommerceOrder", back_populates="customer")
    subscriptions = relationship("Subscription", back_populates="customer")

class EcommerceOrder(Base):
    __tablename__ = "ecommerce_orders"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(String, ForeignKey("ecommerce_customers.id"), nullable=False)
    external_id = Column(String, nullable=True, index=True)
    subscription_id = Column(String, ForeignKey("ecommerce_subscriptions.id"), nullable=True)
    order_number = Column(String, nullable=True)
    
    status = Column(String, default="pending")
    currency = Column(String, default="USD")
    confidence_score = Column(Float, default=1.0)
    
    total_price = Column(Float, default=0.0)
    subtotal_price = Column(Float, default=0.0)
    total_tax = Column(Float, default=0.0)
    total_shipping = Column(Float, default=0.0)
    total_discounts = Column(Float, default=0.0)
    total_refunded = Column(Float, default=0.0)
    
    ledger_transaction_id = Column(String, nullable=True)
    is_ledger_synced = Column(Boolean, default=False)
    
    metadata_json = Column(JSONColumn, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    customer = relationship("EcommerceCustomer", back_populates="orders")
    items = relationship("EcommerceOrderItem", back_populates="order")
    subscription = relationship("Subscription", back_populates="orders")

class EcommerceOrderItem(Base):
    __tablename__ = "ecommerce_order_items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String, ForeignKey("ecommerce_orders.id"), nullable=False)
    
    product_id = Column(String, nullable=True)
    variant_id = Column(String, nullable=True)
    title = Column(String, nullable=False)
    sku = Column(String, nullable=True)
    quantity = Column(Integer, default=1)
    price = Column(Float, default=0.0)
    price_list_id = Column(String, nullable=True)
    tax_amount = Column(Float, default=0.0)
    
    metadata_json = Column(JSONColumn, nullable=True)
    order = relationship("EcommerceOrder", back_populates="items")

class Subscription(Base):
    __tablename__ = "ecommerce_subscriptions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(String, ForeignKey("ecommerce_customers.id"), nullable=False)
    external_id = Column(String, nullable=True, index=True)
    
    status = Column(String, default="active")
    plan_name = Column(String, nullable=True)
    mrr = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    
    billing_interval = Column(String, default="month")
    next_billing_at = Column(DateTime(timezone=True), nullable=True)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tier_id = Column(String, nullable=True)  # Reserved for future use (open-source compatible)
    current_period_usage = Column(JSONColumn, nullable=True)

    customer = relationship("EcommerceCustomer", back_populates="subscriptions")
    orders = relationship("EcommerceOrder", back_populates="subscription")
    audit_logs = relationship("SubscriptionAudit", back_populates="subscription")
    # tier relationship removed - open-source version doesn't use SaaS tiers

class SubscriptionAudit(Base):
    __tablename__ = "ecommerce_subscription_audit"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    subscription_id = Column(String, ForeignKey("ecommerce_subscriptions.id"), nullable=False)
    
    event_type = Column(String, nullable=False)
    previous_mrr = Column(Float, default=0.0)
    new_mrr = Column(Float, default=0.0)
    
    metadata_json = Column(JSONColumn, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    subscription = relationship("Subscription", back_populates="audit_logs")

# Import accounting models from accounting.models to avoid duplicate table definitions
# This resolves SQLAlchemy metadata conflicts that were blocking episodic memory tests
from accounting.models import (
    Account,
    Transaction,
    JournalEntry,
    CategorizationProposal,
    Entity,
    Bill,
    Invoice,
    Document,
    TaxNexus,
    FinancialClose,
    CategorizationRule,
    Budget,
    # Accounting enums
    AccountType,
    TransactionStatus,
    EntryType,
    EntityType,
    BillStatus,
    InvoiceStatus,
)


# Import sales models from their dedicated module
from sales.models import (
    Lead,
    Deal,
    CommissionEntry,
    CallTranscript,
    FollowUpTask,
    LeadStatus,
    DealStage,
    CommissionStatus,
    NegotiationState,
)

# Marketing Enums
class ChannelType(str, enum.Enum):
    PAID_SEARCH = "paid_search"
    PAID_SOCIAL = "paid_social"
    ORGANIC_SEARCH = "organic_search"
    DIRECT = "direct"
    REFERRAL = "referral"
    EMAIL = "email"

class MarketingChannel(Base):
    __tablename__ = "marketing_channels"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    type = Column(SQLEnum(ChannelType), nullable=False)
    status = Column(String, default="active")
    
    metadata_json = Column(JSONColumn, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AdSpendEntry(Base):
    __tablename__ = "marketing_ad_spend"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    channel_id = Column(String, ForeignKey("marketing_channels.id"), nullable=False)
    
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    date = Column(DateTime(timezone=True), nullable=False)
    
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    
    metadata_json = Column(JSONColumn, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AttributionEvent(Base):
    __tablename__ = "marketing_attribution_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(String, ForeignKey("sales_leads.id"), nullable=False)
    channel_id = Column(String, ForeignKey("marketing_channels.id"), nullable=True)
    
    event_type = Column(String, nullable=False)
    touchpoint_order = Column(Integer, default=1)
    
    source = Column(String, nullable=True)
    medium = Column(String, nullable=True)
    campaign = Column(String, nullable=True)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    metadata_json = Column(JSONColumn, nullable=True)

# Import service delivery models from their dedicated module
from service_delivery.models import (
    Contract,
    Project,
    Milestone,
    ProjectTask,
    Appointment,
    ContractType,
    ProjectStatus,
    MilestoneStatus,
    BudgetStatus,
    AppointmentStatus,
)

class ClientHealthScore(Base):
    __tablename__ = "intelligence_client_health"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    client_entity_id = Column(String, ForeignKey("accounting_entities.id"), nullable=False)
    
    overall_score = Column(Float, default=0.0)
    sentiment_score = Column(Float, default=0.0)
    financial_score = Column(Float, default=0.0)
    usage_score = Column(Float, default=0.0)
    
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())
    metadata_json = Column(JSONColumn, nullable=True)

class ResourceRole(Base):
    __tablename__ = "intelligence_resource_roles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    hourly_cost = Column(Float, default=0.0)
    billable_target = Column(Float, default=0.80)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CapacityPlan(Base):
    __tablename__ = "intelligence_capacity_plans"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(String, ForeignKey("intelligence_resource_roles.id"), nullable=False)
    
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    available_hours = Column(Float, default=0.0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    role = relationship("ResourceRole")

class BusinessScenario(Base):
    __tablename__ = "intelligence_business_scenarios"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    parameters_json = Column(JSONColumn, nullable=True)
    impact_json = Column(JSONColumn, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class WorkflowExecutionLog(Base):
    __tablename__ = "analytics_workflow_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # Core linkage
    execution_id = Column(String, index=True, nullable=False)
    workflow_id = Column(String, index=True, nullable=True)
    step_id = Column(String, index=True, nullable=True)
    step_type = Column(String, nullable=True)
    
    # Metrics
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Float, nullable=True)
    
    status = Column(String, nullable=True)
    error_code = Column(String, nullable=True)
    
    # Compatibility with older tests
    level = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=func.now())
    
    trigger_data = Column(JSONColumn, nullable=True)
    results = Column(JSONColumn, nullable=True)
    meta_info = Column(JSONColumn, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# WORKFLOW DEBUGGING MODELS
# ============================================================

class DebugVariable(Base):
    """Debug variables captured during workflow execution"""
    __tablename__ = "workflow_debug_variables"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_execution_id = Column(String, ForeignKey("workflow_executions.execution_id"), nullable=False, index=True)
    variable_name = Column(String(255), nullable=False)
    variable_value = Column(JSONColumn, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    captured_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    workflow_execution = relationship("WorkflowExecution", foreign_keys=[workflow_execution_id])

    __table_args__ = (
        Index('idx_workflow_execution_id', 'workflow_execution_id'),
    )


class ExecutionTrace(Base):
    """Execution traces for workflow debugging"""
    __tablename__ = "workflow_execution_traces"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_execution_id = Column(String, ForeignKey("workflow_executions.execution_id"), nullable=False, index=True)
    step_id = Column(String(255), nullable=False)
    trace_type = Column(String(50), nullable=False)  # info/debug/error
    message = Column(Text, nullable=True)
    trace_metadata = Column(JSONColumn, nullable=True)  # Renamed from 'metadata' (reserved)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    workflow_execution = relationship("WorkflowExecution", foreign_keys=[workflow_execution_id])

    __table_args__ = (
        Index('idx_workflow_execution_trace', 'workflow_execution_id'),
        Index('idx_trace_type', 'trace_type'),
    )


class WorkflowBreakpoint(Base):
    """Breakpoints for workflow debugging"""
    __tablename__ = "workflow_breakpoints"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String, nullable=False, index=True)
    step_id = Column(String(255), nullable=False)
    condition = Column(Text, nullable=True)  # Conditional breakpoint expression
    enabled = Column(Boolean, default=True, nullable=False)
    hit_count = Column(Integer, default=0, nullable=False)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_workflow_breakpoint', 'workflow_id'),
        Index('idx_step_breakpoint', 'step_id'),
    )


class WorkflowDebugSession(Base):
    """Debug sessions for workflow debugging"""
    __tablename__ = "workflow_debug_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_execution_id = Column(String, ForeignKey("workflow_executions.execution_id"), nullable=True, index=True)
    session_type = Column(String(50), nullable=False)  # interactive/automated
    status = Column(String(50), nullable=False)  # active/paused/completed
    breakpoints = Column(JSONColumn, nullable=True, default=list)
    current_step = Column(String(255), nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    workflow_execution = relationship("WorkflowExecution", foreign_keys=[workflow_execution_id])

    __table_args__ = (
        Index('idx_debug_session_execution', 'workflow_execution_id'),
        Index('idx_debug_session_status', 'status'),
    )


# ============================================================
# AWS SES INTEGRATION MODELS
# ============================================================

class SESTemplate(Base):
    """Cache of AWS SES email templates per tenant"""
    __tablename__ = "ses_templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)
    workspace_id = Column(String, index=True)

    template_name = Column(String(255), nullable=False)
    subject_part = Column(Text)
    html_part = Column(Text)
    text_part = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SESEmailEvent(Base):
    """Track all SES email events (Send, Delivery, Bounce, Complaint, Reject)"""
    __tablename__ = "ses_email_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)
    workspace_id = Column(String, index=True)

    message_id = Column(String(255))
    event_type = Column(String(50), nullable=False)  # 'Send', 'Delivery', 'Bounce', 'Complaint', 'Reject'
    recipient_email = Column(String(255), nullable=False)
    from_email = Column(String(255))

    # Event details
    event_data = Column(JSONColumn)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    processed = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # AWS SES specific fields
    ses_message_id = Column(String(255))
    complaint_feedback_type = Column(String(100))
    bounce_type = Column(String(100))
    bounce_subtype = Column(String(100))

    # Link to template if applicable
    template_name = Column(String(255))


class SESBounceList(Base):
    """Suppression list for bounced email addresses"""
    __tablename__ = "ses_bounce_list"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)
    workspace_id = Column(String, index=True)

    email = Column(String(255), nullable=False)
    bounce_type = Column(String(100))  # 'Permanent', 'Transient'
    bounce_subtype = Column(String(100))  # 'General', 'NoEmail', etc.
    bounced_at = Column(DateTime(timezone=True), server_default=func.now())
    bounce_count = Column(Integer, default=1)
    last_bounced_at = Column(DateTime(timezone=True), server_default=func.now())

    # Is this email permanently suppressed?
    is_suppressed = Column(Boolean, default=False)
    suppressed_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SESComplaintList(Base):
    """Suppression list for emails marked as spam"""
    __tablename__ = "ses_complaint_list"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)
    workspace_id = Column(String, index=True)

    email = Column(String(255), nullable=False)
    complaint_feedback_type = Column(String(100))  # 'abuse', 'auth-failure', 'fraud', 'not-spam', 'other', 'virus'
    complaint_sub_type = Column(String(100))
    complained_at = Column(DateTime(timezone=True), server_default=func.now())
    complaint_count = Column(Integer, default=1)
    last_complained_at = Column(DateTime(timezone=True), server_default=func.now())

    # Is this email permanently suppressed?
    is_suppressed = Column(Boolean, default=False)
    suppressed_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# =============================================================================
# DEBUG SYSTEM MODELS (Phase 203)
# =============================================================================

class DebugEvent(Base):
    """
    Debug event captured during agent execution.

    Tracks anomalies, errors, and notable events for debugging
    and system health monitoring.
    """
    __tablename__ = "debug_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(50), nullable=False, index=True)  # log, state_snapshot, metric, error, system
    component_type = Column(String(50), nullable=False, index=True)  # agent, browser, workflow, system
    component_id = Column(String, nullable=True, index=True)  # Component identifier
    correlation_id = Column(String, nullable=False, index=True)  # Links related events
    parent_event_id = Column(String, nullable=True, index=True)  # For event chains
    level = Column(String(20), nullable=True)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message = Column(Text, nullable=True)  # Log message
    data = Column(JSONColumn, nullable=True)  # Full event data
    event_metadata = Column(JSONColumn, nullable=True)  # Tags, labels, additional context
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    def __repr__(self):
        return f"<DebugEvent {self.id}: {self.event_type} - {self.level}>"


class DebugInsight(Base):
    """
    AI-generated insight about a debug event.

    Provides analysis, root cause hypotheses, and suggested actions
    for debug events using AI-powered diagnostics.
    """
    __tablename__ = "debug_insights"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    insight_type = Column(String(50), nullable=False, index=True)  # error, performance, anomaly, consistency, flow
    severity = Column(String(20), nullable=False, index=True)  # critical, warning, info
    title = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    evidence = Column(JSONColumn, nullable=True)  # Evidence data
    confidence_score = Column(Float, default=0.5)  # 0.0 to 1.0
    suggestions = Column(JSONColumn, nullable=True)  # List of suggestion strings
    scope = Column(String(50), nullable=True)  # component, system, distributed
    affected_components = Column(JSONColumn, nullable=True)  # List of affected components
    resolved = Column(Boolean, default=False, index=True)
    generated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    def __repr__(self):
        return f"<DebugInsight {self.id}: {self.insight_type} (confidence: {self.confidence_score})>"


# =============================================================================
# UNIVERSAL COMMUNICATION BRIDGE MODELS (Phase 1 Quick Wins)
# =============================================================================

class CommunicationChannel(Base):
    """
    Represents a communication channel (platform) connected to a tenant.
    Enables Universal Communication Bridge for cross-platform messaging.
    """
    __tablename__ = "communication_channels"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Channel identification
    platform = Column(String(50), nullable=False)  # whatsapp, telegram, slack, discord, etc.
    channel_id = Column(String, nullable=False)  # Platform-specific channel ID
    channel_name = Column(String(255), nullable=True)  # Human-readable name

    # Configuration
    is_active = Column(Boolean, default=True)
    is_two_way = Column(Boolean, default=False)  # Can agents send messages back?
    config = Column(JSONColumn, nullable=True)  # Platform-specific config (webhook URL, tokens, etc.)

    # Routing
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True)  # Default agent for this channel
    auto_reply_enabled = Column(Boolean, default=False)
    auto_reply_threshold = Column(Float, default=0.7)  # Confidence threshold for auto-reply

    # Rate limiting
    rate_limit_per_minute = Column(Integer, default=60)
    rate_limit_per_hour = Column(Integer, default=1000)

    # Metadata
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    message_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="communication_channels")
    agent = relationship("AgentRegistry", backref="monitored_channels")

    __table_args__ = (
        UniqueConstraint('tenant_id', 'platform', 'channel_id', name='uq_tenant_platform_channel'),
    )


class UnifiedMessage(Base):
    """
    Unified representation of messages across all communication platforms.
    Enables cross-platform message aggregation and routing.
    """
    __tablename__ = "unified_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    channel_id = Column(String, ForeignKey("communication_channels.id", ondelete="CASCADE"), nullable=False, index=True)

    # Message content
    platform = Column(String(50), nullable=False)  # Source platform
    platform_message_id = Column(String, nullable=True)  # Original message ID from platform
    sender_id = Column(String, nullable=False)  # Platform-specific sender ID
    sender_name = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)

    # Direction
    direction = Column(String(20), nullable=False)  # inbound, outbound

    # Processing
    status = Column(String(50), default="pending")  # pending, processed, failed, ignored
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True)
    confidence_score = Column(Float, nullable=True)

    # Response (if outbound)
    response_message_id = Column(String, nullable=True)  # Links to outbound response
    response_content = Column(Text, nullable=True)
    response_sent_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    metadata_json = Column(JSONColumn, nullable=True)  # Platform-specific metadata
    attachments = Column(JSONColumn, nullable=True)  # List of attachments
    mentions = Column(JSONColumn, nullable=True)  # List of mentioned users

    # Timestamps
    platform_timestamp = Column(DateTime(timezone=True), nullable=True)  # Original timestamp from platform
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant", backref="unified_messages")
    channel = relationship("CommunicationChannel", backref="messages")
    agent = relationship("AgentRegistry", backref="handled_messages")


class MessageRoutingRule(Base):
    """
    Rules for routing messages to specific agents or workflows.
    Enables intelligent message distribution.
    """
    __tablename__ = "message_routing_rules"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Rule definition
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Higher priority rules evaluated first

    # Conditions (all must match)
    channel_platform = Column(String(50), nullable=True)  # Specific platform
    channel_id = Column(String, nullable=True)  # Specific channel
    sender_id_pattern = Column(String, nullable=True)  # Regex pattern for sender
    content_pattern = Column(String, nullable=True)  # Regex pattern for content
    mention_pattern = Column(String, nullable=True)  # Mention triggers (e.g., "@atom")

    # Action
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True)  # Route to specific agent
    workflow_id = Column(String, nullable=True)  # Route to workflow
    auto_reply = Column(Boolean, default=False)
    auto_reply_message = Column(Text, nullable=True)

    # Rate limiting per rule
    max_matches_per_hour = Column(Integer, nullable=True)

    # Metrics
    match_count = Column(Integer, default=0)
    last_matched_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="message_routing_rules")
    agent = relationship("AgentRegistry", backref="routing_rules")


class MessageTemplate(Base):
    """
    Reusable message templates for proactive messaging.
    Supports variable substitution and multi-language.
    """
    __tablename__ = "message_templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)  # NULL for global templates

    # Template definition
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)  # welcome, followup, reminder, promotional, notification

    # Content
    subject = Column(String(255), nullable=True)  # For email platforms
    body = Column(Text, nullable=False)  # Template body with {{variable}} placeholders
    language = Column(String(10), default="en")  # ISO language code

    # Variables
    variables = Column(JSONColumn, nullable=True)  # List of variable names and descriptions

    # State
    is_active = Column(Boolean, default=True)
    is_public = Column(Boolean, default=False)  # Public templates available to all tenants

    # Usage tracking
    usage_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="message_templates")


class ScheduledMessage(Base):
    """
    Scheduled and recurring messages for proactive communication.
    """
    __tablename__ = "scheduled_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Target
    platform = Column(String(50), nullable=False)  # Target platform
    target_id = Column(String, nullable=False)  # Target user/channel ID

    # Content
    content = Column(Text, nullable=False)  # Message content (or rendered template)
    template_id = Column(String, ForeignKey("message_templates.id"), nullable=True)
    template_variables = Column(JSONColumn, nullable=True)  # Variables for template rendering

    # Scheduling
    scheduled_at = Column(DateTime(timezone=True), nullable=False)  # Next scheduled delivery
    timezone = Column(String(50), default="UTC")  # Recipient timezone
    recurrence_rule = Column(String(255), nullable=True)  # Cron expression or simple pattern: "daily", "weekly", etc.
    recurrence_end_at = Column(DateTime(timezone=True), nullable=True)  # End date for recurring messages

    # Delivery
    status = Column(String(50), default="pending")  # pending, sent, failed, cancelled
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivery_count = Column(Integer, default=0)  # For recurring messages
    error_message = Column(Text, nullable=True)

    # Context
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=True)
    metadata_json = Column(JSONColumn, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="scheduled_messages")
    agent = relationship("AgentRegistry", backref="scheduled_messages")
    template = relationship("MessageTemplate", backref="scheduled_messages")


class MessageDeliveryReport(Base):
    """
    Track delivery status and analytics for scheduled messages.
    """
    __tablename__ = "message_delivery_reports"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    scheduled_message_id = Column(String, ForeignKey("scheduled_messages.id"), nullable=False, index=True)

    # Delivery status
    status = Column(String(50), nullable=False)  # sent, delivered, opened, clicked, bounced, failed
    status_details = Column(Text, nullable=True)  # Additional status information

    # Platform-specific tracking
    platform_message_id = Column(String, nullable=True)  # Message ID from platform
    platform_tracking_id = Column(String, nullable=True)  # Tracking ID from platform

    # Engagement (where supported)
    opened_at = Column(DateTime(timezone=True), nullable=True)
    clicked_at = Column(DateTime(timezone=True), nullable=True)
    click_count = Column(Integer, default=0)

    # Timestamps
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="message_delivery_reports")
    scheduled_message = relationship("ScheduledMessage", backref="delivery_reports")


# ============================================================================
# Remote Access & Distributed Execution Models
# ============================================================================

class Device(Base):
    """
    Edge device for distributed task execution.
    Represents desktop apps, servers, edge devices, or IoT devices.
    """
    __tablename__ = "devices"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Device identification
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)  # desktop, server, edge, iot
    hostname = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    tailscale_ip = Column(String(45), nullable=True)

    # Capabilities
    capabilities = Column(JSONColumn, nullable=True, default=list)  # ["terminal", "docker", "browser"]
    tags = Column(JSONColumn, nullable=True, default=list)  # ["production", "us-east-1"]

    # SSH keys
    ssh_public_key = Column(Text, nullable=True)
    ssh_private_key_encrypted = Column(Text, nullable=True)

    # Status
    status = Column(String(50), default="pending")  # pending, online, offline, error
    last_heartbeat = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    metadata_json = Column(JSONColumn, nullable=True, default={})  # Tailscale auth key, etc.

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="devices")
    executions = relationship("TaskExecution", back_populates="device", cascade="all, delete-orphan")
    attestations = relationship("DeviceAttestation", back_populates="device", cascade="all, delete-orphan")


class DeviceAttestation(Base):
    """
    Device attestation records for security verification.
    Supports TPM, secure boot, and hardware-based attestation.
    """
    __tablename__ = "device_attestations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Attestation type
    attestation_type = Column(String(50), nullable=False)  # initial, tpm, certificate

    # TPM attestation data
    certificate_data = Column(JSONColumn, nullable=True)
    tpm_version = Column(String(50), nullable=True)
    secure_boot_enabled = Column(Boolean, nullable=True)
    hardware_hash = Column(String(255), nullable=True)

    # Verification status
    verified = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    device = relationship("Device", back_populates="attestations")
    tenant = relationship("Tenant", backref="device_attestations")


class MobileDevice(Base):
    """Mobile device registration for push notifications and mobile access"""
    __tablename__ = "mobile_devices"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # Multi-tenant isolation
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)

    # Device information
    device_info = Column(JSONColumn, default=dict)  # {model, os_version, app_version, etc.}

    # Notification preferences
    notification_enabled = Column(Boolean, default=True)
    notification_preferences = Column(JSONColumn, default=dict)  # {agent_alerts, system_alerts, etc.}

    # Biometric authentication support
    biometric_public_key = Column(Text, nullable=True)  # Public key for signature verification
    biometric_enabled = Column(Boolean, default=False)  # Whether biometric auth is enabled
    last_biometric_auth = Column(DateTime(timezone=True), nullable=True)  # Last successful biometric auth
    
    # Ownership and Token
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    device_token = Column(String(512), nullable=True, unique=True)
    platform = Column(String(50), nullable=True) # ios, android, web
    status = Column(String(20), default="active") # active, inactive, revoked

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="mobile_devices")
    tenant = relationship("Tenant")


class UserTask(Base):
    """Standard user task for the web application"""
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    project_id = Column(String, ForeignKey("service_projects.id"), nullable=True, index=True)
    
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="todo")
    priority = Column(String(50), default="medium")
    due_date = Column(DateTime(timezone=True), nullable=True)
    
    tags = Column(JSONColumn, default=[])
    estimated_hours = Column(Float, default=0.0)
    actual_hours = Column(Float, default=0.0)
    color = Column(String(10), default="#3182CE")
    
    metadata_json = Column(JSONColumn, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def as_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "dueDate": self.due_date,
            "priority": self.priority,
            "status": self.status,
            "project": self.project_id,
            "tags": self.tags,
            "estimatedHours": self.estimated_hours,
            "actualHours": self.actual_hours,
            "color": self.color,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "metadata": self.metadata_json
        }

class Task(Base):
    """
    Distributed task for execution on edge devices.
    """
    __tablename__ = "distributed_tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Task definition
    type = Column(String(50), nullable=False)  # terminal, docker, browser, etc.
    data = Column(JSONColumn, nullable=False)  # Task-specific data

    # Priority and status
    priority = Column(String(20), default="medium")  # low, medium, high, urgent
    status = Column(String(50), default="pending")  # pending, scheduled, running, completed, failed, cancelled, retrying

    # Device assignment
    assigned_device_id = Column(String, ForeignKey("devices.id"), nullable=True, index=True)
    required_capabilities = Column(JSONColumn, nullable=True, default=list)

    # Timeout and retry
    timeout_seconds = Column(Integer, default=300)
    retry_count = Column(Integer, default=3)
    current_retry = Column(Integer, default=0)

    # Error tracking
    error_message = Column(Text, nullable=True)

    # Metadata
    metadata_json = Column(JSONColumn, nullable=True, default={})  # workflow_id, etc.

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="distributed_tasks")
    assigned_device = relationship("Device", backref="assigned_tasks")
    executions = relationship("TaskExecution", back_populates="task", cascade="all, delete-orphan")


class TaskExecution(Base):
    """
    Task execution record on a specific device.
    Tracks each attempt (including retries).
    """
    __tablename__ = "task_executions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey("distributed_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(String, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)

    # Execution status
    status = Column(String(50), default="running")  # running, completed, failed, cancelled

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Result
    result = Column(JSONColumn, nullable=True)  # Output, exit code, etc.

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="task_executions")
    task = relationship("Task", back_populates="executions")
    device = relationship("Device", back_populates="executions")


class Machine(Base):
    """
    Machine/Device model for remote desktop and VPN management.

    Used by Headscale/Guacamole integration for tracking machines
    that can be accessed remotely (private_ip required for VPN routing).
    """
    __tablename__ = "machines"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Machine identification
    name = Column(String(255), nullable=False)
    hostname = Column(String(255), nullable=True)
    private_ip = Column(String(45), nullable=True)  # IPv4 or IPv6
    public_ip = Column(String(45), nullable=True)
    mac_address = Column(String(17), nullable=True)  # Format: AA:BB:CC:DD:EE:FF

    # Machine metadata
    os_type = Column(String(50), nullable=True)  # windows, linux, macos
    os_version = Column(String(100), nullable=True)
    architecture = Column(String(50), nullable=True)  # x86_64, arm64

    # Status and configuration
    status = Column(String(50), default="offline")  # online, offline, maintenance
    machine_type = Column(String(50), default="physical")  # physical, vm, container

    # VPN integration (Headscale/Tailscale)
    vpn_ip = Column(String(45), nullable=True)  # Tailscale/Headscale IP
    headscale_name = Column(String(255), nullable=True)  # Headscale hostname

    # Remote desktop configuration
    guacamole_config = Column(JSONColumn, nullable=True)  # Guacamole connection params
    rdp_port = Column(Integer, nullable=True)
    vnc_port = Column(Integer, nullable=True)

    # Timestamps
    last_seen = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Metadata
    tags = Column(JSONColumn, nullable=True)  # Flexible tagging system
    metadata_json = Column(JSONColumn, nullable=True)  # Additional machine-specific data

    # Relationships
    tenant = relationship("Tenant", backref="machines")
    guacamole_sessions = relationship("GuacamoleSession", back_populates="machine", cascade="all, delete-orphan")

    # Unique constraints
    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', name='uq_machine_tenant_name'),
    )


class GuacamoleSession(Base):
    """
    Guacamole remote desktop session model.

    Tracks active remote desktop sessions with proper tenant isolation.
    References machines table for the target device.
    """
    __tablename__ = "guacamole_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    machine_id = Column(String, ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)

    # Session details
    status = Column(String(50), default="active", nullable=False)  # active, ended, error
    session_type = Column(String(50), default="rdp")  # rdp, vnc, ssh

    # Connection details
    connection_params = Column(JSONColumn, nullable=True)  # Protocol-specific settings

    # Fly.io ephemeral container details
    fly_machine_id = Column(String(255), nullable=True)  # Fly.io machine ID
    fly_app_name = Column(String(255), nullable=True)  # Fly.io app name

    # Session timing
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Session metadata
    client_ip = Column(String(45), nullable=True)  # Client IP address
    user_agent = Column(String(500), nullable=True)
    disconnect_reason = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Metadata
    metadata_json = Column(JSONColumn, nullable=True)

    # Relationships
    machine = relationship("Machine", backref="session")
    tenant = relationship("Tenant", backref="guacamole_sessions")


class DesktopApiKey(Base):
    """
    Desktop API Key model for secure desktop app authentication.

    Replaces insecure User ID-based authentication with proper API keys.
    Keys are hashed with SHA-256 before storage - plaintext is never stored.

    Security Features:
    - API keys are UUID v4 with sufficient entropy
    - Keys are hashed before storage (SHA-256)
    - Keys can be revoked without affecting user account
    - Optional expiration dates
    - Device tracking for audit trail
    """
    __tablename__ = "desktop_api_keys"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))  # String to match User.id
    key_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256 hash
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Device information
    device_id = Column(String(255), nullable=True)  # Optional device identifier
    device_name = Column(String(255), nullable=True)  # Human-readable device name

    # Timing
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Optional expiration
    last_used = Column(DateTime(timezone=True), nullable=True)  # Track last usage
    revoked_at = Column(DateTime(timezone=True), nullable=True)  # When key was revoked
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", backref="desktop_api_keys")
    tenant = relationship("Tenant", backref="desktop_api_keys")


class PublicApiKey(Base):
    """
    Public API Key model for external marketplace API authentication.

    Enables server-to-server authentication for external apps (e.g., atom-upstream).
    Keys are hashed with SHA-256 before storage - plaintext is never stored.

    Security Features:
    - API keys use format atom_pub_{UUIDv4} for easy identification
    - Keys are hashed before storage (SHA-256)
    - Tenant-scoped for multi-tenant isolation
    - Configurable scopes (read, read_write)
    - Rate limiting per key
    - Optional expiration dates
    - Usage tracking for analytics
    """
    __tablename__ = "public_api_keys"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    key_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256 hash
    key_prefix = Column(String(16), nullable=False)  # First 16 chars for identification

    # Owner
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Key properties
    name = Column(String(255), nullable=False)  # Human-readable name
    scope = Column(String(20), nullable=False, default="read")  # read, read_write
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Rate limiting
    rate_limit_per_minute = Column(Integer, default=60)  # Default: 60 requests/minute

    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used = Column(DateTime(timezone=True), nullable=True)
    last_rotated = Column(DateTime(timezone=True), nullable=True)

    # Usage tracking
    total_requests = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant", backref="public_api_keys")
    creator = relationship("User", backref="created_api_keys")


class PausedAgentTask(Base):
    """
    Paused Agent Task model for citation freshness tracking.

    Stores tasks that were paused due to stale policy citations with
    re-verification state tracking. Fully tenant-isolated.

    Attributes:
        - verification_status: pending, in_progress, verified, failed
        - resume_status: pending, ready, resumed, failed, cancelled
    """
    __tablename__ = "paused_agent_tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    # Agent task details
    agent_id = Column(String(255), nullable=False, index=True)
    task_id = Column(String(255), nullable=False, unique=True, index=True)
    goal = Column(Text, nullable=False)
    mode = Column(String(50), nullable=True)
    original_status = Column(String(50), nullable=True)

    # Pause reason with fact_id, fact_text, citation_path, verification_failed_at
    pause_reason = Column(JSONColumn, nullable=False)

    # Timing
    paused_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Re-verification tracking
    verification_status = Column(String(50), default="pending", nullable=False)  # pending, in_progress, verified, failed
    verification_attempts = Column(Integer, default=0, nullable=False)
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    verification_result = Column(JSONColumn, nullable=True)  # Store verification details

    # Resume tracking
    resume_status = Column(String(50), default="pending", nullable=False)  # pending, ready, resumed, failed, cancelled
    resumed_at = Column(DateTime(timezone=True), nullable=True)
    resume_result = Column(JSONColumn, nullable=True)  # Store resume details

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="paused_agent_tasks")
    workspace = relationship("Workspace", backref="paused_agent_tasks")

    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_paused_tasks_tenant_status', 'tenant_id', 'verification_status'),
        Index('idx_paused_tasks_workspace', 'workspace_id'),
        Index('idx_paused_tasks_created_at', 'created_at'),
        Index('idx_paused_tasks_resume_status', 'resume_status'),
    )


class CitationVerificationBatch(Base):
    """
    Citation Verification Batch model for bulk verification operations.

    Tracks bulk verification jobs triggered by admin (by document, domain, or all pending).

    Attributes:
        - batch_type: 'document', 'domain', 'all_pending'
        - status: pending, in_progress, completed, failed
    """
    __tablename__ = "citation_verification_batches"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    # Batch details
    batch_type = Column(String(50), nullable=False)  # 'document', 'domain', 'all_pending'
    source_identifier = Column(Text, nullable=True)  # Document path or domain name

    # Status tracking
    status = Column(String(50), default="pending", nullable=False)  # pending, in_progress, completed, failed

    # Results tracking
    total_facts = Column(Integer, default=0, nullable=False)
    verified_facts = Column(Integer, default=0, nullable=False)
    failed_facts = Column(Integer, default=0, nullable=False)

    # Trigger details
    triggered_by = Column(String(255), nullable=False)
    triggered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Detailed results
    results_json = Column(JSONColumn, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="citation_verification_batches")
    workspace = relationship("Workspace", backref="citation_verification_batches")

    # Indexes
    __table_args__ = (
        Index('idx_verification_batches_tenant_status', 'tenant_id', 'status'),
        Index('idx_verification_batches_workspace', 'workspace_id'),
        Index('idx_verification_batches_type', 'batch_type'),
    )


class ScheduledSocialPost(Base):
    """
    Scheduled social media posts for Twitter, LinkedIn, etc.
    
    Enables event-driven posting via Upstash QStash (not 24/7 worker).
    """
    __tablename__ = "scheduled_social_posts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True)

    # Post details
    platform = Column(String(20), nullable=False)  # 'twitter', 'linkedin', 'facebook', 'instagram'
    content = Column(Text, nullable=False)
    media_urls = Column(JSONColumn, nullable=True)  # Array of media URLs (images/videos)

    # Scheduling
    scheduled_time = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String(20), default="scheduled", nullable=False)  # 'scheduled', 'posted', 'failed', 'cancelled'

    # Execution details
    posted_at = Column(DateTime(timezone=True), nullable=True)
    platform_post_id = Column(String(255), nullable=True)  # ID from platform API
    platform_post_url = Column(Text, nullable=True)  # URL to posted content

    # Error tracking
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    last_retry_at = Column(DateTime(timezone=True), nullable=True)

    last_retry_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    metadata_json = Column(JSONColumn, nullable=True)  # Additional platform-specific data

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="scheduled_social_posts")
    workspace = relationship("Workspace", backref="scheduled_social_posts")

    # Indexes
    __table_args__ = (
        Index('idx_scheduled_posts_tenant_status', 'tenant_id', 'status'),
        Index('idx_scheduled_posts_scheduled_time', 'scheduled_time'),
        Index('idx_scheduled_posts_platform', 'platform'),
    )

    def __repr__(self):
        return f"<ScheduledSocialPost(id={self.id}, platform={self.platform}, status={self.status})>"


class SocialPostHistory(Base):
    """
    Audit trail for social media posts (both immediate and scheduled).
    Captures content, target platforms, and execution results.
    """
    __tablename__ = "social_post_history"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(String(255), ForeignKey('users.id'), nullable=False, index=True)
    
    # Post details
    content = Column(Text, nullable=False)
    platforms = Column(JSONColumn, nullable=False)  # List of target platforms
    media_urls = Column(JSONColumn, nullable=True)
    link_url = Column(Text, nullable=True)
    
    # Scheduling & Status
    scheduled_for = Column(DateTime(timezone=True), nullable=True, index=True)
    status = Column(String(20), default="pending", nullable=False)  # 'pending', 'scheduled', 'posting', 'posted', 'partial', 'failed', 'cancelled'
    job_id = Column(String(255), nullable=True)  # RQ Job ID
    
    # Execution results
    posted_at = Column(DateTime(timezone=True), nullable=True)
    platform_results = Column(JSONColumn, nullable=True)  # Dict of results per platform
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="social_post_histories")

    def __repr__(self):
        return f"<SocialPostHistory(post_id={self.post_id}, status={self.status})>"


class SocialMediaAudit(Base):
    """
    Audit log for social media interactions and agent-driven posting.
    Tracks governance compliance, human approvals, and platform execution results.
    """
    __tablename__ = "social_media_audit"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(255), ForeignKey('users.id'), nullable=False, index=True)
    agent_id = Column(String(255), ForeignKey('agent_registry.id'), nullable=True, index=True)
    agent_execution_id = Column(String(255), ForeignKey('agent_executions.id'), nullable=True, index=True)
    
    # Action Details
    platform = Column(String(50), nullable=False)
    action_type = Column(String(50), nullable=False)  # 'post', 'comment', 'delete'
    post_id = Column(String(255), nullable=True)  # Platform-specific post ID
    content = Column(Text, nullable=True)
    media_urls = Column(JSONColumn, nullable=True)
    link_url = Column(Text, nullable=True)
    
    # Status & Results
    success = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    platform_response = Column(JSONColumn, nullable=True)
    
    # Governance & Transparency
    agent_maturity = Column(String(50), nullable=True)
    governance_check_passed = Column(Boolean, default=True)
    required_approval = Column(Boolean, default=False)
    approval_granted = Column(Boolean, nullable=True)
    request_id = Column(String(255), nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", backref="social_media_audits")
    agent = relationship("AgentRegistry", backref="social_media_audits")
    execution = relationship("AgentExecution", backref="social_media_audits")

    def __repr__(self):
        return f"<SocialMediaAudit(id={self.id}, platform={self.platform}, success={self.success})>"


# ============================
# Social Layer Models
# ============================

class SocialPost(Base):
    """
    Social posts for agent-human communication - SOCIAL-01, SOCIAL-06

    Enables agents and humans to communicate via typed posts (status, insight, question, alert, task).
    All posts are tenant-isolated to prevent cross-tenant data leakage.
    """
    __tablename__ = "social_posts"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(255), ForeignKey('tenants.id'), nullable=False, index=True)
    author_type = Column(SQLEnum(AuthorType, values_callable=lambda obj: [e.value for e in obj]), nullable=False, index=True)
    author_id = Column(String(255), nullable=False, index=True)
    post_type = Column(SQLEnum(PostType, values_callable=lambda obj: [e.value for e in obj]), nullable=False, index=True)
    content = Column(Text, nullable=False)  # Post content (will be sanitized per SOCIAL-10)
    post_metadata = Column(JSONColumn, nullable=True)  # Additional structured data (renamed from metadata to avoid SQLAlchemy reserved word)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant", backref="social_posts")
    reactions = relationship("PostReaction", back_populates="post", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_social_posts_tenant_created', 'tenant_id', 'created_at'),
        Index('idx_social_posts_author', 'author_id', 'created_at'),
        Index('idx_social_posts_type', 'post_type'),
    )

    def __repr__(self):
        return f"<SocialPost(id={self.id}, type={self.post_type}, author={self.author_type}:{self.author_id})>"


class PostReaction(Base):
    """
    Emoji reactions to social posts - SOCIAL-07

    Users can add emoji reactions to posts for quick feedback.
    Unique constraint ensures one reaction per emoji per user per post (toggle behavior).
    """
    __tablename__ = "post_reactions"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id = Column(String(255), ForeignKey('social_posts.id'), nullable=False, index=True)
    user_id = Column(String(255), ForeignKey('users.id'), nullable=False, index=True)
    emoji = Column(String(50), nullable=False)  # The emoji reaction
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    post = relationship("SocialPost", back_populates="reactions")
    user = relationship("User", backref="post_reactions")

    # Unique constraint: one reaction per emoji per user per post
    __table_args__ = (
        UniqueConstraint('post_id', 'user_id', 'emoji', name='uq_post_reaction'),
        Index('idx_post_reactions_post', 'post_id'),
        Index('idx_post_reactions_user', 'user_id'),
    )

    def __repr__(self):
        return f"<PostReaction(id={self.id}, post_id={self.post_id}, emoji={self.emoji})>"


class DebugLog(Base):
    """Structured debug logs for distributed system debugging and AI agent insights"""
    __tablename__ = "debug_logs"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    node_type = Column(String(50), nullable=False)  # 'web', 'backend', 'desktop', 'worker', 'data_store'
    node_id = Column(String(255), nullable=False)  # Unique identifier for the node
    tenant_id = Column(String(255), nullable=True, index=True)
    agent_id = Column(String(255), nullable=True, index=True)
    execution_id = Column(String(255), nullable=True, index=True)
    session_id = Column(String(255), nullable=True)
    level = Column(String(20), nullable=False, index=True)  # 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL'
    category = Column(String(100), nullable=True, index=True)  # 'execution', 'memory', 'governance', 'llm', 'integration'
    event_type = Column(String(255), nullable=False, index=True)  # Specific event: 'agent_start', 'memory_recall', etc.
    message = Column(Text, nullable=False)
    data = Column(JSONColumn, nullable=True)  # Additional structured data
    duration_ms = Column(Float, nullable=True)  # Duration in milliseconds
    error = Column(JSONColumn, nullable=True)  # Error details: {type, message, stack_trace}
    correlations = Column(JSONColumn, nullable=True)  # Related IDs for cross-node tracing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Indexes
    __table_args__ = (
        Index('idx_debug_logs_timestamp', timestamp.desc()),
        Index('idx_debug_logs_tenant_execution', 'tenant_id', 'execution_id'),
        Index('idx_debug_logs_agent', 'agent_id'),
        Index('idx_debug_logs_level', 'level'),
        Index('idx_debug_logs_node_type', 'node_type'),
        Index('idx_debug_logs_event_type', 'event_type'),
        Index('idx_debug_logs_category', 'category'),
    )

    def __repr__(self):
        return f"<DebugLog(id={self.id}, level={self.level}, event_type={self.event_type}, node={self.node_type})>"


# ============================
# Supervision System Models
# ============================

class UserAvailability(Base):
    """Track user presence state for supervisor assignment"""
    __tablename__ = "user_availability"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(255), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    tenant_id = Column(String(255), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    status = Column(SQLEnum('online', 'away', 'offline', name='useravailabilitystatus'), nullable=False, default='offline')
    last_activity_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    manual_override = Column(Boolean, nullable=False, default=False)
    away_threshold_seconds = Column(Integer, nullable=False, default=300)  # 5 minutes
    offline_threshold_seconds = Column(Integer, nullable=False, default=900)  # 15 minutes
    active_sessions = Column(JSONColumn, nullable=True)
    override_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", backref="availability")
    tenant = relationship("Tenant", backref="user_availabilities")

    # Indexes
    __table_args__ = (
        Index('idx_user_availability_user_id', 'user_id', unique=True),
        Index('idx_user_availability_tenant_id', 'tenant_id'),
        Index('idx_user_availability_status', 'status'),
    )

    def __repr__(self):
        return f"<UserAvailability(id={self.id}, user_id={self.user_id}, status={self.status})>"





class AgentEvolutionTrace(Base):
    """Track agent evolution and learning across generations"""
    __tablename__ = "agent_evolution_traces"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(255), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    agent_id = Column(String(255), ForeignKey('agent_registry.id', ondelete='CASCADE'), nullable=False)
    
    # GEA Lineage
    parent_agent_id = Column(String(255), ForeignKey('agent_registry.id', ondelete='SET NULL'), nullable=True)
    parent_agent_ids = Column(JSONColumn, nullable=True)  # List of parent IDs for group evolution
    ancestor_count = Column(Integer, default=0)
    
    generation = Column(Integer, nullable=False, default=0)
    evolution_type = Column(SQLEnum('performance_based', 'novelty_based', 'combined', 'manual', name='evolutiontype'), nullable=False)
    
    # Scoring
    performance_score = Column(Float, nullable=True)
    novelty_score = Column(Float, nullable=True)
    combined_score = Column(Float, nullable=True)
    combined_selection_score = Column(Float, nullable=True)
    
    # Experience Pool Data
    tool_use_log = Column(JSONColumn, nullable=True)
    task_log = Column(Text, nullable=True)
    evolving_requirements = Column(Text, nullable=True)  # Final aggregated directives
    
    # Evolution Changes
    config_diff = Column(JSONColumn, nullable=True)  # Changes from parent config
    model_patch = Column(Text, nullable=True)   # Suggested code/prompt changes
    evolution_metadata = Column(JSONColumn, nullable=True)  # Additional evolution metadata
    
    # Evaluation
    benchmark_passed = Column(Boolean, default=False)
    benchmark_name = Column(String(255), nullable=True)
    benchmark_score = Column(Float, nullable=True)
    is_high_quality = Column(Boolean, default=True)
    quality_filter_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant", backref="agent_evolution_traces")
    agent = relationship("AgentRegistry", foreign_keys=[agent_id], backref="evolution_traces")
    parent_agent = relationship("AgentRegistry", foreign_keys=[parent_agent_id], backref="child_evolution_traces")

    # Indexes
    __table_args__ = (
        Index('idx_agent_evolution_traces_tenant_id', 'tenant_id'),
        Index('idx_agent_evolution_traces_agent_id', 'agent_id'),
        Index('idx_agent_evolution_traces_parent_agent_id', 'parent_agent_id'),
        Index('idx_agent_evolution_traces_generation', 'generation'),
        Index('idx_agent_evolution_traces_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<AgentEvolutionTrace(id={self.id}, agent_id={self.agent_id}, generation={self.generation})>"


class AgentProposal(Base):
    """Intern agent proposals awaiting approval"""
    __tablename__ = "agent_proposals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(255), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(String(255), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    agent_id = Column(String(255), ForeignKey('agent_registry.id', ondelete='CASCADE'), nullable=False)
    agent_name = Column(String(255), nullable=True)  # Denormalized for quick queries
    canvas_id = Column(String(255), nullable=True, index=True)
    session_id = Column(String(255), nullable=True, index=True)
    
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    
    proposal_type = Column(SQLEnum('action', 'workflow', 'analysis', name='proposaltype'), nullable=False)
    proposal_data = Column(JSONColumn, nullable=False)
    status = Column(SQLEnum('pending_approval', 'approved', 'rejected', 'cancelled', 'executed', 'execution_failed', name='proposalstatus'), nullable=False, default='pending_approval')
    
    reversible = Column(Boolean, default=True)
    
    approver_type = Column(SQLEnum('autonomous_agent', 'user', name='approvertype'), nullable=True)
    approver_id = Column(String(255), nullable=True)
    approved_by = Column(String(255), nullable=True)  # Legacy alias for approver_id
    approved_at = Column(DateTime(timezone=True), nullable=True)  # Legacy alias for reviewed_at
    approval_reason = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    risk_assessment = Column(Text, nullable=True)
    suggested_modifications = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    execution_id = Column(String(255), nullable=True)


    # Supervision Learning Integration (Phase: Supervision-Learning Integration)
    supervision_outcome_recorded = Column(Boolean, nullable=False, server_default='false', comment='Whether supervision outcome has been recorded to learning systems')
    supervision_metadata = Column(JSONColumn, nullable=True, comment='Extended supervision context (supervisor reasoning, risk assessment, etc.)')
    supervisor_confidence = Column(Float, nullable=True, comment='Supervisor confidence in their decision (0.0 to 1.0)')
    execution_success = Column(Boolean, nullable=True, comment='Did the execution succeed after approval?')
    execution_outcome_details = Column(Text, nullable=True, comment='Details if execution failed (error message, failure reason, etc.)')

    # Relationships
    tenant = relationship("Tenant", backref="agent_proposals")
    user = relationship("User", backref="agent_proposals")
    agent = relationship("AgentRegistry", foreign_keys=[agent_id], backref="agent_proposals")
    approver = relationship("AgentRegistry", primaryjoin="AgentProposal.approver_id == AgentRegistry.id", foreign_keys=[approver_id], backref="approved_proposals")

    # Indexes
    __table_args__ = (
        Index('idx_agent_proposals_tenant_id', 'tenant_id'),
        Index('idx_agent_proposals_agent_id', 'agent_id'),
        Index('idx_agent_proposals_canvas_id', 'canvas_id'),
        Index('idx_agent_proposals_session_id', 'session_id'),
        Index('idx_agent_proposals_status', 'status'),
        Index('idx_agent_proposals_approver', 'approver_type', 'approver_id'),
        {'extend_existing': True},
    )


    @property
    def proposed_action(self):
        """Helper to access action data from proposal_data"""
        if self.proposal_type == 'action':
            return self.proposal_data
        return {}

    @property
    def reasoning(self):
        """Helper to access reasoning from proposal_data"""
        return self.proposal_data.get('reasoning', '')

    def __repr__(self):
        return f"<AgentProposal(id={self.id}, agent_id={self.agent_id}, status={self.status})>"


class PackageWhitelist(Base):
    """Approved packages (Python, npm, yarn, pnpm) with maturity-level permissions"""
    __tablename__ = "package_whitelist"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    package_name = Column(String(255), nullable=False, index=True)
    package_type = Column(String(20), nullable=False, default="python", index=True)
    version_constraint = Column(String(100), nullable=False, default="*")
    maturity_level = Column(String(50), nullable=False, default="student", index=True)
    max_memory_mb = Column(Integer, default=512)
    network_access = Column(Boolean, default=False)
    requires_approval = Column(Boolean, default=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Indexes and constraints
    __table_args__ = (
        UniqueConstraint('package_name', 'package_type', name='uq_package_name_type'),
        Index('idx_package_whitelist_package_name', 'package_name'),
        Index('idx_package_whitelist_maturity_level', 'maturity_level'),
        Index('idx_package_whitelist_type_maturity', 'package_type', 'maturity_level'),
    )

    def __repr__(self):
        return f"<PackageWhitelist(package_name={self.package_name}, package_type={self.package_type}, maturity_level={self.maturity_level})>"


class PackageInstallation(Base):
    """Audit log for all package installations (Python, npm, yarn, pnpm)"""
    __tablename__ = "package_installations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(255), nullable=False, index=True)
    skill_id = Column(String(255), nullable=False, index=True)
    package_name = Column(String(255), nullable=False)
    package_type = Column(String(20), nullable=False, default="python")
    version = Column(String(100), nullable=False)
    maturity_level_at_install = Column(String(50), nullable=False)
    vulnerabilities_found = Column(Integer, default=0)
    vulnerability_details = Column(JSONColumn, nullable=True)
    installation_status = Column(String(50), nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    installed_at = Column(DateTime(timezone=True), server_default=func.now())
    installed_by = Column(String(255), nullable=True)
    uninstalled_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant", backref="package_installations")

    # Indexes
    __table_args__ = (
        Index('idx_package_installations_tenant_id', 'tenant_id'),
        Index('idx_package_installations_agent_id', 'agent_id'),
        Index('idx_package_installations_skill_id', 'skill_id'),
        Index('idx_package_installations_package_name', 'package_name'),
        Index('idx_package_installations_installation_status', 'installation_status'),
        Index('idx_package_installations_tenant_installed_at', 'tenant_id', 'installed_at'),
        Index('idx_package_installations_type', 'package_type'),
    )

    def __repr__(self):
        return f"<PackageInstallation(package_name={self.package_name}, package_type={self.package_type}, status={self.installation_status})>"


class OAuthClient(Base):
    """OAuth 2.0 client applications for user-delegated marketplace access"""
    __tablename__ = "oauth_clients"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = Column(String(64), nullable=False, unique=True, index=True)
    client_secret_hash = Column(String(128), nullable=True)  # Hashed, null for public clients

    # Client info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    homepage_url = Column(String(500), nullable=True)

    # OAuth configuration
    redirect_uris = Column(JSONColumn, nullable=False)  # List of allowed redirect URIs
    allowed_scopes = Column(JSONColumn, nullable=False, default=lambda: ["marketplace:read"])
    is_public_client = Column(Boolean, default=False)  # Public clients (no secret)

    # Owner (who registered this app)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False)  # Verified apps get higher rate limits

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant", backref="oauth_clients")
    creator = relationship("User", backref="registered_oauth_clients")
    tokens = relationship("OAuthToken", back_populates="client", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_oauth_clients_client_id', 'client_id'),
        Index('idx_oauth_clients_tenant_id', 'tenant_id'),
        Index('idx_oauth_clients_is_active', 'is_active'),
    )

    def __repr__(self):
        return f"<OAuthClient(client_id={self.client_id}, name={self.name}, is_public={self.is_public_client})>"


class OAuthToken(Base):
    """OAuth 2.0 tokens for user-delegated access"""
    __tablename__ = "oauth_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Foreign keys
    client_id = Column(String, ForeignKey("oauth_clients.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Tokens
    access_token_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256
    refresh_token_hash = Column(String(64), nullable=True, unique=True, index=True)  # SHA-256
    authorization_code = Column(String(128), nullable=True, unique=True, index=True)  # Single-use code

    # Token metadata
    scope = Column(String(500), nullable=False)  # Granted scopes
    token_type = Column(String(20), nullable=False, default="Bearer")

    # Expiration
    access_token_expires_at = Column(DateTime(timezone=True), nullable=False)
    refresh_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    code_expires_at = Column(DateTime(timezone=True), nullable=True)  # Auth code expiry

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Usage tracking
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    usage_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    client = relationship("OAuthClient", back_populates="tokens")
    user = relationship("User", backref="oauth_tokens")
    tenant = relationship("Tenant", backref="oauth_tokens")

    # Indexes
    __table_args__ = (
        Index('idx_oauth_tokens_client_id', 'client_id'),
        Index('idx_oauth_tokens_user_id', 'user_id'),
        Index('idx_oauth_tokens_tenant_id', 'tenant_id'),
        Index('idx_oauth_tokens_access_token_hash', 'access_token_hash'),
        Index('idx_oauth_tokens_refresh_token_hash', 'refresh_token_hash'),
        Index('idx_oauth_tokens_authorization_code', 'authorization_code'),
        Index('idx_oauth_tokens_user_active', 'user_id', 'is_active'),
        Index('idx_oauth_tokens_is_active', 'is_active'),
    )

    def __repr__(self):
        return f"<OAuthToken(id={self.id}, client_id={self.client_id}, user_id={self.user_id}, is_active={self.is_active})>"


# ============================================================================
# JWT Token Management Models
# ============================================================================

class ActiveToken(Base):
    """
    Active JWT tokens for user authentication.

    Tracks currently active JWT tokens to support token management,
    revocation, and cleanup operations.
    """
    __tablename__ = "active_tokens"

    # JWT ID (jti) - unique identifier for the token
    jti = Column(String, primary_key=True, nullable=False)

    # Foreign key to user
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Token content (hashed for security)
    token = Column(Text, nullable=False)

    # Expiration timestamp
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # Creation timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Token metadata
    token_type = Column(String(20), default="access")  # access, refresh, etc.

    # Indexes for common queries
    __table_args__ = (
        Index('idx_active_tokens_user_id', 'user_id'),
        Index('idx_active_tokens_expires_at', 'expires_at'),
        Index('idx_active_tokens_user_expires', 'user_id', 'expires_at'),
    )

    def __repr__(self):
        return f"<ActiveToken(jti={self.jti}, user_id={self.user_id}, expires_at={self.expires_at})>"


class RevokedToken(Base):
    """
    Revoked JWT tokens for blacklist functionality.

    Tracks revoked tokens to prevent their reuse even if they haven't expired yet.
    Supports token revocation due to logout, password changes, or security incidents.
    """
    __tablename__ = "revoked_tokens"

    # JWT ID (jti) - unique identifier for the token
    jti = Column(String, primary_key=True, nullable=False)

    # Foreign key to user
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # When the token was revoked
    revoked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Original expiration (for cleanup)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # Reason for revocation
    reason = Column(String(100), nullable=True)  # logout, password_change, security_incident, etc.

    # Token metadata
    token_type = Column(String(20), default="access")  # access, refresh, etc.

    # Indexes for common queries
    __table_args__ = (
        Index('idx_revoked_tokens_user_id', 'user_id'),
        Index('idx_revoked_tokens_expires_at', 'expires_at'),
        Index('idx_revoked_tokens_user_expires', 'user_id', 'expires_at'),
    )

    def __repr__(self):
        return f"<RevokedToken(jti={self.jti}, user_id={self.user_id}, revoked_at={self.revoked_at})>"


# ============================================================================
# SDLC Agent Models
# ============================================================================

class SDLCAgentConfig(Base):
    """
    SDLC Agent Configuration

    Per-tenant, per-agent-type configuration for SDLC agents.
    Stores enabled status and type-specific configuration.
    """
    __tablename__ = "sdlc_agent_configs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_type = Column(String(20), nullable=False)  # planner, coder, tester, reviewer, deployer
    enabled = Column(Boolean, default=False, nullable=False)
    config = Column(JSONColumn, default={}, nullable=True)  # Type-specific configuration
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant", backref="sdlc_agent_configs")

    # Constraints and Indexes
    __table_args__ = (
        UniqueConstraint('tenant_id', 'agent_type', name='uq_sdlc_agent_configs_tenant_agent_type'),
        Index('idx_sdlc_agent_configs_tenant_id', 'tenant_id'),
    )

    def __repr__(self):
        return f"<SDLCAgentConfig(id={self.id}, tenant_id={self.tenant_id}, agent_type={self.agent_type}, enabled={self.enabled})>"


class SDLCAuditLog(Base):
    """
    SDLC Agent Audit Log

    Tracks all SDLC agent actions for compliance, debugging, and audit purposes.
    Links to agent_episodes for full execution context.
    """
    __tablename__ = "sdlc_audit_log"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(255), nullable=False, index=True)
    agent_type = Column(String(20), nullable=False)  # planner, coder, tester, reviewer, deployer
    action = Column(String(100), nullable=False)  # Action performed
    input_summary = Column(Text, nullable=True)  # Summary of input
    outcome = Column(Text, nullable=True)  # Result or output
    success = Column(Boolean, nullable=True)  # Whether action succeeded
    approval_required = Column(Boolean, nullable=True)  # Whether approval was needed
    approved_by = Column(String(255), nullable=True)  # Approver identifier
    approved_at = Column(DateTime(timezone=True), nullable=True)  # Approval timestamp
    constitutional_violations = Column(JSONColumn, nullable=True)  # List of violations if any
    episode_id = Column(String, ForeignKey("agent_episodes.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    tenant = relationship("Tenant", backref="sdlc_audit_logs")
    episode = relationship("AgentEpisode", backref="sdlc_audit_logs")

    # Indexes
    __table_args__ = (
        Index('idx_sdlc_audit_log_tenant_id', 'tenant_id'),
        Index('idx_sdlc_audit_log_agent_id', 'agent_id'),
        Index('idx_sdlc_audit_log_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<SDLCAuditLog(id={self.id}, tenant_id={self.tenant_id}, agent_type={self.agent_type}, action={self.action}, success={self.success})>"


class SDLCProject(Base):
    """
    SDLC Project Tracking

    Tracks software projects that SDLC agents work on.
    Links repository URLs and project metadata.
    """
    __tablename__ = "sdlc_projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    repository_url = Column(String(500), nullable=True)
    status = Column(String(50), default="active", nullable=False)  # active, archived, deleted
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant", backref="sdlc_projects")

    # Indexes
    __table_args__ = (
        Index('idx_sdlc_projects_tenant_id', 'tenant_id'),
    )

    def __repr__(self):
        return f"<SDLCProject(id={self.id}, tenant_id={self.tenant_id}, name={self.name}, status={self.status})>"


class PullRequestReview(Base):
    """
    Pull Request Review Tracking

    Tracks code reviews performed by Review Agent on pull requests.
    Stores static analysis results, LLM feedback, and approval decisions.
    """
    __tablename__ = "sdlc_pull_request_reviews"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(255), nullable=False, index=True)
    project_id = Column(String, ForeignKey("sdlc_projects.id", ondelete="CASCADE"), nullable=True, index=True)
    repository_url = Column(String(500), nullable=False)
    pr_number = Column(Integer, nullable=False)
    pr_title = Column(String(500), nullable=True)
    pr_author = Column(String(255), nullable=True)
    branch_name = Column(String(255), nullable=False)
    target_branch = Column(String(255), default="main", nullable=False)
    diff_text = Column(Text, nullable=True)
    static_analysis_results = Column(JSONColumn, nullable=True)
    llm_review_results = Column(JSONColumn, nullable=True)
    overall_assessment = Column(String(50), nullable=False)  # 'approve', 'request_changes', 'comment'
    critical_issues = Column(Integer, default=0, nullable=False)
    high_issues = Column(Integer, default=0, nullable=False)
    medium_issues = Column(Integer, default=0, nullable=False)
    low_issues = Column(Integer, default=0, nullable=False)
    quality_score = Column(Float, default=0.0, nullable=False)
    approval_required = Column(Boolean, default=False, nullable=False)
    review_posted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant", backref="pull_request_reviews")
    project = relationship("SDLCProject", backref="pull_request_reviews")

    # Indexes and constraints
    __table_args__ = (
        Index('idx_pr_reviews_tenant_id', 'tenant_id'),
        Index('idx_pr_reviews_project_id', 'project_id'),
        UniqueConstraint('tenant_id', 'repository_url', 'pr_number', name='uq_pr_reviews_tenant_repo_pr'),
    )

    def __repr__(self):
        return f"<PullRequestReview(id={self.id}, tenant_id={self.tenant_id}, pr_number={self.pr_number}, assessment={self.overall_assessment})>"


class DeploymentRecord(Base):
    """
    Deployment Record Tracking

    Tracks deployments performed by Deployment Agent.
    Records deployment type, status, health checks, and rollback events.
    """
    __tablename__ = "sdlc_deployments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(255), nullable=False, index=True)
    project_id = Column(String, ForeignKey("sdlc_projects.id", ondelete="CASCADE"), nullable=True, index=True)
    environment = Column(String(20), nullable=False)  # 'staging', 'production'
    deployment_type = Column(String(20), nullable=False)  # 'blue_green', 'rolling', 'canary'
    image_tag = Column(String(100), nullable=True)
    git_commit_hash = Column(String(40), nullable=True)
    git_branch = Column(String(255), nullable=True)
    deployment_status = Column(String(50), nullable=False)  # 'pending', 'success', 'failed', 'rolled_back'
    health_check_status = Column(String(50), nullable=True)
    deployment_started_at = Column(DateTime(timezone=True), nullable=False)
    deployment_completed_at = Column(DateTime(timezone=True), nullable=True)
    rollback_triggered_at = Column(DateTime(timezone=True), nullable=True)
    rollback_reason = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    deployment_metrics = Column(JSONColumn, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant", backref="deployment_records")
    project = relationship("SDLCProject", backref="deployment_records")

    # Indexes
    __table_args__ = (
        Index('idx_deployments_tenant_id', 'tenant_id'),
        Index('idx_deployments_status', 'deployment_status'),
    )

    def __repr__(self):
        return f"<DeploymentRecord(id={self.id}, tenant_id={self.tenant_id}, environment={self.environment}, status={self.deployment_status})>"


class DeploymentHealthCheck(Base):
    """
    Deployment Health Check Tracking

    Tracks health check results for deployments.
    Records HTTP status codes, response times, and error messages.
    """
    __tablename__ = "sdlc_deployment_health_checks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    deployment_id = Column(String, ForeignKey("sdlc_deployments.id", ondelete="CASCADE"), nullable=False, index=True)
    check_timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    health_status = Column(String(50), nullable=False)  # 'healthy', 'unhealthy'
    http_status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    endpoint_url = Column(String(500), nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_deployment_health_checks_deployment_id', 'deployment_id'),
    )

    def __repr__(self):
        return f"<DeploymentHealthCheck(id={self.id}, deployment_id={self.deployment_id}, status={self.health_status})>"


class CodeQualityMetrics(Base):
    """
    Code Quality Metrics Tracking

    Tracks quality metrics over time for projects.
    Records technical debt, code smells, bugs, vulnerabilities, and coverage.
    """
    __tablename__ = "sdlc_code_quality_metrics"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String, ForeignKey("sdlc_projects.id", ondelete="CASCADE"), nullable=True, index=True)
    scan_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    commit_hash = Column(String(40), nullable=True)
    files_scanned = Column(Integer, default=0, nullable=False)
    lines_of_code = Column(Integer, default=0, nullable=False)
    technical_debt_ratio = Column(Numeric(5, 2), default=0.0, nullable=False)
    code_smells = Column(Integer, default=0, nullable=False)
    bugs = Column(Integer, default=0, nullable=False)
    vulnerabilities = Column(Integer, default=0, nullable=False)
    security_hotspots = Column(Integer, default=0, nullable=False)
    coverage = Column(Numeric(5, 2), nullable=True)
    duplication_percentage = Column(Numeric(5, 2), default=0.0, nullable=False)
    cyclomatic_complexity = Column(Numeric(5, 2), default=0.0, nullable=False)
    quality_gate_status = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant", backref="code_quality_metrics")
    project = relationship("SDLCProject", backref="code_quality_metrics")

    # Indexes and constraints
    __table_args__ = (
        Index('idx_quality_metrics_tenant_id', 'tenant_id'),
        Index('idx_quality_metrics_project_id', 'project_id'),
        UniqueConstraint('tenant_id', 'project_id', 'commit_hash', name='uq_quality_metrics_tenant_project_commit'),
    )

    def __repr__(self):
        return f"<CodeQualityMetrics(id={self.id}, tenant_id={self.tenant_id}, project_id={self.project_id}, quality_gate={self.quality_gate_status})>"


class HostingProject(Base):
    """
    Hosting Project Tracking

    Tracks Fly.io applications provisioned for tenant projects.
    Records app details, URLs, status, and plan tier.
    """
    __tablename__ = "hosting_projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(100), nullable=False)  # Internal project reference
    project_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    app_name = Column(String(100), nullable=False, unique=True)  # Fly.io app name
    app_url = Column(String(500), nullable=False)  # https://{app_name}.fly.dev
    region = Column(String(20), nullable=False, default="iad")
    status = Column(String(50), nullable=False, default="provisioning")  # 'provisioning', 'running', 'stopped', 'failed', 'deleted'
    deployment_type = Column(String(20), nullable=False, default="internal")  # 'internal', 'external'
    client_project = Column(Boolean, nullable=False, default=False)  # True if external client project
    plan_tier = Column(String(20), nullable=False, default="free")  # 'free', 'solo', 'team', 'enterprise'
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant", backref="hosting_projects")
    resources = relationship("HostingResource", backref="project", cascade="all, delete-orphan")
    deployments = relationship("HostingDeployment", backref="project", cascade="all, delete-orphan")

    # Indexes and constraints
    __table_args__ = (
        Index('idx_hosting_projects_tenant_id', 'tenant_id'),
        Index('idx_hosting_projects_app_name', 'app_name'),
        Index('idx_hosting_projects_status', 'status'),
        UniqueConstraint('tenant_id', 'project_id', name='uq_hosting_projects_tenant_project'),
    )

    def __repr__(self):
        return f"<HostingProject(id={self.id}, tenant_id={self.tenant_id}, project_id={self.project_id}, app_name={self.app_name}, status={self.status})>"


class HostingResource(Base):
    """
    Hosting Resource Tracking

    Tracks resource allocations for hosting projects.
    Records CPU, memory, storage with cost per hour.
    """
    __tablename__ = "hosting_resources"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hosting_project_id = Column(String, ForeignKey("hosting_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_type = Column(String(20), nullable=False)  # 'cpu', 'memory', 'storage'
    resource_value = Column(Numeric(10, 2), nullable=False)  # Amount allocated
    resource_unit = Column(String(20), nullable=False)  # 'cores', 'GB', 'GiB'
    cost_per_hour = Column(Numeric(10, 6), nullable=False)  # Cost per hour in USD
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Indexes
    __table_args__ = (
        Index('idx_hosting_resources_hosting_project_id', 'hosting_project_id'),
    )

    def __repr__(self):
        return f"<HostingResource(id={self.id}, hosting_project_id={self.hosting_project_id}, resource_type={self.resource_type}, value={self.resource_value} {self.resource_unit})>"


class HostingDeployment(Base):
    """
    Hosting Deployment Tracking

    Tracks Docker image deployments to hosted apps.
    Records deployment IDs, image tags, git commits, and status.
    """
    __tablename__ = "hosting_deployments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hosting_project_id = Column(String, ForeignKey("hosting_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    deployment_id = Column(String(100), nullable=False)  # Fly.io deployment ID
    image_tag = Column(String(100), nullable=False)
    git_commit_hash = Column(String(40), nullable=True)
    deployment_status = Column(String(50), nullable=False)  # 'pending', 'success', 'failed'
    deployed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Indexes
    __table_args__ = (
        Index('idx_hosting_deployments_hosting_project_id', 'hosting_project_id'),
        Index('idx_hosting_deployments_deployment_id', 'deployment_id'),
    )

    def __repr__(self):
        return f"<HostingDeployment(id={self.id}, hosting_project_id={self.hosting_project_id}, deployment_id={self.deployment_id}, status={self.deployment_status})>"


class ACUConsumption(Base):
    """
    ACU (Agent Compute Units) Consumption Tracking

    Tracks resource consumption for hosted applications on an hourly basis.
    Records CPU, memory, storage usage and calculates ACU using industry-standard formula.
    """
    __tablename__ = "acu_consumption"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String, ForeignKey("hosting_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    app_name = Column(String(100), nullable=False)
    consumption_date = Column(Date, nullable=False, index=True)
    hour = Column(Integer, nullable=False)  # 0-23 for hourly records

    # Resource metrics
    cpu_cores = Column(Numeric(5, 2), nullable=False)
    memory_gb = Column(Numeric(10, 2), nullable=False)
    storage_gib = Column(Numeric(10, 2), nullable=False)
    runtime_seconds = Column(Integer, nullable=False)

    # ACU calculation
    acu_consumed = Column(Numeric(15, 2), nullable=False)
    acu_cost = Column(Numeric(10, 4), nullable=False)

    # Raw metrics from Fly.io
    raw_metrics = Column(JSONColumn, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant", backref="acu_consumption")
    project = relationship("HostingProject", backref="acu_consumption")

    # Indexes and constraints
    __table_args__ = (
        Index('idx_acu_consumption_tenant_id', 'tenant_id'),
        Index('idx_acu_consumption_project_id', 'project_id'),
        Index('idx_acu_consumption_date', 'consumption_date'),
        UniqueConstraint('project_id', 'consumption_date', 'hour', name='uq_acu_consumption_project_date_hour'),
    )

    def __repr__(self):
        return f"<ACUConsumption(id={self.id}, tenant_id={self.tenant_id}, project_id={self.project_id}, acu={self.acu_consumed})>"


class CustomDomain(Base):
    """
    Custom Domain

    Custom domain configuration for hosted apps with SSL certificate tracking.
    Integrates with Fly.io certificates and Let's Encrypt.
    """
    __tablename__ = "custom_domains"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String, ForeignKey("hosting_projects.id", ondelete="CASCADE"), nullable=False, index=True)

    # Domain configuration
    domain_name = Column(String(255), nullable=False)  # e.g., "app.example.com" or "*.example.com"
    is_primary = Column(Boolean, nullable=False, default=False)  # Primary domain for app
    is_wildcard = Column(Boolean, nullable=False, default=False)  # Wildcard certificate

    # SSL certificate tracking
    ssl_enabled = Column(Boolean, nullable=False, default=True)  # SSL certificate active
    ssl_status = Column(String(20), nullable=False, default="pending")  # 'pending', 'validating', 'issued', 'failed', 'expired'
    ssl_expires_at = Column(DateTime(timezone=True), nullable=True)  # Certificate expiration

    # DNS validation
    dns_target = Column(String(255), nullable=True)  # CNAME target (e.g., "app-name.fly.dev")
    dns_verified = Column(Boolean, nullable=False, default=False)  # DNS record verified
    dns_verified_at = Column(DateTime(timezone=True), nullable=True)  # Verification timestamp

    # Fly.io certificate reference
    certificate_arn = Column(String(500), nullable=True)  # Fly.io certificate ARN
    validation_errors = Column(Text, nullable=True)  # Certificate failure reasons

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant", backref="custom_domains")
    project = relationship("HostingProject", backref="custom_domains")
    validations = relationship("CertificateValidation", back_populates="domain", cascade="all, delete-orphan")

    # Indexes and constraints
    __table_args__ = (
        Index('idx_custom_domains_tenant_id', 'tenant_id'),
        Index('idx_custom_domains_project_id', 'project_id'),
        Index('idx_custom_domains_domain_name', 'domain_name'),
        UniqueConstraint('project_id', 'domain_name', name='uq_custom_domains_project_domain'),
    )

    def __repr__(self):
        return f"<CustomDomain(id={self.id}, domain_name={self.domain_name}, ssl_status={self.ssl_status})>"


class CertificateValidation(Base):
    """
    Certificate Validation

    Audit trail for SSL certificate validation attempts.
    Tracks DNS, HTTP, and TLS-SNI validation challenges.
    """
    __tablename__ = "certificate_validations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    domain_id = Column(String, ForeignKey("custom_domains.id", ondelete="CASCADE"), nullable=False, index=True)

    # Validation details
    validation_type = Column(String(20), nullable=False)  # 'http', 'dns', 'tls-sni'
    status = Column(String(20), nullable=False)  # 'pending', 'success', 'failed'
    validated_at = Column(DateTime(timezone=True), nullable=True)  # Validation timestamp
    failure_reason = Column(Text, nullable=True)  # Failure reason if status='failed'

    # Retry tracking
    retry_count = Column(Integer, nullable=False, default=0)  # Number of validation attempts

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    domain = relationship("CustomDomain", back_populates="validations")

    # Indexes
    __table_args__ = (
        Index('idx_certificate_validations_domain_id', 'domain_id'),
        Index('idx_certificate_validations_status', 'status'),
    )

    def __repr__(self):
        return f"<CertificateValidation(id={self.id}, type={self.validation_type}, status={self.status})>"


# ============================================================================
# Smart Home Integration Models
# ============================================================================

class SmartHomeDevice(Base):
    """
    Smart Home Device

    Registry of all smart home devices across multiple hubs (SmartThings, Hue, HomeKit, Nest).
    Supports device discovery, state management, and energy monitoring.
    """
    __tablename__ = "smarthome_devices"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True)

    # Device identification
    device_id = Column(String(255), nullable=False)  # External device ID from hub
    device_name = Column(String(255), nullable=False)
    device_type = Column(String(100), nullable=False)  # 'light', 'thermostat', 'lock', 'switch', 'sensor'
    hub_type = Column(String(50), nullable=False)  # 'smartthings', 'hue', 'homekit', 'nest'

    # Device location
    room = Column(String(100))
    floor = Column(String(50))

    # Device capabilities (JSON array)
    # ['on_off', 'brightness', 'color', 'color_temperature', 'thermostat', 'lock', 'motion', 'temperature']
    capabilities = Column(JSONColumn, default=list)

    # Current device state (dynamic properties)
    state = Column(JSONColumn, default=dict)

    # Device metadata
    manufacturer = Column(String(255))
    model = Column(String(255))
    firmware_version = Column(String(100))
    protocol = Column(String(50))  # 'zigbee', 'zwave', 'wifi', 'matter', 'ble', 'homekit'

    # Connection status
    is_online = Column(Boolean, nullable=False, default=True)
    last_seen = Column(DateTime(timezone=True))

    # Energy monitoring
    power_consumption_watts = Column(Numeric(8, 2))  # Current power draw in watts
    is_energy_monitoring = Column(Boolean, nullable=False, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant", backref="smarthome_devices")
    workspace = relationship("Workspace", backref="smarthome_devices")

    # Indexes and constraints
    __table_args__ = (
        Index('idx_smarthome_devices_tenant_id', 'tenant_id'),
        Index('idx_smarthome_devices_workspace_id', 'workspace_id'),
        Index('idx_smarthome_devices_device_type', 'device_type'),
        Index('idx_smarthome_devices_hub_type', 'hub_type'),
        Index('idx_smarthome_devices_room', 'room'),
        Index('idx_smarthome_devices_is_online', 'is_online'),
        UniqueConstraint('tenant_id', 'device_id', name='uq_smarthome_devices_tenant_device'),
    )

    def __repr__(self):
        return f"<SmartHomeDevice(id={self.id}, device_id={self.device_id}, name={self.device_name}, type={self.device_type})>"


class SmartHomeAutomationRule(Base):
    """
    Smart Home Automation Rule (TAP Pattern)

    TAP (Trigger-Action Programming) automation rules with optional conditions.
    Trigger -> Condition(s) -> Action(s) pattern from Home Assistant.
    """
    __tablename__ = "smarthome_automation_rules"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True)

    # Rule identification
    rule_name = Column(String(255), nullable=False)
    description = Column(Text)

    # TAP Pattern: Trigger -> Condition(s) -> Action(s)
    # Trigger: What initiates the rule
    trigger_type = Column(String(50), nullable=False)  # 'state', 'time', 'event', 'geolocation'
    trigger_config = Column(JSONColumn, nullable=False)  # Trigger-specific configuration

    # Conditions: Optional filters (AND/OR/NOT logic)
    conditions = Column(JSONColumn, default=list)  # Array of condition objects

    # Actions: What to execute when rule fires
    actions = Column(JSONColumn, nullable=False)  # Array of action objects

    # Rule settings
    is_enabled = Column(Boolean, nullable=False, default=True)
    cooldown_seconds = Column(Integer, nullable=False, default=0)  # Prevent rapid re-triggering

    # Execution tracking
    last_triggered_at = Column(DateTime(timezone=True))
    trigger_count = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant", backref="smarthome_automation_rules")
    workspace = relationship("Workspace", backref="smarthome_automation_rules")

    # Indexes
    __table_args__ = (
        Index('idx_smarthome_automation_rules_tenant_id', 'tenant_id'),
        Index('idx_smarthome_automation_rules_workspace_id', 'workspace_id'),
        Index('idx_smarthome_automation_rules_is_enabled', 'is_enabled'),
        Index('idx_smarthome_automation_rules_trigger_type', 'trigger_type'),
    )

    def __repr__(self):
        return f"<SmartHomeAutomationRule(id={self.id}, rule_name={self.rule_name}, trigger={self.trigger_type})>"


class SmartHomeScene(Base):
    """
    Smart Home Scene

    Reusable multi-device states for quick activation (e.g., "Movie Night", "Good Morning", "Away").
    """
    __tablename__ = "smarthome_scenes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True)

    # Scene identification
    scene_name = Column(String(255), nullable=False)
    description = Column(Text)
    icon = Column(String(100))  # Icon name for UI

    # Scene devices (what to set when scene activates)
    # [{device_id, state, delay_seconds}]
    scene_devices = Column(JSONColumn, nullable=False)

    # Scene settings
    is_favorite = Column(Boolean, nullable=False, default=False)
    activation_count = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant", backref="smarthome_scenes")
    workspace = relationship("Workspace", backref="smarthome_scenes")

    # Indexes
    __table_args__ = (
        Index('idx_smarthome_scenes_tenant_id', 'tenant_id'),
        Index('idx_smarthome_scenes_workspace_id', 'workspace_id'),
        Index('idx_smarthome_scenes_is_favorite', 'is_favorite'),
    )

    def __repr__(self):
        return f"<SmartHomeScene(id={self.id}, scene_name={self.scene_name}, devices={len(self.scene_devices)})>"


class SmartHomeSchedule(Base):
    """
    Smart Home Schedule

    Time-based automation schedules using cron expressions.
    Triggers scenes, devices, or automation rules at specific times.
    """
    __tablename__ = "smarthome_schedules"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True)

    # Schedule identification
    schedule_name = Column(String(255), nullable=False)
    description = Column(Text)

    # Cron expression (when to trigger)
    cron_expression = Column(String(100), nullable=False)  # Standard cron: '* * * * *'

    # What to execute
    target_type = Column(String(50), nullable=False)  # 'scene', 'device', 'automation_rule'
    target_id = Column(String, nullable=False)  # ID of scene/device/rule
    target_config = Column(JSONColumn)  # Configuration for target execution

    # Schedule settings
    is_enabled = Column(Boolean, nullable=False, default=True)
    timezone = Column(String(50), nullable=False, default='UTC')

    # Next run tracking
    next_run_at = Column(DateTime(timezone=True))
    last_run_at = Column(DateTime(timezone=True))
    run_count = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant", backref="smarthome_schedules")
    workspace = relationship("Workspace", backref="smarthome_schedules")

    # Indexes
    __table_args__ = (
        Index('idx_smarthome_schedules_tenant_id', 'tenant_id'),
        Index('idx_smarthome_schedules_workspace_id', 'workspace_id'),
        Index('idx_smarthome_schedules_is_enabled', 'is_enabled'),
        Index('idx_smarthome_schedules_next_run_at', 'next_run_at'),
    )

    def __repr__(self):
        return f"<SmartHomeSchedule(id={self.id}, schedule_name={self.schedule_name}, cron={self.cron_expression})>"


class SmartHomeEnergyUsage(Base):
    """
    Smart Home Energy Usage

    Energy consumption tracking for smart home devices with optimization suggestions.
    Aggregates usage by period (hourly, daily, weekly, monthly).
    """
    __tablename__ = "smarthome_energy_usage"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True)

    # Device identification
    device_id = Column(String, nullable=False, index=True)

    # Usage period
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    period_type = Column(String(20), nullable=False)  # 'hourly', 'daily', 'weekly', 'monthly'

    # Energy consumption
    energy_kwh = Column(Numeric(10, 3), nullable=False)  # Kilowatt-hours consumed
    cost_estimate = Column(Numeric(10, 2))  # Estimated cost in local currency

    # Aggregated data
    avg_power_watts = Column(Numeric(8, 2))
    peak_power_watts = Column(Numeric(8, 2))

    # Optimization suggestions
    optimization_suggestions = Column(JSONColumn)  # Suggestions to reduce consumption

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant", backref="smarthome_energy_usage")
    workspace = relationship("Workspace", backref="smarthome_energy_usage")

    # Indexes and constraints
    __table_args__ = (
        Index('idx_smarthome_energy_usage_tenant_id', 'tenant_id'),
        Index('idx_smarthome_energy_usage_workspace_id', 'workspace_id'),
        Index('idx_smarthome_energy_usage_device_id', 'device_id'),
        Index('idx_smarthome_energy_usage_period_start', 'period_start'),
        Index('idx_smarthome_energy_usage_period_end', 'period_end'),
        Index('idx_smarthome_energy_usage_period_type', 'period_type'),
        UniqueConstraint('tenant_id', 'device_id', 'period_start', 'period_type', name='uq_smarthome_energy_device_period'),
    )

    def __repr__(self):
        return f"<SmartHomeEnergyUsage(id={self.id}, device_id={self.device_id}, period={self.period_type}, kwh={self.energy_kwh})>"



class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=True)
    metadata_json = Column(JSONColumn, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    message_count = Column(Integer, default=0)



class ShellSession(Base):
    """
    Host shell command execution session with governance controls.

    Purpose:
    - Audit trail for all shell commands executed by agents
    - Security tracking for host filesystem access
    - Timeout enforcement and command validation

    Governance:
    - AUTONOMOUS agents only (maturity_level check)
    - Command whitelist validation (ls, pwd, cat, grep, git, etc.)
    - 5-minute maximum execution timeout
    - Working directory restrictions
    """
    __tablename__ = "shell_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Who
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    maturity_level = Column(String, nullable=False)  # AUTONOMOUS required

    # What
    command = Column(Text, nullable=False)  # Shell command executed
    command_whitelist_valid = Column(Boolean, nullable=False)  # True if in whitelist
    working_directory = Column(String, nullable=True)  # Host directory

    # Result
    exit_code = Column(Integer, nullable=True)  # 0 = success
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    timed_out = Column(Boolean, default=False)  # True if killed by timeout

    # When
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)  # Execution duration

    # Governance
    approved_by = Column(String, ForeignKey("users.id"), nullable=True)  # NULL = auto-approved for AUTONOMOUS
    approval_required = Column(Boolean, default=False)  # True for lower maturity

    # Relationships
    agent = relationship("AgentRegistry", backref="shell_sessions")
    user = relationship("User", foreign_keys=[user_id], backref="shell_sessions_initiated")
    approver = relationship("User", foreign_keys=[approved_by])


class PackageRegistry(Base):
    """
    Package registry for Python and npm packages with maturity-based governance.

    Purpose:
    - Track Python and npm packages available for agent skill execution
    - Enforce maturity-based access controls (STUDENT blocked, INTERN+ approved)
    - Maintain security ban list for malicious packages
    - Audit trail for package approvals and usage

    Governance:
    - STUDENT agents: Blocked from all packages (Python and npm)
    - INTERN agents: Require explicit approval for each package version
    - SUPERVISED agents: Allowed if min_maturity <= SUPERVISED
    - AUTONOMOUS agents: Allowed if min_maturity <= AUTONOMOUS
    - Banned packages: Blocked for all agents regardless of maturity

    Package ID format: "{package_name}:{version}" (e.g., "numpy:1.21.0", "lodash:4.17.21")
    """
    __tablename__ = "package_registry"

    # Package type constants
    PACKAGE_TYPE_PYTHON = "python"
    PACKAGE_TYPE_NPM = "npm"

    # Composite primary key: package_name:version
    id = Column(String, primary_key=True)  # Format: "numpy:1.21.0"

    # Package identification
    name = Column(String, nullable=False, index=True)  # Package name (e.g., "numpy", "lodash")
    version = Column(String, nullable=False, index=True)  # Version (e.g., "1.21.0")
    package_type = Column(String, default=PACKAGE_TYPE_PYTHON, nullable=False, index=True)  # 'python' or 'npm'

    # Governance
    min_maturity = Column(String, default="INTERN", nullable=False)  # Required maturity level
    status = Column(String, default="untrusted", nullable=False, index=True)  # untrusted, active, banned, pending
    ban_reason = Column(Text, nullable=True)  # Reason if banned

    # Approval tracking
    approved_by = Column(String, ForeignKey("users.id"), nullable=True)  # User who approved
    approved_at = Column(DateTime(timezone=True), nullable=True)  # Approval timestamp

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    approver = relationship("User", foreign_keys=[approved_by])

class CognitiveTierPreference(Base):
    """Per-workspace cognitive tier routing preferences"""
    __tablename__ = "cognitive_tier_preferences"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)

    # Tier selection
    default_tier = Column(String, nullable=False, default="standard")  # micro, standard, versatile, heavy, complex
    min_tier = Column(String, nullable=True)  # Never route below this tier
    max_tier = Column(String, nullable=True)  # Never route above this tier (cost control)

    # Cost controls
    monthly_budget_cents = Column(Integer, nullable=True)  # Budget in cents
    max_cost_per_request_cents = Column(Integer, nullable=True)  # Per-request limit

    # Feature flags
    enable_cache_aware_routing = Column(Boolean, default=True)
    enable_auto_escalation = Column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint('workspace_id', 'tenant_id', name='uq_workspace_tenant_cognitive_tier_preference'),
    )
    enable_minimax_fallback = Column(Boolean, default=True)

    # Provider preferences (ordered list)
    preferred_providers = Column(JSONColumn, default=list)  # ["deepseek", "openai"]

    # Metadata
    metadata_json = Column(JSONColumn, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    workspace = relationship("Workspace", backref="cognitive_tier_preference")


class EscalationLog(Base):
    """
    Database log of all tier escalations for analytics and auditing.

    Tracks every escalation event across the system to enable:
    - Cost analysis (which tiers are being used most)
    - Quality monitoring (how often quality triggers escalation)
    - Provider reliability (rate limiting, error rates)
    - Optimization opportunities (repeated escalations indicate model mismatch)
    """
    __tablename__ = "escalation_log"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    request_id = Column(String, nullable=False, index=True)  # Track escalations per request

    # Escalation details
    from_tier = Column(String, nullable=False)  # micro, standard, versatile, heavy, complex
    to_tier = Column(String, nullable=False)
    reason = Column(String, nullable=False)  # EscalationReason enum value
    trigger_value = Column(Float, nullable=True)  # quality_score or confidence that triggered

    # Response context
    provider_id = Column(String, nullable=True)  # openai, deepseek, etc.
    model = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    # Metadata
    prompt_length = Column(Integer, nullable=True)
    estimated_tokens = Column(Integer, nullable=True)
    metadata_json = Column(JSONColumn, nullable=True)  # Flexible context storage

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    workspace = relationship("Workspace", backref="escalation_logs")


class FFmpegJob(Base):
    """
    FFmpeg video/audio processing job tracking.

    Tracks async FFmpeg operations for video trimming, format conversion,
    audio extraction, thumbnail generation, and audio normalization.

    Enables:
    - Async job processing (long-running FFmpeg operations)
    - Progress tracking (estimated based on file size)
    - Job status monitoring (pending, running, completed, failed)
    - Audit trail for all creative tool operations
    """
    __tablename__ = "ffmpeg_job"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)

    # Operation details
    operation = Column(String, nullable=False)  # trim_video, convert_format, extract_audio, etc.
    status = Column(String, nullable=False, default="pending")  # pending, running, completed, failed
    progress = Column(Integer, default=0)  # 0-100

    # File paths (within allowed directories for security)
    input_path = Column(String, nullable=True)
    output_path = Column(String, nullable=True)

    # Metadata (operation-specific parameters)
    operation_metadata = Column(JSONColumn, nullable=True)  # {"start_time": "00:00:10", "duration": "00:01:00"}

    # Results
    result = Column(JSONColumn, nullable=True)  # {"success": true, "output_path": "..."}
    error = Column(Text, nullable=True)  # Error message if failed

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", backref="ffmpeg_jobs")


# ============================================================================
# Smart Home Integration Models (Phase 66)
# ============================================================================

class HueBridge(Base):
    """
    Philips Hue bridge connection credentials.

    Stores encrypted API keys for Hue bridge authentication.
    Uses API v2 (python-hue-v2 library) for newer bridges.

    Enables:
    - Local-only Hue control (no cloud relay)
    - Multiple bridge support per user
    - Encrypted credential storage
    - Audit trail for Hue device operations
    """
    __tablename__ = "hue_bridges"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    # Bridge identification
    bridge_ip = Column(String, nullable=False)  # Local network IP (plaintext for easy reference)
    bridge_id = Column(String, nullable=True)  # Hue bridge ID from API
    name = Column(String, nullable=True)  # User-defined name (e.g., "Living Room Bridge")

    # Encrypted credentials
    api_key = Column(String, nullable=False)  # Encrypted Hue API v2 key

    # Metadata
    last_connected_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="hue_bridges")


class HomeAssistantConnection(Base):
    """
    Home Assistant connection credentials.

    Stores encrypted long-lived access tokens for Home Assistant REST API.
    Local-only execution (no cloud relay).

    Enables:
    - Local Home Assistant control
    - Multiple instance support per user
    - Encrypted token storage
    - Audit trail for HA device operations
    """
    __tablename__ = "home_assistant_connections"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    # Connection details
    url = Column(String, nullable=False)  # Home Assistant URL (plaintext for easy reference)
    name = Column(String, nullable=True)  # User-defined name (e.g., "Home Server")

    # Encrypted credentials
    token = Column(String, nullable=False)  # Encrypted long-lived access token

    # Metadata
    last_connected_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="ha_connections")

# ============================================================================
# WebSocket Management Models
# ============================================================================

class WebSocketState(Base):
    """
    WebSocket connection state for Atom SaaS sync.

    Tracks WebSocket connection status, reconnection attempts,
    and fallback to polling mode.
    """
    __tablename__ = "websocket_state"

    id = Column(Integer, primary_key=True, default=1)

    # Connection status
    connected = Column(Boolean, default=False, nullable=False, index=True)
    ws_url = Column(String, nullable=True)

    # Timestamps
    last_connected_at = Column(DateTime(timezone=True), nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    disconnect_reason = Column(String, nullable=True)

    # Reconnection tracking
    reconnect_attempts = Column(Integer, default=0, nullable=False)
    consecutive_failures = Column(Integer, default=0, nullable=False)
    max_reconnect_attempts = Column(Integer, default=10, nullable=False)

    # Fallback mode
    fallback_to_polling = Column(Boolean, default=False, nullable=False)
    fallback_started_at = Column(DateTime(timezone=True), nullable=True)
    next_ws_attempt_at = Column(DateTime(timezone=True), nullable=True)

    # Rate limiting
    rate_limit_messages_per_sec = Column(Integer, default=100, nullable=False)

    # Admin control
    websocket_enabled = Column(Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<WebSocketState(connected={self.connected}, fallback={self.fallback_to_polling})>"


# ============================================================================
# Rating Sync Models
# ============================================================================

class FailedRatingUpload(Base):
    """
    Dead letter queue for failed rating uploads to Atom SaaS.

    Stores ratings that failed to upload so they can be retried later.
    Tracks retry count and error messages for debugging.
    """
    __tablename__ = "failed_rating_uploads"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Rating reference
    rating_id = Column(String, ForeignKey("skill_ratings.id", ondelete="CASCADE"), nullable=False, index=True)

    # Error details
    error_message = Column(Text, nullable=False)

    # Timestamps
    failed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    last_retry_at = Column(DateTime(timezone=True), nullable=True)

    # Retry tracking
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)

    # Metadata
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    rating = relationship("SkillRating", backref="failed_uploads")
    tenant = relationship("Tenant", backref="failed_rating_uploads")

    def __repr__(self):
        return f"<FailedRatingUpload(rating_id={self.rating_id}, retry_count={self.retry_count})>"


# ============================================================================
# Conflict Resolution Models
# ============================================================================

class ConflictLog(Base):
    """
    Log of skill sync conflicts between local and Atom SaaS.

    Tracks conflicts when skill data differs between local instance
    and Atom SaaS. Stores local and remote data for comparison.
    """
    __tablename__ = "conflict_log"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Skill reference
    skill_id = Column(String, ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True)

    # Conflict details
    conflict_type = Column(String, nullable=False, index=True)  # version_mismatch, data_conflict, deletion_conflict
    severity = Column(String, nullable=False, index=True)  # low, medium, high, critical

    # Data snapshots
    local_data = Column(JSONColumn, nullable=False)
    remote_data = Column(JSONColumn, nullable=False)

    # Resolution
    resolution_strategy = Column(String, nullable=True)  # remote_wins, local_wins, merge, manual
    resolved_data = Column(JSONColumn, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String, nullable=True)  # User ID or system

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Metadata
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    skill = relationship("Skill", backref="conflicts")
    tenant = relationship("Tenant", backref="conflicts")

    def __repr__(self):
        return f"<ConflictLog(id={self.id}, skill_id={self.skill_id}, type={self.conflict_type}, severity={self.severity})>"


class SkillCache(Base):
    """
    Cache for skill data from Atom SaaS.

    Stores skill data locally to reduce API calls to Atom SaaS.
    Cached data expires daily and is refreshed on-demand.
    """
    __tablename__ = "skill_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    skill_id = Column(String, nullable=False, unique=True, index=True)

    # Cached skill data
    skill_data = Column(JSONColumn, nullable=False)

    # Cache expiration
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Metadata
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Cache hit tracking
    hit_count = Column(Integer, default=0, nullable=False)
    last_hit_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant", backref="skill_cache")

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        from datetime import datetime
        return datetime.now(self.expires_at.tzinfo) > self.expires_at

    def __repr__(self):
        return f"<SkillCache(skill_id={self.skill_id}, expires_at={self.expires_at})>"


class CategoryCache(Base):
    """
    Cache for category data from Atom SaaS.

    Stores category data locally to reduce API calls to Atom SaaS.
    Cached data expires daily and is refreshed on-demand.
    """
    __tablename__ = "category_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_name = Column(String, nullable=False, unique=True, index=True)

    # Cached category data
    category_data = Column(JSONColumn, nullable=False)

    # Cache expiration
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Metadata
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Cache hit tracking
    hit_count = Column(Integer, default=0, nullable=False)
    last_hit_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant", backref="category_cache")

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        from datetime import datetime
        return datetime.now(self.expires_at.tzinfo) > self.expires_at

    def __repr__(self):
        return f"<CategoryCache(category_name={self.category_name}, expires_at={self.expires_at})>"


# ============================================================================
# GEA & Skills Models (Ported from SaaS)
# ============================================================================

# Note: Duplicate Skill class removed (was at line 7349)
# The canonical Skill definition is at line 1930
# Duplicate classes removed (were SkillVersion, SkillInstallation, AgentSkill, CanvasComponent)
# See canonical definitions at:
# - SkillVersion: line 2032
# - SkillInstallation: line 2066
# - AgentSkill: line 2136
# - CanvasComponent: line 2734

Episode = AgentEpisode  # Alias for backward compatibility


# ============================================================================
# A/B Testing Models
# ============================================================================

class ABTest(Base):
    """
    A/B Test configuration for agent experimentation.

    Supports testing different agent configurations, prompts, strategies, and tools.
    Uses deterministic hash-based variant assignment for consistent user experience.
    """
    __tablename__ = "ab_tests"

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Test configuration
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    test_type = Column(String(50), nullable=False)  # agent_config, prompt, strategy, tool
    agent_id = Column(String, ForeignKey("agent_registry.id"), nullable=False, index=True)

    # Variant configuration
    traffic_percentage = Column(Float, nullable=False, default=0.5)  # Fraction to variant B
    variant_a_name = Column(String(100), nullable=False, default="Control")
    variant_b_name = Column(String(100), nullable=False, default="Treatment")
    variant_a_config = Column(JSONColumn, nullable=False)  # Control variant config
    variant_b_config = Column(JSONColumn, nullable=False)  # Treatment variant config

    # Metrics
    primary_metric = Column(String(50), nullable=False)  # satisfaction_rate, success_rate, response_time
    secondary_metrics = Column(JSONColumn, nullable=True)  # Additional metrics to track

    # Sample size requirements
    min_sample_size = Column(Integer, nullable=False, default=100)
    confidence_level = Column(Float, nullable=False, default=0.95)  # Statistical confidence (0.0-1.0)

    # Statistical results
    variant_a_metrics = Column(JSONColumn, nullable=True)  # Calculated metrics for variant A
    variant_b_metrics = Column(JSONColumn, nullable=True)  # Calculated metrics for variant B
    statistical_significance = Column(Float, nullable=True)  # p-value
    statistical_significance_threshold = Column(Float, nullable=False, default=0.05)
    winner = Column(String(10), nullable=True)  # "A", "B", or "inconclusive"

    # Status tracking
    status = Column(String(20), nullable=False, default="draft", index=True)  # draft, running, paused, completed

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    agent = relationship("AgentRegistry", backref="ab_tests")
    participants = relationship("ABTestParticipant", back_populates="test", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ABTest(id={self.id}, name={self.name}, status={self.status})>"


class ABTestParticipant(Base):
    """
    Participant assignment for A/B tests.

    Tracks which variant each user was assigned to and their metrics.
    Ensures consistent assignment through deterministic hashing.
    """
    __tablename__ = "ab_test_participants"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    test_id = Column(String, ForeignKey("ab_tests.id"), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)

    # Variant assignment
    assigned_variant = Column(String(1), nullable=False)  # "A" or "B"
    session_id = Column(String(255), nullable=True, index=True)

    # Metrics
    success = Column(Boolean, nullable=True)  # Boolean success indicator
    metric_value = Column(Float, nullable=True)  # Numerical metric value
    meta_data = Column(JSONColumn, nullable=True)  # Additional metadata

    # Timestamps
    recorded_at = Column(DateTime(timezone=True), nullable=True)  # When metric was recorded
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    test = relationship("ABTest", back_populates="participants")

    def __repr__(self):
        return f"<ABTestParticipant(test_id={self.test_id}, user_id={self.user_id}, variant={self.assigned_variant})>"


# ============================================================================
# Sync State Models
# ============================================================================

class SyncState(Base):
    """
    Atom SaaS marketplace sync state tracking.

    Tracks the status of background sync operations with Atom SaaS marketplace.
    Used for skill synchronization, rating sync, and conflict resolution.
    """
    __tablename__ = "sync_state"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Sync status
    status = Column(String(50), nullable=False, default="idle")  # idle, syncing, error
    last_sync = Column(DateTime(timezone=True), nullable=True)

    # Cache statistics
    skills_cached = Column(Integer, nullable=False, default=0)
    categories_cached = Column(Integer, nullable=False, default=0)

    # Error tracking
    last_error = Column(Text, nullable=True)
    error_count = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    def __repr__(self):
        return f"<SyncState(id={self.id}, status={self.status}, last_sync={self.last_sync})>"




class CanvasContext(Base):
    """Stores canvas session context for agent learning and memory."""
    __tablename__ = "canvas_contexts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    canvas_id = Column(String, nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    canvas_type = Column(String, nullable=False)  # terminal, browser, desktop, etc.
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    agent_id = Column(String, nullable=True)  # Optional: which agent is active

    # Session history (all actions taken in this canvas)
    session_history = Column(JSONColumn, default=list)  # List[AgentAction]

    # User corrections (for learning)
    user_corrections = Column(JSONColumn, default=list)  # List[{original, modified, context}]

    # Current canvas state (type-specific)
    current_state = Column(JSONColumn, default=dict)

    # User preferences learned from this canvas
    user_preferences = Column(JSONColumn, default=dict)

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_activity_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User")
    tenant = relationship("Tenant")

    def __repr__(self):
        return f"<CanvasContext(id={self.id}, canvas_id={self.canvas_id}, user_id={self.user_id})>"


class CanvasRecording(Base):
    """
    Records canvas sessions for autonomous agent actions, providing
    audit trails, compliance evidence, and user review capabilities.
    """
    __tablename__ = "canvas_recordings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    recording_id = Column(String(255), nullable=False, index=True, unique=True)
    canvas_id = Column(String(255), nullable=True, index=True)
    tenant_id = Column(String(255), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(255), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(255), ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(255), nullable=True, index=True)
    
    # Recording metadata
    reason = Column(String(255), nullable=True)  # governance, autonomous_action, manual
    status = Column(String(50), default="recording", index=True)  # recording, completed, failed
    tags = Column(JSONColumn, default=list)
    recording_metadata = Column(JSONColumn, default=dict)
    
    # Timeline and summary
    events = Column(JSONColumn, default=list)  # List of timestamped events
    summary = Column(Text, nullable=True)
    event_count = Column(Integer, default=0)
    
    # Review status
    flagged_for_review = Column(Boolean, default=False, index=True)
    flag_reason = Column(Text, nullable=True)
    flagged_by = Column(String(255), nullable=True)
    flagged_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metrics
    duration_seconds = Column(Float, nullable=True)
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    stopped_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant")
    user = relationship("User")
    agent = relationship("AgentRegistry")
    reviews = relationship("CanvasRecordingReview", back_populates="recording", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CanvasRecording(id={self.id}, recording_id={self.recording_id}, status={self.status})>"


class CanvasRecordingReview(Base):
    """
    Review and adjudications for canvas recordings.
    Integrates with agent governance and learning systems.
    """
    __tablename__ = "canvas_recording_reviews"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    recording_id = Column(String, ForeignKey("canvas_recordings.recording_id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(255), ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(255), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(255), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Review details
    review_status = Column(String(50), nullable=False, index=True)  # approved, rejected, needs_changes
    overall_rating = Column(Integer, nullable=True)  # 1-5
    performance_rating = Column(Integer, nullable=True)
    safety_rating = Column(Integer, nullable=True)
    feedback = Column(Text, nullable=True)
    identified_issues = Column(JSONColumn, default=list)
    positive_patterns = Column(JSONColumn, default=list)
    lessons_learned = Column(Text, nullable=True)
    
    # Learning/Governance impact
    confidence_delta = Column(Float, default=0.0)
    promoted = Column(Boolean, default=False)
    demoted = Column(Boolean, default=False)
    governance_notes = Column(Text, nullable=True)
    
    # Status flags
    auto_reviewed = Column(Boolean, default=False)
    auto_review_confidence = Column(Float, nullable=True)
    used_for_training = Column(Boolean, default=False)
    world_model_updated = Column(Boolean, default=False)
    training_value = Column(String(50), default="low")  # low, medium, high
    
    # Metadata
    reviewed_by = Column(String(255), nullable=True)  # user_id or null for auto
    reviewed_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    recording = relationship("CanvasRecording", back_populates="reviews")
    agent = relationship("AgentRegistry")

    def __repr__(self):
        return f"<CanvasRecordingReview(id={self.id}, recording_id={self.recording_id}, status={self.review_status})>"


# =============================================================================
# ADDITIONAL DEBUG MODELS
# =============================================================================

class DebugStateSnapshot(Base):
    """
    System state snapshot for debugging.

    Captures complete system state at a point in time for debugging
    and rollback analysis.
    """
    __tablename__ = "debug_state_snapshots"

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Snapshot metadata
    component_type = Column(String(50), nullable=False, index=True)  # agent, workflow, system
    component_id = Column(String(255), nullable=False, index=True)
    snapshot_type = Column(String(50), nullable=False, index=True)  # full, incremental, checkpoint

    # State data
    state_data = Column(JSONColumn, nullable=False)  # Complete state snapshot
    snapshot_metadata = Column(JSONColumn, nullable=True)  # Additional context

    # Timestamps
    captured_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    def __repr__(self):
        return f"<DebugStateSnapshot(id={self.id}, component_id={self.component_id}, type={self.snapshot_type})>"


class DebugMetric(Base):
    """
    Debug metric for performance monitoring.

    Tracks performance metrics and debugging KPIs.
    """
    __tablename__ = "debug_metrics"

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Metric identification
    metric_name = Column(String(100), nullable=False, index=True)
    metric_type = Column(String(50), nullable=False)  # counter, gauge, histogram
    component_type = Column(String(50), nullable=False, index=True)
    component_id = Column(String(255), nullable=True, index=True)

    # Metric value
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=True)  # ms, count, percent, etc.

    # Labels/dimensions
    labels = Column(JSONColumn, nullable=True)  # Additional labels for grouping

    # Timestamps
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    def __repr__(self):
        return f"<DebugMetric(id={self.id}, name={self.metric_name}, value={self.value})>"


# =============================================================================
# FINANCIAL AUDIT MODELS (SOX Compliance & Financial Tracking)
# =============================================================================

class FinancialAudit(Base):
    """
    Financial audit trail for SOX compliance and transaction tracking.

    Records all financial operations with automatic logging via SQLAlchemy
    event listeners. Provides tamper-evidence through hash chain integration.
    """
    __tablename__ = 'financial_audits'

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Account reference
    account_id = Column(String(255), ForeignKey("financial_accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    # Operation details
    operation_type = Column(String(50), nullable=False, index=True)  # INSERT, UPDATE, DELETE
    table_name = Column(String(100), nullable=False, index=True)
    record_id = Column(String(255), nullable=True, index=True)

    # Change tracking
    old_values = Column(JSONColumn, nullable=True)  # Before state
    new_values = Column(JSONColumn, nullable=True)  # After state

    # User context (extracted from session.info)
    user_id = Column(String(255), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    agent_maturity = Column(String(50), nullable=True)  # STUDENT, INTERN, SUPERVISED, AUTONOMOUS

    # Compliance
    hash_chain = Column(String(64), nullable=True)  # SHA-256 hash chain for tamper evidence
    previous_hash = Column(String(64), nullable=True)  # Links to previous audit entry

    # Metadata
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    audit_metadata = Column(JSONColumn, nullable=True)  # Additional compliance data

    # Relationships
    account = relationship("FinancialAccount", backref="audit_trail")

    def __repr__(self):
        return f"<FinancialAudit(id={self.id}, operation_type={self.operation_type}, account_id={self.account_id})>"


class FinancialAccount(Base):
    """
    Financial account for tracking budget limits and expenses.

    Supports account hierarchy with parent-child relationships for
    departmental budget allocation and tracking.
    """
    __tablename__ = 'financial_accounts'

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Account details
    name = Column(String(255), nullable=False)
    account_type = Column(String(50), nullable=False, index=True)  # checking, savings, credit_card, expense
    parent_account_id = Column(String(255), ForeignKey("financial_accounts.id", ondelete="SET NULL"), nullable=True, index=True)

    # Balance tracking
    balance = Column(Float, nullable=False, default=0.0)
    currency = Column(String(3), nullable=False, default="USD")

    # Budget limits
    budget_limit = Column(Float, nullable=True)
    alert_threshold = Column(Float, nullable=True)  # Alert when spending exceeds % of budget

    # Status
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    status = Column(String(50), nullable=False, default="active", index=True)  # active, suspended, closed

    # Tenant
    tenant_id = Column(String(255), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Metadata
    description = Column(Text, nullable=True)
    account_metadata = Column(JSONColumn, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant", backref="financial_accounts")
    parent_account = relationship("FinancialAccount", remote_side=[id], backref="child_accounts")

    def __repr__(self):
        return f"<FinancialAccount(id={self.id}, name={self.name}, balance={self.balance})>"


class ProviderRegistry(Base):
    """Persistent provider registry with auto-discovery metadata"""
    __tablename__ = "provider_registry"

    provider_id = Column(String(50), primary_key=True)  # e.g., "openai", "anthropic", "lux"
    name = Column(String(100), nullable=False)  # Human-readable name
    description = Column(String(500))
    litellm_provider = Column(String(50))  # For mapping to LiteLLM models
    base_url = Column(String(500))  # API endpoint
    supports_vision = Column(Boolean, default=False)
    supports_tools = Column(Boolean, default=False)
    supports_cache = Column(Boolean, default=False)
    supports_structured_output = Column(Boolean, default=False)
    reasoning_level = Column(Integer)  # 1-4 scale for reasoning capability
    quality_score = Column(Float)  # Benchmark score (0-100)
    is_active = Column(Boolean, default=True, index=True)
    discovered_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    provider_metadata = Column(JSONColumn)  # Freeform provider-specific data

    # Relationship to models
    models = relationship("ModelCatalog", back_populates="provider", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ProviderRegistry(provider_id={self.provider_id}, name={self.name}, is_active={self.is_active})>"


class ModelCatalog(Base):
    """Individual models within providers"""
    __tablename__ = "model_catalog"

    model_id = Column(String(100), primary_key=True)  # e.g., "gpt-4o", "lux-1.0"
    provider_id = Column(String(50), ForeignKey("provider_registry.provider_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200))  # Human-readable model name
    description = Column(String(500))
    input_cost_per_token = Column(Float)
    output_cost_per_token = Column(Float)
    max_tokens = Column(Integer)
    max_input_tokens = Column(Integer)
    context_window = Column(Integer)
    mode = Column(String(50))  # "chat", "completion", "vision"
    capabilities = Column(JSONColumn, default=lambda: ["chat"])  # e.g., ["chat", "vision", "tools", "computer_use", "browser_use"]
    exclude_from_general_routing = Column(Boolean, default=False)  # True if not suitable for general text routing
    source = Column(String(50))  # "litellm", "openrouter", "manual"
    discovered_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    model_metadata = Column(JSONColumn)

    # Relationship to provider
    provider = relationship("ProviderRegistry", back_populates="models")

    def __repr__(self):
        return f"<ModelCatalog(model_id={self.model_id}, provider_id={self.provider_id}, mode={self.mode})>"


class EntityType(str, enum.Enum):
    VENDOR = "vendor"
    CUSTOMER = "customer"
    BOTH = "both"

class EntityTypeDefinition(Base):
    """Dynamic entity type definitions with JSON Schema storage.

    Stores tenant-customizable entity type schemas in JSON format.
    Enables runtime model generation without DDL operations.

    IMPORTANT: json_schema and available_skills use JSONBColumn for GraphRAG queries.
    These fields require PostgreSQL and won't work in SQLite tests.
    """
    __tablename__ = "entity_type_definitions"

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Multi-tenancy
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Entity type identity
    slug = Column(String(100), nullable=False)  # e.g., "invoice", "vendor"
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Schema definition (JSON) - REQUIRES PostgreSQL for JSONB query operators
    json_schema = Column(JSONBColumn, nullable=False)  # JSON Schema Draft 2020-12

    # Skill bindings (array of skill IDs) - REQUIRES PostgreSQL for JSONB queries
    available_skills = Column(JSONBColumn, nullable=True)  # ["send_email", "generate_pdf"]

    # Metadata
    is_active = Column(Boolean, default=True, nullable=False)
    is_system = Column(Boolean, default=False)  # True for 20 canonical entities
    version = Column(Integer, default=1, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Indexes for performance
    __table_args__ = (
        Index("ix_entity_types_tenant_slug", "tenant_id", "slug", unique=True),
        Index("ix_entity_types_tenant_id", "tenant_id"),
        Index("ix_entity_types_json_schema_gin", "json_schema", postgresql_using='gin'),
        Index("ix_entity_types_skills_gin", "available_skills", postgresql_using='gin'),
    )


class SkillSuggestionFeedback(Base):
    """Track user feedback on skill suggestions for learning.

    Stores user actions (approved/rejected/dismissed) on AI-suggested skill bindings.
    Enables the system to learn from feedback and improve future recommendations.
    """
    __tablename__ = "skill_suggestion_feedback"

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Multi-tenancy
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Suggestion details
    entity_type_id = Column(String, ForeignKey("entity_type_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id = Column(String, nullable=False, index=True) # Direct skill_id reference

    # Schema snapshot (what entity looked like when suggested)
    schema_features = Column(JSONColumn, nullable=False)  # {properties: [], domain_keywords: []}
    schema_hash = Column(String(64), nullable=False, index=True)  # SHA-256 of json_schema for grouping

    # User action
    action = Column(String(20), nullable=False, index=True)  # approved, rejected, dismissed
    confidence_score = Column(Float, nullable=True)  # System's confidence when suggested

    # Outcome tracking (for approved suggestions)
    usage_count = Column(Integer, default=0)  # How often the skill was used
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Performance
    suggestion_quality = Column(Float, nullable=True)  # Calculated quality score (0-1)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="skill_feedback")
    entity_type = relationship("EntityTypeDefinition", backref="skill_feedback")

    # Indexes for performance
    __table_args__ = (
        Index("ix_skill_feedback_tenant_schema", "tenant_id", "schema_hash"),
        Index("ix_skill_feedback_action", "action"),
    )

class EntityTypeVersionHistory(Base):
    """Historical snapshots of entity type schema changes.

    Stores immutable records of each schema version for audit trail
    and rollback capability. Tenant-isolated for multi-tenancy.
    """
    __tablename__ = "entity_type_version_history"

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Multi-tenancy
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Reference to entity type
    entity_type_id = Column(
        String,
        ForeignKey("entity_type_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Version snapshot data
    version = Column(Integer, nullable=False)
    json_schema = Column(JSONColumn, nullable=False)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    available_skills = Column(JSONColumn, nullable=True)

    # Change metadata
    change_summary = Column(String(500), nullable=True)
    changed_by = Column(String(255), nullable=True)
    schema_hash = Column(String(64), nullable=False)
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


# ============================================================================
# User Activity Models (for supervision routing)
# ============================================================================

class UserState(str, enum.Enum):
    """User availability state for supervision"""
    ONLINE = "online"       # Active within 5 minutes - can supervise
    AWAY = "away"          # Active 5-15 minutes ago - can supervise
    OFFLINE = "offline"     # No activity for 15+ minutes - cannot supervise


class UserActivity(Base):
    """
    Track user activity state for supervision routing.
    
    Used to determine if users are available to supervise INTERN and SUPERVISED agents.
    """
    __tablename__ = "user_activities"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(255), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    
    # State tracking
    state = Column(SQLEnum(UserState, name='userstate'), nullable=False, default=UserState.OFFLINE)
    last_activity_at = Column(DateTime(timezone=True), nullable=False)
    
    # Manual override (optional)
    manual_state = Column(SQLEnum(UserState, name='userstate_manual'), nullable=True)
    manual_state_expiry = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="activity")
    sessions = relationship("UserActivitySession", back_populates="activity", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_user_activity_user_id', 'user_id', unique=True),
        Index('idx_user_activity_state', 'state'),
    )
    
    def __repr__(self):
        return f"<UserActivity(id={self.id}, user_id={self.user_id}, state={self.state.value})>"


class UserActivitySession(Base):
    """
    Track individual user sessions (web, desktop, etc).
    
    Multiple sessions can exist per user. User is online if ANY session is recent.
    """
    __tablename__ = "user_activity_sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(255), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    activity_id = Column(String, ForeignKey('user_activities.id', ondelete='CASCADE'), nullable=False)
    
    # Session info
    session_type = Column(String(50), nullable=False, default="web")  # web, desktop, mobile
    session_token = Column(String(255), nullable=False, unique=True)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 max length
    
    # Heartbeat tracking
    last_heartbeat = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    terminated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    activity = relationship("UserActivity", back_populates="sessions")
    
    __table_args__ = (
        Index('idx_user_activity_session_token', 'session_token', unique=True),
        Index('idx_user_activity_session_user_id', 'user_id'),
        Index('idx_user_activity_session_activity_id', 'activity_id'),
        Index('idx_user_activity_session_last_heartbeat', 'last_heartbeat'),
    )
    
    def __repr__(self):
        return f"<UserActivitySession(id={self.id}, user_id={self.user_id}, type={self.session_type})>"


# Add back-reference to User model
if hasattr(User, '__mapper__'):
    User.activity = relationship("UserActivity", back_populates="user", uselist=False)


# ============================================================================
# Supervised Queue Models (for SUPERVISED agent execution)
# ============================================================================

class QueueStatus(str, enum.Enum):
    """Status of queued executions"""
    PENDING = "pending"       # Waiting for user to be available
    PROCESSING = "processing" # Currently being executed
    COMPLETED = "completed"   # Successfully executed
    FAILED = "failed"         # Execution failed
    EXPIRED = "expired"       # Queue item expired


class SupervisedExecutionQueue(Base):
    """
    Queue for SUPERVISED agent executions when users are unavailable.
    
    When SUPERVISED agents need to execute but the user is away/offline,
    executions are queued and automatically processed when the user returns.
    """
    __tablename__ = "supervised_execution_queue"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(255), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    agent_id = Column(String(255), ForeignKey('agent_registry.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(String(255), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Execution details
    trigger_type = Column(String(100), nullable=False)  # WORKFLOW_ENGINE, DATA_SYNC, etc.
    execution_context = Column(JSONColumn, nullable=False)
    priority = Column(Integer, nullable=False, default=0)
    
    # Status tracking
    status = Column(SQLEnum(QueueStatus, name='queuestatus'), nullable=False, default=QueueStatus.PENDING)
    attempts = Column(Integer, nullable=False, default=0)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    
    # Timing
    queued_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Result
    execution_result = Column(JSONColumn, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    agent = relationship("AgentRegistry", back_populates="queued_executions")
    user = relationship("User", back_populates="queued_executions")
    
    __table_args__ = (
        Index('idx_supervised_queue_status', 'status'),
        Index('idx_supervised_queue_user_id', 'user_id'),
        Index('idx_supervised_queue_agent_id', 'agent_id'),
        Index('idx_supervised_queue_expires_at', 'expires_at'),
        Index('idx_supervised_queue_priority', 'priority'),
    )
    
    def __repr__(self):
        return f"<SupervisedExecutionQueue(id={self.id}, agent_id={self.agent_id}, status={self.status.value})>"


# Add back-references
if hasattr(AgentRegistry, '__mapper__'):
    AgentRegistry.queued_executions = relationship("SupervisedExecutionQueue", back_populates="agent", cascade="all, delete-orphan")

if hasattr(User, '__mapper__'):
    User.queued_executions = relationship("SupervisedExecutionQueue", back_populates="user", cascade="all, delete-orphan")


# ============================================================================
# Integration Models (for integration catalog)
# ============================================================================

class TenantIntegrationConfig(Base):
    """
    Tenant-specific integration configuration and feature flags.
    
    Note: Ported from SaaS (backend-saas/core/models.py) with tenant_id field intact.
    Upstream needs this for multi-instance integration management.
    """
    __tablename__ = "tenant_integration_configs"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(255), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    integration_id = Column(String(100), nullable=False, index=True)  # salesforce, hubspot, slack, etc.
    
    # State
    enabled = Column(Boolean, default=True, nullable=False)
    config_json = Column(JSONColumn, default={}, nullable=False)
    
    # Metadata
    description = Column(Text, nullable=True)
    available_skills = Column(JSONColumn, nullable=True)

    # Change metadata
    change_summary = Column(String(500), nullable=True)
    changed_by = Column(String(255), nullable=True)
    schema_hash = Column(String(64), nullable=False)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


# Add back-reference to Tenant
if hasattr(Tenant, '__mapper__'):
    Tenant.integration_configs = relationship("TenantIntegrationConfig", back_populates="tenant", cascade="all, delete-orphan")


class FleetPerformanceMetric(Base):
    """
    Historical performance metrics for fleet execution.

    Stores aggregated metrics for long-term analysis and trend detection.
    Used by PerformanceMetricsService for adaptive scaling decisions.

    Note: Ported from SaaS (backend-saas/core/models.py) without tenant_id field.
    Upstream is not SaaS multi-tenant, so tenant isolation is not needed.
    """
    __tablename__ = "fleet_performance_metrics"

    # Use Integer for SQLite compatibility (BigInteger autoincrement not supported in SQLite)
    # PostgreSQL handles Integer fine (up to 2^31-1 = 2.1B records)
    id = Column(Integer, primary_key=True, autoincrement=True)
    chain_id = Column(String(255), nullable=False, index=True)
    metric_type = Column(String(50), nullable=False)  # success_rate, avg_latency, throughput
    metric_value = Column(Numeric(precision=10, scale=4), nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<FleetPerformanceMetric(chain_id={self.chain_id}, type={self.metric_type}, value={self.metric_value})>"


class FleetOverage(Base):
    """
    Track temporary fleet size expansions beyond base limits.

    Note: Ported from SaaS (backend-saas/core/models.py) without tenant_id field.
    Upstream doesn't have SaaS plan limits, so this tracks temporary expansions
    approved by users for specific delegation chains.

    SCALE-08: Users can approve temporary fleet expansion with explicit consent.
    Overages expire automatically based on expires_at timestamp.
    """
    __tablename__ = "fleet_overages"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    chain_id = Column(String(255), ForeignKey("delegation_chains.id"), nullable=False, index=True)

    # Approved temporary limit
    approved_size = Column(Integer, nullable=False)
    # Original base limit before overage
    base_limit = Column(Integer, nullable=False)

    # Expiry timestamp
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # Audit trail
    approved_by = Column(String(255), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Status tracking
    status = Column(String(50), nullable=False, default="active")  # active, expired, cancelled

    # Relationship to chain
    chain = relationship("DelegationChain", backref="fleet_overages")

    def __repr__(self):
        return f"<FleetOverage(chain={self.chain_id}, {self.base_limit}->{self.approved_size}, expires={self.expires_at})>"


class ScalingProposal(Base):
    """
    Scaling proposal for adaptive fleet sizing.

    Note: Ported from SaaS (backend-saas/core/models.py) without tenant_id field.
    Upstream doesn't have SaaS cost tracking, so cost_estimate is retained for
    informational purposes but not enforced.

    Stores expansion/contraction proposals with cost estimates and human approval workflow.
    Used by ScalingProposalService for HITL scaling decisions.
    """
    __tablename__ = "scaling_proposals"

    id = Column(String(255), primary_key=True)
    chain_id = Column(String(255), nullable=False, index=True)
    proposal_type = Column(String(50), nullable=False)  # 'expansion' or 'contraction'
    current_fleet_size = Column(Integer, nullable=False)
    proposed_fleet_size = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    metrics_json = Column(JSONColumn, nullable=True)
    cost_estimate = Column(Numeric(precision=10, scale=4), nullable=False)
    duration_hours = Column(Numeric(precision=10, scale=2), nullable=False)
    status = Column(String(50), nullable=False, default='pending', index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    approved_by = Column(String(255), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    is_proactive = Column(Boolean, nullable=True, default=False)  # True if created by predictive scaling

    def __repr__(self):
        return f"<ScalingProposal(id={self.id}, type={self.proposal_type}, current={self.current_fleet_size}, proposed={self.proposed_fleet_size}, status={self.status})>"


class ScalingAutoApproval(Base):
    """
    Auto-approval rules for scaling proposals.

    Note: Ported from SaaS (backend-saas/core/models.py) without tenant_id field.
    Upstream doesn't have SaaS multi-tenancy, so rules apply globally or per-chain.

    Defines conditions under which scaling proposals are automatically approved
    without human intervention. Rules are evaluated based on cost, fleet size,
    and performance metrics thresholds.
    """
    __tablename__ = "scaling_auto_approval_rules"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    chain_id = Column(String(255), nullable=True, index=True)  # NULL = applies to all chains
    rule_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Auto-approval conditions
    max_cost_per_hour = Column(Numeric(precision=10, scale=4), nullable=True)  # Max $/hour
    max_fleet_size = Column(Integer, nullable=True)  # Max agents
    max_size_increase = Column(Integer, nullable=True)  # Max agents to add
    min_success_rate_threshold = Column(Numeric(precision=5, scale=2), nullable=True)  # Min success rate %
    max_latency_threshold = Column(Integer, nullable=True)  # Max latency ms

    # Rule status
    is_active = Column(Boolean, nullable=False, default=True)
    priority = Column(Integer, nullable=False, default=100)  # Lower = higher priority

    # Statistics
    times_applied = Column(Integer, nullable=False, default=0)
    last_applied_at = Column(DateTime(timezone=True), nullable=True)

    # Audit
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<ScalingAutoApproval(id={self.id}, rule_name={self.rule_name})>"
