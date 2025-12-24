from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, DateTime, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from core.database import Base

class SaaSTier(Base):
    __tablename__ = "saas_tiers"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    
    name = Column(String, nullable=False) # e.g. "Pro", "Enterprise"
    base_price = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    billing_interval = Column(String, default="month") # month, year
    
    # Entitlements
    included_seats = Column(Integer, default=1)
    included_api_calls = Column(Integer, default=1000)
    included_storage_gb = Column(Float, default=10.0)
    
    # Overage Pricing
    overage_rate_seat = Column(Float, default=10.0)     # per extra seat
    overage_rate_api = Column(Float, default=0.01)      # per extra call
    overage_rate_storage = Column(Float, default=0.50)  # per extra GB
    
    # Advanced Tiered Pricing
    # Example: {"api_call": [{"limit": 10000, "rate": 0.01}, {"limit": 100000, "rate": 0.005}]}
    pricing_config = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class UsageEvent(Base):
    __tablename__ = "saas_usage_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    subscription_id = Column(String, ForeignKey("ecommerce_subscriptions.id"), nullable=False)
    
    event_type = Column(String, nullable=False) # api_call, storage_snapshot, seat_assigned
    quantity = Column(Float, default=1.0)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    metadata_json = Column(JSON, nullable=True) # Request ID, User ID, etc.

    # Relationships
    # subscription is defined in ecommerce/models.py as backref or we can add it here if needed, 
    # but usually better to stick to one side or strictly define both. 
    # For now, we will assume relationship is set up in Subscription or we just usage joins.
    subscription = relationship("Subscription", backref="usage_events")
