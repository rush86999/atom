from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, DateTime, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from core.database import Base

class EcommerceCustomer(Base):
    __tablename__ = "ecommerce_customers"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    external_id = Column(String, nullable=True, index=True) # Shopify Customer ID
    email = Column(String, nullable=False, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    
    # Cross-System Linking (Identified by Resolver)
    crm_contact_id = Column(String, nullable=True)
    accounting_entity_id = Column(String, nullable=True)
    
    # Intelligence
    risk_score = Column(Float, default=0.0) # 0 to 100
    risk_level = Column(String, default="low") # low, medium, high
    
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    orders = relationship("EcommerceOrder", back_populates="customer")
    subscriptions = relationship("Subscription", back_populates="customer")

class EcommerceOrder(Base):
    __tablename__ = "ecommerce_orders"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    customer_id = Column(String, ForeignKey("ecommerce_customers.id"), nullable=False)
    external_id = Column(String, nullable=True, index=True) # Shopify Order ID
    subscription_id = Column(String, ForeignKey("ecommerce_subscriptions.id"), nullable=True)
    order_number = Column(String, nullable=True)
    
    status = Column(String, default="pending") # pending, paid, fulfilled, cancelled, refunded
    currency = Column(String, default="USD")
    
    # Financial Breakdown
    total_price = Column(Float, default=0.0)
    subtotal_price = Column(Float, default=0.0)
    total_tax = Column(Float, default=0.0)
    total_shipping = Column(Float, default=0.0)
    total_discounts = Column(Float, default=0.0)
    
    # Ledger Sync Status
    ledger_transaction_id = Column(String, nullable=True) # ID in accounting_transactions
    is_ledger_synced = Column(Boolean, default=False)
    
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
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
    tax_amount = Column(Float, default=0.0)
    
    metadata_json = Column(JSON, nullable=True)

    # Relationships
    order = relationship("EcommerceOrder", back_populates="items")

class Subscription(Base):
    __tablename__ = "ecommerce_subscriptions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    customer_id = Column(String, ForeignKey("ecommerce_customers.id"), nullable=False)
    external_id = Column(String, nullable=True, index=True) # Shopify/Stripe Sub ID
    
    status = Column(String, default="active") # active, trial, past_due, canceled
    plan_name = Column(String, nullable=True)
    mrr = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    
    billing_interval = Column(String, default="month") # month, year
    next_billing_at = Column(DateTime(timezone=True), nullable=True)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # SaaS Fields
    tier_id = Column(String, ForeignKey("saas_tiers.id"), nullable=True)
    current_period_usage = Column(JSON, nullable=True) # Cache: {api_calls: 100, seats: 2}

    # Relationships
    customer = relationship("EcommerceCustomer", back_populates="subscriptions")
    orders = relationship("EcommerceOrder", back_populates="subscription")
    audit_logs = relationship("SubscriptionAudit", back_populates="subscription")
    tier = relationship("SaaSTier")

class SubscriptionAudit(Base):
    __tablename__ = "ecommerce_subscription_audit"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    subscription_id = Column(String, ForeignKey("ecommerce_subscriptions.id"), nullable=False)
    
    event_type = Column(String, nullable=False) # renewal, upgrade, downgrade, churn
    previous_mrr = Column(Float, default=0.0)
    new_mrr = Column(Float, default=0.0)
    
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    subscription = relationship("Subscription", back_populates="audit_logs")
