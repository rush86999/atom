
from datetime import datetime
from typing import List, Optional
from enum import Enum

from sqlalchemy import String, Integer, Boolean, ForeignKey, DateTime, Text, Table, Column
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func

class Base(DeclarativeBase):
    pass

# Association table for User-Team many-to-many relationship
team_members = Table(
    "team_members",
    Base.metadata,
    Column("user_id", String, ForeignKey("users.id"), primary_key=True),
    Column("team_id", String, ForeignKey("teams.id"), primary_key=True),
    Column("joined_at", DateTime, default=datetime.utcnow),
)

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String)
    last_name: Mapped[str] = mapped_column(String)
    hashed_password: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, default="member")
    status: Mapped[str] = mapped_column(String, default="active")
    workspace_id: Mapped[Optional[str]] = mapped_column(ForeignKey("workspaces.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    workspace: Mapped[Optional["Workspace"]] = relationship(back_populates="users")
    teams: Mapped[List["Team"]] = relationship(secondary=team_members, back_populates="members")
    audit_logs: Mapped[List["AuditLog"]] = relationship(back_populates="user")

class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="active")
    plan_tier: Mapped[str] = mapped_column(String, default="standard")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users: Mapped[List["User"]] = relationship(back_populates="workspace")
    teams: Mapped[List["Team"]] = relationship(back_populates="workspace")

class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="teams")
    members: Mapped[List["User"]] = relationship(secondary=team_members, back_populates="teams")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_type: Mapped[str] = mapped_column(String)
    security_level: Mapped[str] = mapped_column(String)
    threat_level: Mapped[str] = mapped_column(String, default="normal")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    user_email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    workspace_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    resource: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # Storing JSON as text for simplicity in SQLite/Postgres compatibility
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped[Optional["User"]] = relationship(back_populates="audit_logs")
