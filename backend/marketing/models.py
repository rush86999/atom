import enum
import uuid
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
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    name = Column(String, nullable=False) # e.g., "Google Ads", "LinkedIn Ads"
    type = Column(SQLEnum(ChannelType), nullable=False)
    status = Column(String, default="active")
    
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AdSpendEntry(Base):
    __tablename__ = "marketing_ad_spend"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    channel_id = Column(String, ForeignKey("marketing_channels.id"), nullable=False)
    
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    date = Column(DateTime(timezone=True), nullable=False)
    
    # Metrics from the platform
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AttributionEvent(Base):
    __tablename__ = "marketing_attribution_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    lead_id = Column(String, ForeignKey("sales_leads.id"), nullable=False)
    channel_id = Column(String, ForeignKey("marketing_channels.id"), nullable=True)
    
    event_type = Column(String, nullable=False) # "touchpoint", "conversion"
    touchpoint_order = Column(Integer, default=1) # 1 for first touch, etc.
    
    source = Column(String, nullable=True) # utm_source
    medium = Column(String, nullable=True) # utm_medium
    campaign = Column(String, nullable=True) # utm_campaign
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    metadata_json = Column(JSON, nullable=True)
