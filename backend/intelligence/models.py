import uuid
from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class ClientHealthScore(Base):
    __tablename__ = "intelligence_client_health"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    client_entity_id = Column(String, ForeignKey("accounting_entities.id"), nullable=False)
    
    overall_score = Column(Float, default=0.0) # 0-100
    
    # Component Scores
    sentiment_score = Column(Float, default=0.0)
    financial_score = Column(Float, default=0.0)
    usage_score = Column(Float, default=0.0)
    
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())
    metadata_json = Column(JSON, nullable=True) # Drill-down reasons

class ResourceRole(Base):
    __tablename__ = "intelligence_resource_roles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    
    name = Column(String, nullable=False) # e.g. "Senior Dev"
    hourly_cost = Column(Float, default=0.0)
    billable_target = Column(Float, default=0.80) # % utilization target
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CapacityPlan(Base):
    __tablename__ = "intelligence_capacity_plans"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    role_id = Column(String, ForeignKey("intelligence_resource_roles.id"), nullable=False)
    
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    available_hours = Column(Float, default=0.0) # Total headcount capacity
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    role = relationship("ResourceRole")

class BusinessScenario(Base):
    __tablename__ = "intelligence_business_scenarios"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    parameters_json = Column(JSON, nullable=True) # Input: {"hires": 5}
    impact_json = Column(JSON, nullable=True)     # Output: {"cash_burn": 50000}
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
