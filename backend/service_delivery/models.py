from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, DateTime, Enum as SQLEnum, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
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

class Contract(Base):
    __tablename__ = "service_contracts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    deal_id = Column(String, ForeignKey("sales_deals.id"), nullable=True) 
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
    projects = relationship("Project", back_populates="contract")

class Project(Base):
    __tablename__ = "service_projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    contract_id = Column(String, ForeignKey("service_contracts.id"), nullable=False)
    
    name = Column(String, nullable=False)
    status = Column(SQLEnum(ProjectStatus), default=ProjectStatus.PENDING)
    
    description = Column(Text, nullable=True)
    
    # Financial Controls
    budget_hours = Column(Float, default=0.0)
    actual_hours = Column(Float, default=0.0)
    
    risk_level = Column(String, default="low") # auto-calculated
    
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
    due_date = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    invoice_id = Column(String, nullable=True) # Linked Invoice ID once generated
    
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    project = relationship("Project", back_populates="milestones")
