
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.models import TeamMessage, User
from core.websockets import manager

router = APIRouter(prefix="/api/teams", tags=["Team Messaging"])

class MessageCreate(BaseModel):
    content: str
    context_type: Optional[str] = None
    context_id: Optional[str] = None

class MessageResponse(BaseModel):
    id: str
    team_id: str
    user_id: str
    sender_name: str
    content: str
    context_type: Optional[str]
    context_id: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True

@router.post("/{team_id}/messages", response_model=MessageResponse)
async def send_message(
    team_id: str, 
    message_data: MessageCreate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify user is in team (skip for now or implement check)
    # if team_id not in [t.id for t in current_user.teams]:
    #     raise HTTPException(status_code=403, detail="Not a member of this team")

    new_message = TeamMessage(
        team_id=team_id,
        user_id=current_user.id,
        content=message_data.content,
        context_type=message_data.context_type,
        context_id=message_data.context_id
    )
    
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    
    # Construct response
    response = MessageResponse(
        id=new_message.id,
        team_id=new_message.team_id,
        user_id=new_message.user_id,
        sender_name=f"{current_user.first_name} {current_user.last_name}",
        content=new_message.content,
        context_type=new_message.context_type,
        context_id=new_message.context_id,
        created_at=new_message.created_at
    )
    
    # Broadcast to team channel
    await manager.broadcast(f"team:{team_id}", {
        "type": "message.received",
        "data": response.dict(by_alias=True) # Pydantic v1/v2 compat
    })
    
    return response

@router.get("/{team_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    team_id: str, 
    context_type: Optional[str] = None,
    context_id: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(TeamMessage).filter(TeamMessage.team_id == team_id)
    
    if context_type:
        query = query.filter(TeamMessage.context_type == context_type)
    if context_id:
        query = query.filter(TeamMessage.context_id == context_id)
        
    messages = query.order_by(TeamMessage.created_at.desc()).limit(limit).all()
    
    # Convert to response model with sender name
    return [
        MessageResponse(
            id=m.id,
            team_id=m.team_id,
            user_id=m.user_id,
            sender_name=f"{m.sender.first_name} {m.sender.last_name}" if m.sender else "Unknown",
            content=m.content,
            context_type=m.context_type,
            context_id=m.context_id,
            created_at=m.created_at
        ) for m in messages
    ]
