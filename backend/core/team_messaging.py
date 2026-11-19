
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.models import Team, TeamMessage, User, Workspace

router = APIRouter(prefix="/api/teams", tags=["Team Messaging"])

# A single opaque response for every authorization/missing-team case prevents
# callers from using these routes to discover teams outside their scope.
TEAM_NOT_FOUND_DETAIL = "Team not found"

# Keep history requests bounded even if a client supplies an enormous limit.
MAX_HISTORY_LIMIT = 100

# Reject blank or oversized writes at the request-validation layer only.  Older
# stored records are still returned verbatim because the response model has no
# content constraints.
MAX_MESSAGE_LENGTH = 8000


class MessageCreate(BaseModel):
    content: str
    context_type: Optional[str] = None
    context_id: Optional[str] = None

    @field_validator("content")
    @classmethod
    def _validate_content(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Message content must not be blank")
        if len(value) > MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"Message content must be at most {MAX_MESSAGE_LENGTH} characters"
            )
        # Return the original text so nonblank formatting is preserved.
        return value


class MessageResponse(BaseModel):
    id: str
    team_id: str
    user_id: str
    sender_name: str
    content: str
    context_type: Optional[str]
    context_id: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeamSummary(BaseModel):
    """The only team fields exposed by the membership listing."""

    id: str
    name: str

    model_config = ConfigDict(from_attributes=True)


def _team_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=TEAM_NOT_FOUND_DETAIL,
    )


def _scoped_team_query(db: Session, current_user: User):
    """Return the one membership/workspace/tenant query for the caller's scope.

    Both the team listing and per-team authorization use this definition, so
    the access rules cannot drift.  ``None`` means the caller has no usable
    current scope and therefore sees no teams.
    """
    if not current_user:
        return None

    workspace_id = getattr(current_user, "workspace_id", None)
    tenant_id = getattr(current_user, "tenant_id", None)
    if not workspace_id or not tenant_id:
        return None

    return (
        db.query(Team)
        .join(Workspace, Workspace.id == Team.workspace_id)
        .filter(
            Team.workspace_id == workspace_id,
            Workspace.tenant_id == tenant_id,
            Team.members.any(User.id == current_user.id),
        )
    )


def _get_authorized_team(
    db: Session,
    team_id: str,
    current_user: User,
) -> Optional[Team]:
    """Return the team only when it is inside the caller's scoped query.

    Any mismatch, including a genuinely missing team, returns ``None`` so
    callers can emit the same fixed 404.
    """
    query = _scoped_team_query(db, current_user)
    if query is None:
        return None
    return query.filter(Team.id == team_id).first()


def _bounded_history_limit(limit: int) -> int:
    """Clamp a requested history limit to a safe positive range."""
    try:
        requested = int(limit)
    except (TypeError, ValueError):
        requested = 50
    return max(1, min(requested, MAX_HISTORY_LIMIT))


@router.get("/mine", response_model=List[TeamSummary])
async def get_my_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List only teams the caller may access in their current scope."""
    query = _scoped_team_query(db, current_user)
    if query is None:
        return []

    teams = query.order_by(Team.name.asc(), Team.id.asc()).all()

    return [TeamSummary(id=team.id, name=team.name) for team in teams]


@router.post("/{team_id}/messages", response_model=MessageResponse)
async def send_message(
    team_id: str,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Authorize before constructing or persisting the confidential message.
    if _get_authorized_team(db, team_id, current_user) is None:
        raise _team_not_found()

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

    # The unscoped shared channel cannot carry confidential team text, so the
    # message is deliberately not published outside the authorized team scope.
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
    # Authorize before reading any message content.
    if _get_authorized_team(db, team_id, current_user) is None:
        raise _team_not_found()

    bounded_limit = _bounded_history_limit(limit)
    query = db.query(TeamMessage).filter(TeamMessage.team_id == team_id)

    if context_type:
        query = query.filter(TeamMessage.context_type == context_type)
    if context_id:
        query = query.filter(TeamMessage.context_id == context_id)

    messages = query.order_by(TeamMessage.created_at.desc()).limit(bounded_limit).all()

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
