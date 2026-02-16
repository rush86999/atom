"""
Channel Routes - REST API for channel management.

OpenClaw Integration: Context-specific conversations (project, support, engineering, general).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from core.models import Channel, get_db

router = APIRouter(prefix="/api/channels", tags=["Channels"])


class CreateChannelRequest(BaseModel):
    name: str  # project-xyz, support, engineering
    display_name: str  # "Project XYZ", "Support", "Engineering"
    description: Optional[str] = None
    channel_type: str  # project, support, engineering, general
    is_public: bool = True
    created_by: str  # user_id
    agent_members: List[str] = []
    user_members: List[str] = []


class UpdateChannelRequest(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None
    agent_members: Optional[List[str]] = None
    user_members: Optional[List[str]] = None


class ChannelResponse(BaseModel):
    id: str
    name: str
    display_name: str
    description: Optional[str]
    channel_type: str
    is_public: bool
    created_by: str
    agent_members: List[str]
    user_members: List[str]
    created_at: str


@router.post("/", response_model=ChannelResponse)
async def create_channel(
    request: CreateChannelRequest,
    db: Session = Depends(get_db)
):
    """
    Create new channel.

    **Channel Types:**
    - project: Project-specific discussions
    - support: Customer support coordination
    - engineering: Technical discussions
    - general: Default public channel

    **Access Control:**
    - Humans can create channels
    - is_public=false for private channels
    - agent_members and user_members control access
    """
    # Check if channel name already exists
    existing = db.query(Channel).filter(Channel.name == request.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Channel {request.name} already exists")

    # Validate channel_type
    valid_types = ["project", "support", "engineering", "general"]
    if request.channel_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid channel_type '{request.channel_type}'. Must be one of: {', '.join(valid_types)}"
        )

    channel = Channel(
        name=request.name,
        display_name=request.display_name,
        description=request.description,
        channel_type=request.channel_type,
        is_public=request.is_public,
        created_by=request.created_by,
        agent_members=request.agent_members,
        user_members=request.user_members
    )

    db.add(channel)
    db.commit()
    db.refresh(channel)

    return ChannelResponse(
        id=channel.id,
        name=channel.name,
        display_name=channel.display_name,
        description=channel.description,
        channel_type=channel.channel_type,
        is_public=channel.is_public,
        created_by=channel.created_by,
        agent_members=channel.agent_members,
        user_members=channel.user_members,
        created_at=channel.created_at.isoformat()
    )


@router.get("/", response_model=List[ChannelResponse])
async def list_channels(
    channel_type: Optional[str] = None,
    is_public: Optional[bool] = None,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    List all channels.

    **Filters:**
    - channel_type: Filter by type (project, support, engineering, general)
    - is_public: Filter by public/private
    - Pagination: limit + offset
    """
    query = db.query(Channel)

    if channel_type:
        query = query.filter(Channel.channel_type == channel_type)

    if is_public is not None:
        query = query.filter(Channel.is_public == is_public)

    channels = query.order_by(Channel.created_at.desc()).offset(offset).limit(limit).all()

    return [
        ChannelResponse(
            id=c.id,
            name=c.name,
            display_name=c.display_name,
            description=c.description,
            channel_type=c.channel_type,
            is_public=c.is_public,
            created_by=c.created_by,
            agent_members=c.agent_members,
            user_members=c.user_members,
            created_at=c.created_at.isoformat()
        )
        for c in channels
    ]


@router.get("/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: str,
    db: Session = Depends(get_db)
):
    """
    Get channel by ID.
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()

    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")

    return ChannelResponse(
        id=channel.id,
        name=channel.name,
        display_name=channel.display_name,
        description=channel.description,
        channel_type=channel.channel_type,
        is_public=channel.is_public,
        created_by=channel.created_by,
        agent_members=channel.agent_members,
        user_members=channel.user_members,
        created_at=channel.created_at.isoformat()
    )


@router.put("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: str,
    request: UpdateChannelRequest,
    db: Session = Depends(get_db)
):
    """
    Update channel.

    Only update fields that are provided.
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()

    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")

    if request.display_name is not None:
        channel.display_name = request.display_name

    if request.description is not None:
        channel.description = request.description

    if request.is_public is not None:
        channel.is_public = request.is_public

    if request.agent_members is not None:
        channel.agent_members = request.agent_members

    if request.user_members is not None:
        channel.user_members = request.user_members

    db.commit()
    db.refresh(channel)

    return ChannelResponse(
        id=channel.id,
        name=channel.name,
        display_name=channel.display_name,
        description=channel.description,
        channel_type=channel.channel_type,
        is_public=channel.is_public,
        created_by=channel.created_by,
        agent_members=channel.agent_members,
        user_members=channel.user_members,
        created_at=channel.created_at.isoformat()
    )


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete channel.

    **Warning:** This will also delete all posts in this channel.
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()

    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")

    db.delete(channel)
    db.commit()

    return {"message": f"Channel {channel_id} deleted"}


@router.post("/{channel_id}/members")
async def add_channel_member(
    channel_id: str,
    member_type: str,  # "agent" or "user"
    member_id: str,
    db: Session = Depends(get_db)
):
    """
    Add member to channel.

    ** member_type: "agent" or "user"
    ** member_id: agent_id or user_id
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()

    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")

    if member_type == "agent":
        if member_id not in channel.agent_members:
            channel.agent_members.append(member_id)
    elif member_type == "user":
        if member_id not in channel.user_members:
            channel.user_members.append(member_id)
    else:
        raise HTTPException(status_code=400, detail=f"Invalid member_type '{member_type}'. Must be 'agent' or 'user'")

    db.commit()
    db.refresh(channel)

    return {
        "message": f"Added {member_type} {member_id} to channel {channel_id}",
        "agent_members": channel.agent_members,
        "user_members": channel.user_members
    }


@router.delete("/{channel_id}/members")
async def remove_channel_member(
    channel_id: str,
    member_type: str,  # "agent" or "user"
    member_id: str,
    db: Session = Depends(get_db)
):
    """
    Remove member from channel.

    ** member_type: "agent" or "user"
    ** member_id: agent_id or user_id
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()

    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")

    if member_type == "agent":
        if member_id in channel.agent_members:
            channel.agent_members.remove(member_id)
    elif member_type == "user":
        if member_id in channel.user_members:
            channel.user_members.remove(member_id)
    else:
        raise HTTPException(status_code=400, detail=f"Invalid member_type '{member_type}'. Must be 'agent' or 'user'")

    db.commit()
    db.refresh(channel)

    return {
        "message": f"Removed {member_type} {member_id} from channel {channel_id}",
        "agent_members": channel.agent_members,
        "user_members": channel.user_members
    }
