import enum
import uuid
import accounting.models  # Ensure Entity is registered for relationships

# Import Deal for relationship resolution
from sales.models import Deal
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class ContractType(str, enum.Enum):
    FIXED_FEE = "fixed_fee"
    RETAINER = "retainer"
    TIME_MATERIAL = "time_material"

class ProjectStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED_PAYMENT = "paused_payment" # Payment Aware Delivery Control
    PAUSED_CLIENT = "paused_client"
    COMPLETED = "completed"
    CANCELED = "canceled"

class MilestoneStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed" # Work done
    APPROVED = "approved"   # Client signed off
    INVOICED = "invoiced"   # Sent to billing

class BudgetStatus(str, enum.Enum):
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    OVER_BUDGET = "over_budget"

class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    CANCELED = "canceled"

class Contract(Base):
    __tablename__ = "service_contracts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    deal_id = Column(String, ForeignKey("sales_deals.id"), nullable=True) 
    product_service_id = Column(String, ForeignKey("business_product_services.id"), nullable=True)
    # Link to Deal is crucial for Deal -> Contract automation
    
    name = Column(String, nullable=False)
    type = Column(SQLEnum(ContractType), default=ContractType.FIXED_FEE)
    total_amount = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    deal = relationship("Deal") # Assuming Deal model is imported where used or using string
    product_service = relationship("BusinessProductService")
    projects = relationship("Project", back_populates="contract")

class Project(Base):
    __tablename__ = "service_projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    contract_id = Column(String, ForeignKey("service_contracts.id"), nullable=True)
    
    name = Column(String, nullable=False)
    status = Column(SQLEnum(ProjectStatus), default=ProjectStatus.PENDING)
    
    description = Column(Text, nullable=True)
    
    # Financial Controls
    budget_hours = Column(Float, default=0.0)
    actual_hours = Column(Float, default=0.0)
    budget_amount = Column(Float, default=0.0) # Total financial budget
    actual_burn = Column(Float, default=0.0) # Total costs (labor + expenses)
    budget_status = Column(SQLEnum(BudgetStatus), default=BudgetStatus.ON_TRACK)
    
    priority = Column(String, default="medium") # low, medium, high, critical
    project_type = Column(String, default="general")
    
    planned_start_date = Column(DateTime(timezone=True), nullable=True)
    planned_end_date = Column(DateTime(timezone=True), nullable=True)
    actual_start_date = Column(DateTime(timezone=True), nullable=True)
    actual_end_date = Column(DateTime(timezone=True), nullable=True)
    
    risk_level = Column(String, default="low") # auto-calculated
    predicted_end_date = Column(DateTime(timezone=True), nullable=True)
    risk_score = Column(Float, default=0.0) # 0 to 100
    risk_rationale = Column(Text, nullable=True)
    
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    contract = relationship("Contract", back_populates="projects")
    milestones = relationship("Milestone", back_populates="project")

class Milestone(Base):
    __tablename__ = "service_milestones"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    project_id = Column(String, ForeignKey("service_projects.id"), nullable=False)
    
    name = Column(String, nullable=False)
    amount = Column(Float, default=0.0) # Billing amount
    percentage = Column(Float, default=0.0) # % of contract
    
    status = Column(SQLEnum(MilestoneStatus), default=MilestoneStatus.PENDING)
    order = Column(Integer, default=0) # For sequential tracking
    
    # Financial Controls
    actual_burn = Column(Float, default=0.0)
    budget_status = Column(SQLEnum(BudgetStatus), default=BudgetStatus.ON_TRACK)
    
    planned_start_date = Column(DateTime(timezone=True), nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    invoice_id = Column(String, nullable=True) # Linked Invoice ID once generated
    
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    project = relationship("Project", back_populates="milestones")
    tasks = relationship("ProjectTask", back_populates="milestone")

class ProjectTask(Base):
    __tablename__ = "service_tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    project_id = Column(String, ForeignKey("service_projects.id"), nullable=False)
    milestone_id = Column(String, ForeignKey("service_milestones.id"), nullable=False)
    
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="pending") # pending, in_progress, completed, blocked
    
    assigned_to = Column(String, ForeignKey("users.id"), nullable=True)
    
    due_date = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    actual_hours = Column(Float, default=0.0)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    milestone = relationship("Milestone", back_populates="tasks")
    assignee = relationship("User")

class Appointment(Base):
    """Tracks service engagements for small businesses"""
    __tablename__ = "service_appointments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    customer_id = Column(String, ForeignKey("accounting_entities.id"), nullable=False)
    service_id = Column(String, ForeignKey("business_product_services.id"), nullable=True)
    
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    
    status = Column(SQLEnum(AppointmentStatus), default=AppointmentStatus.SCHEDULED)
    
    deposit_amount = Column(Float, default=0.0)
    is_deposit_paid = Column(Boolean, default=False)
    
    notes = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True) # Travel heuristics, etc.
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    workspace = relationship("Workspace")
    customer = relationship("Entity")
    service = relationship("core.models.BusinessProductService")
