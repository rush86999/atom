from sqlalchemy import Column, String, Float, DateTime, Text, JSON, Boolean, func
from core.database import Base
import uuid
import datetime

class WorkflowExecutionLog(Base):
    """
    Sidecar table for high-volume workflow execution metrics.
    Decoupled from the main transactional data to allow for aggregation without locking.
    """
    __tablename__ = "analytics_workflow_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Core linkage
    execution_id = Column(String, index=True, nullable=False)
    workflow_id = Column(String, index=True, nullable=False)
    step_id = Column(String, index=True, nullable=False)
    step_type = Column(String, nullable=False)
    
    # Metrics
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    duration_ms = Column(Float, nullable=False)
    
    # Outcome
    status = Column(String, nullable=False) # completed, failed
    error_code = Column(String, nullable=True)
    
    # Detailed Data (Nullable to save space/meta only)
    trigger_data = Column(JSON, nullable=True) # Inputs
    results = Column(JSON, nullable=True)      # Outputs
    
    # Lightweight Meta (No heavy inputs/outputs)
    meta_info = Column(JSON, nullable=True) # { "token_usage": 150, "retries": 1 }
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
