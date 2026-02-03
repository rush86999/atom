
from sqlalchemy import Column, String, Text, DateTime, UniqueConstraint
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from core.database import Base
import uuid
import json

class UserPreference(Base):
    __tablename__ = "user_preferences"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    workspace_id = Column(String, nullable=False, index=True)
    key = Column(String, nullable=False)
    value = Column(Text, nullable=True) # Stored as JSON string or raw text
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('user_id', 'workspace_id', 'key', name='uix_user_workspace_key'),
    )

class UserPreferenceService:
    def __init__(self, db: Session):
        self.db = db

    def set_preference(self, user_id: str, workspace_id: str, key: str, value: any):
        """Set a user preference for a specific workspace. Value is JSON encoded."""
        # Check if exists
        existing = self.db.query(UserPreference).filter_by(
            user_id=user_id, workspace_id=workspace_id, key=key
        ).first()

        json_val = json.dumps(value)

        if existing:
            existing.value = json_val
        else:
            new_pref = UserPreference(
                user_id=user_id,
                workspace_id=workspace_id,
                key=key,
                value=json_val
            )
            self.db.add(new_pref)
        
        try:
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise e

    def get_preference(self, user_id: str, workspace_id: str, key: str, default: any = None):
        """Get a specific preference."""
        pref = self.db.query(UserPreference).filter_by(
            user_id=user_id, workspace_id=workspace_id, key=key
        ).first()

        if pref and pref.value:
            try:
                return json.loads(pref.value)
            except json.JSONDecodeError as e:
                logger.debug(f"Failed to parse preference as JSON: {e}")
                return pref.value # Fallback to raw string if not JSON
        return default

    def get_all_preferences(self, user_id: str, workspace_id: str):
        """Get all preferences for this context."""
        prefs = self.db.query(UserPreference).filter_by(
            user_id=user_id, workspace_id=workspace_id
        ).all()
        
        result = {}
        for p in prefs:
            try:
                result[p.key] = json.loads(p.value)
            except json.JSONDecodeError as e:
                logger.debug(f"Failed to parse preference {p.key} as JSON: {e}")
                result[p.key] = p.value
        return result
