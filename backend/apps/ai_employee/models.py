from sqlalchemy import Column, String, JSON, DateTime, ForeignKey
from sqlalchemy.sql import func
from core.database import Base

class EmployeeWorkspace(Base):
    """
    Persistent workspace state for an AI Employee.
    Stores canvas state, sub-tasks, and editor content.
    """
    __tablename__ = "employee_workspaces"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)
    agent_id = Column(String, index=True)
    
    # Store the full canvas state as JSON
    # This matches the structure needed by UseCanvasState.ts
    workspace_state = Column(JSON, nullable=False)
    
    # Track deliverables/artifacts separately if needed
    deliverables = Column(JSON, default=list)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<EmployeeWorkspace(id={self.id}, user_id={self.user_id})>"
