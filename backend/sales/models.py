from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, DateTime, Text, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from core.database import Base

class LeadStatus(str, enum.Enum):
    NEW = "new"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"
    CONTACTED = "contacted"
    SPAM = "spam"

class DealStage(str, enum.Enum):
    DISCOVERY = "discovery"
    QUALIFICATION = "qualification"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"

class CommissionStatus(str, enum.Enum):
    ACCRUED = "accrued"
    APPROVED = "approved"
    PAID = "paid"
    CANCELLED = "cancelled"

class Lead(Base):
    __tablename__ = "sales_leads"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    external_id = Column(String, nullable=True, index=True) # HubSpot/Salesforce ID
    email = Column(String, nullable=False)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    company = Column(String, nullable=True)
    source = Column(String, nullable=True) # Website, LinkedIn, etc.
    status = Column(SQLEnum(LeadStatus), default=LeadStatus.NEW)
    
    # AI Enrichment
    ai_score = Column(Float, default=0.0)
    ai_qualification_summary = Column(Text, nullable=True)
    is_spam = Column(Boolean, default=False)
    is_converted = Column(Boolean, default=False)
    
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Deal(Base):
    __tablename__ = "sales_deals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    external_id = Column(String, nullable=True, index=True)
    name = Column(String, nullable=False)
    value = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    stage = Column(SQLEnum(DealStage), default=DealStage.DISCOVERY)
    probability = Column(Float, default=0.0)
    
    # Intelligence
    health_score = Column(Float, default=0.0) # 0 to 100
    risk_level = Column(String, default="low") # low, medium, high
    last_engagement_at = Column(DateTime(timezone=True), nullable=True)
    
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    transcripts = relationship("CallTranscript", back_populates="deal")
    commissions = relationship("CommissionEntry", back_populates="deal")

class CommissionEntry(Base):
    __tablename__ = "sales_commissions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    deal_id = Column(String, ForeignKey("sales_deals.id"), nullable=False)
    invoice_id = Column(String, nullable=True) # Linked accounting invoice
    
    payee_id = Column(String, nullable=True) # User/Rep ID
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    status = Column(SQLEnum(CommissionStatus), default=CommissionStatus.ACCRUED)
    
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)
    
    metadata_json = Column(JSON, nullable=True)

    # Relationships
    deal = relationship("Deal", back_populates="commissions")

class CallTranscript(Base):
    __tablename__ = "sales_call_transcripts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    deal_id = Column(String, ForeignKey("sales_deals.id"), nullable=True)
    meeting_id = Column(String, nullable=True) # Zoom/Teams ID
    
    title = Column(String, nullable=True)
    raw_transcript = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    objections = Column(JSON, nullable=True) # List of extracted objections
    action_items = Column(JSON, nullable=True) # List of extracted tasks
    metadata_json = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    deal = relationship("Deal", back_populates="transcripts")

class FollowUpTask(Base):
    __tablename__ = "sales_follow_up_tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    deal_id = Column(String, ForeignKey("sales_deals.id"), nullable=False)
    
    description = Column(Text, nullable=False)
    suggested_date = Column(DateTime(timezone=True), nullable=True)
    is_completed = Column(Boolean, default=False)
    
    # Reason why AI suggested this
    ai_rationale = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
